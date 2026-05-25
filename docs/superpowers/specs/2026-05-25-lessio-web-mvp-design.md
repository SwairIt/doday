# Lessio Web MVP — Design Spec

**Дата:** 2026-05-25
**Автор:** brainstorming-session между Yaroslav и Doday-Claude
**Статус:** approved, переходит в writing-plans

## Цель

Сделать **независимый от Telegram** веб-сайт-кабинет для соло онлайн-преподавателей, который закрывает recurring pain points: расписание, оплата (постоплата трекается), CRM клиентов, автонапоминания. Telegram-блок в РФ делает web-first критичным; TG-бот остаётся опциональным каналом уведомлений.

Lessio Web живёт **внутри Doday-монорепо** по `app/lessio/*` — расширяет существующие модели + onboarding + лендинг до полноценного MVP.

## Decisions (brainstorming-output)

| # | Вопрос | Решение |
|---|---|---|
| 1 | Целевая аудитория MVP | **Все онлайн-работники** (broad): репетиторы, тренеры, психологи, коучи. UI-термины нейтральные («встреча», «клиент», «услуга») |
| 2 | Платежи | **Постоплата off-platform** — клиент платит вне системы (СБП/перевод), репетитор toggle'ит «оплачено» в CRM. Никакого embedded payments в MVP. |
| 3 | Auth клиентов | **Anon-booking + magic-link на email** — клиент вводит email/телефон/имя без аккаунта, получает email с ссылкой `/lessio/manage/<token>` |
| 4 | Scope MVP | **Расширенный** (~3 недели): booking + CRM + email-уведомления + видеоссылка вписывается репетитором + CSV-экспорт для самозанятых + Google Calendar sync (busy-times) + групповые занятия |
| 5 | Архитектурный подход | **A. Web-first, Telegram-secondary** — основной интерфейс веб-сайт; TG-бот опциональный канал уведомлений когда инфра починена |

## URL-карта и роли

| URL | Кто видит | Что делает |
|---|---|---|
| `/lessio` | публично | лендинг + waitlist (уже есть, не трогаем) |
| `/lessio/auth/login` `/register` | анонимный репетитор | классический email+password (Doday-auth) |
| `/lessio/app/today` | репетитор logged-in | **сегодняшние встречи** (home) |
| `/lessio/app/calendar` | репетитор | **месяц-вид** все встречи |
| `/lessio/app/clients` | репетитор | **CRM** — список клиентов + карточки |
| `/lessio/app/services` | репетитор | CRUD услуг |
| `/lessio/app/schedule` | репетитор | редактор working hours / days / buffer |
| `/lessio/app/income` | репетитор | доходы + CSV-экспорт |
| `/lessio/app/settings` | репетитор | профиль, slug, видеоссылка-шаблон, GC-sync |
| `/lessio/app/setup-profile` | репетитор без `LessioTutorProfile` | one-time onboarding после register |
| **`/u/<slug>`** | публично (anon-клиент) | **публичная страница репетитора** + booking |
| `/u/<slug>/book/<service_id>` | анон-клиент | выбор слота → email/телефон/имя → confirm |
| `/lessio/manage/<token>` | анон-клиент по magic-link | управление своими записями (отмена/перенос) |
| `POST /api/lessio/cron/dispatch-reminders` | cron-only (X-Cron-Token) | отправить за-24ч и за-1ч email-напоминания |
| `GET /api/lessio/oauth/google/callback` | OAuth | сохранить GC refresh-token в `LessioTutorProfile` |

Существующие Telegram-onboard endpoints (`/lessio/miniapp/cabinet`, `/lessio/miniapp/onboard`) остаются — это **опциональный** путь регистрации для тех у кого есть TG.

## Модели данных — diff к существующим

### `LessioClient` — расширяется под web-anon
**Текущее:** `telegram_user_id` NOT NULL UNIQUE per-tutor; `telegram_first_name/username` опционально.

**Изменения:**
- `telegram_user_id` → nullable (для web-only клиентов)
- + `email: String(255) NOT NULL`
- + `phone: String(50) nullable`
- + `full_name: String(120) NOT NULL`
- UNIQUE constraint `(tutor_id, email)` — клиент уникален per-tutor по email
- existing UNIQUE `(tutor_id, telegram_user_id)` остаётся как partial unique WHERE telegram_user_id IS NOT NULL

### `LessioBooking` — расширяется под web-flow
**Добавляется:**
- `manage_token: String(64) UNIQUE` — secret для magic-link `/lessio/manage/<token>` (32 bytes hex)
- `meeting_url: String(500) nullable` — берётся из `LessioService.meeting_url_template` при create, override per-booking
- `payment_status: String(20) NOT NULL default 'unpaid'` — `unpaid`/`paid`/`refunded` (отдельно от `status` встречи)
- `paid_at: DateTime nullable` — когда репетитор отметил оплату
- **Группы**: для групповых занятий создаются N отдельных `LessioBooking` записей с одинаковым `starts_at`. UNIQUE constraint `(tutor_id, starts_at)` меняется на **partial unique** `(tutor_id, starts_at) WHERE service.is_group_session=false`. Так в CRM видны все участники group session-а, и каждый получает свой manage_token.
- `attendee_count` поле НЕ добавляется (заменено N-record-подходом выше)
- `reminder_24h_sent_at: DateTime nullable`
- `reminder_1h_sent_at: DateTime nullable`
- `client_email: String(255) NOT NULL` — denorm copy от LessioClient.email для быстрого list-view + чтобы напоминания шли даже если клиент потёрт
- `client_full_name: String(120) NOT NULL` — denorm

### `LessioService` — расширяется
**Добавляется:**
- `meeting_url_template: String(500) nullable` — Zoom/Meet/Jitsi default
- `is_group_session: Boolean NOT NULL default false`
- `max_attendees: Integer NOT NULL default 1`
- `location: String(500) nullable` — для offline (адрес или «онлайн»)

### `LessioTutorProfile` — расширяется
**Добавляется:**
- `default_meeting_url_template: String(500) nullable` — fallback для services без явной ссылки
- `notification_email: String(255) nullable` — куда слать уведомления о новых записях (default = `User.email`)
- `google_calendar_refresh_token: String(500) nullable` — encrypted via Fernet, для GC busy-times sync

### `User` (Doday-shared) — НЕ трогаем
Lessio-юзеры регистрируются стандартным `auth/register`. После register middleware смотрит `LessioTutorProfile`; если нет — редирект на `/lessio/app/setup-profile`.

### Миграция 0042
Alter существующих lessio_* таблиц + добавление новых nullable колонок. Backward-compatible. Один файл.

## Ключевые flows

### F1. Onboarding репетитора
```
/lessio (landing) → CTA «Стать репетитором» →
/lessio/auth/register (email+password, Doday-стандарт) →
/lessio/app/setup-profile (форма: slug + display_name + niche + bio + опц. 2-3 шаблона услуг) →
POST → create_tutor_profile + bulk create_services_from_template →
/lessio/app/today (пустой state с CTA «добавить слот / поделиться публичной страницей»)
```

### F2. Booking клиентом (anon)
```
/u/<slug> (публичная страница: услуги cards + календарь под выбранной услугой) →
выбор услуги → выбор слота из free_slots →
форма (email + телефон + имя + комментарий) →
POST /u/<slug>/book/<service_id> →
  - find/create LessioClient (per-tutor by email). Если client уже существует — UPDATE full_name/phone до свежих значений (last-write-wins), notes не трогаем
  - INSERT LessioBooking (status=confirmed, payment_status=unpaid, manage_token=secrets.token_urlsafe(48))
  - send_email(client, "✅ Вы записаны", magic-link manage_url, meeting_url)
  - send_email(tutor.notification_email, "Новая запись от {full_name}", admin_link)
→ страница «✅ Записано, проверь почту»
```

### F3. Управление клиентом (magic-link)
```
GET /lessio/manage/<token> → fetch LessioBooking by manage_token →
  показать список всех своих будущих записей у ЭТОГО репетитора
  (group by tutor — клиент видит только встречи которые он подтвердил, разные репетиторы = разные tokens)
кнопки:
  [Перенести] → /manage/<token>/reschedule → форма выбора нового слота → POST
  [Отменить] → /manage/<token>/cancel → POST (confirm dialog)
Без auth — token самодостаточен (UNIQUE 64-char secret, brute-force impractical)
```

### F4. Уведомления (cron-driven + event-driven)
**Cron** (`POST /api/lessio/cron/dispatch-reminders` каждые 5 мин, X-Cron-Token header):
- SELECT bookings WHERE status='confirmed' AND starts_at BETWEEN now()+55min AND now()+65min AND reminder_1h_sent_at IS NULL
  → `asyncio.gather(send_email_to_client for booking in batch)` + UPDATE reminder_1h_sent_at=now() в одной транзакции
- То же для now()+23h..25h окна и reminder_24h_sent_at
- SMTP-ошибка одного email не должна блокировать остальные — каждый `send_email` обёрнут в `try/except`, лог + продолжение. UPDATE `reminder_*_sent_at=now()` ставится только при success.

**Event-driven** (синхронно в request handler):
- Новая запись → email клиенту + tutor.notification_email
- Отмена клиентом → email репетитору
- Перенос клиентом → email репетитору
- Перенос/отмена репетитором из cabinet → email клиенту

### F5. Постоплата tracking
В карточке клиента + календаре репетитора каждая встреча имеет toggle «Оплачено / Не оплачено». Тап → POST `/lessio/app/bookings/<id>/toggle-paid` → UPDATE payment_status + paid_at. Используется в `/lessio/app/income` для CSV-экспорта.

### F6. Google Calendar sync (опциональный)
```
/lessio/app/settings → [Подключить Google Calendar] → OAuth redirect →
GET /api/lessio/oauth/google/callback?code=… →
  обмен code на access_token + refresh_token (Google's /oauth2/v4/token) →
  save refresh_token (Fernet-encrypted via app_secret_key) в LessioTutorProfile.google_calendar_refresh_token
При вычислении free_slots в /u/<slug>:
  если tutor.google_calendar_refresh_token не пустой:
    GET https://www.googleapis.com/calendar/v3/calendars/primary/events
      ?timeMin=...&timeMax=...&singleEvents=true
    busy_times = events.map(e => (e.start, e.end))
    вычитаем busy_times из computed free slots
В MVP — read-only (busy-times). Write-back (наши booking появляются в GC) — Phase 2.
```

## Внешние интеграции

| Интеграция | Где | Состояние |
|---|---|---|
| **SMTP** | email-уведомления | уже настроено в Doday (`app.auth.email`) |
| **Google Calendar API** | busy-times sync | новое; OAuth client-id/secret в `.env`, `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` |
| **Cron-poll** | dispatch-reminders | уже есть в Doday (cron-poll deploy + X-Cron-Token), просто новый endpoint |
| **Fernet** | encrypt GC refresh_token | новое; ключ derive'ится из `app_secret_key` через PBKDF2 |
| **Telegram бот** | опциональный уведомительный канал | Phase 2 (не критично для MVP) |

## UI-структура (frontend pages)

Стек как в остальном Doday: Jinja2 + HTMX + Tailwind CDN. Без React, без build-step.

**Публичная сторона:**
- `templates/lessio/u/profile.html` — `/u/<slug>` страница репетитора
- `templates/lessio/u/book.html` — `/u/<slug>/book/<service_id>` step-by-step (слот → форма)
- `templates/lessio/u/booked.html` — success-страница после booking
- `templates/lessio/manage/index.html` — `/lessio/manage/<token>` управление записями

**Кабинет:**
- `templates/lessio/app/_base.html` — shell с sidebar (Today / Calendar / Clients / Services / Schedule / Income / Settings)
- `templates/lessio/app/today.html`
- `templates/lessio/app/calendar.html` — простой grid month-view с цветными слотами
- `templates/lessio/app/clients.html` + `client_detail.html`
- `templates/lessio/app/services.html` + service-edit modal
- `templates/lessio/app/schedule.html` — working hours editor
- `templates/lessio/app/income.html` — sum-by-month + CSV-download кнопка
- `templates/lessio/app/settings.html`
- `templates/lessio/app/setup_profile.html` — one-time onboarding form

**Email-шаблоны** (`templates/lessio/email/`):
- `booking_confirmed.html` (клиенту)
- `new_booking.html` (репетитору)
- `reminder_24h.html` (клиенту)
- `reminder_1h.html` (клиенту)
- `cancelled_by_client.html` (репетитору)
- `cancelled_by_tutor.html` (клиенту)

## Service-layer expansion

`app/lessio/service.py` — добавляются:
- `register_tutor(session, *, email, password) -> User` — wrapper над `auth.service.register_user` + flag для Lessio-flow
- `create_services_from_template(session, tutor, template_id) -> list[LessioService]` — bulk-create из template-pack (English / Math / Fitness)
- `find_free_slots(session, tutor, *, date_from, date_to, service) -> list[datetime]` — реальная имплементация (working_days + work_hours + buffer + existing bookings + optional GC busy-times)
- `create_booking(session, *, tutor, service, slot, client_email, client_phone, client_full_name) -> LessioBooking` — find/create LessioClient + INSERT booking + generate manage_token
- `reschedule_booking(session, booking, *, new_slot)` / `cancel_booking(session, booking, *, by_client_or_tutor)`
- `toggle_payment(session, booking) -> LessioBooking` — flip payment_status
- `export_income_csv(session, tutor, *, year, month) -> str` — CSV для «Моего налога»
- `fetch_google_busy_times(tutor, *, date_from, date_to) -> list[tuple[datetime, datetime]]` — wrapper над Google Calendar API

## Cron + jobs

В существующий `app.telegram.bot._run_both` JobQueue (или новый `app.lessio.jobs`) добавляется:
- ` /api/lessio/cron/dispatch-reminders` — каждые 5 мин (cron-poll endpoint, X-Cron-Token)
- (опционально) daily 06:00 UTC — email-дайджест репетитору «Сегодня у тебя N встреч» (Phase 2)

## Тесты — что покрывается в MVP

| Что | Файл | Кол-во |
|---|---|---|
| Register tutor → setup-profile flow | `test_lessio_register_tutor.py` | 4 |
| Public profile `/u/<slug>` render | `test_lessio_public_profile.py` | 3 |
| Booking flow (anon) | `test_lessio_booking_flow.py` | 6 |
| Manage по magic-link | `test_lessio_manage_token.py` | 5 |
| find_free_slots алгоритм | `test_lessio_free_slots.py` | 8 (граничные случаи) |
| Reminders cron | `test_lessio_reminders.py` | 4 |
| CSV-экспорт income | `test_lessio_income_csv.py` | 3 |
| Toggle-payment | `test_lessio_payment_toggle.py` | 2 |
| GC busy-times (mocked HTTP) | `test_lessio_google_calendar.py` | 3 |

Существующие `test_lessio_*` tests остаются зелёными.

## Out of scope (Phase 2+)

- Embedded payments (ЮKassa, Stars-checkout) — у репетитора должно быть юр-лицо
- Аккаунт клиента (полноценный) — пока anon+magic-link достаточно
- Двусторонний GC sync (push booking в GC репетитора) — read-only в MVP
- Telegram-бот как primary канал — он опциональный
- Mobile native app — PWA сойдёт
- Multi-language UI — только RU в MVP
- Доход в нескольких валютах — только RUB
- AI-фичи (smart scheduling, auto-reply) — never (см. memory feedback)
- Маркетплейс (поиск репетитора по нише) — Phase 3, требует scale

## Roadmap timeline

| Неделя | Что |
|---|---|
| Wk 1 | Migration 0042 + service.py expansion + find_free_slots + register/setup-profile + публичная `/u/<slug>` |
| Wk 2 | Booking-flow (book → email → manage-token) + email-шаблоны + reminders cron |
| Wk 3 | Кабинет (Today/Calendar/Clients/Services/Schedule/Income/Settings) + CSV-экспорт + GC OAuth |

## Что меняется vs текущий код (`app/lessio/*` от 92eba3e)

- `LessioClient` model + migration — большой alter
- `LessioBooking`, `LessioService`, `LessioTutorProfile` — добавление полей
- `service.py` — переписываем `auto_onboard_tutor` чтобы поддержать **web-register** path (Telegram-onboard остаётся как одна из ветвей)
- `router.py` — добавляется ~15 новых endpoint'ов
- 12+ новых Jinja-templates
- ~30 новых тестов
- Существующие 39 lessio-тестов остаются зелёными
