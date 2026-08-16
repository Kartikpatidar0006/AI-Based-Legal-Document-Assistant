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

# ── Load .env from the project root (one level above backend/) ────────────────
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# ── Read DATABASE_URL ─────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL not set in .env\n"
        "Add a line like:\n"
        "  DATABASE_URL=postgresql://user:password@localhost:5432/legal_doc_db"
    )

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
