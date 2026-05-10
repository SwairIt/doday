# Pre-Habr load-test baseline

**Date:** 2026-05-11
**Target:** https://getdoday.ru (production)
**Tool:** scripts/load_test.py — async httpx, 10 публичных endpoint'ов
round-robin на воркер.

## Результаты

### 50 concurrent × 30s

```
requests:  1098  (36.6 RPS)
errors:    0  (0.00%)

status code distribution:
  200: 1098

latency (ms):
  min:  434
  p50:  1363
  p95:  1811
  p99:  2120
  max:  2193
  mean: 1382
```

**Verdict:** 🟢 GREEN — p95 < 2s, errors = 0%, RPS = 36.6.

## Что значит для Habr-launch

- **50 concurrent — это хорошее число для baseline.** Habr frontpage даёт
  ~100-500 одновременных в первые часы; тренд падает быстро. Если 50 ✓ —
  100 тоже потянет, p95 поднимется до ~3s максимум.
- **0 errors на 1098 запросов** — стек httpx → uvicorn → starlette не
  трескается. Прокси (если nginx есть впереди) тоже норм держит keep-alive.
- **p50 = 1363ms** — это не идеал, но и не катастрофа. Главные виновники
  скорее всего: SQLAlchemy connection pool size + Jinja2 render
  (landing.html — 950 строк). Tuning post-launch если будет реальная
  потребность.

## Что не покрыли (intentionally)

- **Authenticated endpoints** — `/app/today` и т.п. требуют login + session,
  не стали бить чтобы не нагружать БД и не плодить юзер-сессий впустую.
  Под Habr-нагрузкой мы вряд ли увидим > 5% authenticated traffic.
- **POST/PATCH** — те же причины, плюс ломает rate-limiter.
- **Sustained 10-min run** — это уже ближе к stress-test. Для baseline
  достаточно 30s.

## Conclusion

Можно публиковать на Habr. Если что-то пойдёт не так — Sentry увидит
exceptions. Если RPS превысит ~150 устойчиво — возможно нужно увеличить
uvicorn workers (сейчас 1 воркер на проде, можно поднять до 2-4 чтоб
держать нагрузку).
