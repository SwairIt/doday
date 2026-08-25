"""Billing service — tier definitions, trial logic, and limit enforcement.

Pricing model (revised 2026-05-07):
- Free:    generous limits (10 projects, 500 tasks, 3 custom filters)
- Pro:     unlimited everything + premium themes + email/TG (when ready) — 199₽/мес
- Family:  Pro for up to 5 accounts + parent dashboard — 299₽/мес
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import Entitlement
from app.billing.products import Product
from app.projects.models import Project
from app.tasks.models import Task

logger = logging.getLogger(__name__)


class TierLimits(TypedDict):
    max_active_projects: int | None  # None = unlimited
    max_active_tasks: int | None
    max_bulk_paste_lines: int
    trash_retention_days: int
    kanban_view: bool
    icalendar_export: bool
    pomodoro: bool
    activity_feed: bool
    daily_goal: bool
    label_count: int | None
    bulk_actions: bool
    premium_themes: bool  # forest, minimal — Pro+
    email_digest: bool  # Pro+ (when feature ships)
    tg_bot: bool  # Pro+ (when feature ships)
    family_seats: int  # only Family has >1


TIERS: dict[str, TierLimits] = {
    "free": {
        "max_active_projects": 10,
        "max_active_tasks": 500,
        "max_bulk_paste_lines": 50,
        "trash_retention_days": 14,
        "kanban_view": True,
        "icalendar_export": True,
        "pomodoro": True,
        "activity_feed": True,
        "daily_goal": True,
        "label_count": None,  # uncapped
        "bulk_actions": True,
        "premium_themes": False,
        "email_digest": False,
        "tg_bot": False,
        "family_seats": 1,
    },
    "pro": {
        "max_active_projects": None,
        "max_active_tasks": None,
        "max_bulk_paste_lines": 200,
        "trash_retention_days": 30,
        "kanban_view": True,
        "icalendar_export": True,
        "pomodoro": True,
        "activity_feed": True,
        "daily_goal": True,
        "label_count": None,
        "bulk_actions": True,
        "premium_themes": True,
        "email_digest": True,
        "tg_bot": True,
        "family_seats": 1,
    },
    "family": {
        "max_active_projects": None,
        "max_active_tasks": None,
        "max_bulk_paste_lines": 200,
        "trash_retention_days": 30,
        "kanban_view": True,
        "icalendar_export": True,
        "pomodoro": True,
        "activity_feed": True,
        "daily_goal": True,
        "label_count": None,
        "bulk_actions": True,
        "premium_themes": True,
        "email_digest": True,
        "tg_bot": True,
        "family_seats": 5,
    },
    # legacy alias — was used in tests and can stay as a synonym for pro.
    "team": {
        "max_active_projects": None,
        "max_active_tasks": None,
        "max_bulk_paste_lines": 200,
        "trash_retention_days": 30,
        "kanban_view": True,
        "icalendar_export": True,
        "pomodoro": True,
        "activity_feed": True,
        "daily_goal": True,
        "label_count": None,
        "bulk_actions": True,
        "premium_themes": True,
        "email_digest": True,
        "tg_bot": True,
        "family_seats": 1,
    },
}


def is_trial_active(user: User) -> bool:
    if user.trial_ends_at is None:
        return False
    return user.trial_ends_at > datetime.now(UTC)


def effective_tier(user: User) -> str:
    """Resolve what the user can use, considering trial + paid + beta override.

    Order of precedence:
    1. Beta override (settings.beta_free_for_all) → everyone gets pro.
    2. Paid subscription via Stars → user.tier ('pro'|'family') while
       user.pro_until is in the future.
    3. Trial period → 'pro' if trial_ends_at is in the future.
    4. Otherwise 'free'.

    Why we don't use user.tier directly: a user who paid for Pro 1 month and
    didn't renew should automatically lapse back to free without an admin
    flipping the column. Storing the expiry separately gives us a deterministic
    answer on every request without needing a cron job.
    """
    from app.config import get_settings

    if get_settings().beta_free_for_all:
        return "pro"
    # Paid subscription — user.tier set to pro/family on purchase, pro_until
    # tracks expiry. Once pro_until lapses, fall through to trial/free.
    now = datetime.now(UTC)
    if user.tier in ("pro", "team", "family") and user.pro_until and user.pro_until > now:
        return user.tier
    if is_trial_active(user):
        return "pro"
    return "free"


def limits_for(user: User) -> TierLimits:
    return TIERS[effective_tier(user)]


def trial_days_remaining(user: User) -> int:
    if user.trial_ends_at is None:
        return 0
    delta = user.trial_ends_at - datetime.now(UTC)
    return max(0, delta.days + (1 if delta.seconds else 0))


async def can_create_project(session: AsyncSession, user: User) -> tuple[bool, str | None]:
    """Returns (allowed, reason_if_blocked)."""
    limits = limits_for(user)
    cap = limits["max_active_projects"]
    if cap is None:
        return True, None
    row = await session.execute(
        select(func.count())
        .select_from(Project)
        .where(
            Project.user_id == user.id,
            Project.is_archived.is_(False),
            Project.is_inbox.is_(False),
        )
    )
    current = row.scalar_one()
    if current >= cap:
        return False, (
            f"Достигнут лимит Free-тарифа: {cap} активных проектов. Pro снимает лимит за 199₽/мес."
        )
    return True, None


async def can_create_task(session: AsyncSession, user: User) -> tuple[bool, str | None]:
    """Returns (allowed, reason_if_blocked). Counts non-completed, non-deleted tasks."""
    limits = limits_for(user)
    cap = limits["max_active_tasks"]
    if cap is None:
        return True, None
    row = await session.execute(
        select(func.count())
        .select_from(Task)
        .where(
            Task.user_id == user.id,
            Task.is_completed.is_(False),
            Task.deleted_at.is_(None),
        )
    )
    current = row.scalar_one()
    if current >= cap:
        return False, (
            f"Достигнут лимит Free-тарифа: {cap} активных задач. Pro снимает лимит за 199₽/мес."
        )
    return True, None


def can_use_premium_theme(user: User) -> bool:
    """Forest, Minimal accents are Pro/Family only."""
    return limits_for(user)["premium_themes"]


def can_paste_n_lines(user: User, n: int) -> bool:
    return n <= limits_for(user)["max_bulk_paste_lines"]


def has_pro_features(user: User) -> bool:
    """True if user can use Pro/Family-only features (incl. trial period)."""
    return effective_tier(user) in ("pro", "team", "family")


# ---------------------------------------------------------------------------
# Что пользователю осмысленно покупать при его текущем тарифе.
#
# Нельзя показывать «Купить Pro» тому, у кого уже Pro, и предлагать помесячную
# тому, у кого годовая. Логику держим тут, а не в шаблоне: её используют и
# каталог `/api/billing/products`, и защита эндпоинта оплаты — иначе фронт и
# бэкенд разойдутся, а расхождение в биллинге стоит денег.
# ---------------------------------------------------------------------------

# Ранг тарифа: выше ранг — больше возможностей. team — legacy-синоним pro.
_TIER_RANK: dict[str, int] = {"free": 0, "team": 1, "pro": 1, "family": 2}


def _has_lifetime(user: User) -> bool:
    """Пожизненная подписка: pro_until выставлен в далёкое будущее (год 2099)."""
    return user.pro_until is not None and user.pro_until.year >= 2099


def paid_tier(user: User) -> str:
    """Реально ОПЛАЧЕННЫЙ тариф — без beta-оверрайда и без trial.

    Отличается от :func:`effective_tier`: тот показывает, что пользователю
    доступно (включая бету и триал), а этот — что он реально купил. Для решения
    «предлагать ли покупку» нужен именно оплаченный: триальному и бета-юзеру
    покупку показывать НАДО, хотя фичи у них уже открыты.
    """
    now = datetime.now(UTC)
    if user.tier in ("pro", "team", "family") and user.pro_until and user.pro_until > now:
        return user.tier
    return "free"


def purchase_state(user: User, product: Product) -> str:
    """Как показывать тарифный продукт данному пользователю.

    Возвращает:
    - ``"buy"``    — честный апгрейд, которого у пользователя ещё нет
      (Free→Pro, Pro→Family, срочный→навсегда);
    - ``"extend"`` — тот же тариф, срочная подписка: покупка продлевает срок;
    - ``"owned"``  — уже покрыто (равный/старший тариф или уже пожизненно);
      предлагать бессмысленно — прячем в каталоге и запрещаем оплату.

    Считаем от ОПЛАЧЕННОГО тарифа (:func:`paid_tier`), а не effective: иначе в
    бете, где всем показывается pro, никто не смог бы купить founder-навсегда.
    У вертикалей (ПДД, ``grants_tier is None``) своя логика — тут всегда ``buy``.
    """
    if product.grants_tier is None:
        return "buy"
    user_rank = _TIER_RANK.get(paid_tier(user), 0)
    prod_rank = _TIER_RANK.get(product.grants_tier, 0)
    if user_rank < prod_rank:
        return "buy"  # апгрейд на тариф выше
    if user_rank > prod_rank:
        return "owned"  # у пользователя тариф выше — этот не нужен
    # Равный тариф и он реально оплачен:
    if _has_lifetime(user):
        return "owned"  # уже навсегда на этом тарифе — покупка ничего не даст
    if product.duration_months is None:
        return "buy"  # срочный → навсегда: осмысленный апгрейд
    return "extend"  # продление того же тарифа


async def has_entitlement(session: AsyncSession, user: User, feature: str) -> bool:
    """True if the beta override is on, or the user holds a non-expired grant.

    Per-feature entitlements (e.g. ``pdd_pro``) are independent of the global
    ``user.tier`` — a vertical can be sold and gated on its own without touching
    Doday Tasks/Lessio Pro. Used by ``app/pdd/service.py``; generic so future
    verticals reuse it.
    """
    from app.billing.models import Entitlement
    from app.config import get_settings

    if get_settings().beta_free_for_all:
        return True
    ent = (
        await session.execute(
            select(Entitlement).where(
                Entitlement.user_id == user.id, Entitlement.feature == feature
            )
        )
    ).scalar_one_or_none()
    if ent is None:
        return False
    return ent.expires_at is None or ent.expires_at > datetime.now(UTC)


def require_pro(user: User, feature_name: str) -> None:
    """Raise 402 Payment Required if the user is not on a Pro-tier plan.

    402 (a real but rarely-used HTTP status) clearly distinguishes upgrade-needed
    from generic 403; frontend treats it as «open upgrade modal».
    """
    from fastapi import HTTPException, status

    if not has_pro_features(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"{feature_name} — фича Pro-тарифа. Обнови подписку чтобы использовать.",
        )


# ---------------------------------------------------------------------------
# Выдача купленного доступа — общая для всех платёжных провайдеров.
#
# Раньше эта логика жила внутри обработчика Telegram Stars. С появлением ЮKassa
# её пришлось вынести: иначе два платёжных пути начали бы расходиться при первом
# же изменении тарифов, а расхождение в биллинге — это выданный или потерянный
# доступ за деньги.
# ---------------------------------------------------------------------------


async def grant_product_access(session: AsyncSession, user_id: UUID, product: Product) -> None:
    """Открывает пользователю то, что он купил: тариф и/или доступ к вертикали.

    Продлевает от максимума из «сейчас» и текущего срока — при досрочном
    продлении остаток дней не сгорает. Пожизненная покупка не понижается до
    срочной при повторной оплате.

    :param session: активная сессия БД (коммит делает вызывающий код)
    :param user_id: кому выдаём
    :param product: позиция каталога из app.billing.products
    """
    user = await session.get(User, user_id)
    if user is None:
        logger.error("оплаченный пользователь не найден: %s", user_id)
        return

    # Тарифные продукты (Doday Tasks, Lessio) двигают глобальный тариф.
    # Продукты-вертикали (ПДД) тариф не трогают — у них grants_tier is None.
    if product.grants_tier is not None:
        user.tier = product.grants_tier
        if product.duration_months is None:
            # Пожизненно — ставим 2099 год, а не None: None означает «Pro
            # никогда не было» в остальном коде.
            user.pro_until = datetime(2099, 12, 31, tzinfo=UTC)
        else:
            now = datetime.now(UTC)
            base = user.pro_until if (user.pro_until and user.pro_until > now) else now
            user.pro_until = base + timedelta(days=30 * product.duration_months)

    if product.grants_entitlement is not None:
        await grant_entitlement(session, user_id, product)


async def grant_entitlement(session: AsyncSession, user_id: UUID, product: Product) -> None:
    """Заводит или продлевает доступ к отдельной вертикали (например ``pdd_pro``).

    Идемпотентна при повторном продлении: пожизненный доступ никогда не
    понижается до срочного, срочный продлевается от максимума из «сейчас» и
    текущего срока.
    """
    feature = product.grants_entitlement
    if feature is None:  # вызывающий гарантирует непустое; сужаем для типизации
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
        new_expiry: datetime | None = None  # пожизненно
    else:
        now = datetime.now(UTC)
        base = ent.expires_at if (ent and ent.expires_at and ent.expires_at > now) else now
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

    if ent.expires_at is None:
        return  # пожизненный доступ не понижаем
    ent.expires_at = new_expiry
    ent.source_code = product.code
