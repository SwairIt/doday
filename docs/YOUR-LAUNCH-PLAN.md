# План запуска Lessio — что тебе делать руками

> Всё что мог из кода/SSH — сделал. Здесь то, что требует **твоих рук**: DNS-провайдер,
> Telegram-клиент, Better Stack аккаунт. Шаги по приоритету.

---

## 🟢 Готово к запуску прямо сейчас

Можно открывать `/lessio` для тестовой аудитории (10-50 знакомых):

- ✅ Сайт работает: 93/93 sitemap-URL отдают 200
- ✅ 28 help-статей + 18 blog-статей + 5 SEO landings — все рендерятся
- ✅ Custom 404 для Lessio (брендированная страница с поиском)
- ✅ Onboarding-чеклист в кабинете для новых tutor'ов
- ✅ Floating help-bubble справа-снизу с live-поиском
- ✅ Reading-progress + share-buttons (Telegram/VK/X/WhatsApp/copy) в блоге
- ✅ Atom feed `/lessio/blog/feed.xml`
- ✅ Rate limit на auth (5 register/min, 10 login/min)
- ✅ App-level rate limit 120 req/min на anon-страницы
- ✅ `/health/deep` отдаёт `{"status":"ok","checks":{"db":"ok","lessio_demo":"ok"...}}`
- ✅ Sentry интегрирован, ловит exceptions автоматически
- ✅ Daily pg_backup в 04:30 (retention 7 дней)
- ✅ 234/234 lessio-тестов зелёные
- ✅ Bot username исправлен в коде (`mylessiobot` вместо `LessioBot`)

---

## 🔴 КРИТИЧЕСКИЙ блокер для Stars-оплаты — bot не работает

### Проблема

`@mylessiobot` (он же Lessio) **не отвечает** с 25 мая. В логах:

```
ERROR doday.telegram: Both bots failed to start — Timed out
```

Что значит: пока bot мертв, оплата через Telegram Stars **не сработает**. Клиент заплатит, но
booking не отметится «оплачено» автоматически (нужно вручную).

### Что я уже пробовал (не помогло)

- Поменял порядок hardcoded-IP в `app/telegram/bot.py` — рабочий `.167.220` первым
- Включил cron-watchdog (был DISABLED)
- Убрал `DISABLE_TELEGRAM_IPV4_PATCH=1` → `=0`
- Очистил `__pycache__`, перезапустил bot

Что подтверждено:
- `socket.getaddrinfo` patched корректно
- `asyncio.open_connection("api.telegram.org", 443)` — работает за 200ms
- `curl --resolve api.telegram.org:443:149.154.167.220 https://api.telegram.org/` — работает за 146ms
- **Но** `httpx.AsyncClient.get("https://api.telegram.org/")` — `ConnectTimeout` через 15с

Это значит `httpx` (через `httpcore` → `anyio`) использует **другой mechanism** для resolve
который игнорирует наш monkey-patch на `socket` и `loop.getaddrinfo`.

### Варианты фикса (по сложности)

#### Вариант A: HTTP-прокси (15 минут, рекомендую)

Купить дешёвый европейский VPS-прокси ($3-5/мес) или использовать
[Tinyproxy](https://tinyproxy.github.io) на отдельной VPS, прописать в `.env`:

```
HTTPS_PROXY=http://user:pass@proxy.your-vps.com:8080
```

`httpx` автоматически использует proxy при наличии env-var. Bot пойдёт к Telegram через прокси
из работающей сети. Без monkey-patch'а.

Готовые сервисы:
- [Webshare.io](https://webshare.io) — 10 free proxies, EU/US
- [Proxyseller.com](https://proxyseller.com) — РФ residential

#### Вариант B: MTProxy

Telegram-специфичный прокси, разработан для обхода блокировок. Можно поднять свой через
@MTProxybot или использовать публичный (нестабильны).

В коде нужно добавить в `Application.builder()`:
```python
.proxy_url("https://your-mtproxy.com:443")
```

#### Вариант C: переместить bot на отдельный VPS вне РФ

EU-VPS ($4-6/мес) с открытым доступом к api.telegram.org. Запустить там только bot worker,
DB connection к managed PG через интернет. Самое надёжное долгосрочное.

#### Вариант D: разобраться почему `httpx` игнорит monkey-patch

Нужно копать `anyio.getaddrinfo` или `anyio._backends._asyncio.connect_tcp`. Если найдёшь —
patch на этом уровне сработает. Часы исследования.

### До тех пор пока bot не починен

Клиенты могут бронировать (web-сайт работает). Но **Stars-оплата не сработает** — нужно либо:
- Отметить оплату вручную (через `Сегодня → клиент → Отметить оплачено`)
- Принимать оплату через СБП / нал

Для тестовой аудитории на 10-50 человек — приемлемо. Для широкого запуска — фикс **обязателен**.

---

## 🟡 Что доделать ДО публичного маркетинга (контекст, биржа)

### 1. SPF / DKIM для домена `getdoday.ru` (10-15 минут)

**Текущее состояние** (проверено `dig` 2026-05-26):
- ✅ SMTP сейчас `smtp.resend.com:587`
- ✅ DMARC partial есть (`v=DMARC1; p=none`)
- ❌ SPF на корневой — отсутствует
- ❌ DKIM для Resend — отсутствует

Без этого письма Lessio попадают в спам на mail.ru / yandex.ru.

**Что делать:**

1. Открой [resend.com/domains](https://resend.com/domains) → твой `getdoday.ru` → жми **Verify**.

2. Resend покажет точные DNS-записи (обычно 3-4):
   - **MX** запись на `send.getdoday.ru` → `feedback-smtp.eu-west-1.amazonses.com` (priority 10)
   - **TXT SPF на `send.getdoday.ru`**: `v=spf1 include:amazonses.com ~all`
   - **TXT DKIM на `resend._domainkey.getdoday.ru`**: длинный `v=DKIM1; k=rsa; p=...`

3. Зайди в DNS-провайдер домена `getdoday.ru` (где регистрировал — Reg.ru / Cloudflare / etc),
   добавь эти 3-4 записи.

4. Обнови корневой DMARC чтобы получать алерты:
   ```
   Имя:     _dmarc.getdoday.ru
   Тип:     TXT
   Значение:  v=DMARC1; p=none; rua=mailto:doday.support@gmail.com; aspf=r; adkim=r
   ```

5. Через 5-15 минут — в Resend Dashboard жми **Verify** ещё раз. Должно стать `Verified`.

6. **Тест:** отправь test-email через свою Lessio-страницу на свой gmail/mail.ru:
   ```bash
   # Открой /u/demo, выбери слот, забронируй на свой email — придёт письмо
   # Если в спам — что-то не так, ещё раз проверь TXT-записи
   ```

7. Финальный тест: отправь test-письмо на [mail-tester.com](https://www.mail-tester.com).
   Скор должен быть **9-10 из 10**.

### 2. Better Stack uptime monitor (5 минут, бесплатно)

1. Регистрация на [betterstack.com](https://betterstack.com) (Free plan = 10 monitors).

2. Добавь 2 монитора:

   **Monitor 1 — Liveness:**
   - URL: `https://getdoday.ru/health`
   - Check every: 1 min
   - Alert after: 3 fail
   - Что проверяет: uvicorn вообще жив

   **Monitor 2 — Deep:**
   - URL: `https://getdoday.ru/health/deep`
   - Check every: 5 min
   - Alert after: 2 fail
   - Expected: HTTP 200 + body содержит `"status":"ok"`
   - Что проверяет: DB живая, demo-tutor существует, env-vars set

3. Подключи Telegram-канал для алёртов (Better Stack → Integrations → Telegram).

### 3. Sentry alert rules (5 минут)

В [sentry.io](https://sentry.io) → твой проект → Alerts → Create Alert:

**Alert 1 — Stars-payment failures:**
- Condition: `event.message contains "apply_successful_payment failed"`
- Action: Email + Telegram
- Severity: P1 (потерянный платёж — критично)

**Alert 2 — Unpaid bookings spike:**
- Condition: `event.message contains "lessio_unpaid_spike"`
- Action: Email
- Severity: P3 (spam-bot detection)

**Alert 3 — Error rate:**
- Condition: >10 errors per 5 minutes
- Action: Email + Telegram
- Severity: P2

### 4. @BotFather — аватарка и описание

В @BotFather:
1. `/mybots` → `@mylessiobot` → **Edit Botpic**
2. Загрузи аватарку (готовая SVG в `app/static/lessio/logo.svg`, нужен PNG 512×512)
3. (Опционально) `/setname` — поменять `Lessio` на красивее
4. `/setabouttext` — что видно ДО `/start` (~120 chars)
5. `/setdescription` — длинное описание (~512 chars)

**Готовые тексты:**
- About: `Lessio — кабинет для онлайн-репетиторов, тренеров, психологов. Запись и оплата от клиентов через Telegram Stars.`
- Description:
```
👋 Lessio — кабинет онлайн-учителя.

📅 Клиент выбирает время на твоей странице getdoday.ru/u/<имя>
💳 Платит Telegram Stars (без эквайринга)
✅ Ты получаешь email с подтверждением + iCal в календарь

Открой меню снизу ↓
```

### 5. Реальный тест Stars-платежа

⚠️ Сначала **почини bot** (см. блокер выше). После того как `@mylessiobot` отвечает на `/start`:

1. Со своего основного Telegram-аккаунта открой [@mylessiobot](https://t.me/mylessiobot)
2. `/start` — должно показаться приветствие + кнопка «Открыть Lessio»
3. Открой Lessio через эту кнопку — попадёшь в кабинет (если профиль настроен)
4. Создай тестовую услугу за 100 ₽ (минимальные Stars ~83)
5. Со **второго** аккаунта (или с мобильного, разлогинься из основного) открой
   `https://getdoday.ru/u/<твой-slug>`
6. Забронируй слот → введи email → получи кнопку «Оплатить Stars»
7. Нажми, оплати 83 ⭐
8. **Проверь в кабинете:**
   - `/lessio/app/today` — должна быть карточка с зелёным «✓ Оплачено»
   - В Sentry должен быть breadcrumb-trail `stars.successful_payment`
9. Если что-то пошло не так — посмотри Sentry и `/tmp/uvicorn.log`

---

## 🟢 Команды smoke-теста (запустить когда что-то изменишь)

```bash
# Все основные routes
for p in / /lessio /lessio/help /lessio/blog /lessio/blog/feed.xml \
         /lessio/dlya-repetitorov /u/demo /sitemap.xml /robots.txt /health /health/deep; do
  printf "%-35s " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "https://getdoday.ru$p"
done

# Custom 404 (должен быть HTML, не JSON)
curl -s -H "Accept: text/html" "https://getdoday.ru/lessio/nosuch" | grep -c "Не нашли страницу"

# Rate limit (6-я попытка → 429)
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w "$i: %{http_code}\n" \
    -X POST "https://getdoday.ru/lessio/auth/register" \
    -d "email=ratelimit_test_$i@example.test&password=test123"
done

# Backup статус
plink -batch -ssh -hostkey "SHA256:NwU1dGS29JAjs2K5LfEtu3DLFgg04yo7ZEA4iOGkM6E" \
      -pw "$SSH_PASS" getdoday@getdoday.ru \
      "ls -la /var/www/getdoday/data/backups/ | tail -5"

# Bot health
curl -s "https://api.telegram.org/bot$LESSIO_BOT_TOKEN/getMe" | python -m json.tool

# Bot commands (должно быть 6 — start/menu/help/about/privacy/feedback)
curl -s "https://api.telegram.org/bot$LESSIO_BOT_TOKEN/getMyCommands?language_code=ru" | \
  python -m json.tool
```

---

## 📊 Definition of done

| Сценарий | Готово? |
|---|---|
| Приватный анонс (10-50 знакомых, бесплатные занятия) | ✅ **готово** |
| Тестовая аудитория Telegram-канала (100-300 чел) | ⚠️ **только после фикса bot** для оплаты |
| Маркетинг через биржу / контекст | ⚠️ **bot fix + SPF/DKIM + Better Stack** |
| Stars-оплата работает end-to-end | ❌ **блокер: bot down** |

---

## Если что-то сломается ночью

1. **Сайт лёг** — Better Stack пришлёт алерт. SSH на сервер:
   ```bash
   plink -batch -ssh -hostkey "..." -pw "$SSH_PASS" getdoday@getdoday.ru \
     "for pid in \$(lsof -ti:8011); do kill -9 \$pid; done; \
      python3 /var/www/getdoday/data/start_uvicorn.py"
   ```

2. **DB пропала** — восстановление из бэкапа:
   ```bash
   ssh getdoday@getdoday.ru
   ls -la /var/www/getdoday/data/backups/  # найди свежий
   gunzip -c /var/www/getdoday/data/backups/doday-YYYY-MM-DD.sql.gz | \
     psql "$(grep '^DATABASE_URL=' /var/www/getdoday/data/www/getdoday.ru/app/.env | \
            cut -d= -f2- | sed 's|postgresql+asyncpg|postgresql|')"
   ```

3. **Поток спам-bookings** — Sentry alert на `lessio_unpaid_spike`. В кабинете на «Сегодня»
   видны все unpaid bookings. Cancel вручную через клик по записи.

4. **Bot опять упал** — `/var/www/getdoday/data/logs/bot.log` покажет почему.
   Watchdog включён, поднимает каждую минуту.

---

## 💌 Чтобы спросить меня в следующей сессии

Просто скажи «продолжи launch» — я возьму этот файл, посмотрю что ты сделал и что осталось.

Удачи 🚀
