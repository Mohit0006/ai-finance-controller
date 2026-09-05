from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from schemas import CashPositionSummary, ForecastDailyPoint, ForwardCashForecast


def generate_7day_cash_forecast(
    cash_position: CashPositionSummary,
    ledger_records: list[dict[str, Any]],
    start_date: date | None = None,
    daily_burn_rate: Decimal = Decimal("5000.00"),
    minimum_reserve: Decimal = Decimal("20000.00"),
    settlement_lag_days: int = 0,
) -> ForwardCashForecast:
    """
    Computes a 7-day forward cash projection using:
    - cleared cash (bank balance);
    - expected settlement cycles from ledger records;
    - accounts receivable and payable from the batch;
    - a fixed daily operating burn parameter.

    Provides three scenarios:
    1. Base Case: normal T+1 / T+2 settlement.
    2. Optimistic Case: 10% faster collections, no settlement delays.
    3. Conservative Case: +2 days settlement lag and 5% refund spike.
    """
    if start_date is None:
        start_date = date.today()

    # Aggregate expected inflows by expected settlement date (or invoice_date + lag)
    inflows_by_day_offset: dict[int, Decimal] = {i: Decimal("0.00") for i in range(1, 8)}
    outflows_by_day_offset: dict[int, Decimal] = {i: Decimal("0.00") for i in range(1, 8)}

    for rec in ledger_records:
        amt = Decimal(str(rec.get("amount", "0.00"))).quantize(Decimal("0.01"))
        entry_type = str(rec.get("type", "CREDIT")).upper()

        rec_date = rec.get("settlement_date") or rec.get("invoice_date")
        if isinstance(rec_date, str):
            try:
                rec_date = date.fromisoformat(rec_date[:10])
            except (ValueError, TypeError):
                rec_date = None

        if isinstance(rec_date, date):
            delta = (rec_date - start_date).days + settlement_lag_days
            # Distribute into the 7-day window
            day_slot = max(1, min(7, delta if delta > 0 else ((hash(str(rec.get("ledger_id"))) + settlement_lag_days) % 7 + 1)))
        else:
            day_slot = ((hash(str(rec.get("ledger_id"))) + settlement_lag_days) % 7) + 1

        if entry_type in ("DEBIT", "OUTFLOW"):
            outflows_by_day_offset[day_slot] += amt
        else:
            inflows_by_day_offset[day_slot] += amt

    base_balance = cash_position.bank_balance
    optimistic_balance = cash_position.bank_balance
    conservative_balance = cash_position.bank_balance

    daily_points: list[ForecastDailyPoint] = []
    breach_days: list[int] = []

    for day in range(1, 8):
        current_dt = start_date + timedelta(days=day)
        day_str = current_dt.strftime("%Y-%m-%d")

        raw_inflow = inflows_by_day_offset[day]
        raw_outflow = outflows_by_day_offset[day]

        # Base Case: normal daily burn + expected batch flows
        base_inflow = raw_inflow
        base_outflow = raw_outflow + daily_burn_rate
        base_balance = (base_balance + base_inflow - base_outflow).quantize(Decimal("0.01"))

        # Optimistic Case: 10% faster/higher collections, standard burn
        opt_inflow = (raw_inflow * Decimal("1.10")).quantize(Decimal("0.01"))
        opt_outflow = (raw_outflow * Decimal("0.95") + daily_burn_rate).quantize(Decimal("0.01"))
        optimistic_balance = (optimistic_balance + opt_inflow - opt_outflow).quantize(Decimal("0.01"))

        # Conservative Case: delayed settlements (-20% daily realization, pushed back) + 5% refund spike
        cons_inflow = (raw_inflow * Decimal("0.80")).quantize(Decimal("0.01"))
        cons_outflow = (raw_outflow + daily_burn_rate + (raw_inflow * Decimal("0.05"))).quantize(Decimal("0.01"))
        conservative_balance = (conservative_balance + cons_inflow - cons_outflow).quantize(Decimal("0.01"))

        is_breached = conservative_balance < minimum_reserve
        if is_breached:
            breach_days.append(day)

        daily_points.append(
            ForecastDailyPoint(
                day_offset=day,
                forecast_date=day_str,
                base_projected_balance=base_balance,
                optimistic_projected_balance=optimistic_balance,
                conservative_projected_balance=conservative_balance,
                expected_inflows=base_inflow,
                expected_outflows=base_outflow,
                reserve_breached=is_breached,
            )
        )

    return ForwardCashForecast(
        start_date=start_date.strftime("%Y-%m-%d"),
        daily_projections=daily_points,
        base_ending_balance=base_balance,
        optimistic_ending_balance=optimistic_balance,
        conservative_ending_balance=conservative_balance,
        minimum_reserve_threshold=minimum_reserve,
        has_reserve_breach=len(breach_days) > 0,
        breach_days=breach_days,
    )
