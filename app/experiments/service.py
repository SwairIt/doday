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
    """Catalog entry — feature key + UI copy + readiness label.

    `stage`:
    - "stable" — production-ready, just hidden by default to keep UI focused.
      Shown in /app/settings under «Функции» (no «🧪» badge).
    - "beta"   — usable daily, may still ship breaking UI changes.
    - "alpha"  — actively built, may break, no SLO. Shown under «Эксперименты».
    """

    key: str
    title: str
    description: str
    stage: str = "alpha"


# Single source of truth — referenced by the settings UI and by feature-gating
# checks (`is_enabled(user, EXP.key.GRAPH)`).
AVAILABLE: tuple[Experiment, ...] = (
    Experiment(
        key="school",
        title="Учёба — Школьный портал",
        description=(
            "Подключаешь школьный портал (Школьный портал МО или МЭШ) — домашка "
            "автоматически синхронизируется в твои задачи. В сайдбаре появляется "
            "отдельная вкладка «🎓 Учёба» со всем расписанием, домашкой и "
            "интеграциями. Pull обновления раз в ~15 минут, когда заходишь на "
            "«Сегодня»."
        ),
        stage="stable",
    ),
    Experiment(
        key="graph",
        title="Граф связей задач",
        description=(
            "Космический вид всех активных задач + двунаправленные ссылки между ними "
            "(как в Obsidian). Можно связать любые две задачи — даже из разных проектов."
        ),
        stage="stable",
    ),
    Experiment(
        key="calendar_feed",
        title="Календарь-фид (.ics)",
        description=(
            "Подписка на твои задачи как на календарь — Apple/Google Calendar, "
            "Telegram, Outlook читают этот формат. Получаешь персональный URL, "
            "вставляешь в календарное приложение → все задачи с дедлайнами видны "
            "там же, где встречи. Обновляется автоматически каждые ~15 минут."
        ),
        stage="stable",
    ),
    Experiment(
        key="user_templates",
        title="Свои шаблоны проектов",
        description=(
            "Сохраняешь любой проект (со всеми секциями и активными задачами) "
            "как переиспользуемый шаблон, а потом одним кликом разворачиваешь "
            "его в новый проект. Полезно для типовых процессов: ремонт квартиры, "
            "запуск рекламной кампании, чек-лист отпуска. В шапке проекта "
            "появляется кнопка «Сохранить как шаблон», в настройках — список."
        ),
        stage="stable",
    ),
    Experiment(
        key="habits",
        title="Трекер привычек",
        description=(
            "Простой ежедневный трекер: добавляешь привычку, каждый день отмечаешь "
            "галочкой. Видишь календарь-«ёлку» с отмеченными днями и серию подряд. "
            "Не путать со «стриками задач» — это про привычки (читать, пить воду, "
            "учиться), не про закрытие задач."
        ),
        stage="alpha",
    ),
    Experiment(
        key="mood",
        title="Трекер настроения",
        description=(
            "Один раз в день один тап: 😞 😐 🙂 😄 🤩. Видишь, как менялось настроение "
            "за неделю/месяц — иногда полезно заметить, что «плохие» дни не такие уж "
            "и плохие. Появляется виджет на странице «Сегодня»."
        ),
        stage="alpha",
    ),
    Experiment(
        key="time_tracking",
        title="Трекер времени",
        description=(
            "Засекаешь, сколько времени ушло на задачу: жмёшь ▶, потом ⏸. "
            "В детали задачи видно сумму. Полезно, чтобы понять, на что реально "
            "уходит день."
        ),
        stage="alpha",
    ),
    Experiment(
        key="achievements",
        title="Бейджи и достижения",
        description=(
            "Закрываешь задачи — копятся XP, открываются бейджи («10 задач за день», "
            "«неделя без пропусков», «100 закрытых задач», и т. п.). Лёгкая "
            "геймификация без давления — можно вообще не открывать."
        ),
        stage="alpha",
    ),
)


# Convenience predicates for the settings UI: "stable" features go in one
# section, alpha/beta in another. Mirror the order from AVAILABLE.
STABLE_KEYS: tuple[str, ...] = tuple(e.key for e in AVAILABLE if e.stage == "stable")
EXPERIMENTAL_KEYS: tuple[str, ...] = tuple(e.key for e in AVAILABLE if e.stage != "stable")


# Convenience lookup map: key → Experiment.
BY_KEY: dict[str, Experiment] = {e.key: e for e in AVAILABLE}


def is_enabled(user: User, key: str) -> bool:
    """True if `user` has opted into the experiment `key`. Unknown keys → False."""
    if key not in BY_KEY:
        return False
    flags = user.experiments or {}
    return bool(flags.get(key))
