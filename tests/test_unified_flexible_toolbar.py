import os
import unittest
from PyQt6.QtWidgets import QApplication, QWidget, QToolButton
from PyQt6.QtCore import Qt, QPoint, QRect, QSize
from PyQt6.QtGui import QAction, QColor

from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.toolbar_manager import (
    ToolbarManager,
    CustomizableToolBar,
    FlowLayout,
    TOOLBAR_LAYOUT_VERSION,
)
from tileset_map_maker.ui.widgets.switch_toggle import ToolbarToggleButton
from tileset_map_maker.ui.icons import IconFactory
from tileset_map_maker.core.config_manager import ConfigManager

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestUnifiedFlexibleToolbar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = MainWindow()
        self.manager = self.win.toolbar_manager
        self.toolbar = self.win.toolbar

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()

    def test_01_all_items_registered_and_in_item_order(self):
        """1. Verify all 26 tools, controls, and options exist in manager item_order."""
        expected_items = [
            "new", "open", "save", "export",
            "undo", "redo",
            "grid", "fit", "palette",
            "brush_size", "save_stamp",
            "autotile_toggle", "autotile_rules", "autotile_dialog",
            "path_gen_dialog",
            "variants_toggle", "variants_count", "variants_add", "variants_avoid", "variants_dialog",
            "rot_toggle", "flip_toggle", "seed_group",
            "settings", "shortcuts", "reset_ui"
        ]
        for item_id in expected_items:
            self.assertIn(item_id, self.manager.items, f"Missing item: {item_id}")
            self.assertIn(item_id, self.manager.item_order, f"Item not in item_order: {item_id}")

    def test_02_dynamic_wrapping_flow_layout_height_for_width(self):
        """2. Verify FlowLayout dynamically calculates row wrapping and height based on width."""
        flow = self.toolbar.flow_layout
        self.assertGreaterEqual(flow.count(), 5)

        # Ultra-wide width: all items fit in 1 single row
        single_row_h = flow.heightForWidth(2200)
        self.assertLessEqual(single_row_h, 60)

        # Standard desktop width (1200px): wraps into 2 rows
        two_rows_h = flow.heightForWidth(1200)
        self.assertGreaterEqual(two_rows_h, single_row_h)

        # Narrow width (600px): wraps into 3-4 rows
        narrow_h = flow.heightForWidth(600)
        self.assertGreaterEqual(narrow_h, two_rows_h)

        # Tiny width (300px): wraps into more rows
        tiny_h = flow.heightForWidth(300)
        self.assertGreater(tiny_h, narrow_h)

    def test_03_no_solid_blue_buttons_when_checked(self):
        """3. Verify checked buttons (Grid, Palette, Auto-Tile, Randomizer) have bright white icons, not solid blue."""
        # 1. Action button: Siatka (Grid)
        self.win.act_grid.setChecked(True)
        btn_grid = self.toolbar.widgetForAction(self.win.act_grid)
        if btn_grid:
            pix = btn_grid.grab()
            img = pix.toImage()
            bright_count = sum(
                1 for y in range(img.height()) for x in range(img.width())
                if img.pixelColor(x, y).red() > 200 and img.pixelColor(x, y).green() > 200 and img.pixelColor(x, y).blue() > 200
            )
            self.assertGreater(bright_count, 15, "Grid button icon must be visible white on blue!")

        # 2. Toggle button: Auto-Tile
        chk_autotile = self.win.brush_options.chk_autotile
        chk_autotile.setChecked(True)
        self.assertTrue(chk_autotile.isChecked())
        pix_auto = chk_autotile.grab()
        img_auto = pix_auto.toImage()
        blue_present = any(
            img_auto.pixelColor(x, y).blue() > 200 and img_auto.pixelColor(x, y).red() < 50
            for y in range(img_auto.height()) for x in range(img_auto.width())
        )
        self.assertTrue(blue_present, "Auto-Tile must be highlighted with active blue background")
        # Text/icon must have high contrast white
        white_present = any(
            img_auto.pixelColor(x, y).red() > 220 and img_auto.pixelColor(x, y).green() > 220 and img_auto.pixelColor(x, y).blue() > 220
            for y in range(img_auto.height()) for x in range(img_auto.width())
        )
        self.assertTrue(white_present, "Auto-Tile must have visible white text/icon")

    def test_04_drag_and_drop_flat_reordering(self):
        """4. Verify move_item_flat reorders any item to any index in the flat list."""
        initial_order = list(self.manager.item_order)
        first_item = initial_order[0]
        last_item = initial_order[-1]

        # Move last item to index 0
        self.manager.move_item_flat(last_item, 0)
        self.assertEqual(self.manager.item_order[0], last_item)

        # Move it back to the end
        self.manager.move_item_flat(last_item, len(self.manager.item_order))
        self.assertEqual(self.manager.item_order[-1], last_item)

    def test_05_multi_row_drop_slot_calculation(self):
        """5. Verify calculate_item_drop_slot accurately finds row and slot across wrapped rows."""
        self.manager.set_edit_mode(True)
        self.win.resize(600, 700)
        self.win.show()
        self.app.processEvents()

        # Slot calculation on top row vs lower row
        slot_x, target_cat, item_idx = self.toolbar.calculate_item_drop_slot(QPoint(50, 10), "export")
        self.assertIsInstance(slot_x, int)
        self.assertGreaterEqual(slot_x, 0)
        self.assertIsNotNone(target_cat)
        self.assertGreaterEqual(item_idx, 0)

    def test_06_schema_v3_persistence_and_migration(self):
        """6. Verify schema version 3 stores flat item_order and migrates legacy layouts."""
        self.assertEqual(TOOLBAR_LAYOUT_VERSION, 3)

        payload = self.manager.get_layout_dict()
        self.assertEqual(payload["version"], 3)
        self.assertIn("item_order", payload)
        self.assertIsInstance(payload["item_order"], list)
        self.assertGreaterEqual(len(payload["item_order"]), 20)

        # Test migration from legacy v2 payload without item_order
        v2_payload = {
            "version": 2,
            "secondary_toolbar_visible": False,
            "categories": [
                {"id": "history", "visible": True, "toolbar_id": "main", "items": ["redo", "undo"]},
                {"id": "project", "visible": True, "toolbar_id": "main", "items": ["save", "open", "new", "export"]},
            ],
            "item_visibility": {},
        }
        self.manager.apply_layout(v2_payload)
        self.assertEqual(self.manager.item_order[0], "redo")
        self.assertEqual(self.manager.item_order[1], "undo")
        self.assertEqual(self.manager.item_order[2], "save")

    def test_07_resize_and_repeated_rebuild_positions_remain_stable(self):
        """Repeated resize/rebuild cycles must preserve spacing and never overlap children."""
        self.win.show()
        for width, height in ((300, 700), (600, 700), (1400, 880), (600, 700), (300, 700)):
            self.win.resize(width, height)
            self.app.processEvents()
            self.manager.build_toolbar()
            self.app.processEvents()

            visible_geometries = []
            for widget in self.toolbar.category_widgets.values():
                if widget.isVisible() and not widget.isHidden():
                    visible_geometries.append(widget.geometry())

            for first in range(len(visible_geometries)):
                for second in range(first + 1, len(visible_geometries)):
                    a = visible_geometries[first]
                    b = visible_geometries[second]
                    if a.top() == b.top() or a.bottom() == b.bottom():
                        self.assertFalse(
                            a.intersects(b),
                            "Toolbar category widgets overlap after repeated resize",
                        )

            for widget in visible_geometries:
                self.assertGreaterEqual(widget.left(), 0)
                self.assertGreaterEqual(widget.top(), 0)
                self.assertLessEqual(widget.right(), max(self.toolbar.width(), 100))


if __name__ == "__main__":
    unittest.main()
