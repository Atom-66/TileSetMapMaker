#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -z "${APPIMAGETOOL:-}" ]] && ! command -v appimagetool >/dev/null 2>&1 && [[ -x "$PWD/.tools/appimagetool" ]]; then
    export APPIMAGETOOL="$PWD/.tools/appimagetool"
fi

if [[ -z "${APPIMAGETOOL:-}" ]] && ! command -v appimagetool >/dev/null 2>&1; then
    if [[ "$(uname -m)" != "x86_64" ]]; then
        echo "Automatyczne pobieranie appimagetool jest obecnie obsługiwane tylko na x86_64." >&2
        exit 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "Do pobrania appimagetool wymagane jest polecenie curl." >&2
        exit 1
    fi

    tools_dir="$PWD/.tools"
    appimagetool="$tools_dir/appimagetool"
    mkdir -p "$tools_dir"
    echo "Pobieranie appimagetool do $appimagetool..."
    curl --fail --location --retry 3 \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage \
        --output "$appimagetool"
    chmod +x "$appimagetool"
    export APPIMAGETOOL="$appimagetool"
fi

if [[ -n "${APPIMAGETOOL:-}" ]]; then
    export PATH="$(dirname "$APPIMAGETOOL"):$PATH"
fi

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements-build.txt
exec .venv/bin/python build.py --target appimage
