-- gold_margin_trends.sql
-- Margin evolution over time per company
-- Powers the margin trend chart

SELECT
    ticker,
    fiscal_year,
    gross_margin_pct,
    operating_margin_pct,
    net_margin_pct,
    rd_intensity_pct,
    -- Industry average margins per year
    ROUND(AVG(gross_margin_pct) OVER (
        PARTITION BY fiscal_year
    ), 2)                           AS industry_avg_gross_margin,
    ROUND(AVG(operating_margin_pct) OVER (
        PARTITION BY fiscal_year
    ), 2)                           AS industry_avg_operating_margin,
    ROUND(AVG(net_margin_pct) OVER (
        PARTITION BY fiscal_year
    ), 2)                           AS industry_avg_net_margin,
    -- Above/below industry average
    CASE
        WHEN gross_margin_pct > AVG(gross_margin_pct) OVER (PARTITION BY fiscal_year)
        THEN 'Above Average'
        ELSE 'Below Average'
    END                             AS gross_margin_vs_industry
FROM main_silver.silver_financials
WHERE filing_type = 'Annual'
  AND fiscal_year BETWEEN 2015 AND 2024
  AND gross_margin_pct IS NOT NULL
ORDER BY ticker, fiscal_year