"""Dynamic per-tutor OG-image SVG generator.

1200×630 SVG (Twitter card / OG standard). Inline без headless browser — SVG
рендерится социалкой как PNG автоматически (Facebook, Telegram, VK supports).
Тinted background + emoji + display_name + niche-label.
"""

from __future__ import annotations

from html import escape

from app.lessio.models import LessioTutorProfile

_NICHE_LABELS: dict[str, str] = {
    "english": "Преподаватель английского",
    "ielts": "Преподаватель IELTS / TOEFL",
    "math": "Репетитор математики",
    "school": "Школьный репетитор",
    "fitness": "Тренер",
    "psychology": "Психолог",
    "yoga": "Инструктор йоги",
    "other": "Преподаватель",
}


def render_tutor_og_svg(tutor: LessioTutorProfile) -> bytes:
    """Return bytes of 1200×630 SVG ready as og:image."""
    name = escape(tutor.display_name[:40])
    emoji = escape(tutor.avatar_emoji or "✦")
    niche_label = _NICHE_LABELS.get(tutor.niche, "Преподаватель")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" '
        'viewBox="0 0 1200 630">'
        "<defs>"
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#0f0a1f"/>'
        '<stop offset="1" stop-color="#2e1065"/>'
        "</linearGradient>"
        '<linearGradient id="name" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#a78bfa"/>'
        '<stop offset="1" stop-color="#f472b6"/>'
        "</linearGradient>"
        "</defs>"
        '<rect width="1200" height="630" fill="url(#bg)"/>'
        f'<text x="600" y="240" font-family="Apple Color Emoji, Segoe UI Emoji, sans-serif" '
        f'font-size="140" text-anchor="middle">{emoji}</text>'
        f'<text x="600" y="390" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, '
        'Roboto, sans-serif" font-size="64" font-weight="800" fill="url(#name)" '
        f'text-anchor="middle">{name}</text>'
        f'<text x="600" y="455" font-family="-apple-system, sans-serif" font-size="32" '
        f'fill="#a78bfa" text-anchor="middle">{escape(niche_label)}</text>'
        '<text x="600" y="570" font-family="-apple-system, sans-serif" font-size="22" '
        'fill="rgba(255,255,255,.5)" text-anchor="middle">✦ Lessio · getdoday.ru</text>'
        "</svg>"
    )
    return body.encode("utf-8")
