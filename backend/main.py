"""
backend/main.py
AI-Based Legal Document Assistant for Small Businesses

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

import sys
from pathlib import Path

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

app.add_middleware(
    CORSMiddleware,
    # Local development: allow all origins so the React dev server
    # (any port) can reach the API without preflight rejections.
    # Restrict this to specific domains before deploying to production.
    allow_origins=["*"],
    allow_credentials=False,   # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP EVENT
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup() -> None:
    """
    Safety-net: create any tables that don't exist yet.

    IMPORTANT: db_schema.sql is the source of truth for the schema.
    Run it manually with:
        psql -U <user> -d <database> -f db_schema.sql
    This create_all() is only a convenience fallback for local development
    so you don't have to run psql before the first uvicorn launch.
    It will NOT alter or drop existing tables — purely additive.
    """
    try:
        # Import all models so Base.metadata knows about them
        import backend.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables verified / created.")
    except Exception as exc:
        print(f"⚠️  Database startup check failed: {exc}")
        print("   Make sure PostgreSQL is running and DATABASE_URL in .env is correct.")


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
