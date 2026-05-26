# Lessio — Production Launch Checklist

Контрольный список перед публичным анонсом в Telegram-канал / соцсети.
Что закрыто в коде ✅ и что нужно сделать вручную в DNS / у провайдеров ⚠️.

## ✅ Готово в коде

- [x] **Rate limit на `/lessio/auth/login` и `/lessio/auth/register`**
      (10 login-попыток / 5 регистраций в минуту с IP, см. `app/auth/rate_limit.py`)
- [x] **Custom 404 page** для `/lessio/*` и `/u/*` с поиском по блогу
- [x] **CSRF middleware** на все mutation-методы (same-origin check)
- [x] **Security headers**: HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy
- [x] **Sentry** integrated (logs errors в проде если `SENTRY_DSN` задан)
- [x] **Unpaid bookings audit** в cron (`audit_unpaid_bookings`) + UI badge на «Сегодня»
- [x] **JSON-LD** на всех публичных страницах (Service / Article / FAQPage / BlogPosting / BreadcrumbList / Organization / SoftwareApplication)
- [x] **Sitemap.xml** с 54+ Lessio-URL, обновляется автоматом при добавлении tutor'ов
- [x] **robots.txt** правильный — публичное Allow, cabinet/auth Disallow
- [x] **IndexNow** ping Yandex/Bing при создании tutor-профиля
- [x] **226/226 lessio-тестов** зелёные

## ⚠️ Требует ручных действий в проде

### 1. SPF / DKIM / DMARC для домена `getdoday.ru`

Без этих DNS-записей письма Lessio попадают в спам (особенно на mail.ru / yandex.ru).

**Что сейчас:** письма шлются через SMTP-сервер из `SMTP_HOST=...` (.env на проде).
Если это Gmail или ваш собственный — нужны записи ниже.

**SPF** — TXT-запись на корневой домен. Разрешает указанным серверам отправлять
от вашего домена.

```
Имя:       @  (или getdoday.ru)
Тип:       TXT
Значение:  v=spf1 include:_spf.google.com ~all
```

Если SMTP не Gmail — замените `include:_spf.google.com` на ваш `include:smtp.provider.com`.

**DKIM** — добавляет подпись к письмам, доказывает что письмо реально от вас.

В Google Workspace: Admin Console → Apps → Gmail → Authenticate email → Generate DKIM key.
Получите запись типа:

```
Имя:       google._domainkey.getdoday.ru
Тип:       TXT
Значение:  v=DKIM1; k=rsa; p=MIGfMA0...  (длинная строка)
```

**DMARC** — политика что делать с письмами не прошедшими SPF/DKIM.

```
Имя:       _dmarc.getdoday.ru
Тип:       TXT
Значение:  v=DMARC1; p=none; rua=mailto:doday.support@gmail.com
```

`p=none` на старте (только мониторинг). Через 2 недели после первого пакета писем —
поменять на `p=quarantine`, ещё через месяц — `p=reject`.

**Проверить настройку:** [mxtoolbox.com/spf.aspx](https://mxtoolbox.com/spf.aspx) +
[mxtoolbox.com/dkim.aspx](https://mxtoolbox.com/dkim.aspx).

**Альтернатива (быстрее):** перейти на транзакционного провайдера:
- **Resend** (modernest, $20/мес за 50k писем, SPF/DKIM auto)
- **Brevo / Sendinblue** (free до 300 писем/день)
- **Mailgun** (3-5k писем/мес free first 3 months)

Для перехода — поменять `SMTP_HOST=smtp.resend.com`, добавить TXT-записи которые
они выдадут.

### 2. Реальный тест Stars-платежа

`@LessioBot` имеет `PreCheckoutQueryHandler` + `MessageHandler(SUCCESSFUL_PAYMENT)`,
но они проверялись только моками. Перед публичным запуском:

1. Откройте `@LessioBot` в Telegram с тестового аккаунта.
2. `/start` → откройте Lessio Mini App.
3. Создайте профиль с одной услугой за 100 ₽ (min Stars ~83).
4. Со второго аккаунта зайдите на `/u/<ваш-slug>` (через бот-deeplink).
5. Забронируйте слот, оплатите Stars.
6. Проверьте в Lessio-кабинете:
   - `Today`-карточка появилась
   - `payment_status=paid` (флажок «✓ Оплачено» зелёный)
   - `paid_at` timestamp заполнен
7. Stars пришли на бот-баланс (`@BotFather → /mybots → стат → Stars`).

Если что-то не сработало — смотреть Sentry + logs `lessio_stars_*`.

### 3. DB бэкапы

Managed PostgreSQL обычно делает auto-backup. Проверить у провайдера:
- Retention 7-30 дней.
- Можно ли восстановить на конкретный timestamp (PITR).
- Записать в README команду для восстановления.

Если backup нет — настроить через `pg_dump` cron на отдельный bucket.

### 4. Мониторинг

- **Sentry** — проверить что `SENTRY_DSN` задан в `.env` на проде, в Dashboard'е
  Sentry видны логи + ошибки.
- **Uptime monitor** (Better Stack / UptimeRobot бесплатно): пинговать
  `https://getdoday.ru/health` каждую минуту, алёрт в Telegram-канал при `down`.
- **Sentry-alert на spike `lessio_unpaid_spike`** — если >50 unpaid bookings за
  сутки, прислать на email/Telegram (через Sentry alert rules).

### 5. Telegram bot `/setdescription`

В `@BotFather` для `@LessioBot`:
- `/setdescription` — короткое описание для профиля бота.
- `/setabouttext` — что показывается до `/start`.
- `/setuserpic` — аватарка-логотип (есть в `app/static/lessio/logo.svg`,
  отрисуйте 512×512 PNG из неё).

Эти данные не managed через API, только @BotFather'ом руками.

### 6. Аудит rate-limit правил

Сейчас:
- `/lessio/auth/register` — **5 в минуту с IP** (anti-spam-bot, можно строже для prod)
- `/lessio/auth/login` — **10 в минуту с пары (IP, email)** (anti-brute-force)
- `/lessio/app/*` (cabinet) — без rate-limit (юзер уже аутентифицирован)
- `/u/<slug>` (публичная) — без rate-limit (cache внутри 5 мин на slots)
- `/u/<slug>/book` (booking) — без rate-limit (защита через CSRF + slot-conflict)

На больших объёмах добавить nginx-level rate-limit для anonymous endpoints
(`/u/`, `/lessio/blog`, `/lessio/help` — по 60-100 req/s с IP).

## Команды для smoke-теста после деплоя

```bash
# Health + основные публичные routes
for p in / /lessio /lessio/blog /lessio/help /u/demo /sitemap.xml /robots.txt; do
  printf "%-25s " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "https://getdoday.ru$p"
done

# Atom feed
curl -s -o /dev/null -w "feed: %{http_code} (%{content_type})\n" \
  "https://getdoday.ru/lessio/blog/feed.xml"

# Custom 404 — должен быть HTML, не JSON
curl -s -H "Accept: text/html" "https://getdoday.ru/lessio/nosuch" | grep -c "Не нашли"

# Rate limit — 6 регистраций подряд (последняя должна вернуть 429)
for i in {1..6}; do
  printf "attempt %d: " "$i"
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST "https://getdoday.ru/lessio/auth/register" \
    -d "email=spam$i@test.test&password=fakepass123"
done
```

## Definition of «ready for public launch»

Готово к **анонсу на 100-500 человек** (Telegram-канал автора):
✅ Всё что в разделе «Готово в коде»

Готово к **полноценному маркетингу** (Профи.ру биржа, контекстная реклама):
✅ Плюс P3.1 (SPF/DKIM) и P3.2 (Stars-test) и P3.4 (uptime alerts).

Сейчас Lessio находится между этими двумя состояниями. Для приватного
запуска **готово полностью**.
