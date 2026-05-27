"""Markdown rendering and sanitization for Razbery content.

Pipeline: markdown-it-py → HTML → bleach allow-list.
KaTeX markup (`$x$`, `$$ x $$`) is preserved in the output so client-side
KaTeX auto-render can pick it up.

NEVER trust user input — always pipe through `render_markdown()` before
storing the `_html` columns.
"""

from __future__ import annotations

import re

import bleach
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"breaks": True, "linkify": True, "html": False})
_md.enable("table")
_md.enable("strikethrough")

_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "u",
        "s",
        "del",
        "code",
        "pre",
        "blockquote",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "a",
        "span",
    }
)

_ALLOWED_ATTRS: dict[str, list[str]] = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    "span": ["class"],
    "th": ["align"],
    "td": ["align"],
}

_ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})


def render_markdown(md: str) -> str:
    """Render `md` to safe HTML.

    Pipeline:
    1. markdown-it-py → HTML
    2. bleach.clean with allow-list (strip everything else)
    3. post-pass to add `target=_blank rel=noopener` to external links
    """
    if not md:
        return ""
    raw_html = _md.render(md)
    cleaned = bleach.clean(
        raw_html,
        tags=list(_ALLOWED_TAGS),
        attributes=_ALLOWED_ATTRS,
        protocols=list(_ALLOWED_PROTOCOLS),
        strip=True,
    )
    return _post_process_links(cleaned)


def _post_process_links(html: str) -> str:
    """Add target/rel to external `<a href="http…">` tags."""

    def replace(m: re.Match[str]) -> str:
        href = m.group(1)
        if href.startswith(("http://", "https://")):
            return f'<a href="{href}" target="_blank" rel="noopener nofollow ugc">'
        return m.group(0)

    return re.sub(r'<a href="([^"]+)">', replace, html)


def excerpt(md: str, limit: int = 160) -> str:
    """Strip markdown markers for meta description / OG description.

    Heuristic, not perfect. Removes code fences, links, headings prefix, bold/italic
    markers; collapses whitespace. Truncates with ellipsis.
    """
    text = md
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    truncated = text[: limit - 1].rsplit(" ", 1)[0]
    return truncated.rstrip(",.;:!?") + "…"


def slugify(text: str, max_len: int = 120) -> str:
    """Build URL-safe latin slug from RU/EN title.

    Uses transliteration via a small fixed map (no external dep). Strips
    punctuation, collapses dashes, lowercases. Empty result becomes "q".
    """
    cyr_to_lat = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "j",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shh",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    out = []
    for ch in text.lower():
        if ch in cyr_to_lat:
            out.append(cyr_to_lat[ch])
        elif ch.isascii() and (ch.isalnum() or ch in "-_"):
            out.append(ch)
        elif ch.isspace() or ch in ",.;:!?\"'()[]{}":
            out.append("-")
        # else: drop
    slug = "".join(out)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "q"
    return slug[:max_len].rstrip("-")
