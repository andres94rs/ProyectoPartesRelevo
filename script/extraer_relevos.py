"""
Extrae el texto de los partes de relevo (PDF y Excel) a base/relevos_historico.csv

Mejoras respecto a la versión anterior:
  - Lee también los .xls antiguos (openpyxl solo lee .xlsx/.xlsm; antes
    todos los .xls se guardaban como "ERROR EXCEL").
  - Los errores van a una columna "error" en vez de mezclarse con el texto,
    y al final se muestra un resumen (cuántos fallaron, cuántos PDF salen
    vacíos porque son escaneados, etc.).
  - Ignora los archivos temporales de Excel (~$...).
  - Añade la columna "fecha" (del nombre del archivo o, si no tiene,
    de la fecha de modificación) y calcula el año de forma más fiable.
  - INCREMENTAL: si ya existe el CSV, solo procesa los archivos nuevos o
    modificados. La primera vez tarda lo mismo; las siguientes, segundos.
    Para forzar que se procese todo de nuevo:  python extraer_relevos.py --todo

Uso:
    python extraer_relevos.py
"""

import os
import re
import sys
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook
from pypdf import PdfReader

from buscador import extraer_fecha

RUTA_RELEVOS = os.environ.get("PARTES_ORIGEN", r"I:\Producción\01. LIBRO DE RELEVOS")

CARPETA_BASE = os.environ.get("PARTES_BASE", r"C:\ProyectoPartesRelevo\base")
SALIDA = os.path.join(CARPETA_BASE, "relevos_historico.csv")

CARPETAS_EXCLUIDAS = {
    "OBSOLETO",
    "Cambio de turno Operadores de planta",
    "Cambio de turno Panelistas",
}

EXTENSIONES = {".pdf", ".xls", ".xlsx", ".xlsm"}

# Si un PDF tiene menos caracteres que esto, casi seguro es un escaneo
# (una imagen) y necesitaría OCR para poder leerlo.
MIN_CARACTERES_PDF = 50


# --------------------------------------------------
# LIMPIEZA DE TEXTO
# --------------------------------------------------


def limpiar(texto):
    """Quita espacios repetidos y líneas vacías sobrantes, conserva los saltos."""
    lineas = (re.sub(r"[ \t\u00a0]+", " ", l).strip() for l in texto.splitlines())
    texto = "\n".join(lineas)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def celda_a_texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        # Evita el "00:00:00" en celdas que solo son fecha
        return valor.strftime("%d/%m/%Y" if valor.time() == datetime.min.time()
                              else "%d/%m/%Y %H:%M")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))  # 101.0 -> 101
    return str(valor).strip()


# --------------------------------------------------
# LECTORES
# --------------------------------------------------


def leer_pdf(ruta):
    reader = PdfReader(ruta)
    paginas = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(paginas)


def _filas_a_texto(titulo, filas):
    lineas = [f"=== {titulo} ==="]
    for fila in filas:
        valores = [v for v in (celda_a_texto(c) for c in fila) if v]
        if valores:
            lineas.append(" | ".join(valores))
    return "\n".join(lineas)


def leer_xlsx(ruta):
    wb = load_workbook(ruta, data_only=True, read_only=True)
    try:
        return "\n\n".join(
            _filas_a_texto(h.title, h.iter_rows(values_only=True))
            for h in wb.worksheets
        )
    finally:
        wb.close()


def leer_xls(ruta):
    import xlrd  # pip install xlrd

    libro = xlrd.open_workbook(ruta)
    textos = []
    for hoja in libro.sheets():
        filas = []
        for r in range(hoja.nrows):
            fila = []
            for c in range(hoja.ncols):
                celda = hoja.cell(r, c)
                if celda.ctype == xlrd.XL_CELL_DATE:
                    fila.append(xlrd.xldate.xldate_as_datetime(celda.value, libro.datemode))
                else:
                    fila.append(celda.value)
            filas.append(fila)
        textos.append(_filas_a_texto(hoja.name, filas))
    return "\n\n".join(textos)


def leer(ruta, extension):
    if extension == ".pdf":
        return leer_pdf(ruta)
    if extension == ".xls":
        return leer_xls(ruta)
    return leer_xlsx(ruta)


# --------------------------------------------------
# AÑO
# --------------------------------------------------


def calcular_año(raiz, fecha):
    """Año de la carpeta (p. ej. '...\\2023\\...'); si no hay, el de la fecha."""
    años = re.findall(r"(?<!\d)(20[0-9]{2})(?!\d)", raiz)
    if años:
        return int(años[-1])  # la carpeta más profunda manda
    if fecha:
        return int(fecha[:4])
    return None


# --------------------------------------------------
# PROCESO PRINCIPAL
# --------------------------------------------------


def listar_archivos():
    for raiz, carpetas, archivos in os.walk(RUTA_RELEVOS):
        carpetas[:] = [c for c in carpetas if c not in CARPETAS_EXCLUIDAS]
        for archivo in archivos:
            if archivo.startswith("~$"):
                continue  # archivo temporal de Excel abierto
            extension = os.path.splitext(archivo)[1].lower()
            if extension in EXTENSIONES:
                yield raiz, archivo, extension


def cargar_previo(forzar):
    if forzar or not os.path.exists(SALIDA):
        return {}
    previo = pd.read_csv(SALIDA)
    if "modificado" not in previo.columns:
        return {}  # CSV de la versión anterior: se regenera todo
    if "error" not in previo.columns:
        previo["error"] = ""
    previo["error"] = previo["error"].fillna("")
    # Solo se reutilizan los que salieron bien
    previo = previo[previo["error"] == ""]
    return {fila["ruta"]: fila for fila in previo.to_dict("records")}


def main():
    forzar = "--todo" in sys.argv
    previo = cargar_previo(forzar)
    datos = []
    nuevos = reutilizados = 0

    for raiz, archivo, extension in listar_archivos():
        ruta = os.path.join(raiz, archivo)
        try:
            modificado = os.path.getmtime(ruta)
        except OSError:
            modificado = 0

        anterior = previo.get(ruta)
        if anterior is not None and anterior["modificado"] == modificado:
            datos.append(anterior)
            reutilizados += 1
            continue

        fecha = extraer_fecha(archivo)
        if not fecha and modificado:
            fecha = datetime.fromtimestamp(modificado).strftime("%Y-%m-%d")

        texto, error = "", ""
        try:
            texto = limpiar(leer(ruta, extension))
            if extension == ".pdf" and len(texto) < MIN_CARACTERES_PDF:
                error = "PDF sin texto (posible escaneado, necesita OCR)"
        except Exception as e:  # noqa: BLE001 - cualquier fallo se anota y se sigue
            error = f"{type(e).__name__}: {e}"

        datos.append({
            "año": calcular_año(raiz, fecha),
            "fecha": fecha,
            "archivo": archivo,
            "tipo": extension,
            "ruta": ruta,
            "modificado": modificado,
            "error": error,
            "texto": texto,
        })

        nuevos += 1
        if nuevos % 100 == 0:
            print(f"{nuevos} documentos procesados...")

    df = pd.DataFrame(datos)
    os.makedirs(CARPETA_BASE, exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    errores = df[df["error"].fillna("") != ""] if len(df) else df

    print()
    print("=" * 50)
    print("FINALIZADO")
    print("=" * 50)
    print(f"Documentos:        {len(df)}")
    print(f"  procesados ahora: {nuevos}")
    print(f"  sin cambios:      {reutilizados}")
    print(f"  con problemas:    {len(errores)}")
    if len(errores):
        print()
        print("Problemas por tipo:")
        resumen = errores["error"].str.split(":").str[0].value_counts()
        for motivo, n in resumen.items():
            print(f"  {n:5d}  {motivo}")
        ruta_err = os.path.join(CARPETA_BASE, "errores_extraccion.csv")
        errores[["archivo", "ruta", "error"]].to_csv(
            ruta_err, index=False, encoding="utf-8-sig"
        )
        print(f"Detalle en: {ruta_err}")
    print(f"Salida: {SALIDA}")


if __name__ == "__main__":
    main()
