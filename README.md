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
```

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
| `src/` | Python code: loader and chart |
| `sql/` | SQL views, created by the loader |
| `tests/` | pytest tests |
| `data/raw/` | Raw JSON of each download (not committed; published in releases) |
| `data/monitor.duckdb` | The database (not committed; published in releases) |
| `.github/workflows/` | Weekly load and tests |

## Validation

- **Coverage:** `SELECT * FROM v_coverage` gives the share of country-year cells with data per indicator (Findex counts survey editions only). With the 20 default countries: 1,858 of 1,980 cells (93.8%), measured 2026-11-02.
- **Time to add a country:** add one line to `config.yaml`, then run the loader (~15-18 s, one request per indicator for all countries) and the tests (~7-19 s, they call the API). Measured 2026-11-02 on a home connection.
- **Findex survey year:** some countries of an edition were surveyed a year later (Guatemala and Mexico: 2021 edition, surveyed in 2022). `edition` and `survey_year` keep both.

## Data sources and license

Data licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

- The World Bank: World Development Indicators: Global Findex Database (FX.OWN.TOTL.ZS, FX.OWN.TOTL.FE.ZS, FX.OWN.TOTL.40.ZS)
- The World Bank: World Development Indicators: IMF Financial Access Survey (FB.CBK.BRCH.P5, FB.ATM.TOTL.P5)
- The World Bank: World Development Indicators: ITU World Telecommunication/ICT Indicators Database (IT.CEL.SETS.P2, IT.NET.USER.ZS)
- The World Bank: World Development Indicators: IMF International Financial Statistics and World Bank/OECD estimates (FS.AST.PRVT.GD.ZS)
- The World Bank: World Development Indicators: World Bank and OECD national accounts data (NY.GDP.PCAP.CD)

This project is not affiliated with or endorsed by the World Bank.
