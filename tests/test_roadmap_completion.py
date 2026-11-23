import os
import unittest
import tempfile
import shutil
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

# Ensure QApplication is initialized for headless tests
app = QApplication.instance()
if not app:
    app = QApplication([])

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.history import HistoryManager, TileBatchCommand
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.wand import WandTool
from tileset_map_maker.core.tools.object_tool import ObjectTool
from tileset_map_maker.core.autosave_manager import AutosaveManager
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.map_canvas import MapCanvas
from tileset_map_maker.ui.minimap_widget import MinimapWidget
from tileset_map_maker.ui.quick_action_menu import QuickActionMenu
from tileset_map_maker.ui.dialogs.preferences_dialog import PreferencesDialog


class TestRoadmapCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="test_roadmap_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.asset_mgr = AssetManager()
        self.project = Project(name="TestProj", map_width=20, map_height=15, tile_size=32)
        self.render_engine = RenderEngine(self.asset_mgr)

    # --- TASK-103: Isolated Undo/Redo per map ---
    def test_task_103_isolated_history_per_map(self):
        win = MainWindow()
        map1_id = win.project.active_map_id
        hist1 = win.get_map_history(map1_id)
        self.assertIs(win.history_manager, hist1)

        # Add second map
        map2 = win.project.add_map("Map2", width=10, height=10, tile_size=32)
        win._on_map_switched(map2.id)
        hist2 = win.get_map_history(map2.id)

        self.assertIsNot(hist1, hist2)
        self.assertIs(win.history_manager, hist2)

        # Record operation on map2
        layer2 = win.project.get_active_layer()
        item = MapItem(asset_id="a1", col=0, row=0, source_x=0, source_y=0, source_w=32, source_h=32)
        cmd = TileBatchCommand(win.project, layer2.id, {(0, 0): (None, item)})
        win.history_manager.push(cmd)

        self.assertTrue(hist2.can_undo())
        self.assertFalse(hist1.can_undo())

        # Switch back to map1
        win._on_map_switched(map1_id)
        self.assertIs(win.history_manager, hist1)
        self.assertFalse(win.history_manager.can_undo())

        win.close()

    # --- TASK-203: Floating HUD Overlay on Canvas ---
    def test_task_203_floating_hud(self):
        canvas = MapCanvas(
            project=self.project,
            render_engine=self.render_engine,
            asset_manager=self.asset_mgr,
            history_manager=HistoryManager(),
        )
        self.assertTrue(canvas.show_hud)
        canvas.cursor_tile_col = 5
        canvas.cursor_tile_row = 8
        canvas.cursor_px_x = 160.0
        canvas.cursor_px_y = 256.0
        # Check paint event executes without crashing
        canvas.resize(400, 300)
        img = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(img)
        canvas.render(painter)
        painter.end()
        self.assertFalse(img.isNull())

    # --- TASK-204: Quick Action Menu ---
    def test_task_204_quick_action_menu(self):
        menu = QuickActionMenu()
        selected = []
        menu.tool_selected.connect(lambda k: selected.append(k))

        menu._on_select("brush")
        self.assertEqual(selected, ["brush"])

        menu._on_select("wand")
        self.assertEqual(selected, ["brush", "wand"])

    # --- TASK-505: Minimap Widget ---
    def test_task_505_minimap_dock_widget(self):
        canvas = MapCanvas(
            project=self.project,
            render_engine=self.render_engine,
            asset_manager=self.asset_mgr,
            history_manager=HistoryManager(),
        )
        minimap = MinimapWidget(self.project, self.render_engine, canvas)
        minimap.resize(200, 160)

        # Trigger navigation to center
        minimap._navigate_to_pos(QPointF(100, 80))
        self.assertTrue(canvas.pan_offset.x() != 0 or canvas.pan_offset.y() != 0)

        # Render minimap to image
        img = QImage(200, 160, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        minimap.render(p)
        p.end()
        self.assertFalse(img.isNull())

    # --- TASK-606: Magic Wand Tool ---
    def test_task_606_magic_wand_tool(self):
        layer = self.project.get_active_layer()
        # Create a 3x3 patch of identical tiles
        item_template = MapItem(asset_id="terrain", col=0, row=0, source_x=0, source_y=0, source_w=32, source_h=32)
        for c in range(2, 5):
            for r in range(2, 5):
                it = item_template.clone()
                it.col = c
                it.row = r
                layer.set_tile(c, r, it)

        # Surrounding tile with different source
        diff_item = MapItem(asset_id="terrain", source_x=32, source_y=0, source_w=32, source_h=32, col=5, row=2)
        layer.set_tile(5, 2, diff_item)

        hist = HistoryManager()
        ctx = ToolContext(self.project, self.asset_mgr, hist, active_layer=layer)

        wand = WandTool()
        wand.on_press(3, 3, ctx)

        # Should select all 9 connected cells
        self.assertEqual(len(wand.selected_cells), 9)
        self.assertIn((2, 2), wand.selected_cells)
        self.assertIn((4, 4), wand.selected_cells)
        self.assertNotIn((5, 2), wand.selected_cells)
        self.assertEqual(wand.selection_rect, QRect(2, 2, 3, 3))

        # Copy selection
        wand.copy_selection(ctx)
        self.assertEqual(len(ctx.clipboard_tiles), 9)

        # Delete selection
        wand.delete_selection(ctx)
        self.assertIsNone(layer.get_tile(3, 3))
        self.assertIsNotNone(layer.get_tile(5, 2))
        self.assertTrue(hist.can_undo())

        # Undo deletion
        hist.undo()
        self.assertIsNotNone(layer.get_tile(3, 3))

    # --- TASK-703: Layer Tree Drag & Drop reordering ---
    def test_task_703_layer_tree_drag_drop_order(self):
        l1 = self.project.layers[0]
        l2 = self.project.add_layer("Layer 2")
        l3 = self.project.add_layer("Layer 3")

        win = MainWindow()
        win.project = self.project
        win.layer_panel.set_project(self.project)

        # Verify initial tree count
        self.assertEqual(win.layer_panel.tree_widget.topLevelItemCount(), 3)
        win.close()

    # --- TASK-704: Layer Blend Modes ---
    def test_task_704_blend_modes(self):
        layer = self.project.get_active_layer()
        self.assertEqual(layer.blend_mode, "normal")

        layer.blend_mode = "multiply"
        d = layer.to_dict()
        self.assertEqual(d["blend_mode"], "multiply")

        restored = Layer.from_dict(d)
        self.assertEqual(restored.blend_mode, "multiply")

    # --- TASK-803 & TASK-804: Object Gizmo & Alignment ---
    def test_task_803_and_804_object_gizmo_and_alignment(self):
        layer = self.project.get_active_layer()
        obj1 = MapItem(item_type=ItemType.OBJECT, asset_id="tree", col=0, row=0, free_x=10.0, free_y=20.0, dest_w=40, dest_h=60)
        obj2 = MapItem(item_type=ItemType.OBJECT, asset_id="rock", col=0, row=0, free_x=100.0, free_y=80.0, dest_w=30, dest_h=30)
        obj3 = MapItem(item_type=ItemType.OBJECT, asset_id="bush", col=0, row=0, free_x=180.0, free_y=40.0, dest_w=20, dest_h=20)
        layer.add_object(obj1)
        layer.add_object(obj2)
        layer.add_object(obj3)

        tool = ObjectTool()
        hist = HistoryManager()
        ctx = ToolContext(self.project, self.asset_mgr, hist, active_layer=layer)

        # Select obj1 and test gizmo handles hit detection
        tool.selected_ids = [obj1.id]
        ctx.selected_object_ids = [obj1.id]

        # Click on rotation knob at top center (center.x=30, top - 16 = 4)
        ctx.cursor_pixel_x = 30.0
        ctx.cursor_pixel_y = 4.0
        tool.on_press(0, 0, ctx)
        self.assertEqual(tool.drag_mode, "rotate")

        # Test multi-object alignment (align left)
        tool.selected_ids = [obj1.id, obj2.id, obj3.id]
        tool.align_selected("left", ctx)
        self.assertEqual(obj1.free_x, 10.0)
        self.assertEqual(obj2.free_x, 10.0)
        self.assertEqual(obj3.free_x, 10.0)
        self.assertTrue(hist.can_undo())

        # Test multi-object distribution
        obj1.free_x = 0.0
        obj2.free_x = 40.0
        obj3.free_x = 200.0
        tool.distribute_selected("horizontal", ctx)
        self.assertEqual(obj1.free_x, 0.0)
        self.assertEqual(obj2.free_x, 100.0)
        self.assertEqual(obj3.free_x, 200.0)

    # --- TASK-1204: Autosave Manager ---
    def test_task_1204_autosave_manager(self):
        auto_mgr = AutosaveManager(self.project, self.asset_mgr, interval_ms=0)
        self.assertFalse(self.project.is_modified)

        # When project is not modified, autosave does nothing
        res = auto_mgr.perform_autosave()
        self.assertIsNone(res)

        # Mark modified
        self.project.is_modified = True
        auto_path = auto_mgr.perform_autosave()
        self.assertIsNotNone(auto_path)
        self.assertTrue(os.path.exists(auto_path))

        # Check recovery available
        recovery = auto_mgr.check_recovery_available()
        self.assertEqual(recovery, auto_path)

        # Cleanup autosave
        auto_mgr.cleanup_autosave()
        self.assertFalse(os.path.exists(auto_path))

    # --- TASK-1301: Preferences Dialog ---
    def test_task_1301_preferences_dialog(self):
        dlg = PreferencesDialog()
        self.assertGreater(dlg.tab_widget.count(), 3)
        self.assertTrue(dlg.chk_show_grid.isChecked())
        dlg.chk_show_hud.setChecked(True)
        dlg._save_and_accept()
        dlg.close()

    # --- TASK-1403: Viewport Render Culling ---
    def test_task_1403_viewport_render_culling(self):
        layer = self.project.get_active_layer()
        # Place tile far away at (15, 12)
        item = MapItem(asset_id="a1", col=15, row=12, source_x=0, source_y=0, source_w=32, source_h=32)
        layer.set_tile(15, 12, item)

        # Render with clip_rect that only includes (0, 0) to (5, 5) tiles -> (0, 0, 160, 160) px
        clip_rect = QRectF(0, 0, 160, 160)
        img = QImage(160, 160, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(img)
        options = RenderOptions(show_grid=False, show_selection=False, render_checkerboard=False)
        self.render_engine.render(painter, self.project, options, clip_rect=clip_rect)
        painter.end()
        self.assertFalse(img.isNull())


if __name__ == "__main__":
    unittest.main()
