"""Billing service — tier definitions, trial logic, and limit enforcement.

Pricing model (revised 2026-05-07):
- Free:    generous limits (10 projects, 500 tasks, 3 custom filters)
- Pro:     unlimited everything + premium themes + email/TG (when ready) — 199₽/мес
- Family:  Pro for up to 5 accounts + parent dashboard — 299₽/мес
"""

from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.models import Project
from app.tasks.models import Task


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
