"""Auth HTTP endpoints — registration, email verification, login, logout."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.auth.deps import DbSession
from app.auth.email import send_verification_email
from app.auth.schemas import RegisterIn
from app.auth.security import (
    InvalidToken,
    create_email_verification_token,
    verify_email_verification_token,
)
from app.auth.service import (
    EmailAlreadyExists,
    EmailNotVerified,
    InvalidCredentials,
    TokenInvalid,
    authenticate,
    mark_email_verified,
    register_user,
)
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


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


@router.get("/verify")
async def verify(token: str, session: DbSession) -> Response:
    try:
        user_id = verify_email_verification_token(token)
        await mark_email_verified(session, user_id)
    except (InvalidToken, TokenInvalid):
        return HTMLResponse(
            "Ссылка недействительна или истекла. Запроси новое письмо.",
            status_code=400,
        )
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    session: DbSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    try:
        user = await authenticate(session, email, password)
    except InvalidCredentials:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Неверный email или пароль."},
            status_code=401,
        )
    except EmailNotVerified:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Сначала подтверди email — мы отправили тебе письмо."},
            status_code=403,
        )
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
