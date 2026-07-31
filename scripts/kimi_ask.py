"""Драйвер генерации кода игры через Kimi K3 (TokenRouter, OpenAI-совместимый API).

Две проблемы, ради которых существует этот скрипт:

1. Модель reasoning-типа и медленная (~5 символов/сек), а сервер рвёт стрим
   примерно на 300-й секунде. За одно соединение успевает выйти ~1.5 КБ текста.
2. Поэтому ответ приходится собирать по кускам: как только стрим оборвался,
   уже полученный текст отдаётся модели обратно как её собственная реплика,
   и она продолжает ровно с места обрыва.

Использование:
    python scripts/kimi_ask.py <task-file.md> <out-name> [--paid] [--rounds N]

Пишет ответ в `.kimi/<out-name>.md`, метрики — в `.kimi/<out-name>.log`.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
SYSTEM_PROMPT_FILE = ROOT / "docs" / "kimi-fps-prompt.md"
OUT_DIR = ROOT / ".kimi"

BASE_URL = "https://api.tokenrouter.com/v1"
MODEL_FREE = "moonshotai/kimi-k3-free"
MODEL_PAID = "moonshotai/kimi-k3"

MAX_TOKENS = 8000
DEFAULT_ROUNDS = 40
NETWORK_RETRIES = 3
# Сколько хвоста прошлого куска показать модели, чтобы она поняла место обрыва
TAIL_CONTEXT = 1500
# Маркер, которым модель обязана пометить конец задания
DONE_MARKER = "ЗАДАНИЕ ВЫПОЛНЕНО"


def read_api_key() -> str:
    """Достаёт TOKENROUTER_API_KEY из .env, не читая остальные секреты."""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("TOKENROUTER_API_KEY"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("TOKENROUTER_API_KEY не найден в .env")


def system_prompt() -> str:
    """Системная часть ТЗ — всё до маркера первого задания."""
    text = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    return text.split("## ЗАДАНИЕ ЧАСТЬ 1")[0].strip()


def stream_once(
    key: str, model: str, messages: list[dict[str, str]]
) -> tuple[str, str | None, int]:
    """Один заход стриминга.

    Возвращает (полученный текст, finish_reason, символов размышлений).
    Обрыв соединения не считается ошибкой: возвращаем то, что успели получить,
    с finish_reason=None — вызывающий код продолжит с этого места.
    """
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": MAX_TOKENS,
            "stream": True,
            # Без этого модель уходит в размышления на все 300 секунд соединения
            # и не успевает выдать ни строчки кода. Отключить thinking нельзя,
            # low — минимальный поддерживаемый режим.
            "reasoning_effort": "low",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 — схема https зашита в BASE_URL
        f"{BASE_URL}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )

    parts: list[str] = []
    reasoning = 0
    finish: str | None = None
    try:
        # S310: URL — константа BASE_URL в этом же файле, пользовательского ввода нет
        with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data: "):
                    continue
                body = line[6:]
                if body == "[DONE]":
                    break
                try:
                    chunk = json.loads(body)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    reasoning += len(delta.get("reasoning_content") or "")
                    piece = delta.get("content") or ""
                    if piece:
                        parts.append(piece)
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        print(f"  ! стрим оборван: {type(exc).__name__}", file=sys.stderr, flush=True)
    return "".join(parts), finish, reasoning


def generate(key: str, model: str, task: str, out_path: Path, rounds: int) -> dict[str, Any]:
    """Гоняет запросы кругами, пока модель не выдаст маркер завершения."""
    base_messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": task},
    ]
    collected = ""
    stats = {"rounds": 0, "chars": 0, "reasoning": 0, "seconds": 0, "finished": False}
    started = time.time()

    for round_no in range(1, rounds + 1):
        if collected:
            messages = [
                *base_messages,
                {"role": "assistant", "content": collected[-TAIL_CONTEXT * 4 :]},
                {
                    "role": "user",
                    "content": (
                        "Твой прошлый ответ оборвался на середине. Продолжи ровно "
                        "с места обрыва — не повторяй уже написанное, не извиняйся, "
                        "не начинай файл заново. Просто продолжай символ в символ.\n\n"
                        f"Последние строки, которые я получил:\n{collected[-TAIL_CONTEXT:]}"
                    ),
                },
            ]
        else:
            messages = base_messages

        text, finish, reasoning = stream_once(key, model, messages)
        collected += text
        stats["rounds"] = round_no
        stats["chars"] = len(collected)
        stats["reasoning"] += reasoning
        stats["seconds"] = int(time.time() - started)
        out_path.write_text(collected, encoding="utf-8")

        print(
            f"  круг {round_no}: +{len(text)} симв. (всего {len(collected)}), "
            f"reasoning {reasoning}, finish={finish}, {stats['seconds']}с",
            flush=True,
        )

        if DONE_MARKER in collected:
            stats["finished"] = True
            break
        if not text and finish is None:
            # Пустой круг без причины — сервер отдал только размышления.
            # Повторяем, но если так три раза подряд, дальше смысла нет.
            stats.setdefault("empty_rounds", 0)
            stats["empty_rounds"] += 1
            if stats["empty_rounds"] >= NETWORK_RETRIES:
                print("  ! три пустых круга подряд, останавливаюсь", flush=True)
                break
        else:
            stats["empty_rounds"] = 0

    return stats


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    task_file = Path(sys.argv[1])
    if not task_file.is_absolute():
        task_file = ROOT / task_file
    out_name = sys.argv[2]
    model = MODEL_PAID if "--paid" in sys.argv else MODEL_FREE
    rounds = DEFAULT_ROUNDS
    if "--rounds" in sys.argv:
        rounds = int(sys.argv[sys.argv.index("--rounds") + 1])

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"{out_name}.md"

    task = task_file.read_text(encoding="utf-8")
    task += (
        f"\n\n---\nКогда полностью выполнишь задание, последней строкой ответа "
        f"напиши ровно: {DONE_MARKER}"
    )

    print(f"-> {model}, задание {task_file.name} -> {out_path.name}", flush=True)
    stats = generate(read_api_key(), model, task, out_path, rounds)
    (OUT_DIR / f"{out_name}.log").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state = "завершено" if stats["finished"] else "ОБОРВАНО (не хватило кругов)"
    print(f"[{state}] {stats['chars']} симв. за {stats['seconds']}с, кругов {stats['rounds']}")


if __name__ == "__main__":
    main()
