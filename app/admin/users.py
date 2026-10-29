"""Bounded, server-side search for the owner dashboard."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class UserFilters(BaseModel):
    q: str = Field(default="", max_length=160)
    verified: Literal["all", "yes", "no"] = "all"
    tier: Literal["all", "free", "pro", "family"] = "all"
    sort: Literal["newest", "oldest", "email", "expiry"] = "newest"
    page: int = Field(default=1, ge=1, le=100000)
    per_page: int = Field(default=25, ge=10, le=100)


async def user_page(
    session: AsyncSession, filters: UserFilters
) -> tuple[list[User], int, int, int]:
    stmt = select(User)
    if filters.q.strip():
        stmt = stmt.where(
            func.lower(User.email).contains(filters.q.strip().lower(), autoescape=True)
        )
    if filters.verified != "all":
        stmt = stmt.where(
            User.email_verified_at.is_not(None)
            if filters.verified == "yes"
            else User.email_verified_at.is_(None)
        )
    paid = User.tier.in_(["pro", "team", "family"]) & (User.pro_until > datetime.now(UTC))
    if filters.tier == "free":
        stmt = stmt.where(~func.coalesce(paid, False))
    elif filters.tier == "pro":
        stmt = stmt.where(paid, User.tier.in_(["pro", "team"]))
    elif filters.tier == "family":
        stmt = stmt.where(paid, User.tier == "family")
    total = int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    pages = max(1, (total + filters.per_page - 1) // filters.per_page)
    page = min(filters.page, pages)
    sorts = {
        "newest": User.created_at.desc(),
        "oldest": User.created_at.asc(),
        "email": func.lower(User.email),
        "expiry": User.pro_until.desc().nulls_last(),
    }
    result = await session.execute(
        stmt.order_by(sorts[filters.sort], User.id)
        .offset((page - 1) * filters.per_page)
        .limit(filters.per_page)
    )
    return list(result.scalars()), total, page, pages
