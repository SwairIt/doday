"""Lessio Stars products are wired into the catalog + sign properly."""

from uuid import uuid4

from app.billing.products import BY_CODE, get_product
from app.billing.stars import sign_payload, verify_payload


def test_lessio_products_registered() -> None:
    for code in ("tutor_pro_1m", "tutor_pro_12m", "tutor_pro_forever"):
        assert code in BY_CODE, f"missing product: {code}"
        product = get_product(code)
        assert product is not None
        assert product.grants_tier == "pro"


def test_lessio_pricing_matches_landing_copy() -> None:
    """Landing page promises 1000⭐/мес, 10000⭐/год, 50000⭐ Founder.
    If we change pricing in PRODUCTS, landing copy goes stale — test catches.
    """
    pro_1m = get_product("tutor_pro_1m")
    pro_12m = get_product("tutor_pro_12m")
    forever = get_product("tutor_pro_forever")
    assert pro_1m is not None and pro_1m.stars_amount == 1000
    assert pro_12m is not None and pro_12m.stars_amount == 10000
    assert forever is not None and forever.stars_amount == 50000
    # Founder is lifetime — no duration_months
    assert forever.duration_months is None


def test_lessio_payload_signs_and_verifies() -> None:
    """Round-trip via HMAC — payload signed for a Lessio product verifies back."""
    user_id = uuid4()
    payload = sign_payload("tutor_pro_1m", user_id)
    product_code, returned_uid, nonce = verify_payload(payload)
    assert product_code == "tutor_pro_1m"
    assert returned_uid == user_id
    assert nonce  # non-empty
