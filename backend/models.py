"""
backend/models.py
AI-Based Legal Document Assistant for Small Businesses

SQLAlchemy ORM models — mirror db_schema.sql exactly (column names, types,
constraints, FK relationships).  Six tables:

  User            → users
  Document        → documents
  DocumentChunk   → document_chunks
  ComplianceKB    → compliance_kb
  RiskFlag        → risk_flags
  ChatHistory     → chat_history

NOTE: db_schema.sql must be applied to PostgreSQL first via:
    psql -U <user> -d <database> -f db_schema.sql
These models are kept in sync so SQLAlchemy can query the schema, but the
source of truth for DDL is db_schema.sql, not metadata.create_all().
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: users
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    """
    Mirrors:  users(id, name, email, password_hash, business_name, created_at)
    UUID primary key generated in Python (consistent with gen_random_uuid() in SQL).
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships (back-populates for ORM convenience; not strictly required by routes)
    documents:    Mapped[list["Document"]]    = relationship("Document",    back_populates="user",    cascade="all, delete-orphan")
    chat_history: Mapped[list["ChatHistory"]] = relationship("ChatHistory", back_populates="user",    cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: documents
# ─────────────────────────────────────────────────────────────────────────────

class Document(Base):
    """
    Mirrors:  documents(id, user_id, filename, document_type, upload_date,
                         file_path, status)
    status CHECK: pending | processing | ready | error
    """
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'error')",
            name="documents_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)

    # Relationships
    user:             Mapped["User"]               = relationship("User",          back_populates="documents")
    chunks:           Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    risk_flags:       Mapped[list["RiskFlag"]]      = relationship("RiskFlag",      back_populates="document", cascade="all, delete-orphan")
    chat_history:     Mapped[list["ChatHistory"]]   = relationship("ChatHistory",   back_populates="document")

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename!r} status={self.status!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: document_chunks
# ─────────────────────────────────────────────────────────────────────────────

class DocumentChunk(Base):
    """
    Mirrors:  document_chunks(id, document_id, chunk_text, embedding_id, chunk_index)
    BigSerial PK (integer auto-increment).
    embedding_id links to the ChromaDB chunk_id for vector lookup.
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_index: Mapped[int] = mapped_column(nullable=False)

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: compliance_kb
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceKB(Base):
    """
    Mirrors:  compliance_kb(id, topic, content, source, category)
    Curated knowledge base; populated via db_schema.sql or admin scripts.
    Not directly written by the API routes (read-only from the API's perspective).
    """
    __tablename__ = "compliance_kb"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<ComplianceKB id={self.id} topic={self.topic!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: risk_flags
# ─────────────────────────────────────────────────────────────────────────────

class RiskFlag(Base):
    """
    Mirrors:  risk_flags(id, document_id, clause_text, risk_level, description)
    risk_level CHECK: low | medium | high | critical  (all lowercase in DB schema)
    Written by /documents/{id}/analyze after detect_risks() returns.
    """
    __tablename__ = "risk_flags"
    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="risk_flags_risk_level_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="risk_flags")

    def __repr__(self) -> str:
        return f"<RiskFlag id={self.id} doc={self.document_id} level={self.risk_level!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# TABLE: chat_history
# ─────────────────────────────────────────────────────────────────────────────

class ChatHistory(Base):
    """
    Mirrors:  chat_history(id, user_id, document_id, query, response, timestamp)
    document_id is nullable: general KB queries have no associated document.
    """
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    # Relationships
    user:     Mapped["User"]           = relationship("User",     back_populates="chat_history")
    document: Mapped["Document | None"] = relationship("Document", back_populates="chat_history")

    def __repr__(self) -> str:
        return f"<ChatHistory id={self.id} user={self.user_id}>"
