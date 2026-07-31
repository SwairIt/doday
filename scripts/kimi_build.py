"""Конвейер: гонит манифест игры через Kimi K3, файл за файлом.

Один файл — один запрос: соединение у TokenRouter живёт ~300 секунд, за которые
при reasoning_effort=low выходит около 5 КБ кода. Если ответ всё же обрывается,
скрипт просит модель продолжить с места обрыва (см. kimi_ask.stream_once).

Использование:
    python scripts/kimi_build.py            # все недостающие файлы
    python scripts/kimi_build.py --only src/world/city.js
    python scripts/kimi_build.py --force    # перегенерировать даже существующие
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.kimi_ask import read_api_key, stream_once
from scripts.kimi_manifest import CONTRACT, FILES

ROOT = Path(__file__).resolve().parent.parent
# Именно arena, а не game: в app/static/game/ живёт «Беллстрой ТВ», её index.html
# и styles.css затёрлись бы файлами из манифеста.
GAME_DIR = ROOT / "app" / "static" / "arena"
LOG_FILE = ROOT / ".kimi" / "build.jsonl"

MODEL = "moonshotai/kimi-k3-free"
MAX_CONTINUATIONS = 6
FENCE_LINE = re.compile(r"^\s*```[a-zA-Z]*\s*$")


def system_prompt() -> str:
    return (
        "Ты — senior game-программист, специализация: Three.js, WebGL2, шутеры "
        "от первого лица, оптимизация под мобильные GPU. Пишешь production-код "
        "без заглушек и без TODO.\n" + CONTRACT
    )


def extract_code(text: str) -> str:
    """Склеивает код из ответа, выбрасывая разметку блоков.

    Брать «первый блок» нельзя: при продолжении оборванного ответа модель
    открывает новый блок, и всё, что после него, потерялось бы. Поэтому просто
    выкидываем строки-заборы, а прозу до самого первого забора отрезаем.
    """
    lines = text.splitlines()
    if not any(FENCE_LINE.match(line) for line in lines):
        return text.strip() + "\n"

    kept: list[str] = []
    inside = False
    for line in lines:
        if FENCE_LINE.match(line):
            inside = not inside
            continue
        if inside:
            kept.append(line)
    return "\n".join(kept).strip() + "\n"


def syntax_ok(path: Path) -> tuple[bool, str]:
    """Прогоняет JS через `node --check`. Ловит обрывы, которые баланс скобок не видит."""
    if path.suffix != ".js":
        return True, ""
    try:
        # S603/S607: локальный dev-скрипт, аргумент — путь из манифеста, не ввод извне
        result = subprocess.run(  # noqa: S603
            ["node", "--check", str(path)],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True, ""  # нет node — проверку просто пропускаем
    if result.returncode == 0:
        return True, ""
    # Полезная строка — та, где сам SyntaxError, а не хвост со версией Node
    lines = result.stderr.strip().splitlines()
    detail = next((ln for ln in lines if "Error" in ln), lines[0] if lines else "")
    return False, detail.strip()


def looks_complete(path: str, code: str) -> bool:
    """Грубая проверка, что файл не обрезан на полуслове."""
    if not code.strip():
        return False
    if path.endswith(".html"):
        return "</html>" in code
    if path.endswith(".css"):
        return code.rstrip().endswith("}")
    # JS: скобки должны сходиться
    return code.count("{") == code.count("}") and code.count("(") == code.count(")")


def generate_file(key: str, path: str, spec: str) -> tuple[str, dict[str, Any]]:
    """Генерирует один файл, при обрыве просит продолжить."""
    task = (
        f"Напиши файл `{path}` для проекта Doday Arena.\n\n"
        f"Требования к файлу:\n{spec}\n\n"
        "Выдай ТОЛЬКО код этого файла, целиком, в одном блоке кода."
    )
    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": task},
    ]
    collected = ""
    stats: dict[str, Any] = {"path": path, "rounds": 0, "seconds": 0, "reasoning": 0}
    started = time.time()

    for attempt in range(1, MAX_CONTINUATIONS + 1):
        text, finish, reasoning = stream_once(key, MODEL, messages)
        collected += text
        stats["rounds"] = attempt
        stats["reasoning"] += reasoning
        stats["seconds"] = int(time.time() - started)
        code = extract_code(collected)

        if finish == "stop" or looks_complete(path, code):
            break
        if not text:
            print(f"    пустой круг {attempt}, повтор", flush=True)
            continue
        print(f"    обрыв на {len(collected)} симв., прошу продолжить", flush=True)
        messages = [
            *messages[:2],
            {"role": "assistant", "content": collected[-6000:]},
            {
                "role": "user",
                "content": (
                    "Ответ оборвался. Продолжи ровно с места обрыва, символ в символ. "
                    "Не повторяй написанное, не начинай файл заново, не извиняйся. "
                    "Продолжение оберни в новый блок кода и не пиши вне него ни слова."
                ),
            },
        ]

    stats["chars"] = len(extract_code(collected))
    stats["complete"] = looks_complete(path, extract_code(collected))
    return extract_code(collected), stats


def finish_file(key: str, path: str, spec: str, rounds: int) -> None:
    """Дописывает уже существующий, но оборванный файл.

    Крупные модули не влезают в лимит продолжений одного прохода, поэтому
    хвост добираем отдельным заходом: отдаём модели конец файла и просим
    продолжить с этого места.
    """
    target = GAME_DIR / path
    code = target.read_text(encoding="utf-8")

    for attempt in range(1, rounds + 1):
        valid, _ = syntax_ok(target)
        if valid and looks_complete(path, code):
            print(f"    файл целый на круге {attempt}", flush=True)
            return

        messages = [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": (
                    f"Файл `{path}` для Doday Arena написан не до конца.\n\n"
                    f"Требования к файлу:\n{spec}\n\n"
                    "Ниже — конец того, что уже написано. Продолжи ровно с места "
                    "обрыва, символ в символ, и доведи файл до конца. Не повторяй "
                    "написанное, не начинай заново, не пиши ничего вне блока кода.\n\n"
                    f"```javascript\n{code[-4000:]}\n```"
                ),
            },
        ]
        text, finish, _ = stream_once(key, MODEL, messages)
        if not text:
            print(f"    пустой круг {attempt}", flush=True)
            continue
        code += extract_code(text)
        target.write_text(code, encoding="utf-8")
        print(f"    +{len(text)} симв. (всего {len(code)}), finish={finish}", flush=True)

    valid, error = syntax_ok(target)
    print(f"    итог: {len(code)} симв., синтаксис {'ok' if valid else error}", flush=True)


def main() -> None:
    force = "--force" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    key = read_api_key()
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(exist_ok=True)

    todo = [(p, s) for p, s in FILES if only is None or p == only]

    if "--finish" in sys.argv:
        for path, spec in todo:
            if (GAME_DIR / path).exists():
                print(f"дописываю {path}", flush=True)
                finish_file(key, path, spec, rounds=8)
        return

    print(f"файлов в очереди: {len(todo)}", flush=True)

    for index, (path, spec) in enumerate(todo, 1):
        target = GAME_DIR / path
        if target.exists() and not force:
            print(f"[{index}/{len(todo)}] {path} — уже есть, пропускаю", flush=True)
            continue

        print(f"[{index}/{len(todo)}] {path} — генерирую…", flush=True)
        code, stats = generate_file(key, path, spec)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")

        valid, error = syntax_ok(target)
        stats["syntax_ok"] = valid
        if not valid:
            stats["syntax_error"] = error
            print(f"    СИНТАКСИС: {error}", flush=True)

        mark = "ok" if stats["complete"] and valid else "БРАК"
        print(
            f"    {mark}: {stats['chars']} симв., кругов {stats['rounds']}, {stats['seconds']}с",
            flush=True,
        )
        with LOG_FILE.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(stats, ensure_ascii=False) + "\n")

    print("очередь пройдена", flush=True)


if __name__ == "__main__":
    main()
