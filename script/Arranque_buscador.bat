@echo off
rem Arranca el buscador en segundo plano (ventana minimizada).
rem Lo usa el arranque automatico de Windows; tambien se puede lanzar a mano.
rem Todo lo que pase se apunta en registro_arranque.txt (en esta carpeta).
cd /d "%~dp0"

netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
if not errorlevel 1 exit /b 0

echo [%date% %time%] Arrancando el buscador desde %cd% > registro_arranque.txt
where py >> registro_arranque.txt 2>&1
if errorlevel 1 (
    echo ERROR: no se encuentra "py" ^(Python^). >> registro_arranque.txt
    exit /b 1
)
start "Buscador de partes de relevo" /min cmd /c "py -m streamlit run app.py --server.headless true --server.port 8501 >> registro_arranque.txt 2>&1 & echo El buscador se ha cerrado. >> registro_arranque.txt"
