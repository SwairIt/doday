"""One-shot importer: official ПДД tickets (categories ABM + CD) → Doday PDD seed.

Source: https://github.com/etspring/pdd_russia (public dataset of the official
ГИБДД exam tickets — questions, answers, official commentary, images). For each
category we pull the 40 ticket files + their referenced images, normalise to the
`app.pdd.seed_load.load_dataset` shape (with a `category` field), and write:

  * app/pdd/seed_data/avm.json   — ABM payload (cars / moto)
  * app/pdd/seed_data/cd.json    — CD payload (trucks / buses)
  * app/static/pdd/img/<hash>.jpg — self-hosted question illustrations (shared dir)

Re-runnable to refresh the dataset for a new ПДД year. Run:
  uv run python scripts/pdd_import_avm.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/etspring/pdd_russia/master"
TICKETS = 40
IMG_DIR = Path("app/static/pdd/img")
SEED_DIR = Path("app/pdd/seed_data")

# (category code, source folder, output file)
CATEGORIES = [
    ("ABM", "A_B", "avm.json"),
    ("CD", "C_D", "cd.json"),
]

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}  # fmt: skip


def slugify(text: str) -> str:
    out = "".join(_CYR.get(ch, ch) for ch in text.lower())
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out[:60] or "prochee"


def fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:  # best-effort image download
        print(f"  ! image failed {url}: {exc}", file=sys.stderr)
        return False


def correct_position(answers: list[dict[str, object]], correct_answer: str) -> int:
    for i, a in enumerate(answers, start=1):
        if a.get("is_correct"):
            return i
    m = re.search(r"(\d+)", correct_answer or "")
    return int(m.group(1)) if m else 1


def import_category(category: str, src: str, out_name: str) -> None:
    entries: list[dict[str, object]] = []
    topic_order: dict[str, int] = {}
    images_needed: set[str] = set()

    for n in range(1, TICKETS + 1):
        name = f"Билет {n}.json"
        url = f"{RAW}/questions/{src}/tickets/{urllib.parse.quote(name)}"
        questions = fetch_json(url)
        if not isinstance(questions, list):
            raise TypeError(f"{name}: expected a list of questions")
        for pos, q in enumerate(questions, start=1):
            topics = q.get("topic") or ["Прочее"]
            topic_title = topics[0] if topics else "Прочее"
            topic_slug = slugify(topic_title)
            topic_order.setdefault(topic_slug, len(topic_order) + 1)

            image_ref = q.get("image") or ""
            image_field = None
            if image_ref and "no_image" not in image_ref:
                fname = Path(image_ref).name
                images_needed.add(fname)
                image_field = f"pdd/img/{fname}"

            answers = q.get("answers") or []
            entries.append(
                {
                    "category": category,
                    "ticket": n,
                    "position": pos,
                    "topic_slug": topic_slug,
                    "topic_title": topic_title,
                    "topic_position": topic_order[topic_slug],
                    "text": q.get("question", "").strip(),
                    "image": image_field,
                    "options": [a.get("answer_text", "").strip() for a in answers],
                    "correct_position": correct_position(answers, q.get("correct_answer", "")),
                    "explanation": (q.get("answer_tip") or "").strip(),
                }
            )

    ok = 0
    for fname in sorted(images_needed):
        if download(f"{RAW}/images/{src}/{urllib.parse.quote(fname)}", IMG_DIR / fname):
            ok += 1
    out = SEED_DIR / out_name
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"[{category}] {len(entries)} questions, {len(topic_order)} topics, "
        f"{ok}/{len(images_needed)} images -> {out}"
    )


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    for category, src, out_name in CATEGORIES:
        import_category(category, src, out_name)


if __name__ == "__main__":
    main()
