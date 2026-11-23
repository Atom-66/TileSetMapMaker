import os
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import (
    QApplication,
    QToolBar,
    QToolButton,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QDialog,
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt6.QtGui import QAction, QMouseEvent, QColor

from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.main_window import MainWindow, LAYOUT_VERSION
from tileset_map_maker.ui.toolbar_manager import (
    ToolbarManager,
    CustomizableToolBar,
    ToolbarItemDragFilter,
    TOOLBAR_LAYOUT_VERSION,
)
from tileset_map_maker.models.project import Project


class TestAuditToolbarAndControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.config_manager = ConfigManager(config_path=self.config_path)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_01_persistence_and_restart_restoration(self):
        """1. Modyfikacja kolejności przycisków i kategorii, zapis i wierne odtworzenie po restarcie."""
        main_tb = CustomizableToolBar("Main", toolbar_id="main")
        sec_tb = CustomizableToolBar("Secondary", toolbar_id="secondary")
        manager = ToolbarManager(main_tb, self.config_manager, secondary_toolbar=sec_tb)

        # Reorder items
        manager.move_item("export", "project", 0)
        manager.move_item("save", "history", 1)
        # Move category to secondary toolbar
        manager.move_category("system", 0, target_toolbar_id="secondary")
        # Move autotile category to main toolbar
        manager.move_category("autotile", 1, target_toolbar_id="main")

        manager.save_layout()

        # Simulate restart: create brand new manager loading from same config file
        main_tb2 = CustomizableToolBar("Main2", toolbar_id="main")
        sec_tb2 = CustomizableToolBar("Secondary2", toolbar_id="secondary")
        manager2 = ToolbarManager(main_tb2, self.config_manager, secondary_toolbar=sec_tb2)
        manager2.load_layout()

        # Verify exact restoration
        self.assertEqual(manager2.categories["project"].item_ids[0], "export")
        self.assertIn("save", manager2.categories["history"].item_ids)
        self.assertEqual(manager2.categories["system"].toolbar_id, "secondary")
        self.assertEqual(manager2.categories["autotile"].toolbar_id, "main")
        self.assertEqual(manager2.category_order[0], "system")
        self.assertEqual(manager2.category_order[1], "autotile")

    def test_02_migration_and_deduplication(self):
        """2. Odporność na uszkodzone dane, duplikaty przycisków w JSON i brak wersji (migracja v1 -> v2)."""
        main_tb = CustomizableToolBar("Main", toolbar_id="main")
        sec_tb = CustomizableToolBar("Secondary", toolbar_id="secondary")
        manager = ToolbarManager(main_tb, self.config_manager, secondary_toolbar=sec_tb)

        # Simulate corrupt config: same item 'export' placed in both 'project' and 'history',
        # obsolete item 'obsolete_btn', and missing version tag
        corrupt_layout = {
            "secondary_toolbar_visible": True,
            "categories": [
                {"id": "project", "toolbar_id": "main", "visible": True, "items": ["new", "export", "obsolete_btn"]},
                {"id": "history", "toolbar_id": "main", "visible": True, "items": ["export", "undo", "redo"]},
            ]
        }

        manager.apply_layout(corrupt_layout)

        # 'export' must only exist in 'project' and NOT in 'history'
        self.assertIn("export", manager.categories["project"].item_ids)
        self.assertNotIn("export", manager.categories["history"].item_ids)
        # 'obsolete_btn' must be pruned
        self.assertNotIn("obsolete_btn", manager.categories["project"].item_ids)

        # All registered items not in corrupt categories must be safely recovered to default categories
        self.assertIn("save", manager.categories["project"].item_ids)

        # Serialized dictionary must include version tag 2
        saved_dict = manager.get_layout_dict()
        self.assertEqual(saved_dict.get("version"), TOOLBAR_LAYOUT_VERSION)

    def test_03_no_drag_filter_leak(self):
        """3. Brak wycieków filtrów zdarzeń przy wielokrotnym przebudowywaniu pasków."""
        main_tb = CustomizableToolBar("Main", toolbar_id="main")
        sec_tb = CustomizableToolBar("Secondary", toolbar_id="secondary")
        manager = ToolbarManager(main_tb, self.config_manager, secondary_toolbar=sec_tb)

        test_widget = QPushButton("Custom Widget")
        manager.register_item("custom_item", "Custom", "brush", widget=test_widget)

        # Rebuild toolbar 5 times
        for _ in range(5):
            manager.build_toolbar()

        # Count ToolbarItemDragFilter instances on test_widget
        filters = [c for c in test_widget.children() if isinstance(c, ToolbarItemDragFilter)]
        self.assertEqual(len(filters), 1)

    def test_04_drag_finished_safety_on_deleted_button(self):
        """4. Bezpieczeństwo on_drag_finished przy przeciąganiu przycisków QAction."""
        main_tb = CustomizableToolBar("Main", toolbar_id="main")
        sec_tb = CustomizableToolBar("Secondary", toolbar_id="secondary")
        manager = ToolbarManager(main_tb, self.config_manager, secondary_toolbar=sec_tb)
        manager.set_edit_mode(True)

        act = QAction("Action", main_tb)
        manager.register_item("test_action", "Action", "project", action=act)
        manager.build_toolbar()

        btn = manager.items["test_action"].button
        self.assertIsNotNone(btn)

        manager.on_item_drag_started("test_action", btn)
        # Drop triggers move and rebuild, which clears toolbar and deletes old button
        manager.move_item("test_action", "project", 0)

        # Finishing drag must not throw RuntimeError on deleted widget
        try:
            manager.on_drag_finished()
        except RuntimeError as e:
            self.fail(f"on_drag_finished threw RuntimeError: {e}")

    def test_05_secondary_toolbar_visibility_sync(self):
        """5. Synchronizacja widoczności dodatkowego paska narzędzi z konfiguracją."""
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")), \
             patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), \
             patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            win = MainWindow(config_manager=self.config_manager)
            win.show()
            tm = win.toolbar_manager

            # Hide secondary toolbar
            tm.set_secondary_toolbar_visible(False)
            self.assertFalse(win.secondary_toolbar.isVisible())
            self.assertFalse(tm.secondary_toolbar_visible)

            # Show secondary toolbar
            tm.set_secondary_toolbar_visible(True)
            self.assertTrue(win.secondary_toolbar.isVisible())
            self.assertTrue(tm.secondary_toolbar_visible)

            win.close()

    def test_06_toggle_buttons_highlight_persistence(self):
        """6. Zachowanie podświetlenia przycisków przełączników przy zmianach układu."""
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")), \
             patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), \
             patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            win = MainWindow(config_manager=self.config_manager)
            win.show()
            bar = win.brush_options

            # Activate Auto-Tile and Randomizer
            bar.chk_autotile.setChecked(True)
            bar.chk_variants.setChecked(True)
            self.assertTrue(bar.chk_autotile.isChecked())
            self.assertTrue(bar.chk_variants.isChecked())

            # Move Auto-Tile to project category
            win.toolbar_manager.move_item("autotile_toggle", "project", 0)

            # Verify it is still active and checked
            self.assertTrue(bar.chk_autotile.isChecked())
            self.assertTrue(bar.settings.auto_tile_enabled)

            # Grab widget to verify visual blue color
            pix = bar.chk_autotile.grab()
            img = pix.toImage()
            # Check center pixel color: should be royal blue (#2563eb or #1d4ed8)
            col = img.pixelColor(bar.chk_autotile.width() // 2, bar.chk_autotile.height() // 2)
            self.assertGreater(col.blue(), 200)
            self.assertLess(col.red(), 60)

            win.close()

    def test_07_objects_panel_project_update(self):
        """7. Prawidłowa aktualizacja referencji projektu i historii w ObjectListPanel."""
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")), \
             patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), \
             patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            win = MainWindow(config_manager=self.config_manager)
            initial_proj = win.project
            self.assertIs(win.objects_panel.project, initial_proj)

            # Create new project
            win.new_project()
            self.assertIsNot(win.project, initial_proj)
            self.assertIs(win.objects_panel.project, win.project)

            win.close()


if __name__ == "__main__":
    unittest.main()
