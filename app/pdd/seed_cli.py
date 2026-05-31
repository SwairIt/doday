"""Load the PDD dataset into the database.

Reads DATABASE_URL from the app settings (same engine as the running app), so it
works both locally and on prod against the shared Doday database.

Usage:
    uv run python -m app.pdd.seed_cli app/pdd/seed_data/avm.json
    # on prod where `uv` may not be on the non-interactive PATH:
    .venv/bin/python -m app.pdd.seed_cli app/pdd/seed_data/avm.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from app.db import get_session_maker
from app.pdd.seed_load import load_dataset


async def _run(path: str) -> None:
    data: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))
    async with get_session_maker()() as session:
        counts = await load_dataset(session, data)
    print("seeded:", counts)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m app.pdd.seed_cli <dataset.json>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
