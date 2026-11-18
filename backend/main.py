"""
backend/main.py
# AI-Based Legal Document Assistant for Small Businesses

FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app with metadata
  - Configure CORS for React dev servers (localhost:3000 and localhost:5173)
  - Include all routers with prefixes
  - Startup event: safety-net create_all() for local dev
  - GET /health endpoint

Run server:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs (Swagger UI):
    http://localhost:8000/docs

Alternative docs (ReDoc):
    http://localhost:8000/redoc
"""

import logging
import sys
from pathlib import Path

# ── Configure logging early so all [PERF] / [CACHE] messages are visible ──────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Ensure project root is importable ────────────────────────────────────────
# Required so 'from document_ingest import ...' etc. resolve correctly when
# uvicorn is launched from the project root directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.database import Base, engine
from backend.routers import auth_routes, documents_routes, query_routes
from backend.schemas import HealthResponse

# ─────────────────────────────────────────────────────────────────────────────
# APPLICATION INSTANCE
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI-Based Legal Document Assistant",
    description=(
        "REST API for an AI-powered legal document assistant designed for "
        "small businesses in India.\n\n"
        "**Features:**\n"
        "- Upload legal documents (PDF, DOCX, images)\n"
        "- AI-powered contract summarization, clause extraction, and risk detection\n"
        "- RAG-based Q&A against a curated legal knowledge base\n"
        "- JWT-authenticated user accounts\n\n"
        "**Tech stack:** FastAPI · PostgreSQL · ChromaDB · Google Gemini AI · "
        "Sentence-Transformers · LangChain"
    ),
    version="1.0.0",
    contact={
        "name": "AI Legal Doc Assistant — Major Project",
    },
    license_info={"name": "MIT"},
    # Swagger UI will show an Authorize button linked to the login endpoint
    swagger_ui_parameters={"persistAuthorization": True},
)


# ─────────────────────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────────────────────

# Read allowed origins from ALLOWED_ORIGINS env var (comma-separated), default to http://localhost:5173
import os
raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = ["http://localhost:5173"]

# Allow credentials only when specific origins are configured (disallowed with wildcard "*")
allow_credentials = "*" not in allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP EVENT
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup() -> None:
    """
    Validate environment variables, ensure runtime storage directories exist,
    and initialize database tables.
    """
    # ── 1. Validate required environment variables ────────────────────────────
    missing_vars = []
    if not (os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY")):
        missing_vars.append("SECRET_KEY (or JWT_SECRET_KEY)")
    if not os.getenv("DATABASE_URL"):
        missing_vars.append("DATABASE_URL")
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        missing_vars.append("GEMINI_API_KEY")

    if missing_vars:
        print(f"⚠️  WARNING: Missing required environment variable(s): {', '.join(missing_vars)}")
        print("   Authentication, database, or AI analysis features may fail.")
        print("   Please check your Hugging Face Space secrets or .env configuration.")
    else:
        print("✅ Environment variables verified (SECRET_KEY, DATABASE_URL, GEMINI_API_KEY configured).")

    # ── 2. Ensure upload and ChromaDB paths exist ─────────────────────────────
    uploads_dir = _PROJECT_ROOT / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    vector_db_dir = _PROJECT_ROOT / "data" / "vector_db"
    vector_db_dir.mkdir(parents=True, exist_ok=True)

    audio_cache_dir = _PROJECT_ROOT / "audio_cache"
    audio_cache_dir.mkdir(parents=True, exist_ok=True)
    print("✅ Runtime storage directories verified (uploads/, data/vector_db/, audio_cache/).")

    # ── 3. Database table safety-net ──────────────────────────────────────────
    try:
        # Import all models so Base.metadata knows about them
        import backend.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables verified / created.")
    except Exception as exc:
        print(f"⚠️  Database startup check failed: {exc}")
        print("   Make sure PostgreSQL is running and DATABASE_URL is correct.")


# ─────────────────────────────────────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(auth_routes.router)       # /auth/register, /auth/login
app.include_router(documents_routes.router)  # /documents/*
app.include_router(query_routes.router)      # /query


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Returns {'status': 'ok'} if the API is running.",
)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")
