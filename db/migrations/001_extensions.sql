-- 001: extensions
-- pgvector is used by the RAG pipeline (owner: Mohamed Fathy). Enabled here so
-- the DB is ready for WF-04 later.
CREATE EXTENSION IF NOT EXISTS vector;
