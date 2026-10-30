"""The question form must render safely, including failed submissions."""

import json
import re
from html.parser import HTMLParser

from httpx import AsyncClient


class FormState(HTMLParser):
    state: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form" and values.get("action") == "/qa/ask":
            self.state = values.get("x-data") or ""


async def test_question_form_opens(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.get("/qa/ask")
    assert response.status_code == 200
    assert "Задать вопрос" in response.text


async def test_short_question_returns_form_instead_of_500(logged_in_client: AsyncClient) -> None:
    response = await logged_in_client.post(
        "/qa/ask",
        data={
            "subject_slug": "math",
            "title": "short",
            "body_md": "not long enough",
        },
    )
    assert response.status_code == 422
    assert 'action="/qa/ask"' in response.text


async def test_failed_question_keeps_quotes_newlines_and_html_as_text(
    logged_in_client: AsyncClient,
) -> None:
    title = "Вопрос: \"цитата\" и 'апостроф' <img src=x onerror=alert(1)>"
    body = 'Условие первой строки с "кавычками"\nИ ещё строка: </script><script>alert(1)</script>'
    response = await logged_in_client.post(
        "/qa/ask",
        data={
            "subject_slug": "missing-subject",
            "title": title,
            "body_md": body,
        },
    )
    assert response.status_code == 400
    parser = FormState()
    parser.feed(response.text)
    for field, expected in [("title", title), ("body", body)]:
        match = re.search(rf'{field}:\s*("(?:[^"\\]|\\.)*"),', parser.state)
        assert match
        assert json.loads(match.group(1)) == expected
    assert "<img src=x" not in response.text
    assert "<script>alert(1)</script>" not in response.text
