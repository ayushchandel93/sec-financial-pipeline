# src/ingest.py
# Fetches financial statements from SEC EDGAR for each company
# and loads them into DuckDB bronze layer

import requests
import json
import time
import pandas as pd
import duckdb
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

HEADERS = {"User-Agent": os.getenv("SEC_USER_AGENT")}
DB_PATH  = Path("data/warehouse.duckdb")
RAW_PATH = Path("data/raw")

# ── Fetch Company Facts ───────────────────────────────────────────────────────

def fetch_company_facts(cik: str, ticker: str) -> dict:
    """
    Fetch all financial facts for a company from SEC EDGAR.
    Returns raw JSON with all reported financial metrics.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"  [{ticker}] ✓ fetched {len(str(data)):,} bytes")
        return data
    except Exception as e:
        print(f"  [{ticker}] ✗ failed: {e}")
        return None


def save_raw(data: dict, ticker: str, cik: str):
    """Save raw JSON response to data/raw/."""
    folder = RAW_PATH / "company_facts"
    folder.mkdir(parents=True, exist_ok=True)
    
    file_path = folder / f"{ticker}_{cik}.json"
    with open(file_path, "w") as f:
        json.dump(data, f)
    return file_path

# ── Extract Key Financials ────────────────────────────────────────────────────

def extract_metric(facts: dict, metric: str, unit: str = "USD") -> list:
    """
    Extract a specific financial metric from company facts.
    Returns list of {value, period, form} dicts.
    """
    try:
        entries = facts["facts"]["us-gaap"][metric]["units"][unit]
        return [
            {
                "value":      e["val"],
                "start":      e.get("start"),
                "end":        e["end"],
                "form":       e["form"],        # 10-K, 10-Q etc
                "filed":      e["filed"],
                "accn":       e["accn"],        # accession number
            }
            for e in entries
            # Only annual (10-K) and quarterly (10-Q) filings
            if e["form"] in ["10-K", "10-Q"]
        ]
    except KeyError:
        return []


def extract_financials(facts: dict, ticker: str, cik: str) -> pd.DataFrame:
    """
    Extract key financial metrics for a company.
    Covers Income Statement, Balance Sheet, Cash Flow.
    """
    # Metrics to extract — (sec_name, our_name)
    metrics = [
        # Income Statement
        ("Revenues",                          "revenue"),
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "revenue_alt"),
        ("GrossProfit",                       "gross_profit"),
        ("OperatingIncomeLoss",               "operating_income"),
        ("NetIncomeLoss",                     "net_income"),
        ("ResearchAndDevelopmentExpense",     "rd_expense"),
        ("SellingGeneralAndAdministrativeExpense", "sga_expense"),
        # Balance Sheet
        ("Assets",                            "total_assets"),
        ("Liabilities",                       "total_liabilities"),
        ("StockholdersEquity",                "stockholders_equity"),
        ("CashAndCashEquivalentsAtCarryingValue", "cash"),
        ("LongTermDebt",                      "long_term_debt"),
        # Cash Flow
        ("NetCashProvidedByUsedInOperatingActivities", "operating_cash_flow"),
        ("CapitalExpenditureNet",             "capex"),
    ]

    rows = []
    for sec_name, our_name in metrics:
        entries = extract_metric(facts, sec_name)
        
        # If primary metric empty, try alternate
        if not entries and our_name == "revenue":
            entries = extract_metric(facts, "RevenueFromContractWithCustomerExcludingAssessedTax")

        for entry in entries:
            rows.append({
                "ticker":      ticker,
                "cik":         cik,
                "metric":      our_name,
                "value":       entry["value"],
                "period_start": entry["start"],
                "period_end":  entry["end"],
                "form":        entry["form"],
                "filed_date":  entry["filed"],
                "accn":        entry["accn"],
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["period_end"]   = pd.to_datetime(df["period_end"])
        df["filed_date"]   = pd.to_datetime(df["filed_date"])
        df["period_start"] = pd.to_datetime(df["period_start"], errors="coerce")
        # Only keep data from 2015 onwards
        df = df[df["period_end"].dt.year >= 2015]

    return df

# ── Load to DuckDB ────────────────────────────────────────────────────────────

def load_to_bronze(df: pd.DataFrame, conn: duckdb.DuckDBPyConnection):
    """Load extracted financials into DuckDB bronze layer."""
    if df.empty:
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze_financials (
            ticker        VARCHAR,
            cik           VARCHAR,
            metric        VARCHAR,
            value         DOUBLE,
            period_start  DATE,
            period_end    DATE,
            form          VARCHAR,
            filed_date    DATE,
            accn          VARCHAR,
            ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Delete existing rows for this ticker (idempotent)
    conn.execute("DELETE FROM bronze_financials WHERE ticker = ?", [df["ticker"].iloc[0]])

    # Insert explicitly listing columns — excludes ingested_at (has DEFAULT)
    conn.execute("""
        INSERT INTO bronze_financials 
            (ticker, cik, metric, value, period_start, period_end, form, filed_date, accn)
        SELECT 
            ticker, cik, metric, value, period_start, period_end, form, filed_date, accn
        FROM df
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM bronze_financials WHERE ticker = ?",
        [df["ticker"].iloc[0]]
    ).fetchone()[0]

    print(f"  [{df['ticker'].iloc[0]}] ✓ {count:,} rows loaded to bronze")

# ── Main ──────────────────────────────────────────────────────────────────────

def run_ingestion():
    # Load company list
    companies = pd.read_csv("data/raw/tech_companies.csv")
    print(f"\n══ SEC Ingestion: {len(companies)} companies ══\n")

    # Connect to DuckDB
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))

    summary = []

    for _, row in companies.iterrows():
        ticker = row["ticker"]
        cik    = str(row["cik"]).zfill(10)
        name   = row["company_name"]

        print(f"\n[{ticker}] {name}")

        # 1. Fetch raw data
        facts = fetch_company_facts(cik, ticker)
        if not facts:
            summary.append({"ticker": ticker, "status": "failed"})
            continue

        # 2. Save raw JSON
        save_raw(facts, ticker, cik)

        # 3. Extract financials
        df = extract_financials(facts, ticker, cik)
        if df.empty:
            print(f"  [{ticker}] ✗ no financial data extracted")
            summary.append({"ticker": ticker, "status": "no_data"})
            continue

        print(f"  [{ticker}] extracted {len(df):,} metric rows")

        # 4. Load to DuckDB bronze
        load_to_bronze(df, conn)
        summary.append({"ticker": ticker, "status": "success", "rows": len(df)})

        # SEC rate limit — be polite
        time.sleep(0.5)

    # Summary
    print(f"\n══ Ingestion Summary ══")
    for s in summary:
        status = "✓" if s["status"] == "success" else "✗"
        rows   = f"{s.get('rows', 0):,} rows" if s["status"] == "success" else s["status"]
        print(f"  {status} {s['ticker']}: {rows}")

    # Quick check
    total = conn.execute("SELECT COUNT(*) FROM bronze_financials").fetchone()[0]
    tickers = conn.execute(
        "SELECT COUNT(DISTINCT ticker) FROM bronze_financials"
    ).fetchone()[0]
    print(f"\n[bronze] Total: {total:,} rows across {tickers} companies")

    conn.close()


if __name__ == "__main__":
    run_ingestion()