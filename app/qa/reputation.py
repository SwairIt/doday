"""Reputation deltas and privilege gates for the Razbery feature.

Inspired by StackOverflow but trimmed: see spec §7. Floor: 0.
"""

from __future__ import annotations

from enum import IntEnum


class ReputationDelta(IntEnum):
    Q_UPVOTE = 5
    Q_DOWNVOTE = -2
    A_UPVOTE = 10
    A_DOWNVOTE = -2
    A_ACCEPTED_AUTHOR = 15  # answerer's reward
    A_ACCEPTED_ASKER = 2  # asker's reward for closing the loop
    DOWNVOTER_COST = -1  # cost of casting a downvote
    Q_HIDDEN = -20
    A_HIDDEN = -20


class Privilege(IntEnum):
    """Reputation thresholds required for each privilege."""

    POST = 1
    UPVOTE = 1
    FLAG_OWN = 15
    DOWNVOTE = 50
    COMMENT = 50  # commenting reserved for phase-2 but threshold known
    EDIT_OTHERS = 200
    VOTE_TO_CLOSE = 500
    VOTE_TO_DELETE = 1000
    MODERATE = 2000


def can(rep: int, priv: Privilege) -> bool:
    return rep >= int(priv)


def clamp_floor(value: int) -> int:
    """Reputation never goes below 0."""
    return max(0, value)
