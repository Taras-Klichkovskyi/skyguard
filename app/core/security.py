"""Паролі (argon2id) і JWT-токени."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

ACCESS = "access"
REFRESH = "refresh"

_hasher = PasswordHasher()  # argon2id з параметрами за замовчуванням бібліотеки
# Хеш для порівняння, коли користувача не знайдено: вирівнює час відповіді,
# щоб за ним не можна було вгадати, чи існує такий email.
_DUMMY_HASH = _hasher.hash("skyguard-dummy-password")


class TokenError(Exception):
    """Токен відсутній, прострочений, підроблений або не того типу."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: uuid.UUID, role: str, token_type: str) -> tuple[str, int]:
    """Повертає (токен, час життя в секундах)."""
    settings = get_settings()
    ttl = (
        timedelta(minutes=settings.access_token_ttl_min)
        if token_type == ACCESS
        else timedelta(days=settings.refresh_token_ttl_days)
    )
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_token(token: str, expected_type: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token_invalid") from exc
    if payload.get("type") != expected_type:
        raise TokenError("token_wrong_type")
    try:
        payload["sub"] = uuid.UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise TokenError("token_invalid") from exc
    return payload
