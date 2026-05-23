"""Experimental-features registry + per-user opt-in helper.

Some features that were aggressively removed during phase α (2026-05-13) are
being incrementally revived as opt-in experiments. They live behind a per-user
flag (`users.experiments` JSONB column) so they don't clutter the UI for users
who didn't ask for them, and the team can iterate without breaking the focused
core product.

Add a new experiment here, run the matching migration if it needs schema, then
toggle from /app/settings → «🧪 Экспериментальные функции».
"""

from __future__ import annotations

from dataclasses import dataclass

from app.auth.models import User


@dataclass(frozen=True)
class Experiment:
    """Catalog entry — feature key + UI copy + readiness label."""

    key: str
    title: str
    description: str
    # "alpha" — actively built, may break · "beta" — stable enough for daily use.
    stage: str = "alpha"


# Single source of truth — referenced by the settings UI and by feature-gating
# checks (`is_enabled(user, EXP.key.GRAPH)`).
AVAILABLE: tuple[Experiment, ...] = (
    Experiment(
        key="graph",
        title="Граф связей задач",
        description=(
            "Космический вид всех активных задач + двунаправленные ссылки между ними "
            "(как в Obsidian). Можно связать любые две задачи — даже из разных проектов."
        ),
        stage="beta",
    ),
)


# Convenience lookup map: key → Experiment.
BY_KEY: dict[str, Experiment] = {e.key: e for e in AVAILABLE}


def is_enabled(user: User, key: str) -> bool:
    """True if `user` has opted into the experiment `key`. Unknown keys → False."""
    if key not in BY_KEY:
        return False
    flags = user.experiments or {}
    return bool(flags.get(key))
