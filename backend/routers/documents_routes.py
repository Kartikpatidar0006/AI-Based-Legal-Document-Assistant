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

import hashlib
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, get_db
from backend.models import ChatHistory, Document, RiskFlag, User
from backend.schemas import (
    AnalyzeResponse,
    DocumentAskRequest,
    DocumentAskResponse,
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
from document_processor import full_document_analysis, generate_audio_summary, AUDIO_CACHE_DIR, summarize_document  # summarize + clauses + risks + audio
from rag_pipeline import answer_document_query

# ── Upload folder ──────────────────────────────────────────────────────────────
UPLOADS_DIR = _PROJECT_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ── POST /documents/upload ────────────────────────────────────────────────    

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

    # ── 3. Extract text ─────────────────────────────────────────────────
    t_extract_start = time.perf_counter()
    try:
        ingest_result = extract_text(save_path)
    except Exception as exc:
        # Clean up saved file on extraction failure
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text extraction failed: {exc}",
        )
    t_extract = time.perf_counter() - t_extract_start
    extracted_text = ingest_result.get("text", "")
    char_count = ingest_result.get("char_count", len(extracted_text))
    # SHA-256 of extracted text — used to verify cache validity on future analyses
    content_hash = hashlib.sha256(extracted_text.encode("utf-8", errors="replace")).hexdigest() if extracted_text else None
    logger.info(
        "[PERF] upload/extract: %.2fs | char_count=%d | method=%s | sha256=%s | file=%s",
        t_extract, char_count, ingest_result.get("extraction_method", "unknown"),
        (content_hash or "")[:12] + "...", original_name,
    )

    # ── 4. Persist document record ────────────────────────────────────────────
    doc = Document(
        user_id=current_user.id,
        filename=original_name,
        document_type=document_type,
        file_path=str(save_path),
        status="pending",
        extracted_text=extracted_text or None,  # stored for reuse during /analyze
        content_hash=content_hash,
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
        char_count=char_count,
        extraction_method=ingest_result.get("extraction_method", "unknown"),
        extraction_warnings=ingest_result.get("warnings", []),
        upload_date=doc.upload_date,
    )


# ── POST /documents/{document_id}/analyze ────────────────────────────────────

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
    from datetime import timedelta
    STALE_PROCESSING_TIMEOUT = timedelta(minutes=15)

    t_total_start = time.perf_counter()

    # ── 1. Atomic row-lock: SELECT FOR UPDATE ─────────────────────────────
    # with_for_update() issues a Postgres-level row lock inside the current
    # transaction, ensuring that exactly one request can read-then-write the
    # status field at a time. Any concurrent call blocks here until the first
    # transaction commits and its lock is released.
    doc = (
        db.query(Document)
        .filter(Document.id == document_id)
        .with_for_update()            # <── ATOMIC: row is locked until commit
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # ── 2. Stale-processing guard (crashed worker recovery) ───────────────
    # If a previous worker set status=processing but then crashed, the record
    # is stuck forever. We reset it to 'pending' after a timeout so the next
    # request can re-run the pipeline.
    if doc.status == "processing" and doc.processing_started_at is not None:
        now_utc = datetime.now(timezone.utc)
        if now_utc - doc.processing_started_at > STALE_PROCESSING_TIMEOUT:
            logger.warning(
                "[STALE] document_id=%s was stuck in 'processing' since %s — resetting to pending.",
                document_id, doc.processing_started_at.isoformat(),
            )
            doc.status = "pending"
            doc.processing_started_at = None
            db.flush()

    # ── 3. IDEMPOTENCY GUARD ───────────────────────────────────────────
    if (
        doc.status == "ready"
        and doc.summary_result is not None
        and doc.clause_result is not None
        and doc.risk_result is not None
    ):
        elapsed = time.perf_counter() - t_total_start
        logger.info(
            "[CACHE HIT] analyze: document_id=%s returned cached analysis in %.3fs",
            document_id, elapsed,
        )
        persisted_count = db.query(RiskFlag).filter(RiskFlag.document_id == doc.id).count()
        return AnalyzeResponse(
            filename=doc.filename,
            summary_result=doc.summary_result,
            clause_result=doc.clause_result,
            risk_result=doc.risk_result,
            risks_persisted=persisted_count,
        )

    # ── 4. Repair path: status=ready but JSONB blobs are NULL ───────────────
    # This happens if a previous worker crashed after setting status=ready but
    # before flushing the JSONB results. Re-run the pipeline to repair the record.
    if doc.status == "ready" and (
        doc.summary_result is None or doc.clause_result is None or doc.risk_result is None
    ):
        logger.warning(
            "[REPAIR] document_id=%s is status=ready but analysis cache is incomplete — re-running pipeline.",
            document_id,
        )
        doc.status = "pending"   # will transition to processing below
        db.flush()

    # ── 5. Concurrency guard (active in-flight pipeline) ──────────────────
    # Reached only after the SELECT FOR UPDATE — so if we see 'processing' here
    # it means a genuinely concurrent request that started BEFORE our lock.
    if doc.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already in progress for this document. Please wait and try again.",
        )

    # ── 6. Resolve document text (prefer stored; fall back to disk) ─────────
    if doc.extracted_text and doc.extracted_text.strip():
        document_text = doc.extracted_text
        logger.info(
            "[CACHE HIT] extracted_text: reusing stored text for document_id=%s (char_count=%d)",
            document_id, len(document_text),
        )
    else:
        # Fall back: file may exist but text was never cached (e.g. uploaded before migration)
        file_path = Path(doc.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded file not found on disk: {doc.file_path}",
            )
        t_extract_start = time.perf_counter()
        try:
            ingest_result = extract_text(file_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Text extraction failed: {exc}",
            )
        t_extract = time.perf_counter() - t_extract_start
        document_text = ingest_result.get("text", "")
        logger.info(
            "[CACHE MISS] extracted_text: re-extracted from disk in %.2fs (char_count=%d)",
            t_extract, len(document_text),
        )
        # Store for future calls and compute SHA-256 hash
        doc.extracted_text = document_text or None
        if document_text:
            doc.content_hash = hashlib.sha256(
                document_text.encode("utf-8", errors="replace")
            ).hexdigest()
        db.flush()

    if not document_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from this document. It may be corrupted or blank.",
        )

    # Mark as processing and record timestamp for stale-worker detection
    doc.status = "processing"
    doc.processing_started_at = datetime.now(timezone.utc)
    db.flush()

    # ── 5. Run AI analysis with per-step timing ───────────────────────────
    try:
        t_pipeline_start = time.perf_counter()
        analysis = full_document_analysis(
            document_text=document_text,
            filename=doc.filename,
            document_type=doc.document_type,
        )
        t_pipeline = time.perf_counter() - t_pipeline_start
        logger.info(
            "[PERF] full_document_analysis: %.2fs | file=%s | char_count=%d",
            t_pipeline, doc.filename, len(document_text),
        )
    except Exception as exc:
        doc.status = "error"
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis pipeline failed: {exc}",
        )

    # ── 6. Persist analysis results as JSONB ─────────────────────────────
    doc.summary_result = analysis.get("summary_result") or None
    doc.clause_result  = analysis.get("clause_result")  or None
    doc.risk_result    = analysis.get("risk_result")    or None
    db.flush()

    # ── 7. Persist risk flags ─────────────────────────────────────────────
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

    # ── 5. Cache summary text for voice walkthrough & update status ────────────
    summary_text = analysis.get("summary_result", {}).get("summary", "")
    if summary_text:
        try:
            summary_cache_path = AUDIO_CACHE_DIR / f"{doc.id}_summary.txt"
            summary_cache_path.write_text(summary_text, encoding="utf-8")
        except Exception:
            pass

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
        # Return cached analysis blobs so frontend can render without calling /analyze again
        summary_result=doc.summary_result,
        clause_result=doc.clause_result,
        risk_result=doc.risk_result,
    )


# ── GET /documents/{document_id}/audio-summary ────────────────────────────────

@router.get(
    "/{document_id}/audio-summary",
    summary="Get voice audio summary of the document (MP3)",
    description=(
        "Returns an MP3 audio narration of the AI-generated summary. "
        "The document must be analyzed first (/analyze). Uses cached audio "
        "when available for instant playback."
    ),
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "MP3 audio stream of the contract summary.",
        },
        400: {"description": "Document has not been analyzed yet."},
        403: {"description": "Access denied."},
        404: {"description": "Document not found."},
    },
)
def get_audio_summary(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Audio summary flow:
        1. Fetch document and enforce ownership (404 / 403).
        2. Ensure document has been analyzed (status == 'ready'); return 400 if not.
        3. Retrieve stored summary text (from audio_cache/{doc.id}_summary.txt or re-summarize).
        4. Call voice_walkthrough.generate_audio_summary() -> cached/generated Path.
        5. Return FileResponse with media_type="audio/mpeg".
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Must be analyzed before audio can be listened to
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This document has not been analysed yet. Please run analysis first to generate a summary.",
        )

    # Fetch stored summary text
    summary_cache_file = AUDIO_CACHE_DIR / f"{doc.id}_summary.txt"
    summary_text = ""
    if summary_cache_file.exists():
        try:
            summary_text = summary_cache_file.read_text(encoding="utf-8").strip()
        except Exception:
            summary_text = ""

    # Fallback if summary cache file missing for an already-analyzed document:
    # Re-extract and summarize from the document text
    if not summary_text:
        file_path = Path(doc.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document file not found on disk: {doc.file_path}",
            )
        try:
            from document_processor import summarize_document
            ingest_result = extract_text(file_path)
            doc_text = ingest_result.get("text", "")
            if not doc_text.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No readable text in document to summarize.",
                )
            summary_res = summarize_document(doc_text, doc.filename)
            summary_text = summary_res.get("summary", "")
            if summary_text:
                summary_cache_file.write_text(summary_text, encoding="utf-8")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve document summary: {exc}",
            )

    if not summary_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No summary text is available for this document.",
        )

    try:
        audio_path = generate_audio_summary(summary_text, filename_hint=doc.filename)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate audio summary: {exc}",
        )

    # Safe export filename
    clean_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', Path(doc.filename).stem)
    audio_filename = f"{clean_stem}_summary.mp3"

    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=audio_filename,
    )


# ── POST /documents/{id}/ask ──────────────────────────────────────────────────

@router.post(
    "/{document_id}/ask",
    response_model=DocumentAskResponse,
    summary="Ask a question about a specific document",
    description=(
        "Submit a question grounded solely in this document's text (not generic templates). "
        "Answers are generated by Gemini and cited against the document clauses. "
        "Conversation is persisted into chat_history linked to this document_id."
    ),
)
def ask_document(
    document_id: uuid.UUID,
    body: DocumentAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentAskResponse:
    """
    Document-specific Q&A flow:
        1. Fetch document and verify ownership.
        2. Resolve document text: prefer cached doc.extracted_text; fall back to disk extraction.
        3. Call rag_pipeline.answer_document_query().
        4. Persist Q&A to chat_history table with the real document_id.
        5. Return structured response.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    if doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    # Resolve document text (reuse extracted_text if present, else extract from disk)
    document_text = doc.extracted_text
    if not document_text or not document_text.strip():
        file_path = Path(doc.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded file not found on disk: {doc.file_path}",
            )
        try:
            ingest_result = extract_text(file_path)
            document_text = ingest_result.get("text", "")
            if document_text:
                doc.extracted_text = document_text
                doc.content_hash = hashlib.sha256(
                    document_text.encode("utf-8", errors="replace")
                ).hexdigest()
                db.flush()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Text extraction failed: {exc}",
            )

    if not document_text or not document_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from this document to answer questions.",
        )

    # Convert Pydantic chat history models to dicts
    history_dicts = None
    if body.chat_history:
        history_dicts = [
            {"question": turn.question, "answer": turn.answer}
            for turn in body.chat_history
        ]

    # Run document Q&A pipeline
    try:
        qa_result = answer_document_query(
            question=body.question,
            document_text=document_text,
            filename=doc.filename,
            chat_history=history_dicts,
        )
    except Exception as exc:
        logger.exception("answer_document_query failed for doc_id=%s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer for document: {exc}",
        )

    answer_text = qa_result.get("answer", "")

    # Persist to chat_history table with the real document_id
    history_entry = ChatHistory(
        user_id=current_user.id,
        document_id=doc.id,
        query=body.question,
        response=answer_text,
    )
    try:
        db.add(history_entry)
        db.flush()
    except Exception as exc:
        logger.warning("Failed to persist chat_history entry for doc_id=%s: %s", document_id, exc)

    return DocumentAskResponse(
        question=body.question,
        answer=answer_text,
        filename=doc.filename,
        disclaimer=qa_result.get("disclaimer", ""),
    )

