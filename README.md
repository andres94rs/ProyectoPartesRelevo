# ProyectoPartesRelevo
El proyecto de trabajo donde con IA puedo preguntar a los partes de relevo cualquier cosa para sacar información útil.
Se va a hacer en el disco C: y tendrá carpetas script y base, dónde se almacenará todo el código.

## Estructura

```
script/
  extraer_relevos.py      1) PDF/Excel de I:\ -> base/relevos_historico.csv (incremental)
  extraer_incidencias.py  2) relevos_historico.csv -> base/incidencias.csv (todas las menciones)
                             y base/incidencias_reales.csv (las que tienen palabras clave)
  app.py                  Web de búsqueda (Streamlit)
  buscador.py             Lógica de búsqueda, contexto, fechas y troceado
  preparar_fragmentos.py  Genera base/fragmentos_relevos.csv (paso previo para la IA)
  requirements.txt
base/                     (en C:\ProyectoPartesRelevo\base, no se sube a GitHub)
  relevos_historico.csv
  incidencias_reales.csv
```

## Uso

Con doble clic (carpeta `script`):

| Archivo | Qué hace |
|---|---|
| `Actualizar_y_abrir.bat` | Procesa los partes nuevos y abre el buscador |
| `Abrir_buscador.bat` | Abre el buscador sin actualizar |
| `Crear_indice_IA.bat` | Prepara la búsqueda por significado (una sola vez; tarda) |
| `Instalar_arranque_automatico.bat` | El buscador arranca solo con Windows; basta el favorito `http://localhost:8501` |
| `Quitar_arranque_automatico.bat` | Deshace lo anterior |
| `Arranque_buscador.bat` | Arranca el buscador minimizado (lo usa el arranque automático). Si falla, ver `registro_arranque.txt` |

A mano:

```
py -m pip install -r requirements.txt     (solo la primera vez)
py extraer_relevos.py
py extraer_incidencias.py
py -m streamlit run app.py
```

## Cómo busca

- Varias palabras → partes que contienen **todas** (`bomba fuga`).
- Entre comillas → frase exacta (`"paso interno"`).
- Sin importar tildes ni mayúsculas (`averia` encuentra `Avería`).
- Los tags se buscan sin importar guiones (`vb1070` encuentra `VB-107-0`).
- Muestra **todas** las coincidencias de cada parte, con líneas completas por
  delante y por detrás (ajustable con "Líneas de contexto"), resaltadas y
  ordenadas por fecha.

## Búsqueda por significado (fase 1 de IA)

Pestaña **🧠 Buscar por significado**: encuentra líneas de los partes que
hablan de lo que preguntas aunque usen otras palabras ("derrame al suelo"
encuentra "rebose del foso"). Todo se ejecuta en el ordenador, sin Ollama
y sin enviar datos fuera; solo se descarga una vez el modelo (~470 MB,
`intfloat/multilingual-e5-small`) a `base/modelos`.

- `semantica.py`: modelo, líneas distintas y búsqueda híbrida
  (significado + palabras en común + filtro por tag de equipo).
- `indexar.py`: crea/actualiza `base/indice_semantico/`. Incremental y
  reanudable.
