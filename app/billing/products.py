"""Product catalog — what users can buy with Telegram Stars.

Single source of truth for the Stars price list. Adding a product means adding
an entry here; nothing else needs to change in the payment flow.

Pricing rationale:
- 1 Star ≈ $0.013 USD ≈ ₽1.2 (Telegram takes ~30% commission).
- Net to dev: ~₽0.84 per Star.
- Pro 1 month should net ~₽199 (parity with planned card price) → ~240 Stars
  gross. Round to 250 for symmetry.
- Pro 12 months priced for 17% volume discount → 2500 Stars (vs 250×12=3000).
- Pro forever as ~5× yearly price → 12500 Stars (for people who want to lock
  the «founder» discount before official launch).
- Family seats are 5x → 5× the per-account Pro price minus team discount.

These numbers can be tuned without code changes by editing this file. Existing
StarPayment records keep their historical price — `stars_amount` is stored
per-payment, not looked up retroactively.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    """One line item in the Stars catalog."""

    code: str
    title: str
    description: str
    # What global tier this purchase grants (set on user.tier after payment).
    # None for entitlement-only products (e.g. ПДД) that must NOT touch the
    # studio-wide tier — see grants_entitlement.
    grants_tier: str | None
    # How long the paid period lasts. None == lifetime (no expiry).
    duration_months: int | None
    stars_amount: int
    # If set, the purchase upserts an Entitlement(feature=...) instead of (or in
    # addition to) the global tier. Lets a vertical (pdd_pro) be sold and priced
    # independently of Doday Pro. Defaults to None → behaves exactly as before.
    grants_entitlement: str | None = None


PRODUCTS: tuple[Product, ...] = (
    Product(
        code="pro_1m",
        title="Doday Pro · 1 месяц",
        description=(
            "Безлимитные проекты и задачи, премиум-темы, утренний email-дайджест, "
            "Telegram-бот, эксп-функции — на 30 дней."
        ),
        grants_tier="pro",
        duration_months=1,
        stars_amount=250,
    ),
    Product(
        code="pro_12m",
        title="Doday Pro · 12 месяцев",
        description=(
            "Всё что в Pro 1 мес, но на год. Выгоднее на 17% — как 10 месяцев по цене 12."
        ),
        grants_tier="pro",
        duration_months=12,
        stars_amount=2500,
    ),
    Product(
        code="pro_forever",
        title="Doday Pro · навсегда",
        description=(
            "Founder-тариф — Pro без ограничения по времени. Платишь один раз — "
            "пользуешься пока сервис жив. Лимитировано первой тысячей юзеров."
        ),
        grants_tier="pro",
        duration_months=None,  # lifetime
        stars_amount=12500,
    ),
    Product(
        code="family_1m",
        title="Doday Family · 1 месяц",
        description=(
            "Pro на 5 аккаунтов + родительская панель (когда выйдет) — для "
            "семей с детьми-учениками. На 30 дней."
        ),
        grants_tier="family",
        duration_months=1,
        stars_amount=500,
    ),
    Product(
        code="family_12m",
        title="Doday Family · 12 месяцев",
        description=("Family-подписка на год. Скидка ~17% против помесячной."),
        grants_tier="family",
        duration_months=12,
        stars_amount=5000,
    ),
    # ── Lessio (Telegram-кабинет для репетиторов) — отдельный продукт внутри
    # того же бота @DodayTaskBot. Запускается после прохождения waitlist-
    # валидации (≥100 подписок к 2026-06-01).
    Product(
        code="tutor_pro_1m",
        title="Lessio Pro · 1 месяц",
        description=(
            "Безлимит клиентов и занятий, статистика, экспорт CSV для «Моего "
            "налога», брендирование бота — на 30 дней."
        ),
        grants_tier="pro",
        duration_months=1,
        stars_amount=1000,
    ),
    Product(
        code="tutor_pro_12m",
        title="Lessio Pro · 12 месяцев",
        description=(
            "Всё что в Pro 1 мес, но на год. Выгоднее на 17% — как 10 месяцев по цене 12."
        ),
        grants_tier="pro",
        duration_months=12,
        stars_amount=10000,
    ),
    Product(
        code="tutor_pro_forever",
        title="Lessio Pro · Founder",
        description=(
            "Founder-тариф — Pro без ограничения по времени. Платишь один раз, "
            "пользуешься пока сервис жив. Лимит — первые 200 репетиторов."
        ),
        grants_tier="pro",
        duration_months=None,  # lifetime
        stars_amount=50000,
    ),
    # ── Doday ПДД (driving-exam prep) — standalone `pdd_pro` entitlement,
    # independent of the global tier. Revenue lands on @DodayTaskBot's Stars
    # balance (codes don't start with `tutor_pro_`). The 3-month tier is the
    # hero: a one-time exam-window buy that sidesteps Stars' lack of web
    # auto-renew (the churn cycle is the exam, not a calendar month).
    Product(
        code="pdd_pro_1m",
        title="ПДД Pro · 1 месяц",
        description=(
            "Тренажёр ошибок, история экзаменов, статистика и PDF слабых тем — на 30 дней."
        ),
        grants_tier=None,
        duration_months=1,
        stars_amount=199,
        grants_entitlement="pdd_pro",
    ),
    Product(
        code="pdd_pro_3m",
        title="ПДД Pro · до экзамена (3 мес)",
        description=(
            "Всё что в ПДД Pro, на 3 месяца — ровно на период подготовки к экзамену. "
            "Выгоднее помесячной."
        ),
        grants_tier=None,
        duration_months=3,
        stars_amount=399,
        grants_entitlement="pdd_pro",
    ),
    Product(
        code="pdd_pro_forever",
        title="ПДД Pro · навсегда",
        description="ПДД Pro без ограничения по времени. Платишь один раз.",
        grants_tier=None,
        duration_months=None,  # lifetime
        stars_amount=990,
        grants_entitlement="pdd_pro",
    ),
)


# Convenience lookup: code → Product.
BY_CODE: dict[str, Product] = {p.code: p for p in PRODUCTS}


def get_product(code: str) -> Product | None:
    """Return the product or None for unknown codes."""
    return BY_CODE.get(code)
