"""Thin CLI wrapper — `python -m app.qa.seed_load` calls into seeding.main()."""

from __future__ import annotations

from app.qa.seeding import main

if __name__ == "__main__":
    main()
