-- =============================================================================
-- db_schema.sql
-- AI-Based Legal Document Assistant for Small Businesses
-- PostgreSQL Database Schema
--
-- This script creates all tables required by the backend API.
-- Run once on a fresh database:
--     psql -U <username> -d <database_name> -f db_schema.sql
--
-- Tables:
--   users           → registered small-business users
--   documents       → uploaded legal documents per user
--   document_chunks → chunked text of each document (links to vector DB)
--   compliance_kb   → curated compliance knowledge base (GST, MSME, etc.)
--   risk_flags      → risky/missing clauses detected in a document
--   chat_history    → conversation log for the AI assistant
-- =============================================================================


-- ---------------------------------------------------------------------------
-- EXTENSIONS
-- ---------------------------------------------------------------------------
-- pgcrypto gives us gen_random_uuid() for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ---------------------------------------------------------------------------
-- TABLE: users
-- Stores registered users (small business owners).
-- Each user has a unique email address and may own multiple documents.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255)  NOT NULL,
    email         VARCHAR(255)  NOT NULL UNIQUE,        -- login identifier
    password_hash VARCHAR(255)  NOT NULL,               -- bcrypt/argon2 hash — NEVER store plaintext
    business_name VARCHAR(255),                         -- optional: name of the small business
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()  -- UTC timestamp of registration
);

-- Index: speed up login lookups by email
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

COMMENT ON TABLE  users               IS 'Registered users of the Legal Document Assistant.';
COMMENT ON COLUMN users.password_hash IS 'Hashed password (bcrypt/argon2). Never store raw passwords.';
COMMENT ON COLUMN users.business_name IS 'Optional name of the user''s small business.';


-- ---------------------------------------------------------------------------
-- TABLE: documents
-- Represents a legal document uploaded by a user.
-- After upload, the backend extracts text, chunks it, and updates status.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename      VARCHAR(500)  NOT NULL,              -- original filename as uploaded
    document_type VARCHAR(100),                        -- e.g. NDA, Service Agreement, Rental
    upload_date   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    file_path     TEXT          NOT NULL,              -- path/URL where the file is stored
    status        VARCHAR(50)   NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'processing', 'ready', 'error'))
                                                       -- pipeline stage of this document
);

-- Indexes: most queries filter by user_id; some also filter by status
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status  ON documents (status);

COMMENT ON TABLE  documents               IS 'Legal documents uploaded by users for analysis.';
COMMENT ON COLUMN documents.document_type IS 'High-level type label: NDA, Employment, Rental, etc.';
COMMENT ON COLUMN documents.status        IS 'Tracks pipeline stage: pending → processing → ready | error.';


-- ---------------------------------------------------------------------------
-- TABLE: document_chunks
-- Stores the individual text chunks created during the RAG chunking stage.
-- embedding_id links back to the corresponding vector in ChromaDB (chunk_id).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_chunks (
    id            BIGSERIAL     PRIMARY KEY,
    document_id   UUID          NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text    TEXT          NOT NULL,              -- the raw chunk text
    embedding_id  VARCHAR(255),                        -- ChromaDB chunk_id for vector lookup
    chunk_index   INTEGER       NOT NULL               -- 0-based position within the document
);

-- Index: fast lookup of all chunks belonging to a specific document
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks (document_id);

COMMENT ON TABLE  document_chunks              IS 'Chunked text of uploaded documents; used for RAG retrieval.';
COMMENT ON COLUMN document_chunks.embedding_id IS 'Matching chunk_id in ChromaDB — used to fetch the embedding vector.';
COMMENT ON COLUMN document_chunks.chunk_index  IS '0-based order of this chunk within its parent document.';


-- ---------------------------------------------------------------------------
-- TABLE: compliance_kb
-- A curated knowledge base of Indian compliance regulations.
-- Populated during setup (GST, MSME, Startup India, Labour Law, etc.)
-- This table mirrors the compliance_docs category in the vector DB,
-- giving us a structured, queryable complement to the vector search.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS compliance_kb (
    id         BIGSERIAL     PRIMARY KEY,
    topic      VARCHAR(255)  NOT NULL,                 -- e.g. "GST Registration Basics"
    content    TEXT          NOT NULL,                 -- the regulation text / summary
    source     VARCHAR(500),                           -- origin document filename or URL
    category   VARCHAR(100)                            -- sub-category: tax, labour, startup, etc.
);

-- Index: topic-based lookups (used when surfacing related compliance info)
CREATE INDEX IF NOT EXISTS idx_compliance_kb_category ON compliance_kb (category);
CREATE INDEX IF NOT EXISTS idx_compliance_kb_topic    ON compliance_kb (topic);

COMMENT ON TABLE  compliance_kb          IS 'Curated Indian compliance regulation knowledge base (GST, MSME, etc.).';
COMMENT ON COLUMN compliance_kb.source   IS 'Filename or URL of the original compliance document.';
COMMENT ON COLUMN compliance_kb.category IS 'Broad category: tax | labour | startup | shop_establishment.';


-- ---------------------------------------------------------------------------
-- TABLE: risk_flags
-- Records risky, missing, or unbalanced clauses detected in a document.
-- Populated by the AI risk-review pipeline after document upload.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_flags (
    id           BIGSERIAL     PRIMARY KEY,
    document_id  UUID          NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    clause_text  TEXT          NOT NULL,               -- the exact problematic clause / excerpt
    risk_level   VARCHAR(50)   NOT NULL
                               CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    description  TEXT          NOT NULL                -- human-readable explanation of the risk
);

-- Index: fetch all flags for a given document quickly
CREATE INDEX IF NOT EXISTS idx_risk_flags_document_id  ON risk_flags (document_id);
CREATE INDEX IF NOT EXISTS idx_risk_flags_risk_level   ON risk_flags (risk_level);

COMMENT ON TABLE  risk_flags             IS 'AI-detected risky or missing clauses in uploaded documents.';
COMMENT ON COLUMN risk_flags.risk_level  IS 'Severity: low | medium | high | critical.';
COMMENT ON COLUMN risk_flags.description IS 'Plain-language explanation of why this clause is flagged.';


-- ---------------------------------------------------------------------------
-- TABLE: chat_history
-- Logs every Q&A interaction a user has with the AI assistant.
-- document_id is nullable — some queries are general (not about a specific doc).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_history (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id UUID         REFERENCES documents(id) ON DELETE SET NULL,  -- nullable
    query       TEXT         NOT NULL,                 -- the user's question
    response    TEXT         NOT NULL,                 -- the AI-generated answer
    timestamp   TIMESTAMPTZ  NOT NULL DEFAULT NOW()    -- UTC time of the interaction
);

-- Indexes: retrieve conversation history per user and per document efficiently
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id     ON chat_history (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_document_id ON chat_history (document_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp   ON chat_history (timestamp DESC);

COMMENT ON TABLE  chat_history             IS 'Full conversation log between users and the AI assistant.';
COMMENT ON COLUMN chat_history.document_id IS 'NULL if query is general; set if query is about a specific document.';
COMMENT ON COLUMN chat_history.timestamp   IS 'UTC timestamp; DESC index allows fast "latest messages first" queries.';


-- =============================================================================
-- SCHEMA COMPLETE
-- Verify with:  \dt          (list tables)
--               \d <table>   (describe a table)
-- =============================================================================
