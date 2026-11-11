"""
Búsqueda por significado (fase 1 de IA). Todo en local, sin Ollama.

Idea:
  - Cada línea de los partes se convierte en un vector de números que
    representa su SIGNIFICADO ("embedding"), con un modelo pequeño que se
    ejecuta en el propio ordenador.
  - Para buscar, la pregunta se convierte en otro vector y se devuelven
    las líneas cuyo vector se le parece más. Así "pérdida de producto"
    encuentra "fuga" o "goteo" aunque no compartan ninguna palabra.

Como en los partes la misma línea se copia turno tras turno, solo se
calcula el vector de cada línea DISTINTA (una vez), y se guarda en qué
fechas aparece. Eso reduce muchísimo el trabajo.
"""

import os
import re

import numpy as np
import pandas as pd

from buscador import normalizar, orden_turno, patron_termino, parece_tag, segmentar

CARPETA_BASE = os.environ.get("PARTES_BASE", r"C:\ProyectoPartesRelevo\base")
CARPETA_INDICE = os.path.join(CARPETA_BASE, "indice_semantico")
CARPETA_MODELOS = os.path.join(CARPETA_BASE, "modelos")

RUTA_LINEAS = os.path.join(CARPETA_INDICE, "lineas.csv")
RUTA_VECTORES = os.path.join(CARPETA_INDICE, "vectores.npy")
RUTA_PARCIAL_VEC = os.path.join(CARPETA_INDICE, "parcial_vectores.npy")
RUTA_PARCIAL_CLAVES = os.path.join(CARPETA_INDICE, "parcial_claves.csv")

# Modelo de embeddings multilingüe (funciona en español), ~470 MB, rápido
# en un portátil sin tarjeta gráfica. En las pruebas dio la misma calidad
# que modelos 3 veces más lentos.
MODELO = os.environ.get("PARTES_MODELO", "intfloat/multilingual-e5-small")
DIMENSION = 384

# Los modelos e5 esperan estos prefijos delante de preguntas y de textos
PREFIJO_CONSULTA = "query: "
PREFIJO_TEXTO = "passage: "

# Peso de las palabras que coinciden frente al significado (búsqueda híbrida)
PESO_PALABRAS = 2.0

# Líneas demasiado cortas o que son solo números no aportan nada
MIN_CARACTERES = 25
MIN_PALABRAS = 3
_PALABRA = re.compile(r"[a-zñ]{3,}")


# --------------------------------------------------
# MODELO
# --------------------------------------------------


def cargar_modelo():
    """Carga el modelo (la primera vez lo descarga a base/modelos)."""
    from fastembed import TextEmbedding  # pip install fastembed
    from fastembed.common.model_description import ModelSource, PoolingType

    # Descarga clásica por HTTPS: da menos problemas con proxys de empresa
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    conocidos = {m["model"] for m in TextEmbedding.list_supported_models()}
    if MODELO not in conocidos:
        TextEmbedding.add_custom_model(
            model=MODELO,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=MODELO),
            dim=DIMENSION,
            model_file="onnx/model.onnx",
        )
    os.makedirs(CARPETA_MODELOS, exist_ok=True)
    return TextEmbedding(MODELO, cache_dir=CARPETA_MODELOS)


def _vectores(modelo, textos, lote):
    v = np.array(list(modelo.embed(list(textos), batch_size=lote)), dtype=np.float32)
    if v.size == 0:
        return v.reshape(0, DIMENSION)
    normas = np.linalg.norm(v, axis=1, keepdims=True)
    normas[normas == 0] = 1
    return v / normas


def vectorizar_textos(modelo, textos, lote=64):
    """Vectores (longitud 1) de líneas de partes."""
    return _vectores(modelo, [PREFIJO_TEXTO + t for t in textos], lote)


def vectorizar_consulta(modelo, consulta):
    """Vector (longitud 1) de la pregunta del usuario."""
    return _vectores(modelo, [PREFIJO_CONSULTA + consulta], 1)[0]


# --------------------------------------------------
# LÍNEAS DISTINTAS DE LOS PARTES
# --------------------------------------------------


def clave_linea(linea):
    """Identificador de una línea: su texto sin tildes ni mayúsculas."""
    return normalizar(linea)


def linea_util(linea):
    if len(linea) < MIN_CARACTERES or linea.startswith("==="):
        return False
    return len(_PALABRA.findall(normalizar(linea))) >= MIN_PALABRAS


def lineas_distintas(relevos):
    """
    Recorre los partes en orden cronológico y devuelve un DataFrame con
    cada línea distinta y cuándo aparece:
      clave, texto, n, primera_fecha, primer_archivo, ultima_fecha, ultimo_archivo
    """
    relevos = relevos.assign(
        _turno=relevos["archivo"].map(orden_turno)
    ).sort_values(["fecha", "_turno"])

    registro = {}
    for fecha, archivo, texto in zip(
        relevos["fecha"], relevos["archivo"], relevos["texto"]
    ):
        vistas = set()
        for linea in segmentar(texto):
            if not linea_util(linea):
                continue
            clave = clave_linea(linea)
            if clave in vistas:
                continue  # una vez por parte
            vistas.add(clave)
            r = registro.get(clave)
            if r is None:
                registro[clave] = [linea, 1, fecha, archivo, fecha, archivo]
            else:
                r[1] += 1
                r[4], r[5] = fecha, archivo

    return pd.DataFrame(
        [[c] + r for c, r in registro.items()],
        columns=["clave", "texto", "n", "primera_fecha", "primer_archivo",
                 "ultima_fecha", "ultimo_archivo"],
    )


# --------------------------------------------------
# ÍNDICE EN DISCO
# --------------------------------------------------


def indice_existe():
    return os.path.exists(RUTA_LINEAS) and os.path.exists(RUTA_VECTORES)


def cargar_indice():
    """Devuelve (lineas, vectores) o (None, None) si aún no se ha creado."""
    if not indice_existe():
        return None, None
    lineas = pd.read_csv(RUTA_LINEAS, dtype=str, keep_default_na=False)
    lineas["n"] = lineas["n"].astype(int)
    vectores = np.load(RUTA_VECTORES).astype(np.float32)
    if len(lineas) != len(vectores):
        return None, None  # índice a medias: hay que rehacerlo
    return lineas, vectores


# --------------------------------------------------
# BÚSQUEDA
# --------------------------------------------------


_VACIAS = set(
    "de del la el en los las que por con un una unos unas al se y o a no "
    "para su sus es son ha han hay como mas muy lo le les".split()
)


def raices(texto):
    """Raíces (5 primeras letras) de las palabras con contenido de un texto.
    'ventiladores' y 'ventilador' comparten raíz; 'de', 'la'... no cuentan."""
    return {
        p[:5] for p in re.findall(r"[a-zñ]{3,}", normalizar(texto))
        if p not in _VACIAS
    }


def buscar(modelo, lineas, vectores, claves, consulta, n_resultados=20,
           desde="", hasta=""):
    """
    Devuelve las líneas más relevantes para la consulta, con su puntuación.

    Búsqueda híbrida, combina tres cosas:
      1. Significado: parecido entre el vector de la pregunta y el de la línea
         ("derrame" encuentra "rebose").
      2. Palabras: las líneas que además contienen palabras de la pregunta
         suben puestos.
      3. Tags: si la pregunta lleva un tag de equipo (k-501, vb1070...), solo
         se consideran las líneas que mencionan ese equipo (los modelos de
         significado no entienden bien los códigos).

    `claves` es la columna lineas["clave"] (texto normalizado).
    Devuelve (resultados, tags_detectados).
    """
    palabras = [p.strip(".,;:()¿?¡!") for p in normalizar(consulta).split()]
    tags = [p for p in palabras if parece_tag(p)]

    mascara = np.ones(len(lineas), dtype=bool)
    for t in tags:
        mascara &= claves.str.contains(patron_termino(t).pattern, regex=True).to_numpy()
    if desde:
        mascara &= (lineas["ultima_fecha"] >= desde).to_numpy()
    if hasta:
        mascara &= (lineas["primera_fecha"] <= hasta).to_numpy()

    candidatos = np.flatnonzero(mascara)
    if len(candidatos) == 0:
        return lineas.iloc[[]].assign(puntuacion=[], parecido=[]), tags

    # 1) Significado
    q = vectorizar_consulta(modelo, consulta)
    parecido = vectores[candidatos] @ q
    desviacion = parecido.std() or 1.0
    puntos = (parecido - parecido.mean()) / desviacion

    # 2) Palabras en común (solo sobre los mejores candidatos, por rapidez)
    raices_q = raices(" ".join(p for p in palabras if p not in tags))
    preseleccion = np.argsort(-puntos)[: max(500, n_resultados * 20)]
    if raices_q:
        # ...más cualquier línea que contenga TODAS las palabras de la pregunta
        patron = "".join(f"(?=.*{re.escape(r)})" for r in raices_q)
        con_todas = np.flatnonzero(
            claves.iloc[candidatos].str.contains(patron, regex=True).to_numpy()
        )
        preseleccion = np.unique(np.concatenate([preseleccion, con_todas]))
        for i in preseleccion:
            comunes = len(raices_q & raices(claves.iat[candidatos[i]]))
            puntos[i] += PESO_PALABRAS * comunes / len(raices_q)

    orden = preseleccion[np.argsort(-puntos[preseleccion])][:n_resultados]
    resultado = lineas.iloc[candidatos[orden]].copy()
    resultado["puntuacion"] = puntos[orden]
    resultado["parecido"] = parecido[orden]
    return resultado, tags
