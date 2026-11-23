import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build


@unittest.skipUnless(sys.platform.startswith("linux"), "AppImage is built on Linux")
class TestAppImageBuild(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        icon = self.root / "icons" / "outline" / "map.svg"
        icon.parent.mkdir(parents=True)
        icon.write_text("<svg/>", encoding="utf-8")
        (self.root / "run_app.py").write_text("", encoding="utf-8")
        self.output = self.root / "dist" / (
            f"TileSetMapMaker-{platform.machine()}.AppImage"
        )
        self.output.parent.mkdir()
        self.output.write_bytes(b"previous")
        self.calls = 0

    def run_command(self, command, **kwargs):
        self.calls += 1
        if self.calls == 1:
            distribution = Path(command[command.index("--distpath") + 1])
            program = distribution / "TileSetMapMaker"
            (program / "_internal").mkdir(parents=True)
            (program / "_internal" / "dependency").write_text("library")
            (program / "TileSetMapMaker").write_text("executable")
            self.assertTrue(Path(command[-1]).is_absolute())
            return

        app_dir = Path(command[-2])
        self.assertTrue((app_dir / "tileset-map-maker.svg").is_file())
        self.assertTrue((app_dir / "tileset-map-maker.desktop").is_file())
        self.assertTrue(
            (app_dir / "usr/bin/TileSetMapMaker/_internal/dependency").is_file()
        )
        Path(command[-1]).write_bytes(b"packaged")

    def test_build_packages_internal_and_publishes_one_file(self):
        with patch.object(build, "ROOT", self.root), \
             patch.dict(os.environ, {"APPIMAGETOOL": "/test/appimagetool"}), \
             patch.object(build.subprocess, "run", side_effect=self.run_command):
            build.build_appimage()

        self.assertEqual(self.calls, 2)
        self.assertEqual(self.output.read_bytes(), b"packaged")
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])
        self.assertEqual(list((self.root / "build" / "appimage").iterdir()), [])

    def test_failed_packaging_keeps_previous_appimage(self):
        def fail_packaging(command, **kwargs):
            if self.calls:
                raise subprocess.CalledProcessError(1, command)
            self.run_command(command, **kwargs)

        with patch.object(build, "ROOT", self.root), \
             patch.dict(os.environ, {"APPIMAGETOOL": "/test/appimagetool"}), \
             patch.object(build.subprocess, "run", side_effect=fail_packaging):
            with self.assertRaises(subprocess.CalledProcessError):
                build.build_appimage()

        self.assertEqual(self.output.read_bytes(), b"previous")
        self.assertEqual(list((self.root / "build" / "appimage").iterdir()), [])

    def test_missing_output_is_an_error(self):
        def omit_output(command, **kwargs):
            if not self.calls:
                self.run_command(command, **kwargs)

        with patch.object(build, "ROOT", self.root), \
             patch.dict(os.environ, {"APPIMAGETOOL": "/test/appimagetool"}), \
             patch.object(build.subprocess, "run", side_effect=omit_output):
            with self.assertRaisesRegex(RuntimeError, "nie utworzył"):
                build.build_appimage()

        self.assertEqual(self.output.read_bytes(), b"previous")


if __name__ == "__main__":
    unittest.main()
