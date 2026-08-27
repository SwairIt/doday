"""JSON внутри <script>: заголовок вопроса не должен становиться кодом.

Страница вопроса Razbery публичная, а JSON-LD на ней собирается из заголовка
и текста, которые пишет любой зарегистрированный пользователь. `json.dumps`
экранирует кавычки, но не `<`, и HTML-парсер закрывает `<script>` на первом
же `</script` — независимо от того, что тот стоит внутри JSON-строки.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.qa.seo import qapage_jsonld
from app.safe_json import script_json

PAYLOAD = "</script><script>fetch('https://evil.example')</script>"


def test_angle_brackets_never_survive() -> None:
    out = script_json({"title": PAYLOAD})
    assert "<" not in out
    assert ">" not in out
    assert "\\u003c" in out


def test_ampersand_escaped() -> None:
    """`&` — вход в HTML-сущности, внутри <script> ему делать нечего."""
    assert "&" not in script_json({"q": "a & b"})


def test_line_separators_escaped() -> None:
    """U+2028/U+2029 валидны в JSON, но рвут строку для JS-парсера."""
    out = script_json({"q": "a b c"})
    assert " " not in out
    assert " " not in out


def test_value_survives_roundtrip() -> None:
    """Экранирование не портит данные: JSON остаётся тем же JSON."""
    import json

    data = {"title": PAYLOAD, "русский": "текст", "n": 42}
    assert json.loads(script_json(data)) == data


def _question(title: str) -> Any:
    now = datetime.now(UTC).replace(tzinfo=None)
    return SimpleNamespace(
        id=uuid4(),
        slug="test",
        title=title,
        body_md=PAYLOAD,
        score=1,
        created_at=now,
    )


def test_question_jsonld_is_inert() -> None:
    """Сквозная проверка: вредоносный заголовок вопроса не закрывает тег."""
    subject = SimpleNamespace(name="Математика", slug="math")
    payload = script_json(qapage_jsonld(_question(PAYLOAD), [], subject))
    assert "</script" not in payload
    assert "<script" not in payload
