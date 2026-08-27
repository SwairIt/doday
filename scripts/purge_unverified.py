"""Разбор ботовских регистраций: показать и, по команде, удалить.

Поводом послужили 170 аккаунтов, заведённых за пару недель. Скрипт находит
записи, которые выглядят брошенными ботами, и по умолчанию НИЧЕГО не удаляет —
только показывает список. Удаление включается флагом --apply.

    uv run python scripts/purge_unverified.py                 # посмотреть
    uv run python scripts/purge_unverified.py --days 14       # старше 14 дней
    uv run python scripts/purge_unverified.py --apply         # удалить

Кандидат на удаление — аккаунт, у которого разом:
  * почта не подтверждена,
  * нет ни одной задачи (даже удалённой),
  * нет привязки к Telegram и профиля репетитора,
  * не администратор,
  * создан больше N дней назад (по умолчанию 7).

Такой набор условий выбран нарочно строгим: живой человек, зашедший
попробовать, обычно оставляет хотя бы одну задачу, а неподтверждённая почта
сама по себе поводом не является — письмо могло не дойти.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select

# Модели связаны между собой строковыми ссылками, поэтому SQLAlchemy не
# соберёт маппинги, пока не импортированы все модули с таблицами.
for _module in (
    "admin", "ai", "auth", "billing", "gamification", "habits", "labels", "links",
    "lessio", "mood", "notifications", "pdd", "pomodoro", "projects", "qa",
    "reminders", "school", "sections", "tasks", "telegram", "time_tracking",
    "user_templates",
):  # fmt: skip
    importlib.import_module(f"app.{_module}.models")

from app.auth.models import User  # noqa: E402
from app.db import get_session_maker  # noqa: E402
from app.lessio.models import LessioTutorProfile  # noqa: E402
from app.tasks.models import Task  # noqa: E402
from app.telegram.models import TelegramLink  # noqa: E402


async def _candidates(days: int) -> list[User]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    session_maker = get_session_maker()
    async with session_maker() as session:
        rows = await session.execute(
            select(User)
            .where(
                User.email_verified_at.is_(None),
                User.created_at < cutoff,
                User.is_admin.is_(False),
                ~select(Task.id).where(Task.user_id == User.id).exists(),
                ~select(TelegramLink.id).where(TelegramLink.user_id == User.id).exists(),
                ~select(LessioTutorProfile.id)
                .where(LessioTutorProfile.user_id == User.id)
                .exists(),
            )
            .order_by(User.created_at)
        )
        return list(rows.scalars().all())


async def _total() -> int:
    session_maker = get_session_maker()
    async with session_maker() as session:
        return int(await session.scalar(select(func.count()).select_from(User)) or 0)


async def _delete(ids: list[object]) -> int:
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(delete(User).where(User.id.in_(ids)))
        await session.commit()
        return int(getattr(result, "rowcount", 0) or 0)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="сколько дней аккаунт должен прожить")
    ap.add_argument("--apply", action="store_true", help="удалить найденное")
    ap.add_argument("--limit", type=int, default=50, help="сколько строк показать")
    args = ap.parse_args()

    users = await _candidates(args.days)
    total = await _total()
    print(f"Всего аккаунтов: {total}")
    print(
        f"Кандидатов на удаление (старше {args.days} дн., без задач и подтверждения): {len(users)}"
    )
    if not users:
        return 0

    for u in users[: args.limit]:
        when = u.created_at.strftime("%Y-%m-%d %H:%M")
        print(f"  {when}  {u.email:<45} ip={u.signup_ip or '—'}")
    if len(users) > args.limit:
        print(f"  … и ещё {len(users) - args.limit}")

    by_domain: dict[str, int] = {}
    for u in users:
        domain = u.email.rpartition("@")[2].lower()
        by_domain[domain] = by_domain.get(domain, 0) + 1
    print("\nПо доменам:")
    for domain, count in sorted(by_domain.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {count:>4}  {domain}")

    if not args.apply:
        print("\nНичего не удалено. Чтобы удалить — тот же вызов с --apply.")
        return 0

    removed = await _delete([u.id for u in users])
    print(f"\nУдалено аккаунтов: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
