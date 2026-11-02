"""Valores de control de Perú (Tabla B.1 del libro Findex 2025).

Requiere haber corrido antes:  python src/cargar_peru.py
"""

from pathlib import Path

import duckdb
import pytest

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "monitor.duckdb"


@pytest.fixture
def con():
    """Abre la base en modo solo lectura y la cierra al terminar el test."""
    if not RUTA_DB.exists():
        pytest.fail(f"No existe {RUTA_DB}. Corre primero: python src/cargar_peru.py")
    conexion = duckdb.connect(str(RUTA_DB), read_only=True)
    yield conexion
    conexion.close()


def valor_cuenta_peru(con, anio):
    fila = con.execute(
        """
        SELECT valor FROM observaciones
        WHERE pais_iso3 = 'PER' AND indicador = 'FX.OWN.TOTL.ZS' AND anio = ?
        """,
        [anio],
    ).fetchone()
    assert fila is not None, f"No hay dato de Perú para {anio}"
    return fila[0]


def test_cuenta_peru_2024_es_59(con):
    # Tabla B.1 publica 59 (redondeado); aceptamos +-0,5.
    assert 58.5 <= valor_cuenta_peru(con, 2024) <= 59.5


def test_cuenta_peru_2021_es_57(con):
    assert 56.5 <= valor_cuenta_peru(con, 2021) <= 57.5
