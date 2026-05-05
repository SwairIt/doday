"""Business logic for school portal integrations.

Talks to school.mosreg.ru (Школьный портал МО) and dnevnik.mos.ru (МЭШ) via
their family-web JSON API using the user-supplied `aupd_token` cookie.
Failures surface real HTTP details so the user can debug a stale token.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.school.models import SchoolIntegration
from app.school.schemas import PROVIDER_LABELS, IntegrationIn, Provider, SyncResult

logger = structlog.get_logger(__name__)


class IntegrationNotFound(Exception):
    """Asked for an integration that doesn't exist for this user."""


async def list_integrations(session: AsyncSession, user_id: UUID) -> list[SchoolIntegration]:
    result = await session.execute(
        select(SchoolIntegration).where(SchoolIntegration.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_integration(
    session: AsyncSession, user_id: UUID, provider: Provider
) -> SchoolIntegration | None:
    result = await session.execute(
        select(SchoolIntegration).where(
            SchoolIntegration.user_id == user_id, SchoolIntegration.provider == provider
        )
    )
    return result.scalar_one_or_none()


async def upsert_integration(
    session: AsyncSession, user_id: UUID, payload: IntegrationIn
) -> SchoolIntegration:
    existing = await get_integration(session, user_id, payload.provider)
    if existing is None:
        existing = SchoolIntegration(
            user_id=user_id,
            provider=payload.provider,
            auth_token=payload.auth_token,
            target_project_id=payload.target_project_id,
            enabled=payload.enabled,
        )
        session.add(existing)
    else:
        existing.auth_token = payload.auth_token
        existing.target_project_id = payload.target_project_id
        existing.enabled = payload.enabled
        existing.last_error = None
    await session.commit()
    await session.refresh(existing)
    return existing


async def delete_integration(session: AsyncSession, user_id: UUID, provider: Provider) -> None:
    integ = await get_integration(session, user_id, provider)
    if integ is None:
        raise IntegrationNotFound(provider)
    await session.delete(integ)
    await session.commit()


async def sync_now(session: AsyncSession, user_id: UUID, provider: Provider) -> SyncResult:
    """Pull homework from a school portal and create matching Doday tasks."""
    integ = await get_integration(session, user_id, provider)
    if integ is None:
        raise IntegrationNotFound(provider)
    if not integ.enabled:
        return SyncResult(ok=False, error="Интеграция выключена.")
    if not integ.auth_token:
        return _save_error(session, integ, "Не задан auth_token.")

    try:
        if provider == "school_mo":
            payload = await _fetch_school_mo(integ.auth_token)
        elif provider == "mesh":
            payload = await _fetch_mesh(integ.auth_token)
        else:  # pragma: no cover — Literal["school_mo","mesh"] guards this
            return _save_error(session, integ, f"Неизвестный провайдер: {provider}")
    except _PortalError as e:
        await session.commit()  # persist last_error from _save_error
        return _save_error(session, integ, str(e))

    created = await _create_tasks_from_payload(
        session, user_id, integ.target_project_id, payload
    )

    integ.last_sync_at = datetime.now(UTC)
    integ.last_error = None
    await session.commit()
    logger.info("school_sync_ok", provider=provider, pulled=len(payload), created=created)
    return SyncResult(ok=True, pulled=len(payload), created=created)


def _save_error(session: AsyncSession, integ: SchoolIntegration, msg: str) -> SyncResult:
    integ.last_error = msg[:500]
    return SyncResult(ok=False, error=msg)


class _PortalError(Exception):
    """Anything went wrong talking to the school portal (auth, HTTP, parse)."""


# ---------------------------------------------------------------------------
# Школьный портал МО — school.mosreg.ru. Real-world: auth via aupd_token cookie.
# We try the documented family-web v2 endpoint first, then fall back to v1 if
# the server returns 404 (different regions sometimes lag on rollouts).
# ---------------------------------------------------------------------------

_USER_AGENT = "Doday/0.1 (+self-hosted; contact via .env SMTP_FROM)"


async def _fetch_school_mo(auth_token: str) -> list[dict[str, object]]:
    """Pull homework from Школьный портал МО using `aupd_token` cookie.

    Host is authedu.mosreg.ru (the auth+edu unified portal). Older docs may
    say school.mosreg.ru — that hostname now redirects to authedu anyway.
    """
    today = datetime.now(UTC).date()
    end = today + timedelta(days=21)
    return await _fetch_with_aupd_token(
        host="https://authedu.mosreg.ru",
        token=auth_token,
        date_from=today.isoformat(),
        date_to=end.isoformat(),
    )


async def _fetch_mesh(auth_token: str) -> list[dict[str, object]]:
    """Pull homework from МЭШ (dnevnik.mos.ru) using `auth_token` cookie."""
    today = datetime.now(UTC).date()
    end = today + timedelta(days=21)
    return await _fetch_with_aupd_token(
        host="https://dnevnik.mos.ru",
        token=auth_token,
        date_from=today.isoformat(),
        date_to=end.isoformat(),
    )


async def _fetch_with_aupd_token(
    *, host: str, token: str, date_from: str, date_to: str
) -> list[dict[str, object]]:
    """Hit the family-web homework endpoint. Surfaces HTTP details on failure."""
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        # Both portals serve their family API behind aupd_token cookie auth.
        # Some endpoints additionally honour `Authorization: Bearer <token>`.
        "Cookie": f"aupd_token={token}",
        "Authorization": f"Bearer {token}",
    }
    # Try a couple of plausible path layouts in order. First match wins.
    candidate_paths = [
        f"/api/family/web/v1/homeworks?from={date_from}&to={date_to}",
        f"/api/family/v1/homeworks?from={date_from}&to={date_to}",
        f"/api/v1/homeworks?from={date_from}&to={date_to}",
    ]
    last_error: str | None = None
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for path in candidate_paths:
            url = host + path
            try:
                response = await client.get(url, headers=headers)
            except httpx.HTTPError as e:
                last_error = f"Сеть: {e}"
                continue
            if response.status_code == 401 or response.status_code == 403:
                raise _PortalError(
                    f"Сервер ответил {response.status_code}. "
                    "Скорее всего токен истёк — обнови aupd_token в браузере и сохрани заново."
                )
            if response.status_code == 404:
                last_error = f"{url} → 404"
                continue
            if response.status_code >= 500:
                raise _PortalError(
                    f"Сервер портала ответил {response.status_code}. Попробуй позже."
                )
            if response.status_code != 200:
                raise _PortalError(
                    f"{url} → HTTP {response.status_code}: "
                    f"{response.text[:200]!s}"
                )
            try:
                data = response.json()
            except ValueError:
                raise _PortalError(
                    f"Сервер вернул не JSON по {url} (вероятно, страница логина). "
                    "Проверь токен."
                ) from None
            return _normalize_homework_payload(data)
    raise _PortalError(
        "Не нашёл рабочий API homework на портале. "
        + (f"Последняя попытка: {last_error}" if last_error else "")
    )


def _normalize_homework_payload(raw: object) -> list[dict[str, object]]:
    """Convert the various known portal shapes into a uniform homework list."""
    items: list[object] = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        for key in ("homeworks", "items", "data", "results", "payload"):
            v = raw.get(key)
            if isinstance(v, list):
                items = v
                break
    out: list[dict[str, object]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # Fields vary across deployments — pick the first key that's present.
        # `subject` may be a string OR a {"name": "..."} dict, depending on portal version.
        subj_field = it.get("subject")
        if isinstance(subj_field, dict):
            subject = subj_field.get("name") or ""
        else:
            subject = subj_field or it.get("subject_name") or ""
        body = (
            it.get("task")
            or it.get("description")
            or it.get("text")
            or it.get("homework")
            or ""
        )
        deadline = (
            it.get("deadline")
            or it.get("due_at")
            or it.get("date_to")
            or it.get("date")
        )
        external_id = str(it.get("id") or it.get("homework_id") or "")
        if not body and not subject:
            continue
        out.append(
            {
                "subject": str(subject)[:80],
                "body": str(body)[:400],
                "deadline": str(deadline) if deadline else None,
                "external_id": external_id,
            }
        )
    return out


async def import_pasted_payload(
    session: AsyncSession, user_id: UUID, provider: Provider, raw: object
) -> SyncResult:
    """Manually-imported homework JSON (from browser DevTools paste).

    Used when the portal is reachable from the user's browser (with their
    proxy/VPN extension) but not from this server. Reuses the same parsing
    + task-creation pipeline as `sync_now`.
    """
    integ = await get_integration(session, user_id, provider)
    if integ is None:
        raise IntegrationNotFound(provider)
    try:
        payload = _normalize_homework_payload(raw)
    except Exception as e:
        return _save_error(session, integ, f"Не получилось разобрать JSON: {e}")
    if not payload:
        return _save_error(
            session,
            integ,
            "В JSON не нашёл записей с предметом или текстом. "
            "Проверь что вставил полный response от /api/.../homeworks.",
        )
    created = await _create_tasks_from_payload(
        session, user_id, integ.target_project_id, payload
    )
    integ.last_sync_at = datetime.now(UTC)
    integ.last_error = None
    await session.commit()
    return SyncResult(ok=True, pulled=len(payload), created=created)


async def _create_tasks_from_payload(
    session: AsyncSession,
    user_id: UUID,
    target_project_id: UUID | None,
    payload: list[dict[str, object]],
) -> int:
    """Convert each homework into a Doday task, dedupe by title within project."""
    from sqlalchemy import select as sa_select

    from app.projects.service import ensure_inbox
    from app.tasks.models import Task as TaskModel
    from app.tasks.service import create_task

    if target_project_id is None:
        inbox = await ensure_inbox(session, user_id)
        target_project_id = inbox.id

    existing_titles_q = await session.execute(
        sa_select(TaskModel.title).where(
            TaskModel.user_id == user_id,
            TaskModel.project_id == target_project_id,
            TaskModel.deleted_at.is_(None),
        )
    )
    existing: set[str] = {row[0] for row in existing_titles_q.all()}

    created = 0
    for hw in payload:
        subject = str(hw.get("subject") or "")
        body = str(hw.get("body") or "")
        if subject and body:
            title = f"📚 {subject}: {body}"[:500]
        elif body:
            title = f"📚 {body}"[:500]
        else:
            continue
        if title in existing:
            continue
        due_at: datetime | None = None
        deadline_raw = hw.get("deadline")
        if isinstance(deadline_raw, str) and deadline_raw:
            try:
                # Accept both date-only and full ISO timestamps.
                due_at = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=UTC)
            except ValueError:
                due_at = None
        await create_task(
            session,
            user_id,
            title=title,
            project_id=target_project_id,
            due_at=due_at,
        )
        existing.add(title)
        created += 1
    return created


def provider_label(provider: Provider) -> str:
    return PROVIDER_LABELS.get(provider, provider)
