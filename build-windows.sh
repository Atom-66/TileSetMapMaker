#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "Budowanie Windows EXE przez Wine wymaga systemu Linux x86_64." >&2
    exit 1
fi
if ! command -v wine >/dev/null 2>&1; then
    echo "Nie znaleziono Wine. Zainstaluj Wine dla aplikacji 64-bitowych i uruchom skrypt ponownie." >&2
    exit 1
fi

tools_dir="$PWD/.tools"
export WINEPREFIX="${TILESET_WINEPREFIX:-$tools_dir/wine-windows}"
mkdir -p "$WINEPREFIX"
windows_python='C:\Python312\python.exe'

if [[ ! -f "$WINEPREFIX/drive_c/Python312/python.exe" ]]; then
    if ! command -v curl >/dev/null 2>&1 || ! command -v sha256sum >/dev/null 2>&1; then
        echo "Do pobrania i sprawdzenia instalatora Pythona wymagane sa curl i sha256sum." >&2
        exit 1
    fi
    installer="$tools_dir/python-3.12.10-amd64.exe"
    mkdir -p "$tools_dir"
    echo "Pobieranie instalatora Windows Python 3.12.10..."
    curl --fail --location --retry 3 \
        https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe \
        --output "$installer"
    echo "67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb  $installer" | sha256sum --check
    echo "Instalowanie Windows Python w $WINEPREFIX..."
    wine "$installer" /quiet InstallAllUsers=0 'TargetDir=C:\Python312' Include_test=0 PrependPath=0
    if [[ ! -f "$WINEPREFIX/drive_c/Python312/python.exe" ]]; then
        echo "Instalacja Windows Python nie utworzyla python.exe. Sprawdz komunikaty Wine." >&2
        exit 1
    fi
fi

echo "Sprawdzanie Windows Python..."
wine "$windows_python" --version
echo "Instalowanie zaleznosci Windows..."
wine "$windows_python" -m pip install -r requirements-build.txt
echo "Budowanie Windows EXE..."
wine "$windows_python" build.py --target exe
if [[ ! -f dist/TileSetMapMaker.exe ]]; then
    echo "Build zakonczyl sie bez bledu, ale nie znaleziono dist/TileSetMapMaker.exe." >&2
    exit 1
fi
echo "Gotowe: $PWD/dist/TileSetMapMaker.exe"
