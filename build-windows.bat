@echo off
setlocal
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
cd /d "%~dp0"

set "VENV_PYTHON=.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" goto :install_deps

where py.exe >nul 2>nul
if not errorlevel 1 (
    echo Tworzenie srodowiska .venv za pomoca Python Launcher...
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if not errorlevel 1 (
        py -3 -m venv .venv
        if errorlevel 1 goto :venv_failed
        goto :install_deps
    )
    echo Python znaleziony przez "py" jest starszy niz 3.10.
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    echo Tworzenie srodowiska .venv za pomoca polecenia python...
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if not errorlevel 1 (
        python -m venv .venv
        if errorlevel 1 goto :venv_failed
        goto :install_deps
    )
    echo Python znaleziony w PATH jest starszy niz 3.10.
)

echo.
echo Nie znaleziono Pythona 3.10 lub nowszego.
echo Zainstaluj Python z python.org i zaznacz opcje:
echo   - Add python.exe to PATH
echo   - Install launcher for all users
exit /b 1

:install_deps
if not exist "%VENV_PYTHON%" goto :venv_failed

"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo Srodowisko .venv zawiera Pythona starszego niz 3.10.
    echo Usun katalog .venv i uruchom skrypt ponownie.
    exit /b 1
)

echo Instalowanie zaleznosci buildowych...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :deps_failed
"%VENV_PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :deps_failed

echo Budowanie TileSetMapMaker.exe...
"%VENV_PYTHON%" build.py --target exe
if errorlevel 1 goto :build_failed

echo.
echo Gotowe: dist\TileSetMapMaker.exe
exit /b 0

:venv_failed
echo.
echo Nie udalo sie utworzyc srodowiska .venv.
echo Sprawdz, czy Python zawiera modul venv i czy katalog projektu jest zapisywalny.
exit /b 1

:deps_failed
echo.
echo Instalacja zaleznosci nie powiodla sie.
echo Sprawdz polaczenie internetowe i zawartosc requirements-build.txt.
exit /b 1

:build_failed
echo.
echo Budowanie EXE nie powiodlo sie. Log bledu znajduje sie powyzej.
exit /b 1
