#!/usr/bin/env bash
# Деплой Doday на прод. Запускать НА СЕРВЕРЕ под пользователем getdoday —
# из планировщика FastPanel (cron) или из SSH-сессии.
#
#   bash /var/www/getdoday/data/www/getdoday.ru/app/scripts/deploy.sh
#
# Механизм взят из рабочего деплой-скрипта проекта: сервис поднимается не
# через systemd, а скриптом start_uvicorn.py на порту 8011 под этим же
# пользователем — root и sudo не нужны.
set -uo pipefail

APP_DIR="/var/www/getdoday/data/www/getdoday.ru/app"

# Из планировщика PATH урезан до /usr/bin:/bin, поэтому `command -v uv` не находит
# uv, установленный в ~/.local/bin. Ищем явно; если не нашли — работаем python3.
UV=""
for candidate in "$HOME/.local/bin/uv" "/usr/local/bin/uv" "$(command -v uv 2>/dev/null)"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then UV="$candidate"; break; fi
done
START="/var/www/getdoday/data/start_uvicorn.py"
PORT=8011

log() { printf '\n== %s\n' "$1"; }

cd "$APP_DIR" || { echo "нет каталога $APP_DIR"; exit 1; }

log "Было"
git log -1 --oneline

log "Забираю код"
git fetch origin --quiet
git reset --hard origin/master
git log -1 --oneline

log "Чищу .pyc"
find "$APP_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

log "Миграции базы"
if [ -n "$UV" ]; then
  "$UV" run python -m alembic upgrade head || python3 -m alembic upgrade head
else
  python3 -m alembic upgrade head
fi

log "Перезапуск uvicorn на :$PORT"
for pid in $(lsof -ti:$PORT 2>/dev/null); do kill -9 "$pid"; done
sleep 1
python3 "$START"
sleep 4

log "Проверка"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 "http://127.0.0.1:$PORT/" || echo 000)
echo "  / -> $code"
if [ "$code" = "200" ]; then
  echo "== ГОТОВО, деплой успешен"
else
  echo "== сайт не отвечает 200, смотри логи uvicorn"
  exit 1
fi

# Сообщаем Яндексу и Bing об обновлении — здесь, а не с локальной машины:
# ключ IndexNow лежит в .env сервера, и поисковик сверяет его с /<ключ>.txt.
# Никогда не роняем деплой из-за этого: сайт уже поднят и проверен выше.
log "Уведомляю поисковики (IndexNow)"
if [ -n "$UV" ]; then
  "$UV" run python scripts/indexnow_ping.py || echo "  пинг не прошёл — не критично"
else
  python3 scripts/indexnow_ping.py || echo "  пинг не прошёл — не критично"
fi
