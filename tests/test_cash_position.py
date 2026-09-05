from decimal import Decimal
from cash_position import calculate_cash_position
from schemas import ReconciliationResultItem


def test_cash_position_calculation():
    bank_records = [
        {"transaction_id": "B1", "amount": Decimal("1000.00"), "type": "CREDIT"},
        {"transaction_id": "B2", "amount": Decimal("500.00"), "type": "CREDIT"},
        {"transaction_id": "B3", "amount": Decimal("200.00"), "type": "DEBIT"},
    ]
    ledger_records = [
        {"ledger_id": "L1", "amount": Decimal("1000.00"), "type": "CREDIT"},
        {"ledger_id": "L2", "amount": Decimal("500.00"), "type": "CREDIT"},
        {"ledger_id": "L3", "amount": Decimal("300.00"), "type": "CREDIT"}, # Uncleared float
    ]
    results = [
        ReconciliationResultItem(
            bank_transaction_id="B1",
            ledger_id="L1",
            status="MATCHED",
            decision_source="RULE_ENGINE",
            decision_score=0.95,
        ),
        ReconciliationResultItem(
            bank_transaction_id="B2",
            ledger_id="L2",
            status="MATCHED",
            decision_source="RULE_ENGINE",
            decision_score=0.90,
        ),
        ReconciliationResultItem(
            bank_transaction_id="B3",
            ledger_id=None,
            status="EXCEPTION",
            decision_source="NO_CANDIDATE",
            decision_score=0.0,
        ),
    ]

    cp = calculate_cash_position(bank_records, ledger_records, results)

    # Book balance = 1000 + 500 + 300 = 1800.00
    assert cp.book_balance == Decimal("1800.00")
    # Bank balance = 1000 + 500 - 200 = 1300.00
    assert cp.bank_balance == Decimal("1300.00")
    # Reconciled inflow = 1000 + 500 = 1500.00
    assert cp.reconciled_cash_inflow == Decimal("1500.00")
    # Uncleared float (L3 not matched) = 300.00
    assert cp.uncleared_float == Decimal("300.00")
    # Adjusted Bank = 1300 + 300 = 1600.00; Variance = |1800 - 1600| = 200.00 (from B3 debit)
    assert cp.discrepancy_variance == Decimal("200.00")
    assert cp.reconciliation_status == "UNRECONCILED_VARIANCE"
