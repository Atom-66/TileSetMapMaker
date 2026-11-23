#!/usr/bin/env python3
"""Build a native Windows executable or Linux AppImage."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from tileset_map_maker.version import APP_VERSION


ROOT = Path(__file__).resolve().parent
APP_NAME = "TileSetMapMaker"


def build_executable() -> None:
    if os.name != "nt":
        raise RuntimeError("Plik EXE należy budować w systemie Windows.")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile",
            "--name",
            APP_NAME,
            "--version-file",
            str(ROOT / "build-version.txt"),
            "--add-data",
            f"icons{os.pathsep}icons",
            "run_app.py",
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"\nGotowe: {ROOT / 'dist' / f'{APP_NAME}.exe'}")


def build_appimage() -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("AppImage należy budować w systemie Linux.")

    appimagetool = os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool")
    if not appimagetool:
        raise RuntimeError(
            "Nie znaleziono appimagetool. Zainstaluj appimagetool i dodaj go do PATH."
        )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            APP_NAME,
            "--add-data",
            f"icons{os.pathsep}icons",
            "run_app.py",
        ],
        cwd=ROOT,
        check=True,
    )

    app_dir = ROOT / "build" / "appimage" / "TileSetMapMaker.AppDir"
    if app_dir.exists():
        shutil.rmtree(app_dir)

    app_bin = app_dir / "usr" / "bin" / APP_NAME
    app_bin.parent.mkdir(parents=True)
    shutil.copytree(ROOT / "dist" / APP_NAME, app_bin)

    app_icon = (
        app_dir
        / "usr"
        / "share"
        / "icons"
        / "hicolor"
        / "scalable"
        / "apps"
        / "tileset-map-maker.svg"
    )
    app_icon.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "icons" / "outline" / "map.svg", app_icon)

    (app_dir / "tileset-map-maker.desktop").write_text(
        "[Desktop Entry]\n"
        "Name=TileSet Map Maker\n"
        "Exec=TileSetMapMaker %F\n"
        "Icon=tileset-map-maker\n"
        "Type=Application\n"
        "Categories=Graphics;2DGraphics;\n"
        "Terminal=false\n",
        encoding="utf-8",
    )
    app_run = app_dir / "AppRun"
    app_run.write_text(
        '#!/bin/sh\n'
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        'exec "$HERE/usr/bin/TileSetMapMaker/TileSetMapMaker" "$@"\n',
        encoding="utf-8",
    )
    app_run.chmod(0o755)

    output = ROOT / "dist" / f"{APP_NAME}-{platform.machine()}.AppImage"
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    subprocess.run(
        [appimagetool, "--no-appstream", str(app_dir), str(output)],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    print(f"\nGotowe: {output}")


def main() -> int:
    default_target = (
        "exe"
        if os.name == "nt"
        else "appimage"
        if sys.platform.startswith("linux")
        else None
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=("appimage", "exe"),
        default=default_target,
        required=default_target is None,
        help="format do zbudowania (domyślnie: format bieżącego systemu)",
    )
    args = parser.parse_args()
    if args.target == "exe":
        (ROOT / "build-version.txt").write_text(
            "VSVersionInfo(\n"
            "  ffi=FixedFileInfo(\n"
            f"    filevers=({', '.join(APP_VERSION.split('.'))}, 0),\n"
            f"    prodvers=({', '.join(APP_VERSION.split('.'))}, 0),\n"
            "    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,\n"
            "    date=(0, 0)),\n"
            "  kids=[StringFileInfo([StringTable('040904E4', [\n"
            "    StringStruct('ProductName', 'TileSet Map Maker'),\n"
            f"    StringStruct('ProductVersion', '{APP_VERSION}'),\n"
            f"    StringStruct('FileVersion', '{APP_VERSION}'),\n"
            "    StringStruct('CompanyName', 'Atom-66'),\n"
            "    StringStruct('FileDescription', 'TileSet Map Maker')])]),\n"
            "    VarFileInfo([VarStruct('Translation', [0x409, 1252])])]\n"
            ")\n",
            encoding="utf-8",
        )

    try:
        if args.target == "exe":
            build_executable()
        else:
            build_appimage()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Błąd budowania: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
