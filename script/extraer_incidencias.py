"""
Saca de relevos_historico.csv cada mención a un equipo (tag) con su contexto.

Mejoras respecto a la versión anterior:
  - CONTEXTO: además de la línea donde sale el equipo ("descripcion"),
    guarda las líneas de alrededor ("contexto"). Antes solo se guardaba la
    línea suelta, con el mismo problema que tenía el buscador.
  - Reconoce los formatos de la planta: K-501, K501, PK601, PB101B2,
    PB-151A-2 y 6540C1, también escritos en minúscula.
    La columna "equipo_norm" (sin guiones ni espacios) permite que P-101B y
    P101B cuenten como el mismo equipo.
  - Quita duplicados (el mismo equipo repetido en la misma línea).
  - Descarta lo que no son equipos (OT4455, DN150, PN16, 500m3...).
  - Añade "fecha" y "etiquetas" (problemas/acciones de la línea).
  - Genera también incidencias_reales.csv (solo las líneas con alguna
    palabra clave), que es lo que usa la web. Sustituye a los scripts de
    incidencias_enriquecidas.csv e incidencias_reales.csv.
  - Busca PALABRAS COMPLETAS: antes "centrífuga" contaba como "fuga" y
    "preparada"/"separada" como "parada".

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
    normalizar_tag,
    palabras_presentes,
    segmentar,
)

CARPETA_BASE = os.environ.get("PARTES_BASE", r"C:\ProyectoPartesRelevo\base")
ENTRADA = os.path.join(CARPETA_BASE, "relevos_historico.csv")
SALIDA = os.path.join(CARPETA_BASE, "incidencias.csv")
SALIDA_REALES = os.path.join(CARPETA_BASE, "incidencias_reales.csv")

# Líneas que se guardan por delante y por detrás de cada mención
CONTEXTO = 2

# Formatos de tag de la planta:
#   Letras + número:  K-501, K501, PK601, PB101B2, PB-151A-2
#   (también en minúscula: "k501" se guarda como K501)
PATRON_LETRAS = re.compile(
    r"\b[A-Z]{1,4}-?\d{2,5}[A-Z]{0,2}\d{0,2}(?:-[A-Z0-9]{1,3})*\b",
    re.IGNORECASE,
)
#   Número + letra + número: 6540C1  (solo en mayúscula, para no coger
#   cantidades como "500m3")
PATRON_NUMERO = re.compile(r"\b\d{3,5}-?[A-Z]{1,2}\d{1,2}(?:-[A-Z0-9]{1,3})*\b")

# Cosas que cumplen el patrón pero NO son equipos. Ajusta estas listas
# a tu planta cuando veas falsos positivos en la ficha de equipo.
PREFIJOS_EXCLUIDOS = {
    "OT",        # orden de trabajo (OT4455)
    "DN", "PN",  # diámetro / presión nominal de tubería (DN150, PN16)
}
LETRAS_UNIDADES = {"M", "MM", "CM", "KM", "KG", "KW", "MW", "KV", "L", "HZ"}


def buscar_equipos(linea):
    """Devuelve los tags de equipo de una línea, en mayúsculas y sin repetir."""
    encontrados = {}
    for patron in (PATRON_LETRAS, PATRON_NUMERO):
        for m in patron.finditer(linea):
            tag = m.group().upper()
            letras = re.search(r"[A-Z]+", tag).group()
            if tag[0].isalpha() and letras in PREFIJOS_EXCLUIDOS:
                continue
            if tag[0].isdigit() and letras in LETRAS_UNIDADES:
                continue
            encontrados.setdefault(normalizar_tag(tag), tag)
    return encontrados  # {equipo_norm: equipo}


def etiquetar(texto):
    return ", ".join(palabras_presentes(texto, PROBLEMAS + ACCIONES))


def main():
    df = pd.read_csv(ENTRADA)
    df["texto"] = df["texto"].fillna("").astype(str)

    incidencias = []

    total = len(df)
    print(f"Buscando equipos en {total} partes (puede tardar unos minutos)...")

    for n, (_, fila) in enumerate(df.iterrows(), start=1):
        if n % 500 == 0:
            print(f"{n} de {total} partes revisados...")
        archivo = fila["archivo"]
        fecha = fila["fecha"] if "fecha" in df.columns and pd.notna(fila.get("fecha")) \
            else extraer_fecha(archivo)
        lineas = segmentar(fila["texto"])

        for i, linea in enumerate(lineas):
            for norm, equipo in buscar_equipos(linea).items():
                ini = max(0, i - CONTEXTO)
                contexto = "\n".join(lineas[ini:i + CONTEXTO + 1])

                incidencias.append({
                    "equipo": equipo,
                    "equipo_norm": norm,
                    "fecha": fecha,
                    "archivo": archivo,
                    "descripcion": linea,
                    "contexto": contexto,
                    "etiquetas": etiquetar(linea),
                })

    columnas = ["equipo", "equipo_norm", "fecha", "archivo",
                "descripcion", "contexto", "etiquetas"]
    inc = pd.DataFrame(incidencias, columns=columnas)
    print("Guardando resultados...")
    inc.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    # Incidencias reales: la LÍNEA del equipo tiene alguna palabra clave.
    # (Se mira la línea y no el contexto para que un equipo no "herede"
    # la avería del equipo de la línea de al lado.)
    reales = inc[inc["etiquetas"] != ""]
    reales.to_csv(SALIDA_REALES, index=False, encoding="utf-8-sig")

    print("Menciones de equipos:", len(inc))
    print("Incidencias reales:  ", len(reales))
    if len(inc):
        print("Equipos distintos:", inc["equipo_norm"].nunique())
        print("Más mencionados:")
        print(inc["equipo"].value_counts().head(15).to_string())
    print("Salida:", SALIDA)
    print("Salida:", SALIDA_REALES)


if __name__ == "__main__":
    main()
