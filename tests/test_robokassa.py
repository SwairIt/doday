"""Подписи Robokassa — единственное, что отделяет чужой запрос от настоящего.

Сетевых вызовов здесь нет: проверяем чистую арифметику подписи и формат чека,
чтобы ошибка в порядке полей всплыла в CI, а не на живых деньгах.
"""

from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qs, urlparse

import pytest

from app.billing import robokassa
from app.billing.products import get_product
from app.config import get_settings

LOGIN = "demo_shop"
PASS1 = "pass_one"
PASS2 = "pass_two"


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подкладываем ключи магазина, не трогая .env."""
    settings = get_settings()
    monkeypatch.setattr(settings, "robokassa_login", LOGIN, raising=False)
    monkeypatch.setattr(settings, "robokassa_password1", PASS1, raising=False)
    monkeypatch.setattr(settings, "robokassa_password2", PASS2, raising=False)
    monkeypatch.setattr(settings, "robokassa_test_mode", False, raising=False)


def test_configured_only_with_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    assert robokassa.is_configured() is True
    monkeypatch.setattr(get_settings(), "robokassa_password2", "", raising=False)
    assert robokassa.is_configured() is False


def test_receipt_is_minified_and_vat_free() -> None:
    """Чек самозанятого: без НДС и без пробелов — пробелы ломают подпись."""
    product = get_product("pro_1m")
    assert product is not None
    receipt = robokassa.build_receipt(product)

    assert " " not in receipt.replace(product.title, "")  # пробелы только в названии
    parsed = json.loads(receipt)
    item = parsed["items"][0]
    assert item["tax"] == "none"
    assert item["sum"] == float(product.rub_amount)
    assert item["payment_object"] == "service"


def test_payment_url_signature_matches_documented_order() -> None:
    """Порядок полей задан Robokassa: login:sum:inv:receipt:пароль1:shp."""
    product = get_product("pro_1m")
    assert product is not None
    url = robokassa.build_payment_url(product, inv_id=42, email="user@example.com")

    query = parse_qs(urlparse(url).query)
    receipt = robokassa.build_receipt(product)
    expected = hashlib.md5(  # noqa: S324 — алгоритм диктует Robokassa
        f"{LOGIN}:199.00:42:{receipt}:{PASS1}:Shp_code=pro_1m".encode()
    ).hexdigest()

    assert query["SignatureValue"][0] == expected
    assert query["OutSum"][0] == "199.00"
    assert query["InvId"][0] == "42"
    assert query["Shp_code"][0] == "pro_1m"
    assert query["Email"][0] == "user@example.com"
    assert "IsTest" not in query


def test_test_mode_flag_is_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "robokassa_test_mode", True, raising=False)
    product = get_product("pro_1m")
    assert product is not None
    query = parse_qs(urlparse(robokassa.build_payment_url(product, inv_id=1)).query)
    assert query["IsTest"][0] == "1"


def test_result_signature_uses_second_password() -> None:
    """Уведомление подписывается Паролем №2 — Пароль №1 не подходит."""
    shp = {"Shp_code": "pro_1m"}
    good = hashlib.md5(  # noqa: S324
        f"199.00:42:{PASS2}:Shp_code=pro_1m".encode()
    ).hexdigest()
    assert robokassa.verify_result("199.00", "42", good, shp) is True
    assert robokassa.verify_result("199.00", "42", good.upper(), shp) is True

    with_pass1 = hashlib.md5(  # noqa: S324
        f"199.00:42:{PASS1}:Shp_code=pro_1m".encode()
    ).hexdigest()
    assert robokassa.verify_result("199.00", "42", with_pass1, shp) is False


def test_result_signature_rejects_tampered_amount() -> None:
    """Подменённая сумма обязана ломать подпись — иначе Pro можно купить за рубль."""
    shp = {"Shp_code": "pro_1m"}
    signature = hashlib.md5(  # noqa: S324
        f"199.00:42:{PASS2}:Shp_code=pro_1m".encode()
    ).hexdigest()
    assert robokassa.verify_result("1.00", "42", signature, shp) is False


def test_unconfigured_shop_refuses_to_build_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "robokassa_login", "", raising=False)
    product = get_product("pro_1m")
    assert product is not None
    with pytest.raises(robokassa.RobokassaError):
        robokassa.build_payment_url(product, inv_id=1)
