"""Billing ORM — star_payments idempotency + audit log.

Telegram sends `SuccessfulPayment` updates that may be re-delivered if the bot
crashes between processing and acknowledging. We insert one row per charge with
a unique constraint on `telegram_payment_charge_id`; the second delivery hits
`IntegrityError`, which the service layer treats as «already processed».
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class StarPayment(Base):
    __tablename__ = "star_payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Telegram's idempotency key from the SuccessfulPayment update.
    telegram_payment_charge_id: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True
    )
    # Payment provider's reference (e.g. Telegram Stars internal txn id).
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Catalog code — see app.billing.products.PRODUCTS.
    product_code: Mapped[str] = mapped_column(String(50), nullable=False)
    stars_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # The signed payload that we sent to Telegram in createInvoiceLink. Kept for
    # forensics — if signature ever rotates, we can still trace back.
    invoice_payload: Mapped[str] = mapped_column(String(200), nullable=False)
    # paid → refunded after a successful refundStarPayment call.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
