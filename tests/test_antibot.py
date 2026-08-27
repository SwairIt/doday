"""Защита регистрации от массовой автоматической записи.

Поводом послужили 170 ботов, заведённых за короткий срок.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import antibot
from app.auth.models import User
from tests.conftest import signup_form_token

_form_ts = signup_form_token


# ── одноразовая почта ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "email",
    [
        "bot@mailinator.com",
        "x@10minutemail.com",
        "a@temp-mail.org",
        "b@guerrillamail.com",
        "c@mail.temp-mail.org",  # поддомен
        "D@YOPMAIL.COM",  # регистр не важен
    ],
)
def test_disposable_emails_detected(email: str) -> None:
    assert antibot.is_disposable_email(email) is True


@pytest.mark.parametrize("email", ["vasya@gmail.com", "petya@yandex.ru", "ivan@mail.ru"])
def test_normal_emails_pass(email: str) -> None:
    assert antibot.is_disposable_email(email) is False


# ── сгенерированные адреса ────────────────────────────────────────────────


def test_generated_looking_emails() -> None:
    assert antibot.looks_generated("qwrtpsdfgh@gmail.com") is True


def test_phone_as_local_part_is_not_flagged() -> None:
    """Телефон вместо имени ящика — обычное дело, это живые люди."""
    assert antibot.looks_generated("79161234567@mail.ru") is False


def test_human_emails_are_not_flagged() -> None:
    """Живые адреса не должны попадать под подозрение."""
    for email in ("ivan.petrov@gmail.com", "masha2010@mail.ru", "a.b.smirnov@yandex.ru"):
        assert antibot.looks_generated(email) is False, email


# ── подсеть ───────────────────────────────────────────────────────────────


def test_subnet_of_ipv4() -> None:
    assert antibot.subnet_of("192.168.33.7") == "192.168.33"
    assert antibot.subnet_of("192.168.33.250") == "192.168.33"


def test_subnet_of_ipv6_and_empty() -> None:
    assert antibot.subnet_of("2001:0db8:85a3:0000:0000:8a2e:0370:7334") == "2001:0db8:85a3:0000"
    assert antibot.subnet_of(None) is None
    assert antibot.subnet_of("мусор") is None


# ── время заполнения формы ────────────────────────────────────────────────


def test_instant_submit_rejected() -> None:
    with pytest.raises(antibot.SignupRejected) as exc:
        antibot.check_form_timing(antibot.issue_form_token())
    assert exc.value.log_code == "too_fast"


def test_missing_or_broken_timestamp_rejected() -> None:
    with pytest.raises(antibot.SignupRejected):
        antibot.check_form_timing(None)
    with pytest.raises(antibot.SignupRejected):
        antibot.check_form_timing("не число")


def test_forged_timestamp_rejected() -> None:
    """Главное свойство: метку нельзя сочинить самому.

    Без подписи бот просто подставил бы «пять секунд назад» и проходил всегда.
    """
    ts = f"{datetime.now(UTC).timestamp() - 5:.0f}"
    for forged in (ts, f"{ts}.", f"{ts}.deadbeef", f"{ts}.{'0' * 32}"):
        with pytest.raises(antibot.SignupRejected) as exc:
            antibot.check_form_timing(forged)
        assert exc.value.log_code in ("no_timestamp", "bad_signature")


def test_signature_is_bound_to_its_timestamp() -> None:
    """Подпись от свежей метки не подходит к старой — иначе её можно было бы
    один раз получить и переиспользовать вечно."""
    fresh = antibot.issue_form_token()
    signature = fresh.split(".")[1]
    old_ts = f"{datetime.now(UTC).timestamp() - 100:.0f}"
    with pytest.raises(antibot.SignupRejected) as exc:
        antibot.check_form_timing(f"{old_ts}.{signature}")
    assert exc.value.log_code == "bad_signature"


def test_stale_form_rejected() -> None:
    with pytest.raises(antibot.SignupRejected) as exc:
        antibot.check_form_timing(_form_ts(antibot.MAX_FORM_SECONDS + 10))
    assert exc.value.log_code == "expired"


def test_human_pace_accepted() -> None:
    antibot.check_form_timing(_form_ts(10))


# ── частота по адресу и подсети ───────────────────────────────────────────


async def _make_user(session: AsyncSession, ip: str, *, minutes_ago: int = 1) -> User:
    user = User(
        id=uuid4(),
        email=f"u-{uuid4().hex[:10]}@example.com",
        password_hash="x",
        signup_ip=ip,
        signup_subnet=antibot.subnet_of(ip),
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )
    session.add(user)
    await session.commit()
    return user


async def test_ip_limit_triggers(db_session: AsyncSession) -> None:
    # Адреса нарочно публичные: документационные диапазоны (203.0.113.x и
    # подобные) считаются служебными, и лимит их не трогает.
    ip = "45.132.20.10"
    for _ in range(antibot.MAX_PER_IP_HOUR):
        await _make_user(db_session, ip)
    with pytest.raises(antibot.SignupRejected) as exc:
        await antibot.check_signup_rate(db_session, ip)
    assert exc.value.log_code == "ip_limit"


async def test_subnet_limit_triggers(db_session: AsyncSession) -> None:
    """Смена последнего октета не помогает обойти защиту."""
    for i in range(antibot.MAX_PER_SUBNET_HOUR):
        await _make_user(db_session, f"45.132.21.{i + 1}")
    with pytest.raises(antibot.SignupRejected) as exc:
        await antibot.check_signup_rate(db_session, "45.132.21.200")
    assert exc.value.log_code == "subnet_limit"


async def test_old_signups_do_not_count(db_session: AsyncSession) -> None:
    """Окно скользящее: вчерашние регистрации не мешают сегодняшней."""
    ip = "45.132.22.5"
    for _ in range(antibot.MAX_PER_IP_HOUR + 2):
        await _make_user(db_session, ip, minutes_ago=120)
    await antibot.check_signup_rate(db_session, ip)


async def test_first_signup_from_ip_allowed(db_session: AsyncSession) -> None:
    await antibot.check_signup_rate(db_session, "45.132.23.1")


async def test_no_ip_does_not_crash(db_session: AsyncSession) -> None:
    await antibot.check_signup_rate(db_session, None)


# ── несуществующий домен ──────────────────────────────────────────────────


async def test_nonexistent_domain_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Наши боты приходили именно с таких доменов: sdffsd.sdd, prweorwef.com."""
    monkeypatch.setattr(antibot, "_domain_has_mail", lambda domain: False)
    with pytest.raises(antibot.SignupRejected) as exc:
        await antibot.check_domain_deliverable("bot@sdffsd.sdd")
    assert exc.value.log_code == "no_mx"


async def test_dns_failure_does_not_block_signup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сбой резолвера не должен закрывать регистрацию живым людям."""

    def boom(domain: str) -> bool:
        raise RuntimeError("resolver down")

    monkeypatch.setattr(antibot, "_domain_has_mail", antibot._probe_domain)
    monkeypatch.setattr("email_validator.validate_email", boom)
    await antibot.check_domain_deliverable("kid@gmail.com")


# ── регистрация целиком ───────────────────────────────────────────────────


async def test_registration_rejects_disposable_email(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        data={
            "email": "bot@mailinator.com",
            "password": "StrongPass12345",
            "agree_privacy": "on",
            "form_ts": _form_ts(),
        },
    )
    assert r.status_code == 400
    assert "Временную почту" in r.text


async def test_registration_rejects_instant_submit(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        data={
            "email": f"human-{uuid4().hex[:8]}@gmail.com",
            "password": "StrongPass12345",
            "agree_privacy": "on",
            "form_ts": antibot.issue_form_token(),
        },
    )
    assert r.status_code == 400
    assert "Слишком быстро" in r.text


async def test_registration_rejects_forged_timestamp(client: AsyncClient) -> None:
    """Бот подставил «форму открыли пять секунд назад» — подпись не сойдётся."""
    r = await client.post(
        "/auth/register",
        data={
            "email": f"human-{uuid4().hex[:8]}@gmail.com",
            "password": "StrongPass12345",
            "agree_privacy": "on",
            "form_ts": f"{datetime.now(UTC).timestamp() - 5:.0f}.deadbeefdeadbeefdeadbeefdeadbeef",
        },
    )
    assert r.status_code == 400


async def test_registration_rejects_missing_timestamp(client: AsyncClient) -> None:
    """Бот, постящий форму напрямую, метку не пришлёт."""
    r = await client.post(
        "/auth/register",
        data={
            "email": f"human-{uuid4().hex[:8]}@gmail.com",
            "password": "StrongPass12345",
            "agree_privacy": "on",
        },
    )
    assert r.status_code == 400


async def test_registration_succeeds_for_human(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        data={
            "email": f"human-{uuid4().hex[:8]}@gmail.com",
            "password": "StrongPass12345",
            "agree_privacy": "on",
            "form_ts": _form_ts(),
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303), r.text[:300]


async def test_register_page_has_timestamp_field(client: AsyncClient) -> None:
    html = (await client.get("/auth/register")).text
    assert 'name="form_ts"' in html
    # значение должно быть подставлено, а не остаться шаблоном
    assert "{{" not in html.split('name="form_ts"')[1][:80]


async def test_honeypot_still_works(client: AsyncClient) -> None:
    """Заполненное скрытое поле — аккаунт не создаётся, но бот видит «успех»."""
    email = f"trap-{uuid4().hex[:8]}@gmail.com"
    r = await client.post(
        "/auth/register",
        data={
            "email": email,
            "password": "StrongPass12345",
            "agree_privacy": "on",
            "website": "http://spam.example",
            "form_ts": _form_ts(),
        },
        follow_redirects=False,
    )
    assert r.status_code == 303


async def test_internal_ip_does_not_limit_everyone(db_session: AsyncSession) -> None:
    """Если прокси не проставил заголовок, все клиенты выглядят как 127.0.0.1.

    Считать их одним человеком нельзя — регистрация закроется всему сайту.
    """
    for _ in range(antibot.MAX_PER_IP_HOUR + 3):
        await _make_user(db_session, "127.0.0.1")
    await antibot.check_signup_rate(db_session, "127.0.0.1")
    await antibot.check_signup_rate(db_session, "10.0.0.7")
