# dashboard/app.py

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Tech Sector Financial Analytics",
    page_icon="📊",
    layout="wide"
)

DB_PATH = Path("data/warehouse.duckdb")

# ── Data Loader ───────────────────────────────────────────────────────────────

@st.cache_data
def load_revenue_trends() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df   = conn.execute("""
        SELECT * FROM main_gold.gold_revenue_trends
        ORDER BY ticker, fiscal_year
    """).fetchdf()
    conn.close()
    return df

@st.cache_data
def load_company_comparison() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df   = conn.execute("""
        SELECT * FROM main_gold.gold_company_comparison
        ORDER BY revenue_bn DESC
    """).fetchdf()
    conn.close()
    return df

@st.cache_data
def load_margin_trends() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df   = conn.execute("""
        SELECT * FROM main_gold.gold_margin_trends
        ORDER BY ticker, fiscal_year
    """).fetchdf()
    conn.close()
    return df

# ── Load Data ─────────────────────────────────────────────────────────────────

revenue_df    = load_revenue_trends()
comparison_df = load_company_comparison()
margin_df     = load_margin_trends()

all_tickers = sorted(revenue_df["ticker"].unique())

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📊 Tech Sector Financial Analytics")
st.caption("SEC EDGAR data · 30 companies · 2015–2024 · Built with dbt + DuckDB + Streamlit")

# ── Sidebar Filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")

selected_tickers = st.sidebar.multiselect(
    "Select Companies",
    options=all_tickers,
    default=["AAPL", "MSFT", "NVDA", "GOOGL", "META"]
)

year_range = st.sidebar.slider(
    "Year Range",
    min_value=int(revenue_df["fiscal_year"].min()),
    max_value=int(revenue_df["fiscal_year"].max()),
    value=(2018, 2024)
)

if not selected_tickers:
    st.warning("Please select at least one company.")
    st.stop()

# ── Filter Data ───────────────────────────────────────────────────────────────

rev_filtered = revenue_df[
    (revenue_df["ticker"].isin(selected_tickers)) &
    (revenue_df["fiscal_year"].between(year_range[0], year_range[1]))
]

margin_filtered = margin_df[
    (margin_df["ticker"].isin(selected_tickers)) &
    (margin_df["fiscal_year"].between(year_range[0], year_range[1]))
]

comp_filtered = comparison_df[comparison_df["ticker"].isin(selected_tickers)]

# ── KPI Cards ─────────────────────────────────────────────────────────────────

st.subheader("Latest Year Snapshot")

cols = st.columns(len(selected_tickers[:5]))
for i, ticker in enumerate(selected_tickers[:5]):
    row = comp_filtered[comp_filtered["ticker"] == ticker]
    if not row.empty:
        cols[i].metric(
            ticker,
            f"${row['revenue_bn'].iloc[0]:.1f}B",
            f"{row['revenue_growth_pct'].iloc[0]:+.1f}% YoY" 
            if pd.notna(row['revenue_growth_pct'].iloc[0]) else "N/A"
        )

st.divider()

# ── Row 1: Revenue Trend + YoY Growth ────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Revenue Trend ($B)")
    fig = px.line(
        rev_filtered,
        x="fiscal_year",
        y="revenue_bn",
        color="ticker",
        markers=True,
        labels={
            "fiscal_year": "Year",
            "revenue_bn":  "Revenue ($B)",
            "ticker":      "Company"
        }
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("YoY Revenue Growth (%)")
    growth_df = rev_filtered[rev_filtered["revenue_growth_pct"].notna()]
    fig = px.line(
        growth_df,
        x="fiscal_year",
        y="revenue_growth_pct",
        color="ticker",
        markers=True,
        labels={
            "fiscal_year":        "Year",
            "revenue_growth_pct": "Growth (%)",
            "ticker":             "Company"
        }
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Row 2: Gross Margin + Net Margin ─────────────────────────────────────────

col3, col4 = st.columns(2)

with col3:
    st.subheader("Gross Margin Trend (%)")
    fig = px.line(
        margin_filtered,
        x="fiscal_year",
        y="gross_margin_pct",
        color="ticker",
        markers=True,
        labels={
            "fiscal_year":      "Year",
            "gross_margin_pct": "Gross Margin (%)",
            "ticker":           "Company"
        }
    )
    # Industry average line
    industry_avg = margin_filtered.groupby("fiscal_year")[
        "industry_avg_gross_margin"
    ].mean().reset_index()
    fig.add_scatter(
        x=industry_avg["fiscal_year"],
        y=industry_avg["industry_avg_gross_margin"],
        mode="lines",
        name="Industry Avg",
        line=dict(dash="dash", color="gray")
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("Net Margin Trend (%)")
    fig = px.line(
        margin_filtered,
        x="fiscal_year",
        y="net_margin_pct",
        color="ticker",
        markers=True,
        labels={
            "fiscal_year":    "Year",
            "net_margin_pct": "Net Margin (%)",
            "ticker":         "Company"
        }
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Row 3: Peer Comparison + R&D Intensity ────────────────────────────────────

col5, col6 = st.columns(2)

with col5:
    st.subheader("Peer Revenue Comparison (Latest Year)")
    fig = px.bar(
        comp_filtered.sort_values("revenue_bn", ascending=True),
        x="revenue_bn",
        y="ticker",
        orientation="h",
        color="gross_margin_pct",
        color_continuous_scale="Blues",
        labels={
            "revenue_bn":       "Revenue ($B)",
            "ticker":           "Company",
            "gross_margin_pct": "Gross Margin %"
        }
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

with col6:
    st.subheader("R&D Intensity (% of Revenue)")
    rd_df = rev_filtered[rev_filtered["rd_intensity_pct"].notna()]
    fig = px.line(
        rd_df,
        x="fiscal_year",
        y="rd_intensity_pct",
        color="ticker",
        markers=True,
        labels={
            "fiscal_year":      "Year",
            "rd_intensity_pct": "R&D / Revenue (%)",
            "ticker":           "Company"
        }
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Detailed Table ────────────────────────────────────────────────────────────

st.subheader("Full Comparison Table")
display_df = comp_filtered[[
    "ticker", "report_year", "revenue_bn", "gross_margin_pct",
    "operating_margin_pct", "net_margin_pct", "rd_intensity_pct",
    "revenue_growth_pct", "revenue_cagr_3yr", "cash_bn", "long_term_debt_bn"
]].copy()

display_df.columns = [
    "Ticker", "Year", "Revenue ($B)", "Gross Margin %",
    "Operating Margin %", "Net Margin %", "R&D Intensity %",
    "YoY Growth %", "3yr CAGR %", "Cash ($B)", "LT Debt ($B)"
]

st.dataframe(
    display_df.style.format({
        "Revenue ($B)":       "{:.1f}",
        "Gross Margin %":     "{:.1f}",
        "Operating Margin %": "{:.1f}",
        "Net Margin %":       "{:.1f}",
        "R&D Intensity %":    "{:.1f}",
        "YoY Growth %":       "{:.1f}",
        "3yr CAGR %":         "{:.1f}",
        "Cash ($B)":          "{:.1f}",
        "LT Debt ($B)":       "{:.1f}",
    }, na_rep="N/A"),
    use_container_width=True
)

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption("Data: SEC EDGAR XBRL API · Pipeline: Python → DuckDB (bronze) → dbt models (silver/gold) · Dashboard: Streamlit + Plotly")