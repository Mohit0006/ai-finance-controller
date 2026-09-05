import csv
from datetime import date, timedelta
from decimal import Decimal
import os
import random
from typing import Any

# Fixed seed for perfect reproducibility
RANDOM_SEED = 42
BASE_DATE = date(2026, 8, 1)

MERCHANTS = [
    ("Swiggy", ["Swiggy Bangalore", "SWIGGY PVT LTD", "Swiggy Payments", "Bundl Technologies Swiggy"]),
    ("Zomato", ["Zomato Limited", "ZOMATO MEDIA PVT", "Zomato Gurgaon", "Zomato Food Delivery"]),
    ("Uber India", ["Uber Systems India", "UBER TRIP PAYMENT", "Uber BV India", "Uber Technologies"]),
    ("Amazon Pay", ["Amazon Seller Services", "AMAZON PAY INDIA", "Amazon Retail", "AMZN Mktp"]),
    ("Flipkart", ["Flipkart Internet Pvt", "FLIPKART PAYMENTS", "Flipkart India", "FK Shopping"]),
    ("Razorpay Software", ["Razorpay Merchant", "RAZORPAY BANGALORE", "Razorpay Payment Gateway", "Razorpay"]),
    ("Airtel Payments", ["Bharti Airtel Ltd", "AIRTEL PREPAID", "Airtel Billpay", "Bharti Airtel Telecom"]),
    ("Reliance Jio", ["Jio Infocomm Ltd", "RELIANCE JIO INFO", "Jio Recharge", "Reliance Retail"]),
    ("Netflix India", ["Netflix Entertainment", "NETFLIX SERVICES IN", "Netflix Subscription", "Netflix"]),
    ("Spotify Music", ["Spotify India Pvt", "SPOTIFY AB INDIA", "Spotify Premium", "Spotify IN"]),
]


def generate_synthetic_dataset(output_dir: str = "."):
    random.seed(RANDOM_SEED)

    bank_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    ground_truth_rows: list[dict[str, Any]] = []

    bank_id_counter = 1
    ledger_id_counter = 1

    def next_bank_id() -> str:
        nonlocal bank_id_counter
        b_id = f"BANK_TX_{bank_id_counter:04d}"
        bank_id_counter += 1
        return b_id

    def next_ledger_id() -> str:
        nonlocal ledger_id_counter
        l_id = f"LEDGER_REC_{ledger_id_counter:04d}"
        ledger_id_counter += 1
        return l_id

    def random_utr() -> str:
        return f"UTR{random.randint(100000000000, 999999999999)}"

    # -------------------------------------------------------------
    # Scenario 1: Exact Safe Matches with Standard Fees & Taxes (30 records)
    # -------------------------------------------------------------
    for i in range(30):
        b_id = next_bank_id()
        l_id = next_ledger_id()
        utr = random_utr()
        amount = Decimal(random.randint(500, 5000)).quantize(Decimal("0.01"))
        base_merch, _ = MERCHANTS[i % len(MERCHANTS)]
        tx_date = BASE_DATE + timedelta(days=random.randint(0, 5))
        lag_days = random.choice([0, 1, 2]) # T+0, T+1, T+2 settlement
        settlement_dt = tx_date + timedelta(days=lag_days)

        # Standard 2% platform fee, 18% GST on fee, 1% TDS on gross
        fee_pct = Decimal("2.00")
        gw_fee = (amount * fee_pct / Decimal("100.00")).quantize(Decimal("0.01"))
        gst_amt = (gw_fee * Decimal("0.18")).quantize(Decimal("0.01"))
        tds_amt = (amount * Decimal("0.01")).quantize(Decimal("0.01"))

        bank_rows.append({
            "transaction_id": b_id,
            "utr": utr,
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": str(fee_pct),
            "gateway_fee": str(gw_fee),
            "gst_amount": str(gst_amt),
            "tds_amount": str(tds_amt),
            "settlement_date": settlement_dt.strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{1000 + i}",
            "utr": utr,
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": str(fee_pct),
            "gateway_fee": str(gw_fee),
            "gst_amount": str(gst_amt),
            "tds_amount": str(tds_amt),
            "settlement_date": settlement_dt.strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id,
            "expected_ledger_id": l_id,
            "expected_status": "MATCHED",
            "scenario": "EXACT_SAFE_MATCH",
        })

    # -------------------------------------------------------------
    # Scenario 2: Fuzzy Merchant Name Matches with Exact UTR (25 records)
    # -------------------------------------------------------------
    for i in range(25):
        b_id = next_bank_id()
        l_id = next_ledger_id()
        utr = random_utr()
        amount = Decimal(random.randint(800, 10000)).quantize(Decimal("0.01"))
        base_merch, variants = MERCHANTS[i % len(MERCHANTS)]
        b_merch = variants[0]
        l_merch = variants[1] if len(variants) > 1 else base_merch
        tx_date = BASE_DATE + timedelta(days=random.randint(6, 12))
        lag_days = random.choice([1, 2])
        settlement_dt = tx_date + timedelta(days=lag_days)

        fee_pct = Decimal("1.75")
        gw_fee = (amount * fee_pct / Decimal("100.00")).quantize(Decimal("0.01"))
        gst_amt = (gw_fee * Decimal("0.18")).quantize(Decimal("0.01"))
        tds_amt = (amount * Decimal("0.01")).quantize(Decimal("0.01"))

        bank_rows.append({
            "transaction_id": b_id,
            "utr": utr,
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": b_merch,
            "fee_percentage": str(fee_pct),
            "gateway_fee": str(gw_fee),
            "gst_amount": str(gst_amt),
            "tds_amount": str(tds_amt),
            "settlement_date": settlement_dt.strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{2000 + i}",
            "utr": utr,
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": l_merch,
            "fee_percentage": str(fee_pct),
            "gateway_fee": str(gw_fee),
            "gst_amount": str(gst_amt),
            "tds_amount": str(tds_amt),
            "settlement_date": settlement_dt.strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id,
            "expected_ledger_id": l_id,
            "expected_status": "MATCHED",
            "scenario": "FUZZY_MERCHANT_MATCH",
        })

    # -------------------------------------------------------------
    # Scenario 3: Missing UTR but High Merchant & Amount Match (15 records)
    # (Including 5 items with Tax / Fee Variance for Tax-Line Matcher audit)
    # -------------------------------------------------------------
    for i in range(15):
        b_id = next_bank_id()
        l_id = next_ledger_id()
        amount = Decimal(random.randint(1200, 7500)).quantize(Decimal("0.01"))
        base_merch, variants = MERCHANTS[i % len(MERCHANTS)]
        b_merch = base_merch
        l_merch = variants[0]
        tx_date = BASE_DATE + timedelta(days=random.randint(13, 18))
        settlement_dt = tx_date + timedelta(days=1)

        fee_pct = Decimal("2.00")
        expected_gw_fee = (amount * fee_pct / Decimal("100.00")).quantize(Decimal("0.01"))
        # Introduce deliberate tax/fee discrepancy for 5 records to test Tax-Line Matcher
        if i < 5:
            actual_gw_fee = expected_gw_fee + Decimal("15.00") # Discrepancy
            actual_gst = (expected_gw_fee * Decimal("0.12")).quantize(Decimal("0.01")) # Wrong 12% GST instead of 18%
            actual_tds = Decimal("0.00") # Missing TDS
        else:
            actual_gw_fee = expected_gw_fee
            actual_gst = (expected_gw_fee * Decimal("0.18")).quantize(Decimal("0.01"))
            actual_tds = (amount * Decimal("0.01")).quantize(Decimal("0.01"))

        bank_rows.append({
            "transaction_id": b_id,
            "utr": "",
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": b_merch,
            "fee_percentage": str(fee_pct),
            "gateway_fee": str(actual_gw_fee),
            "gst_amount": str(actual_gst),
            "tds_amount": str(actual_tds),
            "settlement_date": settlement_dt.strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{3000 + i}",
            "utr": random_utr() if i % 2 == 0 else "",
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": l_merch,
            "fee_percentage": str(fee_pct),
            "gateway_fee": str(expected_gw_fee),
            "gst_amount": str((expected_gw_fee * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": settlement_dt.strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id,
            "expected_ledger_id": l_id,
            "expected_status": "MATCHED",
            "scenario": "MISSING_UTR_SAFE_MATCH",
        })

    # -------------------------------------------------------------
    # Scenario 4: Amount Mismatch Exceptions (12 records)
    # -------------------------------------------------------------
    for i in range(12):
        b_id = next_bank_id()
        l_id = next_ledger_id()
        utr = random_utr()
        base_amount = Decimal(random.randint(1000, 8000)).quantize(Decimal("0.01"))
        diff_amount = base_amount + Decimal(random.choice([15.00, 50.00, 100.50, 250.00]))
        base_merch, _ = MERCHANTS[i % len(MERCHANTS)]
        tx_date = BASE_DATE + timedelta(days=random.randint(19, 22))

        bank_rows.append({
            "transaction_id": b_id,
            "utr": utr,
            "amount": str(base_amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((base_amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((base_amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((base_amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{4000 + i}",
            "utr": utr,
            "amount": str(diff_amount),
            "currency": "INR",
            "invoice_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((diff_amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((diff_amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((diff_amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id,
            "expected_ledger_id": l_id,
            "expected_status": "EXCEPTION",
            "scenario": "AMOUNT_MISMATCH_EXCEPTION",
        })

    # -------------------------------------------------------------
    # Scenario 5: Date Tolerance Failure Exceptions (10 records)
    # -------------------------------------------------------------
    for i in range(10):
        b_id = next_bank_id()
        l_id = next_ledger_id()
        utr = random_utr()
        amount = Decimal(random.randint(1000, 4000)).quantize(Decimal("0.01"))
        base_merch, _ = MERCHANTS[i % len(MERCHANTS)]
        tx_date = BASE_DATE + timedelta(days=random.randint(5, 10))
        inv_date = tx_date + timedelta(days=random.randint(6, 15))  # > 3 days apart

        bank_rows.append({
            "transaction_id": b_id,
            "utr": utr,
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{5000 + i}",
            "utr": utr,
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (inv_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id,
            "expected_ledger_id": l_id,
            "expected_status": "EXCEPTION",
            "scenario": "DATE_MISMATCH_EXCEPTION",
        })

    # -------------------------------------------------------------
    # Scenario 6: Conflicting UTR Exceptions (8 records)
    # -------------------------------------------------------------
    for i in range(8):
        b_id = next_bank_id()
        l_id = next_ledger_id()
        amount = Decimal(random.randint(800, 3000)).quantize(Decimal("0.01"))
        base_merch, _ = MERCHANTS[i % len(MERCHANTS)]
        tx_date = BASE_DATE + timedelta(days=random.randint(23, 26))

        bank_rows.append({
            "transaction_id": b_id,
            "utr": random_utr(),
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{6000 + i}",
            "utr": random_utr(),
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id,
            "expected_ledger_id": l_id,
            "expected_status": "EXCEPTION",
            "scenario": "CONFLICTING_UTR_EXCEPTION",
        })

    # -------------------------------------------------------------
    # Scenario 7: Duplicate Ambiguous Candidates (6 bank rows -> 3 ledger rows)
    # -------------------------------------------------------------
    for i in range(3):
        b_id1 = next_bank_id()
        b_id2 = next_bank_id()
        l_id = next_ledger_id()
        amount = Decimal(random.randint(1200, 6000)).quantize(Decimal("0.01"))
        base_merch, _ = MERCHANTS[i % len(MERCHANTS)]
        tx_date = BASE_DATE + timedelta(days=27)

        bank_rows.append({
            "transaction_id": b_id1,
            "utr": "",
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        bank_rows.append({
            "transaction_id": b_id2,
            "utr": "",
            "amount": str(amount),
            "currency": "INR",
            "transaction_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{7000 + i}",
            "utr": "",
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": tx_date.strftime("%Y-%m-%d"),
            "merchant": base_merch,
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (tx_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "CREDIT",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id1,
            "expected_ledger_id": l_id,
            "expected_status": "MATCHED",
            "scenario": "AMBIGUOUS_COMPETITION_WINNER",
        })
        ground_truth_rows.append({
            "bank_transaction_id": b_id2,
            "expected_ledger_id": None,
            "expected_status": "EXCEPTION",
            "scenario": "AMBIGUOUS_COMPETITION_LOSER",
        })

    # -------------------------------------------------------------
    # Scenario 8: Distractor Ledger Rows (15 distractor rows not in bank)
    # -------------------------------------------------------------
    for i in range(15):
        l_id = next_ledger_id()
        amount = Decimal(random.randint(300, 9000)).quantize(Decimal("0.01"))
        base_merch, _ = MERCHANTS[i % len(MERCHANTS)]
        inv_date = BASE_DATE + timedelta(days=random.randint(1, 28))

        ledger_rows.append({
            "ledger_id": l_id,
            "invoice_id": f"INV-{8000 + i}",
            "utr": random_utr(),
            "amount": str(amount),
            "currency": "INR",
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "merchant": f"{base_merch} Unmatched Vendor",
            "fee_percentage": "2.00",
            "gateway_fee": str((amount * Decimal("0.02")).quantize(Decimal("0.01"))),
            "gst_amount": str((amount * Decimal("0.02") * Decimal("0.18")).quantize(Decimal("0.01"))),
            "tds_amount": str((amount * Decimal("0.01")).quantize(Decimal("0.01"))),
            "settlement_date": (inv_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "type": "DEBIT" if i % 3 == 0 else "CREDIT",
        })

    # Write files
    bank_path = os.path.join(output_dir, "bank.csv")
    ledger_path = os.path.join(output_dir, "ledger.csv")
    gt_path = os.path.join(output_dir, "ground_truth.csv")

    bank_fieldnames = [
        "transaction_id", "utr", "amount", "currency", "transaction_date",
        "merchant", "fee_percentage", "gateway_fee", "gst_amount", "tds_amount",
        "settlement_date", "type"
    ]
    with open(bank_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=bank_fieldnames)
        writer.writeheader()
        writer.writerows(bank_rows)

    ledger_fieldnames = [
        "ledger_id", "invoice_id", "utr", "amount", "currency", "invoice_date",
        "merchant", "fee_percentage", "gateway_fee", "gst_amount", "tds_amount",
        "settlement_date", "type"
    ]
    with open(ledger_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ledger_fieldnames)
        writer.writeheader()
        writer.writerows(ledger_rows)

    with open(gt_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["bank_transaction_id", "expected_ledger_id", "expected_status", "scenario"])
        writer.writeheader()
        writer.writerows(ground_truth_rows)

    print(f"Generated synthetic data successfully:")
    print(f"- Bank records: {len(bank_rows)} ({bank_path})")
    print(f"- Ledger records: {len(ledger_rows)} ({ledger_path})")
    print(f"- Ground truth rows: {len(ground_truth_rows)} ({gt_path})")


if __name__ == "__main__":
    generate_synthetic_dataset(".")
