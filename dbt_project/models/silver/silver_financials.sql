-- silver_financials.sql
-- Cleans and pivots bronze data into one row per company per period
-- This is the core model everything else builds on

WITH base AS (
    SELECT
        ticker,
        cik,
        metric,
        value,
        period_start,
        period_end,
        form,
        filed_date,
        -- Extract year and quarter from period end
        YEAR(period_end)                                    AS fiscal_year,
        QUARTER(period_end)                                 AS fiscal_quarter,
        -- Flag annual vs quarterly filings
        CASE WHEN form = '10-K' THEN 'Annual'
             WHEN form = '10-Q' THEN 'Quarterly'
        END                                                 AS filing_type,
        -- Keep only one row per ticker/metric/period (latest filed)
        ROW_NUMBER() OVER (
            PARTITION BY ticker, metric, period_end
            ORDER BY filed_date DESC
        )                                                   AS row_num
    FROM main.bronze_financials
    WHERE value IS NOT NULL
      AND value != 0
      AND YEAR(period_end) BETWEEN 2015 AND 2024
),

deduplicated AS (
    SELECT * FROM base WHERE row_num = 1
),

-- Pivot metrics into columns
pivoted AS (
    SELECT
        ticker,
        cik,
        period_end,
        fiscal_year,
        fiscal_quarter,
        filing_type,
        filed_date,

        -- Income Statement
        MAX(CASE WHEN metric IN ('revenue', 'revenue_alt')
            THEN value END)                                 AS revenue,
        MAX(CASE WHEN metric = 'gross_profit'
            THEN value END)                                 AS gross_profit,
        MAX(CASE WHEN metric = 'operating_income'
            THEN value END)                                 AS operating_income,
        MAX(CASE WHEN metric = 'net_income'
            THEN value END)                                 AS net_income,
        MAX(CASE WHEN metric = 'rd_expense'
            THEN value END)                                 AS rd_expense,
        MAX(CASE WHEN metric = 'sga_expense'
            THEN value END)                                 AS sga_expense,

        -- Balance Sheet
        MAX(CASE WHEN metric = 'total_assets'
            THEN value END)                                 AS total_assets,
        MAX(CASE WHEN metric = 'total_liabilities'
            THEN value END)                                 AS total_liabilities,
        MAX(CASE WHEN metric = 'stockholders_equity'
            THEN value END)                                 AS stockholders_equity,
        MAX(CASE WHEN metric = 'cash'
            THEN value END)                                 AS cash,
        MAX(CASE WHEN metric = 'long_term_debt'
            THEN value END)                                 AS long_term_debt,

        -- Cash Flow
        MAX(CASE WHEN metric = 'operating_cash_flow'
            THEN value END)                                 AS operating_cash_flow,
        MAX(CASE WHEN metric = 'capex'
            THEN value END)                                 AS capex

    FROM deduplicated
    GROUP BY ticker, cik, period_end, fiscal_year,
             fiscal_quarter, filing_type, filed_date
)

SELECT
    ticker,
    cik,
    period_end,
    fiscal_year,
    fiscal_quarter,
    filing_type,
    filed_date,
    revenue,
    gross_profit,
    operating_income,
    net_income,
    rd_expense,
    sga_expense,
    total_assets,
    total_liabilities,
    stockholders_equity,
    cash
    long_term_debt,
    operating_cash_flow,
    capex,
    -- Derived margins (only when revenue exists)
    CASE WHEN revenue > 0
        THEN ROUND(gross_profit / revenue * 100, 2)
    END                                                     AS gross_margin_pct,
    CASE WHEN revenue > 0
        THEN ROUND(operating_income / revenue * 100, 2)
    END                                                     AS operating_margin_pct,
    CASE WHEN revenue > 0
        THEN ROUND(net_income / revenue * 100, 2)
    END                                                     AS net_margin_pct,
    CASE WHEN revenue > 0
        THEN ROUND(rd_expense / revenue * 100, 2)
    END                                                     AS rd_intensity_pct
FROM pivoted
WHERE revenue IS NOT NULL   -- must have revenue to be useful
ORDER BY ticker, period_end