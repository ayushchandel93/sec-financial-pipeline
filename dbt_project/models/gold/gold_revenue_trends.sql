-- gold_revenue_trends.sql
-- Year over year revenue growth per company
-- Powers the main trend chart on the dashboard

WITH annual AS (
    SELECT
        ticker,
        fiscal_year,
        revenue,
        gross_profit,
        operating_income,
        net_income,
        rd_expense,
        gross_margin_pct,
        operating_margin_pct,
        net_margin_pct,
        rd_intensity_pct,
        operating_cash_flow,
        cash,
        long_term_debt,
        total_assets
    FROM main_silver.silver_financials
    WHERE filing_type = 'Annual'
      AND fiscal_year BETWEEN 2015 AND 2024
),

with_growth AS (
    SELECT
        ticker,
        fiscal_year,
        revenue,
        gross_profit,
        operating_income,
        net_income,
        rd_expense,
        gross_margin_pct,
        operating_margin_pct,
        net_margin_pct,
        rd_intensity_pct,
        operating_cash_flow,
        cash,
        long_term_debt,
        total_assets,
        -- YoY revenue growth
        LAG(revenue) OVER (
            PARTITION BY ticker ORDER BY fiscal_year
        )                                                   AS prev_year_revenue,
        CASE
            WHEN LAG(revenue) OVER (
                PARTITION BY ticker ORDER BY fiscal_year
            ) > 0
            THEN ROUND(
                (revenue - LAG(revenue) OVER (
                    PARTITION BY ticker ORDER BY fiscal_year
                )) / LAG(revenue) OVER (
                    PARTITION BY ticker ORDER BY fiscal_year
                ) * 100, 2)
        END                                                 AS revenue_growth_pct,
        -- Revenue rank among peers for that year
        RANK() OVER (
            PARTITION BY fiscal_year ORDER BY revenue DESC
        )                                                   AS revenue_rank
    FROM annual
)

SELECT
    ticker,
    fiscal_year,
    -- Scale to billions for readability
    ROUND(revenue            / 1e9, 2)  AS revenue_bn,
    ROUND(gross_profit       / 1e9, 2)  AS gross_profit_bn,
    ROUND(operating_income   / 1e9, 2)  AS operating_income_bn,
    ROUND(net_income         / 1e9, 2)  AS net_income_bn,
    ROUND(rd_expense         / 1e9, 2)  AS rd_expense_bn,
    ROUND(operating_cash_flow/ 1e9, 2)  AS operating_cash_flow_bn,
    ROUND(cash               / 1e9, 2)  AS cash_bn,
    ROUND(long_term_debt     / 1e9, 2)  AS long_term_debt_bn,
    ROUND(total_assets       / 1e9, 2)  AS total_assets_bn,
    gross_margin_pct,
    operating_margin_pct,
    net_margin_pct,
    rd_intensity_pct,
    revenue_growth_pct,
    prev_year_revenue,
    revenue_rank
FROM with_growth
ORDER BY ticker, fiscal_year