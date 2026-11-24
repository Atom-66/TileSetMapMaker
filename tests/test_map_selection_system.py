import os
import subprocess
import sys
import tempfile
import unittest

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QFocusEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.select_tool import SelectTool
from tileset_map_maker.models.asset import SelectedSubTile
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.models.project import Project
from tileset_map_maker.ui.map_canvas import MapCanvas


class MapSelectionSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.project = Project(map_width=12, map_height=12)
        self.layer = self.project.get_active_layer()
        self.assets = AssetManager()
        self.history = HistoryManager()
        self.context = ToolContext(self.project, self.assets, self.history, self.layer)
        self.tool = SelectTool()

    def select(self, a, b, modifiers=Qt.KeyboardModifier.NoModifier):
        self.context.selection_modifiers = modifiers
        self.tool.on_press(*a, self.context)
        self.tool.on_drag(*b, self.context)
        self.tool.on_release(*b, self.context)

    def snapshot(self):
        return {p: item.to_dict() for p, item in self.layer.tiles.items()}

    def tile(self, col, row, name="asset"):
        item = MapItem(name, col, row, source_x=16, flip_x=True,
                       rotation=90, properties={"nested": {"variant": 4}})
        self.layer.set_tile(col, row, item)
        return item

    def test_selection_add_subtract_invert_and_large(self):
        self.select((1, 1), (2, 2))
        self.select((4, 1), (4, 2), Qt.KeyboardModifier.ShiftModifier)
        self.select((2, 2), (2, 2), Qt.KeyboardModifier.AltModifier)
        self.assertEqual(self.context.selected_cells, {(1, 1), (2, 1), (1, 2), (4, 1), (4, 2)})
        self.tool.invert_selection(self.context)
        self.assertNotIn((1, 1), self.context.selected_cells)
        self.assertIn((0, 0), self.context.selected_cells)
        self.tool.select_all(self.context)
        self.assertEqual(len(self.context.selected_cells), 144)
        self.tile(6, 6)
        self.tool.select_layer_contents(self.context)
        self.assertEqual(self.context.selected_cells, {(6, 6)})
        self.project.map_width = 100000
        self.project.map_height = 100000
        self.tool.select_all(self.context)
        self.assertEqual(self.tool.region.rectCount(), 1)
        self.assertEqual(self.context.selected_cells, set())

    def test_copy_cut_paste_holes_repeated_undo_redo_and_move(self):
        original = self.tile(1, 1)
        self.tile(3, 1, "b")
        self.select((1, 1), (3, 1))
        self.tool.copy_selection(self.context)
        self.assertTrue(self.context.clipboard_region.contains(QPoint(1, 0)))
        self.tile(6, 5, "old")
        before = self.snapshot()
        self.assertTrue(self.tool.start_paste(self.context))
        self.assertTrue(self.tool.paste_at(5, 5, self.context))
        self.assertIsNone(self.layer.get_tile(6, 5))
        self.assertEqual(self.layer.get_tile(5, 5).properties, original.properties)
        after = self.snapshot()
        self.assertTrue(self.project.is_modified)
        self.assertTrue(self.history.undo())
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.history.redo())
        self.assertEqual(self.snapshot(), after)
        self.assertTrue(self.tool.paste_at(5, 7, self.context))
        self.assertEqual(self.layer.get_tile(7, 7).asset_id, "b")
        self.tool.pasting = False
        self.tool.cut_selection(self.context)
        self.assertIsNone(self.layer.get_tile(5, 7))
        self.assertTrue(self.history.undo())
        self.assertIsNotNone(self.layer.get_tile(5, 7))
        self.assertTrue(self.history.redo())
        self.assertIsNone(self.layer.get_tile(5, 7))
        self.assertTrue(self.history.undo())
        before_move = self.snapshot()
        self.assertTrue(self.tool.move_selection(-2, 0, self.context))
        self.assertEqual(self.layer.get_tile(3, 7).asset_id, "asset")
        self.assertTrue(self.history.undo())
        self.assertEqual(self.snapshot(), before_move)
        self.assertTrue(self.history.redo())
        self.assertIsNotNone(self.layer.get_tile(3, 7))

    def test_rejected_operations_and_cancellation(self):
        self.tile(1, 1)
        self.select((1, 1), (2, 2))
        before = self.snapshot()
        self.assertFalse(self.tool.move_selection(-2, 0, self.context))
        self.tool.copy_selection(self.context)
        self.tool.start_paste(self.context)
        self.assertFalse(self.tool.paste_at(11, 11, self.context))
        self.tool.cancel(self.context)
        self.assertFalse(self.tool.pasting)
        self.layer.locked = True
        self.tool.cut_selection(self.context)
        self.tool.delete_selection(self.context)
        self.assertFalse(self.tool.move_selection(1, 0, self.context))
        self.assertFalse(self.tool.paste_at(3, 3, self.context))
        self.layer.locked = False
        self.layer.visible = False
        self.tool.delete_selection(self.context)
        self.assertFalse(self.tool.paste_at(3, 3, self.context))
        self.layer.visible = True
        group = self.project.add_group("locked")
        self.layer.group_id = group.id
        group.locked = True
        self.project.set_active_layer(self.layer.id)
        self.tool.delete_selection(self.context)
        self.assertFalse(self.tool.paste_at(3, 3, self.context))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.history.undo_stack), 0)

    def test_move_empty_area_does_not_erase_target(self):
        self.tile(4, 4)
        self.select((1, 1), (2, 2))
        before = self.snapshot()
        self.assertFalse(self.tool.move_selection(3, 3, self.context))
        self.assertEqual(self.snapshot(), before)

    def test_tile_free_position_and_history_after_lock(self):
        item = self.tile(1, 1)
        item.free_x, item.free_y = 33, 35
        self.select((1, 1), (1, 1))
        self.assertTrue(self.tool.move_selection(2, 1, self.context))
        self.assertEqual((self.layer.get_tile(3, 2).free_x, self.layer.get_tile(3, 2).free_y), (97, 67))
        self.layer.locked = True
        self.assertTrue(self.history.undo())
        self.assertTrue(self.history.redo())
        self.assertEqual((self.layer.get_tile(3, 2).free_x, self.layer.get_tile(3, 2).free_y), (97, 67))

    def test_large_map_selection_can_render(self):
        project = Project(map_width=1000, map_height=1000)
        canvas = MapCanvas(project, RenderEngine(self.assets), self.assets, HistoryManager())
        tool = SelectTool()
        canvas.set_tool(tool)
        tool.select_all(canvas.tool_context)
        canvas.resize(400, 300)
        canvas.show()
        self.app.processEvents()
        self.assertFalse(canvas.grab().isNull())
        self.assertEqual(tool.region.rectCount(), 1)
        canvas.close()

    def test_fill_delete_and_layer_ownership(self):
        self.select((1, 1), (2, 2))
        self.context.selected_asset = SelectedSubTile(
            asset_id="asset", col=0, row=0, sub_x=0, sub_y=0, sub_w=32, sub_h=32
        )
        self.assertTrue(self.tool.fill_selection(self.context))
        filled = self.snapshot()
        self.assertEqual(len(filled), 4)
        self.assertTrue(self.history.undo())
        self.assertEqual(self.snapshot(), {})
        self.assertTrue(self.history.redo())
        self.assertEqual(self.snapshot(), filled)
        other = self.project.add_layer("other")
        self.context.active_layer = other
        self.tool.delete_selection(self.context)
        self.assertEqual(self.snapshot(), filled)
        self.context.active_layer = self.layer
        self.project.set_active_layer(self.layer.id)
        self.tool.delete_selection(self.context)
        self.assertEqual(self.snapshot(), {})
        self.assertTrue(self.history.undo())
        self.assertEqual(self.snapshot(), filled)

    def test_cross_map_copy_and_project_save(self):
        self.tile(1, 1)
        self.select((1, 1), (2, 1))
        self.tool.copy_selection(self.context)
        new_map = self.project.add_map("second", width=12, height=12)
        self.context.active_layer = new_map.get_active_layer()
        self.assertTrue(self.tool.start_paste(self.context))
        self.assertTrue(self.tool.paste_at(4, 4, self.context))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "project.tmmap")
            self.assertTrue(ProjectIO.save_project(self.project, self.assets, path))
            loaded = ProjectIO.load_project(path, AssetManager())
            self.assertEqual(loaded.get_active_layer().get_tile(4, 4).properties["nested"]["variant"], 4)

    def test_real_canvas_mouse_and_escape(self):
        canvas = MapCanvas(self.project, RenderEngine(self.assets), self.assets, self.history)
        canvas.resize(500, 500)
        canvas.pan_offset = QPointF(20, 20)
        canvas.zoom = 1.0
        canvas.set_tool(self.tool)
        canvas.show()
        canvas.setFocus()
        self.app.processEvents()
        self.addCleanup(canvas.close)
        self.tile(1, 1)

        def point(c, r):
            return QPoint(20 + c * 32 + 10, 20 + r * 32 + 10)

        def drag(a, b):
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=point(*a))
            event = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(point(*b)),
                                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(canvas, event)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=point(*b))

        drag((1, 1), (2, 2))
        self.assertEqual(self.tool.selection_rect.width(), 2)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=point(1, 1))
        move = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(point(4, 3)),
                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(canvas, move)
        self.assertTrue(self.tool.moving_selection)
        QTest.keyClick(canvas, Qt.Key.Key_Escape)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=point(4, 3))
        self.assertIsNotNone(self.layer.get_tile(1, 1))
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=point(1, 1))
        QApplication.sendEvent(canvas, move)
        QApplication.sendEvent(canvas, QFocusEvent(QFocusEvent.Type.FocusOut))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=point(4, 3))
        self.assertIsNotNone(self.layer.get_tile(1, 1))
        canvas.setFocus()
        drag((1, 1), (4, 3))
        self.assertIsNone(self.layer.get_tile(1, 1))
        self.assertIsNotNone(self.layer.get_tile(4, 3))
        QTest.keyClick(canvas, Qt.Key.Key_Escape)
        self.assertIsNone(self.tool.selection_rect)
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=point(1, 1))
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, point(2, 1))
        self.assertEqual(canvas.tool_context.selected_cells, {(1, 1), (2, 1)})
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, point(1, 1))
        self.assertEqual(canvas.tool_context.selected_cells, {(2, 1)})
        canvas.pan_offset = QPointF(60, 75)
        canvas.zoom = 2.0
        self.assertEqual(canvas.screen_to_tile(QPointF(60 + 4 * 64 + 2, 75 + 3 * 64 + 2)), (4, 3))

    def test_main_window_shortcuts_and_text_focus(self):
        script = """
import sys
from PyQt6.QtCore import Qt, QPoint, QPointF, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from tileset_map_maker.models.layer import MapItem
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.core.localization import tr

app = QApplication([])
window = MainWindow()
window.show()
app.processEvents()
canvas = window.canvas
canvas.pan_offset = QPointF(20, 20)
canvas.zoom = 1.0
canvas.setFocus()
layer = window.project.get_active_layer()
layer.set_tile(1, 1, MapItem("asset", 1, 1, properties={"value": 7}))
QTest.keyClick(canvas, Qt.Key.Key_S)
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(68, 68))
QTest.keyClick(canvas, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
assert canvas.tool_context.clipboard_tiles, "copy shortcut"
QTest.keyClick(canvas, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
assert layer.get_tile(1, 1) is None, "cut shortcut"
QTest.keyClick(canvas, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
assert canvas.active_tool.pasting, "paste mode"
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(132, 132))
assert layer.get_tile(3, 3).properties["value"] == 7, "paste data"
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(164, 132))
assert layer.get_tile(4, 3) is not None, "repeat paste"
QTest.keyClick(canvas, Qt.Key.Key_Escape)
assert not canvas.active_tool.pasting, "escape paste"
QTest.keyClick(canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
assert layer.get_tile(4, 3) is None, "undo shortcut"
QTest.keyClick(canvas, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
assert layer.get_tile(4, 3) is not None, "redo shortcut"
QTest.keyClick(canvas, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
assert canvas.active_tool.selection_rect.width() == window.project.map_width, "select all"
search = window.tileset_palette.txt_library_search
search.setText("abc")
search.setFocus()
QTest.keyClick(search, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
QTest.keyClick(search, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
assert search.text() == "", "text field shortcuts"
assert layer.get_tile(3, 3) is not None, "text shortcut must not cut map"
QTest.keyClick(search, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
assert layer.get_tile(4, 3) is not None, "text undo must not change map"
canvas.setFocus()
QTest.keyClick(canvas, Qt.Key.Key_Escape)
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(132, 132))
def choose_duplicate():
    menu = QApplication.activePopupWidget()
    assert menu is not None
    action = next(a for a in menu.actions() if a.text() == tr("selection.duplicate"))
    QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())
QTimer.singleShot(50, choose_duplicate)
QTest.mouseClick(canvas, Qt.MouseButton.RightButton, pos=QPoint(132, 132))
assert canvas.active_tool.pasting, "context menu duplicate"
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(196, 132))
assert layer.get_tile(5, 3) is not None, "duplicate data"
QTest.keyClick(canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
assert layer.get_tile(5, 3) is None, "duplicate undo"
new_map = window.project.add_map("second", width=30, height=20)
window._on_map_switched(new_map.id)
canvas.setFocus()
QTest.keyClick(canvas, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
assert canvas.active_tool.pasting, "clipboard survives map switch"
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
assert new_map.get_active_layer().get_tile(2, 2).properties["value"] == 7, "cross-map paste"
QTest.keyClick(canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
assert new_map.get_active_layer().get_tile(2, 2) is None, "cross-map undo"
new_layer = new_map.get_active_layer()
new_layer.set_tile(1, 1, MapItem("asset", 1, 1))
new_layer.set_tile(2, 1, MapItem("asset", 2, 1))
QTest.keyClick(canvas, Qt.Key.Key_Escape)
QTest.keyClick(canvas, Qt.Key.Key_W)
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(68, 68))
QTest.keyClick(canvas, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
assert new_layer.get_tile(1, 1) is None and new_layer.get_tile(2, 1) is None, "wand cut"
QTest.keyClick(canvas, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(132, 132))
assert new_layer.get_tile(3, 3) is not None and new_layer.get_tile(4, 3) is not None, "wand paste"
window.project.is_modified = False
window.close()
app.processEvents()
"""
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update({"TILESET_CONFIG_DIR": directory, "XDG_CONFIG_HOME": directory,
                        "QT_QPA_PLATFORM": "offscreen", "PYTHONDONTWRITEBYTECODE": "1"})
            result = subprocess.run([sys.executable, "-c", script], env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
