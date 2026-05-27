"""SEO helpers for Razbery: JSON-LD, OG-image SVG, sitemap rows.

Each question page emits schema.org/QAPage with embedded Question +
AcceptedAnswer + suggestedAnswers — eligible for Google's rich-results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from app.qa.rendering import excerpt

if TYPE_CHECKING:
    from app.qa.models import QAAnswer, QAQuestion, QASubject

BASE_URL = "https://getdoday.ru"


def qapage_jsonld(
    question: QAQuestion,
    answers: list[QAAnswer],
    subject: QASubject,
) -> dict[str, object]:
    """Return a JSON-LD dict for the question detail page.

    Caller json.dumps() it into a `<script type="application/ld+json">` tag.
    """
    url = f"{BASE_URL}/qa/q/{question.id}-{question.slug}"

    def _answer_node(a: QAAnswer) -> dict[str, object]:
        return {
            "@type": "Answer",
            "text": excerpt(a.answer_md + " — " + a.explanation_md, limit=2000),
            "upvoteCount": max(0, a.score),
            "url": f"{url}#a-{a.id}",
            "dateCreated": a.created_at.replace(tzinfo=UTC).isoformat(),
        }

    accepted = next((a for a in answers if a.is_accepted), None)
    suggested = [a for a in answers if not a.is_accepted]

    main_entity: dict[str, object] = {
        "@type": "Question",
        "name": question.title,
        "text": excerpt(question.body_md, limit=2000),
        "answerCount": len(answers),
        "upvoteCount": max(0, question.score),
        "dateCreated": question.created_at.replace(tzinfo=UTC).isoformat(),
        "url": url,
    }
    if accepted is not None:
        main_entity["acceptedAnswer"] = _answer_node(accepted)
    if suggested:
        main_entity["suggestedAnswer"] = [_answer_node(a) for a in suggested]

    return {
        "@context": "https://schema.org",
        "@type": "QAPage",
        "url": url,
        "mainEntity": main_entity,
        "isPartOf": {
            "@type": "WebSite",
            "name": "Razbery — Doday Q&A",
            "url": f"{BASE_URL}/qa/",
        },
        "about": {
            "@type": "Thing",
            "name": subject.name,
        },
    }


def og_image_svg(question: QAQuestion, subject: QASubject) -> bytes:
    """Render a 1200×630 SVG OG-image for the question.

    SVG keeps the response tiny (<5kb) and we don't need a real rasterizer.
    Most social-share platforms accept SVG. For platforms that don't, we
    serve a fallback PNG (not implemented in MVP — most do accept SVG now).
    """
    title_text = (question.title[:90] + "…") if len(question.title) > 90 else question.title
    grade_text = f"{question.grade} класс" if question.grade else ""
    subject_text = subject.name
    icon = subject.icon or "📚"

    title_lines = _wrap(title_text, max_chars=42)
    title_svg = _multiline(title_lines, x=70, y_start=260, line_height=70, font_size=56)

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#4f46e5"/>
      <stop offset="100%" stop-color="#312e81"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <text x="70" y="120" font-family="Inter, sans-serif" font-size="36" fill="#a5b4fc" font-weight="500">Razbery · разбери</text>
  <text x="70" y="180" font-family="Inter, sans-serif" font-size="32" fill="#e0e7ff" font-weight="600">{escape(icon)} {escape(subject_text)} · {escape(grade_text)}</text>
  {title_svg}
  <text x="70" y="560" font-family="Inter, sans-serif" font-size="28" fill="#c7d2fe">getdoday.ru/qa</text>
</svg>
"""
    return svg.encode("utf-8")


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word-wrap. Russian-aware (just splits on whitespace)."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:4]  # cap at 4 lines


def _multiline(lines: list[str], *, x: int, y_start: int, line_height: int, font_size: int) -> str:
    """Render text lines as one `<text>` with `<tspan>` per line."""
    tspans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_height
        tspans.append(f'<tspan x="{x}" dy="{dy}">{escape(line)}</tspan>')
    return (
        f'<text x="{x}" y="{y_start}" font-family="Inter, sans-serif" '
        f'font-size="{font_size}" fill="#ffffff" font-weight="700">' + "".join(tspans) + "</text>"
    )


def sitemap_url_entry(
    loc: str, *, lastmod: datetime | None = None, changefreq: str = "weekly", priority: float = 0.5
) -> dict[str, object]:
    """Shape used by main sitemap builder when ingesting external feature pages."""
    entry: dict[str, object] = {
        "loc": loc,
        "changefreq": changefreq,
        "priority": priority,
    }
    if lastmod is not None:
        entry["lastmod"] = lastmod.replace(tzinfo=UTC).isoformat()
    return entry
