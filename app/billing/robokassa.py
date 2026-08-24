"""Приём оплаты картой и через СБП по протоколу Robokassa.

Почему именно Robokassa: владелец сервиса — самозанятый, а ЮKassa 29.12.2025
прекратила поддержку сервисов для самозанятых (чеки при платежах и возвратах).
У Robokassa для этого есть «Робочеки СМЗ» — чек уходит в ФНС и покупателю
автоматически, вручную в «Мой налог» ничего вбивать не нужно.

Схема обмена:

1. Мы формируем ссылку на платёжную страницу с подписью на Пароле №1.
2. Пользователь платит на стороне Robokassa.
3. Robokassa дёргает наш ResultURL с подписью на Пароле №2 — это единственный
   источник правды об оплате. Ответ обязан быть строкой ``OK<InvId>``, иначе
   уведомление будет повторяться.
4. Пользователь возвращается на SuccessURL — он ничего не подтверждает и
   доступ по нему НЕ выдаём: адрес можно открыть руками.
"""

from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from urllib.parse import quote, urlencode

from app.billing.products import Product
from app.config import get_settings

logger = logging.getLogger("doday.billing.robokassa")

PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"

# Ставка НДС для самозанятого: он не плательщик НДС.
TAX_NONE = "none"


class RobokassaError(RuntimeError):
    """Ошибка конфигурации или протокола Robokassa."""


def is_configured() -> bool:
    """Настроен ли приём карт. Если нет — на сайте показываем только Stars."""
    s = get_settings()
    return bool(s.robokassa_login and s.robokassa_password1 and s.robokassa_password2)


def _hash(raw: str) -> str:
    """Подпись. Алгоритм должен совпадать с выбранным в личном кабинете магазина.

    По умолчанию у Robokassa MD5. Он тут не для секретности, а для сверки с
    их стороной, поэтому S324 неприменим — заменить в одиночку нельзя.
    """
    return hashlib.md5(raw.encode("utf-8")).hexdigest()  # noqa: S324


def _amount(product: Product) -> str:
    """Сумма строкой с двумя знаками — Robokassa требует формат ``123.45``."""
    return f"{Decimal(product.rub_amount):.2f}"


def build_receipt(product: Product) -> str:
    """Фискальный чек одной позицией.

    Для самозанятого ставка НДС — «без НДС», система налогообложения не
    передаётся: у плательщика НПД её нет.
    """
    receipt = {
        "items": [
            {
                "name": product.title[:128],
                "quantity": 1,
                "sum": float(_amount(product)),
                "payment_method": "full_payment",
                "payment_object": "service",
                "tax": TAX_NONE,
            }
        ]
    }
    # Минифицированный JSON: пробелы изменили бы подпись.
    return json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))


def build_payment_url(product: Product, inv_id: int, email: str | None = None) -> str:
    """Ссылка на страницу оплаты.

    :param product: позиция каталога
    :param inv_id: числовой номер счёта, уникальный в пределах магазина
    :param email: почта плательщика — Robokassa пришлёт на неё чек
    :returns: абсолютный URL, на который нужно отправить пользователя
    :raises RobokassaError: если ключи магазина не настроены
    """
    if not is_configured():
        raise RobokassaError("Robokassa не настроена: заполни ключи в .env")

    s = get_settings()
    out_sum = _amount(product)
    receipt = build_receipt(product)

    # Порядок полей в подписи задан Robokassa и нарушать его нельзя:
    # MerchantLogin:OutSum:InvId:Receipt:Пароль#1:Shp_-параметры по алфавиту.
    shp = {"Shp_code": product.code}
    shp_part = "".join(f":{k}={v}" for k, v in sorted(shp.items()))
    signature = _hash(
        f"{s.robokassa_login}:{out_sum}:{inv_id}:{receipt}:{s.robokassa_password1}{shp_part}"
    )

    params = {
        "MerchantLogin": s.robokassa_login,
        "OutSum": out_sum,
        "InvId": str(inv_id),
        "Description": product.title[:100],
        "SignatureValue": signature,
        "Culture": "ru",
        "Encoding": "utf-8",
        # Чек уходит url-encoded, но в подпись он входит в исходном виде.
        "Receipt": quote(receipt, safe=""),
        **shp,
    }
    if email:
        params["Email"] = email
    if s.robokassa_test_mode:
        params["IsTest"] = "1"

    return f"{PAYMENT_URL}?{urlencode(params, safe=':{}[],"')}"


def verify_result(out_sum: str, inv_id: str, signature: str, shp: dict[str, str]) -> bool:
    """Проверяет подпись уведомления об оплате (ResultURL).

    Считается на Пароле №2 — тем самым, который знает только сервер. Порядок:
    ``OutSum:InvId:Пароль#2`` плюс Shp_-параметры по алфавиту.

    :returns: True, если подпись совпала. При False уведомление игнорируем —
        это либо чужой запрос, либо подделка.
    """
    s = get_settings()
    shp_part = "".join(f":{k}={v}" for k, v in sorted(shp.items()))
    expected = _hash(f"{out_sum}:{inv_id}:{s.robokassa_password2}{shp_part}")
    ok = expected.lower() == signature.lower()
    if not ok:
        logger.warning("подпись Robokassa не совпала: inv_id=%s", inv_id)
    return ok


__all__ = [
    "PAYMENT_URL",
    "RobokassaError",
    "build_payment_url",
    "build_receipt",
    "is_configured",
    "verify_result",
]
