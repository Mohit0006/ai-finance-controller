import pytest
from decimal import Decimal
from config import Settings
from schemas import (
    CashPositionSummary,
    ForecastDailyPoint,
    ForwardCashForecast,
    ReconciliationMetrics,
    SettlementQARequest,
    TaxAuditItem,
    TaxAuditSummary,
)
from settlement_agent import answer_settlement_query


@pytest.mark.asyncio
async def test_settlement_agent_structured_fallback():
    settings = Settings(GOOGLE_API_KEY="") # Gemini disabled

    metrics = ReconciliationMetrics(
        total_bank_records=106,
        total_ledger_records=118,
        matched_count=37,
        exception_count=69,
        auto_match_rate=0.3491,
        precision=1.0,
        recall=0.5068,
        false_positive_count=0,
        unresolved_exception_count=69,
        processing_time_seconds=0.65,
        throughput_records_per_second=163.0,
        ground_truth_available=True,
        metrics_scope="synthetic_ground_truth",
    )

    cash_pos = CashPositionSummary(
        book_balance=Decimal("50000.00"),
        bank_balance=Decimal("45000.00"),
        reconciled_cash_inflow=Decimal("30000.00"),
        reconciled_cash_outflow=Decimal("0.00"),
        uncleared_float=Decimal("5000.00"),
        discrepancy_variance=Decimal("0.00"),
        currency="INR",
        reconciliation_status="BALANCED",
    )

    tax_audit = TaxAuditSummary(
        total_audited_transactions=10,
        pass_count=8,
        variance_count=2,
        total_gross_volume=Decimal("20000.00"),
        total_expected_gst=Decimal("72.00"),
        total_expected_tds=Decimal("200.00"),
        total_fee_variance=Decimal("30.00"),
        audit_items=[
            TaxAuditItem(
                transaction_id="B_VAR_1",
                gross_amount=Decimal("1000.00"),
                fee_percentage=Decimal("2.00"),
                expected_gateway_fee=Decimal("20.00"),
                actual_gateway_fee=Decimal("35.00"),
                expected_gst_18pct=Decimal("3.60"),
                actual_gst_18pct=Decimal("3.60"),
                expected_tds_1pct=Decimal("10.00"),
                actual_tds_1pct=Decimal("10.00"),
                fee_variance=Decimal("15.00"),
                tax_variance=Decimal("0.00"),
                status="VARIANCE_FLAG",
                discrepancy_reason="Gateway fee variance: expected ₹20.00, actual ₹35.00",
            )
        ],
    )

    forecast = ForwardCashForecast(
        start_date="2026-08-01",
        daily_projections=[
            ForecastDailyPoint(
                day_offset=1,
                forecast_date="2026-08-02",
                base_projected_balance=Decimal("40000.00"),
                optimistic_projected_balance=Decimal("45000.00"),
                conservative_projected_balance=Decimal("35000.00"),
                expected_inflows=Decimal("0.00"),
                expected_outflows=Decimal("5000.00"),
                reserve_breached=False,
            )
        ],
        base_ending_balance=Decimal("40000.00"),
        optimistic_ending_balance=Decimal("45000.00"),
        conservative_ending_balance=Decimal("35000.00"),
        minimum_reserve_threshold=Decimal("20000.00"),
        has_reserve_breach=False,
        breach_days=[],
    )

    # 1. Question about float
    req1 = SettlementQARequest(batch_id="test_batch", question="What is our total unreconciled float?")
    res1 = await answer_settlement_query(req1, metrics, cash_pos, forecast, tax_audit, None, settings)
    assert res1.source == "STRUCTURED_FALLBACK"
    assert "5000.00" in res1.answer

    # 2. Question about tax withholding
    req2 = SettlementQARequest(batch_id="test_batch", question="Which transactions had tax withholding mismatches?")
    res2 = await answer_settlement_query(req2, metrics, cash_pos, forecast, tax_audit, None, settings)
    assert "2 transactions" in res2.answer or "B_VAR_1" in res2.answer

    # 3. Question about forecast
    req3 = SettlementQARequest(batch_id="test_batch", question="How will cash look next week under the conservative scenario?")
    res3 = await answer_settlement_query(req3, metrics, cash_pos, forecast, tax_audit, None, settings)
    assert "35000.00" in res3.answer
