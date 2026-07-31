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
    lines = text.splitlines(keepends=True)
    if not any(FENCE_LINE.match(line) for line in lines):
        return text.lstrip()

    kept: list[str] = []
    inside = False
    for line in lines:
        if FENCE_LINE.match(line):
            inside = not inside
            continue
        if inside:
            kept.append(line)
    # Хвост НЕ трогаем: обрыв бывает посреди слова, и добавленный сюда перевод
    # строки разрезал бы идентификатор пополам (SIDEWALK + \n + _HEIGHT).
    return "".join(kept).lstrip()


FENCE_ANY = re.compile(r"```[a-zA-Z]*\n?")


def strip_fences(text: str) -> str:
    """Убирает ограды блоков кода где угодно, включая середину строки.

    Стрим рвётся посреди строки, и продолжение начинается с ```javascript —
    склеенный текст даёт `let```javascript` прямо в коде. Ограду удаляем
    вместе с её переводом строки, чтобы оборванная строка срослась обратно.
    """
    return FENCE_ANY.sub("", text)


OVERLAP_WINDOW = 400


def merge_overlap(head: str, tail: str) -> str:
    """Приклеивает продолжение, срезая повторённый кусок.

    Модель, продолжая оборванный ответ, обычно переписывает конец последней
    строки заново: было `const btn = this[name`, продолжение начинается с
    `this[name];` — и в коде появляется мусор. Ищем наибольший суффикс уже
    написанного, с которого начинается продолжение, и выбрасываем его.
    """
    if not head or not tail:
        return head + tail
    limit = min(OVERLAP_WINDOW, len(head), len(tail))
    for size in range(limit, 8, -1):
        if head.endswith(tail[:size]):
            return head + tail[size:]
    return head + tail


def drop_restart(code: str) -> str:
    """Отрезает второй заход, если модель начала файл заново вместо продолжения.

    После обрыва Kimi нередко пишет файл с нуля, а склейка честно добавляет
    вторую копию — получается `Identifier 'THREE' has already been declared`.
    Ищем повтор «отпечатка» начала файла и режем по нему.
    """
    lines = code.splitlines()
    imports = [i for i, ln in enumerate(lines) if ln.strip().startswith("import ")]
    if len(imports) < 2:
        return code

    def header_at(position: int) -> list[str]:
        """Подряд идущие импорты начиная с указанной строки (пустые строки допустимы)."""
        block: list[str] = []
        previous = None
        for i in imports:
            if i < position:
                continue
            if previous is not None and i - previous > 2:
                break
            block.append(lines[i].strip())
            previous = i
        return block

    block = header_at(imports[0])
    if len(block) < 2:
        return code

    # Ищем строку, С КОТОРОЙ начинается точно такая же шапка импортов
    for start in imports[1:]:
        if header_at(start)[: len(block)] == block:
            # Перезапуск начинается не с import, а с шапки-комментария над ним
            cut = start
            while cut > 0:
                previous = lines[cut - 1].strip()
                if previous and not previous.startswith(("//", "/*", "*", "*/")):
                    break
                cut -= 1
            head = "\n".join(lines[:cut]).rstrip()
            # Оставляем ту копию, что выглядит завершённой
            if "export " in head:
                return head + "\n"
            return "\n".join(lines[cut:]).strip() + "\n"
    return code


def syntax_ok(path: Path) -> tuple[bool, str]:
    """Проверяет JS модульным парсером Node.

    Важно именно `--input-type=module`: обычный `node --check` разбирает файл
    как скрипт и пропускает обрывы, которые браузерный загрузчик модулей
    отвергает (проверено на четырёх файлах — Node молчал, Chrome падал).
    """
    if path.suffix != ".js":
        return True, ""
    try:
        # S603/S607: локальный dev-скрипт, вход — файл из манифеста, не ввод извне
        result = subprocess.run(
            ["node", "--input-type=module", "--check"],  # noqa: S607
            input=path.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            encoding="utf-8",  # иначе stdin уходит в cp1251 и рвётся на кириллице
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


EXPORT_HINT = re.compile(r"[Ээ]кспорт(?:ировать)?\s+(?:также\s+)?([A-Za-z_][A-Za-z0-9_]*)")


def missing_exports(spec: str, code: str) -> list[str]:
    """Какие имена из ТЗ не встретились в коде.

    Ловит случай, когда модель успела выдать только шапку с константами:
    такой файл валиден синтаксически, но бесполезен.
    """
    return [name for name in set(EXPORT_HINT.findall(spec)) if name not in code]


def looks_complete(path: str, code: str, spec: str = "") -> bool:
    """Проверка, что файл не обрезан на полуслове и содержит обещанное."""
    if not code.strip():
        return False
    if path.endswith(".html"):
        return "</html>" in code
    if path.endswith(".css"):
        return code.rstrip().endswith("}")
    # JS: экспорты есть и все имена из ТЗ на месте. Скобки не считаем — их
    # баланс врёт на скобках внутри строк и комментариев, за синтаксис
    # отвечает node --check.
    return "export " in code and not missing_exports(spec, code)


EXPORT_DECL = re.compile(
    r"export\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)"
)
# Сигнатуры: `export function f(a, b)`, `export class C`, `export const f = (a) =>`
EXPORT_SIGNATURE = re.compile(
    r"export\s+(?:async\s+)?(?:"
    r"function\s+(?P<fn>[A-Za-z_$][\w$]*)\s*\((?P<fnargs>[^)]*)\)"
    r"|class\s+(?P<cls>[A-Za-z_$][\w$]*)"
    r"|const\s+(?P<cn>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\((?P<cargs>[^)]*)\)\s*=>"
    r"|const\s+(?P<vn>[A-Za-z_$][\w$]*)\s*="
    r")"
)


CLASS_METHOD = re.compile(
    r"^  (?:async\s+)?(?!constructor)([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*\{", re.M
)


def class_methods(code: str, name: str) -> str:
    """Публичные методы экспортируемого класса — иначе непонятно, как им пользоваться."""
    start = code.find(f"class {name}")
    if start < 0:
        return ""
    body = code[start:]
    methods = [
        f"{m.group(1)}({m.group(2).strip()})"
        for m in CLASS_METHOD.finditer(body)
        if not m.group(1).startswith("_")
    ][:8]
    return f" {{{', '.join(methods)}}}" if methods else ""


def signatures_of(code: str) -> list[str]:
    """Сигнатуры экспортов файла — с именами параметров, а не только имена."""
    found = []
    for m in EXPORT_SIGNATURE.finditer(code):
        if m.group("fn"):
            found.append(f"{m.group('fn')}({m.group('fnargs').strip()})")
        elif m.group("cls"):
            found.append(f"class {m.group('cls')}{class_methods(code, m.group('cls'))}")
        elif m.group("cn"):
            found.append(f"{m.group('cn')}({m.group('cargs').strip()})")
        elif m.group("vn"):
            found.append(m.group("vn"))
    return found


def export_map() -> str:
    """Карта «файл → его РЕАЛЬНЫЕ сигнатуры» для уже написанных модулей.

    Одних имён мало: получив только `createSky`, модель сама придумала ему
    аргументы и вызвала `createSky()` вместо `createSky(scene, renderer,
    settings)`. Такое расхождение не ловится ни синтаксисом, ни сверкой
    импортов — только запуском. Поэтому отдаём параметры.
    """
    lines = []
    for js in sorted(GAME_DIR.rglob("*.js")):
        names = signatures_of(js.read_text(encoding="utf-8"))
        if names:
            rel = js.relative_to(GAME_DIR).as_posix()
            lines.append(f"  {rel} -> {'; '.join(dict.fromkeys(names))}")
    if not lines:
        return ""
    return (
        "\n\nУже написанные модули и их РЕАЛЬНЫЕ сигнатуры. Вызывай ровно так, "
        "с этим числом и порядком аргументов; ничего не выдумывай:\n" + "\n".join(lines)
    )


def generate_file(key: str, path: str, spec: str) -> tuple[str, dict[str, Any]]:
    """Генерирует один файл, при обрыве просит продолжить."""
    task = (
        f"Напиши файл `{path}` для проекта Doday Arena.\n\n"
        f"Требования к файлу:\n{spec}"
        f"{export_map()}\n\n"
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
        # Первый ответ чистим целиком (там есть вступление до блока), продолжения —
        # только от оград, ничего вокруг не трогая: обрыв бывает посреди строки,
        # и лишний перевод строки в этом месте сломал бы код.
        if text:
            piece = extract_code(text) if not collected else strip_fences(text)
            collected = merge_overlap(collected, piece)
        stats["rounds"] = attempt
        stats["reasoning"] += reasoning
        stats["seconds"] = int(time.time() - started)
        code = collected

        if finish == "stop" and looks_complete(path, code, spec):
            break
        if not text:
            print(f"    пустой круг {attempt}, повтор", flush=True)
            continue
        # Выравниваем обрыв по границе строки: недописанную строку выбрасываем,
        # иначе продолжение приклеивается к её огрызку и даёт мусор вида
        # `for            let anyFar = false;` — модель редко попадает
        # в точности в место разрыва посреди выражения.
        newline = collected.rfind("\n")
        if newline > 0:
            collected = collected[: newline + 1]

        print(f"    обрыв на {len(collected)} симв., прошу продолжить", flush=True)
        messages = [
            *messages[:2],
            {"role": "assistant", "content": collected[-6000:]},
            {
                "role": "user",
                "content": (
                    "Ответ оборвался на границе строки. Продолжи со СЛЕДУЮЩЕЙ "
                    "строки — первый же символ твоего ответа должен быть началом "
                    "новой строки кода. Не повторяй написанное, не дописывай "
                    "предыдущую строку, не начинай файл заново, не извиняйся. "
                    "Продолжение оберни в новый блок кода и не пиши вне него ни слова."
                ),
            },
        ]

    stats["chars"] = len(collected)
    stats["complete"] = looks_complete(path, collected, spec)
    return drop_restart(collected).rstrip() + "\n", stats


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
        if valid and looks_complete(path, code, spec):
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
        code = drop_restart(merge_overlap(code, strip_fences(text)))
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
