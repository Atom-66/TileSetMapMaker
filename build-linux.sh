#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v appimagetool >/dev/null 2>&1 && [[ -z "${APPIMAGETOOL:-}" ]]; then
    echo "Nie znaleziono appimagetool. Zainstaluj go i dodaj do PATH." >&2
    exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements-build.txt
exec .venv/bin/python build.py --target appimage
