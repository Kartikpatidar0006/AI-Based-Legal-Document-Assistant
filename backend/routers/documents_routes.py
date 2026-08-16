"""
backend/routers/documents_routes.py
AI-Based Legal Document Assistant for Small Businesses

Document management endpoints:
    POST /documents/upload              — upload a file, extract text, create DB record
    POST /documents/{document_id}/analyze — run full AI analysis, persist risk_flags
    GET  /documents                     — list current user's documents
    GET  /documents/{document_id}       — document detail + persisted risk flags

Design principle: keep handlers thin.
Business logic lives in document_ingest.py + document_processor.py.
Routes: validate → call AI pipeline → persist → return.

NOTE on /analyze performance:
    full_document_analysis() makes multiple sequential Gemini API calls and can
    take 15–60 seconds depending on document length and model latency.
    For this academic project scope, the call is synchronous (blocking).
    In a production system the /analyze call would be submitted to a background
    task queue (e.g. Celery + Redis or FastAPI BackgroundTasks) and the client
    would poll a status endpoint — add that as a future enhancement.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, get_db
from backend.models import Document, RiskFlag, User
from backend.schemas import (
    AnalyzeResponse,
    DocumentDetailResponse,
    DocumentListItem,
    DocumentUploadResponse,
    RiskFlagResponse,
)

# ── Pipeline imports ──────────────────────────────────────────────────────────
# Imported at module level so import errors surface on startup, not mid-request
import sys
import os

# Ensure project root is on sys.path so we can import top-level modules
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from document_ingest import extract_text          # PDF/DOCX/Image → text dict
from document_processor import full_document_analysis  # summarize + clauses + risks

# ── Upload folder ──────────────────────────────────────────────────────────────
UPLOADS_DIR = _PROJECT_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ── POST /documents/upload ────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a legal document",
    description=(
        "Upload a PDF, DOCX, or image file. The system extracts text immediately. "
        "Call /documents/{id}/analyze separately to run AI analysis (takes longer)."
    ),
)
def upload_document(
    file: UploadFile = File(..., description="PDF, DOCX, JPG, PNG, or TIFF file"),
    document_type: str | None = Form(
        None,
        description="e.g. 'Employment Contract', 'NDA', 'Rental Agreement'",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    """
    Upload flow:
        1. Save file to uploads/ with a UUID-prefixed name (avoids collisions).
        2. Extract text via document_ingest.extract_text().
        3. Insert documents row (status='pending').
        4. Return lightweight response — no Gemini calls here.
    """
    # ── 1. Validate file extension ─────────────────────────────────────────────
    allowed_suffixes = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tiff", ".bmp"}
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()

    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Allowed: {', '.join(sorted(allowed_suffixes))}"
            ),
        )

    # ── 2. Save file with unique name ──────────────────────────────────────────
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    save_path = UPLOADS_DIR / unique_name

    try:
        contents = file.file.read()
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        save_path.write_bytes(contents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {exc}",
        )
    finally:
        file.file.close()

    # ── 3. Extract text ────────────────────────────────────────────────────────
    try:
        ingest_result = extract_text(save_path)
    except Exception as exc:
        # Clean up saved file on extraction failure
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text extraction failed: {exc}",
        )

    # ── 4. Persist document record ─────────────────────────────────────────────
    doc = Document(
        user_id=current_user.id,
        filename=original_name,
        document_type=document_type,
        file_path=str(save_path),
        status="pending",
    )
    try:
        db.add(doc)
        db.flush()  # get doc.id before commit
    except Exception as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating document record: {exc}",
        )

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        status=doc.status,
        char_count=ingest_result.get("char_count", 0),
        extraction_method=ingest_result.get("extraction_method", "unknown"),
        extraction_warnings=ingest_result.get("warnings", []),
        upload_date=doc.upload_date,
    )


# ── POST /documents/{document_id}/analyze ─────────────────────────────────────

@router.post(
    "/{document_id}/analyze",
    response_model=AnalyzeResponse,
    summary="Run AI analysis on an uploaded document",
    description=(
        "Runs summarization, clause extraction, and RAG-grounded risk detection. "
        "This endpoint makes multiple Gemini API calls — expect 15–60 seconds "
        "depending on document size. Risk flags are persisted to the database."
    ),
)
def analyze_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyzeResponse:
    """
    Analysis flow:
        1. Fetch document row, enforce ownership.
        2. Re-extract text from saved file.
        3. Run full_document_analysis() (summarize + clauses + risks).
        4. Persist each risk flag as a risk_flags row.
        5. Update document status to 'ready'.
        6. Return full analysis result.
    """
    # ── 1. Fetch & authorise ───────────────────────────────────────────────────
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # ── 2. Extract text from file ──────────────────────────────────────────────
    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Uploaded file not found on disk: {doc.file_path}",
        )

    try:
        ingest_result = extract_text(file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text extraction failed: {exc}",
        )

    document_text = ingest_result.get("text", "")
    if not document_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from this document. It may be corrupted or blank.",
        )

    # Mark as processing before Gemini calls
    doc.status = "processing"
    db.flush()

    # ── 3. Run AI analysis ─────────────────────────────────────────────────────
    # NOTE: This is synchronous and will block the request thread for 15–60s.
    # Production upgrade path: use FastAPI BackgroundTasks or a Celery queue
    # so the client receives an immediate job_id and polls for completion.
    try:
        analysis = full_document_analysis(
            document_text=document_text,
            filename=doc.filename,
            document_type=doc.document_type,
        )
    except Exception as exc:
        doc.status = "error"
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis pipeline failed: {exc}",
        )

    # ── 4. Persist risk flags ──────────────────────────────────────────────────
    # Delete any previously persisted flags for this document (idempotent re-analyze)
    db.query(RiskFlag).filter(RiskFlag.document_id == doc.id).delete()

    flagged_issues = analysis.get("risk_result", {}).get("flagged_issues", [])
    persisted_count = 0

    for issue in flagged_issues:
        if not isinstance(issue, dict):
            continue

        # db_schema.sql CHECK: risk_level IN ('low','medium','high','critical')
        # document_processor returns 'High'/'Medium'/'Low' — normalise to lowercase
        raw_level = str(issue.get("risk_level", "low")).lower()
        # Map any unexpected value to 'medium' as a safe default
        db_level = raw_level if raw_level in ("low", "medium", "high", "critical") else "medium"

        # clause_text: use issue_description if no specific clause text given
        clause_text = (
            issue.get("clause_text")
            or issue.get("clause_type", "Unknown clause")
        )
        description = issue.get("issue_description", "")
        recommendation = issue.get("recommendation", "")

        # Combine description + recommendation into description field
        # (risk_flags.description is a single TEXT column in db_schema.sql)
        full_description = description
        if recommendation:
            full_description += f"\n\nRecommendation: {recommendation}"

        flag = RiskFlag(
            document_id=doc.id,
            clause_text=clause_text[:2000],       # guard against excessively long text
            risk_level=db_level,
            description=full_description or "No description provided.",
        )
        db.add(flag)
        persisted_count += 1

    # ── 5. Update document status ──────────────────────────────────────────────
    doc.status = "ready"
    db.flush()

    return AnalyzeResponse(
        filename=analysis.get("filename", doc.filename),
        summary_result=analysis.get("summary_result", {}),
        clause_result=analysis.get("clause_result", {}),
        risk_result=analysis.get("risk_result", {}),
        risks_persisted=persisted_count,
    )


# ── GET /documents ────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[DocumentListItem],
    summary="List all documents for the current user",
)
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentListItem]:
    """Return all documents owned by the authenticated user, newest first."""
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )
    return [DocumentListItem.model_validate(d) for d in docs]


# ── GET /documents/{document_id} ──────────────────────────────────────────────

@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get full document details including risk flags",
)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentDetailResponse:
    """
    Return one document with its persisted risk_flags rows.
    Enforces ownership — 403 if document belongs to another user.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    flags = (
        db.query(RiskFlag)
        .filter(RiskFlag.document_id == doc.id)
        .order_by(RiskFlag.id)
        .all()
    )

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        upload_date=doc.upload_date,
        status=doc.status,
        file_path=doc.file_path,
        risk_flags=[RiskFlagResponse.model_validate(f) for f in flags],
    )
