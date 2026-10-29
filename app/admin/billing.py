"""A single, read-only ledger for card and Stars payments."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import Select, String, case, cast, false, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app import timezones
from app.auth.models import User
from app.billing.models import ArchivedPayment, CardPayment, StarPayment
from app.billing.products import get_product


class PaymentFilters(BaseModel):
    q: str = Field(default="", max_length=160)
    provider: Literal["all", "robokassa", "stars"] = "all"
    status: Literal["all", "paid", "pending", "refunded", "canceled"] = "all"
    product: str = Field(default="", max_length=50)
    since: date | None = None
    until: date | None = Field(default=None, le=date(9999, 12, 30))
    mode: Literal["live", "test", "all"] = "live"
    sort: Literal["newest", "oldest", "amount_desc", "amount_asc", "email", "product"] = "newest"
    page: int = Field(default=1, ge=1, le=100000)
    per_page: int = Field(default=25, ge=10, le=100)

    @model_validator(mode="after")
    def valid_period(self) -> "PaymentFilters":
        if self.since and self.until and self.since > self.until:
            raise ValueError("Начало периода должно быть раньше окончания")
        return self


class PaymentRow(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    product_code: str
    provider: str
    currency: str
    amount: int
    status: str
    occurred_at: datetime
    refunded_at: datetime | None
    reference: str
    is_test: bool

    @property
    def product_title(self) -> str:
        product = get_product(self.product_code)
        return product.title if product else self.product_code

    @property
    def amount_label(self) -> str:
        return (
            format_rubles(self.amount)
            if self.currency == "RUB"
            else f"{self.amount:,} ⭐".replace(",", " ")
        )


class BillingSummary(BaseModel):
    payments: int = 0
    buyers: int = 0
    rub_gross: int = 0
    rub_refunded: int = 0
    stars_gross: int = 0
    stars_refunded: int = 0
    pending: int = 0
    active_subscriptions: int = 0

    @property
    def rub_net_label(self) -> str:
        return format_rubles(self.rub_gross - self.rub_refunded)

    @property
    def rub_refunded_label(self) -> str:
        return format_rubles(self.rub_refunded)

    @property
    def stars_net(self) -> int:
        return self.stars_gross - self.stars_refunded


class PaymentPage(BaseModel):
    items: list[PaymentRow]
    total: int
    page: int
    pages: int
    summary: BillingSummary


def format_rubles(kopecks: int) -> str:
    sign = "-" if kopecks < 0 else ""
    whole, fraction = divmod(abs(kopecks), 100)
    grouped = f"{whole:,}".replace(",", " ")
    return f"{sign}{grouped},{fraction:02d} ₽"


def request_filters[FilterModel: BaseModel](
    request: Request, model: type[FilterModel], prefix: str = ""
) -> FilterModel:
    values = {
        key: request.query_params[prefix + key]
        for key in model.model_fields
        if request.query_params.get(prefix + key, "") != ""
    }
    try:
        return model.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors(include_context=False)) from exc


def ledger() -> Subquery:
    cards = select(
        CardPayment.id,
        CardPayment.user_id,
        CardPayment.product_code,
        CardPayment.provider,
        literal("RUB").label("currency"),
        CardPayment.amount_kopecks.label("amount"),
        case((CardPayment.status == "succeeded", "paid"), else_=CardPayment.status).label("status"),
        func.coalesce(CardPayment.paid_at, CardPayment.created_at).label("occurred_at"),
        CardPayment.refunded_at,
        CardPayment.provider_payment_id.label("reference"),
        CardPayment.is_test,
    )
    stars = select(
        StarPayment.id,
        StarPayment.user_id,
        StarPayment.product_code,
        literal("stars"),
        literal("XTR"),
        StarPayment.stars_amount,
        StarPayment.status,
        StarPayment.created_at,
        StarPayment.refunded_at,
        StarPayment.telegram_payment_charge_id,
        false(),
    )
    archived = select(
        ArchivedPayment.id,
        ArchivedPayment.buyer_id,
        ArchivedPayment.product_code,
        ArchivedPayment.provider,
        ArchivedPayment.currency,
        ArchivedPayment.amount,
        ArchivedPayment.status,
        ArchivedPayment.occurred_at,
        ArchivedPayment.refunded_at,
        ArchivedPayment.reference,
        ArchivedPayment.is_test,
    )
    return union_all(cards, stars, archived).subquery("payments")


def filtered_ledger(filters: PaymentFilters, tz: str | None) -> Subquery:
    rows = ledger()
    stmt = select(rows, func.coalesce(User.email, "Удалённый аккаунт").label("email")).outerjoin(
        User, User.id == rows.c.user_id
    )
    if filters.provider != "all":
        stmt = stmt.where(rows.c.provider == filters.provider)
    if filters.status != "all":
        stmt = stmt.where(rows.c.status == filters.status)
    if filters.product:
        stmt = stmt.where(rows.c.product_code == filters.product)
    if filters.mode != "all":
        stmt = stmt.where(rows.c.is_test == (filters.mode == "test"))
    zone = ZoneInfo(timezones.normalize(tz))
    if filters.since:
        stmt = stmt.where(rows.c.occurred_at >= datetime.combine(filters.since, time.min, zone))
    if filters.until:
        stmt = stmt.where(
            rows.c.occurred_at < datetime.combine(filters.until + timedelta(days=1), time.min, zone)
        )
    if filters.q.strip():
        needle = (
            "%"
            + filters.q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        stmt = stmt.where(
            User.email.ilike(needle, escape="\\")
            | rows.c.reference.ilike(needle, escape="\\")
            | cast(rows.c.id, String).ilike(needle, escape="\\")
        )
    return stmt.subquery("filtered_payments")


async def summarize(session: AsyncSession, rows: Subquery) -> BillingSummary:
    c = rows.c
    received = c.status.in_(["paid", "refunded"])

    def total(currency: str, refunded: bool = False) -> Any:
        condition = (c.currency == currency) & (c.status == "refunded" if refunded else received)
        return func.coalesce(func.sum(case((condition, c.amount), else_=0)), 0)

    result = (
        (
            await session.execute(
                select(
                    func.count(case((received, 1))).label("payments"),
                    func.count(func.distinct(case((received, c.user_id)))).label("buyers"),
                    total("RUB").label("rub_gross"),
                    total("RUB", True).label("rub_refunded"),
                    total("XTR").label("stars_gross"),
                    total("XTR", True).label("stars_refunded"),
                    func.count(case((c.status == "pending", 1))).label("pending"),
                ).select_from(rows)
            )
        )
        .mappings()
        .one()
    )
    return BillingSummary.model_validate(dict(result))


def sorted_payments(rows: Subquery, filters: PaymentFilters) -> Select[Any]:
    c = rows.c
    sorts: dict[str, list[Any]] = {
        "newest": [c.occurred_at.desc()],
        "oldest": [c.occurred_at.asc()],
        # Currency first: a Star is not a ruble or a kopeck.
        "amount_desc": [c.currency, c.amount.desc()],
        "amount_asc": [c.currency, c.amount.asc()],
        "email": [c.email],
        "product": [c.product_code],
    }
    return select(rows).order_by(*sorts[filters.sort], c.occurred_at.desc(), c.id)


async def payment_page(
    session: AsyncSession, filters: PaymentFilters, tz: str | None
) -> PaymentPage:
    rows = filtered_ledger(filters, tz)
    total = int((await session.execute(select(func.count()).select_from(rows))).scalar_one())
    pages = max(1, (total + filters.per_page - 1) // filters.per_page)
    page = min(filters.page, pages)
    result = await session.execute(
        sorted_payments(rows, filters).offset((page - 1) * filters.per_page).limit(filters.per_page)
    )
    return PaymentPage(
        items=[PaymentRow.model_validate(dict(row)) for row in result.mappings()],
        total=total,
        page=page,
        pages=pages,
        summary=await summarize(session, rows),
    )


async def lifetime_summary(session: AsyncSession) -> BillingSummary:
    summary = await summarize(session, filtered_ledger(PaymentFilters(), None))
    summary.active_subscriptions = int(
        (
            await session.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.tier.in_(["pro", "team", "family"]),
                    User.pro_until > datetime.now(UTC),
                )
            )
        ).scalar_one()
    )
    return summary


async def export_payments(
    session: AsyncSession, filters: PaymentFilters, tz: str | None
) -> list[PaymentRow]:
    rows = filtered_ledger(filters, tz)
    result = await session.execute(sorted_payments(rows, filters).limit(5000))
    return [PaymentRow.model_validate(dict(row)) for row in result.mappings()]
