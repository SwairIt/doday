"""Doday PDD — free SEO-indexed official driving-exam tickets (category A/B/M)
plus a Telegram-Stars Pro layer (mistake trainer, exam simulator, stats, PDF).

Per-feature module layout mirrors `app/qa/`: models / schemas / service / router
/ seo / seed_load / pdf. Routers go through `service`; they never touch the ORM
directly. Monetization rides the standalone `pdd_pro` entitlement in
`app/billing/` (see `app/pdd/service.is_pdd_pro`).
"""
