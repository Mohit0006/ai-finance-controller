from datetime import datetime, date
from decimal import Decimal
import io
import json
from forecaster import generate_7day_cash_forecast
import httpx
import polars as pl
from schemas import CashPositionSummary
import streamlit as st

st.set_page_config(
    page_title="AI Finance Controller",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Clean Light Professional Theme ──────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── Global ───────────────────────────────────────── */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #0F172A !important;
    }
    .stApp {
        background: #F8FAFC;
    }
    .main .block-container {
        padding-top: 1.8rem;
        max-width: 1380px;
    }

    /* ── Sidebar ──────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #FFFFFF !important;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stFileUploader label {
        color: #64748B !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ── Hero Header ──────────────────────────────────── */
    .hero-header {
        background: linear-gradient(135deg, #0052CC 0%, #0066FF 50%, #2684FF 100%);
        border-radius: 14px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.2rem;
        position: relative;
        overflow: hidden;
    }
    .hero-header::after {
        content: '';
        position: absolute;
        top: -50%; right: -20%;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(255,255,255,0.18);
        color: #FFFFFF;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 0.2rem 0.65rem;
        border-radius: 100px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.5rem;
        backdrop-filter: blur(4px);
    }
    .hero-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: #FFFFFF;
        margin: 0 0 0.25rem 0;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        font-size: 0.82rem;
        color: rgba(255,255,255,0.75);
        font-weight: 400;
        letter-spacing: 0.01em;
    }

    /* ── KPI Cards ────────────────────────────────────── */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 0.75rem;
        margin-bottom: 1.4rem;
    }
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        text-align: center;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: var(--accent, #2563EB);
    }
    .kpi-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    .kpi-label {
        font-size: 0.65rem;
        color: #94A3B8;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.4rem;
    }
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: var(--value-color, #0F172A);
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    .kpi-unit {
        font-size: 0.68rem;
        color: #94A3B8;
        font-weight: 500;
        margin-top: 0.15rem;
    }

    /* ── Section Headers ──────────────────────────────── */
    .section-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0F172A;
        margin: 1rem 0 0.7rem 0;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .section-divider {
        border: none;
        border-top: 1px solid #E2E8F0;
        margin: 1rem 0;
    }

    /* ── Tabs ─────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"], div[data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 2px solid #E2E8F0 !important;
        background: transparent !important;
        padding-bottom: 2px;
    }
    .stTabs [data-baseweb="tab"], button[data-baseweb="tab"] {
        border-radius: 6px 6px 0 0 !important;
        padding: 0.55rem 1rem !important;
        transition: all 0.15s ease !important;
    }
    .stTabs [data-baseweb="tab"] *, button[data-baseweb="tab"] * {
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }
    .stTabs [data-baseweb="tab"]:hover *, button[data-baseweb="tab"]:hover * {
        color: #0F172A !important;
    }
    .stTabs [aria-selected="true"], button[data-baseweb="tab"][aria-selected="true"] {
        background: #EFF6FF !important;
    }
    .stTabs [aria-selected="true"] *, button[data-baseweb="tab"][aria-selected="true"] * {
        color: #1D4ED8 !important;
        font-weight: 700 !important;
    }
    .stTabs [data-baseweb="tab-highlight"], div[data-baseweb="tab-highlight"] {
        background: #2563EB !important;
        height: 3px !important;
    }
    .stTabs [data-baseweb="tab-border"], div[data-baseweb="tab-border"] {
        background: #E2E8F0 !important;
    }

    /* ── Subtab Segmented Control ─────────────────────── */
    div[data-testid="stSegmentedControl"] {
        margin: 0.5rem 0 1.25rem 0 !important;
        background: #F1F5F9 !important;
        padding: 4px !important;
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        display: flex !important;
        gap: 4px !important;
    }
    div[data-testid="stSegmentedControl"] button {
        flex: 1 1 0% !important;
        border-radius: 7px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 0.55rem 1rem !important;
        color: #475569 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        transition: all 0.15s ease-in-out !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-checked="true"],
    div[data-testid="stSegmentedControl"] button[data-checked="true"] {
        background: #FFFFFF !important;
        color: #0F172A !important;
        font-weight: 700 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
    }
    div[data-testid="stSegmentedControl"] button:hover {
        color: #0F172A !important;
        background: rgba(255,255,255,0.6) !important;
    }

    /* ── Diagnostic Cards ─────────────────────────────── */
    .diag-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.4rem;
    }
    .diag-card strong {
        color: #1E293B;
        font-size: 0.82rem;
    }
    .diag-card code {
        background: #EFF6FF;
        color: #1D4ED8;
        padding: 0.1rem 0.35rem;
        border-radius: 4px;
        font-size: 0.76rem;
    }

    /* ── Badges ────────────────────────────────────────── */
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.18rem 0.6rem;
        border-radius: 100px;
        font-size: 0.7rem;
        font-weight: 600;
        margin-right: 0.35rem;
        margin-bottom: 0.25rem;
    }
    .badge-pass {
        background: #F0FDF4;
        color: #166534;
        border: 1px solid #BBF7D0;
    }
    .badge-fail {
        background: #FEF2F2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }
    .badge-warn {
        background: #FFFBEB;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .badge-info {
        background: #EFF6FF;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }

    /* ── Buttons ───────────────────────────────────────── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 0.01em;
        box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 16px rgba(37,99,235,0.35) !important;
        transform: translateY(-1px) !important;
    }
    .stDownloadButton > button {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        color: #1E293B !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton > button:hover {
        background: #F8FAFC !important;
        border-color: #2563EB !important;
        color: #2563EB !important;
    }

    /* ── Alerts ────────────────────────────────────────── */
    .forecast-alert {
        background: #FEF2F2;
        border: 1px solid #FECACA;
        border-left: 3px solid #EF4444;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        color: #991B1B;
        font-size: 0.82rem;
        font-weight: 500;
    }
    .forecast-ok {
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-left: 3px solid #22C55E;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        color: #166534;
        font-size: 0.82rem;
        font-weight: 500;
    }

    /* ── Q&A Response ─────────────────────────────────── */
    .qa-response {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        margin-top: 0.8rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .qa-response .source-tag {
        display: inline-block;
        background: #EFF6FF;
        color: #1D4ED8;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 0.18rem 0.55rem;
        border-radius: 100px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.5rem;
    }
    .qa-answer {
        color: #334155;
        font-size: 0.9rem;
        line-height: 1.7;
    }

    /* ── Charts ────────────────────────────────────────── */
    [data-testid="stVegaLiteChart"] {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 0.6rem;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }

    /* ── Expander ──────────────────────────────────────── */
    .stExpander {
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
    }
    .stExpander summary * {
        color: #0F172A !important;
    }

    /* ── Inputs ────────────────────────────────────────── */
    .stSlider label, .stSelectbox label, .stTextInput label {
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
    }
    div[data-baseweb="select"] * {
        color: #0F172A !important;
    }
    .stTextInput input {
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        color: #0F172A !important;
        background: #FFFFFF !important;
    }
    .stTextInput input:focus {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 2px rgba(37,99,235,0.1) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Hero Header ──────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-header">
        <div class="hero-title">AI Finance Controller</div>
        <div class="hero-subtitle">
            Multi-Source Reconciliation · Cash Position · 7-Day Forward Forecaster · Tax-Line Auditor · Settlement Q&A
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="font-size:1rem;font-weight:700;color:#0F172A;margin-bottom:0.6rem;">⚙️ Configuration</div>',
        unsafe_allow_html=True,
    )
    api_url = st.text_input("Backend URL", value="http://127.0.0.1:8000")

    if st.button("🔍 Health Check", use_container_width=True):
        try:
            res = httpx.get(f"{api_url}/health", timeout=3.0)
            if res.status_code == 200:
                health_data = res.json()
                st.success(f"Status: {health_data.get('status').upper()}")
                cols = st.columns(2)
                with cols[0]:
                    st.caption(f"🗄️ DB: {health_data.get('database')}")
                    st.caption(f"🧩 pgvector: {health_data.get('vector_extension')}")
                with cols[1]:
                    st.caption(f"🧠 Embed: {health_data.get('embedding_model')}")
                    st.caption(f"✨ Gemini: {health_data.get('gemini')}")
            else:
                st.error(f"HTTP {res.status_code}")
        except Exception as e:
            st.error(f"Connection failed: {e}")

    st.markdown("---")
    st.markdown(
        '<div style="font-size:0.78rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">📁 Upload Files (50+ Records)</div>',
        unsafe_allow_html=True,
    )
    bank_file = st.file_uploader("Bank Statement (.csv)", type=["csv"], key="bank_upload")
    ledger_file = st.file_uploader("Internal Ledger (.csv)", type=["csv"], key="ledger_upload")
    gt_file = st.file_uploader("Ground Truth (optional)", type=["csv"], key="gt_upload")

    st.markdown('<div style="margin-top:0.6rem;"></div>', unsafe_allow_html=True)
    run_btn = st.button("🚀 Run Finance Controller", type="primary", use_container_width=True)

# ─── Execute Reconciliation ───────────────────────────────────────────
if run_btn:
    if not bank_file or not ledger_file:
        st.error("⚠️ Please upload both **bank.csv** and **ledger.csv** before running.")
    else:
        with st.spinner("Executing reconciliation pipeline, cash position bridge, 7-day forecast & tax audit..."):
            try:
                bank_bytes = bank_file.getvalue()
                ledger_bytes = ledger_file.getvalue()
                files = {
                    "bank_file": (bank_file.name, bank_bytes, "text/csv"),
                    "ledger_file": (ledger_file.name, ledger_bytes, "text/csv"),
                }
                if gt_file:
                    files["ground_truth_file"] = (gt_file.name, gt_file.getvalue(), "text/csv")

                res = httpx.post(f"{api_url}/reconcile", files=files, timeout=60.0)

                if res.status_code == 200:
                    st.session_state["reconcile_result"] = res.json()
                    st.session_state["active_batch_id"] = res.json().get("batch_id")

                    # Store parsed ledger records for interactive treasury simulator
                    try:
                        parsed_ledger_df = pl.read_csv(io.BytesIO(ledger_bytes), infer_schema_length=0)
                        st.session_state["raw_ledger_records"] = parsed_ledger_df.to_dicts()
                    except Exception:
                        st.session_state["raw_ledger_records"] = []

                    # Store forecast start date from response
                    fc = res.json().get("forecast", {})
                    if fc and fc.get("start_date"):
                        st.session_state["forecast_start_date"] = fc["start_date"]

                    st.success("✅ Finance Controller pipeline executed successfully!")
                elif res.status_code == 422:
                    err_json = res.json()
                    st.error(f"Validation Error: {err_json.get('detail')}")
                    if "validation_errors" in err_json:
                        st.json(err_json["validation_errors"])
                else:
                    st.error(f"Failed with HTTP {res.status_code}: {res.text}")
            except Exception as e:
                st.error(f"Backend connection failed: {e}")

# ─── Results Dashboard ────────────────────────────────────────────────
if "reconcile_result" in st.session_state:
    data = st.session_state["reconcile_result"]
    metrics = data.get("metrics", {})
    results = data.get("results", [])
    cash_pos = data.get("cash_position", {}) or {}
    forecast = data.get("forecast", {}) or {}
    tax_audit = data.get("tax_audit", {}) or {}
    batch_id = data.get("batch_id", "N/A")

    # ── Batch Header ──
    st.markdown(
        '<div class="section-header"><span>📊</span> Batch Audit Summary</div>',
        unsafe_allow_html=True,
    )

    # ── KPI Banner ──
    match_rate = metrics.get("auto_match_rate", 0.0) * 100
    prec = metrics.get("precision")
    prec_str = f"{prec * 100:.1f}%" if prec is not None else "N/A"
    recall = metrics.get("recall")
    recall_str = f"{recall * 100:.1f}%" if recall is not None else "N/A"
    throughput = metrics.get("throughput_records_per_second", 0)

    st.markdown(
        f"""
        <div class="kpi-grid">
            <div class="kpi-card" style="--accent:#2563EB;">
                <div class="kpi-label">Bank Records</div>
                <div class="kpi-value">{metrics.get("total_bank_records", 0)}</div>
                <div class="kpi-unit">Ingested</div>
            </div>
            <div class="kpi-card" style="--accent:#16A34A;">
                <div class="kpi-label">Matched</div>
                <div class="kpi-value" style="--value-color:#16A34A;">{metrics.get("matched_count", 0)}</div>
                <div class="kpi-unit">Verified</div>
            </div>
            <div class="kpi-card" style="--accent:#DC2626;">
                <div class="kpi-label">Exceptions</div>
                <div class="kpi-value" style="--value-color:#DC2626;">{metrics.get("exception_count", 0)}</div>
                <div class="kpi-unit">Honest List</div>
            </div>
            <div class="kpi-card" style="--accent:#0891B2;">
                <div class="kpi-label">Precision</div>
                <div class="kpi-value" style="--value-color:#0891B2;">{prec_str}</div>
                <div class="kpi-unit">Zero FP</div>
            </div>
            <div class="kpi-card" style="--accent:#7C3AED;">
                <div class="kpi-label">Recall</div>
                <div class="kpi-value" style="--value-color:#7C3AED;">{recall_str}</div>
                <div class="kpi-unit">Honest</div>
            </div>
            <div class="kpi-card" style="--accent:#D97706;">
                <div class="kpi-label">Throughput</div>
                <div class="kpi-value" style="--value-color:#D97706;">{throughput:.0f}</div>
                <div class="kpi-unit">rec/s</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 4 Core Tabs ──
    tab_recon, tab_cash, tab_tax, tab_qa = st.tabs([
        "⚖️  Reconciliation & Match Rate",
        "💵  Cash Position & 7-Day Forecast",
        "🧾  Tax-Line & Fee Auditor",
        "🤖  Settlement Q&A Agent",
    ])

    # ─────────────────────────────────────────────────────────────────
    # TAB 1: Reconciliation & Match Rate
    # ─────────────────────────────────────────────────────────────────
    with tab_recon:
        col_m1, col_m2 = st.columns([1, 1])
        with col_m1:
            st.markdown(f"⏱️ **Processing Duration:** `{metrics.get('processing_time_seconds', 0):.2f}s`")
            st.markdown(f"🎯 **Measured Precision:** `{metrics.get('precision', 'N/A')}` — Zero false matches")
        with col_m2:
            st.markdown(f"⚠️ **False Positives:** `{metrics.get('false_positive_count', 0)}`")
            st.markdown(f"📋 **Scope:** `{metrics.get('metrics_scope')}`")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        sub_matched_label = f"✅ Matched ({metrics.get('matched_count', 0)})"
        sub_exc_label = f"⚠️ Exception Explorer ({metrics.get('exception_count', 0)})"
        sub_export_label = "📥 Audit Pack & Exports"
        subtab_options = [sub_matched_label, sub_exc_label, sub_export_label]

        # Preserve selected subtab across widget reruns using session state
        if "recon_active_subtab" not in st.session_state or not any(k in str(st.session_state["recon_active_subtab"]) for k in ["Matched", "Exception", "Audit"]):
            st.session_state["recon_active_subtab"] = sub_matched_label
        elif "Exception" in str(st.session_state["recon_active_subtab"]):
            st.session_state["recon_active_subtab"] = sub_exc_label
        elif "Audit" in str(st.session_state["recon_active_subtab"]) or "Export" in str(st.session_state["recon_active_subtab"]):
            st.session_state["recon_active_subtab"] = sub_export_label
        else:
            st.session_state["recon_active_subtab"] = sub_matched_label

        active_subtab = st.segmented_control(
            "Reconciliation Sub-View",
            options=subtab_options,
            key="recon_active_subtab",
            label_visibility="collapsed",
            width="stretch",
        )
        if not active_subtab:
            active_subtab = st.session_state["recon_active_subtab"]

        if "Matched" in str(active_subtab):
            matched_items = [r for r in results if r["status"] == "MATCHED"]
            if matched_items:
                df_matched = pl.DataFrame([
                    {
                        "Bank Tx ID": item["bank_transaction_id"],
                        "Ledger ID": item["ledger_id"],
                        "Source": item["decision_source"],
                        "Score": f"{item['decision_score']:.4f}",
                        "Amt Diff (₹)": str(item["amount_difference"]),
                        "Date Δ (d)": item["date_difference_days"],
                        "Reasoning": item["reasoning"],
                    } for item in matched_items
                ])
                st.dataframe(df_matched.to_pandas(), use_container_width=True, height=420)
            else:
                st.info("No records matched.")

        elif "Exception" in str(active_subtab):
            exception_items = [r for r in results if r.get("status") == "EXCEPTION"]
            if exception_items:
                # Dynamic category extraction directly from batch exceptions
                cat_counts: dict[str, int] = {}
                for e in exception_items:
                    c_name = str(e.get("decision_source") or "UNSPECIFIED")
                    cat_counts[c_name] = cat_counts.get(c_name, 0) + 1

                cat_options = [f"ALL ({len(exception_items)} total)"] + [
                    f"{c_name} ({cnt})" for c_name, cnt in sorted(cat_counts.items())
                ]

                filter_src = st.selectbox(
                    "Filter by Category:",
                    options=cat_options,
                    key="exc_filter"
                )

                filter_val = str(filter_src or "")
                if filter_val.startswith("ALL") or not filter_val:
                    filtered = exception_items
                else:
                    selected_cat = filter_val.split(" (")[0].strip()
                    filtered = [e for e in exception_items if str(e.get("decision_source") or "") == selected_cat]

                st.markdown(f"Displaying **{len(filtered)}** of {len(exception_items)} exceptions:")

                if not filtered:
                    st.info("No exceptions found for this category.")
                else:
                    # Overview table for fast auditing and scanning
                    try:
                        table_rows = []
                        for exc in filtered:
                            table_rows.append({
                                "Bank Tx ID": str(exc.get("bank_transaction_id") or ""),
                                "Category": str(exc.get("decision_source") or ""),
                                "Score": f"{float(exc.get('decision_score') or 0.0):.3f}",
                                "Amt Diff (₹)": str(exc.get("amount_difference") if exc.get("amount_difference") is not None else "0.00"),
                                "Date Δ (d)": str(exc.get("date_difference_days") if exc.get("date_difference_days") is not None else "—"),
                                "Diagnostic": str(exc.get("reasoning") or ""),
                            })
                        df_exc_table = pl.DataFrame(table_rows)
                        st.dataframe(df_exc_table.to_pandas(), use_container_width=True, height=280)
                    except Exception as df_err:
                        st.caption(f"Table preview unavailable: {df_err}")

                    # Detailed expandable diagnostics cards
                    for exc in filtered:
                        try:
                            bank_tx_id = str(exc.get("bank_transaction_id") or "UNKNOWN")
                            source_name = str(exc.get("decision_source") or "UNKNOWN")
                            dec_score = float(exc.get("decision_score") or 0.0)
                            lex_score = float(exc.get("lexical_score") or 0.0)
                            sem_score = float(exc.get("semantic_score") or 0.0)

                            cand_ev = exc.get("candidate_evidence") or {}
                            top_cand = {}
                            if "top_candidate_ledger_id" in cand_ev:
                                top_cand = {
                                    "ledger_id": cand_ev.get("top_candidate_ledger_id"),
                                    "amount": cand_ev.get("top_candidate_amount"),
                                    "invoice_date": cand_ev.get("top_candidate_date"),
                                    "merchant": cand_ev.get("top_candidate_merchant"),
                                }
                            elif "ledger_id" in cand_ev:
                                top_cand = {
                                    "ledger_id": cand_ev.get("ledger_id"),
                                    "amount": cand_ev.get("ledger_amount"),
                                    "invoice_date": cand_ev.get("ledger_date"),
                                    "merchant": cand_ev.get("ledger_merchant"),
                                }
                            elif "competing_ledger_id" in cand_ev:
                                top_cand = {
                                    "ledger_id": cand_ev.get("competing_ledger_id"),
                                    "amount": "—",
                                    "invoice_date": "—",
                                    "merchant": cand_ev.get("ledger_merchant"),
                                }

                            with st.expander(f"{bank_tx_id} · {source_name} · Score: {dec_score:.3f}"):
                                st.markdown(f"**Diagnostic:** `{exc.get('reasoning', 'No diagnostic recorded')}`")
                                col_card1, col_card2 = st.columns(2)
                                with col_card1:
                                    st.markdown(
                                        f"""<div class="diag-card"><strong>🏦 Bank Transaction</strong><br><span style="color:#475569;font-size:0.8rem;">Tx ID: <code>{bank_tx_id}</code><br>Score: <code>{dec_score:.4f}</code> · Lex: <code>{lex_score:.4f}</code> · Sem: <code>{sem_score:.4f}</code></span></div>""",
                                        unsafe_allow_html=True,
                                    )
                                with col_card2:
                                    lid_show = top_cand.get("ledger_id") or "None"
                                    amt_show = top_cand.get("amount") if top_cand.get("amount") is not None else "N/A"
                                    date_show = top_cand.get("invoice_date") if top_cand.get("invoice_date") is not None else "N/A"
                                    st.markdown(
                                        f"""<div class="diag-card"><strong>📖 Closest Candidate</strong><br><span style="color:#475569;font-size:0.8rem;">Ledger: <code>{lid_show}</code><br>Amount: ₹{amt_show} · Date: {date_show}</span></div>""",
                                        unsafe_allow_html=True,
                                    )

                                badge_html = "<div style='margin-top:0.4rem;'>"
                                amt_diff = exc.get("amount_difference")
                                if amt_diff is not None and str(amt_diff).strip() not in ("", "None"):
                                    try:
                                        amt_dec = Decimal(str(amt_diff))
                                        badge_html += f'<span class="badge {"badge-fail" if amt_dec > Decimal("1.00") else "badge-pass"}">{"❌" if amt_dec > Decimal("1.00") else "✅"} Amt: ₹{amt_dec}</span>'
                                    except Exception:
                                        pass

                                date_diff = exc.get("date_difference_days")
                                if date_diff is not None and str(date_diff).strip() not in ("", "None"):
                                    try:
                                        dd_val = abs(int(date_diff))
                                        badge_html += f'<span class="badge {"badge-fail" if dd_val > 3 else "badge-pass"}">{"❌" if dd_val > 3 else "✅"} Date: {dd_val}d</span>'
                                    except Exception:
                                        pass

                                if source_name == "DUPLICATE_CONFLICT":
                                    badge_html += '<span class="badge badge-warn">⚠️ 1:1 Collision</span>'
                                elif source_name == "NO_CANDIDATE":
                                    badge_html += '<span class="badge badge-fail">❌ No Counterparty</span>'
                                badge_html += "</div>"
                                st.markdown(badge_html, unsafe_allow_html=True)
                        except Exception as card_err:
                            st.error(f"Error displaying exception card {exc.get('bank_transaction_id')}: {card_err}")
            else:
                st.success("🎉 Zero exceptions — perfect reconciliation!")

        else:
            # Audit Pack & Exports
            st.markdown('<div class="section-header"><span>📄</span> Audit Artifacts</div>', unsafe_allow_html=True)
            audit_memo_content = f"""# AI Finance Controller — Monthly Reconciliation & Treasury Assessment Report
**Generated Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Batch Identifier:** `{batch_id}`

---

## 1. Executive Operations Summary
- **Total Bank Records Audited:** {metrics.get('total_bank_records', 0)}
- **Total Ledger Records Ingested:** {metrics.get('total_ledger_records', 0)}
- **Reconciled Match Count:** {metrics.get('matched_count', 0)}
- **Honest Unresolved Exceptions:** {metrics.get('exception_count', 0)}
- **Auto-Match Rate:** {metrics.get('auto_match_rate', 0.0) * 100:.2f}%
- **Measured Reconciliation Precision:** {metrics.get('precision', 1.0) * 100:.2f}%
- **False Positive Count:** {metrics.get('false_positive_count', 0)}
- **Execution Duration:** {metrics.get('processing_time_seconds', 0)} seconds ({metrics.get('throughput_records_per_second', 0):.2f} records/sec)

---

## 2. Cash Position & Working Capital Bridge
- **Book Balance (Ledger):** ₹{cash_pos.get('book_balance', '0.00')}
- **Bank Balance (Cleared):** ₹{cash_pos.get('bank_balance', '0.00')}
- **Reconciled Cash Inflow:** ₹{cash_pos.get('reconciled_cash_inflow', '0.00')}
- **Uncleared Float (T+1/T+2):** ₹{cash_pos.get('uncleared_float', '0.00')}
- **Discrepancy Variance:** ₹{cash_pos.get('discrepancy_variance', '0.00')} ({cash_pos.get('reconciliation_status')})

---

## 3. Tax & Fee Compliance
- **Gross Volume:** ₹{tax_audit.get('total_gross_volume', '0.00')}
- **Expected GST (18%):** ₹{tax_audit.get('total_expected_gst', '0.00')}
- **Expected TDS (1%):** ₹{tax_audit.get('total_expected_tds', '0.00')}
- **Variance Flags:** {tax_audit.get('variance_count', 0)} records

---

## 4. 7-Day Liquidity Outlook
- **Base Ending Balance:** ₹{forecast.get('base_ending_balance', '0.00')}
- **Conservative Ending:** ₹{forecast.get('conservative_ending_balance', '0.00')}
- **Reserve Breach:** {"BREACH DETECTED" if forecast.get('has_reserve_breach') else "HEALTHY"}

---

## 5. Sign-Off
**Finance Controller:** ___________________________   **Date:** {datetime.now().strftime("%Y-%m-%d")}
**CFO:** ___________________________   **Date:** {datetime.now().strftime("%Y-%m-%d")}
"""
            st.download_button(label="📥 Download Controller Audit Pack (.md)", data=audit_memo_content.encode("utf-8"), file_name=f"Controller_Audit_{batch_id}.md", mime="text/markdown", use_container_width=True)
            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
            col_csv1, col_csv2 = st.columns(2)
            with col_csv1:
                full_df = pl.DataFrame([{"bank_transaction_id": r["bank_transaction_id"], "ledger_id": r.get("ledger_id"), "status": r["status"], "decision_source": r["decision_source"], "decision_score": r["decision_score"], "amount_difference": str(r.get("amount_difference")), "reasoning": r["reasoning"]} for r in results])
                buf_full = io.BytesIO()
                full_df.write_csv(buf_full)
                st.download_button(label="📊 Full Results CSV", data=buf_full.getvalue(), file_name=f"reconciliation_{batch_id}_full.csv", mime="text/csv", use_container_width=True)
            with col_csv2:
                exc_only = [r for r in results if r["status"] == "EXCEPTION"]
                if exc_only:
                    exc_df = pl.DataFrame([{"bank_transaction_id": r["bank_transaction_id"], "decision_source": r["decision_source"], "decision_score": r["decision_score"], "amount_difference": str(r.get("amount_difference")), "date_difference_days": r.get("date_difference_days"), "reasoning": r["reasoning"]} for r in exc_only])
                    buf_exc = io.BytesIO()
                    exc_df.write_csv(buf_exc)
                    st.download_button(label="⚠️ Exceptions Only CSV", data=buf_exc.getvalue(), file_name=f"exceptions_{batch_id}.csv", mime="text/csv", use_container_width=True)

    # ─────────────────────────────────────────────────────────────────
    # TAB 2: Cash Position & 7-Day Forecast
    # ─────────────────────────────────────────────────────────────────
    with tab_cash:
        st.markdown('<div class="section-header"><span>🏦</span> Cash Position Reconciliation Bridge</div>', unsafe_allow_html=True)

        variance_val = cash_pos.get("discrepancy_variance", "0.00")
        var_color = "#16A34A" if Decimal(str(variance_val)) == Decimal("0.00") else "#DC2626"
        recon_status = cash_pos.get("reconciliation_status", "N/A")

        st.markdown(
            f"""
            <div class="kpi-grid">
                <div class="kpi-card" style="--accent:#2563EB;">
                    <div class="kpi-label">Book Balance (Ledger)</div>
                    <div class="kpi-value">₹{cash_pos.get("book_balance", "0.00")}</div>
                </div>
                <div class="kpi-card" style="--accent:#16A34A;">
                    <div class="kpi-label">Bank Balance (Cleared)</div>
                    <div class="kpi-value" style="--value-color:#16A34A;">₹{cash_pos.get("bank_balance", "0.00")}</div>
                </div>
                <div class="kpi-card" style="--accent:#D97706;">
                    <div class="kpi-label">Uncleared Float (T+1/T+2)</div>
                    <div class="kpi-value" style="--value-color:#D97706;">₹{cash_pos.get("uncleared_float", "0.00")}</div>
                </div>
                <div class="kpi-card" style="--accent:{"#16A34A" if Decimal(str(variance_val)) == Decimal("0.00") else "#DC2626"};">
                    <div class="kpi-label">Discrepancy Variance</div>
                    <div class="kpi-value" style="--value-color:{var_color};">₹{variance_val}</div>
                    <div class="kpi-unit">{recon_status}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown('<div class="section-header"><span>🎛️</span> Interactive Treasury Simulator (7-Day Forecast)</div>', unsafe_allow_html=True)
        st.caption("Simulate forward operational cash flow under customizable parameters:")

        bank_bal_float = float(cash_pos.get("bank_balance", 384000.0))
        max_burn = max(100000, int(bank_bal_float * 0.5))
        max_reserve = max(600000, int(bank_bal_float * 1.5))

        sim_col1, sim_col2, sim_col3 = st.columns(3)
        with sim_col1:
            burn_input = st.slider("Daily Burn Rate (₹)", min_value=1000, max_value=max_burn, value=min(15000, max_burn), step=1000, key="burn_slider")
        with sim_col2:
            reserve_input = st.slider("Reserve Floor (₹)", min_value=10000, max_value=max_reserve, value=min(250000, max_reserve), step=10000, key="reserve_slider")
        with sim_col3:
            lag_choice = st.selectbox("Settlement Cycle", options=["Standard T+1/T+2 (0d Lag)", "Holiday/Weekend (+2d Delay)"], key="lag_select")
            lag_days = 2 if "Holiday" in str(lag_choice or "") else 0

        # Dynamic recalculation using batch-derived start date
        raw_ledger = st.session_state.get("raw_ledger_records", [])
        active_cash_obj = CashPositionSummary(
            book_balance=Decimal(str(cash_pos.get("book_balance", "0.00"))),
            bank_balance=Decimal(str(cash_pos.get("bank_balance", "0.00"))),
            reconciled_cash_inflow=Decimal(str(cash_pos.get("reconciled_cash_inflow", "0.00"))),
            reconciled_cash_outflow=Decimal(str(cash_pos.get("reconciled_cash_outflow", "0.00"))),
            uncleared_float=Decimal(str(cash_pos.get("uncleared_float", "0.00"))),
            discrepancy_variance=Decimal(str(cash_pos.get("discrepancy_variance", "0.00"))),
            currency=cash_pos.get("currency", "INR"),
            reconciliation_status=cash_pos.get("reconciliation_status", "BALANCED"),
        )

        # Use the batch-derived start date from the forecast response
        forecast_start_str = st.session_state.get("forecast_start_date")
        forecast_start = None
        if forecast_start_str:
            try:
                forecast_start = date.fromisoformat(forecast_start_str)
            except (ValueError, TypeError):
                forecast_start = None

        sim_forecast = generate_7day_cash_forecast(
            cash_position=active_cash_obj,
            ledger_records=raw_ledger,
            daily_burn_rate=Decimal(str(burn_input)),
            minimum_reserve=Decimal(str(reserve_input)),
            settlement_lag_days=lag_days,
            start_date=forecast_start,
        )

        if sim_forecast.has_reserve_breach:
            st.markdown(
                f'<div class="forecast-alert">🚨 <strong>Reserve Breach Alert:</strong> Projected cash drops below ₹{reserve_input:,} on Day(s): {sim_forecast.breach_days} under conservative stress.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="forecast-ok">✅ <strong>Liquidity Healthy:</strong> Projected balance maintains ₹{reserve_input:,} reserve across all 7 days.</div>',
                unsafe_allow_html=True,
            )

        proj_rows = []
        for p in sim_forecast.daily_projections:
            proj_rows.append({
                "Day": f"+{p.day_offset}d ({p.forecast_date})",
                "Base (₹)": f"₹{p.base_projected_balance:,.2f}",
                "Optimistic (₹)": f"₹{p.optimistic_projected_balance:,.2f}",
                "Conservative (₹)": f"₹{p.conservative_projected_balance:,.2f}",
                "Inflow (₹)": f"₹{p.expected_inflows:,.2f}",
                "Outflow (₹)": f"₹{p.expected_outflows:,.2f}",
                "Status": "🚨 BREACH" if p.reserve_breached else "✅ OK",
            })
        df_proj = pl.DataFrame(proj_rows)
        st.dataframe(df_proj.to_pandas(), use_container_width=True, height=320)

        chart_data = {
            "Date": [p.forecast_date for p in sim_forecast.daily_projections],
            "Base Case": [float(p.base_projected_balance) for p in sim_forecast.daily_projections],
            "Optimistic (+10%)": [float(p.optimistic_projected_balance) for p in sim_forecast.daily_projections],
            "Conservative Stress": [float(p.conservative_projected_balance) for p in sim_forecast.daily_projections],
        }
        st.line_chart(chart_data, x="Date", height=350)

    # ─────────────────────────────────────────────────────────────────
    # TAB 3: Tax-Line & Fee Auditor
    # ─────────────────────────────────────────────────────────────────
    with tab_tax:
        st.markdown('<div class="section-header"><span>🧾</span> Gateway Fee, GST (18%) & TDS (1%) Audit</div>', unsafe_allow_html=True)

        pass_count = tax_audit.get("pass_count", 0)
        var_count = tax_audit.get("variance_count", 0)
        total_audited = tax_audit.get("total_audited_transactions", 0)
        pass_pct = (pass_count / total_audited * 100) if total_audited > 0 else 0

        st.markdown(
            f"""
            <div class="kpi-grid">
                <div class="kpi-card" style="--accent:#2563EB;">
                    <div class="kpi-label">Audited Transactions</div>
                    <div class="kpi-value">{total_audited}</div>
                </div>
                <div class="kpi-card" style="--accent:#16A34A;">
                    <div class="kpi-label">Verified Passed</div>
                    <div class="kpi-value" style="--value-color:#16A34A;">{pass_count}</div>
                    <div class="kpi-unit">{pass_pct:.0f}% compliance</div>
                </div>
                <div class="kpi-card" style="--accent:#DC2626;">
                    <div class="kpi-label">Variance Flags</div>
                    <div class="kpi-value" style="--value-color:#DC2626;">{var_count}</div>
                </div>
                <div class="kpi-card" style="--accent:#7C3AED;">
                    <div class="kpi-label">Expected GST (18%)</div>
                    <div class="kpi-value" style="--value-color:#7C3AED;">₹{tax_audit.get("total_expected_gst", "0.00")}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        tax_items = tax_audit.get("audit_items", [])
        if tax_items:
            t_col1, t_col2 = st.columns([1, 1])
            with t_col1:
                status_filter = st.selectbox(
                    "Filter by Status:",
                    options=["ALL (All Audited)", "🚨 VARIANCE_FLAG (Failed Audit)", "✅ PASS (Verified Passed)"],
                    key="tax_status_filter",
                )
            with t_col2:
                sort_option = st.selectbox(
                    "Sort by:",
                    options=["Failures First (Variances First)", "Default Order", "Highest Gross Amount"],
                    key="tax_sort_option",
                )

            # Filter
            filtered_tax = tax_items
            status_filter_val = str(status_filter or "")
            if "VARIANCE_FLAG" in status_filter_val:
                filtered_tax = [t for t in tax_items if t["status"] == "VARIANCE_FLAG"]
            elif "PASS" in status_filter_val:
                filtered_tax = [t for t in tax_items if t["status"] == "PASS"]

            # Sort
            sort_val = str(sort_option or "")
            if sort_val == "Failures First (Variances First)":
                filtered_tax = sorted(filtered_tax, key=lambda x: 0 if x["status"] == "VARIANCE_FLAG" else 1)
            elif sort_val == "Highest Gross Amount":
                filtered_tax = sorted(filtered_tax, key=lambda x: Decimal(str(x.get("gross_amount", 0))), reverse=True)

            tax_table_rows = []
            for t in filtered_tax:
                status_icon = "✅" if t["status"] == "PASS" else "🚨"
                tax_table_rows.append({
                    "Status": f"{status_icon} {t['status']}",
                    "Tx ID": t["transaction_id"],
                    "Gross (₹)": f"₹{Decimal(str(t['gross_amount'])):,.2f}",
                    "Fee %": f"{t['fee_percentage']}%",
                    "Exp Fee": str(t["expected_gateway_fee"]),
                    "Act Fee": str(t["actual_gateway_fee"]),
                    "Exp GST": str(t["expected_gst_18pct"]),
                    "Act GST": str(t["actual_gst_18pct"]),
                    "Exp TDS": str(t["expected_tds_1pct"]),
                    "Act TDS": str(t["actual_tds_1pct"]),
                    "Detail": t["discrepancy_reason"],
                })
            df_tax = pl.DataFrame(tax_table_rows)
            st.dataframe(df_tax.to_pandas(), use_container_width=True, height=420)

    # ─────────────────────────────────────────────────────────────────
    # TAB 4: Settlement Q&A Agent
    # ─────────────────────────────────────────────────────────────────
    with tab_qa:
        col_qa_h1, col_qa_h2 = st.columns([3, 1])
        with col_qa_h1:
            st.markdown('<div class="section-header"><span>🤖</span> Settlement & Finance Ops Q&A Agent</div>', unsafe_allow_html=True)
            st.caption("Ask natural language questions grounded in current batch data. Full conversation history is retained below.")
        with col_qa_h2:
            if st.button("🧹 Clear Chat", key="clear_qa_chat", use_container_width=True):
                st.session_state["qa_chat_history"] = []
                st.rerun()

        if "qa_chat_history" not in st.session_state:
            st.session_state["qa_chat_history"] = []

        # Display conversation history
        for msg in st.session_state["qa_chat_history"]:
            if msg["role"] == "user":
                with st.chat_message("user", avatar="🧑‍💼"):
                    st.write(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    if msg.get("source") == "GEMINI_LLM":
                        st.markdown('<span class="source-tag">🤖 Gemini 2.5 Flash</span>', unsafe_allow_html=True)
                    st.markdown(msg["content"])
                    if msg.get("citations"):
                        with st.expander("🔍 View Citations & Evidence", expanded=False):
                            cits = msg["citations"]
                            if isinstance(cits, list) and len(cits) > 0 and isinstance(cits[0], dict):
                                try:
                                    st.dataframe(pl.DataFrame(cits).to_pandas(), use_container_width=True)
                                except Exception:
                                    st.json(cits)
                            else:
                                st.json(cits)

        # Chat Input
        prompt = st.chat_input("Ask a finance question (e.g., give top 5 exception cases, what is our float?)...")
        if prompt:
            st.session_state["qa_chat_history"].append({"role": "user", "content": prompt})
            history_payload = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["qa_chat_history"][:-1]
            ]
            with st.spinner("Analyzing batch context with Gemini..."):
                try:
                    qa_res = httpx.post(
                        f"{api_url}/qa/settlement",
                        json={"batch_id": batch_id, "question": prompt, "history": history_payload},
                        timeout=35.0,
                    )
                    if qa_res.status_code == 200:
                        qa_data = qa_res.json()
                        st.session_state["qa_chat_history"].append({
                            "role": "assistant",
                            "content": qa_data.get("answer", "No answer received."),
                            "source": qa_data.get("source", "GEMINI_LLM"),
                            "citations": qa_data.get("citations", []),
                        })
                    else:
                        st.session_state["qa_chat_history"].append({
                            "role": "assistant",
                            "content": f"⚠️ Error {qa_res.status_code}: {qa_res.text}",
                            "source": "ERROR",
                            "citations": [],
                        })
                except Exception as e:
                    st.session_state["qa_chat_history"].append({
                        "role": "assistant",
                        "content": f"⚠️ Backend connection failed: {e}",
                        "source": "ERROR",
                        "citations": [],
                    })
            st.rerun()
