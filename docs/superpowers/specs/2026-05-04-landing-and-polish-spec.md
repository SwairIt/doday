# Лендинг + полишинг сайта Doday — план работ

**Дата:** 2026-05-04
**Запрос:** длинный лендинг с описанием функций и тарифами, help-центр со статьями, переработка auth-страниц, общий полиш UI, аудиты perf/security/a11y/mobile.

## Принципы

- Все маркетинговые тексты — мои собственные на русском, не копирую копирайт ни одного конкретного приложения.
- Дизайн — фиолетовый стиль Doday, существующая палитра (`grad-bg`, `--accent`, `--surface`).
- Анимации — CSS keyframes + Alpine `x-intersect` (без новых внешних зависимостей).
- Каждый батч = отдельный коммит с тестами.

## Батчи

### B. Тарифы (модель + API)

- Миграция 0009: добавить колонки `users.tier` (enum: `free`/`pro`/`team`), `users.trial_ends_at`.
- Дефолт при регистрации: `tier=free`, `trial_ends_at = now + 14 дней` (Pro-фичи доступны на trial).
- Сервис `app/billing/service.py`:
  - `current_effective_tier(user)` → возвращает фактический уровень с учётом активного trial.
  - `tier_limits(tier)` → структура лимитов.
- Жёсткое ограничение: только `max_active_projects` для Free после окончания trial. Остальные «pro»-фичи декларируются в маркетинге, не enforce-ятся.
- Endpoint `GET /api/billing/me` возвращает `{tier, effective_tier, trial_ends_at, limits}`.
- В UI шапки профиля — бейдж тарифа.

**Тарифные планы (для лендинга):**
| Free (после trial) | Pro · 199₽/мес | Team · 499₽/мес |
|---|---|---|
| 5 активных проектов | ∞ проектов | ∞ проектов |
| Inbox / Сегодня / Календарь | + Канбан / Активность | + всё из Pro |
| 3 встроенных шаблона | Все шаблоны + свои | + общие шаблоны команды |
| Базовые лейблы | Кастомные фильтры | + общие фильтры |
| Pomodoro per task | Уведомления | + email-напоминания |
| Markdown export | + iCal export | + командный календарь |
| 1 устройство активно | До 10 | Безлимит |

(Team tier — заглушка для маркетинга, реальной collaboration пока нет.)

### C. Лендинг /

Замена текущей `landing.html` на длинную страницу с секциями:
1. **Hero** — большой заголовок, sub-копи, две CTA (Попробовать бесплатно / Войти), animated gradient.
2. **Features grid** — 9 карточек по реально шипнутым возможностям.
3. **Showcase** — 3 псевдо-скриншота (HTML mock-ups) с подписями.
4. **Stats** — три цифры (X тестов, Y фич, Z строк кода — реальные метрики).
5. **Pricing** — 3 карточки с тарифами, отметкой «текущий» если залогинен.
6. **FAQ** — 8 вопросов с раскрывающимися ответами (Alpine).
7. **CTA-block** — повторная регистрация-кнопка.
8. **Footer** — ссылки на /help, /privacy (заглушка), GitHub.

Все секции в `x-intersect.once` для fade-in.

### D. Help-центр /help

Структура:
- `/help` — главная со списком статей.
- `/help/{slug}` — отдельная статья.
- Левый сайдбар с навигацией по статьям (на md+).
- Mobile: toc сверху + контент.

Статьи:
1. С чего начать — Inbox и первые задачи.
2. Quick-add: парсер дат, приоритеты, лейблы, проекты.
3. Проекты, секции, шаблоны.
4. Канбан и список — когда что использовать.
5. Лейблы и кастомные фильтры.
6. Календарь и Upcoming с drag-to-reschedule.
7. Подзадачи, комментарии, повтор.
8. Pomodoro и дневная цель.
9. Импорт/экспорт (JSON, Markdown, iCal).
10. Горячие клавиши (вытащить overlay в статью).

Контент — мой собственный, на русском, с примерами кода и скриншотами (HTML-моки).

### E. Auth страницы

Перерисовка `/login` и `/register`:
- Двухколоночный layout: слева форма, справа большой animated gradient + цитата/преимущества.
- Mobile: однокололоночный.
- Поле password: глаз для show/hide, индикатор Caps Lock, strength meter (zxcvbn-like, простой regex-based).
- Поле email: live-валидация + indicator зелёным при валидном.
- Анимированные поля (label-float).
- Confetti при успешной регистрации (CSS-only).
- "Забыли пароль?" — заглушка-ссылка.

### F. Общий полиш

- Audit `app/templates/base.html` CSS — выровнять все `btn-*` классы.
- Hover-эффекты на всех `<button>` с консистентным timing.
- Page-transitions через Alpine `x-transition` на главных контейнерах.
- Replace inline-style transitions на классы.

### G. Performance

- Проверить все списки на N+1 (особенно activity-feed, project-counts).
- Добавить недостающие индексы.
- Использовать `selectinload` для связанных таблиц.

### H. Security

- Rate-limit на /auth/login и /auth/register (5 попыток/мин per IP).
- Verify session cookie flags (httpOnly, secure в prod, sameSite=lax).
- Audit input validation (email, длины строк).
- CSRF: убедиться что есть Origin/Referer check на mutating endpoints (или session cookie достаточно).

### I. Accessibility

- aria-label на иконочные кнопки.
- alt-text на изображения.
- Контраст текста vs фон (тёмная тема — проверить).
- Keyboard nav: Tab order, focus styles.

### J. Mobile

- Все экраны на 375px viewport.
- Sidebar drawer проверить.
- Bulk-bar — wrap.
- Task detail panel — full-screen.

## Прогресс

- [x] A. Spec
- [ ] B. Tariffs
- [ ] C. Landing
- [ ] D. Help center
- [ ] E. Auth polish
- [ ] F. UI polish
- [ ] G. Performance
- [ ] H. Security
- [ ] I. Accessibility
- [ ] J. Mobile

Каждый завершённый батч → апдейт этого файла + commit.
