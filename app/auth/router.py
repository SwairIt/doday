"""Auth HTTP endpoints — registration, email verification, login, logout."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.auth import antibot
from app.auth.deps import DbSession
from app.auth.email import send_verification_email
from app.auth.rate_limit import client_ip, client_key, hit, reset
from app.auth.schemas import RegisterIn
from app.auth.security import (
    InvalidToken,
    create_email_verification_token,
    verify_email_verification_token,
)
from app.auth.service import (
    EmailAlreadyExists,
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
# Подписанная метка времени отрисовки формы — шаблон берёт её сам, чтобы не
# прокидывать через каждый из шести рендеров register.html.
templates.env.globals["form_token"] = antibot.issue_form_token


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
    website: Annotated[str, Form()] = "",  # honeypot: люди это поле не видят
    captcha_token: Annotated[str, Form(alias="g-recaptcha-response")] = "",  # токен reCAPTCHA
    form_ts: Annotated[str, Form()] = "",  # метка времени отрисовки формы
) -> HTMLResponse | RedirectResponse:
    # Honeypot: бот заполнил скрытое поле — отвечаем как на «успех», но аккаунт
    # НЕ создаём. Так поток бот-регистраций с левыми емейлами обрывается, а бот
    # не понимает, что его отсекли.
    if website.strip():
        return RedirectResponse(url="/auth/verify-pending?signup=1", status_code=303)

    ip = client_ip(request)
    # Было 5 в минуту (7200 в сутки) — этого хватило, чтобы за раз завели
    # 170 аккаунтов. Оставляем короткий всплеск на опечатки в форме, а
    # настоящее ограничение считается по БД ниже.
    if not hit(client_key(ip, "register"), max_calls=3, per_seconds=600):
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Слишком много попыток. Подожди минуту и попробуй снова."},
            status_code=429,
        )

    # Капча (если включена в .env). Серверная проверка токена — виджет на форме
    # даёт smart-token, здесь подтверждаем его у Яндекса. request.state отдаёт
    # шаблону публичный ключ, поэтому при ошибке форма перерисуется с капчей.
    from app.auth.captcha import verify as verify_captcha

    if not await verify_captcha(captcha_token, ip):
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": "Подтверди, что ты не робот (капча)."},
            status_code=400,
        )

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

    # Три проверки против массовой регистрации. Порядок от дешёвых к дорогим:
    # разбор строки, потом счёт по БД.
    try:
        antibot.check_form_timing(form_ts)
        antibot.check_email(payload.email)
        await antibot.check_domain_deliverable(payload.email)
        await antibot.check_signup_rate(session, ip)
    except antibot.SignupRejected as exc:
        _log.info("signup_rejected", code=exc.log_code, ip=ip)
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"error": exc.reason},
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

    # Откуда пришла регистрация — по этим полям считается частота.
    user.signup_ip = ip
    user.signup_subnet = antibot.subnet_of(ip)
    session.add(user)
    await session.commit()
    await antibot.notify_if_spike(session)

    settings = get_settings()
    token = create_email_verification_token(str(user.id))
    verify_url = f"{settings.app_base_url}/auth/verify?token={token}"
    smtp_failed = False
    try:
        await send_verification_email(to=user.email, verification_url=verify_url)
    except Exception as e:
        smtp_failed = True
        # Ни адреса, ни ссылки с токеном: ссылка действительна трое суток,
        # и тот, кто читает логи, подтвердил бы по ней чужую почту.
        _log.warning("verification_email_send_failed", user_id=str(user.id), error=str(e))

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
    ip = client_ip(request)
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
    reset(rl_key)
    request.session.clear()  # drop any pre-login session state (anti-fixation)
    request.session["user_id"] = str(user.id)
    request.session["epoch"] = user.session_epoch
    return RedirectResponse(url="/app/today?welcome=1", status_code=303)


@router.post("/logout", response_model=None)
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
