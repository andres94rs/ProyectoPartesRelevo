import os

import pandas as pd
import streamlit as st

from buscador import (
    buscar_en_texto,
    extraer_fecha,
    normalizar,
    parsear_consulta,
    resaltar_html,
)

# --------------------------------------------------
# CONFIGURACION
# --------------------------------------------------

st.set_page_config(
    page_title="Base de Conocimiento de Planta",
    page_icon="🏭",
    layout="wide",
)

# Carpeta de datos. Se puede cambiar sin tocar el código con la variable
# de entorno PARTES_BASE (útil si algún día lo mueves a un servidor).
CARPETA_BASE = os.environ.get("PARTES_BASE", r"C:\ProyectoPartesRelevo\base")
RUTA_RELEVOS = os.path.join(CARPETA_BASE, "relevos_historico.csv")
RUTA_INCIDENCIAS = os.path.join(CARPETA_BASE, "incidencias_reales.csv")

RESULTADOS_POR_PAGINA = 20

st.markdown(
    """
    <style>
    .fragmento {
        font-family: ui-monospace, Consolas, monospace;
        font-size: 0.9rem;
        line-height: 1.5;
        padding: 0.6rem 0.8rem;
        border-left: 3px solid #999;
        background: rgba(127,127,127,0.08);
        margin-bottom: 0.6rem;
        white-space: normal;
    }
    .fragmento mark { background: #ffd54f; color: #000; padding: 0 2px; }
    .corte { color: #888; font-size: 0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# CARGAR DATOS
# --------------------------------------------------


@st.cache_data
def cargar_relevos():
    df = pd.read_csv(RUTA_RELEVOS)
    df["texto"] = df["texto"].fillna("").astype(str)
    df["archivo"] = df["archivo"].fillna("").astype(str)

    # Se calcula UNA vez y queda en caché: búsquedas sin tildes y rápidas.
    df["texto_norm"] = df["texto"].map(normalizar)
    df["fecha"] = df["archivo"].map(extraer_fecha)
    return df


@st.cache_data
def cargar_incidencias():
    df = pd.read_csv(RUTA_INCIDENCIAS)
    df["descripcion"] = df["descripcion"].fillna("").astype(str)
    df["etiquetas"] = df["etiquetas"].fillna("").astype(str)
    df["archivo"] = df["archivo"].fillna("").astype(str)
    df["fecha"] = df["archivo"].map(extraer_fecha)
    return df


relevos = cargar_relevos()
incidencias = cargar_incidencias()

# --------------------------------------------------
# PALABRAS PROBLEMA / ACCION (ya sin duplicados con tilde:
# se compara siempre sobre texto normalizado)
# --------------------------------------------------

PROBLEMAS = [
    "fuga", "fallo", "averia", "paso interno", "mismatch", "alarma",
    "interlock", "vibracion", "atasco", "obstruccion", "rebose", "disparo",
]

ACCIONES = [
    "reparacion", "sustitucion", "solicitud", "limpieza", "revision",
    "actuacion", "verificacion",
]


def mostrar_fragmentos(texto, terminos, contexto):
    """Pinta todas las zonas del parte donde aparece la búsqueda."""
    for ini, fin, segmentos in buscar_en_texto(texto, terminos, contexto):
        cuerpo = "<br>".join(resaltar_html(s, terminos) for s in segmentos)
        corte = '<div class="corte">[…]</div>' if ini > 0 else ""
        st.markdown(
            f'{corte}<div class="fragmento">{cuerpo}</div>',
            unsafe_allow_html=True,
        )


# --------------------------------------------------
# PESTAÑAS
# --------------------------------------------------

tab1, tab2 = st.tabs(["🔎 Buscar relevos", "🛠 Ficha equipo"])

# ==================================================
# TAB 1
# ==================================================

with tab1:
    st.title("🔎 Buscar en relevos")
    st.caption(
        'Escribe varias palabras para buscar partes que contengan TODAS '
        '(ej.: `bomba fuga`). Usa comillas para una frase exacta '
        '(ej.: `"paso interno"`). No importan tildes ni mayúsculas.'
    )

    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

    with col1:
        busqueda = st.text_input("Buscar")

    with col2:
        años = sorted(str(x) for x in relevos["año"].dropna().unique())
        año = st.selectbox("Año", ["Todos"] + años)

    with col3:
        contexto = st.slider(
            "Líneas de contexto",
            min_value=1, max_value=15, value=4,
            help="Cuántas líneas se muestran por delante y por detrás "
                 "de cada coincidencia.",
        )

    with col4:
        orden = st.radio("Orden", ["Más recientes", "Más antiguos"])

    resultado = relevos

    if año != "Todos":
        resultado = resultado[resultado["año"].astype(str) == año]

    terminos = parsear_consulta(busqueda) if busqueda else []

    if terminos:
        # Todas las palabras deben aparecer en el parte.
        # regex=False: caracteres como "(" o "+" en el tag no rompen la búsqueda.
        mascara = pd.Series(True, index=resultado.index)
        for t in terminos:
            mascara &= resultado["texto_norm"].str.contains(t, regex=False)
        resultado = resultado[mascara]

        resultado = resultado.sort_values(
            "fecha", ascending=(orden == "Más antiguos")
        )

        st.success(f"{len(resultado)} partes encontrados")

        columnas = [c for c in ["fecha", "año", "archivo", "tipo"] if c in resultado]
        st.dataframe(resultado[columnas], hide_index=True)

        st.download_button(
            "📥 Exportar resultados",
            resultado.drop(columns=["texto_norm"]).to_csv(index=False),
            file_name=busqueda.replace('"', "").strip() + ".csv",
        )

        st.subheader("Detalle")

        paginas = max(1, -(-len(resultado) // RESULTADOS_POR_PAGINA))
        pagina = 1
        if paginas > 1:
            pagina = st.number_input(
                f"Página (de {paginas})", min_value=1, max_value=paginas, value=1
            )
        inicio = (pagina - 1) * RESULTADOS_POR_PAGINA
        pagina_df = resultado.iloc[inicio:inicio + RESULTADOS_POR_PAGINA]

        for _, fila in pagina_df.iterrows():
            n_zonas = len(buscar_en_texto(fila["texto"], terminos, contexto))
            titulo = (
                f"📅 {fila['fecha'] or 'sin fecha'} | {fila['archivo']} "
                f"— {n_zonas} coincidencia{'s' if n_zonas != 1 else ''}"
            )
            with st.expander(titulo):
                mostrar_fragmentos(fila["texto"], terminos, contexto)
                if st.checkbox("Ver parte completo", key=f"completo_{fila.name}"):
                    st.text(fila["texto"])

# ==================================================
# TAB 2
# ==================================================

with tab2:
    st.title("🛠 Ficha técnica de equipo")

    equipo = st.text_input("Tag del equipo", key="equipo").strip()

    if equipo:
        hist = incidencias[
            incidencias["equipo"].astype(str).str.upper().str.strip()
            == equipo.upper()
        ].copy()

        st.success(f"{len(hist)} incidencias encontradas")

        if len(hist) > 0:
            fechas = [f for f in hist["fecha"] if f]

            col1, col2, col3 = st.columns(3)
            col1.metric("Incidencias", len(hist))
            if fechas:
                col2.metric("Primer registro", min(fechas))
                col3.metric("Último registro", max(fechas))

            texto_total = normalizar(" ".join(hist["descripcion"].tolist()))

            # Se cuenta cuántas veces sale cada palabra, no solo si sale.
            problemas = {p: texto_total.count(p) for p in PROBLEMAS}
            problemas = {p: n for p, n in problemas.items() if n}
            acciones = {a: texto_total.count(a) for a in ACCIONES}
            acciones = {a: n for a, n in acciones.items() if n}

            st.divider()
            st.subheader("🧠 Diagnóstico automático")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Problemas detectados")
                if problemas:
                    for p, n in sorted(problemas.items(), key=lambda x: -x[1]):
                        st.write(f"• {p} ({n})")
                else:
                    st.write("No se detectan problemas recurrentes.")
            with c2:
                st.markdown("### Acciones detectadas")
                if acciones:
                    for a, n in sorted(acciones.items(), key=lambda x: -x[1]):
                        st.write(f"• {a} ({n})")
                else:
                    st.write("No se detectan acciones.")

            st.divider()
            st.subheader("📅 Cronología")

            hist = hist.sort_values("fecha")
            for _, fila in hist.iterrows():
                with st.expander(f"{fila['fecha'] or 'sin fecha'} | {fila['archivo']}"):
                    st.write(fila["descripcion"])

                    # Contexto: busca el equipo en el parte original completo.
                    original = relevos[relevos["archivo"] == fila["archivo"]]
                    if len(original) and st.checkbox(
                        "Ver en el parte original", key=f"orig_{fila.name}"
                    ):
                        mostrar_fragmentos(
                            original.iloc[0]["texto"],
                            [normalizar(equipo)],
                            contexto=4,
                        )

            st.download_button(
                "📥 Exportar histórico",
                hist.to_csv(index=False),
                file_name=f"{equipo}.csv",
            )
