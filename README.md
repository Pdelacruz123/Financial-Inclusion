# Financial-Inclusion
Open-source financial inclusion pipeline and dashboard using data from the World Bank (API v2) and Global Findex. Configurable by country via a YAML file. Built with Python, DuckDB, SQL, GitHub Actions, and pytest.

Status: stage 3 (9 indicators and the 20 Latin American countries from `config.yaml`, weekly load in CI).

## Just want the data?

Every Monday the pipeline publishes a [release](https://github.com/Pdelacruz123/Financial-Inclusion/releases) with:

- `monitor.duckdb`: the database. Latest: <https://github.com/Pdelacruz123/Financial-Inclusion/releases/latest/download/monitor.duckdb>
- `raw-json.zip`: the API responses exactly as received.

Open it with the [DuckDB CLI](https://duckdb.org/docs/installation/) or from Python:

```python
import duckdb
con = duckdb.connect("monitor.duckdb", read_only=True)
con.sql("SELECT * FROM v_coverage").show()
```

## Run it on your computer

Requires Python 3.12 (tested) and internet access. No API key is needed.

```bash
python -m venv .venv

# activate the virtual environment
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # macOS / Linux

pip install -r requirements.txt

python src/load_indicator.py    # downloads the indicators in config.yaml into data/monitor.duckdb
python src/plot_indicator.py    # saves a chart to output/
pytest                          # runs the tests (they also call the World Bank API)

streamlit run src/dashboard.py  # opens the dashboard in your browser
```

The dashboard uses `data/monitor.duckdb` if it exists; otherwise it downloads the latest weekly release, so `streamlit run src/dashboard.py` works even without running the loader.

To change countries or indicators, edit `config.yaml` and run the loader again. Countries are ISO3 codes (e.g. `CHL`); aggregates such as `WLD` or `LCN` are rejected by the tests. A new indicator also needs a valid range in `tests/test_ranges.py`.

## Run your own weekly load

1. Fork this repository.
2. In your fork, open the **Actions** tab and enable workflows (GitHub disables them on forks).
3. Click **Load and test → Run workflow** to run it now; after that it runs every Monday at 06:00 UTC and publishes a release in your fork.

The workflow is `.github/workflows/weekly.yml`. On every push and pull request it loads the data and runs the tests, without publishing.

## Layout

| Path | Contents |
|---|---|
| `config.yaml` | Countries and indicators to load |
| `src/` | Python code: loader, chart and Streamlit dashboard |
| `sql/` | SQL views, created by the loader |
| `tests/` | pytest tests |
| `data/raw/` | Raw JSON of each download (not committed; published in releases) |
| `data/monitor.duckdb` | The database (not committed; published in releases) |
| `.github/workflows/` | Weekly load and tests |

## Validation

- **Coverage:** `SELECT * FROM v_coverage` gives the share of country-year cells with data per indicator (Findex counts survey editions only). With the 20 default countries: 1,858 of 1,980 cells (93.8%), measured 2026-11-02.
- **Time to add a country:** add one line to `config.yaml`, then run the loader (~15-18 s, one request per indicator for all countries) and the tests (~7-19 s, they call the API). Measured 2026-11-02 on a home connection.
- **Findex margins of error:** `data/findex_sample.csv` holds interviews and design effect per country for the 2021 and 2024 editions, from the Findex survey methodology (Table A.1). The margin is computed as `1.96 * sqrt(0.25 / interviews) * sqrt(design_effect)`, which reproduces the published margin in 35 of 36 rows; the other one is a typo in the 2021 methodology (Brazil: 1.5 printed, 4.8 by formula). `v_findex_change` flags a change between editions as significant only when it exceeds the margin of the change, `sqrt(m1^2 + m2^2)`. Earlier editions and subgroups (women, poorest 40%) have no margin.
- **Validation sample:** `data/validation_sample.csv` holds 30 values drawn with a fixed seed (10 Findex, 10 IMF FAS, 10 ITU), each compared with its primary source rather than with data.worldbank.org. `src/validation_sample.py` draws it once, fills the Findex rows from the official Findex file and the IMF FAS rows from the IMF API (`api.imf.org`, series FA26 and FA18 per 100,000 adults); ITU rows are filled by hand from ITU DataHub. Result on 2026-11-02: 19 of 20 checked values match, and the other one is a documented IMF revision (Brazil ATMs 2023); `tests/test_validation_sample.py` checks every filled value against the database. Private credit and GDP per capita are context indicators (financial depth and income, not inclusion) and are not sampled.
- **Findex survey year:** some countries of an edition were surveyed a year later (Guatemala and Mexico: 2021 edition, surveyed in 2022). `edition` and `survey_year` keep both.

## Upstream changes that can affect this project

The data belongs to the World Bank and its sources (Findex, IMF, ITU), and they change it. What can happen, what already protects the project, and what is still open (checked against the API on 2026-11-02):

| Change on the World Bank side | Effect here | Mitigation in place | Still open |
|---|---|---|---|
| **Past values are revised.** The API reports a `lastupdated` date per source (WDI: 2026-10-08). | The dashboard shows new numbers with no warning. | Each weekly release keeps the raw JSON and `extracted_at`, so any two loads can be compared. Checked values in `validation_sample.csv` make the tests fail if they change. | `lastupdated` is kept in the raw JSON but not in the database. |
| **An indicator is retired from WDI.** Retired series move to the source "WDI Database Archives" (id 57). | The loader gets no data for that code. | The loader raises when the API returns no data, and `test_indicator_codes.py` checks every code. The CI job fails, no release is published, and the previous release stays as the latest one, which the dashboard keeps using. | Choosing a replacement indicator is manual. |
| **The same data lives in two sources with different update dates.** Findex is in WDI (id 2, updated 2026-10-08) and in "Global Findex database" (id 28, updated 2025-10-06). | Our values can briefly differ from a Findex page that reads the other source. | The loader always uses WDI, and the raw JSON records `sourceid`. | — |
| **A new Findex edition is published.** | Without a guard, its surveys would be filed under the 2024 edition. | `findex_edition()` raises if a survey year is more than one year after a known edition (tested). | Add the edition to `FINDEX_EDITIONS`, add its sample sizes (methodology Table A.1) to `data/findex_sample.csv`, and review the control values. |
| **The API changes version, goes down or limits requests.** Version 1 was retired in 2018 and stopped working in 2020; usage limits are not documented. | Loads fail. | Three retries with growing waits, a pause between requests, and the release is only published after the tests pass. | Moving to a new API version would mean rewriting `fetch()`. |
| **More data per request than one page.** | The loader stops with "pagination is missing". | Requests ask for 1,000 rows per page and fail explicitly if there are more. With 14 years per country that is about 71 countries per request. | Add pagination before loading more than about 70 countries. |
| **A country is renamed or a code changes.** | Old names in the dashboard, or a missing country. | Names are taken from the API on every load. `test_country_codes.py` fails if a code stops resolving or becomes an aggregate. | — |
| **An indicator's definition changes.** The current account definition includes mobile money. | Editions measured with different definitions get compared. | None automatic. | Read each indicator's `sourceNote` when a new edition comes out. |
| **IMF or ITU revise their figures.** The World Bank republishes them later. Already seen: Brazil's ATMs per 100,000 adults match the IMF up to 2019, but for 2020-2024 the IMF now publishes lower values (2023: World Bank 100.67, IMF 69.61). | The dashboard can show figures the original source has already revised. | The validation test allows 0.05 or 0.5%, and `KNOWN_DIFFERENCES` in `tests/test_validation_sample.py` documents each explained difference. The test fails if a new difference appears or a known one disappears. | The sample checks only 30 values, so other revised series can go unnoticed. The ITU stopped publishing the World Telecommunication/ICT Indicators Database in 2024 and now uses ITU DataHub. |

## License

Code: [MIT](LICENSE). Data: see below.

## Data sources and license

Data licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

- The World Bank: World Development Indicators: Global Findex Database (FX.OWN.TOTL.ZS, FX.OWN.TOTL.FE.ZS, FX.OWN.TOTL.40.ZS)
- The World Bank: World Development Indicators: IMF Financial Access Survey (FB.CBK.BRCH.P5, FB.ATM.TOTL.P5)
- The World Bank: World Development Indicators: ITU World Telecommunication/ICT Indicators Database (IT.CEL.SETS.P2, IT.NET.USER.ZS)
- The World Bank: World Development Indicators: IMF International Financial Statistics and World Bank/OECD estimates (FS.AST.PRVT.GD.ZS)
- The World Bank: World Development Indicators: World Bank and OECD national accounts data (NY.GDP.PCAP.CD)

This project is not affiliated with or endorsed by the World Bank.
