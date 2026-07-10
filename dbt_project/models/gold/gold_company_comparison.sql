-- gold_company_comparison.sql
-- Latest year snapshot for peer comparison
-- Powers the comparison table and bar charts

WITH latest_year AS (
    SELECT
        ticker,
        MAX(fiscal_year) AS latest_year
    FROM main_gold.gold_revenue_trends
    GROUP BY ticker
),

comparison AS (
    SELECT
        r.ticker,
        r.fiscal_year,
        r.revenue_bn,
        r.gross_profit_bn,
        r.net_income_bn,
        r.rd_expense_bn,
        r.cash_bn,
        r.long_term_debt_bn,
        r.gross_margin_pct,
        r.operating_margin_pct,
        r.net_margin_pct,
        r.rd_intensity_pct,
        r.revenue_growth_pct,
        r.revenue_rank,
        -- 3 year revenue CAGR
        ROUND(
            (POWER(
                r.revenue_bn / NULLIF(
                    LAG(r.revenue_bn, 3) OVER (
                        PARTITION BY r.ticker ORDER BY r.fiscal_year
                    ), 0
                ), 1.0/3
            ) - 1) * 100, 2
        )                           AS revenue_cagr_3yr
    FROM main_gold.gold_revenue_trends r
    INNER JOIN latest_year l
        ON r.ticker = l.ticker
        AND r.fiscal_year = l.latest_year
)

SELECT
    ticker,
    fiscal_year                 AS report_year,
    revenue_bn,
    gross_profit_bn,
    net_income_bn,
    rd_expense_bn,
    cash_bn,
    long_term_debt_bn,
    gross_margin_pct,
    operating_margin_pct,
    net_margin_pct,
    rd_intensity_pct,
    revenue_growth_pct,
    revenue_cagr_3yr,
    revenue_rank
FROM comparison
ORDER BY revenue_bn DESC