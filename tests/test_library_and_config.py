import os
import shutil
import tempfile
import unittest
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QApplication
from PIL import Image

from tileset_map_maker.models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from tileset_map_maker.models.category import CategoryTree, CategoryNode
from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.config_manager import ConfigManager
from tileset_map_maker.ui.tileset_palette_widget import TilesetPaletteWidget, TilesetTreeWidget, TilesetCanvas
from tileset_map_maker.ui.dialogs.preferences_dialog import PreferencesDialog


class TestTilesetLibraryAndConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="tmm_test_lib_")
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        self.config_manager = ConfigManager(custom_config_path=self.config_file)
        self.asset_manager = AssetManager()

        # Create dummy PNG tilesets
        self.sample_png = os.path.join(self.temp_dir, "grass_sheet.png")
        img = Image.new("RGBA", (128, 128), color=(34, 139, 34, 255))
        img.save(self.sample_png)

        self.sample_png2 = os.path.join(self.temp_dir, "dungeon_sheet.png")
        img2 = Image.new("RGBA", (96, 64), color=(80, 80, 80, 255))
        img2.save(self.sample_png2)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_no_tabs_above_preview(self):
        """1. Ensure no visual QTabBar exists in TilesetPaletteWidget top section."""
        palette = TilesetPaletteWidget(self.asset_manager, config_manager=self.config_manager)
        
        # Check top_widget layout: only top_header (QLabel + QToolButtons), canvas, and info bar
        top_layout = palette.top_widget.layout()
        for i in range(top_layout.count()):
            w = top_layout.itemAt(i).widget()
            if w:
                from PyQt6.QtWidgets import QTabBar
                self.assertNotIsInstance(w, QTabBar, "Visual QTabBar must NOT exist above preview!")
        
        # Verify title label exists in header
        self.assertTrue(hasattr(palette, "lbl_active_title"))
        self.assertIn("Brak wyboru", palette.lbl_active_title.text())

    def test_02_library_tree_widget_hierarchy(self):
        """2. Tree widget displays folders, subfolders and tilesets with icons and stats."""
        # Create folder structure
        self.asset_manager.category_tree.add_category_path("Środowisko/Zimowe")
        asset, is_dup, err = self.asset_manager.import_single_file(
            self.sample_png,
            target_category_path="Środowisko/Zimowe",
            force_asset_type=AssetType.TILESET,
        )
        self.assertIsNotNone(asset)
        asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)

        palette = TilesetPaletteWidget(self.asset_manager, config_manager=self.config_manager)
        palette.refresh_tilesets()

        # Check tree contains folder
        tree = palette.tree
        self.assertGreaterEqual(tree.topLevelItemCount(), 1)
        root_folder = tree.topLevelItem(0)
        self.assertEqual(root_folder.data(0, Qt.ItemDataRole.UserRole), "folder")
        self.assertIn("Środowisko", root_folder.text(0))

        # Check subfolder
        self.assertGreaterEqual(root_folder.childCount(), 1)
        sub_folder = root_folder.child(0)
        self.assertEqual(sub_folder.data(0, Qt.ItemDataRole.UserRole), "folder")
        self.assertIn("Zimowe", sub_folder.text(0))

        # Check tileset item under subfolder
        self.assertGreaterEqual(sub_folder.childCount(), 1)
        t_item = sub_folder.child(0)
        self.assertEqual(t_item.data(0, Qt.ItemDataRole.UserRole), "tileset")
        self.assertEqual(t_item.data(0, Qt.ItemDataRole.UserRole + 1), asset.id)
        self.assertIn("grass_sheet", t_item.text(0))
        self.assertIn("32×32 px", t_item.text(0))

    def test_03_selecting_tileset_in_tree_updates_preview_immediately(self):
        """3. Selecting a tileset item in the tree immediately updates top preview."""
        asset1, _, _ = self.asset_manager.import_single_file(self.sample_png, force_asset_type=AssetType.TILESET)
        asset2, _, _ = self.asset_manager.import_single_file(self.sample_png2, force_asset_type=AssetType.TILESET)
        asset1.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        asset2.tileset_config = TilesetConfig(tile_width=48, tile_height=32)

        palette = TilesetPaletteWidget(self.asset_manager, config_manager=self.config_manager)
        palette.refresh_tilesets()

        # Select asset2
        palette.set_active_asset(asset2)
        self.assertEqual(palette.active_asset_id, asset2.id)
        self.assertEqual(palette.canvas.current_asset.id, asset2.id)
        self.assertIn("dungeon_sheet", palette.lbl_active_title.text())

        # Select asset1
        palette.set_active_asset(asset1)
        self.assertEqual(palette.active_asset_id, asset1.id)
        self.assertEqual(palette.canvas.current_asset.id, asset1.id)
        self.assertIn("grass_sheet", palette.lbl_active_title.text())

    def test_04_folder_creation_and_renaming(self):
        """4. Category folders can be created and renamed."""
        node = self.asset_manager.category_tree.add_category_path("Architektura/Zamki")
        self.assertIsNotNone(node)
        self.assertEqual(node.path, "Architektura/Zamki")

        # Rename category
        renamed = self.asset_manager.rename_category("Architektura/Zamki", "Pałace")
        self.assertEqual(renamed, "Architektura/Pałace")
        self.assertIsNotNone(self.asset_manager.category_tree.get_node("Architektura/Pałace"))
        self.assertIsNone(self.asset_manager.category_tree.get_node("Architektura/Zamki"))

    def test_05_moving_tileset_between_folders(self):
        """5. Moving tilesets between folders updates asset category path and tree nodes."""
        self.asset_manager.category_tree.add_category_path("FolderA")
        self.asset_manager.category_tree.add_category_path("FolderB")

        asset, _, _ = self.asset_manager.import_single_file(
            self.sample_png,
            target_category_path="FolderA",
            force_asset_type=AssetType.TILESET,
        )
        self.assertEqual(asset.category_path, "FolderA")
        node_a = self.asset_manager.category_tree.get_node("FolderA")
        self.assertIn(asset.id, node_a.asset_ids)

        # Move to FolderB
        ok = self.asset_manager.move_asset(asset.id, "FolderB")
        self.assertTrue(ok)
        self.assertEqual(asset.category_path, "FolderB")
        self.assertNotIn(asset.id, node_a.asset_ids)
        node_b = self.asset_manager.category_tree.get_node("FolderB")
        self.assertIn(asset.id, node_b.asset_ids)

    def test_06_safe_deletion_never_touches_disk_files(self):
        """6. Deleting assets or folders from library never modifies or deletes disk files."""
        asset, _, _ = self.asset_manager.import_single_file(
            self.sample_png,
            target_category_path="KatalogTest",
            force_asset_type=AssetType.TILESET,
        )
        self.assertTrue(os.path.exists(self.sample_png))

        # Delete asset
        self.asset_manager.remove_asset(asset.id)
        self.assertNotIn(asset.id, self.asset_manager.assets)
        self.assertTrue(os.path.exists(self.sample_png), "Disk file must NOT be deleted!")

        # Re-import and delete folder
        asset2, _, _ = self.asset_manager.import_single_file(
            self.sample_png,
            target_category_path="KatalogTest",
            force_asset_type=AssetType.TILESET,
        )
        self.asset_manager.delete_category("KatalogTest", delete_assets=True)
        self.assertIsNone(self.asset_manager.category_tree.get_node("KatalogTest"))
        self.assertTrue(os.path.exists(self.sample_png), "Disk file must NOT be deleted!")

    def test_07_recursive_folder_import_with_subdirectories(self):
        """7. Recursive folder import mirrors disk directory hierarchy and ignores non-images."""
        # Build nested directory structure on disk:
        # root_dir/
        #   img_root.png
        #   readme.txt (should be skipped!)
        #   Środowisko/
        #     Drzewa/
        #       tree.png
        #       invalid.dat (should be skipped!)
        import_root = os.path.join(self.temp_dir, "DirToImport")
        sub_dir = os.path.join(import_root, "Środowisko", "Drzewa")
        os.makedirs(sub_dir, exist_ok=True)

        Image.new("RGBA", (32, 32), (0, 255, 0, 255)).save(os.path.join(import_root, "img_root.png"))
        Image.new("RGBA", (64, 64), (0, 128, 0, 255)).save(os.path.join(sub_dir, "tree.png"))
        with open(os.path.join(import_root, "readme.txt"), "w") as f:
            f.write("text file")
        with open(os.path.join(sub_dir, "invalid.dat"), "w") as f:
            f.write("binary data")

        # Import folder
        default_cfg = TilesetConfig(tile_width=32, tile_height=32)
        res = self.asset_manager.import_folder(
            import_root,
            target_category_path="MojePakiety",
            force_asset_type=AssetType.TILESET,
            default_tileset_config=default_cfg,
        )

        self.assertEqual(res["imported_count"], 2)
        self.assertEqual(res["skipped_count"], 2)
        self.assertEqual(res["duplicates_count"], 0)
        self.assertEqual(res["error_count"], 0)

        # Verify category hierarchy was mirrored
        node_tree = self.asset_manager.category_tree.get_node("MojePakiety/DirToImport/Środowisko/Drzewa")
        self.assertIsNotNone(node_tree)
        self.assertEqual(len(node_tree.asset_ids), 1)

    def test_08_global_import_settings_persistence(self):
        """8. Global import settings can be saved and retrieved from ConfigManager."""
        self.config_manager.set_import_settings(
            tile_width=48,
            tile_height=48,
            margin_x=4,
            margin_y=4,
            spacing_x=2,
            spacing_y=2,
            skip_dialog_on_single=True,
        )

        # Reload config from disk
        reloaded = ConfigManager(custom_config_path=self.config_file)
        cfg = reloaded.get_import_settings()
        self.assertEqual(cfg["default_tile_width"], 48)
        self.assertEqual(cfg["default_tile_height"], 48)
        self.assertEqual(cfg["default_margin_x"], 4)
        self.assertEqual(cfg["default_margin_y"], 4)
        self.assertEqual(cfg["default_spacing_x"], 2)
        self.assertEqual(cfg["default_spacing_y"], 2)
        self.assertTrue(cfg["skip_dialog_on_single"])

    def test_09_full_tileset_library_persistence_and_restoration(self):
        """9. Complete tileset library, folders, configurations, and active tileset are restored."""
        # Setup assets in categories
        self.asset_manager.category_tree.add_category_path("Świat/Lasy")
        asset1, _, _ = self.asset_manager.import_single_file(
            self.sample_png, target_category_path="Świat/Lasy", force_asset_type=AssetType.TILESET
        )
        asset1.tileset_config = TilesetConfig(tile_width=16, tile_height=16, margin_x=1, spacing_x=2)

        asset2, _, _ = self.asset_manager.import_single_file(
            self.sample_png2, target_category_path="Świat", force_asset_type=AssetType.TILESET
        )
        asset2.tileset_config = TilesetConfig(tile_width=48, tile_height=32)

        # Save library to config
        self.config_manager.save_tileset_library(
            self.asset_manager,
            active_asset_id=asset1.id,
            expanded_folders=["Świat", "Świat/Lasy"],
        )

        # Create a fresh AssetManager and restore library
        fresh_mgr = AssetManager()
        self.assertEqual(len(fresh_mgr.assets), 0)

        restored_active_id, expanded = self.config_manager.restore_tileset_library(fresh_mgr)
        self.assertEqual(restored_active_id, asset1.id)
        self.assertEqual(len(fresh_mgr.assets), 2)
        self.assertIn("Świat", expanded)
        self.assertIn("Świat/Lasy", expanded)

        # Verify restored asset configurations
        restored_a1 = fresh_mgr.get_asset(asset1.id)
        self.assertIsNotNone(restored_a1)
        self.assertEqual(restored_a1.tileset_config.tile_width, 16)
        self.assertEqual(restored_a1.tileset_config.margin_x, 1)
        self.assertEqual(restored_a1.tileset_config.spacing_x, 2)
        self.assertEqual(restored_a1.category_path, "Świat/Lasy")

        restored_a2 = fresh_mgr.get_asset(asset2.id)
        self.assertIsNotNone(restored_a2)
        self.assertEqual(restored_a2.tileset_config.tile_width, 48)
        self.assertEqual(restored_a2.tileset_config.tile_height, 32)
        self.assertEqual(restored_a2.category_path, "Świat")

    def test_10_preferences_dialog_tileset_import_tab(self):
        """10. PreferencesDialog contains Import tab that modifies and saves global import settings."""
        dlg = PreferencesDialog()
        dlg.config_manager = self.config_manager

        # Tab 4 is Import tab
        self.assertEqual(dlg.tab_widget.tabText(3), "📥 Import Tilesetów")

        # Set values
        dlg.spin_imp_width.setValue(64)
        dlg.spin_imp_height.setValue(64)
        dlg.spin_imp_margin_x.setValue(8)
        dlg.spin_imp_spacing_x.setValue(4)
        dlg.chk_imp_skip_single.setChecked(True)

        dlg._save_and_accept()

        # Check config_manager has updated values
        cfg = self.config_manager.get_import_settings()
        self.assertEqual(cfg["default_tile_width"], 64)
        self.assertEqual(cfg["default_tile_height"], 64)
        self.assertEqual(cfg["default_margin_x"], 8)
        self.assertEqual(cfg["default_spacing_x"], 4)
        self.assertTrue(cfg["skip_dialog_on_single"])

    def test_11_widget_import_folder_from_path_no_crash(self):
        """11. Ensure palette.import_folder_from_path executes without KeyError."""
        import_root = os.path.join(self.temp_dir, "FolderUiTest")
        os.makedirs(import_root, exist_ok=True)
        Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(os.path.join(import_root, "tile.png"))

        palette = TilesetPaletteWidget(self.asset_manager, config_manager=self.config_manager)
        # Monkey patch QMessageBox.information so it doesn't block GUI in tests
        from PyQt6.QtWidgets import QMessageBox
        original_info = QMessageBox.information
        QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
        try:
            palette.import_folder_from_path(import_root, target_category="Pakiety")
        finally:
            QMessageBox.information = original_info

        # Check it was imported
        self.assertGreaterEqual(len(self.asset_manager.assets), 1)


if __name__ == "__main__":
    unittest.main()
