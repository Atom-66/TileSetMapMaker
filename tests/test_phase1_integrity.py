import json
import os
import tempfile
import unittest
from unittest.mock import patch

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autosave_manager import AutosaveManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.models.project import Project


class TestPhase1Integrity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = os.path.join(self.temp_dir.name, "project.tmmap")
        self.project = Project(name="Integralność")
        self.assets = AssetManager()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_is_atomic_and_keeps_previous_backup(self):
        self.assertTrue(ProjectIO.save_project(self.project, self.assets, self.project_path))
        self.project.name = "Nowsza wersja"
        self.project.is_modified = True
        self.assertTrue(ProjectIO.save_project(self.project, self.assets, self.project_path))

        with open(self.project_path + ".bak", encoding="utf-8") as handle:
            previous = json.load(handle)
        self.assertEqual(previous["project"]["name"], "Integralność")

    def test_invalid_schema_is_rejected_with_diagnostic(self):
        with open(self.project_path, "w", encoding="utf-8") as handle:
            json.dump({"version": "99.0", "project": {}}, handle)

        self.assertIsNone(ProjectIO.load_project(self.project_path, self.assets))
        self.assertIn("Nieobsługiwana wersja", ProjectIO.get_last_error())

    def test_failed_replace_does_not_change_existing_project(self):
        self.assertTrue(ProjectIO.save_project(self.project, self.assets, self.project_path))
        self.project.name = "Niezapisana"
        self.project.is_modified = True
        with patch("tileset_map_maker.core.project_io.os.replace", side_effect=OSError("interruption")):
            self.assertFalse(ProjectIO.save_project(self.project, self.assets, self.project_path))

        loaded = ProjectIO.load_project(self.project_path, AssetManager())
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Integralność")

    def test_autosave_throttles_repeated_changes(self):
        self.project.file_path = self.project_path
        manager = AutosaveManager(self.project, self.assets, interval_ms=60000)
        self.project.is_modified = True
        self.assertIsNotNone(manager.perform_autosave())
        self.project.is_modified = True
        self.assertIsNone(manager.perform_autosave())
        manager.cleanup_autosave()
        manager.deleteLater()


if __name__ == "__main__":
    unittest.main()
