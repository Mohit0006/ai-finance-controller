from datetime import date
from decimal import Decimal
import polars as pl
import pytest
from data_processing import (
    clean_amount_decimal,
    normalize_merchant,
    parse_strict_date,
    preprocess_bank,
    preprocess_ledger,
    validate_columns,
)


def test_merchant_normalization():
    assert normalize_merchant("Swiggy, Bangalore!") == "swiggy bangalore"
    assert normalize_merchant("  ZOMATO  MEDIA   PVT. LTD. ") == "zomato media pvt ltd"
    assert normalize_merchant("Amazon Pay @ India") == "amazon pay india"
    assert normalize_merchant(None) == ""


def test_clean_amount_decimal():
    # Valid currencies and formats
    amt, err = clean_amount_decimal("₹1,500.50")
    assert amt == Decimal("1500.50")
    assert err is None

    amt, err = clean_amount_decimal("$250.00")
    assert amt == Decimal("250.00")
    assert err is None

    amt, err = clean_amount_decimal("  4,200.75  ")
    assert amt == Decimal("4200.75")
    assert err is None

    # Invalid formats
    amt, err = clean_amount_decimal("abc")
    assert amt is None
    assert err is not None

    amt, err = clean_amount_decimal(None)
    assert amt is None
    assert err is not None


def test_parse_strict_date():
    # ISO formats
    d, err = parse_strict_date("2026-08-01")
    assert d == date(2026, 8, 1)
    assert err is None

    d, err = parse_strict_date("2026-08-01T14:30:00")
    assert d == date(2026, 8, 1)
    assert err is None

    # DD-MM-YYYY and DD/MM/YYYY
    d, err = parse_strict_date("05-08-2026")
    assert d == date(2026, 8, 5)
    assert err is None

    d, err = parse_strict_date("15/08/2026")
    assert d == date(2026, 8, 15)
    assert err is None

    # Ambiguous or invalid
    d, err = parse_strict_date("2026/13/45")
    assert d is None
    assert err is not None

    d, err = parse_strict_date("invalid-date")
    assert d is None
    assert err is not None


def test_validate_columns():
    df_valid = pl.DataFrame({
        "transaction_id": ["TX1"],
        "utr": ["UTR1"],
        "amount": ["100"],
        "currency": ["INR"],
        "transaction_date": ["2026-08-01"],
        "merchant": ["Swiggy"],
    })
    is_valid, errors = validate_columns(df_valid, ["transaction_id", "utr", "amount", "currency", "transaction_date", "merchant"])
    assert is_valid is True
    assert len(errors) == 0

    df_invalid = pl.DataFrame({
        "transaction_id": ["TX1"],
        "amount": ["100"],
    })
    is_valid, errors = validate_columns(df_invalid, ["transaction_id", "utr", "amount", "currency", "transaction_date", "merchant"])
    assert is_valid is False
    assert len(errors) > 0


def test_preprocess_bank_and_ledger_raw_preservation():
    bank_df = pl.DataFrame({
        "transaction_id": ["B01"],
        "utr": ["UTR123"],
        "amount": ["₹1,250.00"],
        "currency": ["inr"],
        "transaction_date": ["2026-08-01"],
        "merchant": ["Swiggy, India!"],
    })

    records, errors = preprocess_bank(bank_df)
    assert len(errors) == 0
    assert len(records) == 1
    rec = records[0]
    assert rec["transaction_id"] == "B01"
    assert rec["amount"] == Decimal("1250.00")
    assert rec["amount_raw"] == "₹1,250.00"
    assert rec["currency"] == "INR"
    assert rec["merchant_normalized"] == "swiggy india"
    assert rec["merchant_raw"] == "Swiggy, India!"
    assert rec["transaction_date"] == date(2026, 8, 1)
    assert rec["date_raw"] == "2026-08-01"
