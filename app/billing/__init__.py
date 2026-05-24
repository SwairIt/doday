"""Billing module — tier limits, Stars payments, and product catalog.

The `models` module is imported here so that simply `import app.billing` is
enough to register StarPayment with SQLAlchemy's Base.metadata. Without this,
conftest's drop_all/create_all would leave the table behind (same bug we hit
with gamification in May 2026 — see feedback_test_db_concurrency).
"""

from app.billing import models as _models  # noqa: F401
