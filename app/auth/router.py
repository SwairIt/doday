"""Auth HTTP endpoints — registration, email verification, login, logout."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.auth.deps import DbSession
from app.auth.email import send_verification_email
from app.auth.rate_limit import client_key, hit, reset
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

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/register.html", {"error": None})


@router.post("/register", response_model=None)
async def register_submit(
    request: Request,
    session: DbSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    agree_privacy: Annotated[str | None, Form()] = None,
    audience: Annotated[str | None, Form()] = None,
) -> HTMLResponse | RedirectResponse:
    ip = request.client.host if request.client else None
    if not hit(client_key(ip, "register"), max_calls=5, per_seconds=60):
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Слишком много попыток. Подожди минуту и попробуй снова."},
            status_code=429,
        )

    if agree_privacy != "on":
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Нужно дать согласие на обработку персональных данных."},
            status_code=400,
        )

    aud = audience if audience in ("school", "company", "personal") else None
    try:
        payload = RegisterIn(email=email, password=password, audience=aud)  # type: ignore[arg-type]
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

    settings = get_settings()
    token = create_email_verification_token(str(user.id))
    verify_url = f"{settings.app_base_url}/auth/verify?token={token}"
    smtp_failed = False
    try:
        await send_verification_email(to=user.email, verification_url=verify_url)
    except Exception as e:
        smtp_failed = True
        _log.warning(
            "verification_email_send_failed",
            email=user.email,
            error=str(e),
            verify_url=verify_url,
        )

    # In dev (any non-prod env) auto-verify and render the success page with
    # the verify URL on screen — handy when SMTP either fails or only goes to
    # a local debug server (aiosmtpd) that doesn't actually deliver mail.
    if settings.app_env != "prod":
        from app.auth.service import mark_email_verified as _verify

        await _verify(session, str(user.id))
        return templates.TemplateResponse(
            request,
            "auth/verify_pending.html",
            {"dev_skipped_email": True, "dev_verify_url": verify_url, "fire_signup_goal": True},
        )

    if smtp_failed:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {
                "error": (
                    "Не удалось отправить письмо подтверждения. "
                    "Аккаунт создан — попробуй войти или повторно запросить письмо."
                )
            },
            status_code=503,
        )

    return RedirectResponse(url="/auth/verify-pending?signup=1", status_code=303)


@router.get("/verify-pending", response_class=HTMLResponse)
async def verify_pending(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/verify_pending.html", {})


@router.get("/verify", response_model=None)
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


@router.post("/login", response_model=None)
async def login_submit(
    request: Request,
    session: DbSession,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    ip = request.client.host if request.client else None
    rl_key = client_key(ip, f"login:{email.lower()}")
    if not hit(rl_key, max_calls=10, per_seconds=60):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Слишком много попыток. Подожди минуту."},
            status_code=429,
        )

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
    reset(rl_key)
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/app/today?welcome=1", status_code=303)


@router.post("/logout", response_model=None)
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
