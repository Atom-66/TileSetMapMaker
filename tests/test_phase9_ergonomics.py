import json
import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.app_services import (
    DiagnosticService,
    InterfaceProfileService,
)
from tileset_map_maker.core.shortcuts import ShortcutManager
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.notification_center import NotificationBanner


APP = QApplication.instance() or QApplication([])


class TestPhase9Ergonomics(unittest.TestCase):
    def setUp(self):
        self.settings = QSettings(
            "TileSetMapMakerTests", f"Phase9-{id(self)}"
        )
        self.settings.clear()

    def test_shortcuts_persist_and_detect_conflicts(self):
        manager = ShortcutManager(self.settings)
        action = QAction("Zapisz")
        manager.register("save_project", action)
        manager.set_shortcuts({"save_project": "Ctrl+Shift+S"})
        self.assertEqual(action.shortcut().toString(), "Ctrl+Shift+S")
        restored = ShortcutManager(self.settings)
        self.assertEqual(restored.shortcuts["save_project"], "Ctrl+Shift+S")
        with self.assertRaises(ValueError):
            manager.set_shortcuts(
                {"save_project": "Ctrl+K", "open_project": "Ctrl+K"}
            )

    def test_diagnostics_report_exports(self):
        service = DiagnosticService()
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "diagnostics.json")
            service.export_report(path)
            with open(path, encoding="utf-8") as handle:
                report = json.load(handle)
        self.assertEqual(report["application"], "TileSet Map Maker")
        self.assertIn("python", report)
        self.assertTrue(os.path.isfile(service.log_path))

    def test_interface_profiles_persist_and_retrieve(self):
        service = InterfaceProfileService(self.settings)
        window = MainWindow()
        service.save(
            "Mapa", window.saveGeometry(), window.saveState(), {"version": 3}
        )
        self.assertIn("Mapa", service.names())
        data = service.get("Mapa")
        self.assertTrue(data["geometry"])
        self.assertEqual(data["toolbar_layout"]["version"], 3)
        window.close()

    def test_notifications_are_non_modal_and_show_details(self):
        banner = NotificationBanner()
        called = []
        banner.show_message(
            "Błąd", "error", details=lambda: called.append(True)
        )
        self.assertFalse(banner.isHidden())
        banner.details.click()
        self.assertEqual(called, [True])

    def test_main_window_exposes_search_profiles_and_diagnostics(self):
        window = MainWindow()
        self.assertTrue(window.act_command_search.shortcut().toString())
        self.assertTrue(hasattr(window, "save_interface_profile"))
        self.assertTrue(hasattr(window, "export_diagnostics"))
        self.assertFalse(window.notification_banner.isVisible())
        window.close()

    def test_toolbar_edit_mode_preserves_window_state(self):
        window = MainWindow()
        window.resize(1000, 700)
        before = bytes(window.saveGeometry())
        window.toolbar_manager.set_edit_mode(True)
        self.assertTrue(window.toolbar_manager.is_edit_mode)
        self.assertEqual(bytes(window.saveGeometry()), before)
        window.toolbar_manager.set_edit_mode(False)
        self.assertEqual(bytes(window.saveGeometry()), before)
        window.close()


if __name__ == "__main__":
    unittest.main()
