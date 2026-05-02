# Claude инструкции для проекта SchoolTodo

## Первое что нужно сделать в каждой сессии

1. Прочитай **`PROGRESS.md`** в корне проекта — там текущее состояние, что сделано, что следующее.
2. Прочитай **`docs/superpowers/specs/2026-05-02-school-todo-design.md`** — это главная спецификация проекта.
3. Прочитай свой `MEMORY.md` — там user/project/feedback memory.

## Используй superpowers всегда

В этом проекте обязательно используй skills из плагина **superpowers** на каждом шаге разработки:

- **`superpowers:brainstorming`** — для обсуждения новых фич перед написанием кода.
- **`superpowers:writing-plans`** — для составления детального плана реализации.
- **`superpowers:executing-plans`** — для пошаговой реализации плана.
- **`superpowers:test-driven-development`** — обязательно для всего бизнес-критичного кода (синхронизация, биллинг, диари-источники).
- **`superpowers:systematic-debugging`** — при любой ошибке/баге.
- **`superpowers:verification-before-completion`** — перед заявлением "готово".
- **`superpowers:requesting-code-review`** — после крупных кусков работы.

Если в активной сессии есть skill из superpowers, который применим (даже на 1%) — **обязательно вызывай через Skill tool**.

## Язык

Общение и комментарии в коде/документации — **на русском**. Имена переменных, функций, классов — на английском.

## Tech stack

См. полный список в спецификации. Кратко:
- Backend: Python 3.12 + FastAPI
- Frontend: Jinja2 + HTMX + Alpine.js + Tailwind CSS (минимум JS!)
- БД: PostgreSQL + SQLAlchemy + Alembic
- Очереди: Dramatiq + Redis
- Деплой: Docker Compose + nginx + Let's Encrypt
- Хостинг: РФ-провайдер (Selectel/Timeweb)

**Не используем:** React, Vue, Svelte, Celery, Django, MongoDB.

## Особенности пользователя

Главный разработчик — опытный, **но слабоват в JavaScript**. Объясняй JS-термины простыми словами. Архитектурно избегаем сложного клиентского JS.

## Что НЕ делаем в этом проекте

- ❌ Авто-выполнение ДЗ нейросетью (отказались осознанно).
- ❌ Не показываем оценки.
- ❌ Не парсим МЭШ в MVP (только authedu.mosreg.ru).
- ❌ Не пишем фронт на React/Vue/Svelte.
- ❌ Не храним пароли пользователей от дневников (только токены сессии, зашифрованные).

## После каждой важной работы

- Обнови `PROGRESS.md` (что сделано, что следующее).
- При важных архитектурных решениях — обнови или создай project memory в `~/.claude/projects/c--www-Yaroslav-SchoolProject/memory/`.
