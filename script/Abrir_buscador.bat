@echo off
rem Abre el buscador de partes de relevo (sin actualizar los datos).
title Buscador de partes de relevo
cd /d "%~dp0"
echo Abriendo el buscador... (no cierres esta ventana mientras lo uses)
py -m streamlit run app.py
pause
