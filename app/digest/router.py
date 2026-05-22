"""HTTP routes for the morning digest.

Two endpoints:
- POST /api/digest/send-now — self-test, sends digest to the signed-in user.
- POST /api/digest/cron-trigger — system cron entry. Validated by X-Cron-Token
  header against settings.cron_token (empty in dev → 503 to make accidental
  exposure noisy).
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.auth.deps import DbSession, RequiredUser
from app.config import get_settings
from app.digest.service import send_morning_digest, send_morning_digests_for_all_users

router = APIRouter(prefix="/api/digest", tags=["digest"])


@router.post("/send-now")
async def send_now(user: RequiredUser, session: DbSession) -> dict[str, bool | str]:
    """Send the digest to the current user — for manual testing.

    Returns {sent: True} on success, {sent: False, reason: 'no-tasks'} when
    skipping because the user has nothing on the plan today.
    """
    sent = await send_morning_digest(session, user)
    return {"sent": sent, "reason": "ok" if sent else "no-tasks"}


@router.post("/cron-trigger")
async def cron_trigger(
    session: DbSession,
    x_cron_token: Annotated[str | None, Header(alias="X-Cron-Token")] = None,
) -> dict[str, int]:
    """System cron pings this once per day. Header must match settings.cron_token."""
    settings = get_settings()
    if not settings.cron_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CRON_TOKEN не задан в окружении — endpoint отключён",
        )
    if not x_cron_token or not hmac.compare_digest(x_cron_token, settings.cron_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid cron token")
    return await send_morning_digests_for_all_users(session)
