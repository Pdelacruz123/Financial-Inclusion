# Financial-Inclusion
Open-source financial inclusion pipeline and dashboard using data from the World Bank (API v2) and Global Findex. Configurable by country via a YAML file. Built with Python, DuckDB, SQL, GitHub Actions, and pytest.

Status: stage 2 (9 indicators and the 20 Latin American countries from `config.yaml`).

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate          # on Windows
pip install -r requirements.txt

python src/load_indicator.py    # downloads the indicators in config.yaml into data/monitor.duckdb
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

- The World Bank: World Development Indicators: Global Findex Database (FX.OWN.TOTL.ZS, FX.OWN.TOTL.FE.ZS, FX.OWN.TOTL.40.ZS)
- The World Bank: World Development Indicators: IMF Financial Access Survey (FB.CBK.BRCH.P5, FB.ATM.TOTL.P5)
- The World Bank: World Development Indicators: ITU World Telecommunication/ICT Indicators Database (IT.CEL.SETS.P2, IT.NET.USER.ZS)
- The World Bank: World Development Indicators: IMF International Financial Statistics and World Bank/OECD estimates (FS.AST.PRVT.GD.ZS)
- The World Bank: World Development Indicators: World Bank and OECD national accounts data (NY.GDP.PCAP.CD)

This project is not affiliated with or endorsed by the World Bank.
