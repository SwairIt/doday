# todosites.md — функционал 8 todo-сервисов (deep crawl)

**Метод**: Playwright-обход каждого сайта (landing + features pages где есть) + полный текст Habr-статьи `https://habr.com/ru/companies/leadertask/articles/991040/` через `page.evaluate`. Скриншоты `*-landing.png` и `*-features.png` в корне репо.

**Источник**: статья на Habr (автор maiya_dom, 2 фев 2026, 11k просмотров) — структура каждого приложения: Кому подойдет / Сильная сторона / Слабые места / Основные возможности / Что понравилось / Что мешает / Интеграции / Платформы / Цены.

**Дата**: 2026-05-19 14:49 МСК

---

## 1. ЛидерТаск (https://www.leadertask.ru/)

Российский продукт, в реестре отеч. ПО, ООО «Органайзер ЛидерТаск» (Ярославль), развивается с 2011 года. ИНН: 7603051760. CEO — Иван Абрамовский.

**Скриншоты**: `leadertask-landing.png`, `leadertask-features.png`

### 1.1 Способы создания задачи
- 1.1.1 Вручную в приложении
- 1.1.2 По email (forward → task)
- 1.1.3 Прямо в Telegram
- 1.1.4 Голосом в приложении
- 1.1.5 Через виджет в браузере

### 1.2 Настройка задач
- 1.2.1 Напоминания и повторения
- 1.2.2 Чек-листы и описания
- 1.2.3 Чаты и вложения в карточку
- 1.2.4 Метки, цвета и **Фокус** (выделить главное)

### 1.3 Иерархия и проекты
- 1.3.1 Дерево задач — неограниченная вложенность подзадач
- 1.3.2 Проекты с неограниченной вложенностью подпроектов
- 1.3.3 Канбан-доски (Kanban / Agile / SCRUM)
- 1.3.4 Избранное — быстрый доступ

### 1.4 Контроль и порядок
- 1.4.1 Фильтры по: дате, статусу, исполнителю, проекту, др.
- 1.4.2 Сортировка по важности / срокам / др.
- 1.4.3 Раздел «Актуальное» — непрочитанные, просроченные
- 1.4.4 Корзина и архив с восстановлением

### 1.5 Календарь — 5 видов
- 1.5.1 День
- 1.5.2 Неделя
- 1.5.3 Месяц
- 1.5.4 Год
- 1.5.5 **10 лет** (уникально среди 8 приложений)

### 1.6 Команды
- 1.6.1 Поручения с дедлайнами и контролем прогресса
- 1.6.2 Совместные проекты + комментарии + файлы
- 1.6.3 Общие доски
- 1.6.4 Уведомления о изменениях
- 1.6.5 Роли и права доступа, отделы
- 1.6.6 **Публичные доски** для внешних участников
- 1.6.7 **Жёсткий контроль поручений** (исполнитель не может скрытно менять)

### 1.7 Платформы (5)
- 1.7.1 Веб
- 1.7.2 Windows
- 1.7.3 Android
- 1.7.4 iOS
- 1.7.5 **На ваш сервер** (self-hosted)

### 1.8 Синхронизация
- 1.8.1 Облачная между устройствами (на платных тарифах)
- 1.8.2 **Офлайн-режим** — работа без интернета, автосинк
- 1.8.3 Расширения для браузера

### 1.9 Интеграции
- 1.9.1 Telegram (двусторонняя — задачи + уведомления)
- 1.9.2 Яндекс.Календарь (импорт)
- 1.9.3 Google Календарь (экспорт)
- 1.9.4 Email-to-task

### 1.10 Цены (точно)
- 1.10.1 Бесплатно: 1 устройство, до 100 карточек, до 10 проектов, до 3 досок, **БЕЗ облачной синхронизации**
- 1.10.2 Премиум: 3199 ₽/год (личный)
- 1.10.3 Бизнес: от 4999 ₽/год за пользователя

---

## 2. Strive (https://striveapp.ru/)

В реестре отеч. ПО. С 2022 года 30 000+ команд. На лендинге 40+ кейсов (Буллитт, MISTY, Вкускиппер, Kovalev.media и др.).

**Скриншот**: `strive-landing.png`

### 2.1 Карточка задачи
- 2.1.1 Ярлыки
- 2.1.2 Чек-листы
- 2.1.3 Исполнители
- 2.1.4 Дедлайны
- 2.1.5 Приоритетность
- 2.1.6 **Таймер** (тайм-трекинг)
- 2.1.7 Быстрые ссылки прямо на доске

### 2.2 Виды (4)
- 2.2.1 Список
- 2.2.2 Доски (Kanban)
- 2.2.3 Календарь
- 2.2.4 **Диаграмма Ганта**

### 2.3 Документация и база знаний
- 2.3.1 Хранение знаний компании
- 2.3.2 **Публичные документы** (внешние ссылки)
- 2.3.3 **Тесты по регламентам** (онбординг)
- 2.3.4 **Печать в PDF**
- 2.3.5 Древовидная навигация
- 2.3.6 **Автоматизация онбординга**
- 2.3.7 **Совместное редактирование документов**

### 2.4 Контроль и фокус
- 2.4.1 Тайм-трекинг
- 2.4.2 Уведомления: smartphone + browser + Telegram (selective — только важное)
- 2.4.3 **Визуальные сигналы**: 🔥 (горячая) / 🐌 (устаревшая)
- 2.4.4 История изменений per task
- 2.4.5 Приоритеты + сортировка

### 2.5 Команды
- 2.5.1 **Чат и файлы в задачах** (тред-style)
- 2.5.2 **Telegram интеграция** (двусторонняя)
- 2.5.3 **Реакции** на сообщения
- 2.5.4 **Online presence** в задачах (видно кто сейчас в задаче)
- 2.5.5 История действий
- 2.5.6 Раздача прав на уровне пространств
- 2.5.7 Приглашения по ссылке или email

### 2.6 Платформы
- 2.6.1 Web (только онлайн, нет офлайна)
- 2.6.2 iOS app
- 2.6.3 Android app
- 2.6.4 **«Коробка» (self-hosted)** — упомянуто в кейсе MISTY

### 2.7 Цены
- 2.7.1 Free: 0₽, до 10 человек, безлимит pro features
- 2.7.2 На двоих: 1000₽/мес, 2 user
- 2.7.3 Команда: 3375₽/мес, до 15 user
- 2.7.4 Бизнес: 250₽/user/мес, 15+

---

## 3. Todoist (https://www.todoist.com/)

Doist Inc. 19 лет 111 дней разработки. 50M+ professionals, 374k 5-star ratings, 30M+ app installs, 2B+ tasks done, 160+ стран, 1M+ Pro users. SOC2 Type II сертификация. 19 языков.

**Скриншоты**: `todoist-landing.png`, `todoist-features.png`

### 3.1 Быстрый ввод
- 3.1.1 Quick Add распознает: дату/время, приоритет, ярлык, проект — в одной строке
- 3.1.2 NLP-парсер ("послезавтра", "следующая среда")
- 3.1.3 Email-add-ons (forward → Todoist)
- 3.1.4 Browser extensions
- 3.1.5 Mobile widgets
- 3.1.6 Wearable widgets

### 3.2 Структура задач
- 3.2.1 Проекты → разделы → задачи → подзадачи
- 3.2.2 Чек-листы внутри задачи
- 3.2.3 Приоритеты (4 уровня)
- 3.2.4 Метки (теги)
- 3.2.5 Описания задач
- 3.2.6 Файловые вложения (до 5 MB free)

### 3.3 Виды
- 3.3.1 Список
- 3.3.2 Календарь (на Pro)
- 3.3.3 Доска (Kanban)
- 3.3.4 Today view
- 3.3.5 Upcoming (week-overview)

### 3.4 Фильтры и метки
- 3.4.1 Кастомные фильтры (DSL: `@label & today`, `#project & p1`)
- 3.4.2 Сохранённые smart-списки
- 3.4.3 На Beginner до 3 фильтров, на Pro безлимит

### 3.5 Командная работа
- 3.5.1 Shared projects (приглашения по email)
- 3.5.2 Назначение задач (assigned_to)
- 3.5.3 Комментарии + файлы + голосовые сообщения
- 3.5.4 50,000+ команд использует
- 3.5.5 Public + private team projects
- 3.5.6 Sharing по invite link
- 3.5.7 Filter by team / personal
- 3.5.8 Roles + permissions

### 3.6 Templates (50+, по категориям)
- 3.6.1 Работа
- 3.6.2 Личное
- 3.6.3 Учёба
- 3.6.4 Управление
- 3.6.5 Маркетинг и продажи
- 3.6.6 Поддержка

### 3.7 Productivity tools
- 3.7.1 **Todoist Karma** (gamification points)
- 3.7.2 Productivity visualizations (week/month graphs)
- 3.7.3 Activity history
- 3.7.4 Completed tasks archive
- 3.7.5 **Todoist Assist** (AI feature, новинка)

### 3.8 Платформы (5+)
- 3.8.1 Web
- 3.8.2 Windows desktop
- 3.8.3 macOS desktop
- 3.8.4 Android
- 3.8.5 iOS
- 3.8.6 **Wearables** (Apple Watch, Wear OS)
- 3.8.7 Browser extensions (Chrome, Firefox, др.)
- 3.8.8 Email add-ons (Gmail, Outlook)

### 3.9 Интеграции
- 3.9.1 80+ third-party интеграций
- 3.9.2 Google Calendar (two-way на Pro)
- 3.9.3 Outlook Calendar
- 3.9.4 API для разработчиков
- 3.9.5 Zapier / Make / IFTTT

### 3.10 Безопасность
- 3.10.1 SOC2 Type II
- 3.10.2 Облачное хранение

### 3.11 Цены
- 3.11.1 Beginner (Free): 5 проектов, 3 фильтра, 5 MB файлы, БЕЗ кастомных напоминаний, БЕЗ календарной раскладки
- 3.11.2 Pro: $7/мес monthly, $5/мес at $60/год
- 3.11.3 Business: $10/мес per user monthly, $8/мес at $96/год per user

---

## 4. TickTick (https://ticktick.com/)

**Скриншот**: `ticktick-landing.png`

### 4.1 5 main pillars
- 4.1.1 To-Do List — organize everything
- 4.1.2 Calendar Views — yearly / monthly / weekly / daily / agenda
- 4.1.3 **Pomodoro** — 25-min intervals + white noise
- 4.1.4 **Habit Tracker** — rich library + tracking + statistics
- 4.1.5 **Countdown** ("Dida") — birthdays, anniversaries, exams, deadlines

### 4.2 Views (полный список)
- 4.2.1 Calendar
- 4.2.2 Kanban
- 4.2.3 Timeline (lightweight project mgmt)
- 4.2.4 **Eisenhower Matrix** (urgency × importance)
- 4.2.5 **Sticky Note view**

### 4.3 Reminders
- 4.3.1 Notification + multiple alerts + lock screen pinning (iOS)
- 4.3.2 **Constant Reminder** — ring until task done
- 4.3.3 **Email Reminder**
- 4.3.4 Repeat Reminder (weekly/monthly/yearly/custom)
- 4.3.5 **Location Reminder** (iOS geofence)
- 4.3.6 Daily Reminder для planning ритуала

### 4.4 Quick input
- 4.4.1 NLP-парсинг времени
- 4.4.2 Voice input → text
- 4.4.3 Виджеты на home screen
- 4.4.4 Global desktop keyboard shortcut
- 4.4.5 Right-click selection в браузере → task

### 4.5 Productivity
- 4.5.1 Filter (custom queries)
- 4.5.2 Keyboard shortcuts + command menu
- 4.5.3 Collaboration: shared lists + task assignment
- 4.5.4 Integration: calendar subscriptions, Notion
- 4.5.5 Statistics: tasks + focus duration + habit logs
- 4.5.6 **40+ themes**
- 4.5.7 Custom list backgrounds
- 4.5.8 Time zone aware

### 4.6 Платформы
- 4.6.1 Phone (iOS / Android)
- 4.6.2 Computer (Win / Mac / Linux)
- 4.6.3 Tablet
- 4.6.4 **Watch** (Apple Watch + Wear OS)

### 4.7 Special programs
- 4.7.1 TickTick for Education — 25% скидка для teachers + students

### 4.8 Цены (Habr)
- 4.8.1 Free: 9 lists, 99 tasks, 2 reminders/task, 5 habits, 1 attachment/day, shared до 2, "Plan Your Day" 2x/week
- 4.8.2 Premium: $35.99/год — лимиты сняты

---

## 5. Мяудза (https://myaudza.ru/)

В реестре отеч. ПО. На лендинге 8 персон с stories (Тимлид, CEO стартапа, Дизайнер-фрилансер, Предприниматель, Репетитор, Маркетолог, Блогер, Студентка).

**Скриншот**: `myaudza-landing.png`

### 5.1 4 pillars
- 5.1.1 **Календарь** — все проекты в одном
- 5.1.2 **Документы**
- 5.1.3 **Канбан**
- 5.1.4 **Коммуникация** (мессенджер + видеовстречи)

### 5.2 Виртуальный офис
- 5.2.1 Структура проектов
- 5.2.2 Роли и права
- 5.2.3 Чаты и треды
- 5.2.4 **Планерки** (видеовстречи)

### 5.3 Фокус
- 5.3.1 **Фокус дня** — выделение важного
- 5.3.2 **Закладки** — частые задачи / материалы
- 5.3.3 **Фильтры-шаблоны** (preset filters)
- 5.3.4 **Дашборд** (планируется)

### 5.4 Управление задачами
- 5.4.1 Канбан-доски + перетаскивание в календарной сетке
- 5.4.2 Повторы + чек-листы + файлы + теги + приоритеты
- 5.4.3 Сохранённые фильтры
- 5.4.4 Согласование (если в тарифе)

### 5.5 Roadmap (что планируется)
- 5.5.1 Весна 2026: API интеграции, личные сообщения, заметки/документы, гостевой доступ, **Sync Google Calendar**, MyaudzaStore
- 5.5.2 Лето 2026: Мероприятия, **аудиосообщения**, дашборд, диаграмма продуктивности, **Timeline + Гант в календаре**, система лояльности, командные цели
- 5.5.3 Зима 2026: Интеллект-карты, JAM-доски, **ИИ Мяудза**, автоматизация и боты, **почта с доменом**, облачное хранилище, **интеграция нейросетей**

### 5.6 Платформы
- 5.6.1 Web
- 5.6.2 Mobile (iOS / Android)
- 5.6.3 Windows desktop
- 5.6.4 **Linux desktop (Ubuntu)** — редкость среди РФ-сервисов
- 5.6.5 macOS desktop

### 5.7 Цены
- 5.7.1 СТАРТ: 0 ₽ (сейчас, обычно 290 ₽) — до 5, 3 канбан-доски, мастер-календарь, безлимит переговорки
- 5.7.2 ПРО: 490 ₽/user/мес — до 100, безлимит доски, теги, чаты+треды, роли, безлимит архив
- 5.7.3 ЭНТЕРПРАЙЗ: по запросу — от 1000 user, **закрытый контур** (on-prem)

---

## 6. Tweek (https://tweek.so/)

Минималистичный weekly planner — «бумажный» feel.

**Скриншот**: `tweek-landing.png`

### 6.1 Stats (live на лендинге)
- 6.1.1 90,518 tasks today
- 6.1.2 16,384 active users / 24h
- 6.1.3 4.8 stars App Store, 5,900 reviews

### 6.2 Views (3)
- 6.2.1 Week (default — горизонтальные дни)
- 6.2.2 Month
- 6.2.3 Day

### 6.3 UX patterns (показано в onboarding)
- 6.3.1 **Hover to complete** (немедленный feedback)
- 6.3.2 Click to edit (inline)
- 6.3.3 **Drag to other day**
- 6.3.4 **Color picker** для каждой задачи (визуальные категории)
- 6.3.5 Save моментально (no save button)

### 6.4 Someday section
- 6.4.1 Для задач без даты (длинный backlog)

### 6.5 Premium features
- 6.5.1 Subtasks
- 6.5.2 Notes
- 6.5.3 Вложения
- 6.5.4 Reminders
- 6.5.5 Repeats
- 6.5.6 Themes
- 6.5.7 Sync Google Calendar (one-way)
- 6.5.8 Sync Apple Calendar

### 6.6 Special
- 6.6.1 **Printable weekly templates** (бумажные шаблоны)
- 6.6.2 Localization 14+ languages
- 6.6.3 REST API (с лимитами по тарифу)
- 6.6.4 Export XML / TXT (web only)
- 6.6.5 ChatGPT интеграция (упомянуто в FAQ)

### 6.7 Платформы
- 6.7.1 Web
- 6.7.2 iOS app
- 6.7.3 Android app
- 6.7.4 iPad landscape support

### 6.8 Цены
- 6.8.1 Free: $0, лимит 2 calendars
- 6.8.2 Premium: $5.99/мес или $49.99/год — все features

---

## 7. Google Tasks (https://tasks.google.com/)

Часть Google Workspace. Tasks.google.com сразу редиректит на login — поэтому маркетинг-страница `workspace.google.com/products/tasks/` стала основным источником.

**Скриншот**: `googletasks-landing.png`

### 7.1 Главная позиция
- 7.1.1 "Stay on top of your to-dos where you're already working"
- 7.1.2 Deep integration с Gmail / Calendar / Chat / Docs / Drive
- 7.1.3 Полностью бесплатно

### 7.2 Workspace integrations
- 7.2.1 **Track tasks in Google Calendar** — date+time → calendar event
- 7.2.2 **Add task from Gmail sidebar** — без context switch
- 7.2.3 **Delegate tasks in Google Docs** (Workspace only)
- 7.2.4 **Create & assign tasks in Google Chat / Spaces**
- 7.2.5 **Sidebar в Google Drive**

### 7.3 Reminders / Repeats
- 7.3.1 Reminders по дате/времени
- 7.3.2 **Nudges** — continue prompting until done
- 7.3.3 Auto-repeat: daily, weekly, monthly, annually + custom (every N weeks, by weekday)

### 7.4 Time blocking (новое 17 ноября 2025!)
- 7.4.1 Block time для task в календаре
- 7.4.2 Customize visibility
- 7.4.3 **Mute notifications** во время focus
- 7.4.4 **Auto-decline meetings** в focus block

### 7.5 Управление
- 7.5.1 Separate task lists (по контексту/клиенту/теме)
- 7.5.2 **Star priority** (binary, simple — нет 4-уровневых приоритетов как у Todoist)
- 7.5.3 Подзадачи
- 7.5.4 Drag-to-reorder

### 7.6 Cross-device sync
- 7.6.1 Веб через Calendar/Gmail sidebar
- 7.6.2 Android app + iOS app
- 7.6.3 Sync через Google Account

### 7.7 Limits
- 7.7.1 До 100,000 задач total (vs 99 у TickTick Free!)
- 7.7.2 До 20,000 incomplete per list

### 7.8 Слабые стороны (Habr)
- 7.8.1 Нет приоритетов (только star) / тегов / фильтров
- 7.8.2 Нет удобного поиска между списками
- 7.8.3 Нет CSV/ICS экспорта кнопкой (только Takeout)

### 7.9 Цена
- 7.9.1 **Бесплатно** (с Google Account)

---

## 8. Obsidian + Tasks plugin (https://obsidian.md/)

PKM-приложение, задачи через community plugin Tasks (авторы Martin Schenck + Clare Macrae).

**Скриншот**: `obsidian-landing.png`

### 8.1 Core principles
- 8.1.1 **Your thoughts are yours** — local storage, even offline
- 8.1.2 **Your mind is unique** — 1000+ plugins+themes
- 8.1.3 **Your knowledge should last** — open Markdown format
- 8.1.4 **Free without limits** — base app полностью free

### 8.2 Core features
- 8.2.1 **Links** между notes ([[Wiki-style]])
- 8.2.2 **Graph** — visualize relationships
- 8.2.3 **Canvas** — infinite whiteboard для brainstorming
- 8.2.4 **Plugins** — 1000+ community + open API

### 8.3 Community plugins (для tasks workflow)
- 8.3.1 **Calendar** (Liam Cain) — view daily notes
- 8.3.2 **Kanban** (Matthew Meyers) — Markdown-backed kanban
- 8.3.3 **Dataview** (Michael Brenan) — advanced queries
- 8.3.4 **Outliner** (Viacheslav Slinko) — list manipulation
- 8.3.5 **Tasks** (Schenck + Macrae) — track tasks across vault

### 8.4 Tasks plugin specifics
- 8.4.1 **Query DSL** — filter by date/tag/folder/priority/status
- 8.4.2 **Boolean logic** AND / OR / NOT
- 8.4.3 **Custom JavaScript filters**
- 8.4.4 **Inline metadata** через emoji (🔼 high, 🔽 low, 🔁 recurring, ⏳ scheduled)
- 8.4.5 **Multi-date fields**: due / start / scheduled / done / created
- 8.4.6 **Auto done-date** при completion
- 8.4.7 **Priority levels**
- 8.4.8 **Task IDs** for dependency linking
- 8.4.9 **Dashboard pages** через query blocks
- 8.4.10 **Recurring rules** (estimated даты)
- 8.4.11 Natural language даты (tomorrow, next Monday)

### 8.5 Sync (Obsidian Sync, paid)
- 8.5.1 **E2E encryption**
- 8.5.2 **Version history** (1 год)
- 8.5.3 **Shared vaults** с roles (Owner / Can edit / Read only)
- 8.5.4 **Collaboration** на shared files
- 8.5.5 Fine-grained sync control (subset folders/files)

### 8.6 Publish (paid)
- 8.6.1 Notes → online wiki / KB / digital garden
- 8.6.2 Seamless editing
- 8.6.3 Customization

### 8.7 Платформы
- 8.7.1 Windows / macOS / Linux
- 8.7.2 iOS / Android
- 8.7.3 Sync alternatives: iCloud / Dropbox / Drive / Syncthing / Git (бесплатно с conflict risk)

### 8.8 Цены
- 8.8.1 Free: full app + plugins (personal use)
- 8.8.2 Obsidian Sync: $4/мес Standard или $8/мес Plus
- 8.8.3 Obsidian Publish: $8/мес
- 8.8.4 Commercial license: $50/год per user

---

## Cross-app comparison matrix

| Фича | LT | ST | TD | TT | MY | TW | GT | OB |
|---|---|---|---|---|---|---|---|---|
| Kanban | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ (плагин) |
| Calendar | ✅ 5 видов | ✅ | ✅ (Pro) | ✅ 5 видов | ✅ | ✅ Week | ✅ | ✅ (плагин) |
| Gantt | ❌ | ✅ | ❌ | ✅ Timeline | ✅ Q3'26 | ❌ | ❌ | ✅ (плагин) |
| Pomodoro | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Habit tracker | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Countdown | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Eisenhower matrix | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Email-to-task | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ (Gmail) | ❌ |
| Voice input | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Telegram интеграция | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Google Calendar sync | one-way | ❌ | ✅ (Pro 2way) | ✅ Premium | ✅ план | ✅ Premium one-way | ✅ native | ✅ (плагин) |
| Видеовстречи | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Чат-мессенджер | ❌ | ✅ task-chat | ❌ | ❌ | ✅ полноценный | ❌ | ✅ Chat | ❌ |
| Offline mode | ✅ | ❌ | ✅ Pro | partial | ❌ | ❌ | ❌ | ✅ |
| Native Linux desktop | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Self-hosted | ✅ | ✅ | ❌ | ❌ | ✅ enterprise | ❌ | ❌ | ✅ vault |
| Wearables (watch) | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Browser extension | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| AI / GPT | ❌ | ❌ | ✅ Assist | ❌ | ✅ план | ✅ ChatGPT | ❌ | через плагины |
| 10-year view | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Public sharing | ✅ доски | ✅ docs | ✅ link | ❌ | ❌ | ❌ | ❌ | ✅ Publish |
| API public | ❌ | ❌ | ✅ | ✅ OpenAPI | ✅ план | ✅ REST | ✅ Tasks API | ✅ через плагины |
| Темы / customization | минимум | минимум | минимум | **40+ тем** | минимум | **темы Premium** | минимум | **1000+ плагинов** |
| Print | ❌ | ✅ docs PDF | ❌ | ❌ | ❌ | ✅ weekly | ❌ | ✅ Markdown |
| Templates | ❌ | ✅ регламенты | **50+** | ❌ | ❌ | ✅ printable | ❌ | ✅ vault templates |
| 2FA | proprietary | ❌ | ✅ Pro | ❌ | ❌ | ❌ | ✅ Google | ❌ |
| SOC2 / compliance | реестр отеч ПО | реестр отеч ПО | **SOC2 Type II** | ❌ | реестр отеч ПО | ❌ | ✅ Google Cloud | ❌ |

Легенда: LT=ЛидерТаск, ST=Strive, TD=Todoist, TT=TickTick, MY=Мяудза, TW=Tweek, GT=Google Tasks, OB=Obsidian

---

## Уникальные фичи каждого приложения

### ЛидерТаск
- **10-летний обзор календаря** (life planning) — никто кроме них не делает
- Жёсткий контроль поручений (исполнитель не может скрытно менять)
- Self-hosted на свой сервер

### Strive
- Тесты по регламентам (онбординг внутри сервиса)
- Online presence в задачах (мини-аватарка кто сейчас в задаче)
- Кейс-маркетинг 40+ stories на лендинге

### Todoist
- Todoist Karma (gamification with points + streaks)
- 50+ ready-made templates по 6 категориям
- Todoist Assist (AI feature)
- SOC2 Type II сертификация
- 19 лет в разработке (тренд: long-term trust)

### TickTick
- Eisenhower Matrix view
- Sticky Note view (новый!)
- Habit Tracker встроенный
- Pomodoro со встроенным white noise
- Countdown к датам
- Constant reminder (ring until done)
- 40+ themes
- TickTick for Education (25% off)

### Мяудза
- Встроенный мессенджер с тредами
- Видеоконференции прямо в приложении
- Multi-OS desktop (Win+Linux+Mac)
- 8 персон на лендинге (multi-audience marketing)

### Tweek
- Bare-minimum weekly view (нет nav menu вообще)
- Drag-to-different-day с paper-feel
- Printable weekly templates (бумажные шаблоны)
- Live counter на лендинге
- "Weekly cure" positioning (анти-перегрузка)

### Google Tasks
- Native time blocking в Google Calendar
- Nudges (повторяющиеся напоминания до выполнения)
- Auto-decline meetings во время focus
- Gmail sidebar для add без context switch
- Google Docs assignment
- 100k tasks limit (vs 99 у TickTick Free)
- Полностью бесплатно

### Obsidian + Tasks
- Local-first (полный контроль)
- Markdown open format (no lock-in)
- Linked notes [[wiki-style]] + knowledge graph
- Canvas infinite whiteboard
- 1000+ community plugins
- Query DSL для tasks
- Boolean фильтры AND/OR/NOT
- Custom JavaScript filters
- E2E encryption (Sync)
- Publish notes как digital garden

---

## Gap-анализ для Doday (для Task 2)

Полный матч на actual code в `app/`. См. Task 2 ниже.

---

## Task 2 verification (Playwright deep audit)

Зарегистрирован тестовый юзер (`loop-test-19may-v2@example.com`), 18 страниц Doday прокликаны через Playwright. Скриншоты в `docs/screenshots/doday-{01-18}-*.png`. Per-feature аудит против 8 категорий A-L — в `.loop_verification.md`.

**Итог**: 45 фич ⊕ реально работают, 30 ⊖ остаются gap'ом (документировано с причиной — либо архитектурно крупно, либо отклонено в pivot'е, либо требуют внешних зависимостей вне session).
