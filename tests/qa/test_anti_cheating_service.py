"""Tests for the heuristic anti-cheating filter in app.qa.service.

We test the regex patterns directly via the private helper since they're the
defensive perimeter for the platform's "не списываем" ethos.
"""

from __future__ import annotations

from app.qa.service import _contains_cheating_signal


class TestCheatingSignal:
    def test_normal_question_passes(self) -> None:
        assert _contains_cheating_signal("Как найти корни квадратного уравнения?") is None

    def test_solve_for_me_blocked(self) -> None:
        assert _contains_cheating_signal("Реши за меня уравнение x^2 = 4") is not None

    def test_do_my_homework_blocked(self) -> None:
        assert _contains_cheating_signal("Сделайте мне домашку по физике") is not None

    def test_paid_offer_blocked(self) -> None:
        assert _contains_cheating_signal("Куплю решение задачи 14 ЕГЭ") is not None

    def test_phone_number_blocked(self) -> None:
        assert _contains_cheating_signal("Звоните +7 999 123-45-67 решу за деньги") is not None

    def test_phone_with_dashes_blocked(self) -> None:
        assert _contains_cheating_signal("7-999-555-44-33 пишите") is not None

    def test_telegram_handle_blocked(self) -> None:
        assert _contains_cheating_signal("Пишите телеграм: @math_solver") is not None

    def test_partial_keyword_match_passes(self) -> None:
        """The phrase "решить" alone (without "за меня") is fine — it's a legit
        verb for asking how to do something."""
        assert _contains_cheating_signal("Как решить эту задачу") is None
