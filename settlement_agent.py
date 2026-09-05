import asyncio
import json
import logging
from typing import Any
from google import genai
from config import Settings
from schemas import (
    CashPositionSummary,
    ForwardCashForecast,
    ReconciliationMetrics,
    ReconciliationResultItem,
    SettlementQARequest,
    SettlementQAResponse,
    TaxAuditSummary,
)

logger = logging.getLogger("autoreconcile.settlement_agent")


def build_structured_fallback_answer(
    question: str,
    metrics: ReconciliationMetrics | None,
    cash_position: CashPositionSummary | None,
    forecast: ForwardCashForecast | None,
    tax_audit: TaxAuditSummary | None,
    results: list[ReconciliationResultItem] | None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """
    Deterministic rule-based query parser that produces structured answers
    when Gemini LLM is offline or disabled.
    """
    q = question.lower()
    citations = []
    key_metrics = {}

    # Priority 1: Forecast / next week / conservative scenario (most specific keywords)
    if "forecast" in q or "friday" in q or "conservative" in q or "scenario" in q or "project" in q or "next week" in q or "outlook" in q:
        if forecast:
            key_metrics = {
                "base_ending_balance": str(forecast.base_ending_balance),
                "conservative_ending_balance": str(forecast.conservative_ending_balance),
                "optimistic_ending_balance": str(forecast.optimistic_ending_balance),
                "has_reserve_breach": forecast.has_reserve_breach,
            }
            for p in forecast.daily_projections:
                citations.append({
                    "date": p.forecast_date,
                    "conservative": str(p.conservative_projected_balance),
                    "base": str(p.base_projected_balance),
                })
            answer = (
                f"7-Day Forecast Summary: Base projected ending balance is ₹{forecast.base_ending_balance}, "
                f"Conservative ending balance is ₹{forecast.conservative_ending_balance} (assuming +2 day settlement lag & 5% refund spike), "
                f"and Optimistic ending balance is ₹{forecast.optimistic_ending_balance}. "
                f"Minimum reserve threshold: ₹{forecast.minimum_reserve_threshold} (Reserve Breach: {forecast.has_reserve_breach})."
            )
            return answer, citations, key_metrics

    # Priority 2: Tax / withholding mismatches
    if "tax" in q or "withholding" in q or "tds" in q or "gst" in q or "fee" in q:
        if tax_audit:
            flagged = [item for item in tax_audit.audit_items if item.status == "VARIANCE_FLAG"]
            key_metrics = {
                "total_audited": tax_audit.total_audited_transactions,
                "variance_count": tax_audit.variance_count,
                "total_expected_gst": str(tax_audit.total_expected_gst),
                "total_expected_tds": str(tax_audit.total_expected_tds),
            }
            for f in flagged[:5]:
                citations.append({
                    "transaction_id": f.transaction_id,
                    "variance": str(f.tax_variance + f.fee_variance),
                    "reason": f.discrepancy_reason,
                })
            tx_list = ", ".join([f.transaction_id for f in flagged[:5]]) or "None"
            answer = (
                f"Found {tax_audit.variance_count} transactions with tax/fee variances out of {tax_audit.total_audited_transactions} audited. "
                f"Total expected GST: ₹{tax_audit.total_expected_gst}, Total expected TDS: ₹{tax_audit.total_expected_tds}. "
                f"Flagged transaction IDs: {tx_list}."
            )
            return answer, citations, key_metrics

    # Priority 3: Specific Exception cases / top exceptions / details
    if "exception" in q and ("top" in q or "case" in q or "list" in q or "show" in q or "detail" in q or "give" in q or "tell" in q or "which" in q or "what" in q or "all" in q):
        if results:
            exc_items = [r for r in results if r.status == "EXCEPTION"]
            cat_counts: dict[str, int] = {}
            for r in exc_items:
                cat_counts[r.decision_source] = cat_counts.get(r.decision_source, 0) + 1
            cat_summary = ", ".join([f"**{cnt}** `{cat}`" for cat, cnt in sorted(cat_counts.items())])

            top_exc = exc_items[:5]
            lines = []
            for i, r in enumerate(top_exc, 1):
                diff_str = f", Diff: ₹{r.amount_difference}" if r.amount_difference is not None else ""
                lines.append(f"{i}. **{r.bank_transaction_id}** — Category: `{r.decision_source}` (Score: {r.decision_score:.3f}{diff_str})\n   *Diagnostic:* {r.reasoning}")

            answer = (
                f"### 📋 Unresolved Exceptions Overview\n"
                f"There are **{len(exc_items)} total unresolved exceptions** requiring controller review:\n"
                f"- **Breakdown by Category:** {cat_summary}\n\n"
                f"**Top Prioritized Cases:**\n\n" + "\n\n".join(lines) + "\n\n"
                f"💡 *All {len(exc_items)} records can be filtered by category in the **Exception Explorer** tab or exported via the **Exceptions Only CSV** in Audit Pack.*"
            )
            citations = [{"bank_transaction_id": r.bank_transaction_id, "source": r.decision_source, "score": r.decision_score, "reasoning": r.reasoning} for r in top_exc]
            key_metrics = {"total_exceptions": len(exc_items), "category_counts": cat_counts}
            return answer, citations, key_metrics

    # Priority 4: Match rate / reconciliation overview
    if "match" in q or "accuracy" in q or "precision" in q or "rate" in q or "exception" in q:
        if metrics:
            key_metrics = {
                "matched_count": metrics.matched_count,
                "exception_count": metrics.exception_count,
                "auto_match_rate": f"{metrics.auto_match_rate * 100:.1f}%",
                "precision": f"{metrics.precision * 100:.1f}%" if metrics.precision is not None else "N/A",
            }
            citations.append({"type": "RECONCILIATION_METRICS", "data": key_metrics})
            answer = (
                f"Reconciliation Summary: {metrics.matched_count} matched records out of {metrics.total_bank_records} bank records "
                f"(Auto-Match Rate: {metrics.auto_match_rate * 100:.1f}%, Precision: {metrics.precision * 100 if metrics.precision else 100:.1f}%). "
                f"Total Exceptions: {metrics.exception_count}."
            )
            return answer, citations, key_metrics

    # Priority 4: Float / unreconciled cash / cash position (most general)
    if "float" in q or "unreconciled" in q or "cash" in q or "balance" in q or "position" in q:
        if cash_position:
            key_metrics = {
                "book_balance": str(cash_position.book_balance),
                "bank_balance": str(cash_position.bank_balance),
                "uncleared_float": str(cash_position.uncleared_float),
                "discrepancy_variance": str(cash_position.discrepancy_variance),
            }
            citations.append({"type": "CASH_POSITION", "data": key_metrics})
            answer = (
                f"Total Uncleared Float is ₹{cash_position.uncleared_float} across ledger entries awaiting bank settlement. "
                f"Current Bank Balance is ₹{cash_position.bank_balance}, Book Balance is ₹{cash_position.book_balance}, "
                f"and Discrepancy Variance is ₹{cash_position.discrepancy_variance} ({cash_position.reconciliation_status})."
            )
            return answer, citations, key_metrics

    # Generic fallback
    answer = (
        "Settlement Q&A Summary: Batch data is active. "
        f"Reconciled {metrics.matched_count if metrics else 0} records, "
        f"Bank Balance: ₹{cash_position.bank_balance if cash_position else 0.0}, "
        f"Tax Variances: {tax_audit.variance_count if tax_audit else 0} items."
    )
    return answer, citations, key_metrics


async def answer_settlement_query(
    request: SettlementQARequest,
    metrics: ReconciliationMetrics | None,
    cash_position: CashPositionSummary | None,
    forecast: ForwardCashForecast | None,
    tax_audit: TaxAuditSummary | None,
    results: list[ReconciliationResultItem] | None,
    settings: Settings,
) -> SettlementQAResponse:
    """
    Answers natural language settlement & finance queries grounded in batch data.
    Uses Gemini when configured; otherwise falls back gracefully to structured answers.
    """
    if not settings.is_gemini_configured:
        answer, citations, key_metrics = build_structured_fallback_answer(
            request.question, metrics, cash_position, forecast, tax_audit, results
        )
        return SettlementQAResponse(
            batch_id=request.batch_id,
            question=request.question,
            answer=answer,
            source="STRUCTURED_FALLBACK",
            citations=citations,
            key_metrics_referenced=key_metrics,
        )

    # Gemini LLM grounded answering
    try:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        context_payload: dict[str, Any] = {
            "metrics": metrics.model_dump() if metrics else {},
            "cash_position": {k: str(v) for k, v in cash_position.model_dump().items()} if cash_position else {},
            "forecast_summary": {
                "start_date": forecast.start_date if forecast else "",
                "base_ending_balance": str(forecast.base_ending_balance) if forecast else "",
                "conservative_ending_balance": str(forecast.conservative_ending_balance) if forecast else "",
                "optimistic_ending_balance": str(forecast.optimistic_ending_balance) if forecast else "",
                "has_reserve_breach": forecast.has_reserve_breach if forecast else False,
            },
            "tax_audit_summary": {
                "total_audited": tax_audit.total_audited_transactions if tax_audit else 0,
                "variance_count": tax_audit.variance_count if tax_audit else 0,
                "total_expected_gst": str(tax_audit.total_expected_gst) if tax_audit else "0",
                "total_expected_tds": str(tax_audit.total_expected_tds) if tax_audit else "0",
            },
        }

        # Include specific exception records so Gemini can detail exception cases
        exceptions_list = []
        if results:
            for r in results:
                if r.status == "EXCEPTION":
                    exceptions_list.append({
                        "bank_transaction_id": r.bank_transaction_id,
                        "category": r.decision_source,
                        "decision_score": round(r.decision_score, 4),
                        "amount_diff": str(r.amount_difference) if r.amount_difference is not None else "0.00",
                        "reasoning": r.reasoning,
                    })
        context_payload["top_exceptions"] = exceptions_list[:15]
        context_payload["total_exceptions_count"] = len(exceptions_list)

        system_instruction = (
            "You are an AI Finance Controller. "
            "Answer the user's question accurately and concisely using ONLY the provided structured financial context. "
            "Cite exact numbers, balances, variances, and transaction details. Do not invent any numbers."
        )

        history_text = ""
        if request.history:
            history_lines = [f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in request.history[-6:]]
            history_text = "Previous Conversation:\n" + "\n".join(history_lines) + "\n\n"

        user_content = f"Financial Context:\n{json.dumps(context_payload, indent=2)}\n\n{history_text}Current Question: {request.question}"

        response = None
        for attempt in range(2):
            try:
                response = await client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=user_content,
                    config={"system_instruction": system_instruction, "temperature": 0.1},
                )
                break
            except Exception as api_err:
                err_str = str(api_err)
                if ("503" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt == 0:
                    await asyncio.sleep(3.5)
                    continue
                raise

        llm_answer = "Unable to generate response from Gemini."
        if response and getattr(response, "text", None):
            llm_answer = response.text.strip()
        _, citations, key_metrics = build_structured_fallback_answer(
            request.question, metrics, cash_position, forecast, tax_audit, results
        )

        return SettlementQAResponse(
            batch_id=request.batch_id,
            question=request.question,
            answer=llm_answer,
            source="GEMINI_LLM",
            citations=citations,
            key_metrics_referenced=key_metrics,
        )

    except Exception as e:
        logger.warning(f"Gemini Q&A failed, falling back to structured answer: {e}")
        answer, citations, key_metrics = build_structured_fallback_answer(
            request.question, metrics, cash_position, forecast, tax_audit, results
        )
        return SettlementQAResponse(
            batch_id=request.batch_id,
            question=request.question,
            answer=answer,
            source="STRUCTURED_FALLBACK",
            citations=citations,
            key_metrics_referenced=key_metrics,
        )
