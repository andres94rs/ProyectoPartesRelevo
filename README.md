# ProyectoPartesRelevo
El proyecto de trabajo donde con IA puedo preguntar a los partes de relevo cualquier cosa para sacar información útil.
Se va a hacer en el disco C: y tendrá carpetas script y base, dónde se almacenará todo el código.

## Estructura

```
script/
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
streamlit run app.py
```

## Cómo busca

- Varias palabras → partes que contienen **todas** (`bomba fuga`).
- Entre comillas → frase exacta (`"paso interno"`).
- Sin importar tildes ni mayúsculas (`averia` encuentra `Avería`).
- Muestra **todas** las coincidencias de cada parte, con líneas completas por
  delante y por detrás (ajustable con "Líneas de contexto"), resaltadas y
  ordenadas por fecha.
