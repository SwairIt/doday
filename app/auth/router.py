"""Auth HTTP endpoints — registration, email verify pending screen."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email import send_verification_email
from app.auth.schemas import RegisterIn
from app.auth.security import create_email_verification_token
from app.auth.service import EmailAlreadyExists, register_user
from app.config import get_settings
from app.db import get_session

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/register.html", {"error": None})


@router.post("/register")
async def register_submit(
    request: Request,
    session: DbSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    agree_privacy: Annotated[str | None, Form()] = None,
) -> HTMLResponse | RedirectResponse:
    if agree_privacy != "on":
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Нужно дать согласие на обработку персональных данных."},
            status_code=400,
        )

    try:
        payload = RegisterIn(email=email, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Проверь email и пароль (от 8 символов)."},
            status_code=400,
        )

    try:
        user = await register_user(session, payload)
    except EmailAlreadyExists:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Этот email уже зарегистрирован."},
            status_code=400,
        )

    token = create_email_verification_token(str(user.id))
    verify_url = f"{get_settings().app_base_url}/auth/verify?token={token}"
    await send_verification_email(to=user.email, verification_url=verify_url)

    return RedirectResponse(url="/auth/verify-pending", status_code=303)


@router.get("/verify-pending", response_class=HTMLResponse)
async def verify_pending(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/verify_pending.html", {})
