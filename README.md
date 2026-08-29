<div align="center">

# Doday — планировщик для школы и учёбы

**Домашка из электронного дневника · расписание уроков · напоминания в Telegram · помодоро**
Веб · Telegram Mini App · бот — один бэкенд на всё.

[![CI](https://github.com/SwairIt/doday/actions/workflows/ci.yml/badge.svg)](https://github.com/SwairIt/doday/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![HTMX](https://img.shields.io/badge/HTMX-2-3366cc)](https://htmx.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-1325-success)](#тесты-и-качество)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**[Открыть → getdoday.ru](https://getdoday.ru)** · **[Все проекты → all.getdoday.ru](https://all.getdoday.ru)** · **[Бот → @DodayTaskBot](https://t.me/DodayTaskBot)** · **[Блог](https://getdoday.ru/blog)** · **[Тарифы](https://getdoday.ru/pricing)**

[English version below ↓](#doday--a-planner-for-school-and-study)

</div>

---

## Что это

**Doday** — бесплатный планировщик задач и туду-лист на русском языке, сделанный для школьников и студентов. Домашние задания подтягиваются из электронного дневника, расписание уроков лежит рядом с задачами, напоминания приходят в Telegram, а вечером ничего не забывается, потому что список один и он всегда под рукой.

Если коротко: это **ежедневник, список дел и трекер домашки в одном месте** — в браузере, в Telegram и на телефоне как приложение.

Автор — [Ярослав Боев](https://github.com/SwairIt) (SwairIt).

### Кому пригодится

- **школьнику 5–11 класса** — чтобы не забывать, что задали, и делать уроки быстрее;
- **студенту колледжа или вуза** — сессия, курсовые, дедлайны, пары;
- **родителю** — видеть, что задано, и не спрашивать «ты сделал?»;
- **репетитору и учителю** — расписание занятий, запись учеников, домашние задания;
- **всем остальным** — это обычный todo-лист с проектами, метками и повторениями, просто с уклоном в учёбу.

<div align="center">

![Раздел блога Doday](docs/habr-screenshots/s-01-blog-index.png)

</div>

---

## Возможности

### Задачи и планирование

- задачи с приоритетами P1–P4, сроками, описанием и подзадачами любой вложенности;
- **быстрый ввод на русском языке**: «сдать реферат завтра в 18:00 !!! @школа» — дата, время, приоритет и метка разбираются из текста;
- повторяющиеся задачи: каждый день, по будням, еженедельно, по своему правилу;
- проекты и секции внутри проектов, канбан-доска, перетаскивание мышью;
- метки, свои фильтры, поиск по всему списку;
- представления: **Входящие · Сегодня · Ближайшие · Календарь** (день, неделя, месяц);
- корзина с восстановлением, дубликаты задач, массовые действия;
- комментарии к задачам и вложенные ссылки.

### Школа и учёба

- **синхронизация домашних заданий** с МЭШ (dnevnik.mos.ru) и Школьным порталом Московской области — домашка сама превращается в задачи;
- расписание уроков с предметами и кабинетами;
- учебный стрик: сколько дней подряд ты не забросил уроки;
- разбор задач в **[Razbery](https://getdoday.ru/qa/)** — школьное Q&A, где отвечают объяснением, а не готовым решением;
- тренажёр билетов **[ПДД](https://getdoday.ru/pdd/)** — официальные билеты ГИБДД, экзамен по правилам, статистика ошибок;
- **[блог](https://getdoday.ru/blog)** — 334 статьи про домашку, экзамены, прокрастинацию, конспекты и предметы.

### Напоминания и Telegram

- напоминания о задачах в Telegram и push в браузере;
- утренний дайджест на почту: что сегодня, что просрочено;
- **[бот @DodayTaskBot](https://t.me/DodayTaskBot)**: `/add` — добавить задачу, `/today` — что сегодня, `/upcoming`, `/done`;
- **Telegram Mini App** — полноценное приложение внутри мессенджера, со свайпами и вибрацией.

### Привычки, фокус и статистика

- помодоро-таймер с настраиваемыми интервалами;
- трекер привычек и дневник настроения;
- учёт времени по задачам;
- достижения и уровни, графики выполненного, статистика по проектам и дням.

### ИИ-помощник

- чат с языковой моделью **на своём ключе** — вы подключаете ключ провайдера, а не платите нам;
- кнопка **«Отправить в ИИ»** у каждой задачи: она открывает чат с уже приложенной задачей;
- можно приложить несколько задач и спросить, с чего начать;
- шаблоны вопросов: «объясни простыми словами», «проверь моё решение»;
- ключ шифруется при сохранении, переписка видна только вам, пользоваться можно с 18 лет.

### Совместная работа

- проекты на несколько человек: приглашение по ссылке, назначение исполнителей, комментарии;
- **Family** — тариф на пять аккаунтов для семьи;
- публичные ссылки на прогресс, экспорт в JSON, CSV и Markdown, импорт обратно.

### Приватность

- страница **«Мои данные»**: видно, что о вас хранится, там же выгрузка и удаление аккаунта;
- удаление аккаунта — необратимое, вместе со всеми данными, одной кнопкой;
- нет рекламы и продажи данных;
- база и сервер — в России.

---

## Скриншоты

<div align="center">

![Статья блога с оглавлением](docs/habr-screenshots/s-02-blog-article.png)

![ИИ-помощник внутри приложения](docs/habr-screenshots/s-03-ai-chat.png)

![Страница «Мои данные»](docs/habr-screenshots/s-05-my-data.png)

</div>

---

## Технологии

| Слой | Что использую |
|---|---|
| **Бэкенд** | FastAPI 0.115 · SQLAlchemy 2.0 (async) · Pydantic v2 |
| **База** | PostgreSQL 16 · asyncpg · Alembic |
| **Шаблоны** | Jinja2, серверный рендеринг |
| **Интерактив** | HTMX 2 · Alpine.js — без React и без сборки |
| **Стили** | Tailwind CSS через CDN |
| **Telegram** | python-telegram-bot · WebApp SDK · оплата Stars |
| **Почта** | aiosmtplib + шаблоны писем |
| **Авторизация** | argon2id · подписанная cookie-сессия с отзывом |
| **Логи** | structlog в JSON · Sentry |
| **Инструменты** | uv · ruff · mypy --strict · pre-commit · pytest |
| **CI/CD** | GitHub Actions · автодеплой по push |

**Почему не React.** Весь интерфейс — серверный рендеринг плюс HTMX для частичных обновлений и Alpine.js для мелкого состояния. Ни сборки, ни `node_modules`, ни гидратации. На мобильном это заметно быстрее среднего SPA, а разработка одним человеком идёт втрое быстрее.

---

## Цифры проекта

| Что | Сколько |
|---|---|
| Строк кода | 86 000 (38 000 Python + 27 000 шаблоны + 21 000 тесты) |
| Тестов | 1325 |
| Коммитов | 780+ |
| Миграций базы | 59 |
| Модулей приложения | 41 |
| Статей в блоге | 334 (617 000 слов) |
| Первый коммит | 2 мая 2026 |
| Деплой | `git push` → прод обновлён за минуту |

---

## Быстрый старт

Нужны [uv](https://docs.astral.sh/uv/), Python 3.12+ и PostgreSQL 14+.

```bash
git clone https://github.com/SwairIt/doday.git
cd doday
cp .env.example .env

# в .env заполнить:
#   APP_SECRET_KEY    → python -c "import secrets; print(secrets.token_urlsafe(48))"
#   DATABASE_URL      → postgresql+asyncpg://user:pass@localhost:5432/doday
#   TEST_DATABASE_URL → отдельная база для тестов

createdb doday
createdb doday_test
uv sync
uv run alembic upgrade head
uv run python -m uvicorn app.main:app --reload
```

Открыть `http://localhost:8000`, зарегистрироваться, ссылку подтверждения посмотреть в консоли.

Локальный SMTP для писем, если нужен:

```bash
uv run python -m aiosmtpd -n -l localhost:1025
```

---

## Структура

Модули собраны **по функциям, а не по слоям**: у каждой фичи свои модели, схемы, сервис и роутер рядом.

```
app/
  tasks/        задачи: модели, сервис, API
  projects/     проекты, секции, участники
  auth/         регистрация, вход, защита от ботов
  ai/           ИИ-помощник: ключи, чат, безопасность
  school/       синхронизация с электронным дневником
  blog/         334 статьи из markdown-файлов
  qa/           Razbery — школьное Q&A
  pdd/          тренажёр билетов ПДД
  lessio/       кабинет репетитора и запись клиентов
  miniapp/      Telegram Mini App
  telegram/     бот и уведомления
  billing/      тарифы и оплата
  ...           ещё около тридцати модулей
```

---

## Тесты и качество

```bash
uv run python -m pytest tests -q          # весь набор, 1325 тестов
uv run python -m ruff check .             # линтер
uv run python -m ruff format --check .    # форматирование
uv run python -m mypy --strict app        # типы, строгий режим
uv run python scripts/lint_templates.py   # проверка шаблонов
uv run python scripts/blog_check.py       # проверка статей блога
```

`mypy --strict` зелёный по всему приложению. `pre-commit` гоняет линтер, форматирование и типы на каждом коммите, CI — весь набор тестов на каждый push.

---

## Что было интересного в разработке

Подробные разборы — в статьях, коротко:

- **176 ботов за две недели** и последовавший аудит: подделка `X-Forwarded-For`, из-за которой не работали все лимиты по IP; хранимый XSS через JSON-LD; IDOR в JSON-ручке; сессия, которую нельзя было отозвать.
- **ИИ на ключе пользователя**: шифрование чужих ключей, SSE-стриминг в FastAPI и грабля с `finally` в асинхронном генераторе, из-за которой пропадали ответы.
- **334 статьи как код**: markdown в репозитории, автопроверки структуры и ссылок, дисковый кэш — раздел открывался 11,7 секунды, стал 0,67.
- **Пять продуктов в одном монолите**: HTMX вместо React, грабли Telegram Mini App, оплата через Stars.

---

## Частые вопросы

**Это бесплатно?** Да. Основное — бесплатно навсегда, без карты. Есть платный тариф с дополнительными возможностями и семейный на пять человек.

**Чем отличается от Todoist и других планировщиков?** Уклоном в учёбу: домашка из электронного дневника, расписание уроков, разборы задач, тренажёр ПДД. Плюс всё на русском и работает в Telegram.

**Как импортировать домашние задания из дневника?** В настройках подключается школьный портал — МЭШ или Школьный портал Московской области. Задания превращаются в задачи автоматически.

**Работает ли на телефоне?** Да: как обычный сайт, как приложение (PWA) и как Telegram Mini App.

**Есть ли Telegram-бот?** Есть — [@DodayTaskBot](https://t.me/DodayTaskBot). Добавляет задачи, присылает напоминания и утренний список дел.

**Можно ли пользоваться вместе с одноклассниками или семьёй?** Да, проекты общие: приглашение по ссылке, назначение исполнителей, комментарии.

**Мои данные в безопасности?** Пароли хранятся хешем, соединение по HTTPS, токены и ключи шифруются, база в России. На странице «Мои данные» видно, что именно хранится, и всё можно скачать или удалить.

---

## Другие мои проекты

Все собраны на **[all.getdoday.ru](https://all.getdoday.ru)**:

| Проект | Что это |
|---|---|
| **[Doday Tasks](https://getdoday.ru)** | Планировщик для школы и учёбы |
| **[Razbery](https://getdoday.ru/qa/)** | Школьное Q&A: объяснения вместо готовых ответов |
| **[Doday ПДД](https://getdoday.ru/pdd/)** | Тренажёр официальных билетов ГИБДД |
| **[Lessio](https://getdoday.ru/lessio)** | Страница записи и кабинет для репетиторов |
| **Tap Tower** | Аркада для Telegram Mini Apps |

---

<div align="center">

# Doday — a planner for school and study

**Homework from the school diary · lesson schedule · Telegram reminders · Pomodoro**
Web · Telegram Mini App · bot — all on one backend.

</div>

## What it is

**Doday** is a free task manager and todo list built for students. Homework is pulled from the electronic school diary, the lesson schedule sits next to the tasks, reminders arrive in Telegram, and nothing gets forgotten because there's a single list that's always at hand.

Built solo by [Yaroslav Boev](https://github.com/SwairIt) (SwairIt) since May 2026.

**Live:** [getdoday.ru](https://getdoday.ru) · **All projects:** [all.getdoday.ru](https://all.getdoday.ru)

## Features

**Tasks and planning** — priorities P1–P4, due dates, subtasks of any depth, natural-language quick add, recurring tasks, projects with sections, a kanban board, labels, custom filters, Inbox / Today / Upcoming / Calendar views, trash with restore, bulk actions, comments and attached links.

**School** — homework sync with Russian electronic school diaries, lesson schedule, study streak, a Q&A site where answers are explanations rather than solutions, an official traffic-rules ticket trainer, and a 334-article blog about studying.

**Reminders and Telegram** — task reminders in Telegram, browser push, a morning email digest, a bot with `/add`, `/today`, `/upcoming`, and a full Mini App inside the messenger.

**Focus and stats** — Pomodoro timer, habit tracker, mood log, time tracking, achievements, charts per project and per day.

**AI assistant** — a chat with a language model **on the user's own API key**: an "Ask AI" button on every task, several tasks attachable as context, prompt templates, streamed answers. Keys are encrypted at rest; the conversation belongs to the user.

**Collaboration** — shared projects with invite links, assignees and comments, a Family plan for five accounts, public progress links, export to JSON / CSV / Markdown and import back.

**Privacy** — a "My data" page showing exactly what's stored, with one-click export and irreversible account deletion. No ads, no data selling.

## Stack

FastAPI 0.115 · SQLAlchemy 2.0 async · Pydantic v2 · PostgreSQL 16 · Alembic · Jinja2 · HTMX 2 · Alpine.js · Tailwind · python-telegram-bot · argon2id · structlog · uv · ruff · mypy --strict · pytest · GitHub Actions.

No React, no bundler, no `node_modules`. Server-side rendering plus HTMX for partial updates and Alpine.js for small state.

## Numbers

86,000 lines of code · 1,325 tests · 780+ commits · 59 migrations · 41 modules · 334 blog articles · first commit on 2 May 2026 · deploy is a single `git push`.

## Quick start

```bash
git clone https://github.com/SwairIt/doday.git
cd doday
cp .env.example .env          # set APP_SECRET_KEY, DATABASE_URL, TEST_DATABASE_URL
createdb doday && createdb doday_test
uv sync
uv run alembic upgrade head
uv run python -m uvicorn app.main:app --reload
```

## Engineering write-ups

- **176 bots in two weeks** and the audit that followed: `X-Forwarded-For` spoofing that made every IP rate limit decorative, stored XSS through JSON-LD, an IDOR in a JSON endpoint, a session that couldn't be revoked.
- **AI on the user's own key**: encrypting someone else's secret, SSE streaming in FastAPI, and why `finally` in an async generator silently ate answers.
- **334 articles built like code**: markdown in the repository, automated structure and link checks, a disk cache that took the section from 11.7 s to 0.67 s.

## FAQ

**Is it free?** Yes — the core is free forever, no card required. A paid tier and a five-seat family plan exist on top.

**How is it different from Todoist?** It leans into studying: homework from the school diary, lesson schedules, explanations instead of ready answers, and it lives inside Telegram.

**Does it work on mobile?** Yes — as a website, as a PWA and as a Telegram Mini App.

---

## Ключевые слова

Планировщик задач · туду лист · todo list на русском · список дел онлайн · ежедневник · трекер домашних заданий · приложение для школьников · планировщик для студента · расписание уроков онлайн · напоминание о домашнем задании · домашка из МЭШ · Школьный портал Московской области · дневник · помодоро таймер · трекер привычек · канбан доска · менеджер задач бесплатно · аналог Todoist на русском · task manager · student planner · homework tracker · school planner · Telegram Mini App todo · FastAPI HTMX example · Python monolith example.

---

## Автор и лицензия

**Ярослав Боев** ([@SwairIt](https://github.com/SwairIt)) — разработка, дизайн, инфраструктура и тексты.
Написано на Python в паре с терминальным ИИ-агентом; архитектурные решения, ревью и ответственность — авторские.

Сайт: [getdoday.ru](https://getdoday.ru) · Все проекты: [all.getdoday.ru](https://all.getdoday.ru) · Почта: doday.support@gmail.com

Лицензия — [MIT](LICENSE).
