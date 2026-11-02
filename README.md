# Financial-Inclusion
Open-source financial inclusion pipeline and dashboard using data from the World Bank (API v2) and Global Findex. Configurable by country via a YAML file. Built with Python, DuckDB, SQL, GitHub Actions, and pytest.

Estado: etapa 1 (Perú + un indicador, de punta a punta).

## Cómo correrlo

```bash
python -m venv .venv
.venv\Scripts\activate          # en Windows
pip install -r requirements.txt

python src/cargar_peru.py       # descarga Perú y lo guarda en data/monitor.duckdb
pytest                          # corre los tests
```

## Estructura

| Carpeta | Qué contiene |
|---|---|
| `data/raw/` | JSON crudo de cada descarga, tal como llega de la API |
| `data/` | `monitor.duckdb`, la base de datos (no se sube a git) |
| `src/` | Código Python |
| `sql/` | Consultas SQL |
| `tests/` | Tests con pytest |
| `.github/workflows/` | CI (pendiente) |

## Fuentes y licencia de los datos

Datos bajo licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

- The World Bank: World Development Indicators: Global Findex Database (FX.OWN.TOTL.ZS)

Este proyecto no está afiliado ni respaldado por el Banco Mundial.
