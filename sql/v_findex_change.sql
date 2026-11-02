-- Findex values per edition with their margin of error (95%), and whether the
-- change from the previous edition is larger than the margin of that change.
--   margin        = 1.96 * sqrt(0.25 / interviews) * sqrt(design_effect), in points
--   change_margin = sqrt(margin_previous^2 + margin^2)  (two independent surveys)
-- The margin uses the national sample, so it is only filled for total account
-- ownership; subgroups (women, poorest 40%) have fewer interviews and a larger,
-- unpublished margin, so theirs stays NULL. Editions without sample data
-- (before 2021) also get NULL: "margin not available".
CREATE OR REPLACE VIEW v_findex_change AS
WITH with_margin AS (
    SELECT
        o.country_iso3,
        o.indicator,
        o.edition,
        o.survey_year,
        o.value,
        100 * 1.96 * sqrt(0.25 / s.interviews) * sqrt(s.design_effect) AS margin
    FROM observations AS o
    LEFT JOIN findex_sample AS s
        ON  s.country_iso3 = o.country_iso3
        AND s.edition = o.edition
        AND o.indicator = 'FX.OWN.TOTL.ZS'
    WHERE o.indicator LIKE 'FX.%'
),
with_previous AS (
    SELECT
        *,
        LAG(edition) OVER w AS previous_edition,
        LAG(value)   OVER w AS previous_value,
        LAG(margin)  OVER w AS previous_margin
    FROM with_margin
    WINDOW w AS (PARTITION BY country_iso3, indicator ORDER BY edition)
)
SELECT
    country_iso3,
    indicator,
    edition,
    survey_year,
    value,
    margin,
    previous_edition,
    previous_value,
    value - previous_value                              AS change,
    sqrt(pow(previous_margin, 2) + pow(margin, 2))      AS change_margin,
    abs(value - previous_value)
        > sqrt(pow(previous_margin, 2) + pow(margin, 2)) AS significant
FROM with_previous;
