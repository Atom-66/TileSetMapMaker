import os
import unittest
from unittest.mock import patch
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog

from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.toolbar_manager import ToolbarVisibilityDialog


class TestToolbarItemVisibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")), \
             patch.object(QFileDialog, "getSaveFileName", return_value=("", "")), \
             patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.win = MainWindow()
            self.tm = self.win.toolbar_manager
            # Ensure toolbar starts with clean default order and visibility
            self.tm.reset_to_default(save=False)

    def tearDown(self):
        if hasattr(self, "win") and self.win:
            self.win.close()
            self.win = None

    def test_01_hide_single_item(self):
        """1. Ukrycie pojedynczego przycisku – całkowicie znika z paska bez utraty logiki."""
        self.assertIn("save", self.win.toolbar.item_widgets_map)
        self.assertTrue(self.tm.items["save"].visible)

        # Hide 'save'
        self.tm.hide_item("save")
        self.assertFalse(self.tm.items["save"].visible)

        # Button is no longer present in toolbar widgets map
        self.assertNotIn("save", self.win.toolbar.item_widgets_map)

        # Action itself still exists and is functional
        self.assertIsNotNone(self.win.act_save)
        self.assertTrue(self.win.act_save.isEnabled())

        # Hidden items helper
        hidden = self.tm.get_hidden_items()
        self.assertEqual(len(hidden), 1)
        self.assertEqual(hidden[0].id, "save")

    def test_02_hide_multiple_items_and_repack(self):
        """2. Ukrycie kilku przycisków – pozostałe elementy przesuwają się i wypełniają lukę."""
        initial_count = len(self.win.toolbar.item_widgets_map)
        self.assertGreater(initial_count, 10)

        # Hide 5 items: 'save', 'export', 'undo', 'redo', 'path_gen_dialog'
        to_hide = ["save", "export", "undo", "redo", "path_gen_dialog"]
        for i_id in to_hide:
            self.tm.hide_item(i_id)

        self.assertGreaterEqual(len(self.win.toolbar.item_widgets_map), 10)
        for i_id in to_hide:
            self.assertNotIn(i_id, self.win.toolbar.item_widgets_map)
            self.assertFalse(self.tm.items[i_id].visible)

        # Visible items remain in correct relative order
        vis_items = self.tm.get_visible_items()
        self.assertEqual(len(vis_items), 18)
        vis_ids = [item.id for item in vis_items]
        self.assertEqual(vis_ids[:2], ["new", "open"])
        self.assertIn("grid", vis_ids)
        self.assertNotIn("save", vis_ids)

    def test_03_restore_single_item_to_exact_position(self):
        """3. Przywrócenie wybranego przycisku – wraca dokładnie na swoją pierwotną pozycję."""
        # Record initial full item order
        initial_order = list(self.tm.item_order)

        # Hide 'grid'
        self.tm.hide_item("grid")
        self.assertNotIn("grid", self.win.toolbar.item_widgets_map)

        # Restore 'grid'
        self.tm.show_item("grid")
        self.assertTrue(self.tm.items["grid"].visible)
        self.assertIn("grid", self.win.toolbar.item_widgets_map)

        # Verify item order remained 100% stable
        self.assertEqual(self.tm.item_order, initial_order)

        # Verify 'grid' appears right after 'redo' and before 'fit'
        vis_ids = [item.id for item in self.tm.get_visible_items()]
        grid_idx = vis_ids.index("grid")
        self.assertEqual(vis_ids[grid_idx - 1], "redo")
        self.assertEqual(vis_ids[grid_idx + 1], "fit")

    def test_04_restore_all_items_single_command(self):
        """4. Przywrócenie wszystkich przycisków jednym poleceniem."""
        # Hide 10 items
        for i_id in self.tm.item_order[:10]:
            self.tm.hide_item(i_id)

        self.assertEqual(len(self.tm.get_hidden_items()), 10)
        self.assertGreaterEqual(len(self.win.toolbar.item_widgets_map), 4)

        # Single call to restore all
        self.tm.show_all_items()

        self.assertEqual(len(self.tm.get_hidden_items()), 0)
        self.assertEqual(len(self.tm.get_visible_items()), 23)
        self.assertGreaterEqual(len(self.win.toolbar.item_widgets_map), 14)

    def test_05_drag_and_drop_preserves_hidden_items_order(self):
        """5. Przeciąganie widocznych elementów zachowuje pozycje ukrytych elementów bez duplikatów."""
        # Order starts as default: ... 'undo', 'redo', 'grid', 'fit', 'palette' ...
        # Hide 'grid' and 'fit'
        self.tm.hide_item("grid")
        self.tm.hide_item("fit")

        # Now drag 'palette' to the very beginning (index 0)
        self.tm.move_item_flat("palette", 0)

        # Verify 'palette' is first in item_order
        self.assertEqual(self.tm.item_order[0], "palette")

        # Hidden items 'grid' and 'fit' are still preserved after 'redo' in item_order
        self.assertIn("grid", self.tm.item_order)
        self.assertIn("fit", self.tm.item_order)
        redo_idx = self.tm.item_order.index("redo")
        grid_idx = self.tm.item_order.index("grid")
        fit_idx = self.tm.item_order.index("fit")
        self.assertEqual(grid_idx, redo_idx + 1)
        self.assertEqual(fit_idx, grid_idx + 1)

        # When we unhide 'grid' and 'fit', no duplicates occur
        self.tm.show_item("grid")
        self.tm.show_item("fit")
        self.assertEqual(len(self.tm.item_order), 23)
        self.assertEqual(len(set(self.tm.item_order)), 23)

    def test_06_flow_layout_downward_expansion_respects_visibility(self):
        """6. FlowLayout i wysokość paska uwzględniają wyłącznie widoczne przyciski."""
        tb = self.win.toolbar
        tb.resize(600, 100)

        # With all 26 items at 600px, it takes 3 rows (height >= 85px)
        h_all = tb.flow_layout.heightForWidth(600)
        self.assertGreater(h_all, 30)

        # Hide 18 items, keeping only 8 items
        for i_id in self.tm.item_order[8:]:
            self.tm.hide_item(i_id)

        # Now 8 items fit comfortably in 1 row at 600px width (height <= 40px)
        h_few = tb.flow_layout.heightForWidth(600)
        self.assertGreaterEqual(h_few, 48)

    def test_07_persistence_after_restart(self):
        """7. Trwałość ukrycia i kolejności po zapisie i ponownym uruchomieniu aplikacji."""
        # Hide 'export' and 'path_gen_dialog', and move 'redo' to front
        self.tm.hide_item("export")
        self.tm.hide_item("path_gen_dialog")
        self.tm.move_item_flat("redo", 0)

        # Get serialized layout dict
        layout_data = self.tm.get_layout_dict()
        self.assertEqual(layout_data["version"], 3)
        self.assertFalse(layout_data["item_visibility"]["export"])
        self.assertFalse(layout_data["item_visibility"]["path_gen_dialog"])
        self.assertTrue(layout_data["item_visibility"]["save"])
        self.assertEqual(layout_data["item_order"][0], "redo")

        # Simulate fresh app startup and apply layout
        new_win = MainWindow()
        try:
            new_tm = new_win.toolbar_manager
            new_tm.apply_layout(layout_data)

            # Verification in restored window
            self.assertEqual(new_tm.item_order[0], "redo")
            self.assertFalse(new_tm.items["export"].visible)
            self.assertFalse(new_tm.items["path_gen_dialog"].visible)
            self.assertNotIn("export", new_win.toolbar.item_widgets_map)
            self.assertNotIn("path_gen_dialog", new_win.toolbar.item_widgets_map)
            self.assertIn("save", new_win.toolbar.item_widgets_map)
            self.assertIn("redo", new_win.toolbar.item_widgets_map)
        finally:
            new_win.close()

    def test_08_toolbar_visibility_dialog_interaction(self):
        """8. Dedykowane okno dialogowe ToolbarVisibilityDialog – filtrowanie, zmiana i aplikacja."""
        dlg = ToolbarVisibilityDialog(self.tm, self.win)

        # Check all 23 items populated in list
        self.assertEqual(dlg.list_widget.count(), 23)

        # Test search filter for unique name "Ścieżek"
        dlg._filter_list("Ścieżek")
        single_row = [
            i for i in range(dlg.list_widget.count())
            if not dlg.list_widget.item(i).isHidden()
        ]
        self.assertEqual(len(single_row), 1)
        self.assertIn("Ścieżek", dlg.list_widget.item(single_row[0]).text())

        # Clear filter
        dlg._filter_list("")

        # Test "Ukryj wszystkie"
        dlg._hide_all()
        for vis in dlg.working_visibility.values():
            self.assertFalse(vis)

        # Test "Pokaż wszystkie"
        dlg._show_all()
        for vis in dlg.working_visibility.values():
            self.assertTrue(vis)

        # Uncheck first item manually
        first_item = dlg.list_widget.item(0)
        first_id = first_item.data(Qt.ItemDataRole.UserRole)
        first_item.setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(dlg.working_visibility[first_id])

        # Apply changes
        dlg._apply_changes()
        self.assertFalse(self.tm.items[first_id].visible)
        self.assertNotIn(first_id, self.win.toolbar.item_widgets_map)


if __name__ == "__main__":
    unittest.main()
