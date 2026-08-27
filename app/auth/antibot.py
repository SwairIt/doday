"""Защита регистрации от массовой автоматической записи.

Поводом послужили 170 ботов, зарегистрировавшихся за короткий срок. Разбор
показал три слабых места, которые здесь и закрываются:

1. Лимит стоял 5 регистраций в минуту с одного адреса — это 7200 в сутки.
2. Лимит жил в памяти процесса, а деплой перезапускает сервис на каждый пуш:
   счётчик обнулялся вместе с ним.
3. Боты меняют адрес в пределах одной подсети, поэтому считать только по
   точному IP бесполезно.

Ни одна из проверок не полагается на JavaScript: бот его просто не исполняет,
а честный браузер проходит их незаметно.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from time import monotonic

import anyio
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import get_settings

# Сколько аккаунтов можно завести с одного адреса и с одной подсети за час.
# Запас нарочно большой: наша аудитория сидит за школьным NAT и за CGNAT
# мобильных операторов, где сотня человек делит один адрес. Урок информатики,
# на котором класс регистрируется разом, не должен упереться в лимит.
MAX_PER_IP_HOUR = 5
MAX_PER_SUBNET_HOUR = 30

# Форма, отправленная быстрее этого, заполнена не руками.
MIN_FORM_SECONDS = 2.0

# Верхняя граница — защита от подделки метки времени «из будущего» и от
# случая, когда вкладку открыли вчера и забыли.
MAX_FORM_SECONDS = 60 * 60 * 6


_log = structlog.get_logger(__name__)


class SignupRejected(Exception):
    """Регистрацию отклонили. reason — что писать пользователю."""

    def __init__(self, reason: str, *, log_code: str) -> None:
        super().__init__(log_code)
        self.reason = reason
        self.log_code = log_code


# ── одноразовая почта ─────────────────────────────────────────────────────

# Домены сервисов «почта на 10 минут». Список короткий и покрывает самые
# ходовые: полный перечень бесполезен — их тысячи и они появляются каждый
# день. Задача не закрыть все, а сделать массовую регистрацию неудобной.
_DISPOSABLE_DOMAINS = frozenset(
    {
        "10minutemail.com",
        "temp-mail.org",
        "tempmail.com",
        "guerrillamail.com",
        "guerrillamail.info",
        "mailinator.com",
        "yopmail.com",
        "throwawaymail.com",
        "getnada.com",
        "dropmail.me",
        "maildrop.cc",
        "trashmail.com",
        "sharklasers.com",
        "grr.la",
        "spam4.me",
        "mohmal.com",
        "temp-mail.io",
        "tempmailo.com",
        "emailondeck.com",
        "fakemail.net",
        "mailnesia.com",
        "tempr.email",
        "discard.email",
        "vmani.com",
        "mailcatch.com",
        "inboxbear.com",
        "moakt.com",
        "tmpmail.org",
        "1secmail.com",
        "1secmail.org",
        "mail.tm",
        "internxt.com",
    }
)


def is_disposable_email(email: str) -> bool:
    """Похоже ли на одноразовый ящик."""
    _, _, domain = email.lower().strip().rpartition("@")
    if not domain:
        return False
    if domain in _DISPOSABLE_DOMAINS:
        return True
    # Поддомены вида mail.temp-mail.org.
    return any(domain.endswith("." + d) for d in _DISPOSABLE_DOMAINS)


# ── подозрительный адрес ──────────────────────────────────────────────────

# Ботоводы генерируют ящики пачками. Единственный признак, на который можно
# опереться без ложных срабатываний, — локальная часть из одних согласных:
# «qwrtpsdfgh». Правило «много цифр подряд» я сознательно не применяю: у нас
# полно живых людей с телефоном вместо имени ящика (79161234567@mail.ru).
_NO_VOWELS = re.compile(r"^[bcdfghjklmnpqrstvwxz]{10,}$", re.IGNORECASE)


def looks_generated(email: str) -> bool:
    """Локальная часть похожа на сгенерированную машиной."""
    local = email.lower().split("@")[0]
    letters_only = re.sub(r"[^a-z]", "", local)
    return bool(_NO_VOWELS.match(letters_only))


# ── ограничение частоты по адресу и подсети ───────────────────────────────


def subnet_of(ip: str | None) -> str | None:
    """Первые три октета IPv4 — «дом» адреса.

    Смена последнего октета ничего не стоит, поэтому считать только точный
    адрес бессмысленно. Для IPv6 берём первые четыре группы.
    """
    if not ip:
        return None
    if ":" in ip:
        return ":".join(ip.split(":")[:4])
    parts = ip.split(".")
    return ".".join(parts[:3]) if len(parts) == 4 else None


async def check_signup_rate(session: AsyncSession, ip: str | None) -> None:
    """Не слишком ли много аккаунтов уже завели с этого адреса за час.

    Считаем по таблице пользователей, а не по счётчику в памяти: перезапуск
    сервиса при деплое не должен обнулять защиту.
    """
    if not ip:
        return
    since = datetime.now(UTC) - timedelta(hours=1)

    from_ip = await session.scalar(
        select(func.count()).select_from(User).where(User.signup_ip == ip, User.created_at >= since)
    )
    if (from_ip or 0) >= MAX_PER_IP_HOUR:
        raise SignupRejected(
            "С этого адреса уже создано несколько аккаунтов. Попробуй позже.",
            log_code="ip_limit",
        )

    subnet = subnet_of(ip)
    if subnet:
        from_subnet = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.signup_subnet == subnet, User.created_at >= since)
        )
        if (from_subnet or 0) >= MAX_PER_SUBNET_HOUR:
            raise SignupRejected(
                "Слишком много регистраций из твоей сети. Попробуй позже.",
                log_code="subnet_limit",
            )


# ── время заполнения формы ────────────────────────────────────────────────


def issue_form_token() -> str:
    """Метка времени отрисовки формы с подписью.

    Без подписи метка бесполезна: бот подставит «пять секунд назад» и пройдёт
    проверку всегда. Подписываем тем же ключом приложения — подделать нельзя,
    хранить ничего не нужно.
    """
    ts = f"{datetime.now(UTC).timestamp():.0f}"
    return f"{ts}.{_sign(ts)}"


def _sign(ts: str) -> str:
    secret = get_settings().app_secret_key.encode()
    return hmac.new(secret, f"register:{ts}".encode(), hashlib.sha256).hexdigest()[:32]


def check_form_timing(token: str | None) -> None:
    """Форму, отправленную мгновенно, заполнял не человек.

    В форму кладём подписанную метку времени отрисовки. Бот, который постит
    напрямую по списку URL, либо не пришлёт её вовсе, либо пришлёт мусор —
    и то и другое отсекаем.
    """
    stale = "Форма устарела, обнови страницу."
    if not token or "." not in token:
        raise SignupRejected(stale, log_code="no_timestamp")

    ts, _, signature = token.partition(".")
    if not hmac.compare_digest(signature, _sign(ts)):
        raise SignupRejected(stale, log_code="bad_signature")

    try:
        started = float(ts)
    except ValueError as exc:
        raise SignupRejected(stale, log_code="bad_timestamp") from exc

    elapsed = datetime.now(UTC).timestamp() - started
    if elapsed < MIN_FORM_SECONDS:
        raise SignupRejected("Слишком быстро — заполни форму ещё раз.", log_code="too_fast")
    if elapsed > MAX_FORM_SECONDS:
        raise SignupRejected(stale, log_code="expired")


def check_email(email: str) -> None:
    """Отсеять одноразовые и явно сгенерированные ящики."""
    if is_disposable_email(email):
        raise SignupRejected(
            "Временную почту использовать нельзя — укажи постоянный ящик.",
            log_code="disposable",
        )
    if looks_generated(email):
        raise SignupRejected(
            "Этот адрес выглядит сгенерированным. Укажи свою обычную почту.",
            log_code="generated",
        )


# ── существует ли домен вообще ────────────────────────────────────────────

# Разбор наших ботов показал: почти все адреса были не с temp-mail, а с
# несуществующих доменов — sdffsd.sdd, flsdfmsodf.ro, prweorwef.com. У таких
# доменов нет ни MX, ни A-записи, то есть письмо туда уйти не может в
# принципе. Одна DNS-проверка отсекает их полностью.


def _probe_domain(domain: str) -> bool:
    """Есть ли у домена почтовые записи (MX или хотя бы A)."""
    from email_validator import EmailUndeliverableError, validate_email

    try:
        validate_email(f"probe@{domain}", check_deliverability=True, timeout=3)
    except EmailUndeliverableError:
        return False
    except Exception:
        # Таймаут, сбой резолвера, что угодно ещё — пропускаем. Отказать
        # живому человеку из-за нашей же сетевой проблемы хуже, чем пропустить
        # бота: его поймают остальные проверки.
        return True
    return True


# Кэш: за всплеск регистраций с одного домена ходим в DNS один раз.
_domain_has_mail = lru_cache(maxsize=4096)(_probe_domain)


async def check_domain_deliverable(email: str) -> None:
    """Отсеять адреса на несуществующих доменах.

    Резолвер синхронный, поэтому уводим его в поток: регистрация — не тот
    путь, где можно заблокировать весь event loop на секунду.
    """
    domain = email.rpartition("@")[2].lower()
    if not domain:
        return
    with anyio.move_on_after(5):
        if not await anyio.to_thread.run_sync(_domain_has_mail, domain):
            raise SignupRejected(
                "Домен этой почты не существует — проверь адрес.",
                log_code="no_mx",
            )


# ── сигнализация ──────────────────────────────────────────────────────────

# Обычный фон регистраций — единицы в час. Столько за час это уже волна.
SPIKE_PER_HOUR = 20

# Чтобы во время волны не отправить владельцу сотню писем подряд.
_ALERT_COOLDOWN_SECONDS = 3600.0
_last_alert_at = 0.0


async def notify_if_spike(session: AsyncSession) -> None:
    """Написать владельцу, если регистраций за час стало подозрительно много.

    Прошлую волну в 170 аккаунтов заметили постфактум, разбирая базу вручную.
    Best-effort: любая ошибка здесь не должна ломать регистрацию.
    """
    global _last_alert_at

    now = monotonic()
    if now - _last_alert_at < _ALERT_COOLDOWN_SECONDS:
        return

    since = datetime.now(UTC) - timedelta(hours=1)
    count = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= since)
    )
    if (count or 0) < SPIKE_PER_HOUR:
        return

    _last_alert_at = now
    settings = get_settings()
    to = settings.root_admin_email
    if not to:
        return
    try:
        from app.auth.email import send_signup_spike_alert

        await send_signup_spike_alert(to=to, count=count or 0)
    except Exception:
        _log.warning("signup_spike_alert_failed", count=count)
