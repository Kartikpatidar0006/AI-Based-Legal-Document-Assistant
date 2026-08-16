"""
backend/auth.py
AI-Based Legal Document Assistant for Small Businesses

Password hashing (passlib/bcrypt) and JWT creation/verification (python-jose).

All secrets are read from .env.  Nothing is hardcoded.

Public API:
    hash_password(plain: str) -> str
    verify_password(plain: str, hashed: str) -> bool
    create_access_token(data: dict) -> str
    decode_access_token(token: str) -> dict   # raises HTTPException 401 on failure
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

# ── Load .env ─────────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# ── JWT config ────────────────────────────────────────────────────────────────
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM: str  = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS: int = 24  # tokens last 24 hours

if not JWT_SECRET_KEY:
    raise EnvironmentError(
        "JWT_SECRET_KEY not set in .env\n"
        "Generate one with:  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
        "Then add to .env:   JWT_SECRET_KEY=<the generated value>"
    )

# ── Password hashing ──────────────────────────────────────────────────────────
# bcrypt is the industry-standard adaptive hashing algorithm.
# deprecated="auto" automatically re-hashes old schemes on next login.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return the bcrypt hash of a plaintext password."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT creation ──────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    """
    Create a signed JWT containing `data` payload plus an expiry claim.

    Args:
        data: Dict of claims to encode.  Typically {"sub": str(user.id)}.

    Returns:
        Encoded JWT string (compact serialisation).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ── JWT verification ──────────────────────────────────────────────────────────

def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT.

    Returns:
        The decoded payload dict (includes "sub" and "exp").

    Raises:
        HTTPException 401 if the token is invalid, expired, or tampered with.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials — token is invalid or expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("sub") is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
