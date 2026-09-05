from decimal import Decimal
from typing import Any
from schemas import CashPositionSummary, ReconciliationResultItem


def calculate_cash_position(
    bank_records: list[dict[str, Any]],
    ledger_records: list[dict[str, Any]],
    results: list[ReconciliationResultItem],
    currency: str = "INR",
) -> CashPositionSummary:
    """
    Computes the cash position and reconciliation bridge using strict Decimal arithmetic.

    - Book Balance = sum of recognized ledger credits minus sum of recognized ledger debits.
    - Bank Balance = sum of cleared bank receipts minus sum of bank disbursements.
    - Reconciled Cash Inflow = sum of exactly matched inflow transactions.
    - Reconciled Cash Outflow = sum of exactly matched outflow transactions.
    - Uncleared Float = ledger entries awaiting bank settlement (T+1 / T+2 lag).
    - Discrepancy Variance = absolute difference between Book Balance and Bank Balance after adjusting for float.
    """
    # 1. Book Balance (Ledger)
    ledger_by_id = {str(r["ledger_id"]): r for r in ledger_records}
    book_balance = sum((Decimal(str(r.get("amount", "0.00"))) * (Decimal("-1") if str(r.get("type", "CREDIT")).upper() in ("DEBIT", "OUTFLOW") else Decimal("1")) for r in ledger_records), Decimal("0.00")).quantize(Decimal("0.01"))

    # 2. Bank Balance
    bank_by_id = {str(r["transaction_id"]): r for r in bank_records}
    bank_balance = sum((Decimal(str(r.get("amount", "0.00"))) * (Decimal("-1") if str(r.get("type", "CREDIT")).upper() in ("DEBIT", "OUTFLOW") else Decimal("1")) for r in bank_records), Decimal("0.00")).quantize(Decimal("0.01"))

    # 3. Matched Inflows / Outflows
    matched_results = [r for r in results if r.status == "MATCHED" and r.ledger_id]
    matched_ledger_ids = {r.ledger_id for r in matched_results}
    
    matched_inflows = sum((Decimal(str(bank_by_id[r.bank_transaction_id].get("amount", "0.00"))) for r in matched_results if str(bank_by_id[r.bank_transaction_id].get("type", "CREDIT")).upper() not in ("DEBIT", "OUTFLOW")), Decimal("0.00")).quantize(Decimal("0.01"))
    matched_outflows = sum((Decimal(str(bank_by_id[r.bank_transaction_id].get("amount", "0.00"))) for r in matched_results if str(bank_by_id[r.bank_transaction_id].get("type", "CREDIT")).upper() in ("DEBIT", "OUTFLOW")), Decimal("0.00")).quantize(Decimal("0.01"))

    # 4. Uncleared Float (Ledger entries recognized in books but not yet matched/cleared in bank)
    uncleared_float = sum((Decimal(str(r.get("amount", "0.00"))) for l_id, r in ledger_by_id.items() if l_id not in matched_ledger_ids and str(r.get("type", "CREDIT")).upper() not in ("DEBIT", "OUTFLOW")), Decimal("0.00")).quantize(Decimal("0.01"))

    # 5. Discrepancy Variance
    # Adjusted Bank = Bank Balance + Uncleared Float (deposits in transit)
    # Variance = |Book Balance - Adjusted Bank|
    adjusted_bank = bank_balance + uncleared_float
    discrepancy_variance = abs(book_balance - adjusted_bank).quantize(Decimal("0.01"))

    reconciliation_status = "BALANCED" if discrepancy_variance == Decimal("0.00") else "UNRECONCILED_VARIANCE"

    return CashPositionSummary(
        book_balance=book_balance,
        bank_balance=bank_balance,
        reconciled_cash_inflow=matched_inflows.quantize(Decimal("0.01")),
        reconciled_cash_outflow=matched_outflows.quantize(Decimal("0.01")),
        uncleared_float=uncleared_float.quantize(Decimal("0.01")),
        discrepancy_variance=discrepancy_variance,
        currency=currency,
        reconciliation_status=reconciliation_status,
    )
