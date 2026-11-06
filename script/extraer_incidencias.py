"""
Saca de relevos_historico.csv cada mención a un equipo (tag) con su contexto.

Mejoras respecto a la versión anterior:
  - CONTEXTO: además de la línea donde sale el equipo ("descripcion"),
    guarda las líneas de alrededor ("contexto"). Antes solo se guardaba la
    línea suelta, con el mismo problema que tenía el buscador.
  - Reconoce tags con guion (P-101B, T-201) además de sin guion (P101B).
    La columna "equipo_norm" (sin guiones ni espacios) permite que P-101B y
    P101B cuenten como el mismo equipo.
  - Quita duplicados (el mismo equipo repetido en la misma línea).
  - Descarta prefijos que no son equipos (OT4455 = orden de trabajo...).
  - Añade "fecha" y "etiquetas" (problemas/acciones detectados en el contexto).

Uso:
    python extraer_incidencias.py
"""

import os
import re

import pandas as pd

from buscador import (
    ACCIONES,
    PROBLEMAS,
    extraer_fecha,
    normalizar,
    normalizar_tag,
    segmentar,
)

CARPETA_BASE = os.environ.get("PARTES_BASE", r"C:\ProyectoPartesRelevo\base")
ENTRADA = os.path.join(CARPETA_BASE, "relevos_historico.csv")
SALIDA = os.path.join(CARPETA_BASE, "incidencias.csv")

# Líneas que se guardan por delante y por detrás de cada mención
CONTEXTO = 2

# 1-4 letras, guion opcional, 2-5 cifras y sufijo opcional: P-101B, FV2034, TK-12-A
PATRON_EQUIPO = re.compile(r"\b[A-Z]{1,4}-?[0-9]{2,5}[A-Z0-9\-]*")

# Prefijos que cumplen el patrón pero NO son equipos. Ajusta esta lista
# a tu planta cuando veas falsos positivos en la ficha de equipo.
PREFIJOS_EXCLUIDOS = {"OT"}


def etiquetar(texto):
    t = normalizar(texto)
    return ", ".join(p for p in PROBLEMAS + ACCIONES if p in t)


def main():
    df = pd.read_csv(ENTRADA)
    df["texto"] = df["texto"].fillna("").astype(str)

    incidencias = []

    for _, fila in df.iterrows():
        archivo = fila["archivo"]
        fecha = fila["fecha"] if "fecha" in df.columns and pd.notna(fila.get("fecha")) \
            else extraer_fecha(archivo)
        lineas = segmentar(fila["texto"])

        for i, linea in enumerate(lineas):
            vistos = set()
            for m in PATRON_EQUIPO.finditer(linea):
                equipo = m.group().rstrip("-")
                prefijo = re.match(r"[A-Z]+", equipo).group()
                norm = normalizar_tag(equipo)
                if prefijo in PREFIJOS_EXCLUIDOS or norm in vistos:
                    continue
                vistos.add(norm)

                ini = max(0, i - CONTEXTO)
                contexto = "\n".join(lineas[ini:i + CONTEXTO + 1])

                incidencias.append({
                    "equipo": equipo,
                    "equipo_norm": norm,
                    "fecha": fecha,
                    "archivo": archivo,
                    "descripcion": linea,
                    "contexto": contexto,
                    "etiquetas": etiquetar(contexto),
                })

    inc = pd.DataFrame(incidencias)
    inc.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    print("Registros:", len(inc))
    if len(inc):
        print("Equipos distintos:", inc["equipo_norm"].nunique())
        print("Más mencionados:")
        print(inc["equipo"].value_counts().head(15).to_string())
    print("Salida:", SALIDA)


if __name__ == "__main__":
    main()
