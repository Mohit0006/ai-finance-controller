from datetime import date
from decimal import Decimal
import difflib
from typing import Any, Literal
from config import Settings, get_settings
from schemas import CandidateEdge, DecisionSource, ReconciliationResultItem
from scoring import calculate_composite_decision_score, clamp


def amount_difference(bank_amount: Decimal, ledger_amount: Decimal) -> Decimal:
    return abs(bank_amount - ledger_amount)


def date_difference_days(bank_date: date, ledger_date: date) -> int:
    return (bank_date - ledger_date).days


def merchant_similarity(bank_merchant: str, ledger_merchant: str) -> float:
    b = bank_merchant.strip().lower()
    l = ledger_merchant.strip().lower()
    if not b or not l:
        return 0.0
    if b == l:
        return 1.0
    return difflib.SequenceMatcher(None, b, l).ratio()


def lexical_score(bank_record: dict[str, Any], candidate: dict[str, Any], settings: Settings) -> float:
    score = 0.0
    # 1. Exact UTR
    b_utr = bank_record.get("utr")
    l_utr = candidate.get("utr")
    if b_utr and l_utr and b_utr.strip().lower() == l_utr.strip().lower():
        score += 0.40

    # 2. Currency equality
    b_curr = bank_record.get("currency")
    l_curr = candidate.get("currency")
    if b_curr and l_curr and b_curr.strip().upper() == l_curr.strip().upper():
        score += 0.20

    # 3. Amount tolerance
    b_amt = bank_record.get("amount")
    l_amt = candidate.get("amount")
    if b_amt is not None and l_amt is not None:
        if amount_difference(b_amt, l_amt) <= settings.AMOUNT_TOLERANCE:
            score += 0.20

    # 4. Date tolerance
    b_date = bank_record.get("transaction_date")
    l_date = candidate.get("invoice_date")
    if b_date and l_date:
        if abs(date_difference_days(b_date, l_date)) <= settings.DATE_TOLERANCE_DAYS:
            score += 0.10

    # 5. Merchant lexical ratio
    b_merch = bank_record.get("merchant_normalized") or bank_record.get("merchant") or ""
    l_merch = candidate.get("merchant_normalized") or candidate.get("merchant") or ""
    m_sim = merchant_similarity(b_merch, l_merch)
    score += 0.10 * m_sim

    return round(clamp(score, 0.0, 1.0), 4)


def semantic_score_from_distance(cosine_distance: float) -> float:
    """
    Cosine distance <=> ranges in [0, 2] for unit vectors.
    Semantic similarity is clamp(1.0 - cosine_distance, 0.0, 1.0).
    """
    return round(clamp(1.0 - cosine_distance, 0.0, 1.0), 4)


def apply_hard_rules(
    bank_record: dict[str, Any],
    candidate: dict[str, Any],
    settings: Settings
) -> tuple[bool, list[str]]:
    failures: list[str] = []

    # 1. Currency equality check
    b_curr = (bank_record.get("currency") or "").strip().upper()
    l_curr = (candidate.get("currency") or "").strip().upper()
    if b_curr != l_curr:
        failures.append(f"CURRENCY_MISMATCH: Bank '{b_curr}' vs Ledger '{l_curr}'")

    # 2. Conflicting non-empty UTR
    b_utr = (bank_record.get("utr") or "").strip()
    l_utr = (candidate.get("utr") or "").strip()
    if b_utr and l_utr and b_utr.lower() != l_utr.lower():
        failures.append(f"CONFLICTING_UTR: Bank UTR '{b_utr}' != Ledger UTR '{l_utr}'")

    # 3. Amount tolerance check
    b_amt = bank_record.get("amount")
    l_amt = candidate.get("amount")
    if b_amt is None or l_amt is None:
        failures.append("MISSING_AMOUNT: Amount missing in one or both records")
    else:
        diff_amt = amount_difference(b_amt, l_amt)
        if diff_amt > settings.AMOUNT_TOLERANCE:
            failures.append(f"AMOUNT_MISMATCH: Difference {diff_amt} exceeds tolerance {settings.AMOUNT_TOLERANCE}")

    # 4. Date tolerance check
    b_date = bank_record.get("transaction_date")
    l_date = candidate.get("invoice_date")
    if b_date is None or l_date is None:
        failures.append("MISSING_DATE: Date missing in one or both records")
    else:
        diff_days = abs(date_difference_days(b_date, l_date))
        if diff_days > settings.DATE_TOLERANCE_DAYS:
            failures.append(f"DATE_MISMATCH: Difference {diff_days} days exceeds tolerance {settings.DATE_TOLERANCE_DAYS} days")

    return len(failures) == 0, failures


def evaluate_candidate_edge(
    bank_record: dict[str, Any],
    candidate: dict[str, Any],
    settings: Settings
) -> CandidateEdge:
    b_id = str(bank_record.get("transaction_id"))
    l_id = str(candidate.get("ledger_id"))

    # UTR exact match
    b_utr = (bank_record.get("utr") or "").strip()
    l_utr = (candidate.get("utr") or "").strip()
    is_utr_exact = bool(b_utr and l_utr and b_utr.lower() == l_utr.lower())

    # Amount difference
    b_amt = bank_record.get("amount")
    l_amt = candidate.get("amount")
    amt_diff = amount_difference(b_amt, l_amt) if (b_amt is not None and l_amt is not None) else None

    # Date difference
    b_date = bank_record.get("transaction_date")
    l_date = candidate.get("invoice_date")
    date_diff = date_difference_days(b_date, l_date) if (b_date and l_date) else None

    # Merchant similarity
    b_merch = bank_record.get("merchant_normalized") or bank_record.get("merchant") or ""
    l_merch = candidate.get("merchant_normalized") or candidate.get("merchant") or ""
    m_sim = merchant_similarity(b_merch, l_merch)

    # Lexical and Semantic scores
    lex_score = lexical_score(bank_record, candidate, settings)
    cosine_dist = candidate.get("cosine_distance", 1.0)
    sem_score = semantic_score_from_distance(cosine_dist)

    # Hard rules evaluation
    passed_hard_rules, hard_rule_failures = apply_hard_rules(bank_record, candidate, settings)

    # Decision score
    dec_score = calculate_composite_decision_score(
        is_utr_exact=is_utr_exact,
        amount_diff=amt_diff,
        amount_tolerance=settings.AMOUNT_TOLERANCE,
        date_diff_days=date_diff,
        date_tolerance_days=settings.DATE_TOLERANCE_DAYS,
        merchant_lexical_sim=m_sim,
        semantic_score=sem_score,
    )

    return CandidateEdge(
        bank_transaction_id=b_id,
        ledger_id=l_id,
        is_utr_exact_match=is_utr_exact,
        amount_difference=amt_diff,
        date_difference_days=date_diff,
        merchant_similarity=m_sim,
        lexical_score=lex_score,
        semantic_score=sem_score,
        fused_score=round((lex_score + sem_score) / 2.0, 4),
        decision_score=dec_score,
        hard_rule_failures=hard_rule_failures,
        eligible=passed_hard_rules,
        candidate_data=candidate,
    )


def classify_candidate(
    edge: CandidateEdge,
    settings: Settings
) -> Literal["clearly_safe", "borderline", "ineligible"]:
    if not edge.eligible:
        return "ineligible"

    # Clearly safe conditions:
    # 1. Exact UTR match and decision score >= AUTO_MATCH_THRESHOLD
    # 2. Or high decision score >= AUTO_MATCH_THRESHOLD with merchant similarity >= MERCHANT_SIMILARITY_THRESHOLD
    if edge.is_utr_exact_match and edge.decision_score >= settings.AUTO_MATCH_THRESHOLD:
        return "clearly_safe"
    if edge.decision_score >= settings.AUTO_MATCH_THRESHOLD and (edge.merchant_similarity or 0.0) >= settings.MERCHANT_SIMILARITY_THRESHOLD:
        return "clearly_safe"

    # Borderline condition:
    # Must pass hard rules (already checked by eligible) and decision score in [BORDERLINE_LOWER, AUTO_MATCH_THRESHOLD)
    if settings.BORDERLINE_LOWER <= edge.decision_score < settings.AUTO_MATCH_THRESHOLD:
        return "borderline"

    # If score is below borderline lower or doesn't meet criteria
    return "ineligible"


def sort_candidate_edges(edges: list[CandidateEdge]) -> list[CandidateEdge]:
    """
    Deterministic sort order:
    1. decision_score descending;
    2. is_utr_exact_match descending;
    3. absolute amount_difference ascending, with null values last;
    4. absolute date_difference_days ascending, with null values last;
    5. merchant_similarity descending, with null values last;
    6. ledger_id ascending.
    """
    return sorted(
        edges,
        key=lambda e: (
            -e.decision_score,
            0 if e.is_utr_exact_match else 1,
            abs(e.amount_difference) if e.amount_difference is not None else Decimal("999999999"),
            abs(e.date_difference_days) if e.date_difference_days is not None else 999999,
            -(e.merchant_similarity if e.merchant_similarity is not None else -1.0),
            e.ledger_id,
        )
    )


def assign_one_to_one_matches(
    eligible_edges: list[CandidateEdge],
    all_bank_records: list[dict[str, Any]],
    bank_to_all_edges_map: dict[str, list[CandidateEdge]],
    edge_decision_sources: dict[tuple[str, str], DecisionSource],
    edge_reasonings: dict[tuple[str, str], str],
) -> list[ReconciliationResultItem]:
    sorted_edges = sort_candidate_edges(eligible_edges)

    assigned_bank_ids: set[str] = set()
    assigned_ledger_ids: set[str] = set()
    final_results: list[ReconciliationResultItem] = []

    # Map bank records for lookup
    bank_records_by_id = {str(b["transaction_id"]): b for b in all_bank_records}

    # 1. Global 1:1 assignment
    for edge in sorted_edges:
        if edge.bank_transaction_id in assigned_bank_ids:
            continue
        if edge.ledger_id in assigned_ledger_ids:
            continue

        assigned_bank_ids.add(edge.bank_transaction_id)
        assigned_ledger_ids.add(edge.ledger_id)

        source = edge_decision_sources.get((edge.bank_transaction_id, edge.ledger_id), "RULE_ENGINE")
        reasoning = edge_reasonings.get(
            (edge.bank_transaction_id, edge.ledger_id),
            "Matched via deterministic rule engine with verified financial and identity constraints."
        )

        final_results.append(
            ReconciliationResultItem(
                bank_transaction_id=edge.bank_transaction_id,
                ledger_id=edge.ledger_id,
                status="MATCHED",
                decision_source=source,
                lexical_score=edge.lexical_score,
                semantic_score=edge.semantic_score,
                fused_score=edge.fused_score,
                decision_score=edge.decision_score,
                is_utr_exact_match=edge.is_utr_exact_match,
                amount_difference=edge.amount_difference,
                date_difference_days=edge.date_difference_days,
                merchant_similarity=edge.merchant_similarity,
                reasoning=reasoning,
                missing_fields=[],
                risk_flags=[],
                candidate_evidence={
                    "ledger_id": edge.ledger_id,
                    "ledger_merchant": edge.candidate_data.get("merchant"),
                    "ledger_amount": str(edge.candidate_data.get("amount")),
                    "ledger_date": str(edge.candidate_data.get("invoice_date")),
                    "ledger_utr": edge.candidate_data.get("utr"),
                }
            )
        )

    # 2. Process unassigned bank records
    for bank_record in all_bank_records:
        b_id = str(bank_record["transaction_id"])
        if b_id in assigned_bank_ids:
            continue

        all_edges_for_bank = bank_to_all_edges_map.get(b_id, [])

        if not all_edges_for_bank:
            # Case: No candidate returned
            final_results.append(
                ReconciliationResultItem(
                    bank_transaction_id=b_id,
                    ledger_id=None,
                    status="EXCEPTION",
                    decision_source="NO_CANDIDATE",
                    lexical_score=0.0,
                    semantic_score=0.0,
                    fused_score=0.0,
                    decision_score=0.0,
                    is_utr_exact_match=False,
                    amount_difference=None,
                    date_difference_days=None,
                    merchant_similarity=None,
                    reasoning="No ledger candidates retrieved for this transaction.",
                    missing_fields=[],
                    risk_flags=["NO_CANDIDATES_FOUND"],
                    candidate_evidence={}
                )
            )
        else:
            # Pick best evaluated candidate for diagnostic reporting
            best_edge = sort_candidate_edges(all_edges_for_bank)[0]

            # Check if this bank had an otherwise eligible edge whose ledger was assigned to someone else
            had_eligible_conflict = any(e.eligible and (e.ledger_id in assigned_ledger_ids) for e in all_edges_for_bank)

            if had_eligible_conflict:
                final_results.append(
                    ReconciliationResultItem(
                        bank_transaction_id=b_id,
                        ledger_id=best_edge.ledger_id,
                        status="EXCEPTION",
                        decision_source="DUPLICATE_CONFLICT",
                        lexical_score=best_edge.lexical_score,
                        semantic_score=best_edge.semantic_score,
                        fused_score=best_edge.fused_score,
                        decision_score=best_edge.decision_score,
                        is_utr_exact_match=best_edge.is_utr_exact_match,
                        amount_difference=best_edge.amount_difference,
                        date_difference_days=best_edge.date_difference_days,
                        merchant_similarity=best_edge.merchant_similarity,
                        reasoning="Eligible candidate ledger transaction was assigned to a higher-ranked bank transaction under 1:1 constraints.",
                        missing_fields=[],
                        risk_flags=["DUPLICATE_LEDGER_CONFLICT"],
                        candidate_evidence={
                            "competing_ledger_id": best_edge.ledger_id,
                            "decision_score": best_edge.decision_score,
                            "ledger_merchant": best_edge.candidate_data.get("merchant"),
                        }
                    )
                )
            else:
                # Ineligible candidate / hard rule failure
                failures = best_edge.hard_rule_failures or ["FAILED_SCORE_THRESHOLD"]
                final_results.append(
                    ReconciliationResultItem(
                        bank_transaction_id=b_id,
                        ledger_id=best_edge.ledger_id,
                        status="EXCEPTION",
                        decision_source="VALIDATION" if any("MISMATCH" in f or "MISSING" in f for f in failures) else "RULE_ENGINE",
                        lexical_score=best_edge.lexical_score,
                        semantic_score=best_edge.semantic_score,
                        fused_score=best_edge.fused_score,
                        decision_score=best_edge.decision_score,
                        is_utr_exact_match=best_edge.is_utr_exact_match,
                        amount_difference=best_edge.amount_difference,
                        date_difference_days=best_edge.date_difference_days,
                        merchant_similarity=best_edge.merchant_similarity,
                        reasoning=f"Hard safety rule failure or insufficient evidence: {'; '.join(failures)}",
                        missing_fields=[f for f in failures if "MISSING" in f],
                        risk_flags=failures,
                        candidate_evidence={
                            "top_candidate_ledger_id": best_edge.ledger_id,
                            "top_candidate_merchant": best_edge.candidate_data.get("merchant"),
                            "top_candidate_amount": str(best_edge.candidate_data.get("amount")),
                            "top_candidate_date": str(best_edge.candidate_data.get("invoice_date")),
                        }
                    )
                )

    return final_results
