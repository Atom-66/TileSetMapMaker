import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QPointF, QMimeData
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.models.asset import AssetType
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget


class LibraryMoveSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = ConfigManager(custom_config_path=os.path.join(self.tmp.name, "app_config.json"))
        self.manager = AssetManager()
        self.manager.category_tree.add_category_path("A/Sub/Deep")
        self.manager.category_tree.add_category_path("B")
        self.manager.category_tree.add_category_path("Empty")
        self.assets = []
        for index, folder in enumerate(("A", "A/Sub/Deep", "B")):
            path = os.path.join(self.tmp.name, f"{index}.png")
            Image.new("RGB", (32, 32), (index * 70, 0, 0)).save(path)
            asset, _, error = self.manager.import_single_file(
                path, target_category_path=folder, force_asset_type=AssetType.TILESET
            )
            self.assertFalse(error)
            self.assets.append(asset)
        self.palette = TilesetPaletteWidget(self.manager, self.config)
        self.palette.resize(500, 700)
        self.palette.show()
        self.app.processEvents()
        self.addCleanup(self.palette.close)

    def assert_consistent(self):
        seen = {}

        def walk(node):
            for asset_id in node.asset_ids:
                self.assertNotIn(asset_id, seen)
                seen[asset_id] = node.path
            for name, child in node.children.items():
                self.assertEqual(name, child.name)
                self.assertIs(child.parent, node)
                walk(child)

        walk(self.manager.category_tree.root)
        self.assertEqual(set(seen), set(self.manager.assets))
        for asset_id, asset in self.manager.assets.items():
            self.assertEqual(seen[asset_id], asset.category_path)

    def test_move_nested_folder_and_restart_then_move_to_root(self):
        self.palette.expanded_folders = ["A", "A/Sub", "A/Sub/Deep"]
        self.assertTrue(self.palette._move_library_items([("folder", "A")], "B"))
        self.assertEqual(self.assets[0].category_path, "B/A")
        self.assertEqual(self.assets[1].category_path, "B/A/Sub/Deep")
        self.assertEqual(self.palette.expanded_folders, ["B/A", "B/A/Sub", "B/A/Sub/Deep"])
        self.assert_consistent()

        restored = AssetManager()
        restored_config = ConfigManager(custom_config_path=self.config.config_path)
        _, expanded = restored_config.restore_tileset_library(restored)
        self.assertIsNotNone(restored.category_tree.get_node("B/A/Sub/Deep"))
        self.assertEqual(restored.get_asset(self.assets[1].id).category_path, "B/A/Sub/Deep")
        self.assertIn("B/A/Sub", expanded)

        self.assertTrue(self.palette._move_library_items([("folder", "B/A")], ""))
        self.assertTrue(self.palette._move_library_items([("tileset", self.assets[0].id)], ""))
        restored = AssetManager()
        ConfigManager(custom_config_path=self.config.config_path).restore_tileset_library(restored)
        self.assertEqual(restored.get_asset(self.assets[0].id).category_path, "")
        self.assert_consistent()
        env = os.environ.copy()
        env.update({
            "TILESET_CONFIG_DIR": self.tmp.name,
            "XDG_CONFIG_HOME": self.tmp.name,
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        script = """
import sys
from PyQt6.QtWidgets import QApplication
from tileset_map_maker.ui.main_window import MainWindow
app = QApplication([])
window = MainWindow()
window.show()
app.processEvents()
assert window.asset_manager.category_tree.get_node("A/Sub/Deep") is not None
assert window.asset_manager.get_asset(sys.argv[1]).category_path == ""
window.close()
app.processEvents()
"""
        result = subprocess.run(
            [sys.executable, "-c", script, self.assets[0].id],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_group_and_parent_child_selection_are_one_move(self):
        items = [("folder", "A"), ("folder", "A/Sub"), ("folder", "Empty"),
                 ("tileset", self.assets[1].id), ("tileset", self.assets[2].id)]
        self.assertTrue(self.palette._move_library_items(items, "B"))
        self.assertEqual(self.assets[1].category_path, "B/A/Sub/Deep")
        self.assertIsNotNone(self.manager.category_tree.get_node("B/Empty"))
        self.assert_consistent()

    def test_move_multiple_tilesets_and_empty_folder(self):
        items = [("tileset", self.assets[0].id), ("tileset", self.assets[1].id),
                 ("folder", "Empty")]
        self.assertTrue(self.palette._move_library_items(items, "B"))
        self.assertEqual(self.assets[0].category_path, "B")
        self.assertEqual(self.assets[1].category_path, "B")
        self.assertIsNotNone(self.manager.category_tree.get_node("B/Empty"))
        self.assert_consistent()

    def test_rejections_and_failed_save_preserve_memory_and_disk(self):
        self.assertTrue(self.palette._auto_save_library())
        with open(self.config.config_path, "rb") as file:
            original_disk = file.read()
        original_tree = self.manager.category_tree.to_dict()
        self.manager.category_tree.add_category_path("B/A")
        before = self.manager.category_tree.to_dict()
        with patch("PyQt6.QtWidgets.QMessageBox.warning"):
            for items, target in [
                ([("folder", "A")], "A"),
                ([("folder", "A")], "A/Sub"),
                ([("folder", "A")], "B"),
                ([("folder", "Empty"), ("folder", "A")], "B"),
                ([("folder", "missing")], "B"),
                ([("tileset", "missing")], "B"),
                ([("folder", "Empty")], "missing"),
            ]:
                self.assertFalse(self.palette._move_library_items(items, target))
                self.assertEqual(self.manager.category_tree.to_dict(), before)
            with patch.object(self.config, "save", return_value=False):
                self.assertFalse(self.palette._move_library_items([("folder", "Empty")], "B"))
            with patch.object(self.config, "save", side_effect=OSError("disk error")):
                self.assertFalse(self.palette._move_library_items([("folder", "Empty")], "B"))
        self.assertEqual(self.manager.category_tree.to_dict(), before)
        self.assertEqual(self.config.config_data["tileset_library"]["category_tree"], original_tree)
        with open(self.config.config_path, "rb") as file:
            self.assertEqual(file.read(), original_disk)
        self.assert_consistent()

    def test_cancelled_drag_does_not_change_library(self):
        tree = self.palette.tree
        folder = self.palette._find_folder_item("A")
        tree.setCurrentItem(folder)
        before = self.manager.category_tree.to_dict()

        class CancelledDrag:
            def __init__(self, _source):
                pass

            def setMimeData(self, _mime):
                pass

            def setPixmap(self, _pixmap):
                pass

            def exec(self, _action):
                return Qt.DropAction.IgnoreAction

        with patch("tileset_map_maker.ui.tileset_palette_widget.QDrag", CancelledDrag):
            tree.startDrag(Qt.DropAction.MoveAction)
        self.assertEqual(self.manager.category_tree.to_dict(), before)
        self.assertEqual(tree._drag_items, [])
        self.assert_consistent()

    def test_mouse_selection_and_refresh(self):
        tree = self.palette.tree
        a = self.palette._find_folder_item("A")
        b = self.palette._find_folder_item("B")
        empty = self.palette._find_folder_item("Empty")
        viewport = tree.viewport()

        def click(item, modifiers=Qt.KeyboardModifier.NoModifier):
            QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, modifiers,
                             tree.visualItemRect(item).center())
            self.app.processEvents()

        click(a)
        click(b, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual({i.data(0, Qt.ItemDataRole.UserRole + 1) for i in tree.selectedItems()}, {"A", "B"})
        click(empty, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual({i.data(0, Qt.ItemDataRole.UserRole + 1) for i in tree.selectedItems()}, {"A", "B", "Empty"})
        a.setExpanded(True)
        a.setExpanded(False)
        self.palette.txt_library_search.setText("no match")
        self.palette._apply_library_filter()
        self.assertEqual(self.palette._hidden_selection, {("folder", "A"), ("folder", "B"), ("folder", "Empty")})
        self.palette.refresh_tilesets()
        self.assertEqual(self.palette._hidden_selection, {("folder", "A"), ("folder", "B"), ("folder", "Empty")})
        self.palette.txt_library_search.clear()
        self.palette._apply_library_filter()
        self.assertEqual({i.data(0, Qt.ItemDataRole.UserRole + 1) for i in tree.selectedItems()}, {"A", "B", "Empty"})
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=QPoint(viewport.width() - 3, viewport.height() - 3))
        self.assertEqual(tree.selectedItems(), [])

    def test_drag_handler_moves_mixed_selection_and_preserves_it(self):
        tree = self.palette.tree
        folder = self.palette._find_folder_item("A")
        source = self.palette._find_folder_item("B")
        source.setExpanded(True)
        self.app.processEvents()
        tileset = source.child(0)
        viewport = tree.viewport()
        tree.scrollToItem(folder)
        self.app.processEvents()
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton,
                         pos=tree.visualItemRect(folder).center())
        self.assertEqual(
            [i.data(0, Qt.ItemDataRole.UserRole + 1) for i in tree.selectedItems()],
            ["A"],
            f"folder rect={tree.visualItemRect(folder)}, viewport={viewport.rect()}",
        )
        tree.scrollToItem(tileset)
        self.app.processEvents()
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier,
                         tree.visualItemRect(tileset).center())
        self.assertEqual(
            {(i.data(0, Qt.ItemDataRole.UserRole), i.data(0, Qt.ItemDataRole.UserRole + 1))
             for i in tree.selectedItems()},
            {("folder", "A"), ("tileset", self.assets[2].id)},
        )

        class Drop:
            accepted = False

            def position(self):
                target = self_target()
                tree.scrollToItem(target)
                self_app.processEvents()
                return QPointF(tree.visualItemRect(target).center())

            def mimeData(self):
                return QMimeData()

            def source(self):
                return tree

            def setDropAction(self, action):
                self.action = action

            def accept(self):
                self.accepted = True

            def ignore(self):
                self.accepted = False

        def self_target():
            return self.palette._find_folder_item("Empty")

        self_app = self.app
        drop = Drop()

        class Drag:
            def __init__(self, _source):
                pass

            def setMimeData(self, _mime):
                pass

            def setPixmap(self, _pixmap):
                pass

            def exec(self, _action):
                tree.dropEvent(drop)
                return Qt.DropAction.MoveAction

        with patch("tileset_map_maker.ui.tileset_palette_widget.QDrag", Drag):
            tree.startDrag(Qt.DropAction.MoveAction)
        self.assertTrue(drop.accepted)
        self.assertEqual(self.assets[2].category_path, "Empty")
        self.assertIsNotNone(self.manager.category_tree.get_node("Empty/A/Sub/Deep"))
        self.assertEqual(
            {(i.data(0, Qt.ItemDataRole.UserRole), i.data(0, Qt.ItemDataRole.UserRole + 1))
             for i in tree.selectedItems()},
            {("folder", "Empty/A"), ("tileset", self.assets[2].id)},
        )
        self.assert_consistent()


if __name__ == "__main__":
    unittest.main()
