"""SEO helpers for Doday PDD — per-page meta + schema.org JSON-LD.

Each question page emits a `schema.org/Question` block (with the accepted answer)
so search engines can show rich results — the same compounding-content lever that
drives Razbery.
"""

from __future__ import annotations

import json

from app.pdd.models import PddQuestion, PddTicket, PddTopic

BASE = "https://getdoday.ru"


def _trim(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _correct_option_text(question: PddQuestion) -> str:
    for option in question.options:
        if option.position == question.correct_position:
            return option.text
    return ""


def question_meta(question: PddQuestion) -> dict[str, str]:
    title = f"{_trim(question.text, 70)} — билет {question.ticket.number} | ПДД онлайн"
    answer = _correct_option_text(question)
    description = _trim(f"Правильный ответ: {answer}. {question.explanation}")
    return {
        "title": title,
        "description": description,
        "canonical": f"{BASE}/pdd/vopros/{question.public_slug}",
    }


def ticket_meta(ticket: PddTicket) -> dict[str, str]:
    return {
        "title": f"Билет {ticket.number} ПДД онлайн — 20 вопросов с ответами и пояснениями",
        "description": (
            f"Билет {ticket.number} ПДД категории АВМ: 20 официальных вопросов с "
            "правильными ответами и разбором. Решай онлайн бесплатно."
        ),
        "canonical": f"{BASE}/pdd/bilet/{ticket.number}",
    }


def topic_meta(topic: PddTopic) -> dict[str, str]:
    return {
        "title": f"{topic.title} — вопросы ПДД по теме с ответами",
        "description": _trim(
            topic.description
            or f"Все вопросы ПДД по теме «{topic.title}» с правильными ответами и пояснениями."
        ),
        "canonical": f"{BASE}/pdd/tema/{topic.slug}",
    }


def question_jsonld(question: PddQuestion) -> str:
    """schema.org Question JSON-LD string for embedding in a <script> tag."""
    accepted = _correct_option_text(question)
    accepted_text = accepted
    if question.explanation:
        accepted_text = f"{accepted}. {question.explanation}"
    data = {
        "@context": "https://schema.org",
        "@type": "Question",
        "name": _trim(question.text, 110),
        "text": question.text,
        "acceptedAnswer": {"@type": "Answer", "text": accepted_text},
        "suggestedAnswer": [
            {"@type": "Answer", "text": option.text}
            for option in question.options
            if option.position != question.correct_position
        ],
    }
    return json.dumps(data, ensure_ascii=False)
