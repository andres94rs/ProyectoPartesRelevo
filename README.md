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

```
cd C:\ProyectoPartesRelevo\script
pip install -r requirements.txt
python extraer_relevos.py        (la 1ª vez tarda; después solo procesa lo nuevo)
python extraer_incidencias.py
streamlit run app.py
```

## Cómo busca

- Varias palabras → partes que contienen **todas** (`bomba fuga`).
- Entre comillas → frase exacta (`"paso interno"`).
- Sin importar tildes ni mayúsculas (`averia` encuentra `Avería`).
- Muestra **todas** las coincidencias de cada parte, con líneas completas por
  delante y por detrás (ajustable con "Líneas de contexto"), resaltadas y
  ordenadas por fecha.
