"""Tests for app.qa.reputation — privilege gates + clamp_floor."""

from __future__ import annotations

from app.qa.reputation import Privilege, ReputationDelta, can, clamp_floor


class TestPrivilegeGates:
    def test_post_at_rep_1(self) -> None:
        assert can(1, Privilege.POST)
        assert not can(0, Privilege.POST)

    def test_downvote_requires_50(self) -> None:
        assert not can(49, Privilege.DOWNVOTE)
        assert can(50, Privilege.DOWNVOTE)
        assert can(1000, Privilege.DOWNVOTE)

    def test_edit_others_requires_200(self) -> None:
        assert not can(199, Privilege.EDIT_OTHERS)
        assert can(200, Privilege.EDIT_OTHERS)

    def test_moderate_requires_2000(self) -> None:
        assert not can(1999, Privilege.MODERATE)
        assert can(2000, Privilege.MODERATE)


class TestClampFloor:
    def test_positive_unchanged(self) -> None:
        assert clamp_floor(5) == 5
        assert clamp_floor(1000) == 1000

    def test_zero(self) -> None:
        assert clamp_floor(0) == 0

    def test_negative_becomes_zero(self) -> None:
        assert clamp_floor(-5) == 0
        assert clamp_floor(-100) == 0


class TestReputationDeltas:
    """Sanity-check the magnitudes follow the spec."""

    def test_answer_upvote_bigger_than_question(self) -> None:
        # Spec: A_UPVOTE=10, Q_UPVOTE=5 — answers worth more rep than questions
        assert int(ReputationDelta.A_UPVOTE) > int(ReputationDelta.Q_UPVOTE)

    def test_accept_biggest_award(self) -> None:
        # Spec: A_ACCEPTED_AUTHOR=15 — biggest single award
        assert int(ReputationDelta.A_ACCEPTED_AUTHOR) >= int(ReputationDelta.A_UPVOTE)

    def test_downvotes_smaller_than_upvotes(self) -> None:
        # Downvote pain (-2) should be smaller than upvote joy (+10)
        assert abs(int(ReputationDelta.A_DOWNVOTE)) < int(ReputationDelta.A_UPVOTE)

    def test_hidden_is_steep(self) -> None:
        # Q_HIDDEN should be visibly painful (-20 in spec)
        assert int(ReputationDelta.Q_HIDDEN) <= -10
        assert int(ReputationDelta.A_HIDDEN) <= -10
