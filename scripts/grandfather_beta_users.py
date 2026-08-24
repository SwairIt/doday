"""Выдаёт Pro навсегда всем, кто зарегистрировался в период беты.

На сайте весь период беты висело обещание: «Ранним юзерам Pro останется
навсегда, когда вернём оплату». Выключая бету и включая продажи, мы обязаны
это обещание выполнить — иначе люди, поверившие баннеру, в один день потеряют
доступ. Скрипт проставляет tier=pro и pro_until=2099 всем, кто зарегался до
момента запуска (по умолчанию — «сейчас»).

Запуск НА СЕРВЕРЕ, один раз, ПЕРЕД выключением беты в .env:

    python3 -m scripts.grandfather_beta_users            # применить
    python3 -m scripts.grandfather_beta_users --dry-run  # только показать, сколько

Идемпотентен: повторный запуск никого не трогает, если Pro уже стоит навсегда.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.auth.models import User
from app.db import get_session_maker

# Момент, до которого регистрация считается «ранней». Все, кто был до этой
# отсечки, застали бету и обещание. Меняется только правкой этой константы.
CUTOFF = datetime.now(UTC)
FOREVER = datetime(2099, 12, 31, tzinfo=UTC)


async def main(dry_run: bool) -> None:
    maker = get_session_maker()
    async with maker() as session:
        users = (
            (await session.execute(select(User).where(User.created_at < CUTOFF))).scalars().all()
        )

        already = sum(1 for u in users if u.pro_until == FOREVER and u.tier != "free")
        to_grant = [u for u in users if not (u.pro_until == FOREVER and u.tier == "pro")]

        print(f"всего ранних пользователей: {len(users)}")
        print(f"уже с пожизненным Pro:      {already}")
        print(f"будет выдано:               {len(to_grant)}")

        if dry_run:
            print("(dry-run: изменения не сохранены)")
            return

        for u in to_grant:
            # Family не понижаем до Pro — оставляем более высокий тариф.
            if u.tier not in ("pro", "family"):
                u.tier = "pro"
            u.pro_until = FOREVER
        await session.commit()
        print(f"готово: {len(to_grant)} пользователям выдан Pro навсегда")


if __name__ == "__main__":
    asyncio.run(main("--dry-run" in sys.argv))
