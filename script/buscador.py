"""
Lógica de búsqueda de los partes de relevo (sin Streamlit).

Se separa de la web para poder reutilizarla:
  - en la web de búsqueda (app.py)
  - en el script que prepara los fragmentos para la IA (preparar_fragmentos.py)
"""

import html
import re
import unicodedata

# --------------------------------------------------
# NORMALIZACIÓN
# --------------------------------------------------


def _base(c):
    """Letra sin tilde y en minúscula (á -> a, Ñ -> n). Siempre 1 carácter."""
    return unicodedata.normalize("NFD", c.lower())[0]


def normalizar(texto):
    """
    Minúsculas y sin tildes, CONSERVANDO la longitud del texto.
    Así una posición encontrada en el texto normalizado vale también
    en el texto original (necesario para resaltar).
    """
    return "".join(_base(c) for c in texto)


# --------------------------------------------------
# PALABRAS PROBLEMA / ACCIÓN (sin tildes: se comparan con texto normalizado)
# --------------------------------------------------

PROBLEMAS = [
    "fuga", "fallo", "averia", "paso interno", "mismatch", "alarma",
    "interlock", "vibracion", "atasco", "obstruccion", "rebose", "disparo",
]

ACCIONES = [
    "reparacion", "sustitucion", "solicitud", "limpieza", "revision",
    "actuacion", "verificacion",
]


def normalizar_tag(tag):
    """'p-101 b' -> 'P101B': mismo equipo aunque se escriba distinto."""
    return re.sub(r"[\s\-]", "", str(tag)).upper()


# --------------------------------------------------
# FECHAS
# --------------------------------------------------

_PATRONES_FECHA = [
    # dd.mm.aaaa / dd_mm_aaaa / dd-mm-aaaa
    (re.compile(r"(\d{1,2})[._-](\d{1,2})[._-](\d{4})"), "dma"),
    # aaaa-mm-dd / aaaa_mm_dd / aaaa.mm.dd
    (re.compile(r"(\d{4})[._-](\d{1,2})[._-](\d{1,2})"), "amd"),
    # dd.mm.aa (año con 2 cifras)
    (re.compile(r"(?<!\d)(\d{1,2})[._-](\d{1,2})[._-](\d{2})(?!\d)"), "dma2"),
]


def extraer_fecha(nombre):
    """Devuelve la fecha del nombre de archivo como 'AAAA-MM-DD' o ''."""
    nombre = str(nombre)
    for patron, orden in _PATRONES_FECHA:
        m = patron.search(nombre)
        if not m:
            continue
        if orden == "dma":
            d, mes, a = m.groups()
        elif orden == "amd":
            a, mes, d = m.groups()
        else:
            d, mes, a = m.groups()
            a = "20" + a
        d, mes = int(d), int(mes)
        if 1 <= d <= 31 and 1 <= mes <= 12:
            return f"{a}-{mes:02d}-{d:02d}"
    return ""


# --------------------------------------------------
# CONSULTA
# --------------------------------------------------


def parsear_consulta(consulta):
    """
    Separa la consulta en términos.
    - Palabras sueltas:          bomba fuga      -> ['bomba', 'fuga']
    - Frase exacta entre comillas: "paso interno" -> ['paso interno']
    Los términos se devuelven normalizados (sin tildes, minúsculas).
    """
    terminos = []
    for frase, palabra in re.findall(r'"([^"]+)"|(\S+)', consulta):
        t = normalizar((frase or palabra).strip())
        if t and t not in terminos:
            terminos.append(t)
    return terminos


# --------------------------------------------------
# SEGMENTACIÓN DEL TEXTO
# --------------------------------------------------

_FIN_FRASE = re.compile(r"(?<=[.;!?])\s+(?=\S)")
LARGO_MAX_LINEA = 400


def segmentar(texto):
    """
    Divide el parte en unidades con sentido (líneas / frases).

    - Si el texto tiene saltos de línea (lo normal en partes), cada línea
      no vacía es un segmento.
    - Las líneas muy largas (PDFs que salen "en un solo bloque") se
      dividen por frases para no mostrar párrafos enormes.
    """
    segmentos = []
    for linea in str(texto).splitlines():
        linea = re.sub(r"[ \t]+", " ", linea).strip()
        if not linea:
            continue
        if len(linea) > LARGO_MAX_LINEA:
            segmentos.extend(s.strip() for s in _FIN_FRASE.split(linea) if s.strip())
        else:
            segmentos.append(linea)
    return segmentos


# --------------------------------------------------
# BÚSQUEDA CON CONTEXTO
# --------------------------------------------------


def buscar_en_texto(texto, terminos, contexto=3):
    """
    Busca los términos dentro de un parte y devuelve TODAS las zonas donde
    aparecen, cada una con `contexto` líneas por delante y por detrás.

    Devuelve una lista de ventanas: [(inicio, fin, [segmentos]), ...]
    Las ventanas que se solapan se fusionan para no repetir texto.
    """
    segmentos = segmentar(texto)
    if not segmentos or not terminos:
        return []

    normalizados = [normalizar(s) for s in segmentos]
    aciertos = [
        i for i, s in enumerate(normalizados) if any(t in s for t in terminos)
    ]

    # Si los términos están en líneas distintas (p. ej. "bomba" arriba y
    # "fuga" dos líneas abajo) también se captura gracias al contexto.
    ventanas = []
    for i in aciertos:
        ini = max(0, i - contexto)
        fin = min(len(segmentos), i + contexto + 1)
        if ventanas and ini <= ventanas[-1][1]:
            ventanas[-1][1] = max(ventanas[-1][1], fin)
        else:
            ventanas.append([ini, fin])

    return [(ini, fin, segmentos[ini:fin]) for ini, fin in ventanas]


def resaltar_html(segmento, terminos):
    """Devuelve el segmento en HTML seguro con los términos marcados."""
    norm = normalizar(segmento)
    marcas = [False] * len(segmento)
    for t in terminos:
        inicio = norm.find(t)
        while inicio >= 0:
            for k in range(inicio, inicio + len(t)):
                marcas[k] = True
            inicio = norm.find(t, inicio + 1)

    partes, i = [], 0
    while i < len(segmento):
        j = i
        while j < len(segmento) and marcas[j] == marcas[i]:
            j += 1
        trozo = html.escape(segmento[i:j])
        partes.append(f"<mark>{trozo}</mark>" if marcas[i] else trozo)
        i = j
    return "".join(partes)


# --------------------------------------------------
# FRAGMENTOS PARA LA IA (siguiente versión)
# --------------------------------------------------


def trocear(texto, max_caracteres=1200, solape_segmentos=2):
    """
    Divide un parte en fragmentos de tamaño parecido SIN cortar líneas ni
    frases por la mitad, con algunas líneas de solape entre fragmentos
    para que no se pierda el contexto en los bordes.

    Esto es la base para la búsqueda semántica / IA (RAG): cada fragmento
    se convierte en un vector (embedding) y se guarda con su fecha y archivo.
    """
    segmentos = segmentar(texto)
    fragmentos, actual, largo, nuevos = [], [], 0, 0

    for seg in segmentos:
        if nuevos and largo + len(seg) > max_caracteres:
            fragmentos.append("\n".join(actual))
            actual = actual[-solape_segmentos:] if solape_segmentos else []
            largo = sum(len(s) for s in actual)
            nuevos = 0
        actual.append(seg)
        largo += len(seg)
        nuevos += 1

    if nuevos:
        fragmentos.append("\n".join(actual))
    return fragmentos
