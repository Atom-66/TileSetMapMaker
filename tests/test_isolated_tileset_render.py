import unittest
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QPixmap, QColor, QBrush, QPen
from PyQt6.QtCore import QRectF, QPointF, Qt
from PIL import Image

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget, TilesetCanvas
from tileset_map_maker.ui.properties_panel import create_checkerboard_preview


class TestIsolatedTilesetRender(unittest.TestCase):
    """
    Isolated rendering tests A through F on authentic tileset PNG graphics.
    Guarantees no black box, no brush clipping, and accurate cell slicing and preview.
    """

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.real_png_path = os.path.abspath("sample_assets/Terrain/terrain_tileset.png")
        self.assertTrue(os.path.exists(self.real_png_path), f"Sample asset missing: {self.real_png_path}")

        self.asset_manager = AssetManager()
        asset, dup, err = self.asset_manager.import_single_file(
            self.real_png_path,
            force_asset_type=AssetType.TILESET,
        )
        self.assertIsNotNone(asset)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        self.asset = asset
        self.pixmap = self.asset_manager.get_pixmap(asset.id)
        self.assertIsNotNone(self.pixmap)
        self.assertFalse(self.pixmap.isNull())

    def test_A_render_full_png_untouched(self):
        """Test A: Display full original PNG without slicing. Verify real pixels are rendered."""
        img = QImage(self.asset.width, self.asset.height, QImage.Format.Format_ARGB32)
        img.fill(QColor("#121316"))

        p = QPainter(img)
        p.drawPixmap(0, 0, self.pixmap)
        p.end()

        # Count non-background pixels
        non_bg_count = sum(
            1
            for y in range(img.height())
            for x in range(img.width())
            if img.pixelColor(x, y).name() != "#121316"
        )
        self.assertEqual(non_bg_count, self.asset.width * self.asset.height)
        # Spot check specific color from the asset: #808080 or #696969
        has_gray = any(
            img.pixelColor(x, y).name() in ("#808080", "#696969", "#a0a0a0")
            for y in range(img.height())
            for x in range(img.width())
        )
        self.assertTrue(has_gray, "Authentic pixel colors must be visible")

    def test_B_render_png_with_grid_overlay(self):
        """Test B: Display same PNG with regular grid overlay. Grid must not overwrite graphics with dark brush."""
        img = QImage(self.asset.width, self.asset.height, QImage.Format.Format_ARGB32)
        img.fill(QColor("#121316"))

        cfg = self.asset.tileset_config
        grid = cfg.compute_grid(self.asset.width, self.asset.height)

        p = QPainter(img)
        p.drawPixmap(0, 0, self.pixmap)
        # Render grid lines with explicit NoBrush
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 55)))
        for c in range(grid["cols"]):
            for r in range(grid["rows"]):
                tx, ty, tw, th = cfg.get_tile_rect(c, r)
                p.drawRect(QRectF(tx, ty, tw, th))
        p.end()

        # Ensure authentic tileset colors are still present inside cell (10, 10)
        c = img.pixelColor(10, 10).name()
        self.assertNotIn(c, ["#121316", "#26262e", "#000000"], "Tile graphics must not be covered by dark brush")

    def test_C_render_single_sliced_tile(self):
        """Test C: Extract and render one cut tile (32x32)."""
        cfg = self.asset.tileset_config
        tx, ty, tw, th = cfg.get_tile_rect(0, 0)
        tile_pixmap = self.pixmap.copy(tx, ty, tw, th)

        self.assertFalse(tile_pixmap.isNull())
        self.assertEqual(tile_pixmap.width(), 32)
        self.assertEqual(tile_pixmap.height(), 32)

        # Render onto a test image
        canvas = QImage(32, 32, QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap(0, 0, tile_pixmap)
        p.end()

        # Check that tile contains pixels
        non_transparent = sum(
            1 for y in range(32) for x in range(32) if canvas.pixelColor(x, y).alpha() > 0
        )
        self.assertEqual(non_transparent, 32 * 32)

    def test_D_render_multiple_sliced_tiles_side_by_side(self):
        """Test D: Render several cut tiles side by side."""
        cfg = self.asset.tileset_config
        t1 = self.pixmap.copy(*cfg.get_tile_rect(0, 0))
        t2 = self.pixmap.copy(*cfg.get_tile_rect(1, 0))

        canvas = QImage(64, 32, QImage.Format.Format_ARGB32)
        p = QPainter(canvas)
        p.drawPixmap(0, 0, t1)
        p.drawPixmap(32, 0, t2)
        p.end()

        # Both tiles must be drawn
        self.assertTrue(canvas.pixelColor(16, 16).alpha() > 0)
        self.assertTrue(canvas.pixelColor(48, 16).alpha() > 0)

    def test_E_render_entire_sliced_tileset_cell_by_cell(self):
        """Test E: Reconstruct full sheet by drawing each individual tile cell."""
        cfg = self.asset.tileset_config
        grid = cfg.compute_grid(self.asset.width, self.asset.height)

        canvas = QImage(self.asset.width, self.asset.height, QImage.Format.Format_ARGB32)
        p = QPainter(canvas)
        for c in range(grid["cols"]):
            for r in range(grid["rows"]):
                tx, ty, tw, th = cfg.get_tile_rect(c, r)
                cell_pix = self.pixmap.copy(tx, ty, tw, th)
                p.drawPixmap(tx, ty, cell_pix)
        p.end()

        # Pixel at (5, 5) and (40, 5) must match the source pixmap
        src_img = self.pixmap.toImage()
        self.assertEqual(canvas.pixelColor(5, 5), src_img.pixelColor(5, 5))
        self.assertEqual(canvas.pixelColor(40, 5), src_img.pixelColor(40, 5))

    def test_F_selection_preview_and_widget_rendering(self):
        """Test F: Select tile fragment and verify authentic graphics in TilesetCanvas and preview."""
        palette = TilesetPaletteWidget(self.asset_manager)
        palette.resize(350, 450)
        palette.show()
        self.app.processEvents()

        # Set active asset and select single tile cell (col 0, row 0)
        sub_tile = SelectedSubTile(
            asset_id=self.asset.id,
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
        palette.set_active_asset(self.asset, sub_tile)
        self.app.processEvents()

        # Grab canvas output
        grabbed = palette.canvas.grab()
        img = grabbed.toImage()

        # Ensure authentic tileset colors are present (cell 1, 0 is unselected and untouched)
        colors = set(img.pixelColor(x, y).name() for x in range(img.width()) for y in range(img.height()))
        authentic_found = any(c in colors for c in ("#808080", "#696969", "#a0a0a0", "#8b4513", "#f4a460", "#eed6af"))
        self.assertTrue(authentic_found, f"Authentic colors must be in canvas grab. Found: {list(colors)[:10]}")

        # Check preview thumbnail
        thumb_pix = palette.preview_thumb.pixmap()
        self.assertIsNotNone(thumb_pix)
        self.assertFalse(thumb_pix.isNull())

        # Check checkerboard preview function
        cropped = self.pixmap.copy(0, 0, 64, 64)
        checker_prev = create_checkerboard_preview(cropped, 120, 120)
        self.assertFalse(checker_prev.isNull())
        palette.close()


if __name__ == "__main__":
    unittest.main()
