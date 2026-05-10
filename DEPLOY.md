# Deploying Doday to a VPS

Two flavours below: **Docker** (recommended, one command) or **bare metal** (uvicorn + systemd + host Postgres). Pick one. Both expect Ubuntu 22.04+ with sudo.

> Replace `doday.ru` everywhere with your real domain.

---

## A. Pre-deploy — DNS

Before you SSH anywhere, point the domain at the VPS:

1. Registrar panel → DNS zone for `doday.ru`
2. Add `A` record: `@` → `<VPS_IP>` (TTL 600)
3. Add `A` record: `www` → `<VPS_IP>` (TTL 600)
4. Wait until `nslookup doday.ru` returns the VPS IP (5-30 min)

You can deploy without DNS, but Let's Encrypt won't issue a cert until DNS is live.

---

## B. Docker route (recommended)

### B1. First-time VPS setup

```bash
ssh root@<VPS_IP>

# Create non-root user (skip if you already have one)
adduser doday && usermod -aG sudo doday
su - doday

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker doday
exit  # re-ssh so the docker group takes effect
ssh doday@<VPS_IP>

# Install nginx + certbot for TLS
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### B2. Get the code + config

```bash
sudo mkdir -p /opt/doday && sudo chown doday:doday /opt/doday
cd /opt/doday
git clone https://github.com/SwairIt/SchoolProject.git .

cp .env.example .env
nano .env
```

Fill these in `.env`:

```
APP_ENV=prod
APP_SECRET_KEY=<paste output of: python3 -c "import secrets; print(secrets.token_urlsafe(48))">
APP_BASE_URL=https://doday.ru

POSTGRES_USER=doday
POSTGRES_PASSWORD=<long-random-password>
POSTGRES_DB=doday
DATABASE_URL=postgresql+asyncpg://doday:<same-password>@db:5432/doday

# Gmail app password (https://myaccount.google.com/apppasswords) or Resend/Brevo
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=<16-char-app-password-no-spaces>
SMTP_FROM=noreply@doday.ru
SMTP_START_TLS=true

UVICORN_WORKERS=2
```

Lock it down: `chmod 600 .env`.

### B3. Boot the stack

```bash
docker compose up -d --build
docker compose logs -f web   # confirm "Starting uvicorn on 0.0.0.0:9100"
```

App is now serving on `127.0.0.1:9100` inside the VPS — not reachable from the internet yet.

### B4. Wire nginx + HTTPS

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/doday
# Edit any "doday.ru" mentions in that file to your domain
sudo ln -sf /etc/nginx/sites-available/doday /etc/nginx/sites-enabled/doday
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

sudo mkdir -p /var/www/letsencrypt

sudo certbot --nginx -d doday.ru -d www.doday.ru --redirect --agree-tos -m you@your-email.tld
```

certbot edits the nginx config in place to add SSL + auto-renewal. Confirm:

```bash
curl -I https://doday.ru/health   # expect 200, HSTS header present
```

### B5. Operational basics

| Task | Command |
|---|---|
| Tail logs | `docker compose logs -f web` |
| Restart app | `docker compose restart web` |
| Pull update | `git pull && docker compose up -d --build` |
| DB backup | `docker compose exec db pg_dump -U doday doday \| gzip > /opt/doday/backup-$(date +%F).sql.gz` |
| DB restore | `gunzip -c backup.sql.gz \| docker compose exec -T db psql -U doday doday` |
| Open prod psql | `docker compose exec db psql -U doday doday` |

### B6. Auto-deploy on push (optional)

On the VPS:

```bash
crontab -e
# Add: */5 * * * * cd /opt/doday && git pull --quiet && docker compose up -d --build > /dev/null 2>&1
```

Or set up a webhook with GitHub Actions later.

---

## C. Bare-metal route (no Docker)

Use this if you'd rather run uvicorn under systemd with a host-installed Postgres.

### C1. System packages

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql nginx git certbot python3-certbot-nginx
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo cp ~/.local/bin/uv /usr/local/bin/uv
```

### C2. Postgres + DB

```bash
sudo -u postgres psql <<SQL
CREATE DATABASE doday;
CREATE USER doday WITH PASSWORD '<long-random-password>';
GRANT ALL ON DATABASE doday TO doday;
ALTER DATABASE doday OWNER TO doday;
SQL
```

### C3. App user + checkout

```bash
sudo useradd -r -m -d /opt/doday -s /bin/bash doday
sudo -u doday git clone https://github.com/SwairIt/SchoolProject.git /opt/doday
cd /opt/doday
sudo -u doday cp .env.example .env
sudo nano .env   # same prod values as B2 above; DATABASE_URL host = localhost
sudo chmod 600 .env && sudo chown doday:doday .env

sudo -u doday uv sync --no-dev
```

### C4. systemd

```bash
sudo cp deploy/doday.service /etc/systemd/system/doday.service
sudo systemctl daemon-reload
sudo systemctl enable --now doday
sudo journalctl -u doday -f   # check startup log + migrations
```

### C5. nginx + HTTPS — same as B4 above.

---

## D. Sanity checklist

- [ ] `curl -I https://doday.ru/health` returns `200` with `Strict-Transport-Security` header
- [ ] `https://doday.ru/app/today` redirects to `/auth/login` (i.e. unauth users hit the login page, not 404)
- [ ] Registration sends a verification email and the link works
- [ ] Login sets a `Set-Cookie: session=...; Secure; HttpOnly; SameSite=Lax` (open DevTools)
- [ ] `https://doday.ru/robots.txt` disallows `/app/`, `/api/`, `/htmx/`, `/auth/`
- [ ] `/api/links/graph` requires auth (returns 401 anonymously, not 404)
- [ ] Postgres port 5432 is **not** open externally — `nmap -p 5432 doday.ru` from your laptop should say closed/filtered
- [ ] Old uvicorn isn't lingering on the host — `ss -ltnp | grep 9100` shows exactly one process

---

## E. Cron jobs

Doday полагается на системный cron для одной задачи: утренний email-дайджест.

### E0. Auto-deploy via cron-poll (push в master → ~60 сек до прода)

Прод-cron каждую минуту сравнивает `origin/master` с локальным HEAD.
Если разные — pull → alembic upgrade → restart uvicorn → log в
`/var/www/getdoday/data/logs/deploy-poll.log`. Это обходит SSH-фаервол
который не пускает GitHub Actions runner'ы из вне РФ.

**Setup** (одноразовый):

```bash
uv run python .tmp_ssh_setup_deploy_poll.py
```

Скрипт устанавливает `/var/www/getdoday/data/deploy-poll.sh` + crontab
line `* * * * * .../deploy-poll.sh`. Idempotent — re-runs обновляют
скрипт по marker'у в crontab.

**Disable:** убрать crontab-line:
```bash
ssh getdoday@getdoday.ru
crontab -e  # удалить строку с маркером # doday-deploy-poll
```

**Verify:**
- `tail -f /var/www/getdoday/data/logs/deploy-poll.log` — видно каждый
  pull (или silence если разве push'ей не было)
- `git log -1 --oneline` на проде должен совпадать с `origin/master`
  максимум через 60 секунд после push

### E1. Утренний дайджест (`/api/digest/cron-trigger`)

Раз в день нужно дёрнуть endpoint, который собирает и шлёт письма всем
opt-in юзерам. Endpoint защищён секретом — `X-Cron-Token` header сверяется
с `CRON_TOKEN` из `.env`.

**Как настроить:**

1. Сгенерировать секрет (32 байта URL-safe):
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Положить в прод-`.env`:
   ```
   CRON_TOKEN=<секрет>
   ```
3. Перезапустить uvicorn — endpoint начинает принимать с этим токеном.
4. Добавить системный cron:
   ```bash
   crontab -e
   # 04:00 UTC = 07:00 МСК
   0 4 * * * curl -sS -m 60 -X POST -H "X-Cron-Token: <секрет>" \
       http://127.0.0.1:8011/api/digest/cron-trigger \
       >> /tmp/digest-cron.log 2>&1 # doday-morning-digest
   ```
   Маркер-комментарий `# doday-morning-digest` помогает идемпотентно
   обновлять запись (re-run script-а его удаляет и вставляет заново).

**Проверка:**
- `crontab -l | grep doday` — видит свою строку
- `curl -sS -X POST -H "X-Cron-Token: $CRON_TOKEN" http://127.0.0.1:8011/api/digest/cron-trigger`
  должен вернуть JSON `{sent, skipped_already, skipped_empty, errored}`
- На следующее утро (07:00 МСК) `tail /tmp/digest-cron.log` покажет результат
- В кабинете SMTP-провайдера видно отправленные письма

**Идемпотентность:** endpoint дедуп'ит по `users.morning_digest_last_sent_at >=
сегодня 00:00 UTC` — повторный вызов в тот же день не отправляет повторно.

**Disable:** убрать `CRON_TOKEN=` из `.env` (endpoint начнёт возвращать 503),
ИЛИ удалить crontab-строку (`crontab -e` → удалить → сохранить).

---

## F. If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `502 Bad Gateway` | uvicorn not running | `docker compose logs web` or `journalctl -u doday -f` |
| `{"detail":"Not Found"}` on a new route | stale uvicorn from before last deploy | `docker compose up -d --build` (Docker), or `sudo systemctl restart doday` (bare metal) |
| Login form posts but cookie isn't set | `APP_ENV` ≠ `prod` so cookie is not `Secure`, browser drops it on HTTPS | edit `.env`, set `APP_ENV=prod`, restart |
| `relation "..." does not exist` | migrations didn't run | `docker compose exec web alembic upgrade head` (or systemd: `cd /opt/doday && sudo -u doday .venv/bin/alembic upgrade head`) |
| Verification emails never arrive | wrong SMTP credentials or Gmail rejecting | check `journalctl -u doday \| grep verification_email` — if `verification_email_send_failed`, fix `.env` SMTP creds |
| certbot failure: `connection refused` | DNS not propagated yet, or port 80 closed | `dig +short doday.ru` should match VPS IP; `sudo ufw allow 80/tcp` |
