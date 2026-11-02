-- Countries with no data or outdated data, per indicator.
-- Period = Findex edition, else the year. "outdated" means the country's
-- latest period is older than the newest period any country has.
CREATE OR REPLACE VIEW v_data_gaps AS
WITH periods AS (
    SELECT country_iso3, indicator, coalesce(edition, year) AS period
    FROM observations
),
countries AS (
    SELECT DISTINCT country_iso3 FROM periods
),
newest AS (
    SELECT indicator, max(period) AS newest_period FROM periods GROUP BY indicator
),
latest AS (
    SELECT country_iso3, indicator, max(period) AS latest_period
    FROM periods
    GROUP BY country_iso3, indicator
)
SELECT
    c.country_iso3,
    n.indicator,
    l.latest_period,
    n.newest_period,
    CASE WHEN l.latest_period IS NULL THEN 'no data' ELSE 'outdated' END AS gap
FROM countries AS c
CROSS JOIN newest AS n
LEFT JOIN latest AS l
    ON l.country_iso3 = c.country_iso3 AND l.indicator = n.indicator
WHERE l.latest_period IS NULL OR l.latest_period < n.newest_period;
