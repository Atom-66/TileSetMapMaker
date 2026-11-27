import os
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.widgets.switch_toggle import SwitchToggle

app = QApplication.instance()
if not app:
    app = QApplication([])


class TestToolbarUnification(unittest.TestCase):
    """
    Unit & integration tests verifying:
    1. All editing options (Auto-Tiling, Random Variants, Path Generator, Size, Seed, Rot/Flip)
       are housed in the top main toolbar alongside grid/fit view options.
    2. The separate lower bar is completely removed from the central widget layout.
    3. All controls maintain their functional linkage to brush_settings and canvas.
    """

    def setUp(self):
        self.win = MainWindow()
        self.win.resize(1200, 750)

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()

    def test_01_all_editing_options_in_top_toolbar(self):
        """1. Top toolbar contains the unified brush_options widget and all required controls."""
        toolbar = self.win.toolbar
        self.assertIsNotNone(toolbar)

        # Check brush_options is embedded in the toolbar
        self.assertTrue(hasattr(self.win, "brush_options"))
        bo = self.win.brush_options
        self.assertEqual(bo.parent(), toolbar)

        # Verify editing controls exist on brush_options
        self.assertIsNotNone(bo.spin_size)
        self.assertIsNotNone(bo.btn_path_gen)
        self.assertIsInstance(bo.chk_variants, SwitchToggle)
        self.assertIsNotNone(bo.lbl_variant_count)
        self.assertIsNotNone(bo.btn_add_selection_variants)
        self.assertIsInstance(bo.chk_avoid, SwitchToggle)
        self.assertIsNotNone(bo.btn_randomizer)
        self.assertIsNotNone(bo.btn_rot)
        self.assertIsInstance(bo.chk_flip_h, SwitchToggle)
        self.assertIsInstance(bo.chk_flip_v, SwitchToggle)
        self.assertIsNotNone(bo.txt_seed)

    def test_02_lower_bar_removed_from_central_layout(self):
        """2. The separate lower bar is removed from the central widget layout."""
        central = self.win.centralWidget()
        layout = central.layout()

        # Iterate over all items in central layout
        widgets_in_central = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                widgets_in_central.append(item.widget())

        # Ensure brush_options is NOT inside central_layout
        self.assertNotIn(self.win.brush_options, widgets_in_central)
        # Verify map_tab_bar is at the top of central_layout
        self.assertEqual(widgets_in_central[0], self.win.map_tab_bar)

    def test_03_grid_visibility_and_view_actions_coexist_in_toolbar(self):
        """3. Grid visibility (act_grid) and fit-to-view (act_fit) coexist in toolbar with brush options."""
        toolbar = self.win.toolbar
        actions = toolbar.actions()

        self.assertIn(self.win.act_grid, actions)
        self.assertIn(self.win.act_fit, actions)
        self.assertIn(self.win.act_save_stamp, actions)

        # Toggle grid
        initial_grid = self.win.canvas.show_grid
        self.win.act_grid.setChecked(not initial_grid)
        self.win.act_grid.triggered.emit(not initial_grid)
        self.assertEqual(self.win.canvas.show_grid, not initial_grid)

    def test_04_editing_options_functional_in_top_toolbar(self):
        """4. Toggling options in the top toolbar immediately updates brush_settings and editor state."""
        bo = self.win.brush_options
        bs = self.win.canvas.tool_context.brush_settings

        # 1. Size
        bo.spin_size.setValue(4)
        self.assertEqual(bs.size, 4)

        # 2. Variants
        bo.chk_variants.setChecked(True)
        self.assertTrue(bs.random_variant)
        bo.chk_variants.setChecked(False)
        self.assertFalse(bs.random_variant)

        # 4. Avoid adjacent
        bo.chk_avoid.setChecked(True)
        self.assertTrue(bs.avoid_adjacent)
        bo.chk_avoid.setChecked(False)
        self.assertFalse(bs.avoid_adjacent)

        # 5. Rotation (90° CW step) & Flip
        self.assertEqual(bs.rotation, 0)
        bo.btn_rot.click()
        self.assertEqual(bs.rotation, 90)
        bo.btn_rot.click()
        self.assertEqual(bs.rotation, 180)
        bo.btn_rot.click()
        self.assertEqual(bs.rotation, 270)
        bo.btn_rot.click()
        self.assertEqual(bs.rotation, 0)

        bo.chk_flip_h.setChecked(True)
        self.assertTrue(bs.flip_horizontal)
        self.assertFalse(bs.flip_vertical)
        bo.chk_flip_v.setChecked(True)
        self.assertTrue(bs.flip_vertical)
        bo.chk_flip_h.setChecked(False)
        bo.chk_flip_v.setChecked(False)
        self.assertFalse(bs.flip_horizontal)
        self.assertFalse(bs.flip_vertical)

        # 6. Seed
        bo.txt_seed.setText("42")
        self.assertEqual(bs.seed, 42)
        bo.txt_seed.setText("")
        self.assertIsNone(bs.seed)

    def test_05_refresh_rulesets_and_variants_summary_functionality(self):
        """5. Refreshing variants summary maintains UI sync."""
        bo = self.win.brush_options
        bo.update_variants_summary()
        self.assertEqual(bo.lbl_variant_count.text(), "(0)")


if __name__ == "__main__":
    unittest.main()
