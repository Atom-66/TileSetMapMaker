import unittest
import os
import shutil
import tempfile
from PyQt6.QtWidgets import QApplication, QMainWindow, QDockWidget
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PIL import Image

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import Layer, MapItem, ItemType
from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.history import HistoryManager, LayerAddCommand, LayerRemoveCommand, LayerMoveCommand
from tileset_map_maker.core.render_engine import RenderEngine
from tileset_map_maker.core.tools.base import ToolContext
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.core.tools.fill import FillTool
from tileset_map_maker.core.tools.shapes import LineTool, RectTool
from tileset_map_maker.core.tools.wand import WandTool
from tileset_map_maker.core.tools.eyedropper import EyedropperTool
from tileset_map_maker.ui.properties_panel import PropertiesPanel, create_checkerboard_preview
from tileset_map_maker.ui.layer_panel import LayerPanel
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget
from tileset_map_maker.ui.main_window import MainWindow


class TestAuditVerificationSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project = Project(name="AuditProject", map_width=10, map_height=10, tile_size=32)
        self.asset_manager = AssetManager()
        self.history_manager = HistoryManager()

        # Create dummy tileset image (64x64 px -> 2x2 grid of 32x32 tiles)
        self.tileset_path = os.path.join(self.temp_dir, "test_sheet.png")
        img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
        # Draw top-right tile blue
        for y in range(0, 32):
            for x in range(32, 64):
                img.putpixel((x, y), (0, 0, 255, 255))
        img.save(self.tileset_path)

        asset, _, _ = self.asset_manager.import_single_file(self.tileset_path, AssetType.TILESET)
        self.tileset_asset = asset
        self.tileset_asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # ETAP 3: KRYTYCZNA WERYFIKACJA SYSTEMU WARSTW
    # =========================================================================

    def test_layer_addition_execution_and_active_switch(self):
        """Verify layer addition immediately adds to layers list and can be undone."""
        initial_count = len(self.project.layers)
        new_layer = Layer(name="Nowa Warstwa Testowa")
        cmd = LayerAddCommand(self.project, new_layer)
        cmd.execute()
        self.history_manager.push(cmd)

        self.assertEqual(len(self.project.layers), initial_count + 1)
        self.assertEqual(self.project.active_layer_id, new_layer.id)

        # Undo addition
        self.history_manager.undo()
        self.assertEqual(len(self.project.layers), initial_count)
        self.assertIsNone(self.project.get_layer(new_layer.id))

        # Redo addition
        self.history_manager.redo()
        self.assertEqual(len(self.project.layers), initial_count + 1)
        self.assertIsNotNone(self.project.get_layer(new_layer.id))

    def test_layer_deletion_and_active_fallback(self):
        """Verify layer deletion removes layer, updates active layer, and can be undone."""
        layer2 = self.project.add_layer("Warstwa 2")
        self.project.set_active_layer(layer2.id)
        self.assertEqual(self.project.active_layer_id, layer2.id)

        count_before = len(self.project.layers)
        cmd = LayerRemoveCommand(self.project, layer2.id)
        cmd.execute()
        self.history_manager.push(cmd)

        self.assertEqual(len(self.project.layers), count_before - 1)
        self.assertNotEqual(self.project.active_layer_id, layer2.id)
        self.assertIsNotNone(self.project.get_active_layer())

        # Undo removal
        self.history_manager.undo()
        self.assertEqual(len(self.project.layers), count_before)
        self.assertEqual(self.project.active_layer_id, layer2.id)

    def test_layer_move_and_reorder(self):
        """Verify layer reordering updates list position correctly."""
        l1 = self.project.layers[0]
        l2 = self.project.add_layer("Warstwa Do Przesunięcia")
        idx_l2_initial = self.project.get_layer_index(l2.id)

        cmd = LayerMoveCommand(self.project, idx_l2_initial, 0)
        cmd.execute()
        self.history_manager.push(cmd)

        self.assertEqual(self.project.get_layer_index(l2.id), 0)

        # Undo move
        self.history_manager.undo()
        self.assertEqual(self.project.get_layer_index(l2.id), idx_l2_initial)

    def test_locked_layer_blocks_all_editing_tools(self):
        """Ensure locked layers reject painting, erasing, filling, lines, and rects."""
        layer = self.project.get_active_layer()
        layer.locked = True

        sub_tile = SelectedSubTile(
            asset_id=self.tileset_asset.id,
            col=0,
            row=0,
            cols_count=1,
            rows_count=1,
            sub_x=0,
            sub_y=0,
            sub_w=32,
            sub_h=32,
            tile_width=32,
            tile_height=32,
        )

        context = ToolContext(
            project=self.project,
            asset_manager=self.asset_manager,
            history_manager=self.history_manager,
            active_layer=layer,
            selected_asset=sub_tile,
        )

        brush = BrushTool()
        brush.on_press(2, 2, context)
        brush.on_release(2, 2, context)
        self.assertIsNone(layer.get_tile(2, 2), "Brush must not paint on locked layer")
        self.assertEqual(len(brush.get_preview_items(context)), 0, "No ghost preview on locked layer")

        eraser = EraserTool()
        eraser.on_press(2, 2, context)
        eraser.on_release(2, 2, context)

        fill = FillTool()
        fill.on_press(2, 2, context)
        self.assertIsNone(layer.get_tile(2, 2), "Fill must not paint on locked layer")

        line = LineTool()
        line.on_press(0, 0, context)
        line.on_release(3, 3, context)
        self.assertIsNone(layer.get_tile(0, 0), "Line must not paint on locked layer")

        rect = RectTool()
        rect.on_press(1, 1, context)
        rect.on_release(3, 3, context)
        self.assertIsNone(layer.get_tile(1, 1), "Rect must not paint on locked layer")

    def test_invisible_layer_blocks_painting(self):
        """Ensure invisible (hidden) layers reject painting."""
        layer = self.project.get_active_layer()
        layer.visible = False

        sub_tile = SelectedSubTile(
            asset_id=self.tileset_asset.id,
            col=0,
            row=0,
            cols_count=1,
            rows_count=1,
            sub_x=0,
            sub_y=0,
            sub_w=32,
            sub_h=32,
            tile_width=32,
            tile_height=32,
        )

        context = ToolContext(
            project=self.project,
            asset_manager=self.asset_manager,
            history_manager=self.history_manager,
            active_layer=layer,
            selected_asset=sub_tile,
        )

        brush = BrushTool()
        brush.on_press(3, 3, context)
        brush.on_release(3, 3, context)
        self.assertIsNone(layer.get_tile(3, 3), "Brush must not paint on hidden layer")
        self.assertEqual(len(brush.get_preview_items(context)), 0, "No ghost preview on hidden layer")

    # =========================================================================
    # ETAP 4: KRYTYCZNA WERYFIKACJA POCIĘTEGO PODGLĄDU TILESETÓW
    # =========================================================================

    def test_checkerboard_preview_generator(self):
        """Verify checkerboard preview creates valid non-null pixmaps."""
        # Empty pixmap test
        empty_prev = create_checkerboard_preview(None, 120, 120)
        self.assertFalse(empty_prev.isNull())
        self.assertEqual(empty_prev.width(), 120)
        self.assertEqual(empty_prev.height(), 120)

        # Valid sub-pixmap test
        raw_pix = QPixmap(32, 32)
        raw_pix.fill(QColor("red"))
        prev = create_checkerboard_preview(raw_pix, 120, 120)
        self.assertFalse(prev.isNull())
        self.assertEqual(prev.width(), 120)

    def test_properties_panel_sliced_preview(self):
        """Verify PropertiesPanel displays live visual preview of single and multi-tile selections."""
        panel = PropertiesPanel(self.project, self.asset_manager)

        # 1. Single sub-tile selection
        single_sub = SelectedSubTile(
            asset_id=self.tileset_asset.id,
            col=1,
            row=0,
            cols_count=1,
            rows_count=1,
            sub_x=32,
            sub_y=0,
            sub_w=32,
            sub_h=32,
            tile_width=32,
            tile_height=32,
            asset_name="TestSheet",
        )
        panel.set_selected_item(single_sub)

        self.assertIn("Pojedynczy kafelek", panel.lbl_sel_type.text())
        self.assertEqual(panel.lbl_sel_size.text(), "32 × 32 px")
        self.assertFalse(panel.lbl_preview_img.pixmap().isNull())

        # 2. Multi-tile block selection
        multi_sub = SelectedSubTile(
            asset_id=self.tileset_asset.id,
            col=0,
            row=0,
            cols_count=2,
            rows_count=2,
            sub_x=0,
            sub_y=0,
            sub_w=64,
            sub_h=64,
            tile_width=32,
            tile_height=32,
            asset_name="TestSheet",
        )
        panel.set_selected_item(multi_sub)
        self.assertIn("Blok kafelków", panel.lbl_sel_type.text())
        self.assertEqual(panel.lbl_sel_size.text(), "64 × 64 px")
        self.assertFalse(panel.lbl_preview_img.pixmap().isNull())

    def test_tileset_palette_widget_thumb_render(self):
        """Verify TilesetPaletteWidget renders thumbnail of selected subtile."""
        palette = TilesetPaletteWidget(self.asset_manager)
        single_sub = SelectedSubTile(
            asset_id=self.tileset_asset.id,
            col=0,
            row=0,
            cols_count=1,
            rows_count=1,
            sub_x=0,
            sub_y=0,
            sub_w=32,
            sub_h=32,
            tile_width=32,
            tile_height=32,
        )
        palette._render_thumb(self.tileset_asset, single_sub)
        self.assertIsNotNone(palette.preview_thumb.pixmap())
        self.assertFalse(palette.preview_thumb.pixmap().isNull())

    # =========================================================================
    # ETAP 7: DOCKING SYSTEM & WINDOW FEATURES
    # =========================================================================

    def test_main_window_docking_and_features(self):
        """Verify MainWindow has tabbed/nested docking options and movable/floatable docks."""
        win = MainWindow()
        dock_opts = win.dockOptions()
        self.assertTrue(bool(dock_opts & QMainWindow.DockOption.AnimatedDocks))
        self.assertTrue(bool(dock_opts & QMainWindow.DockOption.AllowTabbedDocks))
        self.assertTrue(bool(dock_opts & QMainWindow.DockOption.GroupedDragging))
        self.assertTrue(bool(dock_opts & QMainWindow.DockOption.AllowNestedDocks))

        for dock in [win.tileset_dock, win.right_dock, win.properties_dock, win.history_dock, win.minimap_dock]:
            feats = dock.features()
            self.assertTrue(bool(feats & QDockWidget.DockWidgetFeature.DockWidgetMovable))
            self.assertTrue(bool(feats & QDockWidget.DockWidgetFeature.DockWidgetFloatable))
            self.assertTrue(bool(feats & QDockWidget.DockWidgetFeature.DockWidgetClosable))
        win.close()


if __name__ == "__main__":
    unittest.main()
