"""
PASO PREVIO PARA LA VERSIÓN CON IA.

Lee relevos_historico.csv y genera fragmentos_relevos.csv: cada parte
troceado en fragmentos de ~1200 caracteres sin cortar líneas, con solape,
y con su fecha y archivo. Este archivo es lo que después se convertirá en
embeddings para que la IA busque por significado y cite fecha + archivo.

Uso:
    python preparar_fragmentos.py
"""

import os

import pandas as pd

from buscador import extraer_fecha, trocear

CARPETA_BASE = os.environ.get("PARTES_BASE", r"C:\ProyectoPartesRelevo\base")
ENTRADA = os.path.join(CARPETA_BASE, "relevos_historico.csv")
SALIDA = os.path.join(CARPETA_BASE, "fragmentos_relevos.csv")


def main():
    df = pd.read_csv(ENTRADA)
    df["texto"] = df["texto"].fillna("").astype(str)

    filas = []
    for _, parte in df.iterrows():
        fecha = extraer_fecha(parte["archivo"])
        for n, frag in enumerate(trocear(parte["texto"])):
            filas.append({
                "id": f"{parte['archivo']}#{n}",
                "fecha": fecha,
                "año": parte.get("año", ""),
                "archivo": parte["archivo"],
                "tipo": parte.get("tipo", ""),
                "n_fragmento": n,
                "texto": frag,
            })

    salida = pd.DataFrame(filas)
    salida.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    print(f"{len(df)} partes -> {len(salida)} fragmentos en {SALIDA}")


if __name__ == "__main__":
    main()
