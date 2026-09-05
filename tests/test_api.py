import asyncio
from datetime import date
from decimal import Decimal
import io
import os
import pytest
from fastapi.testclient import TestClient

from config import Settings
from main import app
from metrics import calculate_reconciliation_metrics
from schemas import CandidateEdge, ReconciliationResultItem
from synthetic_data import generate_synthetic_dataset


client = TestClient(app)


def test_health_endpoint_response_structure():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "vector_extension" in data
    assert "embedding_model" in data
    assert "gemini" in data
    assert data["gemini"] in ("configured", "disabled", "unavailable")


def test_metrics_calculation_with_and_without_ground_truth():
    results = [
        ReconciliationResultItem(
            bank_transaction_id="B1",
            ledger_id="L1",
            status="MATCHED",
            decision_source="RULE_ENGINE",
            decision_score=0.98,
            reasoning="Safe match",
        ),
        ReconciliationResultItem(
            bank_transaction_id="B2",
            ledger_id="L2",
            status="MATCHED",
            decision_source="RULE_ENGINE",
            decision_score=0.92,
            reasoning="Safe match",
        ),
        ReconciliationResultItem(
            bank_transaction_id="B3",
            ledger_id=None,
            status="EXCEPTION",
            decision_source="NO_CANDIDATE",
            decision_score=0.0,
            reasoning="No candidate found",
        ),
    ]

    # 1. Without ground truth
    metrics_no_gt = calculate_reconciliation_metrics(
        results=results,
        total_bank_records=3,
        total_ledger_records=3,
        processing_time_seconds=0.15,
        ground_truth=None,
    )
    assert metrics_no_gt.total_bank_records == 3
    assert metrics_no_gt.matched_count == 2
    assert metrics_no_gt.exception_count == 1
    assert metrics_no_gt.auto_match_rate == round(2 / 3, 4)
    assert metrics_no_gt.precision is None
    assert metrics_no_gt.recall is None
    assert metrics_no_gt.ground_truth_available is False
    assert metrics_no_gt.metrics_scope == "execution_only"

    # 2. With ground truth (B1 expected L1 MATCHED, B2 expected L3 MATCHED, B3 expected EXCEPTION)
    gt_data = [
        {"bank_transaction_id": "B1", "expected_ledger_id": "L1", "expected_status": "MATCHED"},
        {"bank_transaction_id": "B2", "expected_ledger_id": "L3", "expected_status": "MATCHED"},  # B2 matched wrong ledger L2
        {"bank_transaction_id": "B3", "expected_ledger_id": None, "expected_status": "EXCEPTION"},
    ]
    metrics_gt = calculate_reconciliation_metrics(
        results=results,
        total_bank_records=3,
        total_ledger_records=3,
        processing_time_seconds=0.20,
        ground_truth=gt_data,
    )
    assert metrics_gt.ground_truth_available is True
    assert metrics_gt.metrics_scope == "synthetic_ground_truth"
    # B1 was TP (1), B2 was FP (predicted L2, expected L3) -> TP = 1, Predicted = 2 -> Precision = 1/2 = 0.5
    # Expected matches = 2 (B1, B2) -> Recall = 1/2 = 0.5
    assert metrics_gt.precision == 0.5
    assert metrics_gt.recall == 0.5
    assert metrics_gt.false_positive_count == 1



def test_synthetic_data_reproducibility(tmp_path):
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"
    os.makedirs(dir1, exist_ok=True)
    os.makedirs(dir2, exist_ok=True)

    generate_synthetic_dataset(str(dir1))
    generate_synthetic_dataset(str(dir2))

    with open(dir1 / "bank.csv", "rb") as f1, open(dir2 / "bank.csv", "rb") as f2:
        assert f1.read() == f2.read()

    with open(dir1 / "ledger.csv", "rb") as f1, open(dir2 / "ledger.csv", "rb") as f2:
        assert f1.read() == f2.read()

    with open(dir1 / "ground_truth.csv", "rb") as f1, open(dir2 / "ground_truth.csv", "rb") as f2:
        assert f1.read() == f2.read()


def test_reconcile_missing_files_422():
    # Calling POST /reconcile without files should return HTTP 422
    response = client.post("/reconcile")
    assert response.status_code == 422


def test_settlement_qa_endpoint():
    response = client.post("/qa/settlement", json={"batch_id": "non_existent_batch", "question": "What is our float?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "source" in data
    assert data["source"] in ("STRUCTURED_FALLBACK", "GEMINI_LLM")

