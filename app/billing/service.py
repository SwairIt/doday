"""Billing service — tier definitions, trial logic, and limit enforcement."""

from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.projects.models import Project


class TierLimits(TypedDict):
    max_active_projects: int | None  # None = unlimited
    custom_filters: bool
    user_templates: bool
    kanban_view: bool
    icalendar_export: bool
    pomodoro: bool
    activity_feed: bool
    daily_goal: bool
    label_count: int | None
    bulk_actions: bool


TIERS: dict[str, TierLimits] = {
    "free": {
        "max_active_projects": 5,
        "custom_filters": False,
        "user_templates": False,
        "kanban_view": False,
        "icalendar_export": False,
        "pomodoro": True,
        "activity_feed": False,
        "daily_goal": True,
        "label_count": 5,
        "bulk_actions": False,
    },
    "pro": {
        "max_active_projects": None,
        "custom_filters": True,
        "user_templates": True,
        "kanban_view": True,
        "icalendar_export": True,
        "pomodoro": True,
        "activity_feed": True,
        "daily_goal": True,
        "label_count": None,
        "bulk_actions": True,
    },
    "team": {
        "max_active_projects": None,
        "custom_filters": True,
        "user_templates": True,
        "kanban_view": True,
        "icalendar_export": True,
        "pomodoro": True,
        "activity_feed": True,
        "daily_goal": True,
        "label_count": None,
        "bulk_actions": True,
    },
}


def is_trial_active(user: User) -> bool:
    if user.trial_ends_at is None:
        return False
    return user.trial_ends_at > datetime.now(UTC)


def effective_tier(user: User) -> str:
    """During trial, free users get pro features; paid tiers stay as-is."""
    if user.tier in ("pro", "team"):
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
        return False, f"Лимит тарифа Free: {cap} проектов. Перейди на Pro для безлимита."
    return True, None
