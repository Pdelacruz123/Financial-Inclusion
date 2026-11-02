-- Change of each indicator between consecutive years with data.
-- Years without data are never stored, so for Findex (triennial) this
-- compares consecutive survey editions, e.g. 2021 -> 2024.
CREATE OR REPLACE VIEW v_indicator_change AS
SELECT
    country_iso3,
    indicator,
    year,
    value,
    LAG(year)  OVER w         AS previous_year,
    LAG(value) OVER w         AS previous_value,
    value - LAG(value) OVER w AS change
FROM observations
WINDOW w AS (PARTITION BY country_iso3, indicator ORDER BY year);
