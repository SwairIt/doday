"""REST ИИ-помощника: справочник провайдеров и ключ пользователя."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response, status

from app.ai import service as ai_service
from app.ai.client import AiProviderError, verify_key
from app.ai.models import AiCredential
from app.ai.providers import PROVIDERS
from app.ai.schemas import CredentialIn, CredentialOut, ProviderOut
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
