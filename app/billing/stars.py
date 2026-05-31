"""Telegram Stars (XTR) payment flow — invoice creation, signing, and the
idempotent application of successful payments to user.tier / user.pro_until.

Why HMAC-signed payloads:
- Telegram's `invoice_payload` is an arbitrary ≤128-byte string we pick, and
  Telegram echoes it back verbatim in the `pre_checkout_query` and the
  `SuccessfulPayment` update. We use it as the «receipt» that tells us WHICH
  user is paying for WHICH product.
- Without a signature, a malicious user could craft a fake invoice URL with
  a different product code and pay for «pro_forever» at the price of «pro_1m».
  HMAC over (user_id, product_code, nonce) with our secret prevents tampering.
- Bot API verifies *amount* matches what Telegram showed the user (so they
  can't pay 10 Stars and get pro_forever), but ONLY if our pre_checkout
  handler also re-checks the product → amount mapping before answering ok.

Idempotency:
- Telegram may re-deliver SuccessfulPayment if the bot crashes / network blips.
- We rely on `star_payments.telegram_payment_charge_id` UNIQUE constraint:
  second insert raises IntegrityError → service catches it → no double-credit.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import StarPayment
from app.billing.products import BY_CODE, Product, get_product
from app.config import get_settings

logger = logging.getLogger("doday.billing.stars")


# ---------------------------------------------------------------------------
# Payload signing — HMAC-SHA256, base64url, short enough to fit in Telegram's
# 128-byte invoice_payload limit.
#
# Payload format: `v1:{product_code}:{user_id_hex}:{nonce_hex}:{sig_b64url}`
# where sig = HMAC_SHA256(secret, f"v1:{code}:{user_id}:{nonce}")[:18 chars].
# ---------------------------------------------------------------------------

_PAYLOAD_VERSION = "v1"
_SIG_BYTES = 12  # 12 bytes → 16 b64url chars; sufficient for non-repudiation
_NONCE_BYTES = 8


def _secret() -> bytes:
    """Derive the HMAC secret from app_secret_key — already in env, rotation-safe."""
    return hashlib.sha256(get_settings().app_secret_key.encode()).digest()


def sign_payload(product_code: str, user_id: UUID, nonce: str | None = None) -> str:
    """Build a signed `v1:code:user:nonce:sig` payload (URL-safe, ≤80 chars)."""
    if nonce is None:
        nonce = secrets.token_hex(_NONCE_BYTES)
    body = f"{_PAYLOAD_VERSION}:{product_code}:{user_id.hex}:{nonce}"
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()[:_SIG_BYTES]
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{body}:{sig_b64}"


class PayloadError(Exception):
    """Raised when the payload is malformed or signature mismatches."""


def verify_payload(payload: str) -> tuple[str, UUID, str]:
    """Verify signature; return (product_code, user_id, nonce). Raises PayloadError."""
    parts = payload.split(":")
    if len(parts) != 5 or parts[0] != _PAYLOAD_VERSION:
        raise PayloadError("malformed payload")
    _, product_code, user_id_hex, nonce, sig_b64 = parts
    body = f"{_PAYLOAD_VERSION}:{product_code}:{user_id_hex}:{nonce}"
    expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()[:_SIG_BYTES]
    # base64url decoder is lenient about missing padding; restore it.
    padded = sig_b64 + "=" * (-len(sig_b64) % 4)
    try:
        received = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise PayloadError("bad signature encoding") from exc
    if not hmac.compare_digest(expected, received):
        raise PayloadError("signature mismatch")
    try:
        user_id = UUID(hex=user_id_hex)
    except ValueError as exc:
        raise PayloadError("bad user_id in payload") from exc
    return product_code, user_id, nonce


# ---------------------------------------------------------------------------
# Bot API — createInvoiceLink. We don't need a long-running bot client; we just
# POST to api.telegram.org with our bot token. This keeps the web app free of
# python-telegram-bot Application/Updater bookkeeping.
# ---------------------------------------------------------------------------


class StarsError(Exception):
    """Bot API call failed."""


def _bot_token_for_product(product_code: str) -> str:
    """Return the bot token whose Stars-balance should hold this product's revenue.

    Lessio products (`tutor_pro_*`) live on @LessioBot for brand separation +
    isolated revenue accounting. All other Doday Tasks products (`pro_*`,
    `family_*`) live on @DodayTaskBot. Raises StarsError if the matching token
    is not configured.
    """
    settings = get_settings()
    if product_code.startswith("tutor_pro_"):
        if not settings.lessio_bot_token:
            raise StarsError("LESSIO_BOT_TOKEN не задан — Stars-платежи для Lessio отключены")
        return settings.lessio_bot_token
    if not settings.telegram_bot_token:
        raise StarsError("TELEGRAM_BOT_TOKEN не задан — Stars-платежи отключены")
    return settings.telegram_bot_token


async def create_invoice_link(user: User, product_code: str) -> str:
    """Ask Telegram for an `https://t.me/$...` link that opens the payment dialog.

    The user opens the URL inside Telegram (Mini App, chat, browser-deeplink) →
    Telegram shows the Stars-purchase prompt → after confirm, sends
    pre_checkout_query then successful_payment to our bot. The invoice is
    routed to the bot returned by `_bot_token_for_product` — Doday products
    invoice @DodayTaskBot, Lessio products invoice @LessioBot.
    """
    product = get_product(product_code)
    if product is None:
        raise StarsError(f"неизвестный продукт: {product_code}")
    bot_token = _bot_token_for_product(product_code)

    payload = sign_payload(product_code, user.id)
    url = f"https://api.telegram.org/bot{bot_token}/createInvoiceLink"
    body = {
        "title": product.title,
        "description": product.description,
        "payload": payload,
        # Empty provider_token signals Stars (XTR) — Bot API contract.
        "provider_token": "",
        "currency": "XTR",
        "prices": [{"label": product.title, "amount": product.stars_amount}],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=body)
    if resp.status_code != 200:
        raise StarsError(f"Bot API {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if not data.get("ok"):
        raise StarsError(f"Bot API rejected: {data.get('description', 'unknown')}")
    invoice_url = data["result"]
    if not isinstance(invoice_url, str):
        raise StarsError("Bot API returned non-string result")
    return invoice_url


# ---------------------------------------------------------------------------
# Pre-checkout validation — Telegram waits up to 10 seconds for our answer
# before declining the user's payment. The handler in app/telegram/bot.py
# calls this; if it returns (False, reason), bot answers pre_checkout_query
# with `ok=False` and Telegram shows `reason` to the user.
# ---------------------------------------------------------------------------


def validate_pre_checkout(
    payload: str,
    declared_stars_amount: int,
) -> tuple[bool, str | None, Product | None]:
    """Verify signature + that the declared amount matches the catalog price.

    Returns (ok, reason_if_not_ok, product). Reasons are user-facing; the
    payload check is paranoia — even if signature passes, mismatched amount
    means someone tampered with the invoice between createInvoiceLink and
    payment-dialog (shouldn't happen, but defence-in-depth).
    """
    try:
        product_code, _user_id, _nonce = verify_payload(payload)
    except PayloadError:
        return False, "Невалидный счёт (проверьте обновление приложения).", None
    product = get_product(product_code)
    if product is None:
        return False, f"Продукт «{product_code}» больше не доступен.", None
    if declared_stars_amount != product.stars_amount:
        logger.warning(
            "pre_checkout amount mismatch: payload says %s, Telegram says %s",
            product.stars_amount,
            declared_stars_amount,
        )
        return False, "Цена изменилась. Закройте окно и попробуйте снова.", None
    return True, None, product


# ---------------------------------------------------------------------------
# Apply payment — runs from the Telegram bot handler when SuccessfulPayment
# update arrives. Idempotent via DB unique constraint on charge_id.
# ---------------------------------------------------------------------------


async def apply_successful_payment(
    session: AsyncSession,
    *,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: str | None,
    payload: str,
    stars_amount: int,
) -> StarPayment | None:
    """Persist the payment + extend user's pro_until. Idempotent.

    Returns the StarPayment row (existing or newly created), or None if the
    payload couldn't be verified — caller should log and notify the user.
    """
    try:
        product_code, user_id, _nonce = verify_payload(payload)
    except PayloadError as exc:
        logger.error("payload verification failed: %s (raw=%s)", exc, payload[:60])
        return None
    product = get_product(product_code)
    if product is None:
        logger.error("unknown product in successful payment: %s", product_code)
        return None

    # Idempotency: try-insert; if charge_id seen before, fetch existing and exit.
    payment = StarPayment(
        user_id=user_id,
        telegram_payment_charge_id=telegram_payment_charge_id,
        provider_payment_charge_id=provider_payment_charge_id,
        product_code=product_code,
        stars_amount=stars_amount,
        invoice_payload=payload,
        status="paid",
    )
    session.add(payment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(
                select(StarPayment).where(
                    StarPayment.telegram_payment_charge_id == telegram_payment_charge_id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.info(
                "duplicate SuccessfulPayment ignored: charge_id=%s",
                telegram_payment_charge_id,
            )
            return existing
        # Some other integrity error — surface it.
        raise

    # Extend the user's paid period.
    user = await session.get(User, user_id)
    if user is None:
        logger.error("paid user not found: %s", user_id)
        return payment

    # Tier products (Doday Tasks / Lessio) extend the global tier + pro_until.
    # Entitlement-only products (ПДД) leave the tier untouched — grants_tier None.
    if product.grants_tier is not None:
        user.tier = product.grants_tier
        if product.duration_months is None:
            # Lifetime — set far future (year 2099) so effective_tier always sees
            # it as active. We don't use None because that would clash with the
            # «never had Pro» semantics elsewhere.
            user.pro_until = datetime(2099, 12, 31, tzinfo=UTC)
        else:
            # Extend from max(now, current pro_until). Renewals don't lose remaining days.
            now = datetime.now(UTC)
            base = user.pro_until if (user.pro_until and user.pro_until > now) else now
            user.pro_until = base + timedelta(days=30 * product.duration_months)

    # Entitlement products (ПДД, future verticals) upsert a per-feature grant
    # without touching the global tier.
    if product.grants_entitlement is not None:
        await _grant_entitlement(session, user_id, product)

    logger.info(
        "applied star payment: user=%s product=%s stars=%s pro_until=%s",
        user_id,
        product_code,
        stars_amount,
        user.pro_until.isoformat() if user.pro_until else None,
    )
    return payment


async def _grant_entitlement(session: AsyncSession, user_id: UUID, product: Product) -> None:
    """Upsert the per-feature Entitlement for an entitlement product (idempotent
    on renewal). Lifetime grants set expires_at=None and never downgrade to a
    dated expiry. Dated renewals extend from max(now, current expiry)."""
    from app.billing.models import Entitlement

    feature = product.grants_entitlement
    if feature is None:  # caller guarantees non-None; narrow for the type checker
        return
    ent = (
        await session.execute(
            select(Entitlement).where(
                Entitlement.user_id == user_id,
                Entitlement.feature == feature,
            )
        )
    ).scalar_one_or_none()

    if product.duration_months is None:
        new_expiry: datetime | None = None  # lifetime
    else:
        now = datetime.now(UTC)
        if ent is not None and ent.expires_at is not None and ent.expires_at > now:
            base = ent.expires_at
        else:
            base = now
        new_expiry = base + timedelta(days=30 * product.duration_months)

    if ent is None:
        session.add(
            Entitlement(
                user_id=user_id,
                feature=feature,
                expires_at=new_expiry,
                source_code=product.code,
            )
        )
        return
    # Existing grant: a lifetime grant never downgrades to a dated one.
    if ent.expires_at is None:
        return
    ent.expires_at = new_expiry
    ent.source_code = product.code


# ---------------------------------------------------------------------------
# Refund — admin-only. Telegram allows refunds within 21 days of payment.
# ---------------------------------------------------------------------------


async def refund_payment(
    session: AsyncSession, payment: StarPayment, *, reason: str | None = None
) -> bool:
    """Call Bot API refundStarPayment, mark row refunded, and roll back pro_until.

    Returns True on success. On Bot API failure (e.g. >21 days) we keep the
    row as `paid` so the admin sees the error reason. Routes through the same
    bot token that issued the original invoice (Lessio products → @LessioBot;
    Doday products → @DodayTaskBot).
    """
    if payment.status == "refunded":
        return True  # idempotent admin click
    bot_token = _bot_token_for_product(payment.product_code)

    url = f"https://api.telegram.org/bot{bot_token}/refundStarPayment"
    body: dict[str, Any] = {
        "user_id": _telegram_user_id_for(session, payment.user_id),
        "telegram_payment_charge_id": payment.telegram_payment_charge_id,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=body)
    if resp.status_code != 200 or not resp.json().get("ok"):
        logger.warning("refund failed: %s %s", resp.status_code, resp.text[:200])
        return False

    payment.status = "refunded"
    payment.refunded_at = datetime.now(UTC)
    payment.refund_reason = (reason or "")[:500]

    # Roll back: shrink pro_until by the refunded duration (tier products).
    product = get_product(payment.product_code)
    if product is not None and product.duration_months is not None:
        if product.grants_tier is not None:
            user = await session.get(User, payment.user_id)
            if user is not None and user.pro_until is not None:
                user.pro_until = user.pro_until - timedelta(days=30 * product.duration_months)
                if user.pro_until <= datetime.now(UTC):
                    user.pro_until = None
                    user.tier = "free"
        # Symmetric rollback for entitlement products (ПДД): shrink the grant,
        # delete it once it lapses. Lifetime grants (None) are left as-is.
        if product.grants_entitlement is not None:
            from app.billing.models import Entitlement

            ent = (
                await session.execute(
                    select(Entitlement).where(
                        Entitlement.user_id == payment.user_id,
                        Entitlement.feature == product.grants_entitlement,
                    )
                )
            ).scalar_one_or_none()
            if ent is not None and ent.expires_at is not None:
                ent.expires_at = ent.expires_at - timedelta(days=30 * product.duration_months)
                if ent.expires_at <= datetime.now(UTC):
                    await session.delete(ent)
    return True


async def _telegram_user_id_for(session: AsyncSession, user_id: UUID) -> int:
    """Look up the Telegram chat_id (== user id for private chats) for refunds."""
    from app.telegram.models import TelegramLink

    row = (
        await session.execute(select(TelegramLink.chat_id).where(TelegramLink.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        raise StarsError("у пользователя нет привязанного Telegram-аккаунта для возврата")
    return int(row)


# Re-export for service-layer callers — keeps imports tidy.
__all__ = [
    "BY_CODE",
    "PayloadError",
    "Product",
    "StarsError",
    "apply_successful_payment",
    "create_invoice_link",
    "refund_payment",
    "sign_payload",
    "validate_pre_checkout",
    "verify_payload",
]
