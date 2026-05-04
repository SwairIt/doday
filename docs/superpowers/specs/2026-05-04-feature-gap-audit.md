# Feature gap audit для Doday

**Дата:** 2026-05-04
**Подход:** работаем по списку общих паттернов todo-приложений (моё общее знание индустрии). Не копируем фичи конкретного приложения. Помечаем что есть ✓, чего нет ✗, и что добавим в этом заходе.

## Базовые задачи и проекты

| Фича | Статус | Комментарий |
|---|---|---|
| Создать / удалить / завершить задачу | ✓ | |
| Описание задачи | ✓ | inline edit + detail panel |
| Дата срока (день и время) | ✓ | due_at + due_date_only |
| Приоритеты P1–P4 | ✓ | rose/amber/sky/slate цвета |
| Подзадачи | ✓ | глубина не ограничена |
| Лейблы с цветами | ✓ | popover на строке + страница /labels |
| Проекты с цветами | ✓ | + описание + избранное + архив |
| Секции внутри проекта | ✓ | rename + drag-reorder |
| Inbox как дефолтный проект | ✓ | |
| Повторяющиеся задачи | ✓ | daily/weekly/monthly/yearly |
| Завершение спавнит следующую копию | ✓ | в complete_task() |
| Drag-reorder задач | ✓ | внутри проекта/секции |
| Drag-reorder проектов | ✓ | в сайдбаре |
| Drag-reorder секций | ✓ | в kanban + list view |
| Дублировать проект | ✓ | duplicate_project клонирует всё |
| Дублировать одну задачу | ✗ | **build** — endpoint + кнопка в detail |
| Markdown в описании | ✗ | **build** — клиентский render через regex |
| Назначение задачи человеку | ✗ | требует collaboration |
| Прикрепить файл | ✗ | требует storage |

## Ввод и парсинг

| Фича | Статус |
|---|---|
| Quick-add с естественным языком | ✓ |
| Парсинг даты словами (сегодня/завтра/пн/«15 декабря») | ✓ |
| «через N дней/неделю/месяц» | ✓ |
| «след пн» | ✓ |
| Приоритет восклицательными | ✓ |
| Лейбл `@` и проект `#` | ✓ |
| Голосовой ввод | ✗ | Web Speech API; пропускаем — слабая кросс-браузерность |

## Виды

| Фича | Статус |
|---|---|
| Today (просрочка + сегодня) | ✓ |
| Inbox | ✓ |
| Upcoming (7 дней с drag-to-reschedule) | ✓ |
| Календарь — месячный | ✓ |
| Календарь — недельный/дневной | ✗ | **build (week, потом day)** |
| Канбан-доска | ✓ |
| Завершённые (история) | ✓ |
| Активность (лента событий) | ✓ |
| Statistics (streaks, графики) | ✓ |
| Лейблы — отдельная страница | ✓ |
| Архив проектов | ✓ |
| Кастомные фильтры | ✓ |
| Focus mode (только текущий список) | ✗ | **build** — toggle через `f` |

## Поиск и навигация

| Фича | Статус |
|---|---|
| Глобальный поиск | ✓ | через `/` шорткат |
| Сохранить результат поиска как фильтр | ✗ | можно через /app/filters новый, но без drop-in |
| Горячие клавиши + overlay | ✓ |
| Мобильный bottom-nav | ✓ |
| Sidebar drag-reorder проектов | ✓ |
| Счётчики задач в сайдбаре | ✓ |
| Браузерные уведомления | ✓ | client-side polling |
| Email-напоминания | ✗ | требует фоновый scheduler |
| Tab title badge с кол-вом | ✗ | **build** — пишет `(N) Doday` |

## Коллаборация

| Фича | Статус |
|---|---|
| Общие проекты | ✗ | требует project_membership модели |
| Назначение | ✗ | то же |
| Mentions в комментах | ✗ | то же |
| Activity feed по команде | ✗ | то же |

(Команда — отдельный большой кусок, в этом заходе не трогаю.)

## Импорт-экспорт-интеграции

| Фича | Статус |
|---|---|
| JSON-бэкап аккаунта | ✓ |
| Markdown-экспорт проекта | ✓ |
| iCalendar (.ics) экспорт | ✓ |
| Подписка iCal по URL | ✗ | требует токены, пропускаем |
| Email-to-task (мейлбокс → задача) | ✗ | infra |
| Sync с Google Calendar | ✗ | OAuth |

## UX / визуальный полиш

| Фича | Статус |
|---|---|
| Тёмная и светлая темы | ✓ | toggle в topbar |
| Auto тема по prefers-color-scheme | ✗ | **build** — System/Light/Dark переключатель |
| Bulk actions | ✓ | 7 типов |
| Inline edit (priority/date/recurrence) | ✓ |
| Pomodoro per task | ✓ |
| Дневная цель | ✓ |
| Недельная цель | ✗ | **build** — расширение карточки на today |
| Confetti на завершении цели | ✗ | **build** — pure CSS canvas |
| Skeleton loading | ✗ | малоценно для server-render |
| Touch gestures на mobile | ✗ | низкий приоритет |
| Welcome onboarding | ✓ | dismissible card на /today |
| Templates | ✓ | 8 встроенных + user-saved |
| Drag-reschedule на upcoming | ✓ |
| Drag-reschedule на calendar | ✓ |

## Аккаунт

| Фича | Статус |
|---|---|
| Регистрация по email | ✓ |
| Подтверждение по email | ✓ |
| Logout | ✓ (был только в /profile, теперь видимый в sidebar) |
| Сброс пароля | ✗ | заглушка-ссылка существует, без бэкенда |
| Тарифы Free/Pro/Team | ✓ |
| 14-дневный trial | ✓ |
| Удаление аккаунта | ✓ | в /profile danger zone |
| Show/hide пароля | ✓ |
| Strength meter | ✓ |
| Caps Lock detector | ✓ |

## Что добавляю в этом заходе (приоритет)

1. ✅ Logout в sidebar + landing с ?preview=1 для залогиненных (сделано выше)
2. **Browser tab title badge** — `(N) Doday` если есть задачи на сегодня
3. **Auto-тема** + триггер System в profile
4. **Дублирование задачи**
5. **Markdown в описании** (h1/h2/жирный/курсив/ссылки/код, простым regex)
6. **Focus mode** — `f` тоггл, скрывает sidebar+topbar
7. **Недельная цель**
8. **Move-to-section dropdown** в task detail panel
9. **Confetti** при завершении дневной цели
10. **Quick-task duplicate** в bulk-bar

## Прогресс

- [x] 1. Logout + landing preview
- [x] 2. Tab badge
- [x] 3. Auto theme + System (cycle в topbar)
- [x] 4. Task duplicate (одна с подзадачами рекурсивно)
- [x] 5. Markdown rendering (regex, без либ — h1-h3/bold/italic/code/links/lists)
- [x] 6. Focus mode (`f` toggle + exit-pill)
- [x] 7. Weekly goal (вторая полоска под дневной)
- [x] 8. Move-to-section dropdown в task detail
- [x] 9. Confetti (CSS+JS на первом достижении дневной цели)
- [/] 10. Bulk duplicate — отложено (на удивление редко нужно после single-duplicate)

Всего по этому заходу: 5 коммитов, +13 тестов (4 duplicate + 9 polish).
