"""Cabinet: /lessio/app/clients/import — bulk CSV upload."""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessio.models import LessioClient, LessioTutorProfile


async def _setup(client: AsyncClient, *, tg_id: int) -> str:
    slug = f"imp_{tg_id}"
    await client.post(
        "/lessio/auth/register",
        data={"email": f"imp{tg_id}@e.com", "password": "strongpass123"},
        follow_redirects=False,
    )
    await client.post(
        "/lessio/app/setup-profile",
        data={"slug": slug, "display_name": "T", "niche": "english"},
        follow_redirects=False,
    )
    return slug


async def test_import_page_renders_upload_form(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _setup(client, tg_id=95000001)
    resp = await client.get("/lessio/app/clients/import")
    assert resp.status_code == 200
    body = resp.text
    assert 'type="file"' in body
    assert "CSV" in body


async def test_import_csv_creates_clients(client: AsyncClient, db_session: AsyncSession) -> None:
    slug = await _setup(client, tg_id=95000002)
    csv_content = (
        b"email,full_name,phone\n"
        b"alice@e.com,Alice Wonder,+79991111111\n"
        b"bob@e.com,Bob Builder,\n"
        b"carol@e.com,Carol Cat,+79992222222\n"
    )
    resp = await client.post(
        "/lessio/app/clients/import",
        files={"csv": ("clients.csv", BytesIO(csv_content), "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text

    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    clients = (
        (await db_session.execute(select(LessioClient).where(LessioClient.tutor_id == profile.id)))
        .scalars()
        .all()
    )
    emails = {c.email for c in clients}
    assert {"alice@e.com", "bob@e.com", "carol@e.com"} <= emails
    alice = next(c for c in clients if c.email == "alice@e.com")
    assert alice.full_name == "Alice Wonder"
    assert alice.phone == "+79991111111"
    bob = next(c for c in clients if c.email == "bob@e.com")
    assert bob.phone is None


async def test_import_skips_duplicates(client: AsyncClient, db_session: AsyncSession) -> None:
    """Если client.email уже есть у tutor'а — пропускаем (last-write-wins
    update имени/телефона)."""
    slug = await _setup(client, tg_id=95000003)
    first_csv = b"email,full_name,phone\ndup@e.com,Old Name,\n"
    await client.post(
        "/lessio/app/clients/import",
        files={"csv": ("c1.csv", BytesIO(first_csv), "text/csv")},
    )
    second_csv = b"email,full_name,phone\ndup@e.com,New Name,+79993333333\n"
    await client.post(
        "/lessio/app/clients/import",
        files={"csv": ("c2.csv", BytesIO(second_csv), "text/csv")},
    )
    profile = (
        await db_session.execute(select(LessioTutorProfile).where(LessioTutorProfile.slug == slug))
    ).scalar_one()
    clients = (
        (await db_session.execute(select(LessioClient).where(LessioClient.tutor_id == profile.id)))
        .scalars()
        .all()
    )
    dups = [c for c in clients if c.email == "dup@e.com"]
    assert len(dups) == 1
    assert dups[0].full_name == "New Name"
    assert dups[0].phone == "+79993333333"


async def test_import_rejects_malformed_csv(client: AsyncClient, db_session: AsyncSession) -> None:
    await _setup(client, tg_id=95000004)
    # Missing email column
    bad_csv = b"name,phone\nNo Email,+79994444444\n"
    resp = await client.post(
        "/lessio/app/clients/import",
        files={"csv": ("bad.csv", BytesIO(bad_csv), "text/csv")},
    )
    assert resp.status_code == 400
    assert "email" in resp.text.lower()
