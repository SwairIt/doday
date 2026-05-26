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

### 1. SPF / DKIM для домена `getdoday.ru` (через Resend)

**Текущее состояние** (проверено `dig` 2026-05-26):
- ✅ SMTP уже на `smtp.resend.com:587` (отлично!)
- ✅ `_dmarc.getdoday.ru` — есть базовый `v=DMARC1; p=none;`
- ❌ SPF (TXT на корневой) — **отсутствует**
- ❌ DKIM (Resend keys) — **отсутствуют**

Без SPF/DKIM письма Lessio будут падать в спам на mail.ru / yandex.ru.

**Что делать (5-10 минут):**

1. Зайти в [resend.com/domains](https://resend.com/domains) → ваш домен `getdoday.ru` → Verify.

2. Resend покажет точные DNS-записи для вашего аккаунта — обычно 3-4 штуки:
   - **MX**: `send.getdoday.ru` → `feedback-smtp.eu-west-1.amazonses.com` (или ваш регион)
     Priority: 10
   - **TXT SPF на `send.getdoday.ru`**: `v=spf1 include:amazonses.com ~all`
   - **TXT DKIM на `resend._domainkey.getdoday.ru`**:
     длинный `v=DKIM1; k=rsa; p=MIGfMA0...`

3. Параллельно обновить корневой `_dmarc`:
   ```
   Имя:       _dmarc.getdoday.ru
   Тип:       TXT
   Значение:  v=DMARC1; p=none; rua=mailto:doday.support@gmail.com; aspf=r; adkim=r
   ```
   На 2 недели `p=none` (мониторинг), потом `p=quarantine`, ещё через месяц `p=reject`.

4. Добавить эти записи через DNS-провайдера домена `getdoday.ru` (Reg.ru / Cloudflare / etc).

5. В Resend Dashboard нажать **Verify** — обычно валидируется за 5-15 минут.

6. После verification — отправить тестовый email через Lessio booking, проверить
   что письмо приходит **без** «via amazonses.com» в From и не в Спам:
   ```bash
   # Тест: отправить test booking на свой реальный email через demo-tutor
   curl https://getdoday.ru/u/demo
   # → выбрать слот, ввести свой email, проверить inbox
   ```

**Проверить SPF/DKIM после настройки:**
- [mxtoolbox.com/SuperTool.aspx?run=spf:getdoday.ru](https://mxtoolbox.com/SuperTool.aspx?run=spf:getdoday.ru)
- [mxtoolbox.com/SuperTool.aspx?run=dkim:resend._domainkey.getdoday.ru](https://mxtoolbox.com/SuperTool.aspx?run=dkim:resend._domainkey.getdoday.ru)
- [mail-tester.com](https://www.mail-tester.com) — отправить туда test email из Lessio
  и получить score (должно быть 9-10/10).

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

### 3. DB бэкапы ✅ Настроено

**Cron уже работает** (добавлено 2026-05-26):
- Скрипт: `/var/www/getdoday/data/pg_backup.sh`
- Crontab: `30 4 * * *` (ежедневно в 04:30 МСК)
- Retention: **7 daily backups** автоматически
- Storage: `/var/www/getdoday/data/backups/doday-YYYY-MM-DD_HHMM.sql.gz`
- Лог: `/tmp/pg-backup.log`

**Восстановление из бэкапа:**
```bash
ssh getdoday@getdoday.ru
# Найти нужный backup
ls -la /var/www/getdoday/data/backups/
# Распаковать и применить
gunzip -c /var/www/getdoday/data/backups/doday-YYYY-MM-DD_HHMM.sql.gz | \
  psql "$(grep '^DATABASE_URL=' /var/www/getdoday/data/www/getdoday.ru/app/.env | \
         cut -d= -f2- | sed 's|postgresql+asyncpg|postgresql|')"
```

**Дополнительно** — раз в месяц копировать самый свежий backup на внешний storage
(Yandex Object Storage / Selectel S3) на случай если пропадёт весь VPS.

### 4. Мониторинг

**Sentry** ✅ настроен (`SENTRY_DSN` в `.env` на проде задан).
Сейчас ловит:
- Все `logger.exception(...)` через SDK integration
- Stars pre_checkout rejects (как `warning`-сообщения)
- Stars apply_successful_payment fails (как `error` с full stacktrace + breadcrumbs)
- Любые HTTP 500 через FastAPI integration

**Uptime monitor — рекомендация:**

Зарегистрироваться в [Better Stack](https://betterstack.com) (free 10 monitors) и
добавить **два** монитора:

1. **`https://getdoday.ru/health`** — liveness, 1 раз/мин. Алёрт если 3 fail подряд.
2. **`https://getdoday.ru/health/deep`** — DB+seeds check, 1 раз/5 мин.
   Алёрт если 2 fail подряд. Этот вернёт 503 если БД упала или demo-tutor пропал.

Better Stack может слать алёрты в Telegram-канал или на phone.

**Sentry alert rules** — настроить в Dashboard:
- `lessio_unpaid_spike` warning logs → email/Telegram (spam-bot detection)
- любой `apply_successful_payment failed` → немедленно email (потерянный платёж)
- > 5 errors за 5 минут → escalate

### 5. Telegram bot `/setdescription`

В `@BotFather` для `@LessioBot`:
- `/setdescription` — короткое описание для профиля бота.
- `/setabouttext` — что показывается до `/start`.
- `/setuserpic` — аватарка-логотип (есть в `app/static/lessio/logo.svg`,
  отрисуйте 512×512 PNG из неё).

Эти данные не managed через API, только @BotFather'ом руками.

### 6. Аудит rate-limit правил ✅ Все слои закрыты

Сейчас (3 слоя):
- **`/lessio/auth/register`** — 5 req/min с IP → 429
- **`/lessio/auth/login`** — 10 req/min с (IP, email) → 429 + reset на успех
- **`/lessio/help/*`, `/lessio/blog/*`, `/lessio/dlya-*`, `/u/*`** —
  **120 req/min с IP** через app-middleware (anti-DDoS на статический render)
- **`/lessio/app/*`** (cabinet) — без rate-limit (аутентифицированный юзер)
- **`/u/<slug>/book`** (booking POST) — без rate-limit, защита через CSRF + slot-conflict

**На больших объёмах** (1000+ DAU) — добавить nginx-level rate-limit zone:
```nginx
# В /etc/nginx/conf.d/getdoday.ru.conf или fastpanel конфиге:
limit_req_zone $binary_remote_addr zone=lessio_anon:10m rate=60r/m;

location ~ ^/(lessio/(help|blog|dlya-|alternativa-|oplata-)|u/) {
    limit_req zone=lessio_anon burst=20 nodelay;
    proxy_pass http://127.0.0.1:8011;
    # ... стандартные proxy headers
}
```

Требует sudo (или FastPanel UI для редактирования). На текущих объёмах app-middleware
достаточно.

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
