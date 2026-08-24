"""Billing ORM — star_payments idempotency + audit log.

Telegram sends `SuccessfulPayment` updates that may be re-delivered if the bot
crashes between processing and acknowledging. We insert one row per charge with
a unique constraint on `telegram_payment_charge_id`; the second delivery hits
`IntegrityError`, which the service layer treats as «already processed».
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Sequence,
    String,
    UniqueConstraint,
)
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


class Entitlement(Base):
    """A per-user, per-feature access grant.

    Deliberately generic: each new Doday vertical (``pdd_pro`` today, future
    exam/interview verticals) reuses this one table with a different ``feature``
    key instead of bolting per-product columns onto ``users``. Independent of the
    global ``user.tier`` — buying ПДД Pro must not unlock Doday Tasks Pro and vice
    versa. A grant is active while ``expires_at`` is NULL (lifetime) or in the
    future; renewals extend ``expires_at`` in place (one row per user+feature).
    """

    __tablename__ = "entitlements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature: Mapped[str] = mapped_column(String(40), nullable=False)
    # NULL == lifetime. Otherwise active while expires_at is in the future.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Catalog code that last granted/extended this entitlement (audit/forensics).
    source_code: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "feature", name="uq_entitlement_user_feature"),)


class CardPayment(Base):
    """Платёж картой или через СБП через внешнего эквайера.

    Отдельная таблица от ``star_payments``, а не общая «payments»: у провайдеров
    разные идентификаторы, разный жизненный цикл (у Stars нет состояния
    «ожидает оплаты») и разные поля возврата. Смешивать их в одну таблицу
    значило бы половину колонок держать NULL и разбирать провайдера в каждом
    запросе.

    Идемпотентность: ЮKassa повторяет webhook, пока не получит 200, поэтому
    ``yookassa_payment_id`` уникален — повторная доставка падает в
    ``IntegrityError``, и сервис считает её «уже обработано». Тот же приём, что
    и для Telegram-платежей.
    """

    __tablename__ = "card_payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Кто провёл платёж: 'yookassa', 'robokassa', ... Провайдера пришлось
    # вынести в колонку: ЮKassa с 29.12.2025 прекратила обслуживать самозанятых,
    # и выбор эквайера теперь может меняться без переписывания схемы.
    # Робокассе нужен ЧИСЛОВОЙ номер счёта (InvId), UUID она не принимает.
    # Держим отдельную последовательность: номер должен быть уникальным в
    # пределах магазина и монотонным, иначе повторная оплата ломает сверку.
    inv_id: Mapped[int] = mapped_column(
        BigInteger,
        Sequence("card_payment_inv_id_seq"),
        nullable=False,
        unique=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # Идентификатор платежа на стороне провайдера — ключ идемпотентности вебхука.
    provider_payment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Код позиции каталога — см. app.billing.products.PRODUCTS.
    product_code: Mapped[str] = mapped_column(String(50), nullable=False)
    # Сумма в КОПЕЙКАХ: хранить деньги во float нельзя, а в рублях нельзя из-за
    # возможных дробных цен и скидок. В ЮKassa уходит строкой «199.00».
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    # pending → succeeded | canceled. Права выдаём только на succeeded.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Ссылка на страницу оплаты — на случай если пользователь потерял вкладку.
    confirmation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Идемпотентность в паре: у разных провайдеров идентификаторы могут совпасть.
    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id", name="uq_card_payment_provider_id"),
    )
