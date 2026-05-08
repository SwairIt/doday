"""Tests for scripts/lint_templates.py — Jinja template linter."""

from pathlib import Path

import pytest

from scripts.lint_templates import check_text


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
    text = (
        "{# lint-ignore-next-line: small-text #}\n"
        '<span class="text-[10px]">PRO</span>'
    )
    violations = check_text(text, fake_path)
    assert violations == []


def test_suppression_only_affects_immediate_next_line(fake_path: Path) -> None:
    text = (
        "{# lint-ignore-next-line: small-text #}\n"
        "<br>\n"
        '<span class="text-[10px]">PRO</span>'
    )
    violations = check_text(text, fake_path)
    assert len(violations) == 1
