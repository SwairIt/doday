# Кокос Воды — мем-кликер на Three.js

Стек: vanilla HTML + Three.js (via CDN) + JS-modules. Никакого Node.js / npm.
Размер на диске после деплоя: ~50 КБ (без 3D-моделей).

## Файлы

```
app/static/game/
├── index.html      главная страница (Three.js importmap, HUD)
├── styles.css      mobile-first UI overlay
├── game.js         вся 3D-логика и геймплей
├── models/         сюда положи .glb от Tripo3D
│   └── character.glb     (опционально — если есть, заменит procedural placeholder)
└── sounds/         сюда положи .mp3/.ogg от freesound.org
```

## Локальный запуск

```bash
# Через uvicorn (уже запущен для Doday):
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Открой http://127.0.0.1:8000/game
```

## Прод-URL

`https://getdoday.ru/game` — деплоится тем же cron-poll-pull что Doday.

## Как заменить placeholder-персонажа на модель от Tripo3D

1. На https://studio.tripo3d.ai/ сгенери модель с промптом типа
   `cartoon young streamer with headset, exaggerated proportions, low poly`.
2. Экспортируй в формате **.glb** (поддержка анимаций).
3. Положи файл в `app/static/game/models/character.glb`.
4. `git add` + `git push` — через 60 сек на проде.
5. Игра автоматически обнаружит файл (HEAD-fetch) и заменит procedural модель.

## Что в игре сейчас

- 3D-сцена с фиолетовой подсветкой (стримерский стиль)
- Персонаж в центре (procedural placeholder)
- Кокосы падают с неба раз в 1.5–3 сек
- Тап по персонажу: +1 очко, прыжок, частица «+1»
- Тап по кокосу: +5, splash
- Achievement-popup'ы: 10 (Десяточка), 67 (SIX SEVEN, fullscreen), 100, 250, 500
- Поделиться рекордом через Web Share API + Telegram fallback
- High-score в localStorage

## Что добавить

- Звуки на удар (freesound.org → копировать в `sounds/`)
- Анимацию ходьбы через Mixamo (rig модели → Mixamo → анимация → импорт в .glb)
- Background music (loop, тихо)
- Easter egg на 420 / 1488 / другие мем-числа
- Leaderboard (потребует бэкенд — отдельный endpoint в FastAPI)

## Размер на диске

| Файл | Размер |
|---|---|
| index.html | ~3 КБ |
| styles.css | ~6 КБ |
| game.js | ~12 КБ |
| Three.js (через CDN, **0 КБ** на диске) | 0 КБ |
| **Итого код** | **~21 КБ** |
| + character.glb (когда добавишь) | ~1–10 МБ |
| + sounds (опционально) | ~1–5 МБ |
| **Итого с ассетами** | **~5–15 МБ** |

## Анти-юридический момент

Игра НЕ использует имя или образ конкретного блогера (Меллстроя). Persona —
generic «стримерский типаж» (наушники + микрофон + жёлтое лицо). При генерации
моделей в Tripo3D избегай конкретного сходства с реальными людьми — это
закрывает риски по ГК ст. 152.1.

Мемы вроде «67», «кокос воды», «я в моменте» — публичное достояние, можно.
