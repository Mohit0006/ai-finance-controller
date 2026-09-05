from typing import Any, Optional
from schemas import ReconciliationMetrics, ReconciliationResultItem


def calculate_reconciliation_metrics(
    results: list[ReconciliationResultItem],
    total_bank_records: int,
    total_ledger_records: int,
    processing_time_seconds: float,
    ground_truth: Optional[list[dict[str, Any]]] = None,
) -> ReconciliationMetrics:
    matched_count = sum(1 for r in results if r.status == "MATCHED")
    exception_count = sum(1 for r in results if r.status == "EXCEPTION")
    
    auto_match_rate = round(matched_count / total_bank_records, 4) if total_bank_records > 0 else 0.0
    throughput = round(total_bank_records / max(0.001, processing_time_seconds), 2)

    if not ground_truth:
        return ReconciliationMetrics(
            total_bank_records=total_bank_records,
            total_ledger_records=total_ledger_records,
            matched_count=matched_count,
            exception_count=exception_count,
            auto_match_rate=auto_match_rate,
            precision=None,
            recall=None,
            false_positive_count=None,
            unresolved_exception_count=exception_count,
            processing_time_seconds=round(processing_time_seconds, 3),
            throughput_records_per_second=throughput,
            ground_truth_available=False,
            metrics_scope="execution_only",
        )

    # Ground truth evaluation
    gt_map = {str(gt.get("bank_transaction_id") or "").strip(): gt for gt in ground_truth}
    
    true_positive_matches = 0
    false_positive_count = 0
    total_expected_matches = sum(
        1 for gt in ground_truth if str(gt.get("expected_status") or "").strip().upper() == "MATCHED"
    )

    for res in results:
        if res.status == "MATCHED":
            gt_item = gt_map.get(res.bank_transaction_id)
            if gt_item is not None:
                exp_status = str(gt_item.get("expected_status") or "").strip().upper()
                exp_ledger = str(gt_item.get("expected_ledger_id") or "").strip()
                pred_ledger = (res.ledger_id or "").strip()

                if exp_status == "MATCHED" and pred_ledger == exp_ledger:
                    true_positive_matches += 1
                else:
                    false_positive_count += 1
            else:
                false_positive_count += 1

    predicted_matches = matched_count
    precision = round(true_positive_matches / predicted_matches, 4) if predicted_matches > 0 else 0.0
    recall = round(true_positive_matches / total_expected_matches, 4) if total_expected_matches > 0 else 0.0

    return ReconciliationMetrics(
        total_bank_records=total_bank_records,
        total_ledger_records=total_ledger_records,
        matched_count=matched_count,
        exception_count=exception_count,
        auto_match_rate=auto_match_rate,
        precision=precision,
        recall=recall,
        false_positive_count=false_positive_count,
        unresolved_exception_count=exception_count,
        processing_time_seconds=round(processing_time_seconds, 3),
        throughput_records_per_second=throughput,
        ground_truth_available=True,
        metrics_scope="synthetic_ground_truth",
    )
