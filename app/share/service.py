"""Read-only progress-share links — signed tokens, no DB row, no schema.

A user signs their own id into a URL-safe token; anyone holding the resulting
link can view a read-only snapshot of that user's day. Mirrors the
email-verification token pattern in `app.auth.security`. Because the payload is
self-contained there is no table to migrate — which keeps prod deploys (no
auto-migrations) safe.

Trade-off: the link is a bearer token (whoever has the URL can view). It only
exposes task titles + progress, never credentials. It does not expire in v1; the
serializer is timed so an expiry / revocation can be layered on later.
"""

from uuid import UUID

from itsdangerous import BadData, URLSafeTimedSerializer

from app.config import get_settings

# Share links are bearer tokens with no DB row to revoke, so cap their lifetime:
# a leaked link stops working after this window instead of living forever.
SHARE_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 90  # 90 days


class InvalidShareToken(Exception):
    """Raised when a progress-share token is malformed, tampered with, or expired."""


def _serializer() -> URLSafeTimedSerializer:
    # `salt` namespaces this token kind apart from email-verify tokens.
    return URLSafeTimedSerializer(get_settings().app_secret_key, salt="progress-share")


def make_progress_token(user_id: UUID) -> str:
    return _serializer().dumps(str(user_id))


def read_progress_token(token: str) -> UUID:
    try:
        loaded = _serializer().loads(token, max_age=SHARE_TOKEN_MAX_AGE_SECONDS)
    except BadData as exc:
        raise InvalidShareToken(str(exc)) from exc
    if not isinstance(loaded, str):
        raise InvalidShareToken("token payload is not a string")
    try:
        return UUID(loaded)
    except ValueError as exc:
        raise InvalidShareToken("token payload is not a uuid") from exc


def _group_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().app_secret_key, salt="group-progress")


def make_group_token(project_id: UUID) -> str:
    """Sign a project (class) id into a public read-only group-progress link."""
    return _group_serializer().dumps(str(project_id))


def read_group_token(token: str) -> UUID:
    try:
        loaded = _group_serializer().loads(token, max_age=SHARE_TOKEN_MAX_AGE_SECONDS)
    except BadData as exc:
        raise InvalidShareToken(str(exc)) from exc
    if not isinstance(loaded, str):
        raise InvalidShareToken("token payload is not a string")
    try:
        return UUID(loaded)
    except ValueError as exc:
        raise InvalidShareToken("token payload is not a uuid") from exc


def display_name_from_email(email: str) -> str:
    """A friendly first-name-ish label from an email, for the parent's view.

    `ivan.petrov@x.ru` → `Ivan`. Falls back to the whole email if empty.
    """
    local = email.split("@", 1)[0]
    parts = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
    if not parts:
        return email
    first = parts[0]
    return first[:1].upper() + first[1:]
