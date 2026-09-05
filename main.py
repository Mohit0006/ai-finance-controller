import asyncio
from contextlib import asynccontextmanager
import io
import logging
import time
from typing import Optional
import uuid
import polars as pl
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from cash_position import calculate_cash_position
from config import get_settings
from data_processing import preprocess_bank, preprocess_ledger, read_csv_bytes_to_polars
from database import (
    create_batch,
    create_pool,
    get_batch,
    get_batch_results,
    insert_ledger_rows,
    insert_results,
    retrieve_candidates,
    retrieve_candidates_by_utr,
    update_batch_status,
    verify_database_schema,
)
from embeddings import check_embedding_model_status, generate_embeddings, generate_single_embedding, get_embedding_model
from forecaster import generate_7day_cash_forecast
from matching_engine import (
    assign_one_to_one_matches,
    classify_candidate,
    evaluate_candidate_edge,
)
from metrics import calculate_reconciliation_metrics
from schemas import (
    CandidateEdge,
    CashPositionSummary,
    DecisionSource,
    ErrorResponse,
    ForwardCashForecast,
    HealthResponse,
    ReconcileResponse,
    ReconciliationMetrics,
    ReconciliationResultItem,
    RowValidationError,
    SettlementQARequest,
    SettlementQAResponse,
    TaxAuditSummary,
)
from settlement_agent import answer_settlement_query
from tax_matcher import audit_tax_lines

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("autoreconcile")

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

settings = get_settings()
db_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    logger.info("Initializing AutoReconcile AI service...")
    
    # 1. Warm up embedding model in background thread
    try:
        await asyncio.to_thread(get_embedding_model)
        logger.info("Embedding model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")

    # 2. Initialize database connection pool
    try:
        db_pool = await create_pool(settings.DATABASE_URL)
        app.state.pool = db_pool
        is_valid, msg = await verify_database_schema(db_pool)
        if not is_valid:
            logger.warning(f"Database schema verification warning: {msg}")
        else:
            logger.info(f"Database schema verified: {msg}")
    except Exception as e:
        logger.error(f"Database connection initialization failed: {e}")
        app.state.pool = None

    yield

    # Cleanup
    if db_pool:
        logger.info("Closing database connection pool...")
        await db_pool.close()


app = FastAPI(
    title="AI Finance Controller",
    description="Deterministic-first, measurable financial reconciliation engine.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "service": "AI Finance Controller",
        "version": "1.0.0",
        "description": "Financial Reconciliation & Treasury Engine",
        "endpoints": {
            "health": "/health",
            "reconcile": "/reconcile (POST)",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }



@app.get("/health", response_model=HealthResponse)
async def health_check():
    pool = getattr(app.state, "pool", None)
    
    # 0. Health checks
    db_status = "disconnected"
    if pool:
        is_valid, _ = await verify_database_schema(pool)
        if is_valid:
            db_status = "connected"

    current_settings = get_settings()
    gemini_status = "configured" if current_settings.is_gemini_configured else "disabled"
    embedding_status = "ready" if get_embedding_model() is not None else "unavailable"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        vector_extension="available" if db_status == "connected" else "unavailable",
        embedding_model="available" if check_embedding_model_status() else "unavailable",
        gemini=gemini_status,
    )


@app.post(
    "/reconcile",
    response_model=ReconcileResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation Error"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)
async def reconcile(
    bank_file: UploadFile = File(..., description="Required Bank statement CSV"),
    ledger_file: UploadFile = File(..., description="Required Internal Ledger CSV"),
    ground_truth_file: Optional[UploadFile] = File(None, description="Optional Ground Truth CSV for metric evaluation only"),
):
    start_time = time.perf_counter()
    pool = getattr(app.state, "pool", None)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection pool is not available. Please ensure PostgreSQL is running.",
        )

    # 1. Read file bytes with size and type validation
    try:
        bank_bytes = await bank_file.read()
        ledger_bytes = await ledger_file.read()
        gt_bytes = await ground_truth_file.read() if ground_truth_file else None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to read uploaded files: {e}",
        )

    # Validate file sizes
    for label, data in [("bank_file", bank_bytes), ("ledger_file", ledger_bytes)]:
        if len(data) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{label} exceeds maximum upload size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB.",
            )
    if gt_bytes and len(gt_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ground_truth_file exceeds maximum upload size of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB.",
        )

    # 2. Parse into Polars DataFrames
    try:
        bank_df = read_csv_bytes_to_polars(bank_bytes)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                detail=f"Malformed bank CSV file: {e}",
                validation_errors=[RowValidationError(row_number=0, field="bank_file", message=str(e))],
            ).model_dump(),
        )

    try:
        ledger_df = read_csv_bytes_to_polars(ledger_bytes)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                detail=f"Malformed ledger CSV file: {e}",
                validation_errors=[RowValidationError(row_number=0, field="ledger_file", message=str(e))],
            ).model_dump(),
        )

    # 3. Preprocess and validate (skip invalid rows, continue with valid ones)
    bank_records, bank_errors = preprocess_bank(bank_df)
    ledger_records, ledger_errors = preprocess_ledger(ledger_df)
    all_validation_errors = bank_errors + ledger_errors

    # Log validation warnings but do NOT abort the batch for row-level errors.
    # Only abort if required columns are missing (field="column_name", row_number=0).
    column_level_errors = [e for e in all_validation_errors if e.row_number == 0]
    if column_level_errors:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                detail="Input CSV is missing required columns.",
                validation_errors=column_level_errors,
            ).model_dump(),
        )

    if all_validation_errors:
        logger.warning(
            f"Skipped {len(all_validation_errors)} invalid rows during preprocessing. "
            f"Proceeding with {len(bank_records)} bank and {len(ledger_records)} ledger valid records."
        )

    if not bank_records or not ledger_records:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                detail="Bank or ledger file contains no valid records after validation.",
                validation_errors=all_validation_errors or [RowValidationError(row_number=0, field="records", message="No valid records found")],
            ).model_dump(),
        )

    # 4. Optional ground truth parsing (strictly for evaluation metrics)
    ground_truth_records: Optional[list[dict]] = None
    if gt_bytes:
        try:
            gt_df = read_csv_bytes_to_polars(gt_bytes)
            ground_truth_records = gt_df.to_dicts()
        except Exception as e:
            logger.warning(f"Could not parse ground truth file for metrics evaluation: {e}")

    # 5. Create new batch
    batch_uuid = uuid.uuid4()
    try:
        await create_batch(
            pool,
            batch_uuid,
            total_bank=len(bank_records),
            total_ledger=len(ledger_records),
            status="PROCESSING",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reconciliation batch in database: {e}",
        )

    try:
        # 6. Generate embeddings for ledger merchants in batches using worker thread
        ledger_merchants = [r["merchant_normalized"] for r in ledger_records]
        ledger_embeddings = await asyncio.to_thread(generate_embeddings, ledger_merchants, 32)

        # 7. Insert ledger rows with pgvector embeddings
        await insert_ledger_rows(pool, batch_uuid, ledger_records, ledger_embeddings)

        # 8. Candidate Retrieval and Edge Evaluation
        # Batch bank merchant embeddings
        bank_merchants = [r["merchant_normalized"] for r in bank_records]
        bank_embeddings = await asyncio.to_thread(generate_embeddings, bank_merchants, 32)

        eligible_candidate_edges: list[CandidateEdge] = []
        bank_to_all_edges_map: dict[str, list[CandidateEdge]] = {}
        edge_decision_sources: dict[tuple[str, str], DecisionSource] = {}
        edge_reasonings: dict[tuple[str, str], str] = {}

        for bank_rec, b_emb in zip(bank_records, bank_embeddings):
            b_id = str(bank_rec["transaction_id"])

            # UTR-first retrieval: directly find ledger rows with matching UTR
            utr_candidates: list[dict] = []
            bank_utr = bank_rec.get("utr")
            if bank_utr:
                utr_candidates = await retrieve_candidates_by_utr(
                    pool, batch_uuid, bank_utr, b_emb
                )

            # Vector-based retrieval for broader coverage
            vector_candidates = await retrieve_candidates(
                pool,
                batch_uuid,
                bank_rec.get("currency"),
                b_emb,
                limit=15,
            )

            # Merge and deduplicate: UTR matches first, then vector matches
            seen_ledger_ids: set[str] = set()
            candidates: list[dict] = []
            for c in utr_candidates + vector_candidates:
                lid = str(c["ledger_id"])
                if lid not in seen_ledger_ids:
                    seen_ledger_ids.add(lid)
                    candidates.append(c)

            edges_for_this_bank: list[CandidateEdge] = []
            for cand in candidates:
                edge = evaluate_candidate_edge(bank_rec, cand, settings)
                edges_for_this_bank.append(edge)

                classification = classify_candidate(edge, settings)

                if classification == "clearly_safe":
                    eligible_candidate_edges.append(edge)
                    edge_decision_sources[(edge.bank_transaction_id, edge.ledger_id)] = "RULE_ENGINE"
                    edge_reasonings[(edge.bank_transaction_id, edge.ledger_id)] = (
                        "Matched by deterministic rule engine (exact UTR / verified financial criteria)."
                    )
                elif classification == "borderline":
                    # Borderline candidates are treated as exceptions automatically
                    # to maintain strict 100% determinism without LLM dependencies.
                    pass
                else:
                    # Ineligible: do not add to eligible edges graph
                    pass

            bank_to_all_edges_map[b_id] = edges_for_this_bank

        # 9. Global 1:1 Assignment with deterministic tie-breaking
        final_results = assign_one_to_one_matches(
            eligible_edges=eligible_candidate_edges,
            all_bank_records=bank_records,
            bank_to_all_edges_map=bank_to_all_edges_map,
            edge_decision_sources=edge_decision_sources,
            edge_reasonings=edge_reasonings,
        )

        # 11. Insert results and update batch status
        await insert_results(pool, batch_uuid, final_results)
        await update_batch_status(pool, batch_uuid, "COMPLETED")

        # 12. Dynamic metric calculation
        processing_time = time.perf_counter() - start_time
        metrics = calculate_reconciliation_metrics(
            results=final_results,
            total_bank_records=len(bank_records),
            total_ledger_records=len(ledger_records),
            processing_time_seconds=processing_time,
            ground_truth=ground_truth_records,
        )

        # 13. Cash Position Summary
        cash_pos = calculate_cash_position(
            bank_records=bank_records,
            ledger_records=ledger_records,
            results=final_results,
            currency="INR",
        )

        # 14. 7-Day Forward Cash Forecast
        # Derive start date from the batch data (max transaction date)
        batch_max_date = max(
            (r["transaction_date"] for r in bank_records if r.get("transaction_date")),
            default=None,
        )
        forecast = generate_7day_cash_forecast(
            cash_position=cash_pos,
            ledger_records=ledger_records,
            start_date=batch_max_date,
        )

        # 15. Tax-Line Matcher & Fee Audit
        tax_audit = audit_tax_lines(
            bank_records=bank_records,
            ledger_records=ledger_records,
            results=final_results,
        )

        # Store latest batch state in app state for Q&A
        if not hasattr(app.state, "batch_cache"):
            app.state.batch_cache = {}
        app.state.batch_cache[str(batch_uuid)] = {
            "metrics": metrics,
            "cash_position": cash_pos,
            "forecast": forecast,
            "tax_audit": tax_audit,
            "results": final_results,
        }

        return ReconcileResponse(
            batch_id=str(batch_uuid),
            status="COMPLETED",
            metrics=metrics,
            results=final_results,
            validation_errors=[],
            cash_position=cash_pos,
            forecast=forecast,
            tax_audit=tax_audit,
        )

    except Exception as e:
        logger.error(f"Reconciliation batch {batch_uuid} failed with fatal error: {e}", exc_info=True)
        try:
            await update_batch_status(pool, batch_uuid, "FAILED")
        except Exception as update_err:
            logger.error(f"Failed to update batch status to FAILED: {update_err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation execution error: {str(e)}",
        )


@app.post("/qa/settlement", response_model=SettlementQAResponse)
async def settlement_qa(request: SettlementQARequest):
    batch_cache = getattr(app.state, "batch_cache", {})
    batch_data = batch_cache.get(request.batch_id)
    if not batch_data and batch_cache:
        # Fallback to the latest reconciled batch
        latest_key = list(batch_cache.keys())[-1]
        batch_data = batch_cache[latest_key]

    metrics = batch_data.get("metrics") if batch_data else None
    cash_pos = batch_data.get("cash_position") if batch_data else None
    forecast = batch_data.get("forecast") if batch_data else None
    tax_audit = batch_data.get("tax_audit") if batch_data else None
    results = batch_data.get("results") if batch_data else None

    return await answer_settlement_query(
        request=request,
        metrics=metrics,
        cash_position=cash_pos,
        forecast=forecast,
        tax_audit=tax_audit,
        results=results,
        settings=settings,
    )


@app.get("/batches/{batch_id}")
async def get_batch_info(batch_id: uuid.UUID):
    pool = getattr(app.state, "pool", None)
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not available")

    batch = await get_batch(pool, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")

    return batch


@app.get("/batches/{batch_id}/results")
async def get_results_for_batch(batch_id: uuid.UUID):
    pool = getattr(app.state, "pool", None)
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not available")

    results = await get_batch_results(pool, batch_id)
    return {"batch_id": str(batch_id), "count": len(results), "results": results}

