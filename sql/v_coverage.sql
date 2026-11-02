-- Coverage per indicator: country-period cells with data / possible cells.
-- Period = Findex edition (a 2022 survey counts for the 2021 edition), else the year.
-- Possible cells = every loaded country x every period that indicator has for
-- any country. So Findex only counts its editions, and a year nobody has
-- published yet is not counted as missing.
-- shortcut: a country with no rows at all is not counted; compare against config.yaml if that matters.
CREATE OR REPLACE VIEW v_coverage AS
WITH periods AS (
    SELECT country_iso3, indicator, coalesce(edition, year) AS period, value
    FROM observations
),
countries AS (
    SELECT DISTINCT country_iso3 FROM periods
),
indicator_periods AS (
    SELECT DISTINCT indicator, period FROM periods
),
possible_cells AS (
    SELECT ip.indicator, ip.period, c.country_iso3
    FROM indicator_periods AS ip
    CROSS JOIN countries AS c
)
SELECT
    pc.indicator,
    count(p.value)                                 AS cells_with_data,
    count(*)                                       AS possible_cells,
    round(100.0 * count(p.value) / count(*), 1)    AS coverage_pct
FROM possible_cells AS pc
LEFT JOIN periods AS p USING (indicator, period, country_iso3)
GROUP BY pc.indicator;
