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
    "ensuciamiento", "anomalia", "parada", "rotura", "escape", "derrame",
    "incidencia", "problema",
]

ACCIONES = [
    "reparacion", "sustitucion", "solicitud", "limpieza", "revision",
    "actuacion", "verificacion",
]


# Las acciones también se escriben como verbo ("reparada", "se sustituye",
# "revisar"...). Aquí se indica qué formas cuentan para cada una.
VARIANTES = {
    "reparacion": r"repara(?:cion|ciones|d[oa]s?|r)",
    "sustitucion": r"sustitu(?:cion|ciones|id[oa]s?|ir|ye)",
    "solicitud": r"solicit(?:ud|udes|ad[oa]s?|ar|a)",
    "limpieza": r"limpi(?:ezas?|ad[oa]s?|ar)",
    "revision": r"revis(?:ion|iones|ad[oa]s?|ar)",
    "actuacion": r"actua(?:cion|ciones|d[oa]s?|r)",
    "verificacion": r"verific(?:acion|aciones|ad[oa]s?|ar)",
}


def _patron_palabra(palabra):
    # Palabra completa + plural opcional: "fuga" encuentra "fugas" pero NO
    # "centrifuga"; "parada" NO encuentra "preparada" ni "separada".
    if palabra in VARIANTES:
        return re.compile(r"\b" + VARIANTES[palabra] + r"\b")
    return re.compile(r"\b" + re.escape(palabra) + r"(?:s|es)?\b")


_PATRONES = {p: _patron_palabra(p) for p in PROBLEMAS + ACCIONES}


def contar_palabra(texto, palabra):
    """Veces que aparece la palabra completa (texto ya normalizado o no)."""
    patron = _PATRONES.get(palabra) or _patron_palabra(palabra)
    return len(patron.findall(normalizar(texto)))


def palabras_presentes(texto, palabras):
    """Lista de las palabras clave que aparecen como palabra completa."""
    t = normalizar(texto)
    return [p for p in palabras if (_PATRONES.get(p) or _patron_palabra(p)).search(t)]


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


# --------------------------------------------------
# TURNOS
# --------------------------------------------------

# Orden de los turnos dentro de un mismo día (ajústalo si en tu planta
# el día empieza por otro turno).
ORDEN_TURNOS = ["manana", "tarde", "noche"]


def orden_turno(archivo):
    """Posición del turno según el nombre del archivo (para ordenar)."""
    nombre = normalizar(str(archivo))
    for i, turno in enumerate(ORDEN_TURNOS):
        if turno in nombre:
            return i
    return len(ORDEN_TURNOS)


# --------------------------------------------------
# CRONOLOGÍA RESUMIDA (agrupar lo que se repite turno tras turno)
# --------------------------------------------------

# Dos líneas se consideran "la misma" si se parecen al menos este tanto
# (1.0 = idénticas). Tolera erratas y pequeños cambios de redacción.
SIMILITUD_MINIMA = 0.85

# Si una línea deja de aparecer más de estos días y luego vuelve,
# se cuenta como un periodo nuevo.
DIAS_SALTO = 7


def _clave_texto(texto):
    return re.sub(r"[^a-z0-9]+", " ", normalizar(texto)).strip()


def _dias_entre(f1, f2):
    from datetime import date
    try:
        return (date.fromisoformat(f2) - date.fromisoformat(f1)).days
    except ValueError:
        return 0


def agrupar_repetidos(registros):
    """
    Recibe las menciones de un equipo (dicts con 'fecha', 'archivo',
    'descripcion', ...) y junta las que dicen (casi) lo mismo en periodos.

    Devuelve una lista de periodos ordenados por fecha de inicio:
      {'desde', 'hasta', 'n', 'descripcion', 'primero', 'ultimo'}
    donde 'primero' y 'ultimo' son los registros originales de los extremos.
    """
    from difflib import SequenceMatcher

    registros = sorted(
        registros, key=lambda r: (r["fecha"], orden_turno(r["archivo"]))
    )

    # 1) Agrupar por texto parecido
    grupos = []          # [(clave_representante, [registros])]
    exactos = {}         # clave -> índice de grupo (atajo para textos idénticos)
    for r in registros:
        clave = _clave_texto(r["descripcion"])
        idx = exactos.get(clave)
        if idx is None:
            comparador = SequenceMatcher(None, "", clave, autojunk=False)
            for i, (representante, _) in enumerate(grupos):
                comparador.set_seq1(representante)
                if (comparador.real_quick_ratio() >= SIMILITUD_MINIMA
                        and comparador.quick_ratio() >= SIMILITUD_MINIMA
                        and comparador.ratio() >= SIMILITUD_MINIMA):
                    idx = i
                    break
            if idx is None:
                grupos.append((clave, []))
                idx = len(grupos) - 1
            exactos[clave] = idx
        grupos[idx][1].append(r)

    # 2) Partir cada grupo en periodos cuando hay un salto de fechas
    periodos = []
    for _, miembros in grupos:
        tramo = [miembros[0]]
        for r in miembros[1:]:
            if _dias_entre(tramo[-1]["fecha"], r["fecha"]) > DIAS_SALTO:
                periodos.append(tramo)
                tramo = []
            tramo.append(r)
        periodos.append(tramo)

    salida = [
        {
            "desde": t[0]["fecha"],
            "hasta": t[-1]["fecha"],
            "n": len(t),
            "descripcion": t[0]["descripcion"],
            "primero": t[0],
            "ultimo": t[-1],
        }
        for t in periodos
    ]
    salida.sort(key=lambda p: (p["desde"], orden_turno(p["primero"]["archivo"])))
    return salida
