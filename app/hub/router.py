"""Doday Studio hub — витрина всех продуктов студии.

Живёт на поддомене all.getdoday.ru: основной домен занят продуктом
Doday Tasks, а витрина — вспомогательная страница «что ещё делает автор».
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.auth.deps import CurrentUser, DbSession
from app.auth.models import User

router = APIRouter(tags=["hub"])
_templates = Jinja2Templates(directory="app/templates")


async def _registered_users(session: DbSession) -> int | None:
    """Сколько человек реально зарегистрировано.

    Число на витрине берём из базы, а не пишем руками: любая зашитая цифра
    рано или поздно становится неправдой, а на сайте, который проходит
    модерацию платёжной системы, неправда недопустима. Если база недоступна —
    возвращаем None, и блок со статистикой просто не рисуется.
    """
    try:
        return int((await session.execute(select(func.count(User.id)))).scalar_one())
    except Exception:
        return None


@router.get("/all", response_class=HTMLResponse, include_in_schema=False)
async def hub_index(request: Request, user: CurrentUser, session: DbSession) -> HTMLResponse:
    """Витрина студии.

    Доступна по пути /all и по поддомену all.getdoday.ru (host-роутинг живёт
    в app.main). Залогиненных не редиректим — со витрины удобно ходить между
    продуктами.
    """
    return _templates.TemplateResponse(
        request,
        "hub/index.html",
        {"user": user, "registered_users": await _registered_users(session)},
    )
