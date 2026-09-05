from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field

DecisionSource = Literal[
    "RULE_ENGINE",
    "GEMINI",
    "NO_CANDIDATE",
    "VALIDATION",
    "DUPLICATE_CONFLICT",
    "DATA_VALIDATION",
]

BatchStatus = Literal["PROCESSING", "COMPLETED", "FAILED"]
MatchStatus = Literal["MATCHED", "EXCEPTION"]
GeminiStatus = Literal["configured", "disabled", "unavailable"]


class RowValidationError(BaseModel):
    row_number: int
    field: str
    message: str


class ErrorResponse(BaseModel):
    detail: str
    validation_errors: list[RowValidationError] = Field(default_factory=list)


class CandidateEdge(BaseModel):
    bank_transaction_id: str
    ledger_id: str
    is_utr_exact_match: bool = False
    amount_difference: Decimal | None = None
    date_difference_days: int | None = None
    merchant_similarity: float | None = None
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    fused_score: float = 0.0
    decision_score: float = 0.0
    hard_rule_failures: list[str] = Field(default_factory=list)
    eligible: bool = False
    candidate_data: dict[str, Any] = Field(default_factory=dict)


class GeminiDecision(BaseModel):
    status: Literal["MATCHED", "EXCEPTION"]
    reasoning: str
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class ReconciliationResultItem(BaseModel):
    bank_transaction_id: str
    ledger_id: str | None = None
    status: MatchStatus
    decision_source: DecisionSource
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    fused_score: float = 0.0
    decision_score: float = 0.0
    is_utr_exact_match: bool = False
    amount_difference: Decimal | None = None
    date_difference_days: int | None = None
    merchant_similarity: float | None = None
    reasoning: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    candidate_evidence: dict[str, Any] = Field(default_factory=dict)


class ReconciliationMetrics(BaseModel):
    total_bank_records: int
    total_ledger_records: int
    matched_count: int
    exception_count: int
    auto_match_rate: float
    precision: float | None = None
    recall: float | None = None
    false_positive_count: int | None = None
    unresolved_exception_count: int
    processing_time_seconds: float
    throughput_records_per_second: float
    ground_truth_available: bool
    metrics_scope: Literal["synthetic_ground_truth", "execution_only"]


class HealthResponse(BaseModel):
    status: str
    database: str
    vector_extension: str
    embedding_model: str
    gemini: GeminiStatus


class CashPositionSummary(BaseModel):
    book_balance: Decimal
    bank_balance: Decimal
    reconciled_cash_inflow: Decimal
    reconciled_cash_outflow: Decimal
    uncleared_float: Decimal
    discrepancy_variance: Decimal
    currency: str = "INR"
    reconciliation_status: str


class ForecastDailyPoint(BaseModel):
    day_offset: int
    forecast_date: str
    base_projected_balance: Decimal
    optimistic_projected_balance: Decimal
    conservative_projected_balance: Decimal
    expected_inflows: Decimal
    expected_outflows: Decimal
    reserve_breached: bool = False


class ForwardCashForecast(BaseModel):
    start_date: str
    daily_projections: list[ForecastDailyPoint]
    base_ending_balance: Decimal
    optimistic_ending_balance: Decimal
    conservative_ending_balance: Decimal
    minimum_reserve_threshold: Decimal
    has_reserve_breach: bool
    breach_days: list[int] = Field(default_factory=list)


class TaxAuditItem(BaseModel):
    transaction_id: str
    ledger_id: str | None = None
    gross_amount: Decimal
    fee_percentage: Decimal
    expected_gateway_fee: Decimal
    actual_gateway_fee: Decimal
    expected_gst_18pct: Decimal
    actual_gst_18pct: Decimal
    expected_tds_1pct: Decimal
    actual_tds_1pct: Decimal
    fee_variance: Decimal
    tax_variance: Decimal
    status: Literal["PASS", "VARIANCE_FLAG"]
    discrepancy_reason: str = ""


class TaxAuditSummary(BaseModel):
    total_audited_transactions: int
    pass_count: int
    variance_count: int
    total_gross_volume: Decimal
    total_expected_gst: Decimal
    total_expected_tds: Decimal
    total_fee_variance: Decimal
    audit_items: list[TaxAuditItem]


class SettlementQARequest(BaseModel):
    batch_id: str
    question: str
    history: list[dict[str, str]] = Field(default_factory=list)


class SettlementQAResponse(BaseModel):
    batch_id: str
    question: str
    answer: str
    source: Literal["GEMINI_LLM", "STRUCTURED_FALLBACK"]
    citations: list[dict[str, Any]] = Field(default_factory=list)
    key_metrics_referenced: dict[str, Any] = Field(default_factory=dict)


class ReconcileResponse(BaseModel):
    batch_id: str
    status: BatchStatus
    metrics: ReconciliationMetrics
    results: list[ReconciliationResultItem]
    validation_errors: list[RowValidationError] = Field(default_factory=list)
    cash_position: CashPositionSummary | None = None
    forecast: ForwardCashForecast | None = None
    tax_audit: TaxAuditSummary | None = None

