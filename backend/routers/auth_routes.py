"""
backend/routers/auth_routes.py
AI-Based Legal Document Assistant for Small Businesses

Authentication endpoints:
    POST /auth/register  — create new user account, return JWT
    POST /auth/login     — verify credentials, return JWT
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import create_access_token, hash_password, verify_password
from backend.dependencies import get_db
from backend.models import User
from backend.schemas import TokenResponse, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Create a new small-business user account. "
        "Returns a JWT access token so the user is immediately logged in."
    ),
)
def register(body: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Register flow:
        1. Check email is not already taken.
        2. Hash the password (bcrypt).
        3. Insert into users table.
        4. Generate and return a JWT.
    """
    # Check for duplicate email BEFORE hashing (faster fail path)
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{body.email}' already exists.",
        )

    new_user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        business_name=body.business_name,
    )

    try:
        db.add(new_user)
        db.flush()  # assigns id + triggers DB constraints; commit happens in get_db()
    except IntegrityError:
        # Race condition: another request registered the same email concurrently
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already registered.",
        )

    token = create_access_token(data={"sub": str(new_user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(new_user),
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    description="Verify credentials and return a JWT access token.",
)
def login(body: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Login flow:
        1. Look up user by email.
        2. Verify bcrypt password hash.
        3. Return JWT.
    Uses a deliberate generic error message to avoid leaking whether
    the email exists (prevents user enumeration attacks).
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Unified error: don't distinguish "email not found" from "wrong password"
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )
