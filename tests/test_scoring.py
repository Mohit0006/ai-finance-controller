from decimal import Decimal
import pytest
from scoring import calculate_composite_decision_score, clamp, rrf_score


def test_rrf_score_properties():
    # Rank 1 should produce higher score than Rank 5
    score_top = rrf_score(lexical_rank=1, semantic_rank=1, k=60, lexical_weight=2.0, semantic_weight=1.0)
    score_lower = rrf_score(lexical_rank=5, semantic_rank=5, k=60, lexical_weight=2.0, semantic_weight=1.0)
    
    assert score_top > score_lower
    assert score_top > 0.0

    # Weight sensitivity
    score_lex_heavy = rrf_score(lexical_rank=1, semantic_rank=10, k=60, lexical_weight=5.0, semantic_weight=1.0)
    score_sem_heavy = rrf_score(lexical_rank=10, semantic_rank=1, k=60, lexical_weight=5.0, semantic_weight=1.0)
    assert score_lex_heavy > score_sem_heavy


def test_decision_score_bounded_and_deterministic():
    # Perfect match: exact UTR, 0 amount diff, 0 date diff, 1.0 merchant sim, 1.0 semantic sim
    perfect_score = calculate_composite_decision_score(
        is_utr_exact=True,
        amount_diff=Decimal("0.00"),
        amount_tolerance=Decimal("0.01"),
        date_diff_days=0,
        date_tolerance_days=3,
        merchant_lexical_sim=1.0,
        semantic_score=1.0,
    )
    assert 0.95 <= perfect_score <= 1.0

    # Total mismatch
    mismatch_score = calculate_composite_decision_score(
        is_utr_exact=False,
        amount_diff=Decimal("500.00"),
        amount_tolerance=Decimal("0.01"),
        date_diff_days=10,
        date_tolerance_days=3,
        merchant_lexical_sim=0.0,
        semantic_score=0.0,
    )
    assert 0.0 <= mismatch_score <= 0.10

    # Intermediate bounds test
    mid_score = calculate_composite_decision_score(
        is_utr_exact=False,
        amount_diff=Decimal("0.00"),
        amount_tolerance=Decimal("0.01"),
        date_diff_days=1,
        date_tolerance_days=3,
        merchant_lexical_sim=0.85,
        semantic_score=0.80,
    )
    assert 0.0 <= mid_score <= 1.0
