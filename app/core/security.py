import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, Cookie
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from starlette import status
from app.core.config import settings

# === Config ===
JWT_SECRET = settings.jwt_secret
JWT_ALG = "HS256"

ACCESS_MINUTES = int(settings.access_token_minutes)
REFRESH_DAYS = int(settings.refresh_token_days)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_http_bearer = HTTPBearer(auto_error=False)

# === Core ===
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def create_verify_token(user_id: int, email: str, minutes: int = 30) -> str:
    now = _now_utc()
    payload = {
        "sub": str(user_id),
        "email": email,
        "typ": "verify",
        "iat": _ts(now),
        "exp": _ts(now + timedelta(minutes=minutes)),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_access_token(user_id: int, email: str, minutes: Optional[int] = None) -> str:
    """JWT corto para llamadas al API."""
    minutes = minutes or ACCESS_MINUTES
    now = _now_utc()
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "typ": "access",
        "iat": _ts(now),
        "exp": _ts(now + timedelta(minutes=minutes)),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_refresh_token(user_id: int, email: str, days: Optional[int] = None) -> str:
    """Opcional: úsalo si luego implementas /auth/refresh."""
    days = days or REFRESH_DAYS
    now = _now_utc()
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "typ": "refresh",
        "iat": _ts(now),
        "exp": _ts(now + timedelta(days=days)),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    """Lanza excepciones jwt si está expirado o es inválido."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


# === Helpers opcionales ===
def require_token_type(data: dict, expected: str) -> dict:
    """Asegura que el 'typ' del token sea el esperado."""
    typ = data.get("typ")
    if typ != expected:
        raise jwt.InvalidTokenError(f"Invalid token type: {typ}, expected: {expected}")
    return data


def get_bearer_from_auth_header(authorization: Optional[str]) -> Optional[str]:
    """Extrae 'Bearer <token>' de un header Authorization."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_password_hash(password: str) -> str:
    """Devuelve el hash bcrypt del password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si el password en texto plano coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_current_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> dict:
    """Valida Authorization: Bearer <access_token> y devuelve los claims."""
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = creds.credentials
    try:
        data = decode_token(token)
        require_token_type(data, "access")
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_token_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> dict | None:
    """
    Intenta leer y validar Authorization: Bearer <access_token>.
    Si no hay token o es inválido/expirado, devuelve None (no levanta 401).
    """
    if not creds or not creds.credentials:
        return None
    token = creds.credentials
    try:
        data = decode_token(token)
        require_token_type(data, "access")
        return data
    except Exception:
        return None


def get_current_token_cookie_or_header(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    access_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> dict:
    """
    Intenta primero Bearer, si no hay, cae a la cookie 'access_token'.
    """
    token = None
    if creds and creds.credentials:
        token = creds.credentials
    elif access_cookie:
        token = access_cookie

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        data = decode_token(token)
        require_token_type(data, "access")
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_token_optional_cookie_or_header(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    access_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> dict | None:
    """
    Versión opcional: devuelve None si no hay token o si es inválido/expirado.
    """
    token = None
    if creds and creds.credentials:
        token = creds.credentials
    elif access_cookie:
        token = access_cookie
    if not token:
        return None
    try:
        data = decode_token(token)
        require_token_type(data, "access")
        return data
    except Exception:
        return None