"""Токен школьного портала не должен лежать в базе открытым текстом.

`aupd_token` даёт полный доступ к дневнику ребёнка на dnevnik.mos.ru или
Школьном портале МО и живёт около десяти дней.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.school.crypto import decrypt_token, encrypt_token
from app.school.models import SchoolIntegration
from app.school.schemas import IntegrationIn
from app.school.service import upsert_integration

TOKEN = "aupd_token_1234567890_secret"


def test_roundtrip() -> None:
    assert decrypt_token(encrypt_token(TOKEN)) == TOKEN


def test_ciphertext_does_not_contain_plaintext() -> None:
    assert TOKEN not in encrypt_token(TOKEN)


def test_two_encryptions_differ() -> None:
    """Fernet добавляет случайный вектор — одинаковый токен даёт разный текст."""
    assert encrypt_token(TOKEN) != encrypt_token(TOKEN)


def test_legacy_plaintext_still_readable() -> None:
    """Записи, сделанные до шифрования, обязаны продолжать работать."""
    assert decrypt_token(TOKEN) == TOKEN


def test_empty_token() -> None:
    assert decrypt_token(None) is None
    assert decrypt_token("") is None


async def test_saved_integration_is_encrypted(
    db_session: AsyncSession, logged_in_client: object
) -> None:
    from app.auth.models import User

    user = (
        await db_session.execute(select(User).where(User.email == "logged-in@example.com"))
    ).scalar_one()
    await upsert_integration(
        db_session,
        user.id,
        IntegrationIn(provider="school_mo", auth_token=TOKEN, student_id="560752"),
    )
    row = (
        await db_session.execute(
            select(SchoolIntegration).where(SchoolIntegration.user_id == user.id)
        )
    ).scalar_one()
    assert row.auth_token is not None
    assert TOKEN not in row.auth_token
    assert decrypt_token(row.auth_token) == TOKEN
