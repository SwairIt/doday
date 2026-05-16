# Doday Launch Kit

Готовые pitch-тексты для всех каналов кроме Хабра (он отдельно — `docs/articles/2026-05-12-habr-launch.md`).

## Что внутри

| Файл | Куда | Когда |
|---|---|---|
| [`english-article.md`](english-article.md) | dev.to, Medium, Hashnode | День +1 после Хабра |
| [`show-hn.md`](show-hn.md) | Hacker News (Show HN) | День +1, утром EST (~17:00 МСК) |
| [`reddit.md`](reddit.md) | r/SideProject, r/selfhosted, r/programming | Распределить на 3 дня |
| [`cold-dm.md`](cold-dm.md) | Влиятельным дев-блогерам РФ | День +2-3 |
| [`podcast-pitch.md`](podcast-pitch.md) | «Запуск разрешаю», «Между скобок», «Сергеев и Кравченко» | День +3, ответят за неделю-две |
| [`awesome-lists.md`](awesome-lists.md) | PR в awesome-fastapi / awesome-htmx / awesome-telegram-mini-apps | День +1, low-effort high-passive |
| [`tg-pitch.md`](tg-pitch.md) | TG-каналы (Python / индихакеры / школьники / mini-apps) | День +1, 3-5 каналов в день |
| [`kwork-offers.md`](kwork-offers.md) | kwork.ru — **деньги в карман** | СЕГОДНЯ, не зависит от launch'a |

## Timeline (вокруг даты Хабр-публикации = **День 0**)

### День -1 (сегодня, пока Хабр на ревью)
- [ ] Записать `demo.gif` (см. [docs/assets/HOW_TO_RECORD.md](../assets/HOW_TO_RECORD.md))
- [ ] Создать TG-канал `@doday_diary`, опубликовать пост #1-#2 из [tg-channel-drafts.md](../tg-channel-drafts.md)
- [ ] **Опубликовать 3 kwork-оффера** — независимо от Хабра, реальный cash
- [ ] PR в awesome-fastapi / awesome-telegram-mini-apps (entries из awesome-lists.md)

### День 0 (Хабр одобрил)
- [ ] **Утро 10:00 МСК** — публикация Хабр-статьи
- [ ] +30 мин — пост #6 в TG-канал со ссылкой на Хабр
- [ ] +1ч — TG-pitch в 3-5 каналов (Python / индихакеры) из tg-pitch.md
- [ ] +2ч — VC.ru кросс-пост ([`docs/articles/2026-05-12-cross-post-dtf-vc.md`](../articles/2026-05-12-cross-post-dtf-vc.md))
- [ ] +4ч — DTF кросс-пост
- [ ] **Дежурство на комментариях Хабра** — отвечать в течение 5-10 минут

### День +1
- [ ] **Утро 17:00 МСК / 8:00 EST** — Show HN ([`show-hn.md`](show-hn.md))
- [ ] r/SideProject пост (раздел Reddit в [`reddit.md`](reddit.md))
- [ ] dev.to + Medium ([`english-article.md`](english-article.md))
- [ ] Indie Hackers Milestone post

### День +2
- [ ] r/selfhosted пост
- [ ] Cold-DM 3 блогерам ([`cold-dm.md`](cold-dm.md))
- [ ] Подкаст-pitch ([`podcast-pitch.md`](podcast-pitch.md)) — 3 email'a

### День +3-7
- [ ] r/programming пост (отдельный угол — anti-React HTMX-манифест)
- [ ] Школа/одноклассники — тет-а-тет демо
- [ ] Анализ Yandex.Метрики, удвоить что работает

## Принципы pitch'a

- **«15-летний» — в каждом первом предложении.** Это твой главный hook.
- **GIF-демо — в каждом посте.** Текст про код не убедит, GIF убедит.
- **Open source — в первой строке.** Дев-аудитория ценит, инвесторы тоже.
- **Конкретные цифры** (350 коммитов, 650 тестов, 10 дней) **>** общие слова («много работы»).
- **Без хвастовства, без сожаления.** Прямо: «сделал — вот это, открыто — вот тут».
- **Ссылка на GitHub в подписи / footer'е поста.** Чтобы dev-публика стартанула с кода, юзеры — с сайта.

## Что НЕ делать

- ❌ Не публикуй ВСЁ за 1 день — TG/Reddit-алгоритмы любят постепенность, плюс ты не успеешь модерировать комменты.
- ❌ Не используй один и тот же текст в нескольких каналах — каждая площадка любит свой angle.
- ❌ Не вступай в холивары в комментах — на провокации отвечай фактами, без эмоций. У тебя один шанс на первое впечатление.
- ❌ Не пиши «pls upvote» нигде — это badge of shame в любом сообществе.
