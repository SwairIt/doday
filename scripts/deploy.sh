#!/usr/bin/env bash
# Деплой Doday на сервер. Запускать НА СЕРВЕРЕ из каталога проекта.
#
#   bash scripts/deploy.sh
#
# Что делает: подтягивает код, ставит зависимости, накатывает миграции,
# перезапускает сервис и проверяет, что сайт отвечает. Любой шаг падает —
# скрипт останавливается, чтобы не оставить прод в половинчатом состоянии.
set -euo pipefail

SERVICE="${DODAY_SERVICE:-doday}"
BASE_URL="${DODAY_BASE_URL:-http://127.0.0.1:8011}"

step() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }

step "Текущая версия"
git rev-parse --short HEAD

step "Забираю код"
git pull --ff-only

step "Зависимости"
if command -v uv >/dev/null 2>&1; then
  uv sync --frozen || uv sync
else
  echo "uv не найден — пропускаю (зависимости не менялись?)"
fi

step "Миграции базы"
# Через python -m: обёртки в .venv собраны под путь другой машины и падают
# с «uv trampoline failed to canonicalize script path».
if command -v uv >/dev/null 2>&1; then
  uv run python -m alembic upgrade head
else
  python -m alembic upgrade head
fi

step "Перезапуск $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 3
systemctl is-active "$SERVICE"

step "Проверка"
for path in / /all /pricing /app/today; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$BASE_URL$path" || echo 000)
  printf '  %-14s %s\n' "$path" "$code"
  case "$path:$code" in
    /:200|/all:200|/pricing:200) ;;
    "/app/today:401"|"/app/today:302"|"/app/today:303") ;;  # требует входа — норма
    *) echo "  ! неожиданный ответ, смотри journalctl -u $SERVICE -n 50"; exit 1 ;;
  esac
done

step "Готово"
git rev-parse --short HEAD
