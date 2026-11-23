import json
import os
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.models.asset import Asset, AssetType
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.version import APP_VERSION


APP = QApplication.instance() or QApplication([])
ROOT = os.path.dirname(os.path.dirname(__file__))


class TestPhase10Release(unittest.TestCase):
    def test_smoke_test_starts_without_network_or_assets(self):
        environment = dict(os.environ)
        environment.update(
            {
                "QT_QPA_PLATFORM": "offscreen",
                "TILESET_CONFIG_DIR": os.path.join(
                    tempfile.gettempdir(), "tmm-smoke-config"
                ),
            }
        )
        completed = subprocess.run(
            [sys.executable, "run_app.py", "--smoke-test"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )

    def test_corrupt_png_is_reported_without_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "broken.png")
            with open(path, "wb") as handle:
                handle.write(b"not a png")
            manager = AssetManager()
            asset = Asset.__new__(Asset)
            asset.id = "broken"
            asset.name = "Broken"
            asset.file_path = path
            asset.asset_type = AssetType.TILESET
            manager.assets[asset.id] = asset
            self.assertIsNone(manager.get_pixmap(asset.id))
            self.assertIsNone(manager.get_image(asset.id))

    def test_corrupt_project_returns_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "broken.tmmap")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"project":')
            self.assertIsNone(ProjectIO.load_project(path, AssetManager()))
            self.assertTrue(ProjectIO.get_last_error())

    def test_missing_asset_can_be_exported_only_after_validation_failure(self):
        project = Project()
        project.get_active_layer().set_tile(
            0, 0, MapItem("missing", 0, 0)
        )
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "invalid.json")
            manager = AssetManager()
            self.assertFalse(
                ProjectIO.export_public_json(project, manager, output)
            )
            self.assertIn("missing", ProjectIO.get_last_error())
            self.assertFalse(os.path.exists(output))

    def test_multiple_save_load_cycles_preserve_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "cycles.tmmap")
            manager = AssetManager()
            project = Project(name="Cycles", map_width=8, map_height=6)
            project.get_active_layer().set_tile(
                3, 2, MapItem("asset", 3, 2)
            )
            for cycle in range(20):
                self.assertTrue(
                    ProjectIO.save_project(project, manager, path)
                )
                restored = ProjectIO.load_project(path, AssetManager())
                self.assertIsNotNone(restored)
                self.assertIsNotNone(
                    restored.get_active_layer().get_tile(3, 2)
                )
                project = restored
                manager = AssetManager()
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["project"]["name"], "Cycles")
            self.assertTrue(os.path.exists(path + ".bak"))

    def test_repeated_window_resize_and_toolbar_cycles(self):
        window = MainWindow()
        for width, height in (
            (800, 600),
            (1200, 750),
            (500, 500),
            (1400, 850),
        ):
            window.resize(width, height)
            window.toolbar_manager.set_edit_mode(True)
            window.toolbar_manager.build_toolbar()
            window.toolbar_manager.set_edit_mode(False)
            APP.processEvents()
            self.assertEqual((window.width(), window.height()), (width, height))
        window.close()

    def test_dragging_docks_repeatedly_keeps_widgets_valid(self):
        window = MainWindow()
        window.show()
        for _ in range(8):
            window.addDockWidget(
                window.dockWidgetArea(window.properties_dock),
                window.properties_dock,
            )
            window.tabifyDockWidget(
                window.layer_dock, window.properties_dock
            )
            APP.processEvents()
            self.assertIsNotNone(window.properties_dock.parentWidget())
        window.project.is_modified = False
        window.close()

    def test_release_version_is_semantic(self):
        major, minor, patch = APP_VERSION.split(".")
        self.assertTrue(major.isdigit())
        self.assertTrue(minor.isdigit())
        self.assertTrue(patch.isdigit())


if __name__ == "__main__":
    unittest.main()
