-- =============================================================================
-- migration_add_analysis_cache.sql
-- AI-Based Legal Document Assistant for Small Businesses
--
-- Adds analysis-caching and concurrency-control columns to the documents table.
-- Run ONCE against your PostgreSQL database (safe to re-run — uses IF NOT EXISTS):
--
--   psql -U postgres -d legal_assistant -h localhost -p 5432 \
--        -f migration_add_analysis_cache.sql
-- =============================================================================

BEGIN;

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS extracted_text       TEXT          DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS summary_result       JSONB         DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS clause_result        JSONB         DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS risk_result          JSONB         DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS content_hash         VARCHAR(64)   DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ  DEFAULT NULL;

-- Partial index: fast lookup of cached documents
CREATE INDEX IF NOT EXISTS idx_documents_risk_result_cached
  ON documents (id)
  WHERE risk_result IS NOT NULL;

-- Index for stale-processing detection
CREATE INDEX IF NOT EXISTS idx_documents_processing_started
  ON documents (processing_started_at)
  WHERE status = 'processing';

COMMENT ON COLUMN documents.extracted_text        IS 'Raw text extracted at upload time. Reused by /analyze to avoid disk re-reads.';
COMMENT ON COLUMN documents.summary_result        IS 'Cached JSON from summarize_document() — populated after first successful analysis.';
COMMENT ON COLUMN documents.clause_result         IS 'Cached JSON from extract_clauses() — populated after first successful analysis.';
COMMENT ON COLUMN documents.risk_result           IS 'Cached JSON from detect_risks() — populated after first successful analysis.';
COMMENT ON COLUMN documents.content_hash          IS 'SHA-256 hex of extracted_text. Used to detect file changes that invalidate the analysis cache.';
COMMENT ON COLUMN documents.processing_started_at IS 'UTC timestamp set when status transitions to processing. Used to detect stale/crashed workers.';

COMMIT;

-- Verify all columns are present:
SELECT column_name, data_type, character_maximum_length
FROM   information_schema.columns
WHERE  table_name = 'documents'
ORDER  BY ordinal_position;
