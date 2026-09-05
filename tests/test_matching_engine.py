from datetime import date
from decimal import Decimal
import pytest
from config import Settings
from matching_engine import (
    apply_hard_rules,
    assign_one_to_one_matches,
    classify_candidate,
    evaluate_candidate_edge,
    merchant_similarity,
)
from schemas import CandidateEdge, DecisionSource


@pytest.fixture
def default_settings():
    return Settings(
        AUTO_MATCH_THRESHOLD=0.85,
        BORDERLINE_LOWER=0.65,
        AMOUNT_TOLERANCE=Decimal("0.01"),
        DATE_TOLERANCE_DAYS=3,
        MERCHANT_SIMILARITY_THRESHOLD=0.75,
    )


def test_hard_rules_currency_mismatch(default_settings):
    bank = {"currency": "INR", "utr": "UTR1", "amount": Decimal("100.00"), "transaction_date": date(2026, 8, 1)}
    cand = {"currency": "USD", "utr": "UTR1", "amount": Decimal("100.00"), "invoice_date": date(2026, 8, 1)}
    is_safe, failures = apply_hard_rules(bank, cand, default_settings)
    assert is_safe is False
    assert any("CURRENCY_MISMATCH" in f for f in failures)


def test_hard_rules_conflicting_utr(default_settings):
    bank = {"currency": "INR", "utr": "UTR_BANK_123", "amount": Decimal("100.00"), "transaction_date": date(2026, 8, 1)}
    cand = {"currency": "INR", "utr": "UTR_LEDGER_999", "amount": Decimal("100.00"), "invoice_date": date(2026, 8, 1)}
    is_safe, failures = apply_hard_rules(bank, cand, default_settings)
    assert is_safe is False
    assert any("CONFLICTING_UTR" in f for f in failures)


def test_hard_rules_amount_mismatch(default_settings):
    bank = {"currency": "INR", "utr": "UTR1", "amount": Decimal("100.00"), "transaction_date": date(2026, 8, 1)}
    cand = {"currency": "INR", "utr": "UTR1", "amount": Decimal("100.50"), "invoice_date": date(2026, 8, 1)}
    is_safe, failures = apply_hard_rules(bank, cand, default_settings)
    assert is_safe is False
    assert any("AMOUNT_MISMATCH" in f for f in failures)


def test_hard_rules_date_tolerance(default_settings):
    bank = {"currency": "INR", "utr": "UTR1", "amount": Decimal("100.00"), "transaction_date": date(2026, 8, 1)}
    cand = {"currency": "INR", "utr": "UTR1", "amount": Decimal("100.00"), "invoice_date": date(2026, 8, 10)}  # 9 days diff
    is_safe, failures = apply_hard_rules(bank, cand, default_settings)
    assert is_safe is False
    assert any("DATE_MISMATCH" in f for f in failures)


def test_merchant_fuzzy_similarity():
    sim_exact = merchant_similarity("swiggy bangalore", "swiggy bangalore")
    assert sim_exact == 1.0

    sim_fuzzy = merchant_similarity("swiggy bangalore", "swiggy pvt ltd")
    assert 0.5 <= sim_fuzzy < 1.0


def test_one_to_one_global_assignment_duplicate_prevention(default_settings):
    """
    Critical test:
    Bank TX 1 and Bank TX 2 both compete for Ledger REC 100.
    Bank TX 1 has higher decision_score (0.95 vs 0.88).
    Ledger REC 100 MUST be assigned to Bank TX 1.
    Bank TX 2 MUST NOT be assigned Ledger REC 100, and must be marked DUPLICATE_CONFLICT EXCEPTION!
    """
    b1_id = "BANK_01"
    b2_id = "BANK_02"
    shared_ledger_id = "LEDGER_100"

    edge_b1 = CandidateEdge(
        bank_transaction_id=b1_id,
        ledger_id=shared_ledger_id,
        is_utr_exact_match=True,
        amount_difference=Decimal("0.00"),
        date_difference_days=0,
        merchant_similarity=0.95,
        decision_score=0.95,
        eligible=True,
        candidate_data={"ledger_id": shared_ledger_id, "amount": Decimal("500.00"), "merchant": "Swiggy"},
    )

    edge_b2 = CandidateEdge(
        bank_transaction_id=b2_id,
        ledger_id=shared_ledger_id,
        is_utr_exact_match=False,
        amount_difference=Decimal("0.00"),
        date_difference_days=1,
        merchant_similarity=0.88,
        decision_score=0.88,
        eligible=True,
        candidate_data={"ledger_id": shared_ledger_id, "amount": Decimal("500.00"), "merchant": "Swiggy"},
    )

    eligible_edges = [edge_b1, edge_b2]
    all_bank_records = [
        {"transaction_id": b1_id, "amount": Decimal("500.00"), "merchant": "Swiggy"},
        {"transaction_id": b2_id, "amount": Decimal("500.00"), "merchant": "Swiggy"},
    ]
    bank_to_all_edges = {
        b1_id: [edge_b1],
        b2_id: [edge_b2],
    }
    edge_decision_sources: dict[tuple[str, str], DecisionSource] = {
        (b1_id, shared_ledger_id): "RULE_ENGINE",
        (b2_id, shared_ledger_id): "RULE_ENGINE",
    }
    edge_reasonings = {}

    results = assign_one_to_one_matches(
        eligible_edges=eligible_edges,
        all_bank_records=all_bank_records,
        bank_to_all_edges_map=bank_to_all_edges,
        edge_decision_sources=edge_decision_sources,
        edge_reasonings=edge_reasonings,
    )

    assert len(results) == 2

    res_b1 = next(r for r in results if r.bank_transaction_id == b1_id)
    res_b2 = next(r for r in results if r.bank_transaction_id == b2_id)

    # B1 must be MATCHED to LEDGER_100
    assert res_b1.status == "MATCHED"
    assert res_b1.ledger_id == shared_ledger_id

    # B2 must be EXCEPTION with DUPLICATE_CONFLICT
    assert res_b2.status == "EXCEPTION"
    assert res_b2.decision_source == "DUPLICATE_CONFLICT"
    assert "DUPLICATE_LEDGER_CONFLICT" in res_b2.risk_flags

    # Verification: LEDGER_100 appears in MATCHED status at most once across the entire batch
    matched_ledger_ids = [r.ledger_id for r in results if r.status == "MATCHED"]
    assert len(matched_ledger_ids) == 1
    assert matched_ledger_ids[0] == shared_ledger_id
