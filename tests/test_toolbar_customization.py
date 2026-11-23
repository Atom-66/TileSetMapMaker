import os
import tempfile
import unittest
from PyQt6.QtWidgets import QApplication, QToolBar, QWidget
from PyQt6.QtCore import Qt

from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.widgets.switch_toggle import SwitchToggle, ToolbarToggleButton
from tileset_map_maker.ui.toolbar_manager import (
    ToolbarManager,
    ToolbarCustomizerDialog,
    ToolbarCategoryDef,
    ToolbarItemDef,
)
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.models.project import Project
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.models.layer import MapItem, ItemType
from tileset_map_maker.models.brush_preset import BrushSettings

app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestToolbarCustomization(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cfg_path = os.path.join(self.tmp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(custom_config_path=self.cfg_path)
        self.main_toolbar = QToolBar()
        self.sec_toolbar = QToolBar()
        self.manager = ToolbarManager(self.main_toolbar, self.config_manager, secondary_toolbar=self.sec_toolbar)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_toolbar_toggle_button_states_and_active_style(self):
        """Verify ToolbarToggleButton operates as an icon button without solid blinding blue rectangles."""
        btn = ToolbarToggleButton("Randomizer", checked=False, icon_name="randomizer")
        self.assertIsInstance(btn, SwitchToggle, "Must inherit SwitchToggle for 100% backward compatibility")
        self.assertFalse(btn.isChecked())

        # Test toggling
        toggled_events = []
        btn.toggled.connect(lambda val: toggled_events.append(val))
        btn.setChecked(True)
        self.assertTrue(btn.isChecked())
        self.assertEqual(toggled_events, [True])

        # Active style check: vibrant blue (#2563eb) with clear light blue border (#93c5fd) and white text/icon
        self.assertIn("#2563eb", btn.styleSheet())
        self.assertIn("#93c5fd", btn.styleSheet())

        # Pixel-level render check: must actually paint #2563eb onto the screen
        btn.resize(85, 26)
        pix_on = btn.grab()
        self.assertEqual(pix_on.toImage().pixelColor(4, 4).name(), "#2563eb")

        # Test toggle() method back to inactive
        btn.toggle()
        self.assertFalse(btn.isChecked())
        self.assertEqual(toggled_events, [True, False])
        # Inactive style check: neutral dark background
        self.assertIn("#27272a", btn.styleSheet())
        pix_off = btn.grab()
        self.assertEqual(pix_off.toImage().pixelColor(4, 4).name(), "#27272a")
        self.assertEqual(btn.height(), 26)

    def test_manager_registration_and_default_categories(self):
        """Verify all 9 standard categories, Randomizer title, and default toolbars."""
        ordered = self.manager.get_ordered_categories()
        cat_ids = [c.id for c in ordered]
        expected = ["project", "history", "view", "brush", "autotile", "paths", "randomizer", "transforms", "system"]
        self.assertEqual(cat_ids, expected)

        # Check Randomizer category title
        self.assertEqual(self.manager.categories["randomizer"].title, "Randomizer")

        # Check default toolbar assignment
        self.assertEqual(self.manager.categories["project"].toolbar_id, "main")
        self.assertEqual(self.manager.categories["brush"].toolbar_id, "main")
        self.assertEqual(self.manager.categories["autotile"].toolbar_id, "secondary")

        # Register sample items
        w1 = QWidget()
        w2 = QWidget()
        w3 = QWidget()
        self.manager.register_item("item1", "Item 1", "project", widget=w1)
        self.manager.register_item("item2", "Item 2", "brush", widget=w2)
        self.manager.register_item("item3", "Item 3", "autotile", widget=w3)

        self.assertIn("item1", self.manager.categories["project"].item_ids)
        self.assertIn("item2", self.manager.categories["brush"].item_ids)
        self.assertIn("item3", self.manager.categories["autotile"].item_ids)

        self.manager.build_toolbar()
        self.assertTrue(len(self.main_toolbar.actions()) > 0)
        self.assertTrue(len(self.sec_toolbar.actions()) > 0)

    def test_multi_toolbar_category_movement_and_persistence(self):
        """Verify categories can be moved between Main and Secondary toolbars and survive restart."""
        # Move 'brush' category from secondary to main toolbar
        payload = self.manager.get_layout_dict()
        for cat in payload["categories"]:
            if cat["id"] == "brush":
                cat["toolbar_id"] = "main"

        self.manager.apply_layout(payload)
        self.assertEqual(self.manager.categories["brush"].toolbar_id, "main")

        # Save and restore in a fresh manager instance
        self.manager.save_layout()

        fresh_manager = ToolbarManager(self.main_toolbar, self.config_manager, secondary_toolbar=self.sec_toolbar)
        fresh_manager.load_layout()
        self.assertEqual(fresh_manager.categories["brush"].toolbar_id, "main")

    def test_item_moving_between_categories(self):
        """Verify moving a button/item from one category to another."""
        w = QWidget()
        self.manager.register_item("custom_btn", "Custom Button", "project", widget=w)
        self.assertIn("custom_btn", self.manager.categories["project"].item_ids)

        # Move item from 'project' to 'brush'
        payload = self.manager.get_layout_dict()
        for cat in payload["categories"]:
            if cat["id"] == "project" and "custom_btn" in cat["items"]:
                cat["items"].remove("custom_btn")
            if cat["id"] == "brush":
                cat["items"].append("custom_btn")

        self.manager.apply_layout(payload)
        self.assertNotIn("custom_btn", self.manager.categories["project"].item_ids)
        self.assertIn("custom_btn", self.manager.categories["brush"].item_ids)
        self.assertEqual(self.manager.items["custom_btn"].category_id, "brush")

    def test_category_and_item_visibility_toggling(self):
        """Verify hiding and showing categories and items across toolbars."""
        w_undo = QWidget()
        w_redo = QWidget()
        self.manager.register_item("undo", "Undo", "history", widget=w_undo)
        self.manager.register_item("redo", "Redo", "history", widget=w_redo)
        self.manager.build_toolbar()

        self.manager.set_category_visible("history", False)
        self.assertFalse(self.manager.categories["history"].visible)

        # Items in hidden category must be removed from toolbar
        actions = self.main_toolbar.actions()
        action_widgets = [self.main_toolbar.widgetForAction(a) for a in actions]
        self.assertNotIn(w_undo, action_widgets)
        self.assertNotIn(w_redo, action_widgets)

        # Re-enable
        self.manager.set_category_visible("history", True)
        self.assertTrue(self.manager.categories["history"].visible)
        actions = self.main_toolbar.actions()
        action_widgets = [self.main_toolbar.widgetForAction(a) for a in actions]
        self.assertIn(w_undo, action_widgets)
        self.assertIn(w_redo, action_widgets)

    def test_customizer_dialog_operations(self):
        """Verify ToolbarCustomizerDialog with multi-toolbar tabs and switching."""
        win = MainWindow()
        dlg = ToolbarCustomizerDialog(win.toolbar_manager, parent=win)

        # Check tabs exist
        self.assertEqual(dlg.tab_toolbars.count(), 2)

        # Test switching category to the other toolbar
        dlg.tab_toolbars.setCurrentIndex(0)  # Main toolbar
        dlg.list_main_cats.setCurrentRow(0)
        selected_cat_id = dlg._get_current_category_id()
        self.assertIsNotNone(selected_cat_id)

        initial_tb = dlg.working_categories[selected_cat_id].toolbar_id
        dlg._switch_category_toolbar()
        new_tb = dlg.working_categories[selected_cat_id].toolbar_id
        self.assertNotEqual(initial_tb, new_tb)

        dlg.close()
        win.close()

    def test_tool_panel_responsive_horizontal_layout(self):
        """Verify ToolPanel switches to horizontal layout when flattened (height < 250 or width > height)."""
        win = MainWindow()
        win.show()
        tp = win.tool_panel
        app.processEvents()
        self.assertLessEqual(win.tool_dock.widget().width(), 52)
        for button in tp.buttons.values():
            button_rect = button.geometry()
            self.assertGreaterEqual(button_rect.left(), 0)
            self.assertLessEqual(button_rect.right(), tp.width())

        # Normal tall dimensions -> Vertical orientation
        tp.resize(50, 450)
        tp.resizeEvent(None)
        self.assertEqual(tp.current_orientation, Qt.Orientation.Vertical)

        # Flattened dimensions -> Horizontal orientation
        tp.resize(450, 60)
        tp.resizeEvent(None)
        self.assertEqual(tp.current_orientation, Qt.Orientation.Horizontal)

        # Dock area change simulation
        tp.on_dock_location_changed(Qt.DockWidgetArea.TopDockWidgetArea)
        self.assertEqual(tp.current_orientation, Qt.Orientation.Horizontal)

        win.close()

    def test_eraser_size_setting_and_footprint(self):
        """Verify EraserTool respects configurable eraser_size for multi-tile erasing."""
        proj = Project(10, 10, 32)
        layer = proj.get_active_layer()

        # Place tiles in a 3x3 block from (2, 2) to (4, 4)
        for r in range(2, 5):
            for c in range(2, 5):
                item = MapItem(c, r, "test_asset", 0, 0, 32, 32, ItemType.TILE)
                layer.set_tile(c, r, item)

        self.assertIsNotNone(layer.get_tile(3, 3))
        self.assertIsNotNone(layer.get_tile(2, 2))
        self.assertIsNotNone(layer.get_tile(4, 4))

        settings = BrushSettings(size=1, eraser_size=3)
        self.assertEqual(settings.eraser_size, 3)

        context = ToolContext(
            project=proj,
            active_layer=layer,
            selected_asset=None,
            brush_settings=settings,
            asset_manager=None,
        )

        eraser = EraserTool()
        # Erase at center (3, 3) with size 3 (radius 1 covers (2,2) through (4,4))
        eraser.on_press(3, 3, context)
        eraser.on_release(3, 3, context)

        # All 9 tiles in 3x3 area must be erased
        for r in range(2, 5):
            for c in range(2, 5):
                self.assertIsNone(layer.get_tile(c, r), f"Tile at ({c}, {r}) should have been erased by size 3 eraser")

    def test_mainwindow_multi_toolbar_and_randomizer_naming(self):
        """Verify MainWindow has secondary toolbar, 26px controls, and Randomizer naming."""
        win = MainWindow()
        self.assertTrue(hasattr(win, "secondary_toolbar"))
        self.assertIsNotNone(win.secondary_toolbar)

        # Randomizer name verification
        self.assertEqual(win.brush_options.chk_variants.text(), "Randomizer")
        self.assertEqual(win.toolbar_manager.categories["randomizer"].title, "Randomizer")

        # Active tool switches size label
        win.tool_panel.select_tool_by_key("eraser")
        self.assertEqual(win.brush_options.lbl_size.text(), "Gumka:")

        win.tool_panel.select_tool_by_key("brush")
        self.assertEqual(win.brush_options.lbl_size.text(), "Pędzel:")

        win.close()


if __name__ == "__main__":
    unittest.main()
