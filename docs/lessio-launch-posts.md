# Lessio launch — posts + decision rule

Live as of **2026-05-25**, decision day **2026-06-01**. The point of this week
is to find out whether independent tutors will sign up for a TG-native
booking-and-payments service before committing 4 weeks to MVP.

## Decision rule (locked)

| Waitlist count on 2026-06-01 | Decision |
|---|---|
| **≥ 100** unique tutors | ✅ Start MVP (4-week sprint per `app/lessio/` scaffold) |
| 30 – 99 | ⚠️ Pivot — interview 10 of them, find what's missing, re-validate |
| < 30 | ❌ Drop, try next idea (WB price-monitoring, TG storefront) |

Do not move the goalposts mid-week. A no at day 7 saves 80 hours on a product nobody wants.

## Reading waitlist data

`/api/admin/lessio/waitlist/stats.json` (X-Admin-Token-secured) returns:

```json
{
  "total": 47,
  "by_niche": {"english": 18, "ielts": 12, "math": 8, "psychology": 5, "fitness": 4},
  "with_pain_point": 31,
  "decision_threshold": 100,
  "threshold_met": false
}
```

`/api/admin/lessio/waitlist.json` returns the full list newest-first — read every `pain_point` row, it's the most valuable signal for MVP prioritisation.

CLI from local machine:

```bash
TOKEN=$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)
curl -s -H "X-Admin-Token: $TOKEN" https://getdoday.ru/api/admin/lessio/waitlist/stats.json | python -m json.tool
curl -s -H "X-Admin-Token: $TOKEN" https://getdoday.ru/api/admin/lessio/waitlist.json | python -m json.tool | head -80
```

To delete a test/spam entry:

```bash
curl -X DELETE -H "X-Admin-Token: $TOKEN" \
  "https://getdoday.ru/api/admin/lessio/waitlist/by-email?email=spam@example.com"
```

## Day-by-day plan

### Day 0 (today)
- [x] Lessio mounted at `getdoday.ru/lessio` — landing live, waitlist accepting POSTs
- [x] Admin endpoints for monitoring
- [ ] First post in two channels (Day 1 below)

### Day 1 — soft launch in two niche channels
- VK group «Я репетитор» (~180K) — see post template below
- Telegram «Репетиторы России» (~90K) — same copy adapted

**Target end of day 1:** 20 signups. If <5, the hook line doesn't work — rewrite the headline and re-post tomorrow.

### Day 2 — niche channels
- «Тренер-самозанятый» (45K)
- «Психологи частной практики» (60K)
- VK «Подготовка к ЕГЭ» (40K)
- TG «Самозанятые России» (220K)

**Target cumulative:** 50.

### Day 3 — Reddit r/Russian (for tutors of Russian as foreign language)

### Day 4-5 — personal outreach
DM the top-10 waitlist entries (best pain_point answers). Interview-5-questions:
1. What do you do today for scheduling? (Google Calendar / Notion / nothing?)
2. How do clients pay you today? (Сбер / cash / CRM?)
3. What's the single biggest weekly time-sink?
4. Would you pay 750₽/mo for the features described?
5. **Would you pre-pay 37 500₽ now for Founder lifetime access?**

Q5 is the truth detector. People who say yes-yes-no-no-yes-but-not-now were lying. Only count Q5-yes as real intent.

**Target cumulative:** 90 signups + at least 5 founder pre-pays.

### Day 6 — momentum email
Email everyone on the waitlist: "Day 6 — N of you signed up, X pre-paid Founder, here's what's next". Signals momentum, surfaces FOMO.

### Day 7 (2026-06-01) — make the call
Read the rule above. Make the decision. Tell the waitlist either way.

---

## Ready-to-paste posts

### VK group «Я репетитор» (~180K)

> **Заголовок:** Делаю кабинет репетитора в Telegram. Нужен ли он?
>
> Привет. Меня Ярослав, мне 15, год назад собрал бесплатный туду-лист
> [Doday.ru](https://getdoday.ru) — там сейчас около 400 пользователей.
>
> Сейчас собираюсь сделать следующий проект — **Lessio**. Это **Telegram-кабинет
> для репетиторов**: клиент тапает в боте → видит твои свободные слоты →
> платит через Telegram Stars → запись в твой календарь, тебе деньги. Без
> сайта, без переводов на сбер, без Excel-расписания.
>
> Прежде чем 4 недели писать код, я хочу проверить — нужен ли он кому-то.
> Если за неделю наберётся 100 репетиторов в waitlist, делаю MVP. Если нет —
> переключаюсь на другую идею.
>
> Если интересно — оставь email на сайте: https://getdoday.ru/lessio
>
> Особенно полезно, если в форме напишешь, что сейчас больше всего бесит в
> работе (запись клиентов? оплата? напоминания? самозанятый-налог? что-то ещё).
> Это поможет мне понять, что строить в первую очередь.
>
> Спасибо!

### Telegram «Репетиторы России» / «Самозанятые России»

> Привет. Делаю **Telegram-кабинет для репетиторов** — Lessio:
>
> • клиент записывается и платит в боте (не надо «переведи на сбер»)
> • бот сам напомнит за 24 ч и за 1 ч (no-show падает)
> • CSV-выгрузка доходов для «Моего налога»
> • расписание + история клиентов
> • Pro 750₽/мес, Founder-тариф навсегда 37 500₽ (первым 200)
>
> До того как сяду писать, проверяю спрос. Если за неделю наберётся 100 репетиторов в листе ожидания — делаю.
>
> Подписывайся: https://getdoday.ru/lessio
>
> Самое полезное для меня — если в форме напишешь, что больше всего бесит сейчас. Это поможет приоритизировать функции.

### Reddit r/Russian (for tutors of Russian as foreign language)

> **Title:** I'm building a Telegram-native booking + payments system for tutors. Looking for feedback before I commit 4 weeks.
>
> Hi r/Russian. If you tutor Russian online (or know people who do?) — read on, this might be useful.
>
> I'm Yaroslav, 15, I made [Doday.ru](https://getdoday.ru) (Russian todo app, ~400 users). My next project is **Lessio**: lets a tutor (Russian-as-foreign-language, math, fitness, anything) collect bookings + payments via Telegram. Client opens the bot → picks a slot → pays in Telegram Stars → both calendars update. No website, no SBP transfers, no Excel.
>
> Why for Russian-as-foreign-language tutors specifically: international students don't have RU bank cards, but they DO have Telegram and can pay in Stars from any country. That's a real distribution-and-payments advantage over Skyeng-style platforms that force you onto their card-rails.
>
> Before I spend a month coding, I want to validate. If 100 tutors join the waitlist in 7 days, I'll build. If not, I drop it.
>
> Waitlist: https://getdoday.ru/lessio
>
> Most useful for me: in the form, describe the worst part of your current tutoring workflow. That's the feature I'll start with.
>
> Thanks!

### Habr (only after ~50 organic signups, day 4-5)

> **Title:** Хочу сделать «Тильду для репетиторов» в Telegram. Прежде чем писать код — спрашиваю Хабр.
>
> Меня Ярослав, 15 лет, около года назад сделал [Doday](https://getdoday.ru). Сейчас задумал Lessio — Telegram-кабинет для репетиторов: расписание + оплата через Stars + напоминания + самозанятый-учёт.
>
> [3-5 параграфов описания продукта]
>
> Прежде чем 4 недели писать код, хочу провалидировать. Подписался на waitlist X репетиторов за Y дней. Из них Z пре-заплатили 37 500₽ за founder-тариф.
>
> **Что я хочу от Хабра:**
> 1. Если ты репетитор / тренер — оставь email и расскажи, что бесит
> 2. Если ты технарь — посмотри [архитектуру](https://github.com/SwairIt/doday/tree/master/app/lessio) и скажи где утечка
> 3. Если делал похожее — расскажи где грабли
>
> Лучше час на чтение комментариев Хабра, чем неделя на переделку архитектуры.
