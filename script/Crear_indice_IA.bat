@echo off
rem Prepara la busqueda por significado (pestana "Buscar por significado").
rem Solo hace falta ejecutarlo una vez. Se puede cortar con Ctrl+C y
rem volver a lanzar: continua donde lo dejo.
title Crear indice de busqueda por significado
cd /d "%~dp0"

echo ==================================================
echo  1/2  Instalando la libreria necesaria...
echo ==================================================
py -m pip install fastembed truststore
if errorlevel 1 goto error

echo.
echo ==================================================
echo  2/2  Creando el indice (la primera vez tarda)...
echo       Puedes seguir usando el ordenador.
echo       No hagas clic dentro de esta ventana.
echo ==================================================
py indexar.py
if errorlevel 1 goto error

echo.
echo Listo. Abre el buscador y entra en "Buscar por significado".
pause
exit /b 0

:error
echo.
echo *** No se ha podido completar. Haz una foto de esta ventana. ***
pause
exit /b 1
