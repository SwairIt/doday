"""Business logic for school portal integrations.

Holds the provider registry and a stub `sync_now` that documents what
credentials each provider would need. Real network calls are intentionally
not implemented yet — they'll go behind the same `_fetch_<provider>` seam
once the user provides a token in `.env` (see docs/school_integrations.md).
"""

from datetime import UTC, datetime
from uuid import UUID

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
    """Trigger a sync for the given provider.

    Right now this is a documented stub: with no real auth_token configured
    against a working portal it returns `ok=False` with an explanation. The
    intent is that once the user pastes a real token (or we wire up gosuslugi
    OAuth) the `_fetch_*` helpers below get filled in and the rest of the
    pipeline (parse → diff → create_task) Just Works.
    """
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
    except NotImplementedError as e:
        return _save_error(session, integ, str(e))

    integ.last_sync_at = datetime.now(UTC)
    integ.last_error = None
    await session.commit()
    logger.info("school_sync_ok", provider=provider, items=len(payload))
    return SyncResult(ok=True, pulled=len(payload), created=0)


def _save_error(session: AsyncSession, integ: SchoolIntegration, msg: str) -> SyncResult:
    integ.last_error = msg[:500]
    # Best-effort error log — caller awaits commit anyway
    return SyncResult(ok=False, error=msg)


async def _fetch_school_mo(auth_token: str) -> list[dict[str, object]]:
    """Fetch homework from Школьный портал МО.

    Required env (when ready to wire in real HTTP):
      SCHOOL_MO_BASE_URL    = https://school.mosreg.ru/api  (or current host)
      SCHOOL_MO_USER_AGENT  = Doday/1.0 (+contact@…)        (optional)

    Required user input (saved in school_integrations.auth_token):
      cookie/JWT from a logged-in browser session — exact format TBD,
      typically the value of `aupd_token` cookie or an `Authorization` header.
    """
    raise NotImplementedError(
        "Школьный портал МО: нужен auth_token — открой школьный портал в браузере, "
        "F12 → Application → Cookies → скопируй значение `aupd_token`. "
        "Затем сохрани его в Профиле."
    )


async def _fetch_mesh(auth_token: str) -> list[dict[str, object]]:
    """Fetch homework from МЭШ (dnevnik.mos.ru).

    Required env:
      MESH_BASE_URL = https://school.mos.ru/api/family/web/v1

    Required user input:
      auth_token from `auth_token` cookie on dnevnik.mos.ru after login.
    """
    raise NotImplementedError(
        "МЭШ: нужен auth_token из cookie `auth_token` на dnevnik.mos.ru. "
        "Открой dnevnik.mos.ru → войди → F12 → Cookies → скопируй значение."
    )


def provider_label(provider: Provider) -> str:
    return PROVIDER_LABELS.get(provider, provider)
