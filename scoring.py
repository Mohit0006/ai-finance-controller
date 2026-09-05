from decimal import Decimal
import math


def rrf_score(
    lexical_rank: int,
    semantic_rank: int,
    k: int = 60,
    lexical_weight: float = 2.0,
    semantic_weight: float = 1.0
) -> float:
    """
    Computes standard Reciprocal Rank Fusion (RRF) score.
    RRF is a ranking heuristic, not a calibrated probability or percentage.
    """
    lex_part = lexical_weight / (k + max(1, lexical_rank))
    sem_part = semantic_weight / (k + max(1, semantic_rank))
    return lex_part + sem_part


def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, val))


def calculate_composite_decision_score(
    is_utr_exact: bool,
    amount_diff: Decimal | None,
    amount_tolerance: Decimal,
    date_diff_days: int | None,
    date_tolerance_days: int,
    merchant_lexical_sim: float,
    semantic_score: float,
) -> float:
    """
    Calculates a bounded deterministic decision score in [0.0, 1.0].
    Weights:
      - UTR exact match: 0.35
      - Amount match / proximity: 0.30
      - Date match / proximity: 0.15
      - Merchant lexical similarity: 0.10
      - Semantic similarity: 0.10
    """
    score = 0.0

    # 1. UTR Match Component (0.35)
    if is_utr_exact:
        score += 0.35

    # 2. Amount Component (0.30)
    if amount_diff is not None:
        if amount_diff <= amount_tolerance:
            score += 0.30
        else:
            # Gradual penalty for amount difference
            penalty = float(amount_diff / max(Decimal("100.00"), amount_diff))
            score += max(0.0, 0.30 * (1.0 - penalty))

    # 3. Date Component (0.15)
    if date_diff_days is not None:
        abs_days = abs(date_diff_days)
        if abs_days == 0:
            score += 0.15
        elif abs_days <= date_tolerance_days:
            decay = (date_tolerance_days - abs_days + 1) / (date_tolerance_days + 1)
            score += 0.15 * decay
        else:
            score += 0.0

    # 4. Merchant Lexical Similarity (0.10)
    score += 0.10 * clamp(merchant_lexical_sim, 0.0, 1.0)

    # 5. Semantic Similarity (0.10)
    score += 0.10 * clamp(semantic_score, 0.0, 1.0)

    return round(clamp(score, 0.0, 1.0), 4)
