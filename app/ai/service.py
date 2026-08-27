"""CRUD ключей провайдеров. HTTP-запросов здесь нет — только БД и шифрование."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.crypto import KEY_VERSION, decrypt_api_key, encrypt_api_key, key_last4
from app.ai.models import AiCredential
from app.ai.providers import CUSTOM_KEY, get_provider


class UnknownProvider(Exception):
    """Провайдер отсутствует в справочнике или данные для него неполные."""


def _check_public_url(url: str) -> None:
    """Адрес своего провайдера должен вести наружу, а не внутрь сервера.

    Поле «свой провайдер» — это адрес, по которому наш сервер потом сам ходит
    с ключом пользователя. Без проверки его можно навести на внутреннюю сеть
    (SSRF): панель хостинга, соседний сервис, роутер. Ответы у нас
    различаются по коду, так что это ещё и сканер.

    Резолвим имя и отбрасываем всё, что не публичный адрес. Гонка
    «резолв→запрос» тут возможна, но для нашей модели угроз (школьник с
    формой в настройках) этого достаточно.
    """
    host = urlparse(url).hostname
    if not host:
        raise UnknownProvider("не разобрал адрес API")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise UnknownProvider("не удалось разобрать имя хоста в адресе API") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnknownProvider("этот адрес ведёт во внутреннюю сеть — так нельзя")


async def get_credential(session: AsyncSession, user_id: UUID) -> AiCredential | None:
    result = await session.execute(select(AiCredential).where(AiCredential.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_credential(
    session: AsyncSession,
    user_id: UUID,
    *,
    provider: str,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
) -> AiCredential:
    """Создать или заменить ключ пользователя.

    Для известного провайдера адрес и модель берутся из справочника, если не
    заданы явно. Для «custom» и то и другое обязательно.
    """
    known = get_provider(provider)
    if known is None:
        raise UnknownProvider(f"неизвестный провайдер: {provider}")

    resolved_url = (base_url or known.base_url).strip()
    resolved_model = (model or known.default_model).strip()
    if provider == CUSTOM_KEY and (not resolved_url or not resolved_model):
        raise UnknownProvider("для своего провайдера нужны адрес API и название модели")
    if not resolved_url.startswith("https://"):
        raise UnknownProvider("адрес API должен начинаться с https://")
    if provider == CUSTOM_KEY:
        _check_public_url(resolved_url)

    existing = await get_credential(session, user_id)
    if existing is None:
        existing = AiCredential(user_id=user_id)
        session.add(existing)

    existing.provider = provider
    existing.base_url = resolved_url
    existing.model = resolved_model
    existing.key_ciphertext = encrypt_api_key(api_key)
    existing.key_version = KEY_VERSION
    existing.key_last4 = key_last4(api_key)
    await session.commit()
    await session.refresh(existing)
    return existing


async def delete_credential(session: AsyncSession, user_id: UUID) -> bool:
    """Удалить ключ. True, если было что удалять."""
    result = await session.execute(delete(AiCredential).where(AiCredential.user_id == user_id))
    await session.commit()
    # rowcount не объявлен в типах Result, хотя есть у CursorResult — как в
    # app/reminders/service.py:81.
    return bool(getattr(result, "rowcount", 0) or 0)


async def resolve_secret(session: AsyncSession, user_id: UUID) -> tuple[str, str, str] | None:
    """Данные для запроса к провайдеру: (base_url, api_key, model).

    Возвращает расшифрованный ключ — вызывающий обязан не логировать его и
    не отдавать наружу.
    """
    cred = await get_credential(session, user_id)
    if cred is None:
        return None
    return cred.base_url, decrypt_api_key(cred.key_ciphertext, cred.key_version), cred.model
