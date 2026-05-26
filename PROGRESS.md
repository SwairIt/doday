# Doday — Progress tracker

**Purpose:** session-spanning progress tracker. Read this first in every session/iteration.

---

## 2026-05-26 (continued) — 4 фичи которых хотелось сделать (ce1c391)

Юзер: «еще что нибудь сделай, чтобы ты хотел чтобы было». Full autonomy.

**F1. Onboarding-чеклист на «Сегодня»:**
- 5 шагов: bio (≥50 символов) · услуги · расписание · email · первая запись
- Прогресс-бар компактный (1.5px), expandable список с прямыми ссылками
- Скрывается полностью когда complete=True
- Авто-open при 0-2 готовых, свёрнут при 3+

**F2. Reading-progress bar + Share-buttons в blog:**
- Sticky-bar сверху страницы статьи, fill = % прокрутки документа
- Share: Telegram / VK / X / WhatsApp / copy-link с toast «Скопировано»
- Над related-секцией статьи

**F3. Atom-feed /lessio/blog/feed.xml:**
- 18 entries, валидный Atom 1.0
- application/atom+xml; charset=utf-8
- `<link rel="alternate" type="application/atom+xml">` в head всех marketing-страниц
- RSS-ридеры и SearchEngines auto-discover'ят его

**F4. Custom Lessio 404 page:**
- `/lessio/*` и `/u/*` рендерят `lessio/404.html` (брендированный)
- Doday-paths сохраняют свой 404
- Hero (404 + 🌌) + search-input по blog + 6 popular-destination chips
- meta robots noindex,follow

**Прод:** SHA ce1c391, **26/26 тестов зелёные** (5 today + 15 blog + 6 404).

---

## 2026-05-26 (latest) — Lessio Blog + cabinet UX (audit-driven)

Юзер: «а сео ты сделал максимально статей не как пользоваться, а допустим сравнение
с конкурентами, что это и тп. чтобы в инете находилось. И давай прочекай весь
lessio и потом реализуй чего не хватает до прод».

**Audit findings:**
- ✓ SEO basics готовы (canonical/OG/JSON-LD везде)
- ✓ Sitemap 35 URLs, robots ok
- ✗ Top-of-funnel контент отсутствовал — только product docs в help-center
- ✗ /lessio/blog не существовал

**Cabinet UX (предыдущий feedback от юзера):**
- `68ca985` — Помощь+Моя страница в sidebar, max-w-6xl mx-auto, mobile hamburger drawer
- `1b46126` — Floating Help-bubble справа-снизу с live-поиском по articles.json

**Blog implementation:**
- `e6c39c2` — Lessio blog backend + 18 long-form статей (~80 KB)
  - Сравнения (8): Calendly/Profi.ru/YClients/Skillbox/Zoom-Jitsi-Meet/Stars-ЮKassa-СБП/SimplyBook-Setmore/GetCourse-Skillbox vs Lessio
  - Гайды (6): как стать репетитором английского/найти клиентов/назначить цену/сколько зарабатывают/стать психологом/принимать оплату
  - Объяснения (4): что такое Telegram Stars/booking-сервис/онлайн-коуч/самозанятость
  - JSON-LD BlogPosting + BreadcrumbList + Blog (CollectionPage)
  - 12 тестов

- `ed55e8b` — cross-links: blog в /lessio landing footer + marketing-header +
  cabinet sidebar (+_base_marketing footer)

**Прод-статус:** SHA ed55e8b, **54 lessio-URL в sitemap**:
- 2 главные + 5 SEO-niche + 28 help + 18 blog + 1 demo-tutor

JSON-LD типы покрыты: SoftwareApplication, Organization, Service, FAQPage,
Article, BlogPosting, Blog (CollectionPage), BreadcrumbList, HowTo,
BusinessAudience, Person, AggregateRating, Review.

Структура SEO-контента под основные intent-ступени:
- Top-of-funnel (информационный intent): explainers «что такое X»
- Mid-funnel (commercial intent): сравнения «X vs Y»
- Bottom-funnel (transactional): niche-landings + help-center

---

## 2026-05-26 (late) — Lessio Help Center + 5 SEO landings (5 chunks)

Юзер: «Продумай еще улучшения, сделай дофига seo, помощь (так же как с doday, помощь можно открыть и там дофигище статей как пользоваться и можно еще найти по поисковику)». Полная автономия.

**N1 (14a6431) — Backend каркас:**
- `app/lessio/help/articles.py` — TypedDict с 8 категориями (Начало/Профиль/Услуги/Расписание/Оплата/Клиенты/Интеграции/Продвинутое)
- `app/lessio/help/router.py` — /lessio/help + /lessio/help/{slug} + ?q=search + articles.json
- search_articles: scoring title(10) > keywords(8) > summary(5) > body(1)
- `app/lessio/seo_pages.py` — 5 niche-landings (заглушки meta)
- Sitemap: +28 help + 5 niche, priority-tiers (1.0/0.8/0.6)
- 10/10 тестов

**N2 (6d56959) — Шаблоны:**
- `_base_marketing.html` — публичный layout с header+footer, OG/Twitter cards, .prose-lessio CSS для статей
- help/index.html — hero + search + категорийный grid + empty/results states + CTA-card
- help/article.html — sticky sidebar nav + breadcrumbs + prose + related + CTA-card
- JSON-LD Article + BreadcrumbList на каждой странице

**N3 (c8d1ea6) — Контент 28 статей (1225 строк HTML):**
Полноценный контент с конкретными примерами: CSV-формат, RFC5545, OAuth-flow, DST,
Stars-курс, кросс-ссылки между статьями. Темы — от quick-start и payments-stars
до advanced-настроек (vacation, lead-time, GCal-sync, ical-feed, pwa-install, SEO).

**N4 (83ba7b0) — SEO landings контент (875 строк):**
- /lessio/dlya-repetitorov — JSON-LD Service+FAQPage, 4 предметные ниши, 6 FAQ
- /lessio/dlya-trenerov — 4 дисциплины (йога/фитнес/единоборства/бег)
- /lessio/dlya-psihologov — упор на конфиденциальность, 4 практики
- /lessio/alternativa-calendly — comparison-table 13 параметров, 5-step migration guide
- /lessio/oplata-cherez-telegram — JSON-LD HowTo, сравнительная таблица Stars vs ЮKassa
+3 теста (13/13 зелёные)

**N5 (56d7d42) — Final polish:**
- /lessio landing: JSON-LD SoftwareApplication + Organization
- 4-card cross-link секция → 4 niche-landings (Browse-More)
- 4-col footer с 12 внутренними ссылками
- robots.txt: явный Allow для всех публичных Lessio-страниц
+2 теста (15/15 зелёные, 203 lessio total)

**Прод-статус:** SHA 56d7d42, **35 lessio-URL в sitemap**:
- 2 главные (`/lessio`, `/lessio/help`)
- 5 SEO niche-landings
- 28 help-articles
- + индексированы публичные tutor-страницы /u/<slug>

Все JSON-LD типы: SoftwareApplication, Organization, Service, FAQPage, Article,
BreadcrumbList, CollectionPage, HowTo, BusinessAudience.

---

## 2026-05-26 — @LessioBot максимальная доработка (из Lessio-archive сессии)

Юзер передал bot-setup из архивной Lessio-сессии (`c:\www-Yaroslav\Lessio`,
master `1630fc3`). Lessio-Claude в этой сессии работал **только над ботом**;
web-side остаётся за Doday-Claude — не пересекается.

**Коммит e0a5dc4** — bot expansion (3 файла, +342/-58):
- `app/config.py`: `admin_telegram_user_id: int | None = None`
- `app/lessio/telegram_handlers.py` полностью переписан:
  - 6 commands: `/start`, `/menu`, `/help`, `/about`, `/privacy`, `/feedback`
  - `lessio_post_init()` — idempotent setMyCommands ru+en + set_my_short_description
    + set_my_description + set_chat_menu_button (WebApp `/lessio`). Все вызовы
    в try/except BadRequest — Telegram-сторонние ошибки («not modified» и др.)
    не валят worker.
  - Deeplink `lessio_<slug>` в `cmd_start` — открывает `/u/<slug>` через
    WebAppInfo (booking page).
  - `/feedback` через `context.user_data` flag + MessageHandler ChatType.PRIVATE.
  - Welcome обновлён под real-product (убрал «валидационная фаза, собираю
    waitlist» — лендинг уже переписан под real-product в `ac92a83`).
- `app/telegram/bot.py` `build_lessio_app`: заменён inline `_post_init` на
  импорт `lessio_post_init`, -40 строк дублирования.

**Коммит <NEXT> — добавки**:
- `app/telegram/bot.py`: маунт `PreCheckoutQueryHandler(on_pre_checkout_query)`
  + `MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment)` на
  Lessio Application. Без этого `tutor_pro_*` invoice выписан через
  `lessio_bot_token` молча падал — handlers были только на @DodayTaskBot.
- `app/lessio/telegram_handlers.py` `on_feedback_message`: friendly fallback
  с WebApp-кнопкой когда юзер написал текст вне feedback-mode (раньше
  silent return — выглядело как сломанный бот).
- `app/static/lessio/logo.svg`: brand-mark «L» на gradient (4F6EF7→7B5CFF)
  rounded-square для BotFather `/setuserpic`. SVG в репо чтобы конвертить в
  PNG 512×512 (cloudconvert.com) и загрузить руками.

**ruff + mypy --strict зелёные** на изменённых файлах. Tests не запускал
(нет local DB-creds для Doday).

**Что осталось руками (BotFather)**: `/setname`→`Lessio`, `/setuserpic` (PNG
из logo.svg). Description/commands/menu сами обновятся через `lessio_post_init`
на следующем рестарте bot worker'а.

**Что НЕ сделано (deferred)**: на проде Telegram API недоступен напрямую (см.
[[feedback_telegram_api_infra_debt]]). Установить `telegram_proxy_url` в `.env`
прежде чем рестартовать worker — иначе `lessio_post_init` залогирует warning'и
(но не упадёт), а handlers не будут получать updates.

---

## 2026-05-26 — Lessio UI maximum polish: 7 chunk'ов кабинета подряд

Юзер: «Максимально доработай интерфейс, чтобы было все понятно красиво и удобно. А так же автоматизированно.» Продолжение ночной сессии после context-compact.

**N1 — Toast система + Today (425a2d6):**
- _base.html: глобальный Alpine toast с auto-dismiss 4s, URL-strip (saved/paid/imported/gcal/…)
- today.html: hero «следующая встреча в X», карточки с mailto-link + inline notes + per-booking mark-paid + open-meeting кнопки, empty-state с copy-link button

**N2 — Clients (7da7d77):**
- Search-bar с magnifier (q-param, ILIKE по name/email/phone)
- Per-client aggregates: bookings_count + paid_rub + last_contact одним GROUP BY-запросом
- Карточки с gradient-avatar (initial), badge'и stats, not-found state на пустой поиск
- client_detail.html: 4-card stats grid (total/completed/upcoming/avg)

**N3 — Settings tabs (54a2cc9):**
- Alpine-tab nav: Профиль · Встречи · Уведомления · Интеграции
- URL `#hash` persist для F5-stability
- Sticky save-кнопка снизу (скрыта на Integrations)
- GCal OAuth + iCal-URL вынесены в Integrations; info-карточка про auto-emails

**N4 — Calendar week+day view (f7a54d7):**
- Toggle Месяц/Неделя/День в header'е
- Week: 7-col × hourly grid, scroll-x на mobile, клик header → Day-view
- Day: вертикальный hourly strip с полными карточками встреч (цена+статус+duration)
- Часы берутся из work_start/end профиля (fallback 8–22)
- Back-compat: ?month=YYYY-MM продолжает работать

**N5 — Stats charts (5cf07dc):**
- Chart.js 4.4.1 с CDN (no npm)
- Bar: доход + кол-во встреч по месяцам (6 мес), две оси
- Line: встречи по неделям (8 нед) с заливкой и tension-curve
- Doughnut: топ-6 услуг
- Палитра violet/emerald/pink, чарты только при total_count>0

**N6 — Services redesign (5b60d6c):**
- Emoji-picker: 27 пресетов (флаги стран, спорт, наука, искусство)
- Цена теперь в **рублях** (price_rub), не копейках — friendly для users
- Inline edit-form через Alpine x-show, не свёрнутые `<details>`
- Description-поле в UI (раньше только в БД)
- Stars-эквивалент показан рядом с ₽ (≈ price/1.2)
- Back-compat: price_kopecks остаётся как fallback

**N7 — TZ auto-detect (6f35b97):**
- Setup-profile форма: TZ-select с 17 пресетами РФ/СНГ
- JS `Intl.DateTimeFormat().resolvedOptions().timeZone` — авто-detect
- Если детектированная TZ в списке — выбирается, hint меняется на «✓ определили: …»
- Если не в списке — добавляется как option сверху
- Backend валидирует через ZoneInfo, fallback на Europe/Moscow

**Прод-статус:** SHA 6f35b97 живой, /lessio 200, /u/demo 200, /lessio/auth/login 200, /lessio/app/today (no-auth) 401. **188/188 lessio-тестов зелёные** (3:30 минут полный run).

Запушено: 425a2d6, 7da7d77, 54a2cc9, f7a54d7, 5cf07dc, 5b60d6c, 6f35b97 — 7 коммитов за сессию, без поломок существующих фич.

---

## 2026-05-27 — Ночная сессия: Lessio login fix + /u/demo + Doday URL refactor + 5 Phase 3 фич

Юзер заметил баги (после login попадал в Doday cabinet, /u/demo 404), потом дал полную автономию «работай ночь, придумывай фишки». Старт ~23:45 МСК 2026-05-26.

**Bugfix sprint (Lessio auth + demo) — c9aa709:**
- /lessio/auth/login + /lessio/auth/logout (Lessio-scoped, не trogает Doday auth)
- lessio_login.html template
- Re-wire nav «Войти» в landing + register footer + cabinet logout form (все указывают на Lessio URLs)
- scripts/lessio_seed_demo.py — idempotent создаёт реального demo-tutor'а (lessio_demo@auto.lessio, /u/demo, 2 услуги, 3 reviews для aggregateRating)
- Запущен SSH на проде → /u/demo живой
- 5 E2E test'ов (full register→logout→login flow + nav-regex-guard против регрессии)

**Doday URL refactor batch 2A — 68b8060:**
- User: «все страницы которые были раньше теперь будут с префиксом doday». 
- Сделано минимально-инвазивно (только cabinet, visible to user):
  - views_router /app → /doday/app
  - htmx_router /htmx → /doday/htmx
  - auth login redirect → /doday/app/today
  - 301-redirect middleware для legacy /app/* и /htmx/* (SEO-safe, старые закладки + emails работают)
- scripts/refactor_doday_prefix.py — переиспользуемый regex-based rewriter (с look-behind '(?<![\\w-])/app/' чтобы исключить /lessio/app/)
- Mass find-replace: ~171 файла обновлено (templates + tests + scripts)
- НЕ перенесено пока: /api/*, /auth/* (Doday-shared), marketing pages (/pricing, /help, /changelog etc) — следующий batch.
- 2 теста чинены вручную (test_app_shell follow_redirects, test_digest URL).
- Полный suite: **1045 passed**.

**Phase 3 фичи — a6c800a (3 chunks, 4 миграции 0043-0046, 12 новых TDD):**

1. **Jitsi auto-meeting URLs** — если ни у service ни у tutor нет meeting_url template, create_booking auto-generates `https://meet.jit.si/lessio-<booking_uuid>`. Бесплатно, без OAuth, клиент сразу получает clickable link в email.

2. **Booking lead-time + vacation mode** (migration 0045):
   - LessioTutorProfile.booking_lead_hours: int = 2 — клиент не может забронировать раньше чем за N часов
   - LessioTutorProfile.vacation_until: datetime | None — все слоты до этой даты скрыты (отпуск/болезнь)
   - find_free_slots применяет оба фильтра, settings.html UI добавлен

3. **iCal feed для tutor'а** (RFC5545):
   - GET /lessio/app/calendar.ics?token=<Fernet(profile.id)> → text/calendar
   - VEVENT per confirmed/completed booking, CRLF + escape chars
   - Tutor подписывается в Apple Calendar / Outlook / Google Calendar — refresh 15-30 мин
   - settings.html: subscribe URL + copy button

4. **Per-service emoji icons** (migration 0046): LessioService.icon_emoji default '💼'.

**Тесты Phase 3:** 184 Lessio passing (12 новых: 3 jitsi + 5 lead-vacation + 4 ical). Doday-suite full: 1045 passing.

**Коммиты:** c9aa709 (Lessio auth fix) → 68b8060 (Doday URL refactor 2A) → a6c800a (Phase 3 фичи).

---

## 2026-05-26 — Lessio Production Polish: Welcome + Digest + Stats + PWA + GCal scaffolding

Юзер сказал «делай всё» после списка возможных улучшений → 4 batch'а автономно:

- ✅ **Batch A** (85f0669): **Welcome email** после setup-profile + **Daily morning digest cron**. Migration 0044 `lessio_tutor_profiles.last_daily_digest_at` для idempotency (cron-poll каждую минуту → digest 1×/день через 20h check). `send_welcome_email` (3-шаговый onboarding tutorial с публ.ссылкой) и `send_daily_digest_email` (список встреч в tutor TZ). 6 TDD-кейсов.
- ✅ **Batch B** (338352f): **Stats dashboard** `/lessio/app/stats` — 4 metric cards (заработано/ждёт/всего/30d) + breakdown по услугам. **PWA install** — `/lessio/app/manifest.webmanifest` + `/lessio/app/sw.js` (network-first SW с offline cache) + auto-register в `_base.html`. Tutor добавляет cabinet на phone homescreen, выглядит как нативное app. 7 TDD-кейсов.
- ⏭️ **Batch C** SKIPPED: TG-уведомления через @LessioBot — отложены из-за известного Telegram-API infra-debt (бот worker на проде не работает из-за RKN-блокировки). Email-уведомления уже закрывают эту потребность; вернёмся когда инфра починена.
- ✅ **Batch D** (1fb18d3): **Google Calendar OAuth scaffolding** — full flow с Fernet-encrypted refresh-tokens (PBKDF2-SHA256 derived от `app_secret_key`, restart-safe). `fetch_google_busy_times` интегрирован в `find_free_slots` (если refresh_token есть → exchange → FreeBusy API → extend busy_intervals). `/lessio/oauth/google/{connect,callback,disconnect}`. Settings.html: Connect/Disconnect buttons + status banners. **Активируется когда добавишь `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` в прод .env**. `cryptography>=43.0` в deps. 9 TDD-кейсов.
- ⏭️ **Batch E SKIPPED**: Email verification для Lessio — Doday auth вообще не имеет forgot-password flow (shared infra-gap, не Lessio-specific); отложу до Phase 3 для всей платформы.

**Тесты Production Polish:** 6+7+0+9 = **22 новых TDD**. Полный Lessio-suite: **165 passed**. ruff + mypy --strict зелёные.

**Коммиты:** 85f0669 (A) → 338352f (B) → 1fb18d3 (D). Push'нуто на прод.

---

## 2026-05-26 — Lessio Phase 2: Tutor-TZ + Reviews + Bulk-import + IndexNow deployed на прод

После Week 4 юзер сказал «сам всё сделай и продолжай» → автономно сделано Phase 2:

- ✅ **INDEXNOW_KEY** автогенерирован + добавлен в прод `.env` через SSH + uvicorn-restart (порт 8011 убит/поднят без касания Tap Tower 8012 / IndigoSmart 8000); `/8c03…5527.txt` отдаёт ключ на проде; pinger готов слать уведомления Яндексу при создании tutor-профилей.
- ✅ **Phase 2 chunk A** (cfe5a06): tutor-timezone overrides. `tzdata` в deps (Windows-fix); `cabinet_router.py::_LESSIO_TIMEZONES` — 16 popular RU/СНГ зон + UTC; settings.html — select для выбора зоны; today endpoint считает «сегодня» в tutor.timezone (а не в UTC) + pre-computes time_local + tz_label; 4 TDD-кейса.
- ✅ **Phase 2 chunk B** (0d58329): tutor reviews + aggregateRating. Migration 0043 — `lessio_reviews` (UNIQUE booking_id, rating 1-5 CHECK, text 2000). `app/lessio/reviews.py` — create_review/get_tutor_aggregate/get_tutor_recent_reviews; GET+POST `/lessio/review/<token>` через тот же manage_token; profile.html: aggregateRating + review[] в JSON-LD (Google rich snippets → ★ в SERP); visual header показывает звёзды + средняя оценка; reviews section после services; review/submit.html — Alpine star-rating picker; 10 TDD-кейсов.
- ✅ **Phase 2 chunk C** (этот коммит): bulk-CSV import clients. GET `/lessio/app/clients/import` — upload-форма; POST принимает multipart CSV (UTF-8 with/without BOM), парсит DictReader, для каждой строки: invalid email → skip, существующий email → update full_name/phone (last-write-wins), новый → INSERT. Редирект с counters ?created=&updated=&skipped=. clients.html: «Импорт CSV →» button + success-banner. 4 TDD-кейса.

**Тесты Phase 2:** 4 + 10 + 4 = **18 новых TDD**. Полный Lessio-suite: **137 passed** (101 MVP + 18 Week 4 + 18 Phase 2). ruff + mypy --strict + jinja-lint зелёные.

**Коммиты Phase 2:** cfe5a06 (tz) → 0d58329 (reviews + migration 0043) → [этот] (clients/import).

**Что в Phase 3 (deferred — нужны внешние credentials / сильно меняют систему):**
- Google Calendar OAuth busy-times sync (heavy Fernet + refresh-token rotation).
- Embedded payments (ЮKassa требует 18+, Stars вне TG).
- PWA install prompt + push notifications.
- Multi-language UI (только RU сейчас).
- Search/discovery /lessio/discover (нужен scale ≥50 tutors).
- Auto-completion bookings cron + auto-send review-email (сейчас admin вручную marks status='completed', клиент идёт на /lessio/manage/<token> чтобы оценить — но дополнительный «оцените встречу» email пока не шлётся автоматически).

---

## 2026-05-26 — Lessio Week 4: Post-MVP polish (editable profile · TZ · analytics · IndexNow)

После MVP юзер сказал «давай доделывай» → 4 follow-up chunks отполировали UX и SEO:

- ✅ **Chunk 4.1** (8e43b5b): editable profile в Settings (slug/display_name/niche/avatar_emoji/bio) с защитой от collision и invalid-format. Раньше эти поля были locked после setup-profile с заглушкой «появится в следующих версиях» — теперь редактируются.
- ✅ **Chunk 4.2** (8ee4c27): client-side timezone localize для slot-pickers + booking confirm + manage. Каждый отображаемый UTC-слот несёт `data-utc-iso=<ISO>` и `class=lessio-localize`; inline `Intl.DateTimeFormat` JS конвертит в браузерную зону (Europe/Moscow, Asia/Yekaterinburg, etc) с display tz-name. Server-side остаётся UTC fallback если JS отключён.
- ✅ **Chunk 4.3** (c5075d6): Yandex.Metrika tracking + `lessioGoal()` обёртка + `lessio_booking` conversion goal на /booked. Шаблон `templates/lessio/_metrika.html` подключается из всех Lessio public+cabinet страниц; conditional на `request.state.ya_metrika_id` — в dev no-op.
- ✅ **Chunk 4.4** (этот коммит): IndexNow integration — ping Яндекса при создании tutor-профиля и при slug-change в settings → /u/<slug> попадает в индекс за минуты вместо дней. `app/lessio/indexnow.py::ping_indexnow` fire-and-forget. Endpoint `/<KEY>.txt` в `app/main.py` отдаёт ключ для верификации владения. `INDEXNOW_KEY` в `.env.example` документирован.

**Тесты Week 4:** 5 + 3 + 5 + 5 = **18 новых TDD**. Полный Lessio-suite: **124 passed** (101 + 18 + 5). Полный Doday-suite остаётся зелёным.

**Коммиты Week 4:** 8e43b5b (editable profile) → 8ee4c27 (tz-localize) → c5075d6 (metrika+goal) → [этот] (IndexNow).

**Что осталось в Phase 2 (как было до wk4):**
- Google Calendar OAuth busy-times sync.
- Embedded payments (ЮKassa / Stars вне TG).
- Aggregate rating в JSON-LD (нужны отзывы).
- Tutor-timezone overrides на server-side (сейчас всё UTC + client-side display).
- Multi-language UI (только RU).
- PWA install prompt + push notifications.

---

## 2026-05-26 — Lessio Web MVP · Week 3 завершена · Production-ready

Полный кабинет репетитора + Income/CSV + dynamic OG-image. **3-недельный MVP (12 chunks) задеплоен полностью.**

**Что задеплоено в Week 3 (4 chunk'а):**
- ✅ **Chunk 3.1**: `app/lessio/cabinet_router.py` — единый router `/lessio/app/*` для всех cabinet-страниц с `_require_profile` guard. GET `/today` (booking-list на сегодня UTC). GET/POST `/settings` (bio + default_meeting_url_template + notification_email). Templates: `lessio/app/_base.html` (sidebar shell с nav-tabs + публ.ссылка + logout), `today.html` (cards со временем/именем/оплатой/meeting-кнопкой или empty-state), `settings.html` (form + ?saved=1 alert).
- ✅ **Chunk 3.2**: Services CRUD (GET list, POST create с group-session checkbox, POST `/services/<id>/toggle-active`, POST `/services/<id>/edit`). Clients pages (GET list + GET `/clients/<id>` detail с историей bookings). Templates: `services.html` (cards с inline-edit form + Alpine для group toggle), `clients.html`, `client_detail.html`. Auto-calc `price_stars = max(1, kopecks // 120)`.
- ✅ **Chunk 3.3**: GET/POST `/schedule` (working_days checkbox-grid, work_start/end_hour, buffer_minutes + валидация). GET `/calendar?month=YYYY-MM` (6×7 month-grid с цветными bookings: violet=confirmed, rose=cancelled, emerald=completed). Helper `_parse_month` для безопасной валидации query-param. Templates: `schedule.html` (sr-only checkbox + peer-checked label-trick), `calendar.html` (aspect-square cells + top-3 bookings preview).
- ✅ **Chunk 3.4**: GET `/income?month=YYYY-MM` (paid + unpaid totals + booking list + CSV link). POST `/bookings/<id>/toggle-paid` (flip payment_status + paid_at, redirect back via Referer). GET `/income/export.csv?year=&month=` (CSV с UTF-8 BOM для Excel, формат: date/time/client/service/duration/price_rub/status — совместим с импортом в «Мой Налог»). `app/lessio/csv_export.py::bookings_to_csv` (pure function). `app/lessio/og_image.py::render_tutor_og_svg` (1200×630 dynamic SVG с emoji + display_name + niche-label, HTML-escape для XSS-safety). GET `/u/<slug>/og.svg` (public, Cache-Control: 1 day). `profile.html` обновлён → `og:image` теперь per-tutor.

**Architecture (production-ready):**
- 7 cabinet-страниц + 4 manage-страницы + публ. /u/<slug> + booking flow + cron — всё под `app/lessio/*`, 4 router-файла (`router.py`, `web_router.py`, `cabinet_router.py`, `admin.py`) + 2 utility-модуля (`email.py`, `cron.py`, `csv_export.py`, `og_image.py`).
- Все cabinet-endpoint'ы требуют `RequiredUser` + наличие `LessioTutorProfile` (303 redirect на setup-profile если нет).
- Authentication: стандартный Doday `register_user` + session-cookie. Email verification опциональна (не блокирует setup).
- Email-уведомления через `aiosmtplib` + Jinja, SMTP-fail graceful (логирует но не raise'ит, чтобы не блокировать booking-транзакцию).
- Cron `dispatch_reminders` идемпотентный (UPDATE `reminder_*h_sent_at` только при SMTP success).
- SEO: canonical, OG-tags (per-tutor SVG image), Twitter card, JSON-LD Person + makesOffer, sitemap.xml dynamic, robots.txt explicit.

**Тесты:** 6 (chunk 3.1) + 7 (chunk 3.2) + 5 (chunk 3.3) + 7 (chunk 3.4 income+og) = **25 новых TDD-кейсов в Week 3**. Полный Lessio-suite: **101 passed**. Полный Doday-suite: **~975 passed**. ruff + mypy --strict + jinja-lint зелёные.

**Коммиты Week 3:** c641774 (week3 plan + PROGRESS Week 2 close) → a4317e3 (chunk 3.1) → 51e9208 (chunk 3.2) → 571e7a0 (chunk 3.3) → [chunk 3.4 — этот коммит].

**МVP завершён.** За одну сессию: spec → 3 plan-файла → 12 chunks → ~73 новых TDD-кейсов → 13 commits → задеплоено на прод.

**Что в Phase 2 (явно не делалось):**
- Google Calendar OAuth (двусторонняя busy-times sync — heavy: Fernet encryption + refresh-token rotation + Google API calls).
- Embedded payments (ЮKassa требует 18+, Stars — за пределами TG-flow без смысла).
- Aggregate rating в JSON-LD (нужны отзывы клиентов — отдельная фича после первых регистраций).
- IndexNow API для sitemap ping (notify Google/Yandex при tutor signup).
- Search/discovery `/lessio/discover` (нужен scale ≥50 tutors).
- Multi-language UI (только RU в MVP).
- Mobile PWA install prompt + push notifications.
- Tutor timezone overrides (сейчас всё в UTC).

**End-to-end flow на проде:**
1. Tutor: `/lessio` → CTA «Стать репетитором» → register → setup-profile (slug/name/niche) → автогенерация default-услуг → `/lessio/app/today` (cabinet)
2. Tutor: настраивает расписание/услуги/настройки в кабинете, делится публ. ссылкой `getdoday.ru/u/<slug>`
3. Client: открывает `/u/<slug>` → выбирает услугу → `/book/<id>` → слот + email/phone/name → POST → email-подтверждение с magic-link
4. Client: по magic-link `/lessio/manage/<token>` видит свои записи, может перенести/отменить
5. Cron каждые ~5 мин шлёт reminders 24h и 1h на client email
6. Tutor: видит встречи в Today/Calendar, отмечает оплату в `/income`, экспортирует CSV для «Мой Налог»

---

## 2026-05-26 — Lessio Web MVP · Week 2 завершена + задеплоено

End-to-end booking flow живой. Anon-клиент видит `/u/<slug>` → выбирает услугу+слот → POST `/u/<slug>/book/<service_id>` создаёт LessioBooking + рассылает email клиенту (с magic-link) + tutor (на notification_email). Magic-link `/lessio/manage/<token>` показывает все будущие confirmed-записи клиента у этого репетитора с кнопками [Перенести] [Отменить]. Cron-endpoint `/api/lessio/cron/dispatch-reminders` (X-Cron-Token) — батч reminders 24h+1h в окне ±5мин, идемпотентный.

**Что задеплоено (prod SHA 52523f0):**
- ✅ Chunk 2.1: `app/lessio/email.py` (send_booking_emails / send_cancellation_email / send_reminder_email через aiosmtplib + Jinja env), `service.py` обновлён с `create_booking` (find/upsert LessioClient, INSERT booking, конфликт-guard на app-level, manage_token=secrets.token_urlsafe(48)), `cancel_booking`, `reschedule_booking`, `BookingConflictError`. 6 email-шаблонов (HTML+txt каждый): `_base` + booking_confirmed + new_booking + cancelled_by_{client,tutor} + reminder_{24h,1h}.
- ✅ Chunk 2.2: Public booking flow `/u/<slug>/book/<service_id>` GET (Alpine.js slot-picker grid + клиент-форма) + POST (create_booking → redirect на `/u/<slug>/booked?token=…`) + GET booked success-страница.
- ✅ Chunk 2.3: Magic-link manage `/lessio/manage/<token>` GET (siblings: все confirmed-будущие записи клиента у этого репетитора), POST `/cancel`, GET+POST `/reschedule` (cancel-old + create-new в одной транзакции, при BookingConflictError откат старого в confirmed).
- ✅ Chunk 2.4: `app/lessio/cron.py::dispatch_reminders(hours=24|1)` — SELECT confirmed bookings в окне ±5мин без `reminder_*h_sent_at`, на каждый `send_reminder_email`, UPDATE timestamp только при SMTP success. `POST /api/lessio/cron/dispatch-reminders` с `hmac.compare_digest` против `cron_token`, 503 при отсутствии настройки.

**Тесты:** 10 (chunk 2.1) + 6 (chunk 2.2) + 5 (chunk 2.3) + 5 (chunk 2.4) = **26 новых TDD-кейсов**. Полный suite **949 passed, 654s**. ruff + mypy --strict зелёные.

**Архитектура (router-разделение в Lessio):**
- `app/lessio/router.py` — landing + waitlist + Mini App TG-flow
- `app/lessio/web_router.py` — register/setup-profile + cabinet placeholder + manage magic-link + public `/u/<slug>` + booking flow + cron-endpoint. Содержит 3 routers: `router` (`/lessio`), `_public_router` (no prefix), `_cron_router` (`/api/lessio`).
- `app/lessio/admin.py` — admin token-auth endpoints
- `app/lessio/email.py` — все email-функции (booking, cancel, reminder)
- `app/lessio/cron.py` — `dispatch_reminders` batch handler
- Все email-шаблоны в `app/templates/lessio/email/` — отдельная Jinja Environment, чтобы `{% extends "_base.html" %}` работал без префикса.

**Коммиты:** d274961 (week 2 plan) → 25fc166 (chunk 2.1) → 5bb9d98 (chunk 2.2) → b469590 (chunk 2.3) → 52523f0 (chunk 2.4).

**Smoke prod после deploy:** /version SHA совпал за 30с, /lessio/manage/<unknown> → 404, /api/lessio/cron/dispatch-reminders без token → 403, /u/<unknown>/book/<uuid> → 404.

**Что осталось до production-ready (Week 3, plan уже есть):**
- Кабинет: Today / Calendar / Clients / Services / Schedule / Income / Settings (7 страниц с CRUD).
- Toggle-paid + CSV export income (для самозанятого учёта в Мой Налог).
- Dynamic per-tutor OG-image (SVG-генератор, без headless browser).
- README + ENV.example + final PROGRESS update.

**Phase 2 (после wk3):**
- Google Calendar OAuth busy-times sync.
- Embedded payments (ЮKassa требует 18+).
- Aggregate rating в JSON-LD (нужны отзывы).
- IndexNow API для sitemap ping.

---

## 2026-05-25 — Lessio Web MVP · Week 1 завершена + задеплоено

Spec → plan → 4 chunks → prod за одну сессию. Web-flow для репетиторов/тренеров/психологов внутри Doday-монорепо, рынок РФ, postoplata off-platform.

**Что задеплоено (prod SHA 37d06d3):**
- ✅ Migration 0042: расширение `lessio_clients` (email NOT NULL, phone, full_name; telegram_user_id → nullable), `lessio_bookings` (manage_token UNIQUE, payment_status, reminder timestamps, denormalized client_email/full_name, meeting_url), `lessio_services` (meeting_url_template, is_group_session, max_attendees, location), `lessio_tutor_profiles` (default_meeting_url_template, notification_email, google_calendar_refresh_token). Старый UNIQUE (tutor_id, starts_at) убран — replaced by app-level double-booking guard в `create_booking` (Postgres не поддерживает subquery в partial-unique-index).
- ✅ `find_free_slots()` — реальная реализация: working_days/work_hours/buffer-aware + group-session логика (клиенты join'ятся к уже опубликованным временам пока < max_attendees).
- ✅ `create_services_from_template()` — bulk-create default-услуг под 8 ниш (english/ielts/math/school/fitness/psychology/yoga/other).
- ✅ `/lessio/auth/register` (email+password через Doday `register_user`) → auto-login → `/lessio/app/setup-profile` (slug + display_name + niche + bio) → создание `LessioTutorProfile` + автогенерация default-услуг → `/lessio/app/today` (placeholder-кабинет с публичной ссылкой, full UI — Week 3).
- ✅ `/u/<slug>` публичная страница: hero (avatar + display_name + bio), grid услуг с ценами, footer. SEO: canonical, OG (title/desc/url/image/locale ru_RU), Twitter card, JSON-LD Person schema + makesOffer (для каждой услуги — name/price RUB/duration в минутах). 404 на unknown/inactive.
- ✅ `sitemap.xml` — динамический: автоматически добавляет `/u/<slug>` для всех `is_active=true` tutor-профилей. `robots.txt` — явный `Allow: /u/` + `Disallow: /lessio/{app,auth,manage}/`.

**Архитектура (внутри Doday-монорепо):**
- `app/lessio/web_router.py` — новый router (auth/cabinet + public). Параллельно с `app/lessio/router.py` (TG-flow + Mini App) и `app/lessio/admin.py`. Все три зарегистрированы в `app/main.py`.
- `app/templates/lessio/{_base_auth.html, auth/, app/, u/}` — Lessio-брендированные shell+formы+public-profile.
- Auth flow — реиспользует стандартный Doday-`register_user` + sessions cookie, **email verification опционально** (не блокирует setup-profile, в отличие от Doday-flow). Пароль ≥ 8 char (Doday's `RegisterIn` validator).

**Тесты:** 4 (models) + 8 (free_slots) + 4 (register) + 6 (public_profile) = **22 новых TDD-кейса**, все зелёные. Полный suite **923 passed, 660s**. `pre-commit` (ruff/mypy --strict/jinja-lint) — зелёный.

**Коммиты:** e42a1b7 (spec) → 3989fc5 (plan) → d15e883 (chunk 1.1: migration+models) → 4d010eb (chunk 1.2: free_slots + service templates) → 05d3b27 (chunk 1.3: register/setup-profile) → 37d06d3 (chunk 1.4: public profile + SEO).

**End-to-end flow работает на проде**: новый юзер → /lessio/auth/register → setup-profile → today + публичная ссылка → /u/<slug> render'ится с JSON-LD для Google.

**Что НЕ делает Week 1 (планируется на Week 2-3):**
- Booking-flow (форма выбора слота + клиент-форма email/phone/name + email-confirmation) — Week 2.
- Magic-link для управления booking'ом клиентом (отмена/перенос) — Week 2.
- SMTP-уведомления (tutor + client + reminders 24h/1h cron) — Week 2.
- Полный кабинет (calendar/clients/services CRUD/income+CSV/settings) — Week 3.
- Google Calendar OAuth (двусторонняя синхронизация) — Week 3.
- Dynamic per-tutor OG-image (SVG-генератор с именем + аватаром) — SEO chunk Week 3.

---

## 2026-05-25 — @LessioBot подключён dual-Application + обнаружен Telegram-API infra-debt

Bot worker (`app/telegram/bot.py`) переписан под dual-Application:
- @DodayTaskBot (settings.telegram_bot_token) — Doday Tasks
- @LessioBot (settings.lessio_bot_token = `@mylessiobot`) — Lessio /start с CTA на /lessio
- Оба в одном процессе через ручной `await app.initialize() / start() / updater.start_polling()` + `asyncio.Event().wait()`. `Application.run_polling()` несовместим с gather'ом, поэтому отказались.
- **Per-bot graceful degradation**: каждый стартует в своём try/except, если один упал — продолжаем с другим. Если оба упали → return (watchdog перезапустит).
- `app/billing/stars.py._bot_token_for_product`: `tutor_pro_*` → Lessio token, остальное → Doday. Доход Lessio идёт на отдельный Stars-балланс @mylessiobot.
- `app/lessio/telegram_handlers.py`: только `cmd_start` для фазы валидации.
- Тесты: `test_lessio_telegram_handlers.py` + `test_stars_token_routing.py` (7 кейсов).

LESSIO_BOT_TOKEN + LESSIO_BOT_USERNAME подгружены в локальный .env из архивной `c:\www-Yaroslav\Lessio\.env` (где они лежали с момента инициализации Lessio-репо в той сессии). На прод через SSH прокинуто. Bot username — `@mylessiobot` (orphan из той сессии, теперь снова активен под брендом Lessio).

**Infra-debt найден** (НЕ МОЯ задача исправить, до моих изменений):
- Bot worker на проде падает с `TelegramError: Invalid server response` / `TimedOut` уже давно, даже на старом `run_polling()`-коде.
- Причина: hardcoded IPv4 `149.154.167.220` для api.telegram.org устарел — Telegram ротирует DC-адреса.
- Добавлен env-флаг `DISABLE_TELEGRAM_IPV4_PATCH=1` в settings — обходит monkey-patch'инг resolver'а.
- Но и системный DNS на проде тоже даёт TimedOut → провайдер не маршрутизирует к Telegram API через текущие IP. **Нужен SSH с sudo чтобы фикстить `/etc/resolv.conf` или iptables, либо обновить hardcoded IP списком 149.154.167.220-223** (надо найти рабочий из российской сети).
- Pid 2096941 на проде — был **Tap Tower's bot**, не Doday. Случайно убил, восстановил через `start-poller.sh`.

**Что работает сейчас:**
- ✅ Lessio web (`/lessio` лендинг + waitlist API) — задеплоено и работает
- ✅ Lessio admin endpoints (`/api/admin/lessio/waitlist/*` с X-Admin-Token)
- ✅ Hub `/` + Doday Tasks `/doday`
- ✅ Stars-product catalog содержит `tutor_pro_*`
- ✅ Bot code готов и unit-тестирован, ждёт фикса инфры

**Что НЕ работает:**
- ❌ @DodayTaskBot — был сломан до моих изменений (Telegram API timeout)
- ❌ @mylessiobot — не запустится пока инфра не починена (та же причина)

Коммиты этого блока: 0296520 (dual-app), 513cbf0 (per-bot degradation), 7118343 (env-флаг через os.environ — не сработал), cb94de2 (флаг через pydantic-settings — правильно).

pytest -q зелёный 892 passed (+7 от новых тестов). ruff + mypy --strict зелёные.

---

## 2026-05-25 — Studio-hub на `/`, Doday Tasks лендинг переехал на `/doday`

Архитектурный реорг: getdoday.ru теперь зонтичная студия, не один туду-лист. Корневой `/` — это хаб с карточками всех проектов автора (Doday Tasks, Lessio, Беллстрой ТВ, Tap Tower). Бывший `/` (long marketing landing про туду-лист) переехал на `/doday` без изменений в содержимом.

Изменения:
- **`app/hub/__init__.py` + `app/hub/router.py`** — новый модуль для root-landing'а
- **`app/templates/hub/index.html`** — standalone-страница: nav, hero «Мини-продукты которые работают», featured Doday Tasks card сверху, grid из 3 других проектов с статусами (Active / Validation / Toy / Legacy), about-stats block (1 dev · 4 продукта · 400+ юзеров), footer с GitHub/Email
- **`app/pages/router.py`** — `@router.get("/")` → `@router.get("/doday")`. Логика redirect для logged-in остаётся (без `?preview=1` → `/app/today`).
- **`app/main.py`** — `app.include_router(hub_router)` перед `pages_router` (hub отвечает за `/`, pages держит остальные docs-страницы и теперь `/doday`)
- **`sitemap.xml`** — добавлены `/doday`, `/lessio`
- **`scripts/smoke_test.py`** — `/` теперь label `hub`, добавлены `/doday` (doday-tasks-landing) и `/lessio` (lessio-landing)
- **`app/templates/lessio/index.html`** footer — cross-link «На Doday» теперь ведёт на `/doday` (Doday Tasks), а на хаб ведёт «Все проекты студии»
- **Тесты:** `tests/test_hub.py` (3 кейса), все упоминания `/` в test_landing.py / test_landing_page.py / test_help_center.py / test_polish_batch.py заменены на `/doday`

Login flow не тронут — он редиректит на `/app/today?welcome=1` напрямую (не через `/`). Logout редиректит на `/` (теперь юзер видит хаб после logout — это правильное UX).

pytest -q зелёный, ruff + mypy --strict зелёные.

---

## 2026-05-25 — Lessio как модуль внутри Doday + админка waitlist'а (578d8ef + следующий)

Pivot после двух часов в отдельном репо `SwairIt/Lessio`: вместо отдельной инфры и FastPanel-vhost под `lessio.getdoday.ru`, Lessio живёт прямо внутри Doday-репо по пути `/lessio`. Один cron-poll, одна БД, один бот `@DodayTaskBot`. Не дёргаем брата под каждый новый проект — Doday становится monorepo для всех вертикалей.

Что в этом релизе:
- **`app/lessio/`** — 5 ORM-моделей с префиксом `lessio_*` (LessioWaitlistEntry активна, остальные заготовка под MVP), router c `GET /lessio` (лендинг) + `POST /lessio/waitlist` (idempotent по email)
- **`app/templates/lessio/index.html`** — лендинг: hero, pain→solution rows, pricing (Free / Pro 1000⭐ / Founder 50000⭐), FAQ, cross-link на Doday
- **`app/lessio/admin.py`** — X-Admin-Token endpoint'ы: `GET /api/admin/lessio/waitlist.json`, `GET /api/admin/lessio/waitlist/stats.json` (агрегаты + threshold-met флаг), `DELETE /api/admin/lessio/waitlist/by-email`. Для day-7 решения go/pivot/drop.
- **`app/billing/products.py`** — +3 Stars-продукта: `tutor_pro_1m` (1000⭐), `tutor_pro_12m` (10000⭐), `tutor_pro_forever` (50000⭐ lifetime, Founder)
- **`alembic/0040_lessio_module.py`** — 5 таблиц с FK на `users` и `star_payments`
- **Тесты:** 14 кейсов (6 landing + 3 Stars products + 5 admin), pytest 877+5 = 882 passed
- **Архив** старого Lessio-репо в `c:\www-Yaroslav\Lessio\` + `github.com/SwairIt/Lessio` остаётся как референс — может пригодиться когда отделим в свой репо после ≥100 waitlist

Validation phase: с 2026-05-25 до 2026-06-01 собираем waitlist через посты в каналах репетиторов (см. `docs/lessio-launch-posts.md`). Decision rule locked: ≥100 → MVP go, 30-99 → пивот, <30 → drop.

Мониторинг waitlist'а (X-Admin-Token из .env):
```bash
TOKEN=$(grep ADMIN_TOKEN .env | cut -d= -f2-)
curl -s -H "X-Admin-Token: $TOKEN" https://getdoday.ru/api/admin/lessio/waitlist/stats.json | python -m json.tool
```

---

## 2026-05-24 — Беллстрой ТВ → бесконечная аркада с brainrot-врагами (6b1e7da)

По запросу юзера: «нельзя прыгать / маленькая локация / быстро прошёл / текстурки покрасивее / чтобы можно было умереть и мемно». Развалил `game.js` на 4 модуля и дописал HUD:

- **`modules/world.js`** — карта 120×120 (была ~30×30), небо ShaderMaterial с градиентом фиолет→розовый→оранж, солнце с glow на горизонте, 30 procedural-зданий с неон-полосами по верху, point-light внутри каждого 4-го для атмосферы; пол — checkerboard + светящиеся розовые линии.
- **`modules/player.js`** — `createPlayer()` с гравитацией (-25), `jump()` (vy=9), HP=3, invincibility 1.2 сек (мигание через `mesh.visible`), `reset()` для restart; модель Беллстроя сохранена.
- **`modules/enemies.js`** — `Enemy` класс с AI chase + bob, 5 procedural-моделей: Tralalero (акула в 3 синих Nike), Bombardiro (крокодил-самолёт с пропеллером и бомбой), Tung Tung Sahur (деревянный с битой), Brr Brr Patapim (обезьяна-куст), Lirili Larila (кактус-слон с часами); скорости 2.5–4.5 м/с. `checkCollision()` различает stomp (игрок сверху + падает) и side-hit.
- **`modules/pickups.js`** — 17 мемов, infinite respawn после сбора всех (раньше — финальный экран после 17).
- **`game.js`** orchestrator — волновой спавн (25 сек, `2 + 0.7·wave` врагов до 20), camera-shake при ударе, stomp даёт `+50·wave` очков и отскок вверх, game-over overlay с лучшим Score/Волной из `localStorage`, restart по `R` или кнопке.
- **HTML/CSS** — новые HUD-элементы `#wave/#hp/#collected/#jump-btn/#wave-banner/#gameover-overlay`; jump-button (88px) виден только на `pointer: coarse`; game-over — gradient-card с stats и крупной восстанавливающей кнопкой; wave-banner с pop-in анимацией.

`pytest -q` зелёный 868/868. Прод-смоук 26/26. `/game` + все 4 модуля отдают 200. HTML на проде содержит все 6 новых id'шников. Commit `6b1e7da`, деплой подтверждён через `/version`.

---

## 2026-05-21 — Ralph-loop: имя проекта в строке задачи (кросс-проектные виды)

`today/upcoming/filter/label/done` views теперь отдают `project_name_map`
(`{id: name}`). В `_partials/task_row.html` под guard `project_name_map is defined
and task.project_id in …` — точка проекта получает `title` = имя, и рядом
приглушённый чип имени (truncate, цвет проекта). Одиночный `project_view` map не
передаёт → чип не дублируется (паттерн assignee_map/subtask_counts). Без бэкенда
и схемы БД. mypy strict + ruff + lint_templates зелёные, тесты 31 passed,
Playwright: на Today у задач чип «Inbox» (title «Проект: Inbox»), 0 console
errors. Скрин `docs/screenshots/project-name-in-row.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: относительные подписи дедлайна (Сегодня/Завтра/Вчера)

Новый `app/views/template_filters.py::due_label(task)` рядом с `due_state`:
вчера/сегодня/завтра → слова, дальше — `dd.mm` (timed +` HH:MM`). Зарегистрирован
Jinja-глобалом в `views/router.py` и `views/htmx.py`. Чип даты в
`_partials/task_row.html` и `_partials/kanban_card.html` теперь рендерит
`{{ due_label(task) }}` вместо `strftime`. Цвет (`due_state`) и date-dropdown не
тронуты. Без бэкенда и схемы БД. Тесты `tests/test_due_state.py` (10, +2):
относительные слова и абсолютный/timed формат. mypy strict + ruff + lint_templates
зелёные, Playwright: чип сегодняшних задач показывает «Сегодня», 0 console errors.
Скрин `docs/screenshots/relative-due-labels.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: метаданные задачи в task_detail (создано/завершено)

В `_partials/task_detail.html` добавлен футер с `border-t`, мелким текстом:
«Создано dd.mm.yyyy» + «· Завершено dd.mm.yyyy» (если `task.completed_at`).
Серверный рендер из `task.created_at`/`completed_at`, без бэкенда и схемы БД.
lint_templates 0 errors, тесты 19 passed, Playwright: панель показывает
«Создано 21.05.2026», 0 console errors. Скрин
`docs/screenshots/task-detail-meta.png`. Деплой подтверждён через /version.

(Прошлая итерация: задача про markdown-описание оказалась дублем — `window.dodayMd`
уже реализован в base.html; закрыта без коммита, зафиксирован урок проверять
по доменным именам.)

---

## 2026-05-21 — Ralph-loop: входящие приглашения (in-app баннер «Принять»)

Раньше приглашение принималось только по email-ссылке `/invite/{token}`.
`app/projects/invitations.py`: `list_invitations_for_email(session, email)` →
[(invitation, project_name)] (pending, не истёкшие, join Project). Эндпоинты в
invites_router: `GET /api/invites/incoming` (приглашения для email текущего
юзера, схема `IncomingInviteOut`), `POST /api/invites/{token}/accept`
(переиспользует `accept_invitation`). Баннер `_partials/incoming_invites.html`
(Alpine, fetch на загрузке, «Принять»/скрыть) подключён в app_base. Без
изменений схемы БД. Тесты `tests/test_incoming_invites.py` (3): сервис видит
свои pending, incoming-эндпоинт + accept присоединяет к проекту, 401 без auth.
mypy strict + ruff + lint_templates зелёные, Playwright: приглашённый видит
баннер «Вас пригласили…» → «Принять» → проект в сайдбаре, 0 console errors. Скрин
`docs/screenshots/incoming-invite-banner.png`. Деплой подтверждён через /version.
Цикл членства полный: пригласить → принять in-app → передать владение → покинуть.

---

## 2026-05-21 — Ralph-loop: передача владения проектом

Закрывает дыру из leave-фичи («передайте владение»). `app/projects/membership.py`:
новый `set_role(session, project_id, user_id, role)`. Эндпоинт
`POST /api/projects/{id}/members/{user_id}/make-owner` (owner-only): target→owner,
caller→member (полная передача), 403 для не-владельца, 404 для не-члена.
В `share_modal.html` у участника — действие «👑 Передать владение» (confirm →
make-owner → reload). Без изменений схемы БД. Тесты `tests/test_leave_project.py`
(6, +3): передача меняет роли, требует владельца (403), аноним 401. mypy strict +
ruff + lint_templates зелёные, Playwright: владелец → «Передать владение» →
confirm → reload, в шапке стало «Покинуть» (бывший владелец — участник), 0
console errors. Скрин `docs/screenshots/transfer-ownership.png`. Деплой подтверждён
через /version. Цикл членства замкнут: добавить → передать владение → покинуть.

---

## 2026-05-21 — Ralph-loop: «Покинуть проект» для участника-не-владельца

Новый эндпоинт `POST /api/projects/{id}/leave` (`app/projects/router.py`):
участник удаляет себя через `remove_member`; владелец → 400, не-член → 400,
без auth → 401. Кнопка «🚪 Покинуть» в шапке `project.html` для не-владельца
не-inbox проекта (`{% elif not project.is_inbox %}`), `hx-confirm` +
`hx-on::after-request` редирект на /app/today. Без изменений схемы БД. Тесты
`tests/test_leave_project.py` (3): участник выходит (204, role→None), владелец
400, аноним 401. mypy strict + ruff + lint_templates зелёные, Playwright:
участник видит «Покинуть» → confirm → редирект, проект исчез из сайдбара, 0
console errors. Скрин `docs/screenshots/leave-project-button.png`. Деплой
подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: «Перенести всё на сегодня» на фильтре Просрочено

Расширение Today-фичи на `/app/filters/overdue`. В `app/templates/app/filter.html`
кнопка «📅 На сегодня» + инлайн `dodayRescheduleAllOverdue()` рендерятся только
при `filter.slug == 'overdue'` и непустом списке (другие фильтры и label-view с
dict-filter без slug не затронуты — Jinja Undefined-guard). Собирает id всех
задач страницы → `/htmx/bulk` set_due=сегодня → reload. Без бэкенда и схемы.
Тест `tests/test_label_tasks.py` (5, +1): label-view с dict-filter рендерится 200
(не падает на filter.slug). lint_templates 0 errors, тесты 23 passed, Playwright:
на overdue-фильтре кнопка → задача ушла («найдено: 0»), на no-date кнопки нет, 0
console errors. Скрин `docs/screenshots/overdue-filter-reschedule.png`. Деплой
подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: бейджи-счётчики у фильтров в сайдбаре

`app/filters/service.py`: вынес where-условия в `_filter_conditions`, добавил
`count_for_filter(session, user_id, slug)` (общая логика с `list_for_filter`).
`sidebar_counts_endpoint` отдаёт новые ключи `no_date/high_priority/this_week`
(overdue уже был). В `_partials/sidebar.html` цикл фильтров получил бейдж
`x-show counts[key]>0` цвета фильтра. Без изменений схемы БД. Тесты
`tests/test_assigned.py` (19, +1): count_for_filter == len(list_for_filter) по
всем slug, эндпоинт содержит новые ключи. mypy strict + ruff + lint_templates
зелёные, Playwright: «Высокий приоритет · 2», «На этой неделе · 5», 0 console
errors. Скрин `docs/screenshots/filter-badges.png`. Деплой подтверждён через
/version.

---

## 2026-05-21 — Ralph-loop: bulk «Назначить выбранные на меня»

Замыкает набор assign-операций (одиночное — ctx-меню/детали). Ветка
`assign_me` в `app/views/htmx.py::bulk_action` (для каждого id
`update_task(assigned_to=user.id)`, try/except TaskNotFound/ValueError —
не-член пропускается). Кнопка «🙋 На меня» в `_partials/bulk_bar.html` (форма
как complete/duplicate). Без изменений схемы БД и нового эндпоинта. Тесты
`tests/test_assigned.py` (18, +2): bulk assign_me назначает на юзера, /htmx/bulk
401 без auth. mypy strict + ruff + lint_templates зелёные, Playwright: выделил
2 задачи → «На меня» → ушли в группу «ralphassigned» с аватарами, 0 console
errors. Скрин `docs/screenshots/bulk-assign-me.png`. Деплой подтверждён через
/version.

---

## 2026-05-21 — Ralph-loop: аватары участников в шапке shared-проекта

В шапке `app/templates/app/project.html` добавлен кластер аватаров участников
(перед «Поделиться»): инициалы на цветном фоне из `assignee_map`, наложение
`-space-x-2`, ring под фон. Показывается только при `assignee_map|length > 1`
(соло-проекты не засоряются), первые 5 + «+N». Без бэкенда и схемы
(assignee_map уже в контексте). lint_templates 0 errors, тесты 16 passed,
Playwright: для команды (2 участника R+T) кластер виден, 0 console errors. Скрин
`docs/screenshots/project-member-avatars.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: вид «задачи по лейблу» + кликабельные лейблы

Новый `app.labels.service.list_tasks_by_label` (join task_labels, открытые
top-level, не в корзине; labels eager via lazy=selectin). Роут
`GET /app/labels/{label_id}` в views/router (auth, 404 на чужой лейбл),
переиспользует `app/filter.html` с filter-dict (name=@лейбл, цвет лейбла,
tag-иконка). Лейблы стали кликабельны: чип в `task_row.html` → `<a>` на вид
лейбла, счётчик на `app/labels.html` → ссылка. Без изменений схемы БД. Тесты
`tests/test_label_tasks.py` (3). mypy strict + ruff + lint_templates зелёные,
Playwright: вид «@важное · найдено 1» + клик по чипу навигирует, 0 console
errors. Скрин `docs/screenshots/label-tasks-view.png`. Деплой подтверждён через
/version.

---

## 2026-05-21 — Ralph-loop: переиспользуемые toast-уведомления (dodayToast)

Новый партиал `_partials/toast.html` — singleton с глобальной
`window.dodayToast(message, {icon?, duration=2500})` (Alpine, по образцу
undo_toast, fixed bottom-center, role=status/aria-live, авто-скрытие). Подключён
в `app_base.html`. «🔗 Скопировать ссылку» в task_context_menu теперь даёт
отклик: success → «Ссылка скопирована», ошибка → «Не удалось скопировать». Без
бэкенда и схемы. lint_templates 0 errors, тесты 16 passed, Playwright +
evaluate-проверка: тост рендерится (display:flex, opacity:1, текст
«🔗 Ссылка скопирована»), 0 console errors. Скрин
`docs/screenshots/toast-copied.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: кнопка «Перенести просроченное на сегодня» (Today)

Focused-todo классика. В `app/templates/app/today.html` секции «Просрочено»
добавлена кнопка «📅 На сегодня» + инлайн-скрипт `dodayRescheduleOverdue()`:
собирает id задач из `#overdue-section`, шлёт `POST /htmx/bulk`
(`action=set_due`, `due=сегодня YYYY-MM-DD`), reload. Переиспользует
существующий bulk-эндпоинт — без бэкенда и схемы БД. lint_templates 0 errors,
тесты 16 passed, Playwright: клик убрал секцию «Просрочено», задача (18.05)
переехала в «Сегодня · 3» с янтарной датой, 0 console errors. Скрин
`docs/screenshots/reschedule-overdue-today.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: deep-link на задачу (?task=) + «Скопировать ссылку»

Чистый фронт в `_partials/task_context_menu.html` (глобальный скрипт на всех
/app). Пункт меню «🔗 Скопировать ссылку» → `navigator.clipboard.writeText(
origin+pathname+'?task='+id)`. На загрузке страницы `openDeepLinkedTask()` читает
`?task=<uuid>` и открывает деталь через существующий `GET /htmx/tasks/{id}/detail`
в `#task-detail-slot` (UUID-regex, guard на htmx/slot). Без бэкенда и схемы.
lint_templates 0 errors, тесты 16 passed, Playwright: `?task=<id>` авто-открыл
панель детали, 0 console errors. Скрин `docs/screenshots/deep-link-task.png`.
Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: группировка задач по исполнителю (проект-вью)

Расширил существующий Alpine-механизм `groupBy` в `app/templates/app/project.html`
(было none/priority/date) вариантом `assignee`. `project_view` отдаёт
`assignee_map_js` (строко-ключевой dict для JSON); в шаблоне он встроен через
`<script type="application/json">` и читается `JSON.parse` в x-data (чтобы кавычки
не ломали x-data-атрибут). `_groupKey/_groupLabel/_groupOrder` получили ветку
assignee; пункт меню «По исполнителю». В `task_row.html` добавлен
`data-assignee`. Без изменений схемы БД и бэкенда (assignee_map уже был).
mypy strict + ruff + lint_templates зелёные, тесты 28 passed, Playwright:
группы «🙋 …@example.com · 2» и «👤 Без исполнителя · 3», 0 console errors.
Скрин `docs/screenshots/group-by-assignee.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: счётчик подзадач «X/Y» в строке задачи

Новый `app.tasks.service.subtask_counts_for(session, user_id, parent_ids) ->
dict[UUID, tuple[done, total]]` — один group-by SELECT (case-sum), без N+1, без
изменения схемы, корзина исключена. `project_view` собирает `subtask_counts` по
активным родителям (из by_section.values) и кладёт в контекст. В
`_partials/task_row.html` бейдж «{done}/{total}» рядом с кареткой (зелёный когда
всё закрыто), в `_partials/kanban_card.html` — в полосе chips. Guard
`subtask_counts is defined` → today/inbox/filter не затронуты. Тесты
`tests/test_assigned.py` (16, +3). mypy strict + ruff + lint_templates зелёные,
Playwright: бейдж «1/3» виден, 0 console errors. Скрин
`docs/screenshots/subtask-count-badge.png`. Деплой подтверждён через /version.

---

## 2026-05-21 — Ralph-loop: эндпоинт /version для проверки доставки деплоя

Enabler для авто-проверки деплоя в лупе. `app/main.py::_read_git_sha()` читает
git SHA один раз при старте (env `DODAY_GIT_SHA` → `git rev-parse HEAD` в repo →
"unknown"), `GET /version` отдаёт `{"sha": ...}`. Добавлен в `scripts/smoke_test.py`
(24 endpoint'а). Теперь луп после push поллит `https://getdoday.ru/version`
пока SHA != запушенного, и только тогда считает деплой дошедшим; если не доходит
за ~4 мин — самолечение (SSH git pull + рестарт, диагностика cron-poll).

---

## 2026-05-21 — Ralph-loop: подсветка просроченных/сегодняшних дедлайнов

Новый Jinja-helper `app/views/template_filters.py::due_state(task) ->
overdue|today|future|none` (date-only — по дню, timed — по моменту UTC;
завершённые не overdue). Зарегистрирован глобалом на template-env в
`views/router.py` и `views/htmx.py` (оба рендерят task_row). Чип даты в
`_partials/task_row.html` и `_partials/kanban_card.html`: overdue → красный
(rose), today → янтарный (amber), иначе цвет проекта. Без изменений схемы БД.
Тесты `tests/test_due_state.py` (8). mypy strict + ruff + lint_templates
зелёные, Playwright: 18.05 красная, 21.05 янтарная, 22.05 приглушённая, 0
console errors. Скрин `docs/screenshots/due-overdue-highlight.png`.

---

## 2026-05-21 — Ralph-loop: быстрое «Назначить на меня / Снять» в контекст-меню

Чистый фронт (бэкенд PATCH `assigned_to` уже поддерживал назначение и снятие
через `_SENTINEL`). В `_partials/task_context_menu.html` добавлены пункты
«🙋 Назначить на меня» (PATCH `assigned_to=current_user.id`) и «🙅 Снять
назначение» (PATCH `assigned_to=null`); id текущего юзера проброшен через
`data-me="{{ current_user.id }}"` на меню (доступен, т.к. меню инклудится в
app_base, а `current_user` в контексте всех /app). Без изменений схемы БД и без
нового эндпоинта. Тест `tests/test_assigned.py` (13, +1): `update_task`
назначает self и снимает (None). mypy strict + ruff + lint_templates зелёные,
Playwright: меню → «Назначить на меня» → у задачи появился аватар «R», 0 console
errors. Скрин `docs/screenshots/ctx-assign-me.png`.

---

## 2026-05-21 — Ralph-loop: аватар исполнителя в строке задачи (проект-вью)

Замыкает серию «Назначено мне». Новый `app.projects.membership.assignee_map_for_project`
— `dict[user_id, {initial, label, color}]` (join ProjectMember+User, цвет
детерминированно из палитры Tailwind по `user_id.hex`). `project_view` кладёт
`assignee_map` в контекст project.html/kanban.html. В `_partials/task_row.html`
и `_partials/kanban_card.html` — аватар-кружок с инициалом исполнителя, guard
`assignee_map is defined and task.assigned_to in assignee_map` (обратно-совместимо:
today/inbox/filter map не передают → ничего не рендерится). Без изменений схемы БД.
Тесты `tests/test_assigned.py` (12, +2): map содержит участника с верным
инициалом/цветом, пустой map для неизвестного проекта. mypy strict + ruff +
lint_templates зелёные, Playwright залогиненным: на задаче виден аватар «R»
с тултипом, 0 console errors. Скрин `docs/screenshots/task-row-assignee-avatar.png`.

---

## 2026-05-21 — Ralph-loop: бейдж-счётчик «Назначено мне» в сайдбаре

Продолжение фичи /app/assigned. Новый `app.tasks.service.count_assigned_to_user`
(тот же фильтр, что у `list_assigned_to_user` — open, не в корзине, только
проекты-членства). Эндпоинт `GET /api/projects/sidebar-counts` расширен ключом
`"assigned"` (контракт `dict[str,int]` — только новый ключ). В
`_partials/sidebar.html` пункт `assigned` в `secondary_nav` получил бейдж по
паттерну inbox/today (`x-show counts['assigned']>0`). Без изменений схемы БД.
Тесты `tests/test_assigned.py` (10, +4): count матчит list, исключает
завершённые/непринадлежащие, эндпоинт отдаёт ключ `assigned`, 401 без auth.
mypy strict + ruff + lint_templates зелёные, curl эндпоинт → 401, Playwright
0 console errors, эндпоинт в браузере вернул `"assigned":0`. Скрин
`docs/screenshots/sidebar-assigned-badge.png`.

---

## 2026-05-21 — Ralph-loop: фикс console-ошибки чипа стрика в топбаре

Чип стрика в `_partials/topbar.html` инициализировал `s: null` и фетчил
`/api/stats/streak`; `x-show` скрывал элемент, но Alpine всё равно вычислял
`:title` и `x-text="s.current"` при init → `Uncaught TypeError: Cannot read
properties of null (reading 'current')` на ВСЕХ `/app/*` у нового юзера без
streak. Фикс: дефолт `s: { current: 0, longest: 0, today_done: false }` вместо
null, `x-show="s.current > 0"`. Поведение чипа не изменилось. Playwright-смоук
залогиненным юзером без стрика: `/app/today` и `/app/assigned` теперь **0
console errors** (было 2). Скрин `docs/screenshots/topbar-streak-fix-no-console-errors.png`.
Найден в прошлой итерации при смоуке /app/assigned.

---

## 2026-05-21 — Ralph-loop: вид «Назначено мне» (assigned to me)

Аддитивная team-collab фича поверх δ. Новый сервис
`app.tasks.service.list_assigned_to_user` — открытые (не завершённые, не в
корзине) задачи, назначенные текущему юзеру, по всем проектам где он участник
(фильтр через `member_project_ids`, чтобы stale-назначение из проекта, откуда
юзера убрали, не утекало). Веб-роут `GET /app/assigned` (`app/views/router.py`),
шаблон `app/templates/app/assigned.html` (группировка по проекту, переиспользует
`_partials/task_row.html`, пустое состояние), ссылка в сайдбаре (блок «Ещё»).
Без изменений схемы БД. Тесты `tests/test_assigned.py` (6) зелёные, mypy strict
чист, ruff/lint_templates чисто, curl `/app/assigned` → 401, Playwright-смоук
залогиненным OK (скрин `docs/screenshots/assigned-empty.png`).

**Замечен предсуществующий баг** (не из этой задачи): чип стрика в топбаре
кидает `Cannot read properties of null (reading 'current')` на всех `/app/*`
для нового юзера без streak-данных — кандидат на отдельную задачу.

---

## 2026-05-22 — Ralph-loop: массовое «Вернуть в работу» (uncomplete) в bulk-баре

Обратное к bulk «Завершить»: ветка `uncomplete` в `bulk_action` (uncomplete_task
по выбранным) + кнопка «↩ Вернуть» в bulk_bar.html (статичная hx-post форма).
`uncomplete_task` уже был. Без изменений схемы БД/эндпоинтов. Тест в
`tests/test_bulk.py`, `pytest -q` 752 passed. Playwright: 2 завершённые на
/app/done → «Вернуть» → обе active, 0 console errors. Скрин
`docs/screenshots/bulk-uncomplete.png`. Деплой: prod `/version` sha=05a8dec за
~25с, smoke 25/25 green. Commit `05a8dec`.

---

## 2026-05-22 — Ralph-loop: хоткей a — назначить выделенную задачу на меня

Клавиатурный triage: на выделенной (j/k) задаче `a` → назначить на себя
(дополняет c/1-4/t/w/e/p/Delete). Фронт-only: ветка `a` в `task_keyboard.html`
через существующий `patchSelected({assigned_to: me})` (me из `#task-ctx-menu`
data-me) + подсказка в shortcuts overlay. Без бэкенда/схемы. Тест
`tests/test_assign_hotkey.py`, `pytest -q` 751 passed. Playwright: j→a → БД
assigned_to==me (API), после reload аватар в строке, 0 console errors. Скрин
`docs/screenshots/assign-hotkey-a.png`. Деплой: prod `/version` sha=8cadacc за
~15с, smoke 25/25 green. Commit `8cadacc`. (Worklog: 2 заметки по тестам —
persisted localStorage-фильтры скрывают строки в смоуке; htmx row-swap не
освежает data-атрибуты внешнего wrapper.)

---

## 2026-05-22 — Ralph-loop: кнопка «Восстановить всё» в корзине (bulk restore)

Симметричный комплемент к «Очистить корзину»: массовое восстановление всех
soft-deleted задач. Без изменений схемы БД: `restore_all_trashed` (UPDATE
deleted_at=NULL, rowcount через cast CursorResult), `POST
/api/tasks/trash/restore` → `{"restored": n}` (объявлен до `/{task_id}/restore`),
кнопка «↩ Восстановить всё» в trash.html (без confirm). Тесты в
`tests/test_trash_bin.py` (+3), `pytest -q` 750 passed. Playwright: 3 удалённые →
«Восстановить всё» → корзина пуста, все вернулись, 0 console errors. Скрин
`docs/screenshots/trash-restore-all.png`. Деплой: prod `/version` sha=f08cf89 за
~25с, smoke 25/25 green. Commit `f08cf89`.

---

## 2026-05-22 — Ralph-loop: горячие клавиши g m / g e (Команда / Назначено мне)

Goto-шорткаты покрывали ~12 вью, но не teams-хабы. Добавил `g m` → /app/team и
`g e` → /app/assigned в `shortcuts.html` (g-ветка + overlay-справка). Фронт-only,
без бэкенда/схемы. Тест `tests/test_goto_shortcuts.py`, `pytest -q` 747 passed.
Playwright: g+m → Команда, g+e → Назначено мне, overlay показывает обе строки, 0
console errors. Скрин `docs/screenshots/goto-shortcuts-overlay.png`. Деплой: prod
`/version` sha=884d0ef за ~25с, smoke 25/25 green. Commit `884d0ef`. (Заметка по
тестам шорткатов в Playwright — в worklog: blur активного инпута + диспатч обоих
keydown подряд, т.к. pendingG живёт 1500мс.)

---

## 2026-05-22 — Ralph-loop: бейдж комментариев 💬 N на хабах Команда/Назначено

Бейдж «💬 N» был только в списке/доске проекта; добавил на кросс-проектные
teams-хабы `/app/team` и `/app/assigned`. Без изменений схемы БД/эндпоинтов/
шаблонов: `team_view` и `assigned_view` считают `comment_count_map`
(`comment_counts_for`) и кладут в контекст; task_row уже рендерит чип gated через
`comment_count_map is defined`. Тесты `tests/test_comment_badge_hubs.py` (3),
`pytest -q` 746 passed. Playwright: коммент к задаче → `/app/team` показал «💬 1»,
0 console errors. Скрин `docs/screenshots/comment-badge-team-view.png`. Деплой:
prod `/version` sha=d389ae7 за ~35с, smoke 25/25 green. Commit `d389ae7`.

---

## 2026-05-21 — Ralph-loop: поиск находит задачи команды в общих проектах

Глобальный поиск искал задачи только созданные мной (`Task.user_id == user`) —
задачи напарников в shared-проектах не находились (хотя поиск проектов уже шёл по
членству — рассогласование). Сменил фильтр задач на `Task.project_id IN
member_project_ids`; JSON project-name lookup тоже по member_ids. Без изменений
схемы БД и эндпоинтов; выдача строго ⊇ прежней в пределах прав (member_ids
включает личные проекты). Тесты `tests/test_search_team.py` (3), `pytest -q` 743
passed. Playwright: teammate создал задачу в shared-проекте → owner находит её
(JSON + живой ⌘K keyup), project_name резолвится, 0 console errors. Скрин
`docs/screenshots/search-team-tasks.png`. Деплой: prod `/version` sha=d0987ef за
~50с, smoke 25/25 green. Commit `d0987ef`.

---

## 2026-05-21 — Ralph-loop: «Создал: <участник>» в панели задачи

В детали-панели теперь виден автор задачи (создатель) для shared-проектов —
командная подотчётность (раньше виден только assignee). Без изменений схемы БД и
эндпоинтов: `task_detail` зовёт `assignee_map_for_project` → `is_shared` +
`creator = map[task.user_id]` (без доп. запроса), `task_detail.html` рисует
строку «Создал: аватар+email» в мета-футере, gated `is_shared` (одиночные
проекты не меняются), fallback «бывший участник». `Task.user_id` = создатель уже
есть. Тесты `tests/test_task_creator.py` (3), `pytest -q` 740 passed. Playwright:
деталь в shared-проекте → «Создал: trashpurge@example.com», 0 console errors.
Скрин `docs/screenshots/task-creator-detail.png`. Деплой: prod `/version`
sha=e16d862 за ~25с, smoke 25/25 green. Commit `e16d862`.

---

## 2026-05-21 — Ralph-loop: массовое «Назначить на участника» в bulk-баре

Дополнение к bulk «На меня»/«Снять»: дропдаун «Назначить» назначает выделенные
задачи на конкретного участника проекта. Без изменений схемы БД и эндпоинтов:
ветка `assign_user` в `bulk_action` (assignee_id → update_task(assigned_to),
не-member пропускается), дропдаун в `bulk_bar.html` определяет общий проект
выделения по `data-project`, грузит `/api/projects/{id}/members`. Переиспользует
паттерн дропдауна «Секция» 1:1 (common-project detection + ручной fetch, не
hx-post — Alpine-динамика). Тесты `tests/test_bulk_assign_user.py` (3), `pytest
-q` 737 passed. Playwright: 2 задачи → «Назначить» → teammate → обе
`data-assignee` = id напарника, URL чистый, 0 console errors. Скрин
`docs/screenshots/bulk-assign-member.png`. Деплой: prod `/version` sha=8d62db0 за
~50с, smoke 25/25 green. Commit `8d62db0`.

---

## 2026-05-21 — Ralph-loop: массовое «Перенести в секцию» в bulk-баре

Дополнение к bulk «В проект»: дропдаун «Секция» раскладывает выделенные задачи по
секциям проекта за раз. Без изменений схемы БД и эндпоинтов: ветка `set_section`
в `bulk_action` (пусто → clear_section, иначе section_id; чужой проект/секция
пропускаются), дропдаун в `bulk_bar.html` определяет общий проект выделения по
`data-project`, грузит `/api/sections`. **Урок:** Alpine-генерируемые лениво
`hx-post`-формы htmx не процессит → срабатывал нативный GET (`?ids=...`, задачи не
двигались, Playwright поймал); переписал на ручной `fetch().then(reload)` как у
date-пикера. Записал в память [[feedback_htmx_alpine_dynamic_forms]]. Тесты
`tests/test_bulk_section.py` (3), `pytest -q` 734 passed. Playwright: 2 задачи →
«Секция» → «В работе» → обе в section-контейнере, 0 console errors. Скрин
`docs/screenshots/bulk-move-to-section.png`. Деплой: prod `/version` sha=0da0c3b
за ~70с, smoke 25/25 green. Commit `0da0c3b`.

---

## 2026-05-21 — Ralph-loop: инлайн-превью описания задачи (📝)

У задач с описанием в строке появилась кнопка 📝, раскрывающая отрендеренный
markdown инлайн (без detail-панели), как аккордеоны подзадач/комментов.
Фронт-only: `descOpen` в `x-data`, текст описания в `<script
type="application/json" id="desc-data-<id>">{{ ...|tojson }}</script>` (безопасно
от XSS/поломки атрибута), слот `desc-slot-<id>`, рендер `window.dodayMd`
(XSS-safe). Селекторы в `@click` одинарными кавычками — без Alpine quoting trap.
Работает на всех вью с task_row. Бэкенд/схему не трогал. Тесты
`tests/test_desc_preview.py` (2), `pytest -q` 731 passed. Playwright: `**Жирный**`
→ `<strong>`, `код` → `<code>`, тоггл off, без описания кнопки нет, 0 console
errors. Скрин `docs/screenshots/task-desc-preview.png`. Деплой: prod `/version`
sha=bba8770 за ~60с, smoke 25/25 green. Commit `bba8770`.

---

## 2026-05-21 — Ralph-loop: вид «Команда» (team workload)

Кросс-проектный обзор всей команды: открытые задачи всех участников
shared-проектов, сгруппированные по исполнителю (дополняет «Назначено мне» —
только свои). Новый `membership.shared_project_ids` (проекты юзера с >1
участником), `tasks.service.list_team_tasks` (открытые задачи по shared, без
completed/trashed), веб-роут `GET /app/team` + шаблон `team.html` (группы по
участнику + «Не назначено», переиспользует task_row), ссылка «Команда» в
сайдбаре, `/app/team` добавлен в smoke_test (25 endpoint). Без изменений схемы БД
и API. Тесты `tests/test_team_view.py` (5), `pytest -q` 729 passed. Playwright:
shared-проект owner/teammate/none → 3 группы (teammate·1, trashpurge·1, Не
назначено·1), 0 console errors. Скрин `docs/screenshots/team-view.png`. Деплой:
prod `/version` sha=5722e04 за ~15с, smoke 25/25 green. Commit `5722e04`.

---

## 2026-05-21 — Ralph-loop: фильтр по исполнителю на канбан-доске

В list-вью фильтр по исполнителю был (f2025c3), на доске — нет (у доски не было
тулбара вообще). Добавил чипы «Все · Мои · Не назначено · участники» над доской.
Чистый клиент: логика в `<script>`-функции `window.applyKanbanAssigneeFilter`
(прячет `.kanban-card` по `data-assignee`, пересчитывает счётчики колонок),
Alpine-`x-data` держит только состояние + персист localStorage и зовёт функцию —
**намеренно без селекторов с двойными кавычками в x-data** (обход Alpine quoting
trap f2025c3). Gated `assignee_map|length>1`. Данные (`data-assignee` на kcard,
`assignee_map`, `current_user`) уже были. Тесты `tests/test_kanban_assignee_filter.py`
(2), `pytest -q` 724 passed. Playwright: доска owner/teammate/none → Все=3/Мои=1/
Не назначено=1, 0 console errors (нет SyntaxError). Скрин
`docs/screenshots/kanban-assignee-filter.png`. Деплой: prod `/version` sha=f8d6f8c
за ~50с, smoke 24/24 green. Commit `f8d6f8c`.

---

## 2026-05-22 — Ralph-loop: команды-навигация в ⌘K-палитре (launcher)

⌘K-палитра только искала. Превратил в launcher: в `search_palette.html` x-data
получил `q`, массив `commands` (11 целей с эмодзи), геттер `matchedCommands`
(live-фильтр), `go(url)`; инпут — `x-model="q"` рядом с htmx-поиском; блок
«Перейти» с `x-for` над результатами. Пустой `q` → все команды; ввод фильтрует.
Только шаблон, без схемы/эндпоинтов; htmx-поиск/⌘K/Escape не тронуты. Тест +1,
`pytest -q` 777 passed. Playwright: open-search → 11 команд, ввод «ком» →
остаётся «Команда», клик → `/app/team`, 0 console errors. Скрин
`docs/screenshots/palette-commands.png`. Деплой: prod `/version` sha=84d3caf,
smoke 25/25 green. Commit `84d3caf`.

---

## 2026-05-22 — Ralph-loop: бейджи подзадач и комментариев на ежедневных вью

Бейджи `X/Y` (подзадачи) и `💬 N` (комменты) были только на project/kanban. Добавил
их на «Сегодня» и «Ближайшие» (прокинул `subtask_counts` + `comment_count_map` в
`today_view`/`upcoming_view`), и добил недостающий `subtask_counts` в
`assigned_view`/`team_view` — единообразие по всем кросс-проектным вью. Только
`router.py` (контекст), шаблоны не тронуты — `task_row.html` рисует под гейтом
`is defined`; хелперы одним запросом. Тесты +3, `pytest -q` 776 passed.
Playwright: задача с 2 подзадачами+комментом на today → бейджи `0/2` + 💬, 0
console errors. Скрин `docs/screenshots/today-badges.png`. Деплой: prod
`/version` sha=ab5abcb, smoke 25/25 green. Commit `ab5abcb`.

---

## 2026-05-22 — Ralph-loop: кнопка «Поделиться» в панели деталей

Copy-link был только в контекст-меню. Добавил в шапку панели деталей кнопку
share-иконкой: копирует `origin+pathname+?task={id}` в буфер + тост `dodayToast`.
Переиспользует существующий deep-link `?task=` (открывает деталь на загрузке) и
тост-хелпер. Только `task_detail.html`, без схемы/эндпоинтов. Тест +1,
`pytest -q` 773 passed. Playwright: стаб clipboard → клик «Поделиться» →
захвачен корректный URL `…/app/today?task=<id>`, 0 console errors. Скрин
`docs/screenshots/task-share-link.png`. Деплой: prod `/version` sha=407b6d3,
smoke 25/25 green. Commit `407b6d3`.

Примечание: фичи без миграций почти исчерпаны; крупные оставшиеся идеи
(полноценные @mentions с уведомлениями, атрибуция завершений в ленте) требуют
схемы (`completed_by`, notifications) — на отдельный заход с миграцией.

---

## 2026-05-22 — Ralph-loop: вкладка «Активность» на странице проекта

Глобальная `/app/activity` показывала активность только текущего юзера. Добавил
пер-проектную ленту: ветка `view == "activity"` в `project_view` →
`_project_activity_view` собирает created/completed задачи + комментарии по
проекту за 30 дней (все участники), группирует по дням, у created/comment ставит
`actor` из `assignee_map_for_project` (completed — без актора, поля completed_by
нет, схему не трогаем). Новый шаблон `project_activity.html` (шапка + таб
Список/Доска/Активность + лента с аватаром автора), третья вкладка в
project/kanban. Без схемы/новых таблиц/эндпоинтов. Тесты +3, `pytest -q` 772
passed. Playwright: 4 события (завершено без аватара, коммент+создал×2 с
аватаром), 0 console errors. Скрин `docs/screenshots/project-activity.png`.
Деплой: prod `/version` sha=677f7e3, smoke 25/25 green. Commit `677f7e3`.

---

## 2026-05-22 — Ralph-loop: drag задач между секциями на list-виде

На list-виде задачи таскались только внутри секции (изолированные Sortable без
`group`); перенос — только через контекст-меню. Канбан cross-column умел давно.
Добавил каждому `.sortable-tasks` `group: 'tasks-{project.id}'` и переписал
`onEnd(evt)`: при `evt.to !== evt.from` → `PATCH /api/tasks/{id}
{section_id: evt.to.dataset.sectionId || null}` + reorder целевого контейнера;
внутри контейнера — прежний reorder. Используются существующие эндпоинты, без
схемы. Тесты +2, `pytest -q` 768 passed (один flaky `test_subtasks…today` —
полуночная гонка в самом тесте, в изоляции зелёный). Playwright: программный
вызов реального onEnd → после reload сервер рендерит задачу во второй секции
(PATCH сохранился), 0 console errors. Скрин
`docs/screenshots/drag-between-sections.png`. Деплой: prod `/version`
sha=fdd70bd, smoke 25/25 green. Commit `fdd70bd`.

---

## 2026-05-22 — Ralph-loop: фильтр по сроку на странице проекта

Завершил тройку фильтров проекта (исполнитель/лейбл/срок). В `project.html`
добавлен `dueFilter` (persist `doday-due-filter-{id}`), `_passesDue`
(overdue/today/week/nodate/dated, нормализация даты как в `_groupKey`),
`setDueFilter`, chip+dropdown «Срок». Общий display-проход теперь
`_passesAssignee && _passesLabel && _passesDue` (AND); восстановление секций при
всех фильтрах 'all'. Без схемы/эндпоинтов; `task_row` не тронут (`data-due` был).
Тест +1, `pytest -q` 767 passed. Playwright: 3 задачи (сегодня/без даты/
просрочено) → каждый фильтр показывает ровно свою, «Все» → все три; 0 console
errors. Скрин `docs/screenshots/due-filter.png`. Деплой: prod `/version`
sha=1e214ac, smoke 25/25 green. Commit `1e214ac`.

---

## 2026-05-22 — Ralph-loop: «Скопировать выделенные» в bulk-баре

Продолжение select-all: кнопка в bulk-баре кладёт выделенные задачи в буфер
обмена markdown-чек-листом (`- [ ] Название`) — для стендапа/чата. На обёртку
задачи/карточку добавлен `data-title-text` (точный регистр; `data-title` —
нижний). В root x-data bulk-бара метод `copySelected()` (ids из store → titles
из dataset → markdown → `navigator.clipboard.writeText`), кнопка с локальным
`copied`-флагом → зелёная галочка «Скопировано ✓» на 1.5с. Чистый фронт, без
схемы/эндпоинтов. Тесты +2, `pytest -q` 766 passed. Playwright: 16 задач, стаб
clipboard, select-all → клик → 16 строк `- [ ]` с точными заголовками, 0 console
errors. Скрин `docs/screenshots/copy-selected.png`. Деплой: prod `/version`
sha=71249b2, smoke 25/25 green. Commit `71249b2`.

---

## 2026-05-22 — Ralph-loop: аватар исполнителя в «Сегодня»/«Ближайшие»

Аватар-исполнителя был только на странице проекта и в командном виде, а в
кросс-проектных списках «Сегодня»/«Ближайшие» член команды не видел, кто
отвечает за задачу из общего проекта. Добавил `assignee_map_for_projects`
(объединённый map по нескольким проектам, один `distinct`-запрос; общая
initial/color/label-логика вынесена в `_avatar_data`) и в `today_view`/
`upcoming_view` прокидываю `assignee_map` по project_ids показанных задач ∩
`shared_project_ids` (только общие проекты — чтобы не было шума на личных).
Шаблоны не тронуты — `task_row.html` уже рисует аватар. Solo-юзер не замечает
изменений (пустой map). Без схемы/эндпоинтов. Тесты +4 (merge/empty юнит +
интеграционные today: общая задача показывает аватар, личная — нет),
`pytest -q` 764 passed. Playwright: /app/today и /app/upcoming грузятся, 0
console errors. Скрин `docs/screenshots/today-assignee-avatar.png`. Деплой:
prod `/version` sha=5cf9732, smoke 25/25 green. Commit `5cf9732`.

---

## 2026-05-22 — Ralph-loop: «Выделить всё» для массовых действий

Массовые действия мощные, но не было способа выделить все задачи разом — только
поштучно/shift-диапазонами. Добавил в store `selection` (`app_base.html`)
`visibleIds()` (только видимые строки через `offsetParent !== null` — уважает
фильтры/свёрнутые секции), `selectAll/allSelected/toggleAll`, и хоткей Ctrl/Cmd+A
→ `toggleAll()` с гардом полей (в INPUT/TEXTAREA/SELECT/contentEditable — нативное
выделение текста). В `bulk_bar.html` — кнопка «Выделить все видимые». Чистый
фронт, без схемы/эндпоинтов. Тесты +2, `pytest -q` 760 passed. Playwright: 16
задач → Ctrl+A выделяет все 16, повтор → 0, в поле Ctrl+A не срабатывает, кнопка
работает; 0 console errors. Скрин `docs/screenshots/select-all.png`. Деплой:
prod `/version` sha=824aaad, smoke 25/25 green. Commit `824aaad`.

---

## 2026-05-22 — Ralph-loop: фильтр по лейблу на странице проекта

В тулбаре проекта был фильтр по исполнителю, но не по лейблу. Добавил
клиентский фильтр по лейблу по образцу assignee-фильтра: на обёртку задачи
(`task_row`/`kanban_card`) — `data-labels` (пробел-разделённые id), в
`project_view` собирается `project_labels` (str-keyed dict уникальных лейблов
проекта из уже загруженных задач, `lazy="selectin"`, без доп. запросов),
script-тег `label-map-{id}` + Alpine `labelFilter` (persist
`doday-label-filter-{id}`) + `_passesLabel`, объединённый с assignee-фильтром в
одном display-проходе. Chip+dropdown «Лейбл» только при `{% if project_labels
%}`. Без схемы и новых эндпоинтов; сортировка/группа/assignee/секции не тронуты.
Урок-тест: shared-сессия кэширует пустую labels-коллекцию задачи → `expire_all()`
перед GET, id/slug захватить в локали до expire (иначе MissingGreenlet). Тесты
+2, `pytest -q` 758 passed. Playwright: выбор лейбла «work» → видна только
рабочая задача, возврат «Все» → обе; 0 console errors. Скрин
`docs/screenshots/label-filter.png`. Деплой: prod `/version` sha=0500401,
smoke 25/25 green. Commit `0500401`.

---

## 2026-05-22 — Ralph-loop: автор комментария в блоке комментариев

Под комментарием показывался только timestamp — в командном проекте не видно,
кто написал. Добавил чип автора: круглый аватар-инициал с цветом из палитры +
email, перед датой. Оба htmx-хендлера (`comments_block` GET, `comment_create`
POST) теперь подтягивают `author_map = assignee_map_for_project(session,
task.project_id)` и прокидывают в шаблон; `comments_block.html` рендерит чип под
гейтом `{% if author_map is defined %}` с fallback на серый «?» для автора вне
map. Без схемы (`Comment.user_id` уже был) и без новых эндпоинтов; CRUD/форма/
edit/delete не тронуты. Урок: тело коммента рендерится через Alpine `x-text` из
`{{ c.body|tojson|forceescape }}`, поэтому кириллица в HTML экранируется как
`\uXXXX` — тесты ассертят по автору (литеральный текст), тело ASCII. Тесты
+2 в test_comments.py, `pytest -q` 756 passed. Playwright: создан коммент →
виден аватар-инициал + email + дата, 0 console errors. Скрин
`docs/screenshots/comment-author.png`. Деплой: prod `/version` sha=18ffb9c,
smoke 25/25 green. Commit `18ffb9c`.

---

## 2026-05-24 — Telegram Stars (XTR) — единственный legal путь монетизации

Юзер 16 лет, ЮKassa требует 18+. Госуслуги (детская учётка), ручная анкета,
любой банк-эквайер — всё блокируется на проверке возраста по паспорту/счёту.
Открыть ИП тоже нельзя. Через родителя — пока не вариант. Stars работают с
13 лет (договор с Telegram), есть Mini App + бот-инфраструктура — всё
готово к интеграции.

**Schema (migration 0039):**
- `users.pro_until` (timestamp) — когда платная Pro истекает.
- `star_payments` — log платежей с UNIQUE на `telegram_payment_charge_id`
  (идемпотентность для re-delivered webhooks через IntegrityError).

**Каталог продуктов** (`app/billing/products.py`) — единственный source of
truth для цен: pro_1m=250⭐, pro_12m=2500⭐ (скидка 17%), pro_forever=12500⭐,
family_1m=500⭐, family_12m=5000⭐.

**Core service** (`app/billing/stars.py`):
- HMAC-SHA256 signed payloads `v1:{product}:{user_hex}:{nonce}:{sig}` —
  защищает от подмены product в URL. ≤80 байт, влезает в Telegram-лимит 128.
- `create_invoice_link(user, product)` → t.me-deeplink через Bot API.
- `validate_pre_checkout` — verify signature + amount mismatch (defence-in-depth).
- `apply_successful_payment` — idempotent, продлевает pro_until от
  `max(now, current)` + 30×months; lifetime → 2099 sentinel.
- `refund_payment` — refundStarPayment Bot API + откат pro_until.

**Bot handlers** (`app/telegram/bot.py`):
- `PreCheckoutQueryHandler` отвечает в 10 сек ok/error до списания.
- `MessageHandler(filters.SUCCESSFUL_PAYMENT)` → apply + благодарность.

**HTTP endpoints:**
- `POST /api/billing/stars/invoice`, `GET /api/billing/stars/payments`,
  `GET /api/billing/products`, `GET /api/billing/me` теперь с `pro_until`.
- **SECURITY FIX**: `POST /api/billing/change-tier` upgrades теперь 402.
  Раньше любой залогиненный юзер мог POST'нуть {tier:pro} и стать Pro
  бесплатно — это был gap из аудита 2026-05-22. Закрыли вместе с
  появлением платной альтернативы.
- Admin: `GET /api/admin/billing/payments` + `POST .../{id}/refund`.

**effective_tier** теперь учитывает pro_until: lapsed → free автоматически
без cron-задачи, lazy eval на каждом запросе.

**UI:**
- `/miniapp/me` — карточка «⭐ Купить Pro» с 5 продуктами →
  `Telegram.WebApp.openInvoice(url, callback)`.
- `/app/settings` — карточка «⭐ Подписка» в верху с текущим сроком +
  кнопками покупки (window.open для десктопа).
- `/pricing` — кнопки Pro/Family теперь активные с реальными ⭐ ценами
  (вместо «Скоро — настраиваем ЮKassa»).
- Help-статья `stars-payments` с полной инструкцией.

**Тесты** (`tests/test_stars_payments.py`, 24 теста):
- HMAC sign/verify, tampered payload отвергается (product, user_id, malformed)
- Payload ≤128 байт
- Pre-checkout amount mismatch отвергается
- apply_successful_payment idempotent (same charge_id → один row, не двойной
  extend)
- Renewal extends from existing pro_until, lifetime → year 2099
- effective_tier: expired→free, active→pro/family
- /api/billing/products listing
- change_tier upgrade → 402, downgrade → 200
- Catalog internal consistency (codes unique, year cheaper per-month)

Существующие тесты адаптированы — `_make_user` в test_tier_enforcement
выставляет `pro_until` при tier=pro/team/family, иначе эффективный тариф
теперь падает обратно на free.

Commits: `f3175ae` (infra + UI + security fix) → `fe041d0` (pricing + help) →
`766bb84` (test fix). Prod на `766bb84`, smoke 26/26 ✓, full suite 858/858 ✓.

---

## 2026-05-24 — Разделил «Функции» / «Эксперименты» + пресеты + «🎓 Учёба» + фикс сайдбара

Юзер: «Я попробовал повключать разные экспериментальные функции, но почему то
вкладки слева не начали появляться как раньше. Сделай чтобы автоматически
синхронизировался дневник и чтобы это всё было в отдельной вкладке учёба, а
проекты тоже пусть будут в настройках чтоб можно было включить. И сделай
пресеты — типо школьнику, студенту, максимум — нажал и всё включается.»

Четыре изменения за один пуш (commit `b68dc71`):

**1. Фикс сайдбара.** Раньше когда юзер включал, например, эксп. `graph`,
ссылка `/app/graph` рисовалась — но ВНУТРИ свёрнутого `<details «Ещё»>`. Юзер
включал и думал «не работает». Теперь когда любая фича включена, появляется
секция «Дополнительно» в основном сайдбаре между «Фильтры» и «Избранное» —
выше fold, всегда видна. Опустошённую секцию из `<details «Ещё»>` удалил.

**2. Stable vs experimental split в `/app/settings`.** В `Experiment` появился
новый `stage="stable"`. Две секции на странице:
- ✨ **Дополнительные функции** (stable): school, graph, calendar_feed,
  user_templates.
- 🧪 **Экспериментальные функции** (alpha): habits, mood, time_tracking,
  achievements.

Toggle-row вынес в новый партиал `_partials/_experiment_toggle.html` (DRY
между секциями).

**3. School как stable-фича + новая вкладка «🎓 Учёба».** Школьный синк
больше не «всегда вкл» — теперь опт-ин через `school` флаг. Когда вкл:
- В сайдбаре появляется «🎓 Учёба».
- Открывается `/app/school` — hub-view: подключённые порталы со статусами и
  кнопкой «↻ Синхр.», список ближайшей домашки, компактная сетка расписания,
  ссылки на полную страницу `/app/schedule` и `/app/settings#school`.
- Авто-синк на `/today` теперь срабатывает ТОЛЬКО когда `school` on +
  есть интеграция.

**4. Пресеты.** Новый `app/experiments/presets.py` с 4 пресетами:
- **Минимум** — нулевая конфигурация (чистый Todoist-like)
- **Школьник** — habits + achievements + mood + school
- **Студент** — graph + calendar_feed + user_templates + habits + time_tracking
- **Максимум** — все эксперименты включены

Endpoint `POST /api/profile/experiments/preset/{key}` bulk-replace'ит весь
реестр флагов одним запросом. UI: первая секция в `/app/settings` — 4 кнопки
в grid'е.

Tests: 30/30 (experiments +5 = 22, user_templates 8) green. Smoke 26/26 на
prod. mypy strict + ruff + lint_templates зелёные. Commit `b68dc71`.

---

## 2026-05-24 — Доделал revival-батч (user_templates + timer UI + habit widget + help)

Юзер: «работай долго». Закрыл хвост revival'ов и допилил UX для уже
воскрешённых эксп-функций, чтобы они были не только в API, но и в живом
интерфейсе.

### user_templates (7-й эксперимент)
- Миграция **0038** пересоздаёт `user_templates` (1-в-1 с 0008).
- Восстановлен `app/user_templates/{models,router,service}.py` из истории.
- Снял `require_pro` гейт с save-as-template — теперь это эксперимент,
  доступен всем без Pro-tier.
- `Experiment(key='user_templates', stage='alpha')` в реестре.
- В `app/templates/app/project.html` кнопка «📁 Сохранить как шаблон»
  под guard'ом `current_user.experiments.get('user_templates')`. Alpine
  helper `dodaySaveAsTemplate` — prompt → POST → toast.
- Лендинг: feature-card описание сделан честным («Сохранение своих
  шаблонов — экспериментально»), в comparison-table добавлена строка.
- Тесты `tests/test_user_templates.py` восстановлены, button-тест
  переписан под experimental-pattern (off→hidden, on→visible).
- Commit `d95683b`.

### Per-task ▶/⏸ таймер в task_detail
- `app/views/htmx.py::task_detail`: добавил `time_tracking_enabled` +
  server-preload `total_seconds_for_task` и `running` state.
- `app/templates/_partials/task_detail.html`: новый блок между
  «🔗 Связи» и «Комментарии» под guard'ом. Alpine x-data с
  live-tick (setInterval раз в секунду), MM:SS / H:MM:SS, тосты.
- +2 теста в `test_experiments.py` (visibility + running-state).
- Commit `341b133`.

### Habit quick-checkin виджет на /today
- `app/templates/_partials/habit_widget.html`: новый компонент. Grid
  1/2 колонки, fetch `/api/habits` → топ-5 активных. Чекин/унчекин
  через POST/DELETE `/api/habits/{id}/checkin`, обновляет state +
  тостит. Стрики и рекорды видны в каждой карточке.
- Подключён в `today.html` под guard'ом `experiments.habits` —
  рядом с уже существующими mood и sprint widgets.
- +1 тест в `test_experiments.py` (off→hidden, on→visible).
- Commit `ec86b7d`.

### Help articles (6 новых статей про эксперименты)
- `app/help/articles.py`: +6 ARTICLES.append блоков. Слаги:
  calendar-feed, habits, mood, time-tracking, achievements,
  user-templates. У каждой статьи структура: что это, зачем, как
  включить, что попадает / что не попадает в данные, нюансы.
- В реестре статей было 19, стало 25.
- Commit `234abde`.

### Итог revival-batch'а (накопительно за 2026-05-23 + 2026-05-24)
- 7 эксп-функций в реестре: graph, calendar_feed, habits, mood,
  time_tracking, achievements, user_templates.
- 7 миграций 0032-0038 (флаги + по таблице на эксп).
- Все API доступны без gate'а, UI gated через
  `current_user.experiments.get('<key>')`.
- 17 тестов в `test_experiments.py` + 7 в `test_user_templates.py`.
- 6 справочных статей.

Стратегия: ничего не удаляется обратно из репозитория, всё
живёт за тумблером. Юзер, который не хочет графов / привычек /
бейджей / шаблонов — не увидит их.

---

## 2026-05-24 — Воскресил mood + time-tracking + achievements (теперь 6 эксп.)

Юзер снова сказал «работай долго, доделай всё, используй superpowers». Добил
весь хвост удалённого в phase α по той же схеме revival'ов.

### Mood (трекер настроения)
- Миграция **0035** воссоздаёт `mood_entries` (1-в-1 со старой 0019).
- Восстановлен модуль `app/mood/` + виджет `_partials/mood_widget.html`.
- `/api/mood/today` + history. Widget включается на `/today` только если
  `experiments.mood`.
- Эксп `mood` (alpha) в `AVAILABLE`.

### Time-tracking (трекер времени)
- Миграция **0036** воссоздаёт `time_entries` (1-в-1 со старой 0018).
- Восстановлен модуль `app/time_tracking/` + виджеты
  `_partials/sprint_widget.html` и `school_streak.html` из истории.
- API `/api/time/*` (start/stop/total).
- Sprint widget включается на `/today` только если `experiments.time_tracking`.
- Эксп `time_tracking` (alpha) в `AVAILABLE`.

### Achievements / gamification (бейджи + XP)
- Миграция **0037** воссоздаёт `user_progress` (XP/level) + `user_achievements`
  (unlocked badges) — 1-в-1 со старыми 0024+0025.
- Восстановлены оба модуля: `app/achievements/` (router + service с компьютом
  unlocked) + `app/gamification/` (achievements catalog + daily challenges +
  XP/level service).
- Новая страница **`/app/achievements`** с гейтом — карточки бейджей, XP,
  level, % unlocked. Использует существующий API `/api/achievements`.
- Sidebar-link «🏅 Бейджи» (gated).
- Эксп `achievements` (alpha) в `AVAILABLE`.

### Лендинг — три новых строки в табличке
- «Трекер настроения ✓ (эксп.)»
- «Трекер времени ✓ (эксп.)»
- «Бейджи / XP ✓ (эксп.)»

### Тесты
`tests/test_experiments.py` теперь **14 тестов** — каждый эксп. имеет тест на
гейт + базовую операцию. Полный `pytest -q` зелёный.

### Реестр экспериментов: 6 опт-инов
1. graph (beta) — граф связей задач.
2. calendar_feed (beta) — .ics-подписка.
3. habits (alpha) — трекер привычек.
4. mood (alpha) — трекер настроения.
5. time_tracking (alpha) — таймер по задачам.
6. achievements (alpha) — бейджи + XP/levels.

### Долг (на потом)
- Полноценный UI таймера на каждой задаче (сейчас только API + sprint виджет).
- UI добавления привычек (если шаблон restored из истории — пройтись на свежий
  глаз; возможна минорная доработка).
- `user_templates` (тоже была удалена в phase α) — последняя крупная отстающая.
- `company / standup` — не относится к школьному фокусу, оставляем.

---

## 2026-05-23 — Доделал UI графа + воскресил .ics-фид и Привычки (3 экспа в реестре)

Юзер сказал «работай долго, доделай всё, используй superpowers». Продолжил
revival по той же экспериментальной инфре — три experiments теперь в реестре,
все опт-ин через Настройки.

### Доделанное по графу
- **UI «🔗 Связать с задачей»** в task-detail: Alpine-поиск через
  `/htmx/search?format=json` (использует уже существующий поиск), POST на
  `/api/tasks/{id}/links`, авто-reload панели после создания. Удаление связи
  кнопкой ×. Видно только когда эксп. `graph` включён.
- **Sidebar-link «🧪 Граф»** — рендерится в подменю «Ещё», только когда
  `current_user.experiments.get('graph')`.

### Воскрешение .ics calendar feed (`calendar_feed`)
- Восстановлен модуль `app/calendar_feed/` из git-history (`f1fe6537^`).
- Колонка `users.ical_token` уже была от миграции 0014 — миграция не нужна.
- Эндпоинты: `/api/calendar/all.ics` (cookie-auth), `/api/calendar/feed/{token}.ics`
  (публичный по signed-token — Apple/Google Calendar подписываются),
  `GET /api/profile/ical-token` + rotate.
- Гейт `_require_calendar_feed_experiment` на ical-token issuance/rotate (само
  потребление по токену — без гейта, чтобы старые подписки не ломались).
- В Settings UI добавлен inline-Alpine блок: получить URL подписки → копировать.

### Воскрешение Привычек (`habits`)
- Миграция **0034**: воссоздаёт `habits` + `habit_checkins` по схеме старой 0015.
- Восстановлен модуль `app/habits/` (model+router+schemas+service) из истории
  + шаблон `app/templates/app/habits.html` (150 строк).
- `/app/habits` роут с гейтом `is_enabled(user, 'habits')`.
- Sidebar-link «🧪 Привычки» с alpha-badge.

### Лендинг — таблица теперь правда вернулась
Добавил обратно строки «Трекер привычек ✓ (эксп.)» и «Календарь-фид (.ics) ✓
(эксп.)». «Граф связей задач» снова «✓ (эксп.)». Никакого вранья.

### Тесты + качество
- `tests/test_experiments.py` теперь 10 тестов: токгл, гейтинг /graph, /habits,
  /ical-token, public .ics token feed, link create end-to-end, no-self-link,
  settings рендер.
- Полный `pytest -q` зелёный (806+ tests).
- Per-file ignores в pyproject для греч.α / кириллицы в восстановленных модулях.

### Деплой
- Миграции 0034 на проде через alembic upgrade head.
- Smoke зелёный.

### Долг на следующие итерации
- **Achievements** (badges + progress page) — следующее revival по той же
  схеме (миграции 0024+0025 в истории, app/achievements/ + app/gamification/
  тоже восстановимы). Это была более крупная фича — отложил на отдельную
  сессию.
- **Mood log** (миграция 0019), **time-tracking** (0018) — мелкие, можно
  пачкой в один заход следующий раз.
- **Полноценное Pomodoro UI** на десктопе (миниапп его уже умеет).

### Паттерн revival'ов (для будущего меня)
1. Найти удаление в git: `git log --all --format="%H %s" | grep cleanup-α`.
2. `PARENT=<del>^; git show $PARENT:app/<feature>/...` → восстановить файлы.
3. Новая alembic-миграция, схема 1-в-1 со старой.
4. `Experiment(...)` в `AVAILABLE` в `app/experiments/service.py`.
5. Если есть view: `is_enabled(user, key)` гейт в роуте + sidebar-link.
6. Тест в `test_experiments.py` — гейт + базовая операция.

---

## 2026-05-23 — Честность лендинга + воскрешение графа задач как «эксп-функция»

Юзер увидел, что в табличке сравнения на лендинге заявлены фичи, которых нет
(«Граф связей задач ✓», «Открытый исходник MIT» без LICENSE, «Привычки и стрики»
с давно удалёнными привычками). И сразу попросил: вместо удаления старых
фич — вернуть их через опт-ин в Настройках.

### Честность сейчас
- LICENSE MIT добавлен в корень (был обещан, файла не было).
- В табличке `landing.html`: «Привычки и стрики ✓» → «Стрики (дни подряд) ✓»
  (без привычек, потому что привычки удалены). Уточнено
  «Граф связей задач ✓ (эксп.)».
- Help-статья `graph-and-links` переписана с пометкой «🧪 эксп., включи
  в Настройках».

### Инфра экспериментальных функций (одна точка для будущих revival'ов)
- Миграция `0032`: `users.experiments` JSONB (per-user opt-in flags).
- `app/experiments/service.py`: реестр доступных экспериментов
  (`AVAILABLE`, dataclass `Experiment` со stage `alpha`/`beta`),
  `is_enabled(user, key) → bool`.
- `POST /api/profile/experiments/{key}` — переключатель.
- Секция «🧪 Экспериментальные функции» в Настройках с тогглами по каждому;
  если включён `graph` — рядом ссылка «→ Открыть граф».

### Граф задач — revival как эксперимент (gated)
- Миграция `0033`: восстановила `task_links` (схема 1-в-1 со старой `0020`).
- Восстановлен модуль `app/links/` (model+service+schemas+router из git-history,
  коммита перед phase-α удалением).
- Восстановлен `app/templates/app/graph.html` (космический force-layout).
- Восстановлен `/app/graph` роут с гейтом: `is_enabled(user, "graph")` → или
  страница, или 303 на `/app/settings#experiments`.
- Wired в `main.py`: `links_router` + `graph_router`.
- API: `POST /api/tasks/{id}/links`, `DELETE /api/tasks/{id}/links/{link_id}`,
  `GET /api/links/graph`.

### Тесты + качество
- `tests/test_experiments.py` — 6 тестов: 422 на unknown, on/off гейтит /graph,
  settings рендерит секцию, /api/links/graph возвращает {nodes, edges},
  E2E создания связи, no-self-link.
- Прогон `pytest -q` зелёный, pre-commit (ruff + mypy strict + lint_templates)
  без ошибок (per-file-ignores для греческой α в docstring + Cyrillic в
  восстановленном модуле).

### Деплой
- Pushed.
- На проде применены миграции 0032+0033 через SSH (`alembic upgrade head`).
- Smoke зелёный.

### Долг на следующие итерации
- UI-кнопка «Связать с задачей» в детали задачи (сейчас API есть, кнопки
  ещё нет — связи можно создавать через консоль/curl).
- Возможные следующие revivals (та же инфра): habits, mood, time_tracking,
  achievements, .ics calendar feed. Каждое = миграция (восстановить таблицу из
  git) + 1 запись в `AVAILABLE` + соответствующий код.

---

## 2026-05-23 — Авто-синк школы на /today + 🔥-серия в шапке (полная автономия)

Юзер ушёл спать с полным мандатом «сам принимай все решения». Сделал две вещи
малого риска и большого мотивационного веса.

**Авто-синк школьного дневника** на `/app/today`: FastAPI `BackgroundTasks`
после ответа дёргает `lazy_sync_stale_integrations` — обновляет интеграции,
у которых `last_sync_at` старше 30 мин. Pre-check `has_integration` гасит
bg-задачу для 99% юзеров без школы. Helper ловит `BaseException` (на случай
`CancelledError` при teardown тестового event loop). Поведение: открыл
/today → если последняя синхронизация была давно → фоном тянется домашка,
страница не ждёт.

**🔥-серия (streak) в шапке /today**. `current_streak(session, user_id)` —
новый публичный helper в `stats/service.py`, переиспользует
`_completed_dates`+`_current_streak`. Шапка показывает «🔥 N дней» (clickable
на /app/stats). Если серия > 0 но сегодня ничего не сделано — мягкий нудж
«не сорви серию» под датой.

Полный `pytest -q` = **796 passed** (auto-sync helper + streak helper не
сломали ничего). Прод `eb40214`: smoke 25/25, `/app/today`→401 (auth-gate ок).

**Лонг-список UX-полировки на завтра** в `docs/ux-audit-2026-05-23.md`:
task-completion micro-animation, empty-state /app/projects, project-graph
view («где графы?» юзер спрашивал — это требует cytoscape.js через CDN +
визуализация parent_task_id дерева, без новой схемы), quick-add NLP полиш и
другое. Память [[project_simplify_direction]] обновлена: 2026-05-23
**частичный откат** «no gamification» — поверхностные мотивационные сигналы
(streak, confetti, joyful interactions) приветствуются, тяжёлые удалённые
модули (XP/levels/16-achievements/mood/habits) — нет.

**Урок (память [[feedback_test_db_concurrency]]):** не запускать два pytest
параллельно на `schooltodo_test` — `drop_all`/`create_all` дедлочатся,
выглядит как «duplicate user @logged-in» в setup-ах. Лечится pg_terminate_backend.

---

## 2026-05-23 — Доделал школьный парсер (Школьный портал МО, живой API)

Реанимация витринной школьной фичи (см. [[project_pivot]]). До этого fetch
ходил по угаданным путям без обязательных заголовков — портал не пускал.
Юзер прислал реальный запрос из браузера authedu.mosreg.ru → прописал точные
заголовки family-web Gravitee-шлюза: `X-mes-subsystem=familyweb`, `Profile-Id`,
`Profile-Type=student`, `X-Mes-RoleId`, `Authorization: Bearer`. Эндпоинт
`/api/family/web/v1/homeworks?from&to&student_id` подтверждён. Добавил
`student_id` (поле в форме + миграция 0031 + проброс в query/Profile-Id).
Нормализатор пропускает «не задано»/пустые (на реальной выборке их ~5 из 13).
Букмарклет теперь автотянет и `student_id` (cookie `active_student`) — клик по
закладке на портале → токен+student_id прилетают и сохраняются.

**Прокси не нужен — подтверждено.** Прод в Москве (79.137.237.2). С сервера
точный эндпоинт `/api/family/web/v1/homeworks?...` отвечает 401 за 0.16с (с
фейковым токеном) — доступен, не WAFится. Старая «Azure EU»-причина устарела
(переехали на РФ-хост), error-text обновил.

Качество: 16 школьных тестов (+ test_create_integration_stores_student_id +
test_import_skips_not_assigned_and_empty), pytest -q = 795 passed, pre-commit
зелёный. Прод 7d1b6a7: миграция 0031 накачена по SSH (DB at head), smoke 25/25,
school API живой (401, не 500). Commit `7d1b6a7`.

Юзеру: войти на портал → нажать закладку «📥 Получить токен Doday» (или вручную
ввести токен + student_id из URL дневника, у тебя 560752) → «Синхронизировать»
→ домашка станет задачами. После теста обязательно перелогиниться на портале —
тот токен из чата протухнет.

---

## 2026-05-23 — Мягкая верификация email (по итогам аудита, осознанное решение)

Email-верификация была несогласованной: парольный логин требовал подтверждение
(403 + риск локаута, сброса пароля нет), а Telegram-miniapp его не требовал.
Выбрал **мягкую** линию (лучше для роста/конверсии школьной+TG-аудитории):
неподтверждённые юзеры **входят и пользуются** приложением; письмо и
verify-эндпоинт остаются; подтверждённая почта требуется **только** для
email-дайджеста (он реально шлётся на почту). Убрал блок `EmailNotVerified` в
`authenticate` + ветку в логин-роуте (+ удалил мёртвый класс), повесил
verified-gate на `/api/profile/morning-digest`, переписал страницу после
регистрации («Аккаунт создан, можешь войти»). Тесты обновлены (login/authenticate
unverified → allowed) + добавлен тест гейта дайджеста. `pytest -q` = 793 passed.
Прод 59ad949: smoke 25/25; E2E — неподтверждённый юзер регается→логинится
(303 /app/today)→открывает /app/today (200). Commit `59ad949`.

---

## 2026-05-22 — Security-аудит (4 параллельных агента) + групповая ссылка прогресса

**Аудит** всей поверхности: access-control, auth/сессии, XSS/инъекции, CSRF/конфиг.
Фундамент крепкий — нет IDOR, SQLi, open-redirect, mass-assignment; секреты чисты.
Исправил 9 находок (все аддитивно, без схемы): (1) **HIGH** stored-XSS в
`dodayMd` — экранирование `"` (markdown-ссылки в описаниях/комментах могли
вырваться из `href`); (2) **CRITICAL** нет CSRF → same-origin middleware в
`main.py` (Origin/Referer vs Host, miniapp/taptower исключены); (3) `/docs`,
`/redoc`, `/openapi` off в prod; (4) TTL 90д на share/group токены; (5) кап
backup-импорта 5МБ+50k; (6) `max_length=5000` на reorder; (7) `session.clear()`
перед логином (web+miniapp); (8) `hmac.compare_digest` для admin/cron токенов;
(9) метка исполнителя `textContent` вместо `innerHTML`. `tests/test_security.py`
+5. Полный `pytest -q` = 792 passed. Прод 06598a1: smoke 25/25, /docs→404,
cross-origin POST→403, same-origin/no-origin POST→401 (юзеров не сломал).
Commits `132351f` (групповая ссылка) + `06598a1` (security).

**НЕ чинил (осознанно):** free-upgrade `change_tier` (замок = касса ЮKassa,
в очереди, ждёт самозанятость); email-верификация (политика — спросить юзера);
rate-limit в памяти (нужен Redis); CSP (нужен nonce-рефактор).

**Групповая ссылка прогресса** (Трек 2, чанк 2): публичный read-only
`/share/group/{token}` — преподаватель/родитель видит прогресс всех участников
класса (просрочено/осталось/сделано). Подписанный токен на project_id, ноль
схемы. Встроено в модалку «Поделиться проектом».

---

## 2026-05-22 — Монетизация: пивот на B2B + родительская панель (Трек 2, чанк 1)

Интерактивная сессия (Ralph-цикл остановлен на итерации 97). Диагностировал
**настоящие блокеры денег**: (1) кассы нет — `change_tier` пускает в Pro
бесплатно, ни одного провайдера; (2) «родительская панель» Family-тарифа — лишь
название, фичи не было. Стратегия в 3 трека (см. память `project_monetization.md`):
B2B репетиторским центрам (быстрые деньги, касса не нужна — счёт самозанятого),
Клод строит кассу+панель, контент TT/YouTube — долгий актив.

Реализовал **чанк 1 Трека 2 — публичная read-only ссылка прогресса** для
родителей/преподавателей. Подписанный токен (как email-верификация,
`app/share/service.py`), **ноль схемы** → безопасно для cron-poll деплоя без
миграций. Публичный `GET /share/progress/{token}` без авторизации и без единого
мутирующего эндпоинта → не трогает существующие права. Кнопка «Создать ссылку» в
настройках + `GET /api/profile/share-link`. `tests/test_share_progress.py` 6
тестов, полный `pytest -q` = 783 passed. Pre-commit зелёный. Прод `/version`
sha=c0a87be за ~20с, smoke 25/25, на проде битый токен→404, ссылка без auth→401.
Также добавил B2B-материалы `docs/sales/b2b-tutoring-centers.md`. Commits
`fb75359` (фича) + `c0a87be` (B2B-доки).

Примечание: Playwright MCP в этой сессии отключён — браузерного скрина нет,
проверял curl-ом + рендером HTML. Порт :8000 держит неубиваемый процесс из
прошлой сессии (access denied) — локально проверял на :8001.

---

## 2026-05-22 — Ralph-loop: кнопка «Свернуть/развернуть все секции»

На странице проекта секции сворачивались только поодиночке. Добавил тоггл в
тулбар (виден только при наличии секций, `{% if section_groups %}`): по клику
диспатчит `CustomEvent('doday-sections-toggle', {detail:{open}})`, подпись
«Свернуть секции» ↔ «Развернуть секции». Каждая `<section>` слушает
`@doday-sections-toggle.window="open = $event.detail.open"` и синхронно
сворачивается/разворачивается. Чисто фронт — без бэкенда/эндпоинтов/схемы.
Селекторы Alpine без вложенных двойных кавычек (профилактика x-data trap).
Тест `tests/test_collapse_sections.py` (2), `pytest -q` 754 passed. Playwright:
проект с 2 секциями → «Свернуть секции» → 0 видимых тел, обратно → 2 видимых, 0
console errors. Скрин `docs/screenshots/collapse-sections.png`. Деплой: prod
`/version` sha=3315fcd, smoke 25/25 green. Commit `3315fcd`.

---

## 2026-05-21 — Ralph-loop: «Перенести в секцию →» в контекст-меню

Дополнение к «Перенести в проект →»: быстрый перенос задачи между секциями
проекта из правого меню (на list и kanban). Фронт-only: новый пункт
`move-section` + сабменю в `task_context_menu.html`, лениво тянет `GET
/api/sections?project_id` (кэш по проекту, пункт виден только если секций ≥1),
клик → `PATCH /api/tasks/{id}` `{section_id}` (или null для «Без секции») →
reload. Бэкенд/эндпоинты/схему не трогал — PATCH уже умеет ставить/снимать
section_id. Опирается на `data-project` (есть на task-wrap и kcard). Тест
`tests/test_move_section_menu.py`, `pytest -q` 722 passed. Playwright: правый
клик → «Перенести в секцию →» → «В работе» → задача внутри section-контейнера, 0
console errors. Скрин `docs/screenshots/move-to-section-submenu.png`. Деплой:
prod `/version` sha=b824edf за ~30с, smoke 24/24 green. Commit `b824edf`.

---

## 2026-05-21 — Ralph-loop: контекст-меню (правый клик) на канбан-карточках

Богатое right-click меню работало только в list-вью (листенер матчил
`task-wrap-`), на доске карточки `kcard-` его не открывали. Включил меню на
канбане. Фронт-only: в `kanban_card.html` добавил `data-project`+`data-assignee`
на корень; в `task_context_menu.html` листенер теперь матчит и `task-wrap-` и
`kcard-` (id через regex-replace), плюс гварды для list-only DOM (`delete` без
wrap → reload; `comments`/`labels` без slot → открыть деталь). Бэкенд/эндпоинты/
схему не трогал. Тест `tests/test_kanban_context_menu.py`, `pytest -q` 721
passed. Playwright: правый клик по карточке доски → меню → «Назначить на →» →
teammate → карточка переназначена, 0 console errors. Скрин
`docs/screenshots/kanban-context-menu.png`. Деплой: prod `/version` sha=c751681
за ~50с, smoke 24/24 green. Commit `c751681`.

---

## 2026-05-21 — Ralph-loop: массовое «Снять назначение» в bulk-баре

Обратное к «На меня»: bulk-бар умел массово назначать на себя, но не снимать. Без
изменений схемы БД и эндпоинтов: новая ветка `unassign` в `bulk_action`
(`update_task(assigned_to=None)` по выбранным, чужие/несуществующие
пропускаются) + кнопка «Снять» в `bulk_bar.html` рядом с «На меня».
`update_task` уже умел снимать назначение через sentinel `_SENTINEL`. Тест
`test_bulk_unassign`, `pytest -q` 720 passed. Playwright: shared-проект, 3
назначенные задачи → «Снять» → у всех `data-assignee` пуст, 0 console errors.
Скрин `docs/screenshots/bulk-unassign-bar.png`. Деплой: prod `/version`
sha=e005d3d за ~40с, smoke 24/24 green. Commit `e005d3d`.

---

## 2026-05-21 — Ralph-loop: бейдж комментариев 💬 N на канбан-карточке

Паритет с list-вью: на канбан-доске карточки теперь показывают «💬 N» (в списке
бейдж был с a48e872, на доске — нет). Шаблон-only: в `kanban_card.html` чип рядом
с subtask/assignee/priority/due, gated через `comment_count_map`, плюс расширил
условие видимости meta-ряда на `_comments` (иначе карточка с одними комментами
не отрисовала бы ряд). Данные `comment_count_map` уже клались в контекст канбана
из `project_view` — бэкенд/схему не трогал. Тесты `tests/test_comment_counts.py`
(+2 на `?view=kanban`), `pytest -q` 719 passed. Playwright: kanban Inbox →
карточки «💬 1»/«💬 2», 0 console errors. Скрин
`docs/screenshots/kanban-comment-badge.png`. Деплой: prod `/version` sha=4d7e632
за ~40с, smoke 24/24 green. Commit `4d7e632`.

---

## 2026-05-21 — Ralph-loop: «Назначить на → участника» в контекст-меню

Контекст-меню умело только assign-me/unassign — переназначить на конкретного
напарника требовало открыть детали. Добавил подпункт «👤 Назначить на →» со
списком участников проекта. Без изменений схемы БД и без новых эндпоинтов: на
`task-wrap` добавлен `data-project`, меню лениво тянет `GET
/api/projects/{id}/members` (кэш по проекту), клик → `PATCH /api/tasks/{id}`
`{assigned_to}` → reload. Пункт показывается только в проектах с >1 участником
(ленивый members-fetch на открытии меню); свой помечен «(вы)», текущий — ✓. Весь
JS в `<script>`-блоке. Тесты `tests/test_assign_member_menu.py` (2), `pytest -q`
717 passed. Playwright: shared-проект 2 участника → меню → сабменю с обоими →
клик teammate → строка переназначена (data-assignee сменился), 0 console errors.
Скрин `docs/screenshots/assign-member-submenu.png`. Деплой: prod `/version`
sha=0e44b66 за ~60с, smoke 24/24 green. Commit `0e44b66`.

---

## 2026-05-21 — Ralph-loop: фильтр по исполнителю на доске проекта

На странице проекта была группировка по исполнителю, но не было фильтра — нельзя
сузить доску до задач одного человека. Добавил чипы «Все · Мои · Не назначено ·
<участники>». Чисто клиентский фильтр поверх существующих `data-assignee` +
`assigneeMap`, без бэкенда и схемы БД. В `project.html`: состояние
`assigneeFilter` (персист localStorage), `myId='{{ current_user.id }}'`,
`setAssigneeFilter`, `_passesAssignee`; интеграция — финальный `display`-проход в
существующем `apply()` (прячет неподходящие строки + пустые группы/секции, при
`all` секции восстанавливаются; snapshot/sort/group/drag не тронуты). Дропдаун
gated `assignee_map|length > 1`. Тесты `tests/test_assignee_filter.py` (2),
`pytest -q` 715 passed. **Урок:** двойные кавычки в селекторе внутри
double-quoted `x-data` ломали парсинг → Alpine SyntaxError рушил весь x-data (24
console errors в смоуке); заменил на `&quot;`. Рендер-тесты на httpx это не ловят
— Playwright обязателен. Playwright: shared-проект 2 участника, Все=3/Мои=1/Не
назначено=1, 0 console errors. Скрин `docs/screenshots/assignee-filter-mine.png`.
Деплой: prod `/version` sha=f2025c3 за ~15с, smoke 24/24 green. Commit `f2025c3`.

---

## 2026-05-21 — Ralph-loop: бейдж-счётчик комментариев 💬 N в строке задачи

В shared-проектах обсуждение в комментариях, но в списке не было видно, у каких
задач они есть. Новый `app.comments.service.comment_counts_for(session,
task_ids) -> dict[UUID, int]` — один group-by COUNT по `comments` (без N+1,
задачи без комментов отсутствуют), зеркалит `subtask_counts_for`. `project_view`
кладёт `comment_count_map` в контекст. Чип «💬 N» в `_partials/task_row.html`
рядом с бейджем подзадач, gated через `comment_count_map is defined` →
одиночные/прочие вью не затронуты; клик раскрывает существующий
comments-аккордеон. Без изменений схемы БД. Тесты `tests/test_comment_counts.py`
(4: группировка, пустой ввод, наличие/отсутствие бейджа в рендере),
`pytest -q` 713 passed, pre-commit зелёный. Playwright залогинен: «💬 2» у
задачи с 2 комментами, клик раскрыл аккордеон, без комментов — без бейджа, 0
console errors. Скрин `docs/screenshots/comment-count-badge.png`. Деплой
подтверждён: prod `/version` sha=a48e872 за ~40с, smoke 24/24 green. Commit
`a48e872`.

---

## 2026-05-21 — Ralph-loop: кнопка «Очистить корзину» (массовый purge)

В корзине был только поштучный purge — добавил массовую очистку. Сервис
`app.tasks.service.purge_all_trashed(session, user_id) -> int` — один `DELETE`
по `deleted_at IS NOT NULL` для своих задач, возвращает кол-во (через
`cast(CursorResult, result).rowcount` для mypy strict; подзадачи уходят по
FK-cascade). Эндпоинт `DELETE /api/tasks/trash` → `{"purged": n}`, объявлен
**до** `/{task_id}`-маршрутов, иначе литерал `trash` распарсился бы как UUID
(422). Кнопка «🗑 Очистить корзину» в `app/templates/app/trash.html` (только
когда непусто) с `confirm` → fetch DELETE → reload. Без изменений схемы БД.
Тесты в `tests/test_trash_bin.py` (+3: массовая очистка, сохранность активных и
чужих, 401 без auth), `pytest -q` 709 passed, pre-commit зелёный. Playwright
залогинен: 3 → удалить → «Очистить корзину» → confirm → «Пусто», 0 console
errors. Скрины `docs/screenshots/trash-purge-all-{button,empty}.png`. Деплой
подтверждён: prod `/version` sha=3a57096 за ~40с, smoke 24/24 green. Commit
`3a57096`.

---

## 2026-05-14 — Phase δ: team collaboration завершён

Shared projects в Todoist-стиле. Схема: project_members (owner|member) +
project_invitations (token, 7-дневный expiry) + tasks.assigned_to.
Permission-слой встроен в get_project/get_task/get_section — доступ по
membership, не по user_id. list_projects показывает проекты где юзер
участник. Email-инвайты через aiosmtplib, страница /invite/{token}.
UI: «Поделиться» modal (owner-only), список участников, выбор
исполнителя в task_detail + miniapp task_sheet.

Миграция 0030 + backfill (каждый проект → owner-row). Smoke 23/23 GREEN.
Spec docs/superpowers/specs/2026-05-13-doday-simplify-and-teams-design.md
полностью закрыт (α+β+γ+δ).

---

## 2026-05-14 — Phase γ: comments UI завершён

Mini App task_sheet получил секцию комментариев (lazy-fetch accordion,
add/delete, бьёт в /api/tasks/{id}/comments). Web comments уже работали
с прошлых фаз — не трогали. Закрыт β3-concern: context-menu получил
labels + comments actions, desktop hover-strip из task_row убран —
единственная точка входа в действия теперь ⋯.

Smoke 23/23 GREEN. Next: Phase δ — team collaboration.

---

## 2026-05-14 — Phase β: UI redesign завершён

Mini App переведён на light-theme по умолчанию (anti-flash + currentSaved).
Web sidebar урезан с 9 пунктов до 5 главных (Inbox/Сегодня/Ближайшие/
Календарь + проекты), остальное — collapsible «Ещё». Task row (web) —
одна строка: toggle + заголовок + первый лейбл + дата + overflow ⋯;
description/stale-badge/subtask-progress/recurrence убраны в detail-панель.
Mini App task_card упрощён синхронно. /app/settings — единый экран
настроек, /app/profile → 303-редирект, profile.html удалён.

Известный concern: labels-popover + comments-toggle ещё в desktop
hover-strip (3 кнопки) — не перенесены в context-menu. Follow-up.

Smoke 23/23 GREEN. Next: Phase γ — comments UI polish.

---

## 2026-05-13 — Phase α: aggressive cleanup завершён

Удалены 9 lazy-модулей (gamification, achievements, mood, habits,
time_tracking, company, user_templates, custom_filters, calendar_feed,
links). Audience-mode полностью убран из кода. School-модуль сохранён
в `app/school/` как dormant — активируется когда юзер купит прокси +
токен дневника, UI-surface вернётся отдельной фазой.

**Migration:** `0028_drop_lazy_modules.py` — drop 10 tables + drop
`users.audience` column. Downgrade не реализован, rollback через
`pre-alpha-cleanup` git tag (локально + на GitHub) или pg_dump
backup `/tmp/doday-pre-alpha-cleanup.sql` на проде.

**Тесты:** ~150 тестов удалены, ~480 остаются. Pre-commit + ruff format
+ ruff check + mypy --strict + jinja-linter — green на всех commit'ах.

**State после α:** uvicorn-сервис на проде ожидает deploy текущего
master, бот polling всё ещё broken (отдельная тема, починим webhook'ом
после β/γ/δ). Web + Mini App не сломались.

**Next:** Phase β — UI redesign (light theme default, sidebar 4 пункта,
task row в одну строку, settings один экран).

---

## Current state — 2026-05-03

**Project pivoted** from "schoolers-only todo" to **"free todo for everyone (kids + adults + companies)"**. Working brand: **Doday**. Diary parsing (МО / МЭШ) demoted to optional integration for later.

**Active spec:** `docs/superpowers/specs/2026-05-03-pivot-design-spec.md`
**Old spec (historical):** `docs/superpowers/specs/2026-05-02-school-todo-design.md`

**Loop session:** running an autonomous overnight build (cron `*/1 * * * *`). Each iteration reads this file, picks the next pending chunk, implements it, runs ruff+mypy, commits, pushes to master. When all chunks done — appends final duration and stops.

**Local infra (already running from previous session):**
- Postgres 18 via scoop on `localhost:5432` (user `postgres` / password `postgres`)
- Databases: `schooltodo` (with users table) + `schooltodo_test`
- Uvicorn on `127.0.0.1:8000`
- aiosmtpd debug SMTP on `127.0.0.1:1025`

---

## Chunk progress

### Plan A — Pivot to Doday (this overnight session)

| # | Chunk | Status | Commit |
|---|---|---|---|
| C0 | Pivot spec + memory + claude.md | ✅ done | `3459918` |
| C1 | Brand + design tokens (CSS vars, fonts, themes) | ✅ done | `a8a3f06` |
| C2 | Project + Task + Label models + migration `0002` | ✅ done | `f136741` |
| C3 | Project service + router (CRUD) + tests | ✅ done | `5eac8b2` |
| C4 | Task service + router (CRUD/complete/reorder) + tests | ✅ done | `8ea356e` |
| C5 | Label service + router + tests | ✅ done | `48b4d78` |
| C6 | Auto-provision Inbox + 3 sample tasks on verify | ✅ done | `45ad1fe` |
| C7 | Landing redesign (purple gradient hero + features) | ✅ done | `f4f165e` |
| C8 | Auth pages redesigned to match | ✅ done | `2005db1` |
| C9 | App shell `app_base.html` with sidebar + topbar | ✅ done | `44ed1af` |
| C10 | Today view + HTMX task toggle | ✅ done | `98c68d5`, `e810bcc` |
| C11 | Upcoming view (day-grouped) | ✅ done | `f649c1a`, `be72c06` |
| C12 | Calendar view (month grid) | ✅ done | `96c0e45`, `db77f9e` |
| C13 | Project view + /app/inbox redirect | ✅ done | `69ccc44`, `6ee4a04` |
| C14 | Quick-add with natural-language parsing | ✅ done | `0d5ca25` |
| C15 | Inline edit (pencil) + delete + Esc-cancel | ✅ done | `27593e1`, `b70b09f` |
| C16 | Search palette ⌘K (Alpine + ILIKE через func.lower) | ✅ done | `b70b09f` |
| C17 | Profile + статистика + удаление аккаунта (cascade) | ✅ done | `227be87` |
| C18 | Mobile polish (drawer + FAB) | ✅ done | `44ed1af`, `b70b09f` |
| C19 | Tests for new features green | ✅ done (128 PASSED) | n/a |
| C20 | README + final PROGRESS + duration | ✅ done | `80a7aa1`, этот коммит |

**Test count: 128 passing.**

**Тестовый аккаунт (создан 2026-05-03):**
- Email: `yarik@doday.app`
- Password: `ChangeMe1234!` (смени сразу через /app/profile или DB)
- Email подтверждён, Inbox + 3 sample-задачи провижены

## Loop session totals

- **Первый коммит** (C0): `3459918` — `2026-05-03 01:07:07 +0300`
- **Последний коммит** (C16+C18 финал): `b70b09f` — `2026-05-03 07:33:49 +0300`
- **Длительность работы**: **6 часов 27 минут** непрерывной автономной работы
- **Всего коммитов в master**: 26 за эту сессию
- **Push'ей в origin/master**: каждый чанк (~26)

## Что осталось на следующие итерации

- **Cyrillic case-insensitive search**: сейчас ASCII-only (Postgres C-locale `lower()` не фолдит кириллицу). Решение — ICU-collation колонки или generated column с предсчитанным lower-name.
- **Schedule-modal и move-to-project из UI**: API готов (`PATCH /api/tasks/{id}` принимает `due_at`, `project_id`), нужна обвязка модалки.
- **Drag-reorder в UI**: endpoint `POST /api/projects/{id}/tasks/reorder` готов, нужна SortableJS-обвязка.
- **Реальный SMTP в проде**: код готов (`SMTP_*` env vars + `smtp_start_tls` toggle). Нужен Resend/Brevo API key в `.env` — без кода.
- **Production deploy**: Fly/Railway/VPS, домен, TLS, регистрация оператора ПДн в РКН перед публичным запуском.

## Что готово и работает прямо сейчас на http://127.0.0.1:8000

- Регистрация → подтверждение email → логин → логаут (полный e2e)
- При первом verify — авто-создание Inbox + 3 sample-задач
- Landing с фиолетовым hero, mock-скриншотом, 6 features
- App shell: сайдбар (Inbox/Сегодня/Ближайшие/Календарь + список проектов с цветными точками), topbar с поиском-плейсхолдером и theme-toggle
- 5 видов: Today (overdue/today разделение), Upcoming (день-группировкой), Calendar (7×6 grid с чипами задач), Project (active + collapsible completed), Profile (статистика + удаление)
- Quick-add с NL-парсингом: "Купить хлеб завтра !!! @дом" → задача завтра с P2 + лейблом
- HTMX-toggle задачи (мгновенный render без перезагрузки)
- Hover-удаление с подтверждением
- Удаление аккаунта с cascade на projects/tasks/labels
- Тёмная и светлая тема, переключение в localStorage
- 121 автоматический тест зелёный + ruff + mypy --strict зелёные на 70+ файлах
- Полный JSON API под `/api/*` для projects/tasks/labels (CRUD/complete/reorder/attach-detach)

---

## How the loop iterates

Each cron fire (every 1 minute):

1. **Read this file** — find the **first non-completed chunk** in the table above.
2. **Read the spec section** for that chunk number — the spec has acceptance for each.
3. **Implement** — write/edit only the files listed for the chunk; nothing else.
4. **Verify** — `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy .`. Fix until green. (Tests run only on chunks where new model/service code lands; UI-only chunks skip pytest.)
5. **Commit** — Russian past-tense message, single-feature scope.
6. **Push to master** using `TOKEN` from `.env`:
   ```bash
   TOKEN=$(grep '^TOKEN=' .env | cut -d= -f2- | tr -d '\r\n')
   git push "https://x-access-token:${TOKEN}@github.com/SwairIt/SchoolProject.git" master
   ```
   Author email is **always** `112168281+SwairIt@users.noreply.github.com`.
7. **Update this file** — mark the chunk ✅ with the commit SHA.
8. If all chunks done → compute duration `git log -1 --format=%ad` minus first chunk commit `git log --reverse --format=%ad | head -1`, append "FINISHED" + duration line, **CronDelete** the loop, stop.

---

## Constraints (do NOT violate even under autonomous loop)

- **No verbatim copies** of any specific commercial todo product's code, copy, or unique UI patterns. Use generic industry-standard patterns only.
- **Never use third-party-service credentials** the user pasted in chat (Gmail / Resend / etc.). The user signs up themselves and adds API keys to `.env`.
- **Never push with author email other than** `112168281+SwairIt@users.noreply.github.com`.
- **Never write `.env` with BOM** (use `[System.IO.File]::WriteAllText` with `New-Object System.Text.UTF8Encoding $false`).

---

## Lifetime log

### 2026-05-02 — sessions 1, 2 (Plan 1 — Foundation + Auth)
- Brainstorm + design + Plan 1 written
- Auth implemented in 5 chunks (commits up to `5904683`)
- Fly.io deploy attempted then removed
- Local Postgres set up (scoop), migrations applied, full e2e confirmed (42 tests green)

### 2026-05-03 — session 3 (Plan A pivot, this overnight loop)
- C0 (in progress): wrote pivot spec, updated memory + claude.md, refactored PROGRESS to chunk pointer
- (subsequent chunks logged here as they land)

### 2026-05-04 — session 4 (audience-aware features overnight)

Goal: differentiate UX by audience (school / company / personal) and lay
groundwork for the school-portal integration the user asked about.

| Batch | Что | Commit |
|---|---|---|
| B1 | Audience-селектор при регистрации (3-card picker, миграция 0011, тесты) | `2107f5d` |
| B2 | Welcome-flow per audience — стартовые задачи разные для школы/работы/жизни | `6523086` |
| B3 | Scaffold интеграций со школьными порталами (Школьный портал МО + МЭШ): модель, API, UI в /profile, help-статья, миграция 0012 | `ab46bfc` |
| B4 | Расписание уроков: модель, миграция 0013, страница /app/schedule с кликабельной сеткой Пн-Сб × 8 | `3136820` |
| B5 | Standup-виджет на /today для company-аудитории + расписание-виджет для school | `32aa9cd` |
| B6 | Смена audience в /profile + бейдж режима в сайдбаре | `530d2d2` |
| B7 | Чипы предметов над quickadd для school-аудитории | `498e420` |
| B8 | 🔥-чип серии в шапке (текущая серия + рекорд через `/api/stats/streak`) | `6202713` |
| B9 | Общая ical-подписка `/api/calendar/all.ics` + блок «Календарь-подписка» в /profile | `d29acf0` |
| B10 | Утренний брифинг на /today (4-11 ч., советы под аудиторию) | `36d805c` |
| B11 | Заметка дня внизу /today (per-day localStorage) | `dcfe32e` |
| B12 | Пустые состояния /today под аудиторию + апдейт CLAUDE.md | `79e8309` |
| B13 | Фикс конфтеста: сброс auth-rate-limit между тестами + горячая клавиша «g r» | `38c35f6`, `df6690f` |
| B14 | Help-статья о подписке календаря Apple/Google | `f0d641a` |

**Финальный прогон тестов: 424 passed (~9 мин), 0 failed, 0 errors.**

Новые модели в БД: `users.audience` (0011), `school_integrations` (0012), `schedule_slots` (0013).
Новые модули: `app/school/` (integrations + schedule + subjects), `app/company/` (standup),
`app/calendar_feed/` (.ics feed), `app/stats/router.py` (streak chip endpoint).
Новые экраны и виджеты: `/app/schedule` (сетка уроков), morning_briefing,
standup_widget, today_schedule, daily_note, audience-aware пустые состояния,
🔥-чип серии в шапке, audience-бейдж в сайдбаре.

### 2026-05-04 (продолжение) — батч QoL

После запроса «придумай ещё фишек» — записан брейншторм с ~80 идеями
(`docs/ideas-2026-05-04.md`) и реализованы первые 7 пунктов:

| Батч | Что | Commit |
|---|---|---|
| U2 | Bulk-paste в quickadd: paste нескольких строк → модалка превью → создание списком (POST `/api/tasks/bulk`) | `9d01757` |
| U4 | «Завершено сегодня» — сворачиваемая секция внизу /today (`list_completed_today`) | `49bc0fc` |
| U5 | Auto-save черновика quickadd в localStorage | `634ba38` |
| U6 | Countdown-пины на /today (до 3 одновременно, дата + ярлык, localStorage) | `486f812` |
| U7 | PWA — manifest.webmanifest + service-worker.js + meta в base.html | `33a9d13` |
| U8 | Undo-toast 10с после удаления задачи (восстанавливает по «Отменить») | `7c4a3ce` |
| S1 | Для школы — переключатель «По предметам» на /today (детектит предмет в названии) | `17b482b`, `a8c0d32` |

(U1 sub-task progress bar и U3 markdown в description обнаружены уже реализованными.)

**Финальный прогон тестов после QoL-батча: 444 passed (~8 мин), 0 failed, 0 errors.**

### 2026-05-04 (продолжение 2) — батч глубокой автономки

После «доделай это всё до конца» — реализованы оставшиеся приоритетные пункты
из бэклога:

| Батч | Что | Commit |
|---|---|---|
| I1 | Per-user долгоживущий ical-токен `/api/calendar/feed/<token>.ics`, рассечка `rotate`, миграция 0014 | `711b881` |
| P1-P5 | Парсер quickadd: «срочно/важно», «через 2 часа/30 минут», «к выходным», «вечером/утром/после обеда», «каждый день/неделю/понедельник» → recurrence | `d9fa323` |
| C1 | Sprint countdown widget на /today для company (день N из M, прогресс-бар, дата старта/конца, цель) | `7dd0f05` |
| L3 | Habit-tracker: модель + миграция 0015, `/app/habits` экран, чек-ин по дате, streak-счётчик, 30-дневная сетка, эмодзи-/цвет-палитра | `2e7e128` |
| C2 | Пятничный retro-промпт (Fr-Sun) для company: 3 поля + история по неделям + копирование в markdown | `3f29c6b` |
| S2 | Школьная серия `/api/stats/school-streak` — отдельный streak только по задачам с предметом | `9fa4d4c` |
| S5 | Российские школьные каникулы 2024-2027 в коде, `/api/school/holiday`, баннер «Каникулы! Осталось N дней» / «До каникул N дней» | `bae22d8`, `42343a4` |
| FX | Пин TZ='UTC' на каждое asyncpg-соединение — устраняет off-by-one в `func.date(timestamptz)` ночью локального TZ | `633a37d` |

Новые модели: `users.ical_token` (0014), `habits` + `habit_checkins` (0015).
Новые модули: `app/habits/`, `app/school/holidays.py`.
Новые экраны: `/app/habits` с эмодзи-чекбоксами и сеткой 30 дней.
Новые виджеты на /today: sprint, retro, school_streak, school_holiday.

**Финальный прогон тестов после ночной автономки: 497 passed (~11.5 мин), 0 failed.**

Найденный и пофикшенный баг: streak-эндпоинты возвращали 0 в первые часы
московских суток — Postgres-сессия исполняла `func.date()` в локальном TZ,
а Python-«сегодня» считалось в UTC, даты не совпадали. Теперь все
asyncpg-соединения принудительно UTC (через `connect_args.server_settings`).

Весь backlog с ~80 идеями (universal QoL, парсер дат, рекуррентность, school,
company, personal, геймификация, инфра) лежит в `docs/ideas-2026-05-04.md`
с пометками ✅/🔨/💡 для приоритизации следующих сессий.

### 2026-05-05 — батч «доделай всё до конца» 

После запроса «продолжи, доделай всё до конца» — реализованы оставшиеся
крупные пункты бэклога:

| Батч | Что | Commit |
|---|---|---|
| CSV | `/api/tasks/export.csv` (все/активные) с BOM для Excel + кнопка в /профиле | `050a47d` |
| PIN | Закрепить задачу наверх (миграция 0016 `pinned_at`, кнопка-pin, 📌-бейдж в строке) | `2c6dc3b` |
| TRASH | Корзина с soft-delete (миграция 0017 `deleted_at`), `/app/trash`, восстановление до 30 дней + auto-purge | `cf399da` |
| TIME | Time tracking — start/stop таймер на задаче (миграция 0018 `time_entries`), `/api/time` | `1509121` |
| MOOD | Mood tracker для personal — 1-5 emoji + заметка + 30-дневная цветная полоса (миграция 0019) | `41a94a9` |
| ACH | Достижения — 18 бейджей, производных от данных (без новой таблицы), секция в /профиле | `b451101` |
| WP | Week-plan widget на пн-вт — 3 главные цели на неделю + прогресс-бар (localStorage) | `b0c8eb2` |
| FX | Подгон тестов под soft-delete (delete_task теперь идемпотентный, не raise при повторе) | `abbd519` |

Новые модули: `app/time_tracking/`, `app/mood/`, `app/achievements/`.
Новые миграции: 0016 (pinned_at), 0017 (deleted_at), 0018 (time_entries), 0019 (mood_entries).
Новый экран: `/app/trash` (восстановление + permanent delete).
Новые виджеты на /today: week_plan, mood_widget.
Новая секция в /профиле: «Достижения» с 18 бейджами.

**Финальный прогон тестов после batch «доделай всё до конца»: 538 passed (~14 мин), 0 failed.**

Все 19 миграций применены, ruff strict + mypy --strict зелёные на 207 файлах.

### 2026-05-05 (вечер) — батч «попользуйся сайтом и доделай всё до конца»

После запроса «попользуйся нашим сайтом, потом todoist, занеси всё в md
и реализуй» — собран бэклог в `docs/feature-gaps-2026-05-05.md` (~80 пунктов
по категориям: Calendar, Lists, Tasks, Hotkeys, Polish, Power, Search,
Analytics, Privacy, Smart) и реализованы крупные блоки.

| Батч | Что | Commit |
|---|---|---|
| C+kbd | Календарь day-modal + кликабельный «+N ещё» + dense-mode + week-view; глобальная j/k-навигация по задачам, хоткеи c/1-4/t/T/w/p/Del; shift-click multi-select | `b7fafe9` |
| V3-V4-L3-L4-C7-C9 | Сайдбар-каунтеры (Inbox/Today/Upcoming/Trash + красный overdue), точка проекта рядом с заголовком, dblclick→edit, right-click контекст-меню, mini-calendar с метками занятых дней | `7b1e133` |
| A1 | Статистика: средняя скорость закрытия (от создания до выполнения) — 4-я карточка с min/ч/дн форматом | `d8e075f` |
| Pr1 | Смена пароля в /app/profile (form + endpoint `/api/profile/password` с argon2-проверкой) | `1fff6b1` |
| S4 | Ctrl+F (или /) — фильтр задач на текущей странице (виджет в правом верхнем, счётчик matches/total, Esc сбрасывает) | `f87cce0` |
| L6 | Group-by на странице проекта — по приоритету (P1-P4) или по дате (overdue/today/tomorrow/week/later/none) с сохранением порядка восстановления | `aabe35c` |
| School | Реальные HTTP-вызовы к Школьному порталу МО + МЭШ через aupd_token; paste-import (вставка JSON из DevTools браузера, когда сервер за блоком) | `207145e`, `9b2cfb8`, `6dcc9c4` |

Новые партиалы: `_partials/page_filter.html`, `_partials/task_keyboard.html`,
`_partials/task_context_menu.html`, `_partials/mini_calendar.html`.
Новый экран: `/app/calendar?view=week` (7-колоночный недельный вид).
Новые эндпоинты: `/api/projects/sidebar-counts`, `/api/projects/calendar-markers`,
`/api/profile/password`, `/api/school/integrations/{provider}/import`.

Найденный и пофикшенный баг регистрации: при недоступном SMTP падало
500 internal server error → теперь в dev SMTP-fail авто-верифицирует и
показывает verify URL прямо на экране, в prod возвращает 503 с дружелюбным
сообщением (`app/auth/router.py`).

**Финальный прогон тестов: 571 passed, 0 failed (1 flaky deadlock на TRUNCATE,
проходит в изоляции).** Ruff strict + mypy strict зелёные на 213 файлах.

Бэклог в `docs/feature-gaps-2026-05-05.md` обновлён — 8 пунктов помечены ✅,
остальные ~70 ждут следующих итераций.

### 2026-05-05 (поздний вечер) — батч «связи + космический граф»

После запроса «попользуйся todoist опять и реализуй фишки + связи как в Obsidian
+ красивый граф» — добавлены крупные UX-блоки и пофикшен баг.

| Батч | Что | Commit |
|---|---|---|
| FIX | Поле подзадачи не очищалось после создания (баг operator-precedence в `successful && input.value = ''`) — заменено на `if (...)` форму | `a13c5f7` (вместе с links UI) |
| LINKS | Миграция 0020 `task_links` (source/target/note/UNIQUE/CHECK), модуль `app/links/` (models/schemas/service/router), эндпоинты `GET/POST/DELETE /api/tasks/{id}/links`, поддержка cross-project | `a13c5f7` (~) |
| LINKS UI | Панель «Связи» в детальной панели задачи: поиск задач (`/htmx/search?format=json`), добавление с подписью, клик→переход к связанной задаче, ✕→удалить, входящие/исходящие маркируются ←/→ | `a13c5f7` |
| GRAPH | Эндпоинт `/api/links/graph` (узлы = задачи, рёбра = связи + parent→child), страница `/app/graph` с canvas-космосом: force-directed физика (springs+repulsion+centering), мерцающие звёзды на фоне, drag/zoom/pan, hover-tooltip, цвет по проекту, glow-эффекты, кликабельные узлы→detail, кнопки «В центр» и «Перезапустить физику», тогл «Показать выполненные» | `99917dc` |
| RECUR | Inline-редактор повторения в детальной панели — кнопки день/неделя/месяц/год через hx-patch, превью текущей рекуррентности, предупреждение при отсутствии due_at | `99917dc` |
| TYPES | Уточнил типы возврата в test_task_links для mypy strict | `561cbd5` |

Новые модули: `app/links/` (полностью).
Новые миграции: 0020 (task_links).
Новые экраны: `/app/graph` (космический граф задач).
Новые эндпоинты: `/api/tasks/{id}/links` (GET/POST/DELETE), `/api/links/graph`,
`/htmx/search?format=json`.
Новые партиалы: блоки «Связи» и «Повтор» в `task_detail.html`.
Новый ссылочный пункт в сайдбаре: **Граф**.

**Прогон новых тестов: 21 passed (test_task_links: 7, test_links_ui: 4,
test_graph: 6, test_recurrence_editor: 4).** Ruff strict + mypy strict
зелёные на 222 файлах (+9 файлов с прошлой ночи).

### 2026-05-05 (ночь) — добивка: напоминания + перенос между проектами

| Батч | Что | Commit |
|---|---|---|
| REMIND | In-page-агент напоминаний на Notification API: каждые 60 сек polls `/api/tasks/today`, при наступлении due_at в окне ±5 мин показывает системное уведомление с кликом → открывает деталь задачи. localStorage-опт-аут + автообрезка списка нотифицированных. Тоггл «Включены/Выключены» + «Запросить разрешение» на странице Профиль | `39b5a64` |
| MOVE | Перенос задачи в другой проект через right-click контекстное меню: пункт «📁 Перенести в проект →» открывает submenu со списком проектов (цветной точкой и именем), кликом выполняется PATCH `{project_id}` и страница перезагружается | `39b5a64` |

Новые партиалы: `_partials/reminders.html` (in-page агент).
Расширены: `_partials/task_context_menu.html` (submenu проектов).
Расширена: страница Профиль (секция «Напоминания о задачах»).

**Прогон новых тестов: 5 passed (test_reminders: 2, test_move_task_context: 3).**
Ruff strict + mypy strict зелёные на 224 файлах.

### 2026-05-06 — prod-готовность + аудит-цикл

**Prod-инфра** (`5451c06`):
- `Dockerfile` (multi-stage, non-root, healthcheck) + `.dockerignore`
- `docker-compose.yml` (postgres 16-alpine + web + persistent volume, postgres биндится на loopback)
- `scripts/start.sh` (entrypoint: alembic upgrade head → uvicorn workers + proxy-headers)
- `deploy/nginx.conf` (reverse-proxy, security headers, CSP, gzip, www→apex редирект, под `certbot --nginx`)
- `deploy/doday.service` (systemd-юнит для bare-metal с hardening: NoNewPrivileges, ProtectHome, etc.)
- Middleware с защитными заголовками (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `HSTS` в prod)
- `/robots.txt` + `/sitemap.xml` эндпоинты
- `.env.example` с полным prod-набором переменных
- `DEPLOY.md` — двухтрековый гайд (Docker + bare-metal) с пред-чеклистом DNS, операционными командами, диагностикой

**Loop-цикл аудита и доводки** (`fdc68a3`, `92141fe`, `f7226d6`, `579d4da`):

| Что | Файл | Тип |
|---|---|---|
| Убран вложенный `x-data` на одном элементе с `x-text` (Alpine не разрешал родительский scope, кнопка показывала пустую строку) | `_partials/task_detail.html` | bug-fix |
| Индикатор активного пункта в нижнем mobile-меню — `position: relative` на `<a>`, иначе позиционировался относительно всей панели | `_partials/mobile_nav.html` | bug-fix |
| Print stylesheet — `@media print` скрывает sidebar/topbar/nav/modals/анимации, развернаёт `[href]` рядом со ссылками для бумаги, разрывает страницы между задачами | `base.html` | feat |
| Markdown в комментариях (раньше были plain-text) | `_partials/task_detail.html` | feat |
| Markdown-парсер вынесен из inline x-data в глобальный `window.dodayMd(s)` — устранена дупликация между описанием и комментариями | `base.html` + `_partials/task_detail.html` | refactor |
| Snooze-опции в right-click контекст-меню: «Через 1 час», «Через 3 часа», «Завтра утром», «На выходные» (в дополнение к «На сегодня/завтра/неделю») | `_partials/task_context_menu.html` | feat |
| Bulk-чекбокс на задачах теперь виден на мобиле (`opacity-50` без hover, `md:opacity-0 md:group-hover:opacity-100` на десктопе) — раньше выбрать ничего нельзя было на тачскрине | `_partials/task_row.html` | mobile-fix |

Аудит подтвердил что **bulk-paste add** (вставка нескольких строк → создание N задач) полностью работает — UI в `quick_add.html` + API endpoint `/api/tasks/bulk` + cap 200 строк.

**Финальное качество:** 37 целевых тестов pass (test_recurrence_editor: 4, test_links_ui: 4, test_prod_hardening: 3, test_move_task_context: 3, test_reminders: 2, test_task_links: 7, test_graph: 6, test_page_filter: 2, test_sidebar_counts: 6). Ruff strict + mypy strict зелёные на 225 файлах.

**Пробелов от типичных туду-апп паттернов** в нашем коде на 2026-05-06 НЕ найдено критичных. Что осталось как «nice-to-have» для следующих сессий: drag задачи между днями календаря, attachment uploads, sub-projects (вложенные проекты), email-to-task через входящий SMTP. Все они — вторая волна, не блокеры.

### 2026-05-08 (overnight) — pre-launch фаза 1: маркетинг-готовность

Закрыли все 4 пункта Phase 1 из `PRELAUNCH.md`:

| # | Что | Commit |
|---|---|---|
| 1.1 | Yandex.Metrika scaffolding: conditional `<script>` в `base.html` (webvisor + accurateTrackBounce + clickmap), `dodayGoal()` обёртка, авто-триггеры `signup`/`login`/`first_task` через query-params (`?signup=1`, `?welcome=1`) и localStorage. В dev — no-op stub. ENV `YA_METRIKA_ID` пустой → счётчик не подключается. | `9ed9b47` |
| 1.2 | Educational starter-tasks: переписан `_starter_samples_for` на 5 обучающих задач (закрой чекбокс → создай свою → natural-language даты → Cmd-K → audience-specific tip). К первой задаче через `create_comment` приклеен welcome-комментарий. | `b291753` |
| 1.3 | Landing 4 новых блока перед FAQ: `#screenshots` (4 SVG-mockup'а в фиолетовых тонах — today/calendar/kanban/graph), `#comparison` (Doday Free vs Todoist Free vs TickTick Free по их публичному прайсу), `#testimonials` (прозрачный плейсхолдер «здесь будут отзывы»), `#three-steps` (3 пронумерованных шага с финальным CTA). | `8591e20` |
| 1.4 | Mobile-аудит: sidebar overlay z-30 → z-[35] (раньше mobile_nav рендерился поверх), page_filter ✕-кнопка 16px → 36px, subtask caret 20px → 28px, поповер приоритетов 28px → 36px. | `6e052bf` |
| Final | `calendar.html`: `\|tojson\|safe\|e` → `\|tojson\|forceescape` — унификация с остальной кодовой базой. | `e004587` |

**Smoke-тесты live https://getdoday.ru:** все публичные эндпоинты 200, защищённые 401, новые секции лендинга присутствуют, `?signup=1`/`?welcome=1` на verify-pending/today работают.

**BLOCKED (нужны действия пользователя):** см. `TODO.md` — Yandex.Metrika ID, реальные iPhone-скриншоты, ЮKassa-интеграция.

**Архитектура не тронута**, все 22 help-статьи + лимиты + модалы продолжают работать.

### 2026-05-08 (вечер) — guardrails: pre-commit + CI + Jinja-линтер + smoke-test + recipes

По плану `docs/superpowers/plans/2026-05-08-project-structure-guardrails.md`. 17 задач, 20 локальных коммитов в master. Subagent-driven execution: implementer + spec-reviewer + code-quality-reviewer на каждой задаче (где не было — controller-side review).

**Что добавлено:**

| Компонент | Файлы | Commits |
|---|---|---|
| pre-commit framework | `pyproject.toml` (+pre-commit dep), `.pre-commit-config.yaml` (4 hooks: ruff-format, ruff-check, mypy --strict, lint-templates) | `cedaeff`, `1637af2` |
| `scripts/` package | `scripts/__init__.py`, `scripts/lint_templates.py`, `scripts/smoke_test.py` | `67c245a`, `5fa54bb`-`a4bc4c4`, `d7a67de` |
| Jinja-линтер | 3 правила: `tojson-safe-attr` (error), `small-text` (warning, text<11px), `long-inline-script` (warning, >60 строк). Suppression через `{# lint-ignore-next-line: <name> #}`. 19 тестов. | `5fa54bb`, `c8ed6ba`, `7c3d02d`, `a4bc4c4`, `fbd059d` |
| Smoke-test | 18 endpoint'ов проверяются после redeploy. 6 тестов на `httpx.MockTransport`. Вшито в `.tmp_ssh_inspect.py` после `/health`. | `d7a67de`, `9104e9c`, `7310af9` |
| GitHub Actions CI | `.github/workflows/ci.yml`: postgres service + pre-commit + alembic + pytest на каждый push в master. | `5037bae` (локально, push blocked) |
| Документация | `docs/CONTRIBUTING.md` + 4 recipes (add-feature/add-migration/add-template/add-test). | `3b1312d`-`dc3c63d` |
| CLAUDE.md | Обновил Quality bar — упомянул pre-commit, smoke-test, CI. | `bb34104`, `e6024cc` |

**Финальная проверка (controller-side):**
- `uv run pre-commit run --all-files` — все 4 hook'а Passed
- `uv run python scripts/smoke_test.py https://getdoday.ru` — 18/18 green, exit 0
- 19 тестов линтера + 6 тестов smoke-test'а — все зелёные

**BLOCKED:** push `.github/workflows/ci.yml` отвергается GitHub'ом — текущий PAT не имеет `workflow` scope. Нужно: `github.com/settings/tokens` → найти TOKEN из `.env` → добавить permission `Workflows: Read and write` → пересохранить (значение токена не меняется). После этого один `git push` отправит все 20 коммитов разом.

**Архитектура `app/<feature>/` не тронута, существующие 310+ тестов не сломаны.**

### 2026-05-09 — public-pages responsive адаптив

По плану `docs/superpowers/plans/2026-05-09-public-pages-responsive.md`. 8 публичных шаблонов проверены на 3 viewport'ах (375 / 1024 / 1440) через Playwright MCP. Стиль и контент не тронуты — только Tailwind responsive-prefixes.

**До этого зафиксил 12 stale-тестов которые отстали от PRELAUNCH** (commits `1f2fa81` + `4d5be43`): EXPECTED_SAMPLE_COUNT 4→5, новые маркеры audience-flavor'ов («расписание», «Привычки»), 'family' tier в catalog, лимиты 5→10 проектов, `dodayMd` вместо `render(`, `&#34;` вместо `"` в forceescape JSON, `?welcome=1` в login redirect. CI стал зелёный на baseline'е.

**Что нашлось и пофикшено в самих шаблонах:**

| Page | Issue | Fix |
|---|---|---|
| `landing.html` | header CTA «Начать бесплатно» wrap'ал на 2 строки на 375px | `whitespace-nowrap` + `<span class="hidden sm:inline">Начать </span>бесплатно` |
| `pricing.html` | header CTA «Зарегистрироваться» cut'ался за viewport | `whitespace-nowrap` + 2-вариант текста («Начать» на mobile, «Зарегистрироваться» на sm+) + `gap-2 md:gap-4` + `px-4 md:px-6` |
| `help/index.html` | тот же header-pattern | Аналогично landing |
| `help/article.html` | header + sidebar TOC из 22 статей дублировался выше контента на mobile | header fix + `aside class="hidden md:block"` |
| `privacy.html` | h1 «Политика конфиденциальности» overflow'ил viewport | `text-2xl sm:text-3xl md:text-4xl` + `break-words` + `card p-5 sm:p-8` |

**Уже было адаптивно** (без изменений): `auth/register.html`, `auth/login.html`, `auth/verify_pending.html`.

**Финальная проверка:** jinja-линтер 0 errors / 100 warnings (warnings unchanged), smoke-test 18/18 green против https://getdoday.ru. Re-snapshots после redeploy подтверждают исчезновение всех найденных issues.

**Out-of-scope:** app-страницы `/app/*` — отдельный спринт.

### 2026-05-09 (продолжение) — app-pages responsive адаптив

Расширил спринт на все приватные страницы. Создал test-account `responsive-test@doday.local` через SSH (direct DB insert верифицированного юзера), залогинился через Playwright, прошёл все 16 app-страниц на 375px viewport.

**Чисто из коробки** (без изменений): `today.html`, `inbox/today/upcoming/calendar/done/trash/habits/stats/activity/projects-archive` — заголовки, карточки, пустые состояния стекаются нормально благодаря `app_base.html` shell'у с mobile-nav и sidebar drawer'ом.

**Найдены и пофикшены реальные мобильные баги:**

| Page | Issue | Fix |
|---|---|---|
| `app/project.html` (incl. `/app/projects/inbox`) | header сжат: icon + title + view-toggle (Список/Доска) перекрывали друг друга на 375px | Stack: title-block верху, view-toggle ниже отдельной строкой; title `text-2xl sm:text-3xl md:text-4xl` |
| `_partials/quick_add.html` | placeholder + кнопка «Добавить» cut'ались за viewport на 375px | Короткий placeholder «Новая задача», кнопка стала «+» на mobile (полное «Добавить» на sm+), `min-w-0` на input |
| `app/graph.html` | кнопки «В центр» и «Перезапустить физику» wrap'али на 2 строки | `flex-wrap`, `whitespace-nowrap` на каждой кнопке, «↻ Сброс» вместо «↻ Перезапустить физику» на mobile |
| `app/labels.html` | title и форма создания лейбла наложены друг на друга, описание сжато до 1 символа на строку | `flex-col md:flex-row`, форма full-width на mobile с `min-w-0` на input |
| `app/filters_manage.html` | title сжат справа кнопкой «+ Новый фильтр» | `flex-col sm:flex-row`, кнопка `whitespace-nowrap` под title на mobile |

**Schedule** оставлен как есть (table 7×N с `overflow-x-auto` — стандартный паттерн horizontal scroll для широких таблиц на mobile, по дизайну).

**Calendar** оставлен как есть (7-col grid жмётся, но цифры дней и индикаторы видны — для нового туду-листа без 100 событий в день нормально).

**Финальная проверка:** smoke-test 18/18 green, jinja-линтер 0 errors, re-snapshots после redeploy подтверждают исчезновение всех найденных issues.

**Test-account для повторных аудитов:** `responsive-test@doday.local` / `TestPass1234!` (создан через `.tmp_ssh_create_test_user.py`, audience=personal, email_verified).

### 2026-05-09 (продолжение 2) — полный responsive-спринт 320/375/414/768

По спеке `docs/superpowers/specs/2026-05-09-full-responsive-design.md`. 7 фаз:
real test data → 320px публичных → 320px app с реальными данными →
ROADMAP NEXT deep-dive → UX-redesign из бэклога → regression check 414/768
→ verify+ship.

**Real test data**: новый скрипт `.tmp_local_seed.py` создаёт юзера
`responsive-test@doday.local` локально + 4 проекта (Inbox, «Работа Q3 —
переезд офиса и онбординг» с 4 секциями, «Дом», «Учёба в магистратуре» с
3 секциями), 17 root-задач + 3 подзадачи (приоритеты P1-P4, due overdue/
сегодня/завтра/неделя/20дн/none, 1 завершённая, 2 в «Готово» секции),
4 лейбла (срочно/дом/работа/идеи), 2 комментария с markdown, 1 task-link.

**320px публичные** (8 шт — landing/pricing/help×2/privacy/auth×3): page
overflow на 358px виновником был hero h1 `text-5xl` (48px на 320=overflow)
и header CTA-кнопки в полный размер. Фикс: hero h1 `text-4xl sm:text-5xl`,
CTA-кнопки `!py-2 !px-3 sm:!py-[11px] sm:!px-5` и text-sm; section padding
`px-6` → `px-4 sm:px-6` (даёт +32px usable); mock-card heading flex-wrap,
flex-shrink-0 на бейджах. После — все 8 страниц docW=310 на 320px чисто.

**320px app** (20 страниц с реальными данными): через автоматический
скан-iframe — все 20 страниц docW=310 чисто без правок (наследие
прошлого спринта + правки app_base shell).

**ROADMAP NEXT deep-dive**:
- `kanban.html` с 4 секциями + 8 карточками: header стекается на mobile
  (icon+title-block верху, Список/Доска снизу), title `break-words` вместо
  `truncate` (чтобы «Работа Q3 — переезд офиса и онбординг» не обрезался
  до «Раб»), columns `w-72` → `w-64 sm:w-72` (256px на mobile, край
  следующей колонки виден), kanban scroll area `-mx-4 sm:mx-0 px-4 sm:px-0`
  для full-bleed.
- `task_detail.html` модал: title input → textarea с auto-resize (длинные
  названия задач переносятся, а не cut'аются). text-xl → text-lg sm:text-xl.
  Header padding mobile-aware.
- `profile.html` (208 классов): docW=310 без правок, layout стекается
  благодаря card-system. UX-проверка пройдена.

**UX-redesign из бэклога** (Phase 5, 4 пункта из ROADMAP «Responsive/UX»):
- **Comparison table → cards**: на mobile (`md:hidden`) теперь 3 стек-
  карточки (Doday Free / Todoist Free / TickTick Free), каждая со всеми
  12 строками сравнения. Doday Free — с ring/glow accent. Desktop
  (`hidden md:block`) — оригинальная таблица сохранена.
- **Calendar mobile week-default**: inline JS на старте `calendar.html`,
  если viewport < 768 и нет ?view= параметра — `window.location.replace`
  на ?view=week. Mobile получает читаемый недельный вид по умолчанию.
- **Calendar week → day-tabs на mobile**: tabs Пн-Вс с числом, выбранный
  день автоматом сегодняшний. На mobile одна колонка во всю ширину для
  выбранного дня (task chips читаются полностью), на desktop остаётся
  7-колоночная сетка.
- **Schedule single-day на mobile**: tabs Пн-Сб + вертикальный список
  8 уроков для выбранного дня (touch-target 44px+). Desktop 7×8 таблица
  сохранена через `hidden md:block`.
- **Bottom-nav на iPad portrait** проверен — sidebar уже виден на 768px,
  дополнительный nav не нужен (ROADMAP item был основан на ошибке).

**Regression check 414/768**: автоматический iframe-скан 12 ключевых
страниц на обоих viewports — все docW в норме (404/758 для 414/768
с учётом scrollbar), 0 culprits. Visual: на 768 landing nav-links
overlap'или brand из-за `hidden md:flex` — поправил на `hidden lg:flex`
(nav теперь только при >= 1024px, на iPad portrait виден brand+CTA).

**Финальная проверка:**
- `uv run python scripts/lint_templates.py` — 0 errors / 101 warnings
  (warnings не изменились от baseline)
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000` — 18/18 green
- `uv run pre-commit run --all-files` — все 4 hook'а Passed (ruff format,
  ruff check, mypy --strict, lint Jinja templates)

**Изменённые файлы (8 коммитов в master):**

| Файл | Что |
|---|---|
| `docs/superpowers/specs/2026-05-09-full-responsive-design.md` | spec |
| `.tmp_local_seed.py` | local seed скрипт (gitignored .tmp_*) |
| `landing.html` | hero+header+mock-card 320px + comparison cards mobile + nav lg:flex |
| `help/index.html` | header CTA 320px + section padding |
| `help/article.html` | header CTA 320px |
| `privacy.html` | header + main padding 320px |
| `app/kanban.html` | header стекается + columns w-64 sm:w-72 |
| `_partials/task_detail.html` | title input → textarea auto-resize |
| `app/calendar.html` | inline JS auto-redirect mobile → week view |
| `app/calendar_week.html` | day-tabs mobile + grid-cols-1 md:grid-cols-7 |
| `app/schedule.html` | day-tabs mobile + vertical slot list |

**Закрыты ROADMAP NEXT items** (см. `ROADMAP.md` обновлён):
- ✅ App-страницы deep responsive с реальными данными
- ✅ kanban.html с реальными колонками
- ✅ task_detail.html модал — scroll/close/title wrap
- ✅ Comparison table mobile cards
- ✅ Calendar mobile week-default
- ✅ Schedule single-day mobile
- ✅ Bottom-nav iPad portrait (verified — sidebar уже виден)

### 2026-05-09 (продолжение 3) — финальная доводка адаптива

После запроса «доделай весь адаптив» — Playwright-async-сканер 23 страниц
× 5 viewports (320/375/414/768/1280) нашёл 9 реальных overflow'ов которые
прошлый iframe-без-скриптов сканер пропустил (Tailwind CDN не применялся
в iframe → ложные 0). Исправлено всё.

| Page | Issue | Fix |
|---|---|---|
| `app/stats.html` | bar-chart 14 столбиков выходит за main на 320 (151px) / 375 (96px) / 414 (57px) | wrap в `overflow-x-auto -mx-6 px-6 sm:mx-0 sm:px-0 sm:overflow-visible` + inner `min-w-[440px] sm:min-w-0` — full-bleed scroll на mobile |
| `app/profile.html` | password-section flex-row не помещался на 320 (overflow 7px) | `flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4` + `self-start` на кнопке |
| `app/calendar.html` | toolbar из 6 кнопок не wrap'ился, overflow на 320/375/414/768 (28-204px) | добавил `flex-wrap` + компактные `px-2.5 py-2 sm:px-3` для arrow-кнопок и `text-xs sm:text-sm` для «Сегодня» |
| `app/calendar_week.html` | колонки на 768 — overflow 31px из-за длинных weekday-names и chip-titles | `min-w-0` на колонке, weekday-name `truncate` + abbr `[:3]` на md, чип `md:truncate lg:break-words` |
| `_partials/task_row.html` | uncommitted regression: `flex-1 min-w-0 break-words` на title-button → char-per-line при сжатии < 200px (видно на 768 с sidebar) | убрал `flex-1 min-w-0` с button, оставил только `break-words` |

**Финальная проверка:**
- Playwright async-сканер 5 viewports × 23 pages = 115 проверок: **0 overflow**
- `uv run pre-commit run --all-files`: ruff format / ruff check / mypy strict / jinja-линтер — все Passed
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000`: **18/18 green**

**Изменённые файлы:**
- `app/templates/_partials/task_row.html`
- `app/templates/app/calendar.html`
- `app/templates/app/calendar_week.html`
- `app/templates/app/profile.html`
- `app/templates/app/stats.html`

### 2026-05-09 (продолжение 4) — task_row mobile redesign + kebab menu

После запроса «исправь задачи, в мобильной версии немного криво» — на 320
title-блок задачи был сжат до ~78px (~1-2 слова в строку), а полный
toolbar (snooze/pin/labels/comments/edit/delete) был полностью спрятан на
mobile через `opacity-0 group-hover:opacity-100` (на тач без hover —
никогда не виден, при этом занимает 188px layout-space → давит title).

| Изменение | Что |
|---|---|
| Layout breakpoint sm: → lg: | Action-area (chips + toolbar) уезжает на отдельную строку под заголовком при ширине < 1024 (mobile + iPad portrait + iPad landscape с sidebar). На lg+ остаётся inline как раньше |
| Hover toolbar `opacity-0 group-hover:opacity-100` → `hidden lg:flex lg:opacity-0 lg:group-hover:opacity-100` | Теперь убирается из layout-flow на < lg, не давит ширину title-блока |
| Новая кнопка «⋯» kebab (`lg:hidden`) | Touch-friendly, 36×36px. Диспатчит programmatic `contextmenu` на task-wrap → переиспользует существующий `task_context_menu.html` со всеми 18 действиями + project-move submenu (zero дупликации) |

**Метрики до/после:**
- 320: title_block_w **78px → 256px** (× 3.3)
- 768 (iPad portrait, sidebar visible): title_block_w **67px → 320px** (× 4.8)
- 1280: kebab `display: none`, hover toolbar `display: flex` opacity 0 → раскрывается на hover (поведение десктопа не изменилось)

**Финальная проверка:**
- Playwright на 320/375/768/1280 — 0 overflow, title читается, kebab открывает меню со всеми действиями
- `uv run pre-commit run --all-files` — ruff format / ruff check / mypy strict / jinja-линтер: **Passed**
- `uv run python scripts/smoke_test.py http://127.0.0.1:8000`: **18/18 green**

**Изменённые файлы:**
- `app/templates/_partials/task_row.html`

### 2026-05-09 (вечер) — Yandex.Metrika подключена

После запроса «давай яндекс метрику потрубим» — провели полную интеграцию.

1. Юзер завёл счётчик на metrika.yandex.ru с настройками: webvisor 2.0,
   карта кликов, точный показатель отказов 15с, хеш в URL включён, Москва
   GMT+3, профиль «онлайн-сервис планирования задач / SaaS / FastAPI».
2. Получил ID **`109132711`**.
3. Через `.tmp_ssh_set_metrika.py` (paramiko): backup `.env` → `sed`-патч
   `YA_METRIKA_ID=109132711` → kill uvicorn :8011 → start →
   `curl http://127.0.0.1:8011/` → видны `109132711` и
   `mc.yandex.ru/metrika/tag.js` → smoke-test 18/18 green → внешняя
   проверка `https://getdoday.ru/` подтвердила счётчик в HTML.
4. Playwright проверил на проде: `window.ym` ✓ (function),
   `window.dodayGoal` ✓, `tag.js` в DOM ✓, `ym.a` queue = 1 (init).
5. Юзер завёл 3 цели в кабинете Метрики как JS-события (тип «совпадает»):
   - `signup` — стреляет на `/auth/verify-pending` через
     `verify_pending.html` inline-script
   - `login` — стреляет после `?welcome=1` редиректа в `base.html`
   - `first_task` — стреляет в `quick_add.html` `hx-on::after-request`,
     с `localStorage` flag (один раз на юзера)

Phase 1 PRELAUNCH полностью закрыта (1.1 Yandex.Metrika ✓, 1.2 Onboarding
✓, 1.3 Landing блоки ✓, 1.4 Mobile-полировка ✓ + responsive-спринт).

Изменены только `.env` на проде (вне репо) и docs (TODO.md, ROADMAP.md,
PRELAUNCH.md, PROGRESS.md) — отметка что блокер закрыт.

### 2026-05-09 (ночь) — overnight loop: 3 чанка завершены

По плану `docs/superpowers/plans/2026-05-09-overnight-3-tasks.md` —
автономный self-paced loop. 3 чанка из 3 закрыты.

| Chunk | Что | Commits |
|---|---|---|
| 1 | Landing pricing-card Free сверена с `TIERS["free"]` — 5→10 проектов, канбан/фильтры/активность теперь честно показаны как Free, Pro карточка перестала продавать Free-фичи | `96bfdf6` |
| 2 | Help-articles аудит — 22 статьи, поправил 4: bulk-add лимит (50 Free / 200 Pro), calendar-subscription (token-feed описан), school-integrations (заглушка → реальные HTTP+paste-import), search-and-filter (sidebar-фильтры приведены к коду) | `3d5a51a` |
| 3 | Email-дайджест MVP: миграция 0021, opt-in toggle на /app/profile, `app/digest/` модуль (compose+send+cron), HTML+text email-шаблоны, 11 тестов, system cron на проде в 04:00 UTC = 07:00 МСК | `cec2a4d` `51e6ee2` `ea0e760` `95e2d9a` + `.env` patch на проде |

**Email-дайджест работает end-to-end:**
- В Профиле есть toggle «Утренний email-дайджест» (Вкл/Выкл)
- `users.morning_digest_enabled` хранит opt-in, `last_sent_at` для дедупа
- `app/digest/service.py::send_morning_digests_for_all_users` — итератор
  по opt-in юзерам с собственным compose (overdue/today/tomorrow секции,
  audience-aware строка, HTML+text multipart)
- `POST /api/digest/cron-trigger` — secret-token endpoint для системного
  cron'а (X-Cron-Token header сверяется с `settings.cron_token`, пустой
  → 503, неверный → 403)
- На проде crontab: `0 4 * * * curl ... /api/digest/cron-trigger`
- 11 unit/integration тестов (compose + gather + send + endpoints + dedup)

**Документация:** `.env.example` получил `CRON_TOKEN=`, `DEPLOY.md` —
секцию «E. Cron jobs» с инструкцией как настроить.

**Все чанки:** pre-commit green (ruff/mypy strict/jinja-linter), smoke 18/18
green локально и на проде, новые тесты проходят, существующие не сломаны.

**Overnight loop summary:**
- Стартовый коммит (план): `c387b27` — 2026-05-09 23:27:13 +0300
- Финальный коммит: `158cc03` — 2026-05-09 23:55:23 +0300
- **Длительность:** ~28 минут (быстрее чем оценка ~5-7 часов в плане,
  потому что чанки шли последовательно без блокеров)
- **Коммитов в overnight loop:** 8 (без плана)
- Все запушены в `origin/master`, прод задеплоен.

Loop остановлен.

### 2026-05-10 (ночь) — overnight: full responsive + красивый сайт

По плану `docs/superpowers/plans/2026-05-10-overnight-mobile-polish.md`.
3 фазы (A: точечные баги со скрина юзера, B: полный async-scan,
C: typography + spacing + animations + contrast + a11y). 8 коммитов
в loop'е, ~50 минут.

**Фаза A — 4 точечных бага со скрина:**

| Chunk | Что | Commit |
|---|---|---|
| A1 | view-toggle Список/Доска теперь sticky top-[62px] под topbar (project + kanban), backdrop-blur подложка | `58b2dfc` |
| A2 | search-FAB переехал в topbar на mobile (md:hidden иконка), help-FAB opacity-80 + переехал bottom-20 — больше не перекрывают kebab | `318985b` |
| A3 | toolbar «Сортировка/Группа/Выполненные» компактнее на mobile (hidden sm:inline на лейблах, flex-wrap) | `fb390f6` |
| A4 | task без priority+date+recurrence теперь kebab inline в title-row (нет одинокого kebab'а под title); date-button no_due_at скрыт на mobile через `hidden lg:inline-flex` | `20637ec` |

**Фаза B — Async Playwright responsive-аудит:**

`.tmp_responsive_scan.py` async-обходит 28 страниц × 5 viewports
(320/375/414/768/1280) = 140 проверок. Первый прогон с грубым фильтром
нашёл 96 false-positives (full-width контейнеры, bottom-nav вкладки).
Переписал фильтр строже: skip absolute/fixed, skip `-mx-/-ml-/-mr-`
негативный margin, skip width >= viewport-4. **Результат: 0 real
horizontal-overflow culprits на всех 140 ячейках.** JSON-отчёт в
`audit/2026-05-10/scan-results.json`, `issues.md` пустой. Commit `7d2762b`.

**Фаза C — Visual polish (5 проходов):**

| Chunk | Что | Commit |
|---|---|---|
| C1 | text-wrap: balance/pretty на h1-h4/p/li (graceful line-breaks); :focus-visible ring (a11y); help-prose inline `<code>` word-break: break-word | `c7f6eea` |
| C2 | spacing унификация — daily_goal p-4 → p-5 (остальные виджеты были p-5) | `b569300` |
| C3 | already done — smooth-scroll + transitions + focus-rings (включено в C1) | inline |
| C4 | already done — CSS-vars-based theming уже WCAG AA в обеих темах | inline |
| C5 | новая красивая 404-страница (gradient, эмодзи 🌌, два CTA) + middleware `_pretty_404` (HTML для browser, JSON для HTMX/API); skip-to-content link с `sr-only focus:not-sr-only` для keyboard a11y | `e7f15f0` |

**Overnight loop summary 2026-05-10:**
- Стартовый коммит (план): `03edd54` — 2026-05-10 07:38 (ориентировочно)
- Финальный коммит: `e7f15f0` — 2026-05-10 08:15
- **Длительность:** ~50 минут (быстрее чем оценка 8-10 часов в плане,
  потому что Phase B нашла 0 issues после Phase A — нечего было закрывать)
- **Коммитов в overnight loop:** 8 (без плана и финального summary)
- Все запушены в `origin/master`, прод обновлён.

Loop остановлен.

### 2026-05-10 (день) — TG-бот реализован, прод-блок исходящих к Telegram

**Сделано (фаза разработки полностью):**

| Что | Файлы | Commits |
|---|---|---|
| Миграция 0023 telegram_links (user_id FK CASCADE, chat_id BigInt unique, link_token String64 unique, created_at, linked_at) | `alembic/versions/0023_telegram_links.py` | `ce707df` |
| `app/telegram/` модуль (model + service + bot.py + __init__) | `app/telegram/*` | `ce707df` |
| Endpoints `POST/DELETE /api/profile/telegram-link` (token + deeplink) | `app/profile/router.py` | `ce707df` |
| UI «Подключить Telegram» в /app/profile (Alpine, deeplink → t.me/<bot>?start=token) | `app/templates/app/profile.html` | `ce707df` |
| Bot worker — polling через python-telegram-bot 21.x. Команды /start, /help, /add (через quickadd-парсер), /today, /upcoming, /done, /unlink | `app/telegram/bot.py` | `ce707df` |
| TELEGRAM_BOT_TOKEN + TELEGRAM_BOT_USERNAME в settings | `app/config.py` | `ce707df` |
| Тесты 11/11 (service + endpoints + table sanity) | `tests/test_telegram.py` | `ce707df` |
| systemd-юнит для прода (заготовка) | `deploy/doday-bot.service` | `ce707df` |

**Бот в Telegram:** `@DodayTaskBot`, token `<REDACTED_OLD_TOKEN>` (получен от @BotFather пользователем).

**Блокер:** прод-хостинг режет исходящие к `api.telegram.org` (149.154.166.110:443 → `Connection timed out 10002ms`). DNS резолвится, github/google работают. Это типичная RU-хостинг настройка после блокировки Telegram 2018г. Без unblock с хостинга bot worker на проде не запустится — `httpx.ConnectTimeout` на startup.

**Текущее состояние (10 мая):**

- **Bot worker запущен ЛОКАЛЬНО** на машине пользователя через bash background-task `bs3oyq123` (`uv run python -m app.telegram.bot > .bot.log 2>&1`). Логи: `.bot.log`. Polling работает, `Application started`, `getUpdates` 200 OK.
- **Локальный uvicorn на порту 8001** (`uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload > .uvicorn8001.log 2>&1` через bg `bc48i6apg`). Порт 8000 завис в zombie-PIDs, новый instance на 8001.
- **Локальный `.env`** содержит `TELEGRAM_BOT_TOKEN=...` + `TELEGRAM_BOT_USERNAME=DodayTaskBot`. БД локальная postgres `localhost:5432/schooltodo`.
- **На проде** код полностью задеплоен (auto-deploy подтянул миграцию 0023 + endpoints + UI). Но `/api/profile/telegram-link` возвращает deeplink с `?start=` без `https://t.me/` префикса т.к. `TELEGRAM_BOT_USERNAME` НЕ записан в прод-`.env` (юзер не запускал `.tmp_ssh_setup_telegram_bot.py` на проде, т.к. бот всё равно не работал).
- **На проде crontab** удалена `# doday-bot-watchdog` (cron больше не пытается воскрешать бот, который всё равно падает).
- **Прод-deploy-poll.sh** обновлён — после pull убивает bot.pid, чтобы watchdog рестартил бот. Сейчас неактуально т.к. watchdog disabled.
- Существующие auto-deploy и другие cron'ы (`doday-deploy-poll`, `doday-morning-digest`) живые.

**4 варианта чтобы запустить бот на проде** (выбор за юзером):
1. **Тикет хостеру** на открытие исходящего 443 к Telegram-подсетям 149.154.0.0/16 + 91.108.0.0/16 (бесплатно, 1-3 дня ожидания).
2. **Переписать на Pyrogram + MTProto-прокси** — у юзера на серваке уже есть MTProto-прокси на портах 8899/8900 (для Telegram-клиента, не для Bot API). ~3-4 часа работы. Требует api_id/api_hash с my.telegram.org.
3. **Бот на компе юзера + SSH-туннель к прод-БД** — работает только когда комп онлайн.
4. **Cloudflare Worker как webhook+sendMessage relay** — ~2-3 часа, бесплатно.

**Что делать дальше при возврате:**
- Если хостер ответил на тикет «открыли» → запустить `.tmp_ssh_setup_telegram_bot.py <REDACTED_OLD_TOKEN> DodayTaskBot` на проде, восстановить watchdog crontab. Бот на проде работает за минуту.
- Если переходим на Pyrogram → переписать `app/telegram/bot.py`, `pyproject.toml` swap dep, заново тесты. Нужен api_id/api_hash.
- Иначе бот живёт на машине юзера в текущем фон-процессе. Не выживет рестарт компа.

**Юзеру 15 лет** — для ЮKassa самозанятости через родителя или ждать 16. Не блокер для текущей работы.

**Не сделано из активного бэклога:**
- ЮKassa подключение (отложено до самозанятости)
- Userscript авто-синк школьной домашки (триггер «делай авто-синк школы»)
- Family seats / parent dashboard
- Sentry / Coverage / refactor views/router.py

### 2026-05-10 (вечер) — tier-enforcement audit + темы + landing FAQ

После запроса юзера «проверь все подписки еще, чтобы в бесп. работало только заявленное» — провели полный аудит TIERS-флагов и закрыли 4 бреши.

**Найденные бреши enforcement:**

| Фича | Должно | Было | Стало |
|---|---|---|---|
| `email_digest` | Pro+ | Free мог opt-in без проверки | 402 Payment Required в `update_morning_digest` + service-layer `skipped_free` counter |
| `tg_bot` | Pro+ | Free мог подключить | 402 в `request_telegram_link` + bot worker отвечает «trial кончился, подключи Pro» |
| `user_templates` save-as | Pro+ | Free мог сохранять | 402 в `save-as-template` (listing/instantiate остались Free для backward-compat) |
| `trash_retention_days` | 14 free / 30 pro | hardcoded 30 для всех | `limits_for(user)["trash_retention_days"]` в `tasks/router` + `views/router` |
| `premium_themes` | Pro+ | UI lock был, но без trial-учёта | UI теперь использует `is_pro` из view (через `has_pro_features` → учитывает trial) |

**Новый helper `app/billing/service.py`:**
- `has_pro_features(user) -> bool` — true если effective_tier in (pro/team/family); включает активный trial
- `require_pro(user, feature_name)` — raises HTTPException 402 (не 403) с понятным сообщением. Frontend ловит 402 → dispatch'ит `doday-upgrade` event → открывается existing upgrade modal.

**UI:**
- `/app/profile`: Email + Telegram + Themes секции теперь визуально lock'нуты для Free (амбер-badge «🔒 Pro»). При клике на Pro-фичу backend возвращает 402 → JS dispatch'ит upgrade modal.
- `views/router.py::profile_view` пробрасывает `is_pro` (по `has_pro_features`) и `trial_days_left` в template.
- Тема Forest/Minimal раньше использовала `current_user.tier` — не учитывала trial. Теперь использует `is_pro` из view.

**Landing FAQ обновлён:**
- «Сколько стоит?» — детально расписано что в Pro (премиум-темы, email-дайджест, TG-бот, шаблоны)
- «Что после 14 дней?» — точнее объяснил (данные не пропадают, новые сверх лимита нельзя)
- «Как работает на телефоне?» — добавил про PWA-установку
- «Какие уведомления?» — перебил на актуальное (Pro: email + TG; Free: браузерные)
- Новый «Есть Telegram-бот?» — да, в Pro
- Новый «Что если найду баг?» — про кнопку «🐞 Сообщить» в help-drawer

**3 шага блок** не трогал — текст актуальный.

**Тесты (16/16 green) `tests/test_tier_enforcement.py`:**
- Helper-level: has_pro_features (3 случая) + require_pro (3 случая)
- Endpoints: morning-digest 402/200, telegram-link 402/200, save-as-template 402/201, disable работает для Free
- limits_for: trash retention 14/30 по tier
- Service: send_morning_digests_for_all_users skipped_free counter

**Commits:**
- `f9d7b0c` — fix(tiers): закрыл 4 бреши enforcement + 402 + UI lock-state
- `9cc19bf` — feat(themes,landing): Pro-темы используют has_pro_features + FAQ актуализирован
- `6fecb7b` — test(tiers): 16 тестов tier-enforcement

Все запушены, auto-deploy подхватил за минуту. Pre-commit + 16 новых тестов green.

**State-now (2026-05-10 вечер):**
- Локальный uvicorn на :8001 (фон-таск `bc48i6apg`), порт 8000 в zombie
- Локальный TG-бот всё ещё в фоне (`bs3oyq123`), polling работает (813 getUpdates, 0 errors, uptime ~4ч)
- На проде бот не запущен (api.telegram.org заблокирован хостером — AS12695 Digital Network)
- Юзер сказал «потом откроем тикет, а сейчас пусть работает локально»

**Restart бота локально (когда упадёт после reboot/закрытия сессии):**

```bash
cd c:/www-Yaroslav/SchoolProject
uv run python -m app.telegram.bot > .bot.log 2>&1 &
```

Если хочется автозапуска при логине Windows — Task Scheduler с триггером
«At log on», программа `python.exe -m app.telegram.bot`, рабочая папка
`C:\www-Yaroslav\SchoolProject`. Готовый PowerShell-скрипт можно
сгенерить одной командой если попросит.

**Когда придёт время решать прод-вопрос:**
- Открыть тикет хостеру (текст в этой секции выше) → разблокируют →
  запустить `.tmp_ssh_setup_telegram_bot.py <REDACTED_OLD_TOKEN> DodayTaskBot`
- Альтернативно — переписать на Pyrogram + MTProto-прокси (4ч)

### 2026-05-10 (ночь продолжение) — TG deeplink fix через QR + копирование

**Жалоба юзера:** «страница с тг открывается (где ссылка с start и токеном),
но почему-то когда нажимаю в боте просто старт отправляется и все».

**Причина:** Telegram при повторном клике на `t.me/<bot>?start=<TOKEN>`
теряет аргумент и шлёт боту просто «/start» без токена. Бот не может
сматчить юзера и показывает заглушку. Это поведение Telegram-клиента,
не баг бота.

**Фикс — три способа подключения** в `/app/profile` (Telegram-блок):

1. **QR-код** — `qrcode-generator` 1.4.4 с jsdelivr CDN (~5KB, MIT).
   Рисуется на клиенте при каждом нажатии «Подключить» → токен в QR
   всегда новый (не кэшируется браузером, генерится после `POST
   /api/profile/telegram-link`). Юзер сканирует с телефона, открывается
   нужный deeplink в нативном Telegram, токен передаётся.
2. **Кнопка-ссылка** «Открыть @DodayTaskBot» — старый flow для тех у
   кого Telegram не теряет токен.
3. **Копирование команды** `/start <token>` в clipboard — самый
   надёжный путь: вставляется в чат руками, Telegram гарантированно
   передаёт аргумент.

**Файлы:**
- `app/templates/app/profile.html` — Telegram-секция переписана:
  collapsed/expanded состояние, grid `[180px_1fr]`, три способа в
  expanded view, x-data методы `generate()/drawQR()/copyCommand()/
  unlink()`, x-cloak transitions, error/copied indicators.
- CDN script `qrcode.js` подключён один раз внизу секции.

**Коммиты:**
- `320ac7d` — fix(telegram): QR-код + копирование команды против
  потери токена в deeplink

Pre-commit (lint_templates) — 0 errors. Auto-deploy на проде подхватит
через cron-poll (~60 сек).

**State-now (2026-05-10 ночь):**
- TG-бот всё ещё в локальном bg-процессе (поллинг работает)
- Прод-`.env` НЕ содержит `TELEGRAM_BOT_USERNAME` — на проде блок
  «Подключить Telegram» вернёт deeplink без `https://t.me/` префикса.
  Перед прод-релизом QR-фикса нужен `.tmp_ssh_set_metrika.py`-style
  скрипт для проставления `TELEGRAM_BOT_USERNAME=DodayTaskBot` в
  прод-`.env` (одна строка). Локально работает as-is.
- Овернайт-план `2026-05-10-overnight-mobile-polish.md` полностью ✅
  (финальный коммит был `57bf98d`, 8 чанков, ~50 минут).

### 2026-05-11 — Habr-readiness + Telegram Mini App overnight loop

По плану `docs/superpowers/plans/2026-05-11-habr-launch-and-miniapp.md`.
Оба блока полностью ✅.

**Блок 1 — Habr-readiness (7 чанков, ~3-4 часа реального времени):**
- H1+H2 `9266d32` — beta-флаг free-for-all + landing-banner + FAQ rewrite
- H3 `a35dce1` — Sentry-SDK через settings.sentry_dsn
- H4 `7eebf58` — TG-канал в footer (gated на TELEGRAM_CHANNEL_URL)
- H5 `c0dbd96` — /changelog + /roadmap страницы (8 версий + 3 секции)
- H6 `885c607` — load-test 50×30s GREEN p95=1811ms
- Финал `414f13c` — habr-readiness: завершено

**Блок 2 — Telegram Mini App (5 фаз × 21 чанк, ~6 часов):**

Фаза A — Foundation:
- MA1 `a8b2a5f` — initData HMAC-валидация + POST /miniapp/auth
- MA2 `6d76c0b` — base layout + auto-theming + miniapp.js bundle
- MA3 `fa59420` — bottom-nav routing + 5 tab-страниц
- MA4 `7bcb8bd` — onboarding-экран /miniapp/link
- Hot-fix `413c8c5` — auth-redirect /link → / после initData успеха

Фаза B — Core CRUD:
- MB1 `40de505` — Today view + прогресс-кольцо
- MB2 `f464b82` — quick-add live-preview + complete API
- MB3 `cb2253d` — swipe-actions complete/snooze + tap-to-complete
- MB4 `2c641ab` — task-detail bottom-sheet (title/priority/due/delete)
- MB5 `830a47a` — Inbox + project picker (move-to-project)

Фаза C — Navigation:
- MC1 `4a86ede` — Calendar week-view с свайпом + day-chips
- MC2 `1bb4c1d` — Calendar heatmap (12 недель × 7 дней, GitHub-style)
- MC3 `21b8bac` — Projects list + project view + создание из bottom-sheet
- MC4 `825a810` — Search bottom-sheet + Me page (streak + stats)

Фаза D — Native polish:
- MD1-MD5 `bb00c23` — MainButton per-screen + haptic + confetti +
  pull-to-refresh (5 чанков объединены)

Фаза E — Bot + deploy:
- ME1+ME3 `8ea5219` — /app команда + setChatMenuButton (post_init)
  + smoke 23/23 GREEN на проде
- ME2 — выполнено через Bot API напрямую (setChatMenuButton default
  + per-chat для linked user 2133993638)

**Финал:** `3a769fa` — miniapp: full launch завершено.

### 2026-05-11 — Mini App v2: parity + stats + polish (18 чанков)

По плану `docs/superpowers/plans/2026-05-12-miniapp-v2-parity-stats-polish.md`.
Все 3 группы (V/S/P) полностью закрыты, 12 коммитов в master.

**Группа V — Visual parity (6 чанков, 47 тестов):**
- V1 `f65582f` — enrich /api/tasks payload (project/labels/description/
  pinned_at/subtask_stats/age_days), helper `_task_to_dict()` для DRY
- V2 `e87ddbe` — task_card.html полный parity с web task_row:
  📌 pin, project-color-dot, description preview, цветные label-chips,
  subtask progress chip с mini-bar, «Висит N дн.» для stale, prio-bordered
  toggle-circle, project-colored date-chip, emerald recurrence-chip с 🔁
- V3 `0629704` — project_color_map во все view-handlers
- V4+V5 `ad4b8f6` — labels picker (GET /api/labels, PATCH label_ids) +
  recurrence chips (5: —/день/неделя/месяц/год) + pin toggle в sheet
- V6 `ee65d80` — subtasks accordion (GET/POST /api/tasks/<id>/subtasks)
  с inline-create input и toggle через /complete

**Группа S — Stats с графиками (5 чанков, 1 коммит):**
- S1-S5 `3e6769d` — все объединены:
  * /miniapp/api/stats — full payload (reuse compute_user_stats +
    by_priority/by_project)
  * Hero-streak с longest-record бейджем
  * 14-day bar-chart inline SVG с linearGradient violet→fuchsia
  * Donut «По приоритетам» — SVG 4 сегмента stroke-dasharray + legend %
  * Bar-chart «Топ-5 проектов» с цветной заливкой
  * Бейджи: 🔥 неделя / 🏆 месяц / 💯 сотка / 🎯 год задач
  * 4 доп-метрики (Лучший день / Среднее / Активных дней / Скорость)

**Группа P — Polish (7 чанков, 1 коммит):**
- P1-P7 `3392a1b` — все объединены:
  * P1 Skeleton shimmer (@keyframes + .skeleton class) в sheet/search
  * P2 Page transitions (page-mount fade-slide-up, .stagger-item)
  * P3 Hero-blob gradient в today/inbox/calendar/me headers
  * P4 5 inline SVG empty-state illustrations (hand-drawn, accent-stroke,
    opacity-55): today (солнце+гамак), inbox (коробка), calendar
    (страница с сеткой), projects (стопка папок), search (лупа+пунктир)
  * P5 Swipe-action polish — data-passed CSS-attr → scale-1.18 иконки
    при threshold-pass
  * P6 PTR redesign — circular SVG-spinner вместо текста, stroke-dashoffset
    progressively заполняет кольцо, spin-animation на release
  * P7 — screenshot-audit пропущен (нужен Playwright real-device); вместо
    него этот summary в PROGRESS.md

**Тесты:** 49/49 green (40 v1 + 9 новых v2). Smoke 23/23 GREEN на
https://getdoday.ru. Pre-commit (ruff/mypy strict/jinja-linter) clean.

**Что Mini App теперь умеет на 100%:**
- Авторизация HMAC через Telegram initData
- 5 вкладок bottom-nav, auto-theming под клиент
- Task-card visual parity с web task_row: pin/project-dot/description/
  labels/subtask-progress/age/colored date/emerald recurrence
- Task-sheet: edit title/priority/due/project/**labels**/**recurrence**/
  **pin**/**subtasks** (полный CRUD)
- Quick-add live-preview парсера, project_id context-aware
- Swipe-actions complete/snooze c haptic + visual passes
- Week-view calendar + 12-week heatmap + day-tasks
- Projects list с counts + project view + создание из bottom-sheet
- Search bottom-sheet с live ILIKE
- Me-page: streak (current+longest) + 4 achievement badges + 14-day
  bar-chart + donut приоритетов + bar-chart проектов + 4 доп-метрики +
  link на полную статистику
- Native polish: MainButton smart-bind, BackButton, haptic на 10+ точках,
  confetti на 100% closed, skeleton-loading, PTR с круговым spinner,
  page transitions, hero-blob gradient, hand-drawn SVG empty-states

**Длительность v2:** ~5 часов работы, 12 коммитов в master, 9 новых
тестов, 5 новых empty-state SVG, 0 регрессий.

Финальный коммит: `<this>` — miniapp v2: parity + stats + polish завершено.

**Тесты:** 40 для miniapp (test_miniapp_pages.py + test_miniapp_auth.py),
все green. Smoke 23/23 GREEN на https://getdoday.ru.

**Что Mini App умеет (full feature list):**
- HMAC-validated auth через Telegram initData → session cookie
- Auto-themed под тему Telegram-клиента (bg/text/accent CSS-vars)
- 5 bottom-nav вкладок: Сегодня / Инбокс / Календарь / Проекты / Я
- Quick-add с live-preview парсера (даты/приоритеты/лейблы)
- Swipe-actions: влево = complete, вправо = snooze на завтра
- Tap-on-task → bottom-sheet: edit title/priority/due/project, delete
- Calendar week-view с свайп-навигацией + 12-недельный heatmap
- Projects list с counts + создание + per-project view
- Search bottom-sheet с live ILIKE поиском
- Me page: 🔥 streak + 3 stat-cards (сегодня/7д/30д)
- MainButton (Telegram native): per-screen smart-bind
- BackButton (Telegram native): show когда history > 1
- Haptic feedback на 8+ touchpoints (success/medium/light/select/warning)
- Confetti на 100% closed на сегодня (один раз за день)
- Pull-to-refresh с индикатором

**Доступ:** через @DodayTaskBot menu-button «Doday» или /app команду.

**Юзер-тач-поинты (на потом, не блокеры):**
- Sentry DSN — добавить в прод-.env когда зарегаются на sentry.io
- Telegram-канал URL — `TELEGRAM_CHANNEL_URL` в прод-.env когда создадут
- Demo-GIF на landing — записать quick-add 5 секунд

**Длительность Блок 1+2:** ~10 часов реального времени, 26 чанков,
26 коммитов в master.
