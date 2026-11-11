@echo off
rem Abre el buscador de partes de relevo (sin actualizar los datos).
title Buscador de partes de relevo
cd /d "%~dp0"
netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
if not errorlevel 1 (
    echo El buscador ya esta funcionando. Abriendo http://localhost:8501 ...
    start "" http://localhost:8501
    timeout /t 3 >nul
    exit /b 0
)
echo Abriendo el buscador... (no cierres esta ventana mientras lo uses)
py -m streamlit run app.py --server.port 8501
pause
