import os
import sys
import tempfile
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QColor

APP = QApplication.instance() or QApplication(sys.argv)

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.layer import MapItem, ItemType
from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.autotile_engine import AutoTileEngine
from tileset_map_maker.core.render_engine import RenderEngine, RenderOptions
from tileset_map_maker.core.history import HistoryManager
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.rpg_autotile import (
    RPGAutotile,
    SelectedAutotile,
    CANONICAL_47_MASKS,
    create_rpg_autotile_from_tile,
)
from tileset_map_maker.core.tools.brush import BrushTool
from tileset_map_maker.core.tools.eraser import EraserTool
from tileset_map_maker.ui.main_window import MainWindow
from tileset_map_maker.ui.dialogs.path_generator_dialog import PathGeneratorDialog


class TestPathsNoBlackTilesRegression(unittest.TestCase):
    """
    End-to-end verification of the critical Paths bug fix:
    Ensures painting Paths NEVER deletes existing tiles or produces black/empty cells,
    renders real synthesized textures for all 47 variants, supports Undo/Redo and Save/Load,
    and aborts safely on invalid autotile configurations.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sheet_path = os.path.join(self.temp_dir.name, "terrain_sheet.png")
        # Create a 128x128 tileset (4x4 tiles of 32x32):
        # (0,0) = Green grass (#22aa33)
        # (1,0) = Sandy/tan path (#d4a857)
        sheet = QImage(128, 128, QImage.Format.Format_ARGB32)
        sheet.fill(QColor(0, 0, 0, 0))
        p = QPainter(sheet)
        p.fillRect(0, 0, 32, 32, QColor(34, 170, 51, 255))     # Grass tile at (0,0)
        p.fillRect(32, 0, 32, 32, QColor(212, 168, 87, 255))   # Sand path tile at (1,0)
        p.fillRect(64, 0, 32, 32, QColor(120, 110, 100, 255))  # Stone tile at (2,0)
        p.end()
        self.assertTrue(sheet.save(self.sheet_path))

        cfg = ConfigManager(os.path.join(self.temp_dir.name, "test_cfg.json"))
        self.win = MainWindow(config_manager=cfg)
        self.win.canvas.tool_context.brush_settings.size = 1
        self.asset, _, err = self.win.asset_manager.import_single_file(
            self.sheet_path, force_asset_type=AssetType.TILESET
        )
        self.assertIsNotNone(self.asset, f"Import failed: {err}")
        self.asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        # Fill base layer with grass so any black/empty cell is immediately detectable
        layer = self.win.project.get_active_layer()
        for r in range(10):
            for c in range(10):
                layer.set_tile(
                    c,
                    r,
                    MapItem(
                        asset_id=self.asset.id,
                        col=c,
                        row=r,
                        item_type=ItemType.TILE,
                        source_x=0,
                        source_y=0,
                        source_w=32,
                        source_h=32,
                        dest_w=32,
                        dest_h=32,
                    ),
                )

    def tearDown(self):
        self.win.close()
        self.temp_dir.cleanup()

    def _create_and_accept_path_via_dialog(self) -> RPGAutotile:
        dlg = PathGeneratorDialog(
            self.win.autotile_engine,
            self.win.asset_manager,
            self.win,
            initial_asset_id=self.asset.id,
            initial_col=1,
            initial_row=0,
        )
        dlg._on_tile_clicked(1, 0)
        self.assertIsNotNone(dlg.current_autotile)
        dlg._accept_and_paint()
        at = dlg.current_autotile
        dlg.close()
        return at

    def _render_map_to_image(self, project=None, render_engine=None) -> QImage:
        proj = project or self.win.project
        re = render_engine or self.win.render_engine
        img = QImage(320, 320, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 255))  # Pure black background to expose any missing draw!
        painter = QPainter(img)
        opts = RenderOptions(show_grid=False, show_selection=False, render_checkerboard=False)
        re.render(painter, proj, opts)
        painter.end()
        return img

    def _cell_center_color(self, img: QImage, col: int, row: int) -> QColor:
        return img.pixelColor(col * 32 + 16, row * 32 + 16)

    def _assert_cell_is_path_not_black(self, img: QImage, col: int, row: int):
        c = self._cell_center_color(img, col, row)
        # Path tile is sandy/tan (~212, 168, 87). Must NOT be black (0,0,0) or dark canvas bg!
        self.assertGreater(
            c.red(),
            140,
            f"Cell ({col},{row}) rendered black/wrong color: ({c.red()},{c.green()},{c.blue()})",
        )
        self.assertGreater(
            c.green(),
            100,
            f"Cell ({col},{row}) rendered wrong green channel: ({c.red()},{c.green()},{c.blue()})",
        )

    def _assert_cell_is_grass(self, img: QImage, col: int, row: int):
        c = self._cell_center_color(img, col, row)
        self.assertEqual((c.red(), c.green(), c.blue()), (34, 170, 51))

    def test_01_all_47_variants_have_visible_non_empty_pixels(self):
        """9. Poprawność tekstur wszystkich 47 wygenerowanych wariantów."""
        at = self._create_and_accept_path_via_dialog()
        pm = self.win.asset_manager.get_pixmap(at.id)
        self.assertIsNotNone(pm, "Autotile must be registered in AssetManager!")
        self.assertFalse(pm.isNull())
        atlas_img = pm.toImage()
        for mask in CANONICAL_47_MASKS:
            sx, sy, sw, sh = at.get_tile_slice_for_mask(mask, 0, 0)
            self.assertEqual((sw, sh), (32, 32))
            center = atlas_img.pixelColor(sx + 16, sy + 16)
            self.assertGreater(center.alpha(), 200, f"Mask {mask} center is transparent!")
            self.assertGreater(center.red(), 140, f"Mask {mask} center is black/invalid!")

    def test_02_paint_single_horizontal_vertical_corners_wide_and_join(self):
        """1-6 & 8 & 12. Malowanie pojedynczego pola, poziomej, pionowej, zakrętów, poszerzania, łączenia."""
        at = self._create_and_accept_path_via_dialog()
        ctx = self.win.canvas.tool_context
        brush = BrushTool()

        # 1. Single cell (2, 2)
        brush.on_press(2, 2, ctx)
        brush.on_release(2, 2, ctx)
        img = self._render_map_to_image()
        self._assert_cell_is_path_not_black(img, 2, 2)
        self._assert_cell_is_grass(img, 0, 0)
        self._assert_cell_is_grass(img, 5, 5)

        # 2. Horizontal path (2,2) -> (5,2) + 3. Vertical (5,2) -> (5,5) + 4. Corner at (5,2)
        brush.on_press(3, 2, ctx)
        brush.on_drag(4, 2, ctx)
        brush.on_drag(5, 2, ctx)
        brush.on_drag(5, 3, ctx)
        brush.on_drag(5, 4, ctx)
        brush.on_drag(5, 5, ctx)
        brush.on_release(5, 5, ctx)

        # 5 & 6. Widen & join at (3,3), (4,3)
        brush.on_press(3, 3, ctx)
        brush.on_drag(4, 3, ctx)
        brush.on_release(4, 3, ctx)

        img = self._render_map_to_image()
        painted = [(2, 2), (3, 2), (4, 2), (5, 2), (5, 3), (5, 4), (5, 5), (3, 3), (4, 3)]
        for c, r in painted:
            self._assert_cell_is_path_not_black(img, c, r)
            tile = self.win.project.get_active_layer().get_tile(c, r)
            self.assertEqual(tile.asset_id, at.id)
            self.assertTrue(tile.is_auto_tiled)

        # Verify surrounding grass tiles were NEVER touched or turned black
        for c, r in [(0, 0), (1, 1), (6, 6), (9, 9)]:
            self._assert_cell_is_grass(img, c, r)

        # Verify corner (5,2) and interior/edge slices actually differ from isolated (0) slice
        iso_slice = at.get_tile_slice_for_mask(0, 0, 0)
        corner_tile = self.win.project.get_active_layer().get_tile(5, 2)
        self.assertNotEqual(
            (corner_tile.source_x, corner_tile.source_y, corner_tile.source_w, corner_tile.source_h),
            iso_slice,
        )

    def test_03_eraser_removes_fragment_and_updates_neighbors(self):
        """7. Usuwanie fragmentów gumką i aktualizacja sąsiadów."""
        at = self._create_and_accept_path_via_dialog()
        ctx = self.win.canvas.tool_context
        brush = BrushTool()
        brush.on_press(2, 2, ctx)
        brush.on_drag(3, 2, ctx)
        brush.on_drag(4, 2, ctx)
        brush.on_release(4, 2, ctx)

        layer = self.win.project.get_active_layer()
        before_left = (layer.get_tile(2, 2).source_x, layer.get_tile(2, 2).source_y)

        eraser = EraserTool()
        eraser.on_press(3, 2, ctx)
        eraser.on_release(3, 2, ctx)

        self.assertIsNone(layer.get_tile(3, 2))
        after_left = (layer.get_tile(2, 2).source_x, layer.get_tile(2, 2).source_y)
        self.assertNotEqual(before_left, after_left, "Neighbor (2,2) must update after erasing (3,2)!")

        # Remaining endpoints still render visibly (not black)
        img = self._render_map_to_image()
        self._assert_cell_is_path_not_black(img, 2, 2)
        self._assert_cell_is_path_not_black(img, 4, 2)

    def test_04_undo_redo_is_atomic_and_restores_exact_tiles(self):
        """10. Undo/Redo przywraca dokładnie poprzednie kafelki i pojedynczy wpis historii."""
        self._create_and_accept_path_via_dialog()
        ctx = self.win.canvas.tool_context
        brush = BrushTool()

        hist = self.win.history_manager
        initial_undo_count = len(hist.undo_stack)

        # Single drag stroke of 4 cells -> MUST be 1 history command
        brush.on_press(1, 1, ctx)
        brush.on_drag(2, 1, ctx)
        brush.on_drag(3, 1, ctx)
        brush.on_drag(4, 1, ctx)
        brush.on_release(4, 1, ctx)

        self.assertEqual(len(hist.undo_stack), initial_undo_count + 1)

        img_painted = self._render_map_to_image()
        for c in (1, 2, 3, 4):
            self._assert_cell_is_path_not_black(img_painted, c, 1)

        # Undo -> restores original green grass tiles!
        self.assertTrue(hist.undo())
        img_undone = self._render_map_to_image()
        for c in (1, 2, 3, 4):
            self._assert_cell_is_grass(img_undone, c, 1)

        # Redo -> restores exact path!
        self.assertTrue(hist.redo())
        img_redone = self._render_map_to_image()
        for c in (1, 2, 3, 4):
            self._assert_cell_is_path_not_black(img_redone, c, 1)

    def test_05_save_and_reload_map_preserves_rendered_path_textures(self):
        """11. Zapis i ponowne otwarcie mapy zachowuje widoczny wygląd ścieżek bez czarnych pól."""
        self._create_and_accept_path_via_dialog()
        ctx = self.win.canvas.tool_context
        brush = BrushTool()
        brush.on_press(2, 4, ctx)
        brush.on_drag(3, 4, ctx)
        brush.on_drag(4, 4, ctx)
        brush.on_release(4, 4, ctx)

        save_path = os.path.join(self.temp_dir.name, "paths_test.tmmap")
        self.assertTrue(
            ProjectIO.save_project(
                self.win.project, self.win.asset_manager, save_path, self.win.autotile_engine
            )
        )

        # Completely fresh AssetManager, AutoTileEngine, and RenderEngine (simulates restart)
        fresh_am = AssetManager()
        fresh_engine = AutoTileEngine(asset_manager=fresh_am)
        fresh_render = RenderEngine(fresh_am, autotile_engine=fresh_engine)
        reloaded = ProjectIO.load_project(save_path, fresh_am, autotile_engine=fresh_engine)
        self.assertIsNotNone(reloaded)

        img = self._render_map_to_image(project=reloaded, render_engine=fresh_render)
        for c in (2, 3, 4):
            self._assert_cell_is_path_not_black(img, c, 4)
        self._assert_cell_is_grass(img, 0, 0)

    def test_06_invalid_autotile_configuration_never_destroys_map_tiles(self):
        """3. Nieprawidłowa konfiguracja Paths nie może usuwać istniejących kafelków ani tworzyć czarnych pól."""
        broken_at = RPGAutotile(
            name="Broken Path",
            terrain_type="broken",
            tile_size=32,
            source_image_path="/nonexistent/path/to/missing_texture.png",
        )
        self.win.autotile_engine.register_rpg_autotile(broken_at)
        ctx = self.win.canvas.tool_context
        ctx.selected_asset = SelectedAutotile(broken_at)
        ctx.brush_settings.selected_autotile = ctx.selected_asset

        hist_before = len(self.win.history_manager.undo_stack)
        brush = BrushTool()
        brush.on_press(3, 3, ctx)
        brush.on_drag(4, 3, ctx)
        brush.on_release(4, 3, ctx)

        # History must NOT have gained a broken entry
        self.assertEqual(len(self.win.history_manager.undo_stack), hist_before)

        # Original grass tiles at (3,3) and (4,3) MUST remain 100% intact!
        img = self._render_map_to_image()
        self._assert_cell_is_grass(img, 3, 3)
        self._assert_cell_is_grass(img, 4, 3)


if __name__ == "__main__":
    unittest.main()
