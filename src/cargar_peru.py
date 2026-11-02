"""Descarga FX.OWN.TOTL.ZS (cuenta, % adultos 15+) de Perú y lo guarda en DuckDB.

Pasos:
1. Llama a la API v2 del Banco Mundial (con pausas y reintentos).
2. Guarda el JSON crudo en data/raw/ (para tener historial de revisiones).
3. Convierte la respuesta en una tabla con pandas.
4. Reemplaza las filas de Perú + indicador en la tabla `observaciones` de DuckDB.

Uso:  python src/cargar_peru.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests

PAIS = "PER"
INDICADOR = "FX.OWN.TOTL.ZS"
RANGO_ANIOS = "2011:2024"

URL_API = "https://api.worldbank.org/v2/country/{pais}/indicator/{indicador}"

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RAW = RAIZ / "data" / "raw"
RUTA_DB = RAIZ / "data" / "monitor.duckdb"


def descargar(pais, indicador, intentos=3, pausa_seg=2):
    """Pide los datos a la API y devuelve el JSON ya convertido a listas/dicts.

    Si falla (red caída, error 5xx...), espera y reintenta. La espera crece
    en cada intento: 2 s, 4 s, 6 s.
    """
    url = URL_API.format(pais=pais, indicador=indicador)
    params = {"format": "json", "date": RANGO_ANIOS, "per_page": 1000}

    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.get(url, params=params, timeout=30)
            respuesta.raise_for_status()  # lanza error si el código HTTP no es 200
            datos = respuesta.json()
            break
        except requests.RequestException as error:
            if intento == intentos:
                raise
            espera = pausa_seg * intento
            print(f"Intento {intento} falló ({error}). Reintento en {espera} s...")
            time.sleep(espera)

    # Respuesta normal: [metadatos, [filas]]. Con un código inválido la API
    # responde 200 pero con [{"message": [...]}], así que lo revisamos aquí.
    if len(datos) < 2 or datos[1] is None:
        raise ValueError(f"La API no devolvió datos para {pais}/{indicador}: {datos}")
    if datos[0]["pages"] > 1:
        raise ValueError("La respuesta tiene más de una página; falta paginar.")

    return datos


def guardar_crudo(datos, pais, indicador, extraido_el):
    """Guarda el JSON tal cual llegó. El nombre lleva fecha y hora (UTC)."""
    CARPETA_RAW.mkdir(parents=True, exist_ok=True)
    marca = extraido_el.strftime("%Y-%m-%dT%H%M%SZ")  # sin ":" porque Windows no los acepta
    ruta = CARPETA_RAW / f"{indicador}_{pais}_{marca}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def a_tabla(datos, extraido_el):
    """Convierte las filas de la API en un DataFrame con nuestras columnas.

    Los años sin valor (null) se descartan: Findex es trienal y no se interpola.
    """
    filas = []
    for registro in datos[1]:
        if registro["value"] is None:
            continue
        anio = int(registro["date"])
        filas.append(
            {
                "pais_iso3": registro["countryiso3code"],
                "indicador": registro["indicator"]["id"],
                "anio": anio,
                "edicion": anio,  # edición de Findex = año que reporta la API
                "anio_encuesta": None,  # la API no lo trae; se llenará con el archivo oficial de Findex
                "valor": float(registro["value"]),
                "extraido_el": extraido_el.replace(tzinfo=None),  # se guarda en UTC
            }
        )
    tabla = pd.DataFrame(filas)
    tabla["anio_encuesta"] = tabla["anio_encuesta"].astype("Int64")  # entero que admite vacíos
    return tabla


def guardar_en_duckdb(tabla, pais, indicador, ruta_db=RUTA_DB):
    """Reemplaza las filas de este país + indicador, para no duplicar si se corre dos veces."""
    con = duckdb.connect(str(ruta_db))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS observaciones (
                pais_iso3     VARCHAR   NOT NULL,
                indicador     VARCHAR   NOT NULL,
                anio          INTEGER   NOT NULL,
                edicion       INTEGER,
                anio_encuesta INTEGER,
                valor         DOUBLE    NOT NULL,
                extraido_el   TIMESTAMP NOT NULL,  -- hora UTC de la descarga
                PRIMARY KEY (pais_iso3, indicador, anio)
            )
            """
        )
        # Una transacción: o se hace el borrado + inserción completo, o nada.
        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM observaciones WHERE pais_iso3 = ? AND indicador = ?",
            [pais, indicador],
        )
        con.register("tabla_nueva", tabla)  # DuckDB puede leer el DataFrame por nombre
        con.execute(
            """
            INSERT INTO observaciones
            SELECT pais_iso3, indicador, anio, edicion, anio_encuesta, valor, extraido_el
            FROM tabla_nueva
            """
        )
        con.execute("COMMIT")
    finally:
        con.close()


def main():
    extraido_el = datetime.now(timezone.utc)

    datos = descargar(PAIS, INDICADOR)
    ruta_crudo = guardar_crudo(datos, PAIS, INDICADOR, extraido_el)
    tabla = a_tabla(datos, extraido_el)
    guardar_en_duckdb(tabla, PAIS, INDICADOR)

    print(f"JSON crudo guardado en: {ruta_crudo.relative_to(RAIZ)}")
    print(f"Filas cargadas en {RUTA_DB.relative_to(RAIZ)}: {len(tabla)}")
    print(tabla[["pais_iso3", "anio", "valor"]].to_string(index=False))


if __name__ == "__main__":
    main()
