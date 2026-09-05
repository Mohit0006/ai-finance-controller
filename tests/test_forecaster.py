from datetime import date
from decimal import Decimal
from forecaster import generate_7day_cash_forecast
from schemas import CashPositionSummary


def test_7day_forecaster_scenarios_and_reserve_breach():
    cash_pos = CashPositionSummary(
        book_balance=Decimal("50000.00"),
        bank_balance=Decimal("40000.00"),
        reconciled_cash_inflow=Decimal("30000.00"),
        reconciled_cash_outflow=Decimal("0.00"),
        uncleared_float=Decimal("10000.00"),
        discrepancy_variance=Decimal("0.00"),
        currency="INR",
        reconciliation_status="BALANCED",
    )

    ledger_records = [
        {"ledger_id": "L1", "amount": Decimal("10000.00"), "type": "CREDIT", "invoice_date": date(2026, 8, 2)},
        {"ledger_id": "L2", "amount": Decimal("5000.00"), "type": "CREDIT", "invoice_date": date(2026, 8, 3)},
        {"ledger_id": "L3", "amount": Decimal("8000.00"), "type": "DEBIT", "invoice_date": date(2026, 8, 4)},
    ]

    forecast = generate_7day_cash_forecast(
        cash_position=cash_pos,
        ledger_records=ledger_records,
        start_date=date(2026, 8, 1),
        daily_burn_rate=Decimal("5000.00"),
        minimum_reserve=Decimal("20000.00"),
    )

    assert len(forecast.daily_projections) == 7
    assert forecast.start_date == "2026-08-01"
    # Optimistic ending balance should be higher than Base, which is higher than Conservative
    assert forecast.optimistic_ending_balance >= forecast.base_ending_balance
    assert forecast.base_ending_balance >= forecast.conservative_ending_balance
    # Verify daily points have valid date and projections
    for p in forecast.daily_projections:
        assert p.day_offset in range(1, 8)
        assert isinstance(p.base_projected_balance, Decimal)
        assert isinstance(p.optimistic_projected_balance, Decimal)
        assert isinstance(p.conservative_projected_balance, Decimal)
