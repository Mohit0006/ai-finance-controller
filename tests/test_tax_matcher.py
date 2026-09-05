from decimal import Decimal
from schemas import ReconciliationResultItem
from tax_matcher import audit_tax_lines


def test_tax_matcher_gst_tds_audit():
    bank_records = [
        {
            "transaction_id": "B1",
            "amount": Decimal("1000.00"),
            "fee_percentage": Decimal("2.00"),
            "gateway_fee": Decimal("20.00"),
            "gst_amount": Decimal("3.60"), # 18% of 20 = 3.60
            "tds_amount": Decimal("10.00"), # 1% of 1000 = 10.00
        },
        {
            "transaction_id": "B2",
            "amount": Decimal("2000.00"),
            "fee_percentage": Decimal("2.00"),
            "gateway_fee": Decimal("50.00"), # Variance: expected 40.00
            "gst_amount": Decimal("5.00"),  # Variance: expected 7.20
            "tds_amount": Decimal("0.00"),  # Variance: expected 20.00
        },
    ]
    ledger_records = []
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
    ]

    summary = audit_tax_lines(bank_records, ledger_records, results)

    assert summary.total_audited_transactions == 2
    assert summary.pass_count == 1
    assert summary.variance_count == 1
    assert summary.audit_items[0].status == "PASS"
    assert summary.audit_items[1].status == "VARIANCE_FLAG"
    assert summary.audit_items[1].fee_variance == Decimal("10.00")
    assert summary.total_expected_gst == Decimal("10.80") # 3.60 + 7.20
    assert summary.total_expected_tds == Decimal("30.00") # 10.00 + 20.00
