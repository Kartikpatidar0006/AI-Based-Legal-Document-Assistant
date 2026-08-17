"""
backend/dependencies.py
AI-Based Legal Document Assistant for Small Businesses

FastAPI dependencies injected into route handlers via Depends():

    get_db()           → yields a SQLAlchemy Session, commits on success,
                         rolls back on exception, always closes.

    get_current_user() → reads Authorization header via HTTPBearer,
                         verifies JWT, returns the User ORM object.
                         Raises 401 if token is missing/invalid.
                         Raises 404 if the user_id in the token no longer exists.
"""

import uuid
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.auth import decode_access_token
from backend.database import SessionLocal
from backend.models import User

# ── DB session dependency ─────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session for each request.

    Pattern: session is created → request runs → session is committed
             on clean exit, or rolled back on any exception → always closed.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Auth dependency ───────────────────────────────────────────────────────────

# HTTPBearer extracts the raw token from `Authorization: Bearer <token>`.
# Swagger UI's "Authorize" popup will simply ask for the token string,
# avoiding the form-data username/password flow of OAuth2PasswordBearer.
_http_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the JWT and return the authenticated User ORM object.

    The token is extracted from the `Authorization: Bearer <token>` header
    by HTTPBearer.  In Swagger UI, click "Authorize" and paste the
    access_token you received from POST /auth/login.

    Raises:
        HTTPException 401 — token missing, invalid, or expired
        HTTPException 404 — user_id from token no longer in database
    """
    payload = decode_access_token(credentials.credentials)  # raises 401 on failure

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub' claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains invalid user ID format.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found — account may have been deleted.",
        )

    return user
