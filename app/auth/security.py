"""Password hashing (argon2) and email-verification tokens (itsdangerous)."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

EMAIL_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 3  # 3 days

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


class InvalidToken(Exception):
    """Raised when an email verification token is malformed or expired."""


def _serializer() -> URLSafeTimedSerializer:
    # `salt` here is itsdangerous's namespace separator, not a cryptographic salt.
    return URLSafeTimedSerializer(get_settings().app_secret_key, salt="email-verify")


def create_email_verification_token(user_id: str) -> str:
    return _serializer().dumps(user_id)


def verify_email_verification_token(
    token: str,
    max_age: int = EMAIL_TOKEN_MAX_AGE_SECONDS,
) -> str:
    try:
        loaded = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired) as exc:
        raise InvalidToken(str(exc)) from exc
    if not isinstance(loaded, str):
        raise InvalidToken("token payload is not a string")
    return loaded
