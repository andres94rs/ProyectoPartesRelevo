"""
Crea / actualiza el índice de búsqueda por significado.

Qué hace:
  1. Lee base/relevos_historico.csv y saca cada línea DISTINTA de los partes
     (la misma línea copiada 500 turnos se procesa una sola vez).
  2. Calcula el vector de significado de las líneas que aún no lo tienen.
     La primera vez puede tardar bastante (lo indica al empezar); las
     siguientes solo procesa las líneas nuevas.
  3. Guarda todo en base/indice_semantico/.

Se puede cortar con Ctrl+C: guarda el progreso cada pocos minutos y la
próxima vez continúa donde lo dejó.

Uso:
    py indexar.py              crea o actualiza el índice
    py indexar.py --si-existe  solo actualiza si ya se creó alguna vez
"""

import os
import sys
import time

import numpy as np
import pandas as pd

import semantica as sem
from buscador import extraer_fecha

ENTRADA = os.path.join(sem.CARPETA_BASE, "relevos_historico.csv")

LOTE = 2000          # líneas entre mensajes de progreso
GUARDAR_CADA = 5     # lotes entre guardados parciales


def cargar_relevos():
    df = pd.read_csv(ENTRADA, dtype={"texto": str, "fecha": str, "archivo": str})
    df["texto"] = df["texto"].astype(object).fillna("")
    df["archivo"] = df["archivo"].astype(object).fillna("")
    if "fecha" not in df.columns:
        df["fecha"] = df["archivo"].map(extraer_fecha)
    df["fecha"] = df["fecha"].astype(object).fillna("")
    return df


def cargar_vectores_previos():
    """{clave: vector} con lo ya calculado (índice anterior + progreso parcial)."""
    previos = {}
    lineas, vectores = sem.cargar_indice()
    if lineas is not None and vectores.shape[1] == sem.DIMENSION:
        previos.update(zip(lineas["clave"], vectores.astype(np.float16)))
    if os.path.exists(sem.RUTA_PARCIAL_VEC) and os.path.exists(sem.RUTA_PARCIAL_CLAVES):
        try:
            claves = pd.read_csv(sem.RUTA_PARCIAL_CLAVES, dtype=str, keep_default_na=False)["clave"]
            vec = np.load(sem.RUTA_PARCIAL_VEC)
            if len(claves) == len(vec) and vec.shape[1] == sem.DIMENSION:
                previos.update(zip(claves, vec))
        except Exception:  # noqa: BLE001 - un parcial corrupto se ignora
            pass
    return previos


def guardar_parcial(claves, vectores):
    np.save(sem.RUTA_PARCIAL_VEC + ".tmp.npy", np.array(vectores, dtype=np.float16))
    os.replace(sem.RUTA_PARCIAL_VEC + ".tmp.npy", sem.RUTA_PARCIAL_VEC)
    pd.DataFrame({"clave": claves}).to_csv(sem.RUTA_PARCIAL_CLAVES, index=False)


def duracion(segundos):
    if segundos < 90:
        return f"{segundos:.0f} segundos"
    if segundos < 5400:
        return f"{segundos / 60:.0f} minutos"
    return f"{segundos / 3600:.1f} horas"


def main():
    if "--si-existe" in sys.argv and not sem.indice_existe():
        print("Búsqueda por significado: aún no se ha creado el índice (se omite).")
        return

    if not os.path.exists(ENTRADA):
        print(f"ERROR: no existe {ENTRADA}. Ejecuta antes extraer_relevos.py")
        sys.exit(1)

    os.makedirs(sem.CARPETA_INDICE, exist_ok=True)

    print("Leyendo los partes...")
    lineas = sem.lineas_distintas(cargar_relevos())
    print(f"Líneas distintas con contenido: {len(lineas)}")

    previos = cargar_vectores_previos()
    pendientes = [
        (c, t) for c, t in zip(lineas["clave"], lineas["texto"]) if c not in previos
    ]
    print(f"Ya calculadas: {len(lineas) - len(pendientes)}   Nuevas: {len(pendientes)}")

    if pendientes:
        print("Cargando el modelo (la primera vez se descarga, ~470 MB)...")
        try:
            modelo = sem.cargar_modelo()
        except ImportError:
            print("ERROR: falta la librería. Ejecuta:  py -m pip install fastembed")
            sys.exit(1)
        except Exception as e:  # noqa: BLE001
            print("ERROR: no se ha podido cargar o descargar el modelo.")
            print("Si es la primera vez, puede que la red de la empresa bloquee")
            print("la descarga desde huggingface.co. Detalle:")
            print(f"  {type(e).__name__}: {e}")
            sys.exit(1)

        nuevas_claves, nuevos_vec = [], []
        inicio = time.time()
        try:
            for n_lote, i in enumerate(range(0, len(pendientes), LOTE), start=1):
                trozo = pendientes[i:i + LOTE]
                vec = sem.vectorizar_textos(modelo, [t for _, t in trozo])
                nuevas_claves.extend(c for c, _ in trozo)
                nuevos_vec.extend(vec.astype(np.float16))

                hechas = len(nuevas_claves)
                ritmo = hechas / (time.time() - inicio)
                falta = (len(pendientes) - hechas) / ritmo
                print(
                    f"{hechas} de {len(pendientes)} líneas "
                    f"({ritmo:.0f} por segundo, faltan unos {duracion(falta)})"
                )
                if n_lote % GUARDAR_CADA == 0:
                    guardar_parcial(nuevas_claves, nuevos_vec)
        except KeyboardInterrupt:
            guardar_parcial(nuevas_claves, nuevos_vec)
            print("\nInterrumpido. Progreso guardado: la próxima vez continúa desde aquí.")
            sys.exit(1)

        previos.update(zip(nuevas_claves, nuevos_vec))

    # Índice final, alineado fila a fila con lineas.csv
    vectores = np.array([previos[c] for c in lineas["clave"]], dtype=np.float16)
    if len(lineas) == 0:
        vectores = vectores.reshape(0, sem.DIMENSION)
    np.save(sem.RUTA_VECTORES + ".tmp.npy", vectores)
    lineas.to_csv(sem.RUTA_LINEAS + ".tmp", index=False, encoding="utf-8-sig")
    os.replace(sem.RUTA_VECTORES + ".tmp.npy", sem.RUTA_VECTORES)
    os.replace(sem.RUTA_LINEAS + ".tmp", sem.RUTA_LINEAS)
    for ruta in (sem.RUTA_PARCIAL_VEC, sem.RUTA_PARCIAL_CLAVES):
        if os.path.exists(ruta):
            os.remove(ruta)

    print()
    print("Índice de búsqueda por significado listo.")
    print(f"  Líneas: {len(lineas)}")
    print(f"  Carpeta: {sem.CARPETA_INDICE}")


if __name__ == "__main__":
    main()
