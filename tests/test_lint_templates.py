"""Tests for scripts/lint_templates.py — Jinja template linter."""

from pathlib import Path

import pytest

from scripts.lint_templates import check_text, format_violation, lint_directory


# Override the session-scoped DB fixture from conftest — this module needs no DB.
@pytest.fixture(scope="session", autouse=True)
def _init_test_db() -> None:  # shadows conftest fixture intentionally — no DB needed here
    return


@pytest.fixture
def fake_path(tmp_path: Path) -> Path:
    return tmp_path / "fake.html"


def test_tojson_safe_in_attribute_is_error(fake_path: Path) -> None:
    text = '<div x-data="{{ data|tojson|safe }}"></div>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "tojson-safe-attr"
    assert violations[0].rule.level == "error"


def test_tojson_forceescape_is_clean(fake_path: Path) -> None:
    text = '<div x-data="{{ data|tojson|forceescape }}"></div>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_tojson_safe_e_is_clean(fake_path: Path) -> None:
    """`|tojson|safe|e` is the legacy-but-correct pattern; not flagged."""
    text = '<div x-data="{{ data|tojson|safe|e }}"></div>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_text_8px_warns(fake_path: Path) -> None:
    text = '<span class="text-[8px]">Tiny</span>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "small-text"
    assert violations[0].rule.level == "warning"


def test_text_10px_warns(fake_path: Path) -> None:
    text = '<span class="text-[10px]">Almost</span>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "small-text"


def test_text_11px_clean(fake_path: Path) -> None:
    text = '<span class="text-[11px]">OK</span>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_text_16px_clean(fake_path: Path) -> None:
    text = '<span class="text-[16px]">Large</span>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_suppression_disables_warning(fake_path: Path) -> None:
    text = '{# lint-ignore-next-line: small-text #}\n<span class="text-[10px]">PRO</span>'
    violations = check_text(text, fake_path)
    assert violations == []


def test_suppression_only_affects_immediate_next_line(fake_path: Path) -> None:
    text = '{# lint-ignore-next-line: small-text #}\n<br>\n<span class="text-[10px]">PRO</span>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1


def test_long_script_warns(fake_path: Path) -> None:
    body = "\n".join(["x = 1;"] * 70)
    text = f"<script>{body}</script>"
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    assert violations[0].rule.name == "long-inline-script"
    assert violations[0].rule.level == "warning"


def test_short_script_clean(fake_path: Path) -> None:
    body = "\n".join(["x = 1;"] * 10)
    text = f"<script>{body}</script>"
    violations = check_text(text, fake_path)
    assert violations == []


def test_script_at_60_lines_clean(fake_path: Path) -> None:
    """60 lines is the boundary — only >60 warns."""
    body = "\n".join(["x = 1;"] * 60)
    text = f"<script>{body}</script>"
    violations = check_text(text, fake_path)
    assert violations == []


def test_format_violation_includes_file_line_col_message(fake_path: Path) -> None:
    text = '<div x-data="{{ data|tojson|safe }}"></div>'
    violations = check_text(text, fake_path)
    assert len(violations) == 1
    output = format_violation(violations[0])
    assert str(fake_path) in output
    assert ":1:" in output  # line number
    assert "tojson-safe-attr" in output
    assert "error" in output


def test_lint_directory_walks_html_files(tmp_path: Path) -> None:
    bad = tmp_path / "bad.html"
    bad.write_text('<div x-data="{{ data|tojson|safe }}"></div>')
    good = tmp_path / "good.html"
    good.write_text('<div x-data="{{ data|tojson|forceescape }}"></div>')
    nested = tmp_path / "subdir" / "nested.html"
    nested.parent.mkdir()
    nested.write_text('<span class="text-[8px]">tiny</span>')

    violations = lint_directory(tmp_path)
    rule_names = {v.rule.name for v in violations}
    assert rule_names == {"tojson-safe-attr", "small-text"}


def test_lint_directory_ignores_non_html(tmp_path: Path) -> None:
    py = tmp_path / "x.py"
    py.write_text("data|tojson|safe")  # would match rule, but .py not scanned
    violations = lint_directory(tmp_path)
    assert violations == []


def test_main_returns_1_on_errors(tmp_path: Path) -> None:
    from scripts.lint_templates import main

    bad = tmp_path / "bad.html"
    bad.write_text('<div x-data="{{ data|tojson|safe }}"></div>')
    rc = main([str(tmp_path)])
    assert rc == 1


def test_main_returns_0_on_clean(tmp_path: Path) -> None:
    from scripts.lint_templates import main

    good = tmp_path / "good.html"
    good.write_text('<div x-data="{{ data|tojson|forceescape }}"></div>')
    rc = main([str(tmp_path)])
    assert rc == 0


def test_main_returns_0_on_warnings_only(tmp_path: Path) -> None:
    """Warnings shouldn't block — only errors."""
    from scripts.lint_templates import main

    warn = tmp_path / "warn.html"
    warn.write_text('<span class="text-[8px]">tiny</span>')
    rc = main([str(tmp_path)])
    assert rc == 0
