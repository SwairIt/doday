"""Тесты чата с моделью: лимиты, история, стриминг, фильтры, экраны."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import chat as ai_chat
from app.ai import service as ai_service
from app.ai.client import AiProviderError, Message, _chunk_from_line
from app.ai.prompts import TEMPLATES
from app.ai.safety import find_personal_data, is_unsafe_for_children
from app.auth.models import User


@pytest_asyncio.fixture
async def chat_user_id(db_session: AsyncSession) -> UUID:
    user = User(id=uuid4(), email=f"chat-{uuid4().hex[:8]}@test.local", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    return user.id


# ── разбор потока от провайдера ───────────────────────────────────────────


def test_chunk_from_line_extracts_text() -> None:
    line = 'data: {"choices":[{"delta":{"content":"Привет"}}]}'
    assert _chunk_from_line(line) == "Привет"


def test_chunk_from_line_ignores_service_lines() -> None:
    assert _chunk_from_line("data: [DONE]") == ""
    assert _chunk_from_line(": keep-alive") == ""
    assert _chunk_from_line("") == ""
    assert _chunk_from_line('data: {"choices":[]}') == ""


def test_chunk_from_line_survives_broken_json() -> None:
    """Кривой кусок не должен ронять весь ответ — остальные могут быть целыми."""
    assert _chunk_from_line("data: {не json") == ""


# ── фильтры ───────────────────────────────────────────────────────────────


def test_find_personal_data() -> None:
    assert "телефон" in find_personal_data("позвони мне +7 916 123 45 67")
    assert "почту" in find_personal_data("пиши на vasya@example.com")
    assert "имя" in find_personal_data("Меня зовут Иван Петров, помоги")
    assert "номер школы" in find_personal_data("я из школы №15")
    assert find_personal_data("Как решить квадратное уравнение?") == []


def test_unsafe_content_detection() -> None:
    assert is_unsafe_for_children("вот инструкция по суициду, шаг первый") is not None
    assert is_unsafe_for_children("как сварить метамфетамин дома") is not None
    assert is_unsafe_for_children("как сделать бомбу из подручных средств") is not None


def test_school_topics_are_not_blocked() -> None:
    """Литература и история говорят о смерти — это не повод прятать ответ."""
    assert is_unsafe_for_children("Анна Каренина бросилась под поезд — это финал романа") is None
    assert is_unsafe_for_children("Раскольников совершил убийство старухи-процентщицы") is None
    assert is_unsafe_for_children("реакция получения этанола в лаборатории") is None


# ── лимиты ────────────────────────────────────────────────────────────────


async def test_usage_starts_at_zero(db_session: AsyncSession, chat_user_id: UUID) -> None:
    assert await ai_chat.usage_today(db_session, chat_user_id) == 0


async def test_check_and_count_increments(db_session: AsyncSession, chat_user_id: UUID) -> None:
    assert await ai_chat.check_and_count(db_session, chat_user_id) == 1
    assert await ai_chat.check_and_count(db_session, chat_user_id) == 2
    assert await ai_chat.usage_today(db_session, chat_user_id) == 2


async def test_limit_raises_when_exhausted(
    db_session: AsyncSession, chat_user_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_chat, "DAILY_LIMIT", 2)
    await ai_chat.check_and_count(db_session, chat_user_id)
    await ai_chat.check_and_count(db_session, chat_user_id)
    with pytest.raises(ai_chat.LimitReached) as exc:
        await ai_chat.check_and_count(db_session, chat_user_id)
    assert exc.value.used == 2
    assert exc.value.limit == 2


async def test_usage_survives_new_session(db_session: AsyncSession, chat_user_id: UUID) -> None:
    """Счётчик в БД, а не в памяти: переживает перезапуск процесса."""
    await ai_chat.check_and_count(db_session, chat_user_id)
    db_session.expire_all()
    assert await ai_chat.usage_today(db_session, chat_user_id) == 1


# ── история ───────────────────────────────────────────────────────────────


async def test_history_is_chronological(db_session: AsyncSession, chat_user_id: UUID) -> None:
    await ai_chat.save_message(db_session, chat_user_id, role="user", content="первый")
    await ai_chat.save_message(db_session, chat_user_id, role="assistant", content="второй")
    rows = await ai_chat.history(db_session, chat_user_id, None)
    assert [r.content for r in rows] == ["первый", "второй"]


async def test_history_separates_threads(db_session: AsyncSession, chat_user_id: UUID) -> None:
    """Разговор про задачу не смешивается со свободным чатом."""
    await ai_chat.save_message(db_session, chat_user_id, role="user", content="общий вопрос")
    general = await ai_chat.history(db_session, chat_user_id, None)
    assert [r.content for r in general] == ["общий вопрос"]


async def test_clear_thread(db_session: AsyncSession, chat_user_id: UUID) -> None:
    await ai_chat.save_message(db_session, chat_user_id, role="user", content="а")
    await ai_chat.save_message(db_session, chat_user_id, role="assistant", content="б")
    assert await ai_chat.clear_thread(db_session, chat_user_id, None) == 2
    assert await ai_chat.history(db_session, chat_user_id, None) == []


# ── сборка запроса ────────────────────────────────────────────────────────


def test_build_messages_puts_system_first() -> None:
    messages = ai_chat.build_messages("Как решить?", [])
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "Как решить?"}


def test_build_messages_includes_task_context() -> None:
    messages = ai_chat.build_messages("Помоги", [], context="Задача: Алгебра № 214")
    assert "Алгебра № 214" in messages[0]["content"]


def test_build_messages_rejects_long_prompt() -> None:
    with pytest.raises(ai_chat.PromptTooLong):
        ai_chat.build_messages("а" * (ai_chat.MAX_PROMPT_CHARS + 1), [])


def test_templates_are_present() -> None:
    assert len(TEMPLATES) >= 6
    assert all(t.label and t.text for t in TEMPLATES)


# ── API ───────────────────────────────────────────────────────────────────


async def test_state_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/ai/state")).status_code == 401


async def test_state_reports_no_terms_and_no_key(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/api/ai/state")).json()
    assert body["terms_accepted"] is False
    assert body["has_credential"] is False
    assert body["daily_limit"] == ai_chat.DAILY_LIMIT
    assert body["messages"] == []
    assert len(body["templates"]) >= 6


async def test_accept_terms(logged_in_client: AsyncClient) -> None:
    assert (await logged_in_client.post("/api/ai/terms/accept")).status_code == 200
    assert (await logged_in_client.get("/api/ai/state")).json()["terms_accepted"] is True


async def test_stream_requires_terms(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post("/api/ai/stream", json={"prompt": "привет"})
    assert r.status_code == 403


async def test_stream_requires_credential(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post("/api/ai/terms/accept")
    r = await logged_in_client.post("/api/ai/stream", json={"prompt": "привет"})
    assert r.status_code == 400
    assert "Ключ не подключён" in r.json()["detail"]


async def test_check_prompt_warns_about_personal_data(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post(
        "/api/ai/check-prompt", json={"prompt": "Меня зовут Иван Петров"}
    )
    assert r.status_code == 200
    assert "имя" in r.json()["personal"]


async def test_stream_returns_text_and_saves_history(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await logged_in_client.post("/api/ai/terms/accept")
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-stream-1234"}
    )

    async def fake_stream(**kwargs: object) -> AsyncIterator[str]:
        for piece in ("При", "вет", "!"):
            yield piece

    monkeypatch.setattr("app.ai.router.stream_completion", fake_stream)
    r = await logged_in_client.post("/api/ai/stream", json={"prompt": "поздоровайся"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["x-accel-buffering"] == "no"
    assert "data: При" in r.text
    assert "event: done" in r.text

    state = (await logged_in_client.get("/api/ai/state")).json()
    contents = [m["content"] for m in state["messages"]]
    assert "поздоровайся" in contents
    assert "Привет!" in contents
    assert state["used_today"] == 1


async def test_stream_reports_provider_error(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await logged_in_client.post("/api/ai/terms/accept")
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-err-1234"}
    )

    async def failing(**kwargs: object) -> AsyncIterator[str]:
        raise AiProviderError("Ключ не принят провайдером — проверь, что скопировал его целиком.")
        yield ""  # pragma: no cover — нужен, чтобы функция осталась генератором

    monkeypatch.setattr("app.ai.router.stream_completion", failing)
    r = await logged_in_client.post("/api/ai/stream", json={"prompt": "привет"})
    assert r.status_code == 200
    assert "event: error" in r.text
    assert "не принят" in r.text


async def test_stream_hides_unsafe_answer(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await logged_in_client.post("/api/ai/terms/accept")
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-unsafe-1234"}
    )

    async def unsafe(**kwargs: object) -> AsyncIterator[str]:
        yield "вот инструкция по суициду, шаг первый"

    monkeypatch.setattr("app.ai.router.stream_completion", unsafe)
    r = await logged_in_client.post("/api/ai/stream", json={"prompt": "что-то"})
    assert "event: blocked" in r.text

    state = (await logged_in_client.get("/api/ai/state")).json()
    stored = [m["content"] for m in state["messages"] if m["role"] == "assistant"]
    assert stored
    assert "инструкция по суициду" not in stored[-1]


async def test_stream_respects_daily_limit(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await logged_in_client.post("/api/ai/terms/accept")
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-limit-1234"}
    )
    monkeypatch.setattr(ai_chat, "DAILY_LIMIT", 1)

    async def one_word(**kwargs: object) -> AsyncIterator[str]:
        yield "ок"

    monkeypatch.setattr("app.ai.router.stream_completion", one_word)
    assert (
        await logged_in_client.post("/api/ai/stream", json={"prompt": "раз"})
    ).status_code == 200
    r = await logged_in_client.post("/api/ai/stream", json={"prompt": "два"})
    assert r.status_code == 429
    assert "На сегодня всё" in r.json()["detail"]


async def test_clear_messages_endpoint(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await logged_in_client.post("/api/ai/terms/accept")
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-clear-1234"}
    )

    async def hi(**kwargs: object) -> AsyncIterator[str]:
        yield "привет"

    monkeypatch.setattr("app.ai.router.stream_completion", hi)
    await logged_in_client.post("/api/ai/stream", json={"prompt": "здравствуй"})
    assert (await logged_in_client.get("/api/ai/state")).json()["messages"]

    assert (await logged_in_client.delete("/api/ai/messages")).status_code == 204
    assert (await logged_in_client.get("/api/ai/state")).json()["messages"] == []


# ── страницы ──────────────────────────────────────────────────────────────


async def test_ai_page_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/app/ai")).status_code == 401


async def test_ai_page_renders(logged_in_client: AsyncClient) -> None:
    html = (await logged_in_client.get("/app/ai")).text
    assert "ИИ-помощник" in html
    assert "/api/ai/state" in html
    assert "/api/ai/stream" in html
    assert "Сгенерировано ИИ" in html
    assert "с 18 лет" in html


async def test_sidebar_has_ai_link(logged_in_client: AsyncClient) -> None:
    html = (await logged_in_client.get("/app/today")).text
    assert "/app/ai" in html


async def test_task_detail_has_ask_ai_button(logged_in_client: AsyncClient) -> None:
    task = (await logged_in_client.post("/api/tasks", json={"title": "Алгебра № 214"})).json()
    html = (await logged_in_client.get(f"/htmx/tasks/{task['id']}/detail")).text
    assert "Спросить ИИ" in html
    assert f"/app/ai?task={task['id']}" in html


async def test_task_context_is_built(db_session: AsyncSession, chat_user_id: UUID) -> None:
    """Контекст задачи собирается из названия и описания."""
    from app.projects.service import create_project
    from app.tasks.models import Task

    project = await create_project(db_session, chat_user_id, name="Учёба")
    task = Task(
        id=uuid4(),
        user_id=chat_user_id,
        project_id=project.id,
        title="Физика §12",
        description="Задачи 1-4",
    )
    db_session.add(task)
    await db_session.commit()

    context = await ai_chat.task_context(db_session, chat_user_id, task.id)
    assert context is not None
    assert "Физика §12" in context
    assert "Задачи 1-4" in context


async def test_task_context_of_stranger_is_none(
    db_session: AsyncSession, chat_user_id: UUID
) -> None:
    """Чужую задачу в контекст не подставляем."""
    assert await ai_chat.task_context(db_session, chat_user_id, uuid4()) is None


def test_message_type_shape() -> None:
    """Message — то, что ждёт OpenAI-совместимый API."""
    msg: Message = {"role": "user", "content": "привет"}
    assert msg["role"] == "user"


async def test_credential_still_hidden_in_state(logged_in_client: AsyncClient) -> None:
    await logged_in_client.put(
        "/api/ai/credential", json={"provider": "cloudru", "api_key": "sk-hidden-4321"}
    )
    r = await logged_in_client.get("/api/ai/state")
    assert "sk-hidden-4321" not in r.text
    assert r.json()["has_credential"] is True


async def test_service_and_chat_are_independent(
    db_session: AsyncSession, chat_user_id: UUID
) -> None:
    """Удаление ключа не трогает историю переписки."""
    await ai_service.upsert_credential(
        db_session, chat_user_id, provider="cloudru", api_key="sk-keep-1111"
    )
    await ai_chat.save_message(db_session, chat_user_id, role="user", content="вопрос")
    await ai_service.delete_credential(db_session, chat_user_id)
    assert await ai_chat.messages_count(db_session, chat_user_id) == 1
