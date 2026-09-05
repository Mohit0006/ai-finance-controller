-- 001_init.sql: Idempotent database schema for AutoReconcile AI
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS reconciliation_batches (
    batch_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_bank_records INTEGER NOT NULL,
    total_ledger_records INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('PROCESSING', 'COMPLETED', 'FAILED')
    )
);

CREATE TABLE IF NOT EXISTS ledger_transactions (
    batch_id UUID NOT NULL REFERENCES reconciliation_batches(batch_id)
        ON DELETE CASCADE,
    ledger_id TEXT NOT NULL,
    invoice_id TEXT,
    utr TEXT,
    amount NUMERIC(18, 2) NOT NULL,
    currency TEXT NOT NULL,
    invoice_date DATE NOT NULL,
    merchant TEXT NOT NULL,
    merchant_normalized TEXT NOT NULL,
    merchant_embedding vector(384) NOT NULL,
    PRIMARY KEY (batch_id, ledger_id)
);

CREATE TABLE IF NOT EXISTS reconciliation_results (
    result_id BIGSERIAL PRIMARY KEY,
    batch_id UUID NOT NULL REFERENCES reconciliation_batches(batch_id)
        ON DELETE CASCADE,
    bank_transaction_id TEXT NOT NULL,
    ledger_id TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('MATCHED', 'EXCEPTION')
    ),
    decision_source TEXT NOT NULL CHECK (
        decision_source IN (
            'RULE_ENGINE',
            'GEMINI',
            'NO_CANDIDATE',
            'VALIDATION',
            'DUPLICATE_CONFLICT',
            'DATA_VALIDATION'
        )
    ),
    lexical_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    semantic_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    fused_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    decision_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    amount_difference NUMERIC(18, 2),
    date_difference_days INTEGER,
    merchant_similarity DOUBLE PRECISION,
    reasoning TEXT NOT NULL,
    missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    candidate_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, bank_transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_ledger_batch_utr
ON ledger_transactions(batch_id, utr);

CREATE INDEX IF NOT EXISTS idx_ledger_batch_amount
ON ledger_transactions(batch_id, amount);

CREATE INDEX IF NOT EXISTS idx_ledger_batch_date
ON ledger_transactions(batch_id, invoice_date);

CREATE INDEX IF NOT EXISTS idx_results_batch
ON reconciliation_results(batch_id);

-- IVFFlat index for fast cosine similarity vector search.
-- lists=10 is appropriate for up to ~1000 rows per batch.
CREATE INDEX IF NOT EXISTS idx_ledger_embedding_cosine
ON ledger_transactions USING ivfflat (merchant_embedding vector_cosine_ops)
WITH (lists = 10);
