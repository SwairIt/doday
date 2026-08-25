"""Billing HTTP endpoints — read current tier, change tier (downgrade-only),
Telegram Stars invoice creation, and per-user payment history."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import desc, select

from app.auth.deps import DbSession, RequiredUser
from app.billing import robokassa
from app.billing.models import CardPayment, StarPayment
from app.billing.products import PRODUCTS, get_product
from app.billing.service import (
    TIERS,
    effective_tier,
    grant_product_access,
    is_trial_active,
    limits_for,
    purchase_state,
    trial_days_remaining,
)
from app.billing.stars import StarsError, create_invoice_link


class TierMeOut(BaseModel):
    user_id: UUID
    tier: str
    effective_tier: str
    trial_active: bool
    trial_ends_at: datetime | None
    trial_days_remaining: int
    pro_until: datetime | None
    limits: dict[str, object]


class ProductOut(BaseModel):
    code: str
    title: str
    description: str
    grants_tier: str | None
    duration_months: int | None
    stars_amount: int
    rub_amount: int
    # Прямая ссылка на оплату картой. None, когда эквайринг не настроен —
    # фронт тогда показывает только Stars.
    card_pay_url: str | None
    # Что это за покупка для ТЕКУЩЕГО пользователя: "buy" (новый тариф) или
    # "extend" (продление того, что уже есть). Уже купленное («owned») в каталог
    # не попадает вовсе — фронт по этому полю подписывает кнопку.
    state: str


class InvoiceCreateIn(BaseModel):
    product_code: str


class InvoiceCreateOut(BaseModel):
    invoice_url: str
    stars_amount: int
    product_code: str
    product_title: str


class PaymentHistoryItem(BaseModel):
    id: UUID
    product_code: str
    stars_amount: int
    status: str
    created_at: datetime
    refunded_at: datetime | None


class ChangeTierPayload(BaseModel):
    tier: Literal["free", "pro", "team"]


router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/me", response_model=TierMeOut)
async def me_endpoint(user: RequiredUser) -> TierMeOut:
    return TierMeOut(
        user_id=user.id,
        tier=user.tier,
        effective_tier=effective_tier(user),
        trial_active=is_trial_active(user),
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=trial_days_remaining(user),
        pro_until=user.pro_until,
        limits=dict(limits_for(user)),
    )


@router.get("/products", response_model=list[ProductOut])
async def list_products_endpoint(user: RequiredUser) -> list[ProductOut]:
    """Каталог покупок для Doday Tasks, отфильтрованный под ТЕКУЩИЙ тариф.

    Показываем только то, что осмысленно купить именно этому пользователю:
    - уже купленное (равный/старший тариф, либо пожизненный) — не показываем;
    - помесячное продление тому, у кого подписка уже есть, — не показываем
      (предлагаем год или «навсегда»), чтобы не было «купил год → купи месяц»;
    - остальное помечаем ``state`` = "buy" (новый тариф) / "extend" (продление).

    В бете (`BETA_FREE_FOR_ALL=true`) отдаём только founder-«навсегда»: месячные
    и годовые сбивают с толку, когда всё и так бесплатно — платят лишь за то,
    чтобы закрепить тариф до включения оплаты.

    ПДД и Lessio (`pdd_`, `tutor_`) продаются на своих страницах — в каталог
    Doday Tasks их не пускаем.
    """
    from app.config import get_settings

    beta = get_settings().beta_free_for_all
    cards_on = robokassa.is_configured()
    if beta:
        candidates = [p for p in PRODUCTS if p.code == "pro_forever"]
    else:
        candidates = [p for p in PRODUCTS if not p.code.startswith(("pdd_", "tutor_"))]

    out: list[ProductOut] = []
    for p in candidates:
        state = purchase_state(user, p)
        if state == "owned":
            continue  # уже есть — не предлагаем
        if state == "extend" and p.duration_months is not None and p.duration_months < 12:
            # У пользователя уже есть подписка этого тарифа — помесячное продление
            # не показываем: пусть берёт год или «навсегда».
            continue
        out.append(
            ProductOut(
                code=p.code,
                title=p.title,
                description=p.description,
                grants_tier=p.grants_tier,
                duration_months=p.duration_months,
                stars_amount=p.stars_amount,
                rub_amount=p.rub_amount,
                card_pay_url=(f"/api/billing/pay/{p.code}" if cards_on else None),
                state=state,
            )
        )
    return out


@router.post("/stars/invoice", response_model=InvoiceCreateOut)
async def create_stars_invoice(payload: InvoiceCreateIn, user: RequiredUser) -> InvoiceCreateOut:
    """Build a Telegram-hosted invoice link for the user x product.

    Frontend opens this URL via `Telegram.WebApp.openInvoice(url, callback)`
    inside Mini App, or via plain `window.location` in a browser (Telegram
    routes the user through the t.me deeplink).
    """
    product = get_product(payload.product_code)
    if product is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"продукт «{payload.product_code}» не найден"
        )
    try:
        invoice_url = await create_invoice_link(user, payload.product_code)
    except StarsError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return InvoiceCreateOut(
        invoice_url=invoice_url,
        stars_amount=product.stars_amount,
        product_code=product.code,
        product_title=product.title,
    )


@router.get("/stars/payments", response_model=list[PaymentHistoryItem])
async def list_my_payments(user: RequiredUser, session: DbSession) -> list[PaymentHistoryItem]:
    """Logged-in user sees their own payments — receipts, refund status."""
    rows = await session.execute(
        select(StarPayment)
        .where(StarPayment.user_id == user.id)
        .order_by(desc(StarPayment.created_at))
        .limit(50)
    )
    return [
        PaymentHistoryItem(
            id=p.id,
            product_code=p.product_code,
            stars_amount=p.stars_amount,
            status=p.status,
            created_at=p.created_at,
            refunded_at=p.refunded_at,
        )
        for p in rows.scalars().all()
    ]


@router.get("/tiers")
async def list_tiers(_: RequiredUser) -> dict[str, dict[str, object]]:
    """Public catalog of tier limits — used by the pricing section on landing."""
    return {tier: dict(lim) for tier, lim in TIERS.items()}


@router.post("/change-tier", response_model=TierMeOut)
async def change_tier(
    payload: ChangeTierPayload, user: RequiredUser, session: DbSession
) -> TierMeOut:
    """Self-service tier change. SAFE direction only — anyone can DOWNGRADE
    themselves to free; upgrades require payment (Stars or future ЮKassa).

    Closes the security gap from 2026-05-22 audit: previously this endpoint
    let any logged-in user POST `{"tier": "pro"}` and silently become Pro
    without paying. Now upgrades go through app/billing/stars.py only.
    """
    if payload.tier not in TIERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "неизвестный тариф")
    if payload.tier != "free":
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Самовольное повышение тарифа запрещено. Оплати через Telegram Stars: "
            "POST /api/billing/stars/invoice",
        )
    user.tier = "free"
    user.pro_until = None  # explicit cancel — they want off.
    await session.commit()
    await session.refresh(user)
    return TierMeOut(
        user_id=user.id,
        tier=user.tier,
        effective_tier=effective_tier(user),
        trial_active=is_trial_active(user),
        trial_ends_at=user.trial_ends_at,
        trial_days_remaining=trial_days_remaining(user),
        pro_until=user.pro_until,
        limits=dict(limits_for(user)),
    )


# ---------------------------------------------------------------------------
# Оплата картой через Robokassa
#
# Три эндпоинта: увести на оплату, принять уведомление, вернуть пользователя.
# Доступ выдаём ТОЛЬКО по уведомлению на ResultURL — страницу «успех» можно
# открыть руками, доверять ей нельзя.
# ---------------------------------------------------------------------------


@router.get("/pay/{product_code}", include_in_schema=False)
async def start_card_payment(
    product_code: str, user: RequiredUser, session: DbSession
) -> RedirectResponse:
    """Заводит счёт и уводит пользователя на страницу оплаты Robokassa."""
    if not robokassa.is_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Оплата картой временно недоступна. Напиши в поддержку.",
        )
    product = get_product(product_code)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Тариф не найден")

    # Защита от повторной/бессмысленной покупки по прямой ссылке: если тариф уже
    # покрыт (равный/старший или пожизненный), оплату не заводим. Каталог такие
    # продукты и так прячет, но ссылку можно открыть руками.
    if purchase_state(user, product) == "owned":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="У тебя уже есть этот тариф или выше — повторно платить не нужно.",
        )

    payment = CardPayment(
        user_id=user.id,
        provider="robokassa",
        provider_payment_id="",  # проставим номером счёта после flush
        product_code=product.code,
        amount_kopecks=product.rub_amount * 100,
        status="pending",
    )
    session.add(payment)
    # flush, а не commit: нужен выданный последовательностью InvId, но фиксируем
    # запись вместе со ссылкой — иначе при падении останется счёт без адреса.
    await session.flush()
    # inv_id — серверный DEFAULT (nextval) и НЕ первичный ключ, поэтому после
    # INSERT его значение SQLAlchemy сразу не подтягивает. Ленивое чтение
    # атрибута в async-сессии падает в MissingGreenlet (IO вне await) — поэтому
    # подгружаем номер счёта явно, в await-контексте.
    await session.refresh(payment, ["inv_id"])
    payment.provider_payment_id = str(payment.inv_id)

    url = robokassa.build_payment_url(product, payment.inv_id, email=user.email)
    payment.confirmation_url = url
    await session.commit()
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.api_route("/robokassa/result", methods=["GET", "POST"], include_in_schema=False)
async def robokassa_result(request: Request, session: DbSession) -> PlainTextResponse:
    """Уведомление об оплате. Единственное место, где выдаётся доступ.

    Robokassa повторяет запрос, пока не получит ``OK<InvId>``, поэтому обработка
    обязана быть идемпотентной: второй раз по тому же счёту доступ не выдаём,
    но отвечаем успехом, иначе уведомления будут идти вечно.

    Принимаем И GET, И POST: метод отправки Result URL задаётся в настройках
    магазина Robokassa, и по умолчанию там часто стоит GET. Параметры берём из
    query-строки (GET) и из тела формы (POST) — что пришло, то и читаем.
    """
    params: dict[str, str] = {k: str(v) for k, v in request.query_params.items()}
    if request.method == "POST":
        params.update({k: str(v) for k, v in (await request.form()).items()})
    out_sum = params.get("OutSum", "")
    inv_id = params.get("InvId", "")
    signature = params.get("SignatureValue", "")
    shp = {k: v for k, v in params.items() if k.startswith("Shp_")}

    if not robokassa.verify_result(out_sum, inv_id, signature, shp):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="bad signature")

    payment = (
        await session.execute(select(CardPayment).where(CardPayment.inv_id == int(inv_id)))
    ).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown invoice")

    if payment.status == "succeeded":
        return PlainTextResponse(f"OK{inv_id}")  # повторная доставка

    # Сверяем сумму: подпись верна, но клиент мог подменить цену в ссылке.
    if round(float(out_sum) * 100) != payment.amount_kopecks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="amount mismatch")

    product = get_product(payment.product_code)
    if product is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="product gone")

    payment.status = "succeeded"
    payment.paid_at = datetime.now(UTC)
    await grant_product_access(session, payment.user_id, product)
    await session.commit()
    return PlainTextResponse(f"OK{inv_id}")


@router.get("/robokassa/success", include_in_schema=False)
async def robokassa_success() -> RedirectResponse:
    """Куда Robokassa возвращает пользователя после оплаты.

    Доступ здесь НЕ выдаём: адрес открывается вручную. Просто отправляем
    в приложение — к моменту возврата уведомление обычно уже обработано.
    """
    return RedirectResponse(url="/app/today?paid=1", status_code=302)


@router.get("/robokassa/fail", include_in_schema=False)
async def robokassa_fail() -> RedirectResponse:
    """Оплата не прошла или пользователь отменил её."""
    return RedirectResponse(url="/pricing?payment=failed", status_code=302)
