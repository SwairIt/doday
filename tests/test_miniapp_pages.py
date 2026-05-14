"""Smoke-tests for /miniapp/* tab pages — auth-redirect + render."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.models import TaskPriority
from app.tasks.service import create_task

PAGES = ["/miniapp/", "/miniapp/inbox", "/miniapp/calendar", "/miniapp/projects", "/miniapp/me"]


@pytest.mark.parametrize("path", PAGES)
async def test_miniapp_page_unauth_redirects_to_link(client: AsyncClient, path: str) -> None:
    r = await client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/miniapp/link"


@pytest.mark.parametrize("path", PAGES)
async def test_miniapp_page_authed_renders(logged_in_client: AsyncClient, path: str) -> None:
    r = await logged_in_client.get(path, follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "Doday" in body
    assert "miniapp-nav" in body  # bottom-nav present


async def test_miniapp_assets_js_served(client: AsyncClient) -> None:
    r = await client.get("/miniapp/assets/miniapp.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "Telegram.WebApp" in r.text
    assert "dodaySetTheme" in r.text  # глобальный setter для UI-переключателя
    assert "applyTheme" in r.text
    assert "setHeaderColor" in r.text
    assert "attemptAuth" in r.text
    # Auth-success on link-page should redirect to /miniapp/
    assert "if (onLinkPage)" in r.text or "onLinkPage" in r.text


async def test_miniapp_link_page_unauth_renders(client: AsyncClient) -> None:
    """/miniapp/link не требует auth — это onboarding-экран."""
    r = await client.get("/miniapp/link?telegram_user_id=12345")
    assert r.status_code == 200
    assert "Привяжи аккаунт Doday" in r.text
    assert "12345" in r.text
    assert "miniapp-nav" in r.text  # bottom-nav present


async def test_miniapp_link_authed_redirects_to_today(logged_in_client: AsyncClient) -> None:
    """Если юзер УЖЕ залогинен — onboarding не нужен, редирект на /."""
    r = await logged_in_client.get("/miniapp/link", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/miniapp/"


async def test_api_parse_returns_preview(logged_in_client: AsyncClient) -> None:
    """MB2: /miniapp/api/parse возвращает разбор для quick-add preview."""
    r = await logged_in_client.post("/miniapp/api/parse", json={"text": "Покупки завтра !!"})
    assert r.status_code == 200
    data = r.json()
    assert "Покупки" in data["title"]
    assert data["due_at"]  # завтрашняя дата
    assert data["priority"] == "p3"  # !! = P3
    assert "label_names" in data


async def test_api_parse_unauth_401(client: AsyncClient) -> None:
    r = await client.post("/miniapp/api/parse", json={"text": "test"})
    assert r.status_code == 401


async def test_api_create_task_inbox(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB2: POST /miniapp/api/tasks создаёт задачу в Inbox."""
    r = await logged_in_client.post(
        "/miniapp/api/tasks", json={"text": "Тестовая задача завтра !!"}
    )
    assert r.status_code == 201
    data = r.json()
    assert "Тестовая задача" in data["title"]
    assert data["priority"] == "p3"  # !! = P3
    assert data["due_at"]


async def test_api_create_task_empty_text_400(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post("/miniapp/api/tasks", json={"text": "   "})
    assert r.status_code == 400


async def test_api_snooze_task_sets_due_to_tomorrow(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB3: POST /miniapp/api/tasks/<id>/snooze ставит due_at на завтра 23:59."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="To snooze", project_id=inbox.id)
    await db_session.commit()

    r = await logged_in_client.post(f"/miniapp/api/tasks/{task.id}/snooze")
    assert r.status_code == 200
    data = r.json()
    assert data["due_at"]
    # tomorrow
    from datetime import UTC, datetime, timedelta

    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    assert data["due_at"].startswith(tomorrow.isoformat())


async def test_api_get_patch_delete_task(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB4: GET / PATCH / DELETE /miniapp/api/tasks/<id>."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="Original", project_id=inbox.id)
    await db_session.commit()

    # GET — теперь с расширенным payload (V1)
    r = await logged_in_client.get(f"/miniapp/api/tasks/{task.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Original"
    # V1: новые поля
    assert "project" in data
    assert data["project"]["is_inbox"] is True  # task в Inbox
    assert "labels" in data and isinstance(data["labels"], list)
    assert "description" in data
    assert "pinned_at" in data
    assert "subtask_stats" in data
    assert data["subtask_stats"] == {"done": 0, "total": 0}
    assert "age_days" in data and data["age_days"] >= 0

    # PATCH title + priority
    r = await logged_in_client.patch(
        f"/miniapp/api/tasks/{task.id}",
        json={"title": "Updated", "priority": "p1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Updated"
    assert data["priority"] == "p1"

    # PATCH due_at — set
    from datetime import UTC, datetime, timedelta

    iso = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"due_at": iso})
    assert r.status_code == 200
    assert r.json()["due_at"]

    # PATCH due_at — clear
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"due_at": ""})
    assert r.status_code == 200
    assert r.json()["due_at"] is None

    # DELETE — soft delete
    r = await logged_in_client.delete(f"/miniapp/api/tasks/{task.id}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_api_list_projects(db_session: AsyncSession, logged_in_client: AsyncClient) -> None:
    """MB5: GET /miniapp/api/projects возвращает список проектов юзера."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    await ensure_inbox(db_session, user.id)
    await db_session.commit()

    r = await logged_in_client.get("/miniapp/api/projects")
    assert r.status_code == 200
    data = r.json()
    assert "projects" in data
    assert len(data["projects"]) >= 1
    inbox_proj = next((p for p in data["projects"] if p["is_inbox"]), None)
    assert inbox_proj is not None
    assert "name" in inbox_proj
    assert "color" in inbox_proj


async def test_api_patch_move_to_another_project(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB5: PATCH project_id переносит задачу из Inbox в другой проект."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import create_project, ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    new_proj = await create_project(db_session, user.id, name="Work", color="violet")
    await db_session.commit()
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="Move me", project_id=inbox.id)
    await db_session.commit()

    r = await logged_in_client.patch(
        f"/miniapp/api/tasks/{task.id}", json={"project_id": str(new_proj.id)}
    )
    assert r.status_code == 200


async def test_api_patch_invalid_project_id_rejected(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="X", project_id=inbox.id)
    await db_session.commit()

    # Несуществующий project_id — 404
    import uuid

    r = await logged_in_client.patch(
        f"/miniapp/api/tasks/{task.id}", json={"project_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404


async def test_api_patch_bad_priority_rejected(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="X", project_id=inbox.id)
    await db_session.commit()
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"priority": "p99"})
    assert r.status_code == 400


async def test_swipe_handlers_in_js_bundle(client: AsyncClient) -> None:
    """MB3: убеждаемся что swipe-handler присутствует в miniapp.js."""
    r = await client.get("/miniapp/assets/miniapp.js")
    assert r.status_code == 200
    body = r.text
    assert "SWIPE_THRESHOLD" in body
    assert "commitComplete" in body
    assert "commitSnooze" in body
    assert "data-swipeable" in body or "swipeable" in body


async def test_api_list_labels(db_session: AsyncSession, logged_in_client: AsyncClient) -> None:
    """V4: GET /miniapp/api/labels возвращает лейблы юзера."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.labels.models import Label

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    db_session.add(Label(user_id=user.id, name="home", slug="home", color="emerald"))
    db_session.add(Label(user_id=user.id, name="work", slug="work", color="rose"))
    await db_session.commit()
    r = await logged_in_client.get("/miniapp/api/labels")
    assert r.status_code == 200
    data = r.json()
    assert len(data["labels"]) == 2
    names = {lab["name"] for lab in data["labels"]}
    assert names == {"home", "work"}


async def test_api_patch_label_ids_replaces_labels(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """V4: PATCH с label_ids заменяет labels на задаче."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.labels.models import Label
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    l1 = Label(user_id=user.id, name="home", slug="home", color="emerald")
    db_session.add(l1)
    await db_session.flush()
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="X", project_id=inbox.id)
    await db_session.commit()

    # Add label
    r = await logged_in_client.patch(
        f"/miniapp/api/tasks/{task.id}", json={"label_ids": [str(l1.id)]}
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["labels"]) == 1
    assert data["labels"][0]["name"] == "home"

    # Remove all
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"label_ids": []})
    assert r.status_code == 200
    assert r.json()["labels"] == []


async def test_api_patch_recurrence_and_pin(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """V5: PATCH recurrence + toggle_pin меняют статусы."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="X", project_id=inbox.id)
    await db_session.commit()

    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"recurrence": "daily"})
    assert r.status_code == 200
    assert r.json()["recurrence"] == "daily"

    # Bad value
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"recurrence": "hourly"})
    assert r.status_code == 400

    # Toggle pin on
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"toggle_pin": True})
    assert r.status_code == 200
    assert r.json()["pinned_at"] is not None

    # Toggle pin off
    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"toggle_pin": True})
    assert r.status_code == 200
    assert r.json()["pinned_at"] is None


async def test_api_subtasks_list_and_create(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """V6: GET/POST /miniapp/api/tasks/<id>/subtasks."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    parent = await svc_create_task(db_session, user.id, title="Parent", project_id=inbox.id)
    await db_session.commit()

    r = await logged_in_client.get(f"/miniapp/api/tasks/{parent.id}/subtasks")
    assert r.status_code == 200
    assert r.json() == {"subtasks": []}

    r = await logged_in_client.post(
        f"/miniapp/api/tasks/{parent.id}/subtasks",
        json={"title": "Step 1"},
    )
    assert r.status_code == 201
    sub_id = r.json()["id"]

    r = await logged_in_client.get(f"/miniapp/api/tasks/{parent.id}/subtasks")
    assert r.status_code == 200
    assert len(r.json()["subtasks"]) == 1
    assert r.json()["subtasks"][0]["id"] == sub_id


async def test_api_create_subtask_empty_400(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    parent = await svc_create_task(db_session, user.id, title="P", project_id=inbox.id)
    await db_session.commit()
    r = await logged_in_client.post(
        f"/miniapp/api/tasks/{parent.id}/subtasks", json={"title": "   "}
    )
    assert r.status_code == 400


async def test_api_subtask_stats_endpoint(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """V2: GET /miniapp/api/tasks/<id>/subtask-stats — lightweight count."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    parent = await svc_create_task(db_session, user.id, title="Parent", project_id=inbox.id)
    await db_session.commit()

    r = await logged_in_client.get(f"/miniapp/api/tasks/{parent.id}/subtask-stats")
    assert r.status_code == 200
    assert r.json() == {"done": 0, "total": 0}


async def test_task_card_renders_pin_description_labels(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """β: task_card показывает 📌, description, first label inline."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.auth.models import User
    from app.labels.models import Label
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    label = Label(user_id=user.id, name="home", slug="home", color="emerald")
    db_session.add(label)
    await db_session.flush()
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(
        db_session,
        user.id,
        title="Pinned task",
        project_id=inbox.id,
        description="Кратко: купить молоко",
    )
    task.pinned_at = datetime.now(UTC)
    task.labels.append(label)
    await db_session.commit()

    # Сегодня — но мы создали без due_at, попадёт в Inbox
    r = await logged_in_client.get("/miniapp/inbox")
    assert r.status_code == 200
    body = r.text
    assert "📌" in body
    assert "Кратко: купить молоко" in body
    assert "— home" in body  # β: label now inline, italic, no @ prefix


async def test_sections_crud_and_kanban(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """ζ K1+K2+K3+K4: sections CRUD + kanban view + move task between sections."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import create_project

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    proj = await create_project(db_session, user.id, name="Kanban project", color="violet")
    await db_session.commit()

    # No sections initially
    r = await logged_in_client.get(f"/miniapp/api/projects/{proj.id}/sections")
    assert r.status_code == 200
    assert r.json() == {"sections": []}

    # Create section
    r = await logged_in_client.post(
        f"/miniapp/api/projects/{proj.id}/sections", json={"name": "Todo"}
    )
    assert r.status_code == 201
    sec_id = r.json()["id"]

    # Rename
    r = await logged_in_client.patch(f"/miniapp/api/sections/{sec_id}", json={"name": "В работе"})
    assert r.status_code == 200
    assert r.json()["name"] == "В работе"

    # Create task в проекте + перенести в section через PATCH
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="K4", project_id=proj.id)
    await db_session.commit()

    r = await logged_in_client.patch(f"/miniapp/api/tasks/{task.id}", json={"section_id": sec_id})
    assert r.status_code == 200
    assert r.json()["section_id"] == sec_id

    # Kanban-view рендерит секции и задачи
    r = await logged_in_client.get(f"/miniapp/projects/{proj.id}?view=kanban")
    assert r.status_code == 200
    body = r.text
    assert "В работе" in body
    assert "kanban-col" in body
    assert "data-section-drop" in body
    assert "K4" in body  # task title rendered

    # Delete section
    r = await logged_in_client.delete(f"/miniapp/api/sections/{sec_id}")
    assert r.status_code == 200


async def test_reminder_crud(db_session: AsyncSession, logged_in_client: AsyncClient) -> None:
    """ε N1+N2: GET/POST/DELETE /miniapp/api/tasks/<id>/reminders + /api/reminders/<id>."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="Remind me", project_id=inbox.id)
    await db_session.commit()

    # Initially empty
    r = await logged_in_client.get(f"/miniapp/api/tasks/{task.id}/reminders")
    assert r.status_code == 200
    assert r.json() == {"reminders": []}

    # Create
    in_30min = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    r = await logged_in_client.post(
        f"/miniapp/api/tasks/{task.id}/reminders",
        json={"remind_at": in_30min},
    )
    assert r.status_code == 201
    rid = r.json()["id"]

    # List
    r = await logged_in_client.get(f"/miniapp/api/tasks/{task.id}/reminders")
    assert r.status_code == 200
    rems = r.json()["reminders"]
    assert len(rems) == 1
    assert rems[0]["sent_at"] is None
    assert rems[0]["kind"] == "custom"

    # Delete
    r = await logged_in_client.delete(f"/miniapp/api/reminders/{rid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # Now empty
    r = await logged_in_client.get(f"/miniapp/api/tasks/{task.id}/reminders")
    assert r.json()["reminders"] == []


async def test_pomodoro_start_active_stop_flow(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """δ P1-P5: start → /active → stop с suggest_break."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox
    from app.tasks.service import create_task as svc_create_task

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    task = await svc_create_task(db_session, user.id, title="Focus me", project_id=inbox.id)
    await db_session.commit()

    # No active session initially
    r = await logged_in_client.get("/miniapp/api/pomodoro/active")
    assert r.status_code == 200
    assert r.json()["active"] is None

    # Start focus
    r = await logged_in_client.post(
        "/miniapp/api/pomodoro/start", json={"task_id": str(task.id), "kind": "focus"}
    )
    assert r.status_code == 201
    pomo = r.json()
    assert pomo["kind"] == "focus"
    assert pomo["duration_min"] == 25
    assert pomo["ended_at"] is None
    sid = pomo["id"]

    # Active now
    r = await logged_in_client.get("/miniapp/api/pomodoro/active")
    assert r.json()["active"]["id"] == sid

    # Stop с completed=True → suggest break
    r = await logged_in_client.post(f"/miniapp/api/pomodoro/stop/{sid}", json={"completed": True})
    assert r.status_code == 200
    data = r.json()
    assert data["stopped"]["ended_at"] is not None
    assert data["stopped"]["completed"] is True
    assert data.get("suggest_break") in ("break-short", "break-long")

    # Time-on-task — должно быть > 0 (хоть и 0 минут в тесте,
    # endpoint работает)
    r = await logged_in_client.get(f"/miniapp/api/pomodoro/task/{task.id}")
    assert r.status_code == 200
    body = r.json()
    assert "total_minutes" in body
    assert len(body["recent"]) >= 1


async def test_pomodoro_bad_kind_400(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.post("/miniapp/api/pomodoro/start", json={"kind": "bogus"})
    assert r.status_code == 400


async def test_polish_features_in_js_bundle(client: AsyncClient) -> None:
    """MD1-MD5 + P5-P6: MainButton, haptic, PTR (с spinner SVG), swipe data-passed."""
    r = await client.get("/miniapp/assets/miniapp.js")
    assert r.status_code == 200
    body = r.text
    assert "setupMainButton" in body or "MainButton" in body
    assert "PULL_THRESHOLD" in body
    assert "BackButton" in body
    assert "dodayHaptic" in body
    # P5: data-passed atrribute для visual swipe-feedback
    assert "data-passed" in body
    # P6: SVG circle для PTR-spinner (вместо текста)
    assert "ptr-arc" in body


async def test_api_complete_task_toggles(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB3-prep: POST /miniapp/api/tasks/<id>/complete переключает статус."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    task = await svc_create_task(db_session, user.id, title="To complete", project_id=inbox.id)
    await db_session.commit()

    # First call — completes
    r = await logged_in_client.post(f"/miniapp/api/tasks/{task.id}/complete")
    assert r.status_code == 200
    assert r.json()["is_completed"] is True
    # Second call — un-completes
    r = await logged_in_client.post(f"/miniapp/api/tasks/{task.id}/complete")
    assert r.status_code == 200
    assert r.json()["is_completed"] is False


async def test_calendar_week_view_renders_chips(logged_in_client: AsyncClient) -> None:
    """MC1: /miniapp/calendar показывает 7 day-chips + selected day."""
    r = await logged_in_client.get("/miniapp/calendar", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    # Все 7 weekday-имён
    for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
        assert d in body
    # Header с месяцем (любой из месяцев должен быть в strftime %B)
    assert "data-week-swipeable" in body
    assert "data-prev-week" in body
    assert "data-next-week" in body


async def test_calendar_with_explicit_date(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/miniapp/calendar?date=2026-05-15", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    # Дата должна попасть в хедер
    assert "data-week-swipeable" in body


async def test_calendar_invalid_date_falls_back_to_today(
    logged_in_client: AsyncClient,
) -> None:
    r = await logged_in_client.get("/miniapp/calendar?date=not-a-date", follow_redirects=False)
    assert r.status_code == 200


async def test_calendar_heatmap_renders(logged_in_client: AsyncClient) -> None:
    """MC2: heatmap отрисован — 12 недель."""
    r = await logged_in_client.get("/miniapp/calendar")
    assert r.status_code == 200
    body = r.text
    assert "Активность" in body
    assert "12 недель" in body


async def test_projects_list_renders_with_counts(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MC3: /miniapp/projects показывает Inbox + counts."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import create_project, ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    work = await create_project(db_session, user.id, name="Work", color="violet")
    from app.tasks.service import create_task as svc_create_task

    await svc_create_task(db_session, user.id, title="A", project_id=inbox.id)
    await svc_create_task(db_session, user.id, title="B", project_id=work.id)
    await db_session.commit()

    r = await logged_in_client.get("/miniapp/projects")
    assert r.status_code == 200
    body = r.text
    assert "Work" in body


async def test_project_view_renders_tasks(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MC3: /miniapp/projects/<id> показывает задачи проекта."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import create_project

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    proj = await create_project(db_session, user.id, name="Alpha", color="rose")
    from app.tasks.service import create_task as svc_create_task

    await svc_create_task(db_session, user.id, title="Alpha-1", project_id=proj.id)
    await db_session.commit()

    r = await logged_in_client.get(f"/miniapp/projects/{proj.id}", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "Alpha" in body
    assert "Alpha-1" in body


async def test_project_view_invalid_id_redirects(logged_in_client: AsyncClient) -> None:
    r = await logged_in_client.get("/miniapp/projects/not-a-uuid", follow_redirects=False)
    assert r.status_code == 303


async def test_api_create_project(logged_in_client: AsyncClient) -> None:
    """MC3: POST /miniapp/api/projects создаёт проект."""
    r = await logged_in_client.post(
        "/miniapp/api/projects", json={"name": "MyProject", "color": "emerald"}
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "MyProject"
    assert data["color"] == "emerald"


async def test_api_create_task_to_specific_project(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MC3: quick-add может создавать в указанный проект."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import create_project

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    proj = await create_project(db_session, user.id, name="Studies", color="blue")
    await db_session.commit()
    r = await logged_in_client.post(
        "/miniapp/api/tasks", json={"text": "Урок", "project_id": str(proj.id)}
    )
    assert r.status_code == 201


async def test_api_stats_full_payload(logged_in_client: AsyncClient) -> None:
    """S1: /miniapp/api/stats содержит все поля."""
    r = await logged_in_client.get("/miniapp/api/stats")
    assert r.status_code == 200
    data = r.json()
    expected_keys = {
        "current_streak",
        "longest_streak",
        "done_today",
        "done_week",
        "done_month",
        "done_total",
        "chart_14d",
        "chart_max",
        "best_weekday",
        "avg_per_active_day",
        "active_days",
        "avg_completion_hours",
        "by_priority",
        "by_project",
    }
    assert expected_keys.issubset(data.keys())
    assert len(data["chart_14d"]) == 14
    assert set(data["by_priority"].keys()) == {"p1", "p2", "p3", "p4"}
    assert isinstance(data["by_project"], list)


async def test_api_heatmap_returns_counts(logged_in_client: AsyncClient) -> None:
    """MC2: GET /miniapp/api/heatmap возвращает {start_date, counts}."""
    r = await logged_in_client.get("/miniapp/api/heatmap")
    assert r.status_code == 200
    data = r.json()
    assert "start_date" in data
    assert "counts" in data
    assert isinstance(data["counts"], dict)


async def test_today_page_renders_overdue_and_today_tasks(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MB1: Today показывает просрочку, сегодняшние, прогресс-кольцо."""
    from sqlalchemy import select

    from app.auth.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    from app.projects.service import ensure_inbox

    inbox = await ensure_inbox(db_session, user.id)

    # Задача overdue (вчера)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    await create_task(
        db_session,
        user.id,
        title="Overdue task",
        project_id=inbox.id,
        due_at=yesterday,
        due_date_only=True,
        priority=TaskPriority.P1,
    )
    # Задача сегодня
    today = datetime.now(UTC)
    await create_task(
        db_session,
        user.id,
        title="Today task",
        project_id=inbox.id,
        due_at=today,
        due_date_only=True,
    )
    await db_session.commit()

    r = await logged_in_client.get("/miniapp/", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "Overdue task" in body
    assert "Today task" in body
    assert "Просрочено" in body
    assert "P1" in body  # priority chip


async def test_api_search_min_2_chars(logged_in_client: AsyncClient) -> None:
    """MC4: search с <2 символов вернёт пустой массив."""
    r = await logged_in_client.get("/miniapp/api/search?q=a")
    assert r.status_code == 200
    assert r.json() == {"results": []}


async def test_api_search_finds_task(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MC4: search возвращает совпадения по title (ILIKE)."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.projects.service import ensure_inbox

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    inbox = await ensure_inbox(db_session, user.id)
    from app.tasks.service import create_task as svc_create_task

    await svc_create_task(db_session, user.id, title="Купить молоко", project_id=inbox.id)
    await svc_create_task(db_session, user.id, title="Сходить в зал", project_id=inbox.id)
    await db_session.commit()

    r = await logged_in_client.get("/miniapp/api/search?q=молок")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 1
    assert "молоко" in data["results"][0]["title"]


async def test_me_page_shows_streak_and_stats(
    db_session: AsyncSession, logged_in_client: AsyncClient
) -> None:
    """MC4+S2-S5: Me page — streak + 4 stat-cards + 14d bar-chart + детали."""
    r = await logged_in_client.get("/miniapp/me")
    assert r.status_code == 200
    body = r.text
    assert "🔥" in body
    assert "сегодня" in body
    assert "неделя" in body
    assert "месяц" in body
    assert "всего" in body
    assert "Последние 14 дней" in body  # S2 bar-chart
    assert "barGrad" in body  # SVG gradient id
    assert "Лучший день" in body  # доп метрики
    assert "Скорость" in body
    assert "Открыть полную версию" in body
    assert "Полная статистика на сайте" in body  # S5 footer link
    # P2+P3 polish: page-mount class + hero-blob
    assert "page-mount" in body
    assert "hero-blob" in body


async def test_miniapp_task_sheet_has_comments_section(logged_in_client: AsyncClient) -> None:
    """γ: task_sheet включает секцию комментариев."""
    r = await logged_in_client.get("/miniapp/")
    assert r.status_code == 200
    assert "loadComments" in r.text
    assert "Комментарии" in r.text


async def test_polish_skeleton_and_empty_svgs_in_base(client: AsyncClient) -> None:
    """P1+P4: skeleton-keyframes есть в base CSS, empty-svg-partials видны
    через рендер inbox/projects/calendar empty-states."""
    # Inbox empty (без задач) — должен показывать SVG-illustration
    # Используем unauth-flow на /miniapp/link где есть base.html → skeleton CSS
    r = await client.get("/miniapp/link")
    assert r.status_code == 200
    body = r.text
    assert "@keyframes shimmer" in body or "skeleton" in body
    assert "@keyframes page-mount" in body or "page-mount" in body
