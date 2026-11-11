@echo off
rem Hace que el buscador arranque solo al iniciar sesion en Windows.
rem Despues basta con abrir el favorito http://localhost:8501 en Chrome.
rem Para quitarlo: ejecuta Quitar_arranque_automatico.bat
rem Si algo falla, mira registro_arranque.txt en esta carpeta.
cd /d "%~dp0"
set "DESTINO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BuscadorRelevos.bat"

> "%DESTINO%" echo @echo off
>> "%DESTINO%" echo call "%~dp0Arranque_buscador.bat"

if not exist "%DESTINO%" (
    echo No se ha podido instalar. Puede que tu equipo no lo permita.
    pause
    exit /b 1
)

echo Instalado. El buscador arrancara solo cada vez que inicies sesion.
echo Guarda en Chrome el favorito:  http://localhost:8501
echo.
echo Arrancandolo ahora...
call "%~dp0Arranque_buscador.bat"
timeout /t 10 >nul
start "" http://localhost:8501
echo.
echo Si la pagina no carga, espera unos segundos y pulsa Recargar.
echo Si sigue sin cargar, abre registro_arranque.txt en esta carpeta.
pause
