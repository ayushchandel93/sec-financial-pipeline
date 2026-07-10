# src/get_companies.py
# Fetches all company tickers from SEC EDGAR and filters to Tech sector

import requests
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

HEADERS = {"User-Agent": os.getenv("SEC_USER_AGENT")}

# Tech companies we want (well-known, complete filings)
TECH_COMPANIES = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "AMD",
    "INTC", "CRM", "ADBE", "ORCL", "IBM", "CSCO", "QCOM",
    "TXN", "AVGO", "MU", "AMAT", "KLAC", "LRCX",
    "NOW", "SNOW", "PLTR", "NET", "DDOG", "MDB", "ZS",
    "TEAM", "OKTA", "HUBS"
]

def fetch_company_tickers() -> pd.DataFrame:
    """Fetch all company tickers from SEC EDGAR."""
    print("[companies] Fetching company list from SEC EDGAR...")
    
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    
    data = response.json()
    df   = pd.DataFrame.from_dict(data, orient="index")
    df.columns = ["cik", "ticker", "company_name"]
    df["cik"] = df["cik"].astype(str).str.zfill(10)  # pad to 10 digits
    
    print(f"[companies] Total companies in EDGAR: {len(df):,}")
    return df


def filter_tech_companies(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to our tech company list."""
    tech_df = df[df["ticker"].isin(TECH_COMPANIES)].copy()
    tech_df = tech_df.reset_index(drop=True)
    print(f"[companies] Tech companies found: {len(tech_df)}")
    return tech_df


def save_company_list(df: pd.DataFrame):
    """Save to data/raw for reference."""
    path = Path("data/raw/tech_companies.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"[companies] Saved → {path}")
    print(df[["ticker", "cik", "company_name"]].to_string(index=False))
    return df


def run():
    all_companies  = fetch_company_tickers()
    tech_companies = filter_tech_companies(all_companies)
    save_company_list(tech_companies)
    return tech_companies


if __name__ == "__main__":
    run()