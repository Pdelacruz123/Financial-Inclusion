# Financial-Inclusion
Open-source financial inclusion pipeline and dashboard using data from the World Bank (API v2) and Global Findex. Configurable by country via a YAML file. Built with Python, DuckDB, SQL, GitHub Actions, and pytest.

Status: stage 1 (one example country + one indicator, end to end).

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate          # on Windows
pip install -r requirements.txt

python src/load_indicator.py    # downloads the data into data/monitor.duckdb
python src/plot_indicator.py    # saves a chart to output/
pytest                          # runs the tests
```

## Layout

| Folder | Contents |
|---|---|
| `data/raw/` | Raw JSON of each download, exactly as returned by the API |
| `data/` | `monitor.duckdb`, the database (not committed) |
| `src/` | Python code |
| `sql/` | SQL queries |
| `tests/` | pytest tests |
| `.github/workflows/` | CI (pending) |

## Data sources and license

Data licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

- The World Bank: World Development Indicators: Global Findex Database (FX.OWN.TOTL.ZS)

This project is not affiliated with or endorsed by the World Bank.
