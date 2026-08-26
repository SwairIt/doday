"""REST ИИ-помощника: справочник провайдеров и ключ пользователя."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from app.ai import chat as ai_chat
from app.ai import service as ai_service
from app.ai.client import AiProviderError, stream_completion, verify_key
from app.ai.models import AiCredential
from app.ai.prompts import TEMPLATES
from app.ai.providers import PROVIDERS
from app.ai.safety import find_personal_data, is_unsafe_for_children
from app.ai.schemas import (
    AskIn,
    ChatStateOut,
    CredentialIn,
    CredentialOut,
    MessageOut,
    ProviderOut,
)
from app.ai.service import UnknownProvider
from app.auth.deps import DbSession, RequiredUser

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _to_out(cred: AiCredential) -> CredentialOut:
    return CredentialOut(
        provider=cred.provider,
        base_url=cred.base_url,
        model=cred.model,
        key_last4=cred.key_last4,
    )


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(user: RequiredUser) -> list[ProviderOut]:
    return [ProviderOut(**asdict(p)) for p in PROVIDERS]


@router.get("/credential", response_model=CredentialOut | None)
async def read_credential(user: RequiredUser, session: DbSession) -> CredentialOut | None:
    cred = await ai_service.get_credential(session, user.id)
    return None if cred is None else _to_out(cred)


@router.put("/credential", response_model=CredentialOut)
async def save_credential(
    payload: CredentialIn, user: RequiredUser, session: DbSession
) -> CredentialOut:
    try:
        cred = await ai_service.upsert_credential(
            session,
            user.id,
            provider=payload.provider,
            api_key=payload.api_key,
            model=payload.model,
            base_url=payload.base_url,
        )
    except UnknownProvider as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _to_out(cred)


@router.delete("/credential", status_code=status.HTTP_204_NO_CONTENT)
async def remove_credential(user: RequiredUser, session: DbSession) -> Response:
    await ai_service.delete_credential(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/credential/verify")
async def check_credential(user: RequiredUser, session: DbSession) -> dict[str, bool]:
    resolved = await ai_service.resolve_secret(session, user.id)
    if resolved is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ключ не подключён")
    base_url, api_key, model = resolved
    try:
        await verify_key(base_url=base_url, api_key=api_key, model=model)
    except AiProviderError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.user_message) from exc
    return {"ok": True}


# ── чат ───────────────────────────────────────────────────────────────────


def _parse_task_id(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Некорректный идентификатор задачи"
        ) from exc


@router.post("/terms/accept")
async def accept_terms(user: RequiredUser, session: DbSession) -> dict[str, bool]:
    """Отметить, что пользователь принял условия чата (18+, ответы от ИИ)."""
    user.ai_terms_accepted_at = datetime.now(UTC)
    session.add(user)
    await session.commit()
    return {"ok": True}


@router.get("/state", response_model=ChatStateOut)
async def chat_state(
    user: RequiredUser, session: DbSession, task_id: str | None = None
) -> ChatStateOut:
    """Состояние чата при открытии: согласие, ключ, лимит, история, шаблоны."""
    parsed = _parse_task_id(task_id)
    past = await ai_chat.history(session, user.id, parsed)
    return ChatStateOut(
        terms_accepted=user.ai_terms_accepted_at is not None,
        has_credential=(await ai_service.get_credential(session, user.id)) is not None,
        used_today=await ai_chat.usage_today(session, user.id),
        daily_limit=ai_chat.DAILY_LIMIT,
        messages=[
            MessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat(),
            )
            for m in past
        ],
        templates=[{"label": t.label, "text": t.text} for t in TEMPLATES],
    )


@router.post("/check-prompt")
async def check_prompt(payload: AskIn, user: RequiredUser) -> dict[str, list[str]]:
    """Подсказать, что в вопросе похоже на личные данные. Не блокирует."""
    return {"personal": find_personal_data(payload.prompt)}


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_messages(
    user: RequiredUser, session: DbSession, task_id: str | None = None
) -> Response:
    await ai_chat.clear_thread(session, user.id, _parse_task_id(task_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/stream")
async def stream_answer(
    payload: AskIn, user: RequiredUser, session: DbSession
) -> StreamingResponse:
    """Ответ модели по мере генерации.

    Отдаём text/event-stream: строки «data: <кусок>» и служебные события
    «event: error» / «event: done». Браузер читает через fetch + ReadableStream,
    поэтому метод POST (EventSource умеет только GET).
    """
    if user.ai_terms_accepted_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Сначала прими условия ИИ-помощника")

    resolved = await ai_service.resolve_secret(session, user.id)
    if resolved is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ключ не подключён")
    base_url, api_key, model = resolved

    task_id = _parse_task_id(payload.task_id)
    try:
        await ai_chat.check_and_count(session, user.id)
    except ai_chat.LimitReached as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"На сегодня всё: {exc.used} из {exc.limit} запросов. Лимит обновится завтра.",
        ) from exc

    context = await ai_chat.task_context(session, user.id, task_id) if task_id else None
    past = await ai_chat.history(session, user.id, task_id)
    try:
        messages = ai_chat.build_messages(payload.prompt, past, context)
    except ai_chat.PromptTooLong as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await ai_chat.save_message(
        session, user.id, role="user", content=payload.prompt, task_id=task_id
    )

    async def events() -> AsyncIterator[str]:
        collected: list[str] = []
        try:
            async for chunk in stream_completion(
                base_url=base_url, api_key=api_key, model=model, messages=messages
            ):
                collected.append(chunk)
                yield f"data: {chunk.replace(chr(10), chr(92) + 'n')}\n\n"
        except AiProviderError as exc:
            yield f"event: error\ndata: {exc.user_message}\n\n"
            return
        finally:
            # Сохраняем даже частичный ответ: пользователь его уже прочитал,
            # и в истории он должен остаться. Пустой — не пишем.
            answer = "".join(collected).strip()
            if answer:
                unsafe = is_unsafe_for_children(answer)
                stored = (
                    "Ответ скрыт: тема не подходит для сервиса, которым пользуются школьники."
                    if unsafe
                    else answer
                )
                await ai_chat.save_message(
                    session, user.id, role="assistant", content=stored, task_id=task_id
                )
                if unsafe:
                    yield f"event: blocked\ndata: {stored}\n\n"
        yield "event: done\ndata: ok\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Без этого nginx буферизует ответ и стрим превращается в
            # «ничего не происходит, потом всё сразу».
            "X-Accel-Buffering": "no",
        },
    )
