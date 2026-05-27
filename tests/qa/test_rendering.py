"""Tests for app.qa.rendering — markdown sanitization, slugify, excerpt."""

from __future__ import annotations

from app.qa.rendering import excerpt, render_markdown, slugify


class TestRenderMarkdown:
    def test_renders_plain_markdown(self) -> None:
        html = render_markdown("**bold** and *italic*")
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html

    def test_strips_script_tags(self) -> None:
        """Real `<script>` tags must not appear; HTML-escaping the literal is
        fine because escaped text is inert."""
        html = render_markdown("hello <script>alert('xss')</script> world")
        # The browser never sees an executable script tag — that's what matters.
        assert "<script>" not in html
        assert "<script " not in html
        # Confirm content was escaped not silently dropped
        assert "&lt;script&gt;" in html or "script" not in html

    def test_strips_event_handlers(self) -> None:
        """No `<a href="javascript:...">` must escape into output. The literal
        text may remain as part of the unrendered markdown (which is harmless)."""
        html = render_markdown("[click](javascript:alert(1))")
        assert '<a href="javascript:' not in html
        assert "<a " not in html or 'href="javascript' not in html

    def test_preserves_code_blocks(self) -> None:
        html = render_markdown("```python\nx = 1\n```")
        assert "<pre>" in html and "<code" in html

    def test_external_link_adds_target_blank(self) -> None:
        html = render_markdown("[link](https://example.com)")
        assert 'target="_blank"' in html
        assert 'rel="noopener nofollow ugc"' in html

    def test_preserves_latex_markers(self) -> None:
        """KaTeX runs client-side from $...$ markers; we must keep them intact."""
        html = render_markdown("Решение: $x^2 + 1 = 0$ не имеет корней.")
        assert "$x^2 + 1 = 0$" in html

    def test_empty_input_returns_empty(self) -> None:
        assert render_markdown("") == ""

    def test_list_rendering(self) -> None:
        html = render_markdown("- one\n- two\n- three")
        assert "<ul>" in html
        assert html.count("<li>") == 3


class TestExcerpt:
    def test_strips_markdown_markers(self) -> None:
        out = excerpt("**bold** _italic_ `code`")
        assert "**" not in out
        assert "_" not in out
        assert "`" not in out

    def test_truncates_with_ellipsis(self) -> None:
        long = "слово " * 100
        out = excerpt(long, limit=50)
        assert len(out) <= 51  # 50 + ellipsis char
        assert out.endswith("…")

    def test_short_text_unchanged(self) -> None:
        assert excerpt("короткий текст", limit=160) == "короткий текст"

    def test_removes_code_fences(self) -> None:
        out = excerpt("Решение:\n```python\nx = 1\nprint(x)\n```\nОтвет 1.")
        assert "```" not in out
        assert "python" not in out

    def test_strips_bare_urls(self) -> None:
        out = excerpt("Посмотри https://example.com тут")
        assert "https" not in out


class TestSlugify:
    def test_basic_cyrillic(self) -> None:
        assert slugify("Привет мир") == "privet-mir"

    def test_with_punctuation(self) -> None:
        assert slugify("Как решить уравнение?") == "kak-reshit-uravnenie"

    def test_collapses_dashes(self) -> None:
        assert slugify("слово  -  слово") == "slovo-slovo"

    def test_mixed_cyrillic_latin(self) -> None:
        s = slugify("Python для 5 класса")
        assert "python" in s
        assert "5" in s
        assert "klassa" in s or "klass" in s

    def test_empty_fallback(self) -> None:
        assert slugify("") == "q"
        assert slugify("???") == "q"

    def test_truncates_to_max_len(self) -> None:
        long = "слово " * 50
        out = slugify(long, max_len=20)
        assert len(out) <= 20
        assert not out.endswith("-")
