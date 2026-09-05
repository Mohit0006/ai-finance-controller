import json
import logging
from typing import Any, Optional
import uuid
import asyncpg
from pgvector.asyncpg import register_vector
from schemas import ReconciliationResultItem

logger = logging.getLogger(__name__)


async def init_connection(connection: asyncpg.Connection):
    try:
        await register_vector(connection)
    except Exception as e:
        logger.error(f"Failed to register pgvector codec on asyncpg connection: {e}")
        raise


async def create_pool(database_url: str) -> asyncpg.Pool:
    try:
        from pgvector.asyncpg import register_vector as _check_import
    except ImportError:
        raise RuntimeError("pgvector.asyncpg is required but could not be imported.")

    return await asyncpg.create_pool(
        dsn=database_url,
        init=init_connection,
        min_size=2,
        max_size=10
    )


async def verify_database_schema(pool: asyncpg.Pool) -> tuple[bool, str]:
    """
    Verifies:
    1. PostgreSQL connectivity
    2. Vector extension
    3. Required tables
    4. 384-dimensional vector handling
    """
    try:
        async with pool.acquire() as conn:
            # 1. Connection check
            val = await conn.fetchval("SELECT 1;")
            if val != 1:
                return False, "Database connectivity check failed."

            # 2. Vector extension check
            ext = await conn.fetchval("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
            if not ext:
                return False, "pgvector extension is not installed or enabled in PostgreSQL."

            # 3. Required tables check
            tables = await conn.fetch(
                """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_name IN ('reconciliation_batches', 'ledger_transactions', 'reconciliation_results');
                """
            )
            found_tables = {r["table_name"] for r in tables}
            required_tables = {"reconciliation_batches", "ledger_transactions", "reconciliation_results"}
            if not required_tables.issubset(found_tables):
                missing = required_tables - found_tables
                return False, f"Missing required database tables: {missing}. Please run the initial migration."

            # 4. 384-dimensional vector codec test
            dummy_vec = [0.0] * 384
            dummy_vec[0] = 1.0
            test_dist = await conn.fetchval("SELECT ($1::vector <=> $1::vector);", dummy_vec)
            if test_dist is None or abs(test_dist) > 1e-5:
                return False, "pgvector 384-dimensional vector test calculation failed."

            return True, "Database schema and vector extension verified successfully."
    except Exception as e:
        return False, f"Database verification error: {e}"


async def create_batch(
    pool: asyncpg.Pool,
    batch_id: uuid.UUID,
    total_bank: int,
    total_ledger: int,
    status: str = "PROCESSING"
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reconciliation_batches (batch_id, total_bank_records, total_ledger_records, status)
            VALUES ($1, $2, $3, $4);
            """,
            batch_id, total_bank, total_ledger, status
        )


async def insert_ledger_rows(
    pool: asyncpg.Pool,
    batch_id: uuid.UUID,
    ledger_records: list[dict[str, Any]],
    embeddings: list[list[float]]
) -> None:
    if not ledger_records:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            records_to_insert = []
            for record, emb in zip(ledger_records, embeddings):
                records_to_insert.append((
                    batch_id,
                    record["ledger_id"],
                    record.get("invoice_id"),
                    record.get("utr"),
                    record["amount"],
                    record["currency"],
                    record["invoice_date"],
                    record["merchant"],
                    record["merchant_normalized"],
                    emb,
                ))

            await conn.executemany(
                """
                INSERT INTO ledger_transactions (
                    batch_id, ledger_id, invoice_id, utr, amount, currency,
                    invoice_date, merchant, merchant_normalized, merchant_embedding
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                """,
                records_to_insert
            )


async def retrieve_candidates(
    pool: asyncpg.Pool,
    batch_id: uuid.UUID,
    bank_currency: Optional[str],
    bank_embedding: list[float],
    limit: int = 15
) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ledger_id,
                invoice_id,
                utr,
                amount,
                currency,
                invoice_date,
                merchant,
                merchant_normalized,
                (merchant_embedding <=> $2) AS cosine_distance
            FROM ledger_transactions
            WHERE batch_id = $1
              AND ($3::text IS NULL OR currency = $3)
            ORDER BY merchant_embedding <=> $2 ASC
            LIMIT $4;
            """,
            batch_id,
            bank_embedding,
            bank_currency,
            limit
        )

        return [dict(r) for r in rows]


async def retrieve_candidates_by_utr(
    pool: asyncpg.Pool,
    batch_id: uuid.UUID,
    bank_utr: str,
    bank_embedding: list[float],
) -> list[dict[str, Any]]:
    """Direct UTR lookup — guarantees exact UTR matches are found regardless of merchant embedding distance."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ledger_id,
                invoice_id,
                utr,
                amount,
                currency,
                invoice_date,
                merchant,
                merchant_normalized,
                (merchant_embedding <=> $3) AS cosine_distance
            FROM ledger_transactions
            WHERE batch_id = $1
              AND utr = $2;
            """,
            batch_id,
            bank_utr,
            bank_embedding,
        )
        return [dict(r) for r in rows]


async def insert_results(
    pool: asyncpg.Pool,
    batch_id: uuid.UUID,
    results: list[ReconciliationResultItem]
) -> None:
    if not results:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            rows_to_insert = []
            for item in results:
                rows_to_insert.append((
                    batch_id,
                    item.bank_transaction_id,
                    item.ledger_id,
                    item.status,
                    item.decision_source,
                    item.lexical_score,
                    item.semantic_score,
                    item.fused_score,
                    item.decision_score,
                    item.amount_difference,
                    item.date_difference_days,
                    item.merchant_similarity,
                    item.reasoning,
                    json.dumps(item.missing_fields),
                    json.dumps(item.risk_flags),
                    json.dumps(item.candidate_evidence),
                ))

            await conn.executemany(
                """
                INSERT INTO reconciliation_results (
                    batch_id, bank_transaction_id, ledger_id, status, decision_source,
                    lexical_score, semantic_score, fused_score, decision_score,
                    amount_difference, date_difference_days, merchant_similarity,
                    reasoning, missing_fields, risk_flags, candidate_evidence
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14::jsonb, $15::jsonb, $16::jsonb
                );
                """,
                rows_to_insert
            )


async def update_batch_status(pool: asyncpg.Pool, batch_id: uuid.UUID, status: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE reconciliation_batches
            SET status = $2
            WHERE batch_id = $1;
            """,
            batch_id, status
        )


async def get_batch(pool: asyncpg.Pool, batch_id: uuid.UUID) -> Optional[dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT batch_id, created_at, total_bank_records, total_ledger_records, status
            FROM reconciliation_batches
            WHERE batch_id = $1;
            """,
            batch_id
        )
        return dict(row) if row else None


async def get_batch_results(pool: asyncpg.Pool, batch_id: uuid.UUID) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                bank_transaction_id,
                ledger_id,
                status,
                decision_source,
                lexical_score,
                semantic_score,
                fused_score,
                decision_score,
                amount_difference,
                date_difference_days,
                merchant_similarity,
                reasoning,
                missing_fields,
                risk_flags,
                candidate_evidence,
                created_at
            FROM reconciliation_results
            WHERE batch_id = $1
            ORDER BY result_id ASC;
            """,
            batch_id
        )
        return [dict(r) for r in rows]
