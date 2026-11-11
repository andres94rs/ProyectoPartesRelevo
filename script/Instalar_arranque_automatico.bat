@echo off
rem Hace que el buscador arranque solo al iniciar sesion en Windows.
rem Despues basta con abrir el favorito http://localhost:8501 en Chrome.
rem Para quitarlo: ejecuta Quitar_arranque_automatico.bat
set "DESTINO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BuscadorRelevos.bat"

> "%DESTINO%" echo @echo off
>> "%DESTINO%" echo cd /d "%~dp0"
>> "%DESTINO%" echo start "Buscador de partes de relevo" /min py -m streamlit run app.py --server.headless true --server.port 8501

if exist "%DESTINO%" (
    echo Instalado. El buscador arrancara solo cada vez que inicies sesion.
    echo Guarda en Chrome el favorito:  http://localhost:8501
    echo.
    netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
    if errorlevel 1 (
        echo Arrancandolo ahora por primera vez...
        call "%DESTINO%"
        timeout /t 8 >nul
    )
    start "" http://localhost:8501
) else (
    echo No se ha podido instalar. Puede que tu equipo no lo permita.
)
pause
