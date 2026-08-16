"""
backend/routers/query_routes.py
AI-Based Legal Document Assistant for Small Businesses

General knowledge-base Q&A endpoint:
    POST /query  — answer a legal question using RAG (no document upload needed)

Uses rag_pipeline.answer_query() which retrieves relevant chunks from the
ChromaDB knowledge base (templates, compliance_docs, sample_contracts) and
generates a grounded answer via Gemini API.

Conversation is persisted to chat_history table for later review.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, get_db
from backend.models import ChatHistory, User
from backend.schemas import QueryRequest, QueryResponse, SourceItem

# Import rag_pipeline from project root (sys.path adjusted in documents_routes.py
# on the same process, but we import here for explicit clarity)
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rag_pipeline import answer_query  # RAG pipeline public function

router = APIRouter(prefix="/query", tags=["Knowledge Base Q&A"])


# ── POST /query ───────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=QueryResponse,
    summary="Ask a legal question against the knowledge base",
    description=(
        "Submit a natural language question. The system retrieves the most "
        "relevant chunks from the legal knowledge base (templates, compliance docs, "
        "sample contracts) and generates a grounded, cited answer via Gemini AI. "
        "Conversation is saved to chat history."
    ),
)
def ask_query(
    body: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    """
    Query flow:
        1. Call rag_pipeline.answer_query() — retrieves chunks + generates answer.
        2. Persist the Q&A to chat_history (document_id=NULL for general queries).
        3. Return structured response.
    """
    # ── 1. Run RAG Q&A pipeline ────────────────────────────────────────────────
    try:
        rag_result = answer_query(
            query=body.question,
            top_k=body.top_k,
            category_filter=body.category_filter,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG pipeline error: {exc}",
        )

    answer_text: str = rag_result.get("answer", "")
    if not answer_text:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG pipeline returned an empty answer.",
        )

    # ── 2. Persist to chat_history ─────────────────────────────────────────────
    # document_id is NULL — this is a general KB query, not about one specific doc
    history_entry = ChatHistory(
        user_id=current_user.id,
        document_id=None,
        query=body.question,
        response=answer_text,
    )
    try:
        db.add(history_entry)
        db.flush()
    except Exception as exc:
        # Log but don't fail the request — the answer is more important than persistence
        print(f"  ⚠️  Failed to persist chat_history entry: {exc}")

    # ── 3. Build response ──────────────────────────────────────────────────────
    sources = [
        SourceItem(
            filename=s.get("filename", "unknown"),
            category=s.get("category", "unknown"),
            similarity_score=float(s.get("similarity_score", 0.0)),
        )
        for s in rag_result.get("sources", [])
    ]

    return QueryResponse(
        query=rag_result.get("query", body.question),
        answer=answer_text,
        sources=sources,
        chunks_used=rag_result.get("chunks_used", 0),
        model=rag_result.get("model", "unknown"),
    )
