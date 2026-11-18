"""
backend/database.py
AI-Based Legal Document Assistant for Small Businesses

SQLAlchemy engine + session factory.

Reads DATABASE_URL from .env (or environment).
All ORM models inherit from Base defined here.

Usage in other modules:
    from backend.database import SessionLocal, engine, Base
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ── Load .env from the project root (environment variables take precedence) ───
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH, override=False)
else:
    load_dotenv(override=False)

# ── Read DATABASE_URL strictly from environment ──────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL not set in environment.\n"
        "Please configure DATABASE_URL in your environment variables."
    )

# Fix for SQLAlchemy requiring postgresql:// instead of legacy postgres:// scheme
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Ensure Neon serverless PostgreSQL connection includes sslmode=require
if "neon.tech" in DATABASE_URL and "sslmode=" not in DATABASE_URL:
    delimiter = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{delimiter}sslmode=require"

# ── SQLAlchemy engine ─────────────────────────────────────────────────────────
# pool_pre_ping=True: test connections before using them, avoids stale-connection errors
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

# ── Session factory ───────────────────────────────────────────────────────────
# autocommit=False + autoflush=False: explicit transaction control (safer for APIs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Declarative base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this base class."""
    pass
