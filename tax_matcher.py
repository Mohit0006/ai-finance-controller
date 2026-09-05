from decimal import Decimal
from typing import Any
from schemas import ReconciliationResultItem, TaxAuditItem, TaxAuditSummary

DEFAULT_FEE_PCT = Decimal("2.00")
GST_RATE = Decimal("0.18")
TDS_RATE = Decimal("0.01")
VARIANCE_TOLERANCE = Decimal("0.05")


def audit_tax_lines(
    bank_records: list[dict[str, Any]],
    ledger_records: list[dict[str, Any]],
    results: list[ReconciliationResultItem],
    tolerance: Decimal = VARIANCE_TOLERANCE,
) -> TaxAuditSummary:
    """
    Audits gateway fee and tax deductions using deterministic Decimal calculations:
    - Expected Platform Gateway Fee = Gross Amount * (Fee % / 100)
    - Expected GST = Expected Gateway Fee * 18%
    - Expected TDS = Gross Amount * 1% (where applicable)
    - Flags variance if |Actual - Expected| > tolerance
    """
    bank_by_id = {str(r["transaction_id"]): r for r in bank_records}
    ledger_by_id = {str(r["ledger_id"]): r for r in ledger_records}

    audit_items: list[TaxAuditItem] = []
    total_gross = Decimal("0.00")
    total_expected_gst = Decimal("0.00")
    total_expected_tds = Decimal("0.00")
    total_fee_variance = Decimal("0.00")
    pass_count = 0
    variance_count = 0

    for b_rec in bank_records:
        tx_id = str(b_rec["transaction_id"])
        gross_amt = Decimal(str(b_rec.get("amount", "0.00"))).quantize(Decimal("0.01"))
        total_gross += gross_amt

        # Fee percentage
        fee_pct_val = b_rec.get("fee_percentage")
        fee_pct = Decimal(str(fee_pct_val)).quantize(Decimal("0.01")) if fee_pct_val is not None else DEFAULT_FEE_PCT

        # Expected calculations
        expected_gw_fee = (gross_amt * fee_pct / Decimal("100.00")).quantize(Decimal("0.01"))
        expected_gst = (expected_gw_fee * GST_RATE).quantize(Decimal("0.01"))
        expected_tds = (gross_amt * TDS_RATE).quantize(Decimal("0.01"))

        # Actual values from bank or ledger
        actual_gw_fee = Decimal(str(b_rec.get("gateway_fee", expected_gw_fee))).quantize(Decimal("0.01"))
        actual_gst = Decimal(str(b_rec.get("gst_amount", expected_gst))).quantize(Decimal("0.01"))
        actual_tds = Decimal(str(b_rec.get("tds_amount", expected_tds))).quantize(Decimal("0.01"))

        fee_diff = abs(actual_gw_fee - expected_gw_fee).quantize(Decimal("0.01"))
        gst_diff = abs(actual_gst - expected_gst).quantize(Decimal("0.01"))
        tds_diff = abs(actual_tds - expected_tds).quantize(Decimal("0.01"))
        tax_diff = (gst_diff + tds_diff).quantize(Decimal("0.01"))

        total_expected_gst += expected_gst
        total_expected_tds += expected_tds
        total_fee_variance += fee_diff

        # Find matching ledger_id if any
        matching_ledger_id = next((res.ledger_id for res in results if res.bank_transaction_id == tx_id and res.status == "MATCHED"), None)

        reasons = []
        if fee_diff > tolerance:
            reasons.append(f"Gateway fee variance: expected ₹{expected_gw_fee}, actual ₹{actual_gw_fee}")
        if gst_diff > tolerance:
            reasons.append(f"GST 18% variance: expected ₹{expected_gst}, actual ₹{actual_gst}")
        if tds_diff > tolerance:
            reasons.append(f"TDS 1% variance: expected ₹{expected_tds}, actual ₹{actual_tds}")

        is_variance = len(reasons) > 0
        if is_variance:
            variance_count += 1
            status_val = "VARIANCE_FLAG"
        else:
            pass_count += 1
            status_val = "PASS"

        audit_items.append(
            TaxAuditItem(
                transaction_id=tx_id,
                ledger_id=matching_ledger_id,
                gross_amount=gross_amt,
                fee_percentage=fee_pct,
                expected_gateway_fee=expected_gw_fee,
                actual_gateway_fee=actual_gw_fee,
                expected_gst_18pct=expected_gst,
                actual_gst_18pct=actual_gst,
                expected_tds_1pct=expected_tds,
                actual_tds_1pct=actual_tds,
                fee_variance=fee_diff,
                tax_variance=tax_diff,
                status=status_val,
                discrepancy_reason="; ".join(reasons) if reasons else "Tax lines verified successfully",
            )
        )

    return TaxAuditSummary(
        total_audited_transactions=len(audit_items),
        pass_count=pass_count,
        variance_count=variance_count,
        total_gross_volume=total_gross.quantize(Decimal("0.01")),
        total_expected_gst=total_expected_gst.quantize(Decimal("0.01")),
        total_expected_tds=total_expected_tds.quantize(Decimal("0.01")),
        total_fee_variance=total_fee_variance.quantize(Decimal("0.01")),
        audit_items=audit_items,
    )
