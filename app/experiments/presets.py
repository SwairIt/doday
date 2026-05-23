"""Feature presets — bulk-toggle multiple experiments at once.

The full experiments registry (`app.experiments.service.AVAILABLE`) grew to 7
entries. New users have to flip them one by one to find the combo that fits
their workflow. A preset is a named bundle: «school student», «productivity
maximalist», «minimalist» — picking one flips the right flags in one request.

Presets are NOT exclusive — the user can pick a preset, then individually
flip a single flag off/on. The preset is just a starting configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    """A named bundle of experiment-keys.

    `enabled_keys` lists the keys to turn on; every other registered experiment
    is turned off when this preset is applied (full reset semantics — picking
    a preset gives you exactly the listed set, nothing else).
    """

    key: str
    title: str
    description: str
    enabled_keys: tuple[str, ...]


# Order matters — the UI renders them in this order. The first preset is
# "what most people want" → keep MIN simple at the top.
PRESETS: tuple[Preset, ...] = (
    Preset(
        key="minimum",
        title="Минимум",
        description=(
            "Чистый фокус-todo, как Todoist. Никаких графов, привычек, бейджей. "
            "Только задачи, проекты, лейблы, дедлайны. Хорошо для тех, кому "
            "нужно просто закрывать дела."
        ),
        enabled_keys=(),
    ),
    Preset(
        key="schoolchild",
        title="Школьник",
        description=(
            "Привычки, бейджи, настроение, авто-синк школьного дневника. "
            "Лёгкая геймификация для мотивации + интеграция со школьными "
            "порталами. Без сложных продуктивных штук."
        ),
        enabled_keys=("habits", "achievements", "mood", "school"),
    ),
    Preset(
        key="student",
        title="Студент",
        description=(
            "Графы связанных задач (для курсовых/проектов), таймер времени, "
            "свои шаблоны проектов, привычки, календарь-фид. Без «детской» "
            "геймификации, но с продуктивными инструментами."
        ),
        enabled_keys=(
            "graph",
            "calendar_feed",
            "user_templates",
            "habits",
            "time_tracking",
        ),
    ),
    Preset(
        key="schoolchild_plus",
        title="Школьник +",
        description=(
            "Всё из «Школьника» плюс встроенная игра Tap Tower для пятиминутных "
            "отвлечений между уроками. Геймификация по полной."
        ),
        enabled_keys=(
            "habits",
            "achievements",
            "mood",
            "school",
            "taptower",
        ),
    ),
    Preset(
        key="maximum",
        title="Максимум",
        description=(
            "Включает всё. Для тех, кто хочет попробовать все эксперименты "
            "сразу или для админов. Можно выключить отдельные функции после."
        ),
        # Will be filled with every registered experiment key at startup; see
        # `expand_maximum_keys()` below for the resolution.
        enabled_keys=("__all__",),
    ),
)


BY_KEY: dict[str, Preset] = {p.key: p for p in PRESETS}


def expand_maximum_keys(all_experiment_keys: tuple[str, ...]) -> dict[str, Preset]:
    """Return BY_KEY with the «maximum» preset's `__all__` placeholder expanded.

    Done at request-time (not module-load) so the registry can grow without
    rewriting this file."""
    result: dict[str, Preset] = {}
    for preset in PRESETS:
        if preset.enabled_keys == ("__all__",):
            result[preset.key] = Preset(
                key=preset.key,
                title=preset.title,
                description=preset.description,
                enabled_keys=all_experiment_keys,
            )
        else:
            result[preset.key] = preset
    return result
