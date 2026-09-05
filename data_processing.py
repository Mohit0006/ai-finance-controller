from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import io
import re
from typing import Any
import polars as pl
from schemas import RowValidationError

BANK_REQUIRED_COLUMNS = [
    "transaction_id",
    "utr",
    "amount",
    "currency",
    "transaction_date",
    "merchant",
]

LEDGER_REQUIRED_COLUMNS = [
    "ledger_id",
    "invoice_id",
    "utr",
    "amount",
    "currency",
    "invoice_date",
    "merchant",
]

SUPPORTED_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
]

PUNCTUATION_REGEX = re.compile(r"[^\w\s]")
WHITESPACE_REGEX = re.compile(r"\s+")
AMOUNT_CLEAN_REGEX = re.compile(r"[^\d.-]")


def validate_columns(df: pl.DataFrame, required_columns: list[str]) -> tuple[bool, list[RowValidationError]]:
    errors: list[RowValidationError] = []
    columns = set(df.columns)
    for col in required_columns:
        if col not in columns:
            errors.append(
                RowValidationError(
                    row_number=0,
                    field=col,
                    message=f"Missing required column: '{col}'"
                )
            )
    return len(errors) == 0, errors


def normalize_merchant(text: Any) -> str:
    if text is None:
        return ""
    s = str(text).lower()
    s = PUNCTUATION_REGEX.sub(" ", s)
    s = WHITESPACE_REGEX.sub(" ", s).strip()
    return s


def clean_amount_decimal(val: Any) -> tuple[Decimal | None, str | None]:
    if val is None:
        return None, "Amount is empty or null"
    s = str(val).strip()
    if not s:
        return None, "Amount is empty"
    
    # Remove currency symbols, commas, and extra spaces
    cleaned = AMOUNT_CLEAN_REGEX.sub("", s)
    if not cleaned or cleaned in ("-", ".", "-."):
        return None, f"Invalid amount format: '{s}'"
    
    try:
        dec = Decimal(cleaned).quantize(Decimal("0.01"))
        return dec, None
    except (InvalidOperation, ValueError):
        return None, f"Could not parse amount into Decimal: '{s}'"


def parse_strict_date(val: Any) -> tuple[date | None, str | None]:
    if val is None:
        return None, "Date is empty or null"
    s = str(val).strip()
    if not s:
        return None, "Date is empty"

    # Try ISO datetime format first (e.g. 2026-08-01T12:00:00 or 2026-08-01 12:00:00)
    if "t" in s.lower() or ":" in s:
        try:
            # Clean possible trailing Z
            iso_str = s.replace("Z", "").replace("z", "")
            dt = datetime.fromisoformat(iso_str)
            return dt.date(), None
        except ValueError:
            pass

    # Try explicit date formats
    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date(), None
        except ValueError:
            continue

    return None, f"Date '{s}' does not match supported formats: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, or ISO datetime."


def read_csv_bytes_to_polars(csv_bytes: bytes) -> pl.DataFrame:
    return pl.read_csv(io.BytesIO(csv_bytes), infer_schema_length=0)


def preprocess_bank(df: pl.DataFrame) -> tuple[list[dict[str, Any]], list[RowValidationError]]:
    valid_cols, errors = validate_columns(df, BANK_REQUIRED_COLUMNS)
    if not valid_cols:
        return [], errors

    cleaned_records: list[dict[str, Any]] = []
    
    for row_idx, row in enumerate(df.iter_rows(named=True), start=1):
        tx_id = str(row.get("transaction_id") or "").strip()
        if not tx_id:
            errors.append(RowValidationError(row_number=row_idx, field="transaction_id", message="transaction_id cannot be empty"))
            continue

        raw_amount = row.get("amount")
        dec_amount, amt_err = clean_amount_decimal(raw_amount)
        if amt_err:
            errors.append(RowValidationError(row_number=row_idx, field="amount", message=amt_err))
            continue

        raw_date = row.get("transaction_date")
        parsed_date, date_err = parse_strict_date(raw_date)
        if date_err:
            errors.append(RowValidationError(row_number=row_idx, field="transaction_date", message=date_err))
            continue

        raw_currency = str(row.get("currency") or "").strip().upper()
        if not raw_currency:
            errors.append(RowValidationError(row_number=row_idx, field="currency", message="currency cannot be empty"))
            continue

        raw_merchant = str(row.get("merchant") or "")
        merchant_norm = normalize_merchant(raw_merchant)
        raw_utr = str(row.get("utr") or "").strip()
        utr_val = raw_utr if raw_utr and raw_utr.lower() not in ("nan", "none", "null") else None

        # Optional fee and tax fields
        fee_pct_raw = row.get("fee_percentage")
        fee_pct_dec, _ = clean_amount_decimal(fee_pct_raw) if fee_pct_raw is not None else (None, None)
        
        gw_fee_raw = row.get("gateway_fee")
        gw_fee_dec, _ = clean_amount_decimal(gw_fee_raw) if gw_fee_raw is not None else (None, None)

        gst_raw = row.get("gst_amount")
        gst_dec, _ = clean_amount_decimal(gst_raw) if gst_raw is not None else (None, None)

        tds_raw = row.get("tds_amount")
        tds_dec, _ = clean_amount_decimal(tds_raw) if tds_raw is not None else (None, None)

        settlement_date_raw = row.get("settlement_date")
        settlement_date_parsed, _ = parse_strict_date(settlement_date_raw) if settlement_date_raw is not None else (None, None)

        tx_type = str(row.get("type") or "CREDIT").strip().upper()

        cleaned_records.append({
            "transaction_id": tx_id,
            "utr": utr_val,
            "amount": dec_amount,
            "amount_raw": str(raw_amount or ""),
            "currency": raw_currency,
            "transaction_date": parsed_date,
            "date_raw": str(raw_date or ""),
            "merchant": raw_merchant,
            "merchant_raw": raw_merchant,
            "merchant_normalized": merchant_norm,
            "fee_percentage": fee_pct_dec,
            "gateway_fee": gw_fee_dec,
            "gst_amount": gst_dec,
            "tds_amount": tds_dec,
            "settlement_date": settlement_date_parsed,
            "type": tx_type if tx_type in ("CREDIT", "DEBIT", "INFLOW", "OUTFLOW") else "CREDIT",
            "row_number": row_idx,
        })

    return cleaned_records, errors


def preprocess_ledger(df: pl.DataFrame) -> tuple[list[dict[str, Any]], list[RowValidationError]]:
    valid_cols, errors = validate_columns(df, LEDGER_REQUIRED_COLUMNS)
    if not valid_cols:
        return [], errors

    cleaned_records: list[dict[str, Any]] = []

    for row_idx, row in enumerate(df.iter_rows(named=True), start=1):
        ledger_id = str(row.get("ledger_id") or "").strip()
        if not ledger_id:
            errors.append(RowValidationError(row_number=row_idx, field="ledger_id", message="ledger_id cannot be empty"))
            continue

        raw_amount = row.get("amount")
        dec_amount, amt_err = clean_amount_decimal(raw_amount)
        if amt_err:
            errors.append(RowValidationError(row_number=row_idx, field="amount", message=amt_err))
            continue

        raw_date = row.get("invoice_date")
        parsed_date, date_err = parse_strict_date(raw_date)
        if date_err:
            errors.append(RowValidationError(row_number=row_idx, field="invoice_date", message=date_err))
            continue

        raw_currency = str(row.get("currency") or "").strip().upper()
        if not raw_currency:
            errors.append(RowValidationError(row_number=row_idx, field="currency", message="currency cannot be empty"))
            continue

        raw_merchant = str(row.get("merchant") or "")
        merchant_norm = normalize_merchant(raw_merchant)
        raw_utr = str(row.get("utr") or "").strip()
        utr_val = raw_utr if raw_utr and raw_utr.lower() not in ("nan", "none", "null") else None
        invoice_id_raw = str(row.get("invoice_id") or "").strip()
        invoice_id_val = invoice_id_raw if invoice_id_raw and invoice_id_raw.lower() not in ("nan", "none", "null") else None

        fee_pct_raw = row.get("fee_percentage")
        fee_pct_dec, _ = clean_amount_decimal(fee_pct_raw) if fee_pct_raw is not None else (None, None)

        gw_fee_raw = row.get("gateway_fee")
        gw_fee_dec, _ = clean_amount_decimal(gw_fee_raw) if gw_fee_raw is not None else (None, None)

        gst_raw = row.get("gst_amount")
        gst_dec, _ = clean_amount_decimal(gst_raw) if gst_raw is not None else (None, None)

        tds_raw = row.get("tds_amount")
        tds_dec, _ = clean_amount_decimal(tds_raw) if tds_raw is not None else (None, None)

        settlement_date_raw = row.get("settlement_date")
        settlement_date_parsed, _ = parse_strict_date(settlement_date_raw) if settlement_date_raw is not None else (None, None)

        entry_type = str(row.get("type") or "CREDIT").strip().upper()

        cleaned_records.append({
            "ledger_id": ledger_id,
            "invoice_id": invoice_id_val,
            "utr": utr_val,
            "amount": dec_amount,
            "amount_raw": str(raw_amount or ""),
            "currency": raw_currency,
            "invoice_date": parsed_date,
            "date_raw": str(raw_date or ""),
            "merchant": raw_merchant,
            "merchant_raw": raw_merchant,
            "merchant_normalized": merchant_norm,
            "fee_percentage": fee_pct_dec,
            "gateway_fee": gw_fee_dec,
            "gst_amount": gst_dec,
            "tds_amount": tds_dec,
            "settlement_date": settlement_date_parsed,
            "type": entry_type if entry_type in ("CREDIT", "DEBIT", "INFLOW", "OUTFLOW") else "CREDIT",
            "row_number": row_idx,
        })

    return cleaned_records, errors
