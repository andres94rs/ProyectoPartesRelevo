@echo off
rem Procesa los partes nuevos y abre el buscador.
title Buscador de partes de relevo
cd /d "%~dp0"

echo ==================================================
echo  1/4  Leyendo partes nuevos...
echo ==================================================
py extraer_relevos.py
if errorlevel 1 goto error

echo.
echo ==================================================
echo  2/4  Actualizando equipos e incidencias...
echo ==================================================
py extraer_incidencias.py
if errorlevel 1 goto error

echo.
echo ==================================================
echo  3/4  Actualizando la busqueda por significado...
echo ==================================================
py indexar.py --si-existe
if errorlevel 1 echo (No se ha podido actualizar; el resto del buscador funciona igual.)

echo.
echo ==================================================
echo  4/4  Abriendo el buscador...
echo       (no cierres esta ventana mientras lo uses)
echo ==================================================
py -m streamlit run app.py
pause
exit /b 0

:error
echo.
echo *** Ha habido un error. Los datos anteriores no se han borrado. ***
echo *** Haz una foto de esta ventana para revisarlo.               ***
pause
exit /b 1
