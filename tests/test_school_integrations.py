"""Tests for the school portal integration scaffold (CRUD + stub sync)."""

import pytest
from httpx import AsyncClient


async def test_list_empty_initially(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/school/integrations")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_integration(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "fake-token-1234567"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "school_mo"
    assert body["enabled"] is True
    assert body["last_sync_at"] is None


async def test_upsert_replaces_existing(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "first-token-1234"},
    )
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "second-token-5678"},
    )
    listing = (await logged_in_client.get("/api/school/integrations")).json()
    assert len(listing) == 1


async def test_invalid_provider_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "alien_portal", "auth_token": "fake-token-1234567"},
    )
    assert response.status_code == 422


async def test_short_token_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "mesh", "auth_token": "x"},
    )
    assert response.status_code == 422


async def test_sync_handles_unauthorized(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad/expired token should surface a friendly message, not a 500."""

    class _FakeResponse:
        def __init__(self) -> None:
            self.status_code = 401
            self.text = "unauthorized"

        def json(self) -> dict[str, object]:
            return {"error": "unauthorized"}

    class _FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)

    await logged_in_client.post(
        "/api/school/integrations",
        data={
            "provider": "school_mo",
            "auth_token": "stale-token-12345",
            "student_id": "560752",
        },
    )
    response = await logged_in_client.post("/api/school/integrations/school_mo/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "401" in body["error"] or "истёк" in body["error"]


async def test_sync_creates_tasks_from_payload(
    logged_in_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock the portal returning two homeworks and verify Doday tasks appear."""

    fake_payload: dict[str, object] = {
        "homeworks": [
            {
                "id": 1,
                "subject_name": "Алгебра",
                "task": "§ 5, № 12-15",
                "deadline": "2026-12-31",
            },
            {
                "id": 2,
                "subject": {"name": "Физика"},
                "description": "Лабораторная по оптике",
                "due_at": "2026-12-25T20:00:00Z",
            },
        ]
    }

    class _FakeResponse:
        def __init__(self) -> None:
            self.status_code = 200
            self.text = ""

        def json(self) -> dict[str, object]:
            return fake_payload

    class _FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)

    await logged_in_client.post(
        "/api/school/integrations",
        data={
            "provider": "school_mo",
            "auth_token": "good-token-1234567",
            "student_id": "560752",
        },
    )
    response = await logged_in_client.post("/api/school/integrations/school_mo/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["pulled"] == 2
    assert body["created"] == 2

    # Re-running is idempotent — already-existing titles aren't duplicated.
    again = (await logged_in_client.post("/api/school/integrations/school_mo/sync")).json()
    assert again["created"] == 0


async def test_sync_unknown_integration_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post("/api/school/integrations/mesh/sync")
    assert response.status_code == 404


async def test_sync_without_student_id_returns_friendly_error(
    logged_in_client: AsyncClient,
) -> None:
    """Pre-flight: portal returns an opaque 400 if student_id is missing — we
    catch this before hitting the portal and surface a clear instruction."""
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "tok-1234567"},  # no student_id
    )
    response = await logged_in_client.post("/api/school/integrations/school_mo/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "student_id" in body["error"].lower() or "ученика" in body["error"]


async def test_delete_integration(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "mesh", "auth_token": "fake-token-1234567"},
    )
    response = await logged_in_client.delete("/api/school/integrations/mesh")
    assert response.status_code == 204
    listing = (await logged_in_client.get("/api/school/integrations")).json()
    assert listing == []


async def test_paste_import_creates_tasks(logged_in_client: AsyncClient) -> None:
    """Manual paste-import: user pastes raw JSON, Doday creates tasks."""
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "doesnt-matter-for-paste-12345"},
    )
    payload = {
        "homeworks": [
            {"id": 1, "subject_name": "История", "task": "Параграф 7", "deadline": "2026-12-20"},
            {"id": 2, "subject_name": "ОБЖ", "task": "Реферат про пожар"},
        ]
    }
    response = await logged_in_client.post(
        "/api/school/integrations/school_mo/import", json=payload
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["pulled"] == 2
    assert body["created"] == 2

    # Idempotent on second call.
    again = (
        await logged_in_client.post("/api/school/integrations/school_mo/import", json=payload)
    ).json()
    assert again["created"] == 0


async def test_paste_import_empty_payload_returns_error(
    logged_in_client: AsyncClient,
) -> None:
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "tok-1234567"},
    )
    response = await logged_in_client.post(
        "/api/school/integrations/school_mo/import", json={"homeworks": []}
    )
    body = response.json()
    assert body["ok"] is False
    assert body["error"]


async def test_paste_import_unknown_integration_404(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations/mesh/import", json={"homeworks": [{"task": "x"}]}
    )
    assert response.status_code == 404


async def test_help_article_renders(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/help/school-integrations")).text
    assert "Школьный портал МО" in body
    assert "aupd_token" in body
    assert "dnevnik.mos.ru" in body


async def test_profile_shows_school_section(logged_in_client: AsyncClient) -> None:
    body = (await logged_in_client.get("/doday/app/settings")).text
    assert "Школьный дневник" in body
    assert "/api/school/integrations" in body
    # Primary token-acquisition method: portal's /v2/token/refresh pages.
    assert "authedu.mosreg.ru/v2/token/refresh" in body
    assert "school.mos.ru/v2/token/refresh" in body


async def test_create_integration_stores_student_id(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/integrations",
        data={
            "provider": "school_mo",
            "auth_token": "fake-token-1234567",
            "student_id": "560752",
        },
    )
    assert response.status_code == 200
    assert response.json()["student_id"] == "560752"


async def test_import_skips_not_assigned_and_empty(logged_in_client: AsyncClient) -> None:
    """Real authedu shape: «не задано» / blank homework must not become tasks."""
    await logged_in_client.post(
        "/api/school/integrations",
        data={"provider": "school_mo", "auth_token": "tok-1234567", "student_id": "560752"},
    )
    payload = {
        "payload": [
            {"subject_name": "Литература", "homework": "не задано", "date": "2026-12-25"},
            {"subject_name": "Физика", "homework": "", "date": "2026-12-25"},
            {
                "subject_name": "Алгебра",
                "homework": "§ 5, № 12",
                "date": "2026-12-25",
                "homework_id": 99,
            },
        ]
    }
    body = (
        await logged_in_client.post("/api/school/integrations/school_mo/import", json=payload)
    ).json()
    assert body["ok"] is True
    assert body["pulled"] == 1  # only Алгебра survives the «не задано» filter
    assert body["created"] == 1
