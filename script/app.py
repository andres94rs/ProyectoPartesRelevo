import os

import pandas as pd
import streamlit as st

from buscador import (
    ACCIONES,
    agrupar_repetidos,
    PROBLEMAS,
    buscar_en_texto,
    contar_palabra,
    extraer_fecha,
    normalizar,
    normalizar_tag,
    orden_turno,
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
# Todas las menciones de equipos (preferido) o, si no existe, solo las
# que tienen palabras clave (CSV antiguo).
RUTA_MENCIONES = os.path.join(CARPETA_BASE, "incidencias.csv")
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
    ruta = RUTA_MENCIONES if os.path.exists(RUTA_MENCIONES) else RUTA_INCIDENCIAS
    df = pd.read_csv(ruta)
    df["descripcion"] = df["descripcion"].fillna("").astype(str)
    df["archivo"] = df["archivo"].fillna("").astype(str)
    # Columnas opcionales: así funciona con el CSV antiguo y con el nuevo
    for col in ["etiquetas", "contexto"]:
        df[col] = df[col].fillna("").astype(str) if col in df else ""
    df["fecha"] = df["archivo"].map(extraer_fecha)
    # P-101B, P101B y "p 101 b" cuentan como el mismo equipo
    df["equipo_norm"] = df["equipo"].map(normalizar_tag)
    return df


relevos = cargar_relevos()
incidencias = cargar_incidencias()

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

        # Por fecha y, dentro del día, por turno (mañana, tarde, noche)
        resultado = resultado.assign(
            _turno=resultado["archivo"].map(orden_turno)
        ).sort_values(
            ["fecha", "_turno"], ascending=(orden == "Más antiguos")
        ).drop(columns="_turno")

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
            incidencias["equipo_norm"] == normalizar_tag(equipo)
        ].copy()

        solo_claves = st.toggle(
            "Solo líneas con palabras clave (fuga, avería, reparación…)",
            value=False,
            help="Desactivado: se ven TODAS las líneas donde sale el equipo, "
                 "para no perder novedades que no usan esas palabras "
                 "(p. ej. 'se deja en vigilancia').",
        )
        if solo_claves:
            hist = hist[hist["etiquetas"] != ""]

        st.success(f"{len(hist)} menciones encontradas")

        if len(hist) > 0:
            fechas = [f for f in hist["fecha"] if f]
            periodos = agrupar_repetidos(hist.to_dict("records"))

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                "Situaciones distintas", len(periodos),
                help="Las líneas que se repiten turno tras turno cuentan "
                     "como una sola situación.",
            )
            col2.metric(
                "Turnos con mención", hist["archivo"].nunique(),
                help="Número de partes en los que aparece el equipo.",
            )
            if fechas:
                col3.metric("Primer registro", min(fechas))
                col4.metric("Último registro", max(fechas))

            texto_total = " ".join(hist["descripcion"].tolist())

            # Cuántas veces sale cada palabra (completa: "centrífuga" no es "fuga")
            problemas = {p: contar_palabra(texto_total, p) for p in PROBLEMAS}
            problemas = {p: n for p, n in problemas.items() if n}
            acciones = {a: contar_palabra(texto_total, a) for a in ACCIONES}
            acciones = {a: n for a, n in acciones.items() if n}

            st.divider()
            st.subheader("🧠 Diagnóstico automático")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Problemas detectados")
                if problemas:
                    for p, n in sorted(problemas.items(), key=lambda x: -x[1]):
                        st.write(f"• {p} ({n} menciones)")
                else:
                    st.write("No se detectan problemas recurrentes.")
            with c2:
                st.markdown("### Acciones detectadas")
                if acciones:
                    for a, n in sorted(acciones.items(), key=lambda x: -x[1]):
                        st.write(f"• {a} ({n} menciones)")
                else:
                    st.write("No se detectan acciones.")

            st.divider()
            st.subheader("📅 Cronología")

            hist = hist.assign(
                _turno=hist["archivo"].map(orden_turno)
            ).sort_values(["fecha", "_turno"]).drop(columns="_turno")

            agrupar = st.toggle(
                "Agrupar lo que se repite turno tras turno",
                value=True,
                help="Activado: una línea que se copia igual durante muchos "
                     "turnos se muestra una sola vez, con el periodo que "
                     "duró. Desactivado: se ve cada parte por separado.",
            )

            def detalle(fila, clave):
                """Texto de la mención y acceso al parte original."""
                st.text(fila["contexto"] or fila["descripcion"])
                original = relevos[relevos["archivo"] == fila["archivo"]]
                if len(original) and st.checkbox(
                    f"Ver en el parte original ({fila['archivo']})", key=clave
                ):
                    mostrar_fragmentos(
                        original.iloc[0]["texto"], [normalizar(equipo)], contexto=4
                    )

            if agrupar:
                st.caption(
                    f"{len(hist)} menciones resumidas en {len(periodos)} "
                    "situaciones. 🔁 = se repite durante varios turnos · "
                    "📌 = aparece una sola vez (novedad puntual)."
                )
                for i, p in enumerate(periodos):
                    resumen = p["descripcion"]
                    if len(resumen) > 90:
                        resumen = resumen[:90] + "…"
                    if p["n"] > 1:
                        titulo = (
                            f"🔁 {p['desde'] or 'sin fecha'} → {p['hasta']} "
                            f"({p['n']} turnos) | {resumen}"
                        )
                    else:
                        titulo = f"📌 {p['desde'] or 'sin fecha'} | {resumen}"
                    with st.expander(titulo):
                        if p["n"] > 1:
                            st.markdown("**Primera vez que aparece:**")
                            detalle(p["primero"], f"orig_{i}_a")
                            st.markdown("**Última vez que aparece:**")
                            detalle(p["ultimo"], f"orig_{i}_b")
                        else:
                            detalle(p["primero"], f"orig_{i}_a")
            else:
                for n, (_, fila) in enumerate(hist.iterrows()):
                    with st.expander(
                        f"{fila['fecha'] or 'sin fecha'} | {fila['archivo']}"
                    ):
                        detalle(fila, f"orig_s_{n}")

            st.download_button(
                "📥 Exportar histórico",
                hist.to_csv(index=False),
                file_name=f"{equipo}.csv",
            )
