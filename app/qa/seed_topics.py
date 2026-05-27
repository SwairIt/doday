"""Static lookup of seed subjects for the bot-user attribution + dev seeding.

The full Q&A seed content lives as JSON in `seed_data/` (built by the
overnight agent run). This file only declares the system-bot identity
and per-subject metadata used by the loader.
"""

from __future__ import annotations

BOT_USER_EMAIL = "bot@razbery.local"
BOT_USER_DISPLAY_NAME = "Razbery"
BOT_USER_DISPLAY_SLUG = "razbery-bot"
BOT_USER_BIO = "Редакторские заготовки для старта. Помогают учить — а не списывать."


# Marker that distinguishes seed JSON files from arbitrary other files
# inside `seed_data/`. Loader globs `seed_data/*.json`.
SEED_FILES_GLOB = "*.json"
