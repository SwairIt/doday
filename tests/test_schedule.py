"""Tests for the school weekly schedule (CRUD + view rendering)."""

from httpx import AsyncClient


async def test_schedule_view_renders_for_logged_in(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/app/schedule")
    assert response.status_code == 200
    body = response.text
    assert "Расписание уроков" in body
    # subjects = {{ ... |tojson|forceescape }} produces HTML-escaped JSON in the
    # x-data attribute — Alpine decodes &quot; → " at runtime, so we check the
    # HTML-encoded form.
    assert "&quot;math&quot;" in body and "&quot;physics&quot;" in body
    assert "/api/school/schedule" in body


async def test_list_empty_initially(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/api/school/schedule")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_slot(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "0", "period": "1", "subject_code": "math", "room": "318"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["weekday"] == 0
    assert body["period"] == 1
    assert body["subject_code"] == "math"
    assert body["room"] == "318"


async def test_upsert_replaces_existing_slot(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "0", "period": "1", "subject_code": "math"},
    )
    await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "0", "period": "1", "subject_code": "physics", "room": "412"},
    )
    listing = (await logged_in_client.get("/api/school/schedule")).json()
    assert len(listing) == 1
    assert listing[0]["subject_code"] == "physics"
    assert listing[0]["room"] == "412"


async def test_delete_slot(logged_in_client: AsyncClient) -> None:
    await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "1", "period": "3", "subject_code": "biology"},
    )
    response = await logged_in_client.delete("/api/school/schedule/1/3")
    assert response.status_code == 204
    listing = (await logged_in_client.get("/api/school/schedule")).json()
    assert listing == []


async def test_invalid_subject_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "0", "period": "1", "subject_code": "alchemy"},
    )
    assert response.status_code == 422


async def test_out_of_range_weekday_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "9", "period": "1", "subject_code": "math"},
    )
    assert response.status_code == 422


async def test_out_of_range_period_rejected(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/api/school/schedule",
        data={"weekday": "0", "period": "99", "subject_code": "math"},
    )
    assert response.status_code == 422


async def test_multiple_slots_persist(logged_in_client: AsyncClient) -> None:
    for w, p, code in [(0, 1, "math"), (0, 2, "rus"), (1, 1, "eng")]:
        await logged_in_client.post(
            "/api/school/schedule",
            data={"weekday": str(w), "period": str(p), "subject_code": code},
        )
    listing = (await logged_in_client.get("/api/school/schedule")).json()
    assert len(listing) == 3
