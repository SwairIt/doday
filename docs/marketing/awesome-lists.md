# Awesome lists — PR entries для бесплатных пассивных stars

Самый дешёвый способ долгосрочно копить GitHub stars: PR в популярные `awesome-*` списки. **Один PR = просмотры списка месяцами**.

**Правила PR в awesome-lists:**
- Прочитай CONTRIBUTING.md (если есть) — каждый список имеет свои форматные требования
- Размер entry — **≤ 1 строка markdown** обычно
- Категория — выбери правильную (не клади «todo» в «webapps»)
- Alphabetical order — большинство списков отсортированы
- Без emoji в title (если только список сам их не использует)
- Pull request commit message: `Add Doday — short description`
- PR description: 2-3 строки про проект + ссылка

---

## 1) awesome-fastapi

**Репо:** https://github.com/mjhea0/awesome-fastapi  
**Категория:** «Open Source Projects → Personal Projects» или «Real-world Apps»  
**Format:** `- [Name](url) — Description.`

**Entry:**

```markdown
- [Doday](https://github.com/SwairIt/doday) — Free open-source todo app with web UI, Telegram Mini App, and bot. FastAPI + HTMX + Alpine + Tailwind. Shared projects, comments, Pomodoro, recurring tasks. MIT.
```

**PR description:**

```
Adds Doday to the Real-world Apps section.

Doday is a free MIT-licensed todo app with three surfaces (web, Telegram
Mini App, bot) built on FastAPI 0.115 + async SQLAlchemy 2.0 + Pydantic
v2. Live at https://getdoday.ru.

Features include shared projects with email-based invitations,
owner/member roles, task assignment, recurring tasks, Pomodoro,
comments. mypy --strict + ruff strict-set + 650 tests + CI on GitHub
Actions.

I'm the author. The codebase serves as a real-world example of FastAPI
+ HTMX without React, with end-to-end auth, sharing, and Mini App
integration. Hope it's useful for the list!
```

---

## 2) awesome-self-hosted

**Репо:** https://github.com/awesome-selfhosted/awesome-selfhosted  
**Категория:** «Software → Task management & to-do lists»  
**Format:** `- [Doday](https://getdoday.ru) - Description. ([Source Code](https://github.com/SwairIt/doday)) `MIT` `Python``

**Entry:**

```markdown
- [Doday](https://getdoday.ru) - Free todo app with Telegram Mini App and bot interface. Shared projects with email invitations, recurring tasks, Pomodoro, comments. ([Source Code](https://github.com/SwairIt/doday)) `MIT` `Python`
```

**CONTRIBUTING.md** of this repo requires:
- Stable releases (1+ year old) — **risk: too new, may reject**. If they reject — comment "happy to wait, here's a milestone tag", note re-submission for `v1.0` release in 6+ months.
- AGPL/free-licensed (MIT counts).
- Self-hostable (yes — single-process uvicorn + Postgres).

**Try awesome-russian-self-hosted** as fallback if main rejects:  
https://github.com/awesome-selfhosted/awesome-selfhosted-data  (similar but data-driven, easier acceptance).

---

## 3) awesome-htmx

**Репо:** https://github.com/rajasegar/awesome-htmx  
**Категория:** «Real World Apps» или «Examples»  
**Format:** `- [Name](url) - description`

**Entry:**

```markdown
- [Doday](https://github.com/SwairIt/doday) - Todo app with web UI + Telegram Mini App + bot. FastAPI + HTMX 2 + Alpine + Tailwind CDN. Real-world example of HTMX in production with shared projects + auth.
```

**PR description:**

```
Adds Doday under "Real World Apps".

It's a free MIT todo app built on HTMX 2 (no React, no JS build step).
Three surfaces (web, Telegram Mini App, bot) sharing one FastAPI
backend.

Specifically illustrates:
- HTMX hx-get/hx-post/hx-target/hx-swap throughout the task management UI
- Combining HTMX with Alpine for inline state (Alpine for in-page reactivity,
  HTMX for server round-trips)
- Tailwind CDN + Jinja2 templates as the alternative to a React bundle

Live: https://getdoday.ru. Code: https://github.com/SwairIt/doday.

I'm the author.
```

---

## 4) awesome-telegram-bots / awesome-telegram-mini-apps

**Репо (попробуй оба):**
- https://github.com/yajia7674/awesome-telegram-bots
- https://github.com/topics/telegram-mini-app (нет одного списка, но есть похожие)

**Если awesome-telegram-mini-apps НЕ существует** — **создай свой!** Это никем не занятая ниша. Просто `awesome-telegram-mini-apps` репо у тебя на GitHub. Через 6-12 месяцев + 50-100 stars, твой список станет первым в Google по этому слову. Это hack.

**Entry для существующего:**

```markdown
- [Doday](https://t.me/DodayTaskBot) ([source](https://github.com/SwairIt/doday)) - Open-source todo bot with native Mini App. Tasks, shared projects, Pomodoro, recurring tasks, comments. MIT.
```

---

## 5) awesome-russian-developers / awesome-russian-startups (если есть)

**Поиск:** https://github.com/search?q=awesome+russian&type=repositories

Если найдёшь подходящий — entry:

```markdown
- [Doday](https://getdoday.ru) — бесплатный open-source todo (web + Telegram Mini App + бот). FastAPI + HTMX. MIT. Автор — школьник 15 лет.
```

---

## 6) awesome-mypy / awesome-python-typing

**Если найдёшь** список ультра-стрикт Python проектов:

```markdown
- [Doday](https://github.com/SwairIt/doday) - Real-world FastAPI app with `mypy --strict` across 38 modules. Pre-commit-enforced. MIT.
```

---

## 7) Hacktoberfest projects (если попадёшь в октябрь)

**Тематические списки:** хостятся каждый октябрь
**Подача:** add `hacktoberfest` topic to your GitHub repo settings → автоматически попадаешь в discoverability

---

## Чек-лист для каждого PR

- [ ] Fork the repo
- [ ] Прочитай `CONTRIBUTING.md` если есть
- [ ] Сделай **минимальный** edit — 1 строка add, не trailing whitespace
- [ ] Commit message: `Add Doday`
- [ ] PR title: `Add Doday — todo app with Telegram Mini App`
- [ ] PR body: 2-3 строки про проект + ссылка
- [ ] Не отправляй несколько PR одновременно в один список — выглядит как спам
- [ ] **После merge** — добавь badge `[![Awesome](https://...)](https://github.com/.../awesome-fastapi)` в свой README. Это feedback loop — твой README показывает что ты в awesome, awesome показывает на твой README.

---

## Если PR висит больше 30 дней

- **Не баги** — большие awesome-lists модерируются медленно (раз в 1-3 месяца batch'ами)
- Просто жди. Большинство PR в итоге merge'нутся
- Если совсем безответно через 6 месяцев — закрой PR с комментом «no problem if not a fit», открой новый позже когда у тебя 100+ stars

---

## Ожидаемый эффект

| Если PR merged | Эффект |
|---|---|
| awesome-fastapi (12k stars) | ~50-200 stars / квартал, ~500-5000 visitors / месяц |
| awesome-self-hosted (200k stars) | ~100-500 stars / квартал, ~5000-50000 visitors / месяц |
| awesome-htmx (1k stars, but niche) | ~5-30 stars / квартал, более targeted audience |
| awesome-telegram-* | сильно зависит от размера списка |

Suмarно если merged 3-5 списков → **+200-1000 stars / квартал** пассивно. Это **бесплатное продвижение которое работает годами**.
