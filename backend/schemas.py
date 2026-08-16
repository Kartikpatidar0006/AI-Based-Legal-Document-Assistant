"""
backend/schemas.py
AI-Based Legal Document Assistant for Small Businesses

Pydantic v2 request/response models for all API endpoints.
These are intentionally separate from SQLAlchemy ORM models (models.py)
— ORM models are for DB operations, Pydantic models are for API I/O.

Naming convention:
  <Entity>Create   → request body for POST (create)
  <Entity>Response → response body (never includes password_hash)
  <Entity>Login    → login-specific request
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Request body for POST /auth/register"""
    name:          str = Field(..., min_length=1, max_length=255, examples=["Amit Sharma"])
    email:         EmailStr = Field(..., examples=["amit@mybusiness.com"])
    password:      str = Field(..., min_length=8, examples=["SecurePass123"])
    business_name: str | None = Field(None, max_length=255, examples=["Sharma Traders"])


class UserLogin(BaseModel):
    """Request body for POST /auth/login"""
    email:    EmailStr = Field(..., examples=["amit@mybusiness.com"])
    password: str = Field(..., examples=["SecurePass123"])


class UserResponse(BaseModel):
    """User details returned in API responses — no password_hash ever."""
    id:            uuid.UUID
    name:          str
    email:         str
    business_name: str | None
    created_at:    datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token + user info returned after register/login."""
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    """Response for POST /documents/upload — fast, no Gemini calls."""
    id:                  uuid.UUID
    filename:            str
    document_type:       str | None
    status:              str
    char_count:          int
    extraction_method:   str
    extraction_warnings: list[str]
    upload_date:         datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """One item in GET /documents list response."""
    id:            uuid.UUID
    filename:      str
    document_type: str | None
    upload_date:   datetime
    status:        str

    model_config = {"from_attributes": True}


class RiskFlagResponse(BaseModel):
    """One persisted risk flag row."""
    id:          int
    clause_text: str
    risk_level:  str
    description: str

    model_config = {"from_attributes": True}


class DocumentDetailResponse(BaseModel):
    """GET /documents/{id} — full document info with persisted risk flags."""
    id:            uuid.UUID
    filename:      str
    document_type: str | None
    upload_date:   datetime
    status:        str
    file_path:     str
    risk_flags:    list[RiskFlagResponse]

    model_config = {"from_attributes": True}


class AnalyzeResponse(BaseModel):
    """
    POST /documents/{id}/analyze — full analysis result.
    Mirrors the shape returned by document_processor.full_document_analysis().
    Using dict/Any for the nested results since their schemas are defined
    entirely by the AI pipeline and vary per document.
    """
    filename:       str
    summary_result: dict[str, Any]
    clause_result:  dict[str, Any]
    risk_result:    dict[str, Any]
    risks_persisted: int  # number of rows inserted into risk_flags


# ─────────────────────────────────────────────────────────────────────────────
# QUERY (General KB Q&A)
# ─────────────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Request body for POST /query"""
    question:        str = Field(
        ..., min_length=3,
        examples=["What is the GST registration process for small businesses?"]
    )
    category_filter: str | None = Field(
        None,
        examples=["compliance_docs"],
        description="Optional: restrict retrieval to 'templates', 'compliance_docs', or 'sample_contracts'",
    )
    top_k: int = Field(
        default=5, ge=1, le=20,
        description="Number of KB chunks to retrieve (1–20).",
    )


class SourceItem(BaseModel):
    """One retrieved source document in the Q&A response."""
    filename:         str
    category:         str
    similarity_score: float


class QueryResponse(BaseModel):
    """Response for POST /query"""
    query:       str
    answer:      str
    sources:     list[SourceItem]
    chunks_used: int
    model:       str


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
