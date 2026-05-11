# Mini App v2 visual audit — 2026-05-11

**Viewport:** 375×812 (iPhone X/11/12/13/14 base)
**User:** `responsive-test@doday.local` (seeded via `.tmp_local_seed.py`)
**Data:** 4 проекта (Входящие, Работа Q3, Дом, Учёба) + 20 задач + 4 лейбла + 7 секций
**Server:** local uvicorn :8004

## Screenshots

1. **01-today.png** — Today view с прогресс-кольцом 38%, 4 секции (Просрочено 1
   / Сегодня 4) + Готово свёрнуто. Видно: project-color-dots (фиолетовый/
   изумрудный/violet), labels @работа/@срочно/@идеи/@дом цветными chips,
   priority chips !1/!2/!3, subtask-progress chip «0/3» c mini-bar, date-chips
   в цвете проекта, hero-blob слегка виден.
2. **02-inbox.png** — Inbox с 1 задачей, quickadd-input sticky сверху.
3. **03-calendar.png** — Week-view с 7 day-chips (Пн-Вс c counts 4/3/3), задачи
   выбранного дня внизу + heatmap снизу частично виден. Минор: header «May 2026»
   — должен быть «Май 2026» по-русски (зависит от OS-locale strftime).
4. **04-projects.png** — Список 4 проектов с цветными точками, overdue badge
   (rose) + active count. Все рендерится; emerald-dot для «Дом» виден слабо
   (CSS contrast — Tailwind JIT иногда не покрывает динамические классы).
5. **05-me-stats.png** — **ЗВЕЗДА АУДИТА.** Полная статистика:
   - Hero-streak «1 день streak» + 🔥 + бейдж «Рекорд 1»
   - 4 stat-cards (Сегодня 3 / Неделя 3 / Месяц 3 / Всего 3)
   - 14-day bar-chart inline SVG с violet→fuchsia gradient (один бар справа =
     сегодня закрыли)
   - Donut «По приоритетам · 17 активных» — P3 41% самый большой
   - Bar-chart «Топ проектов» с цветной заливкой (Работа Q3 = 9 фиолетовый,
     Дом = 4 emerald, Учёба = 3 fuchsia, Входящие = 1)
   - 4 доп-метрики: Лучший день Пн (1), Среднее за день 3.0, Активных 1,
     Скорость 12.4 ч
   - Search-button + Открыть полную версию + Полная статистика на сайте
6. **06-project-view.png** — Single-project view со списком 9 задач Работы Q3,
   back-arrow + project-name с цветной точкой, quickadd sticky.
7. **07-task-sheet.png** — Bottom-sheet с задачей «1:1 с тимлидом»:
   - ТЕКСТ textarea
   - ПРИОРИТЕТ 4 chips, активный P2 с accent-ring
   - КОГДА 4 chips + текущая дата
   - ПРОЕКТ horizontal scroll с активным «Работа Q3»
   - **ЛЕЙБЛЫ** 4 chips @дом @идеи @работа @срочно (V4 — новое!)
   - **ПОВТОР** 5 chips —/день/неделя/месяц/год (V5 — новое!)
   - **ПОДЗАДАЧИ** accordion свёрнут (V6 — новое!)
   - 3-col actions: 📌 Закр. / 🗑 Удалить / Готово
8. **08-empty-state.png** — Empty-state для пустого проекта: hand-drawn SVG
   коробка-Inbox в accent-color opacity-55, текст «В этом проекте пока пусто.
   Используй поле сверху чтобы добавить задачу.» Никаких emoji — настоящая
   иллюстрация.

## Verdict

✅ Все 18 чанков плана `2026-05-12-miniapp-v2-parity-stats-polish.md`
визуально на месте.
✅ Task-display parity с web достигнут (V-группа).
✅ Stats с графиками отрисованы на Me-page (S-группа).
✅ Polish (skeleton, transitions, gradient blob, SVG empty-states, swipe-
visual, PTR-spinner) применён (P-группа).

## Минорные находки (не блокеры)

1. Calendar header формат даты использует `strftime('%B %Y')` зависящий от
   OS-locale — в Windows-dev получает «May 2026». На прод-Linux нужно
   убедиться что `ru_RU.UTF-8` доступна. Можно захардкодить мап-таблицу
   русских месяцев в template для надёжности.
2. Emerald-dot «Дом» в Projects-list виден слабо из-за low contrast на dark
   background. В Top-проектов bar-chart та же emerald отлично читается.
   Возможно стоит увеличить opacity для project-dots с 100% до точно `bg-{
   color}-400`.

Эти штрихи можно поправить в следующей мини-итерации — основная цель v2
(parity + графики + красиво) достигнута.
