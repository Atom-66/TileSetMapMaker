import json
import os
import tempfile
import unittest

from PIL import Image
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.core.asset_manager import AssetManager
from tileset_map_maker.core.external_formats import resolve_safe_asset_path
from tileset_map_maker.core.project_io import ProjectIO
from tileset_map_maker.core.render_engine import RenderEngine
from tileset_map_maker.core.schema import schema_errors
from tileset_map_maker.models.asset import AssetType, TilesetConfig
from tileset_map_maker.models.layer import (
    CollisionObject,
    CollisionShape,
    ItemType,
    MapItem,
)
from tileset_map_maker.models.project import Project


APP = QApplication.instance() or QApplication([])


class TestPhase8Interoperability(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = self.directory.name
        self.image_path = os.path.join(self.base, "terrain.png")
        Image.new("RGBA", (64, 32), (20, 120, 40, 255)).save(
            self.image_path
        )
        self.assets = AssetManager()
        self.asset, _, _ = self.assets.import_single_file(
            self.image_path,
            force_asset_type=AssetType.TILESET,
        )
        self.asset.tileset_config = TilesetConfig(
            tile_width=32, tile_height=32
        )
        self.project = Project(map_width=4, map_height=3, tile_size=32)
        self.layer = self.project.get_active_layer()
        self.layer.name = "Ground"
        self.layer.set_tile(
            1,
            1,
            MapItem(
                self.asset.id,
                1,
                1,
                source_x=32,
                source_y=0,
                source_w=32,
                source_h=32,
                flip_x=True,
            ),
        )
        collision = self.project.add_layer(
            "Gameplay", layer_type="collision"
        )
        collision.add_collision(
            CollisionObject(
                32,
                16,
                64,
                32,
                shape=CollisionShape.ELLIPSE,
                trigger=True,
                blocking=False,
            )
        )
        obj = MapItem(
            self.asset.id,
            2,
            2,
            item_type=ItemType.OBJECT,
            free_x=64,
            free_y=64,
            object_type="portal",
            interaction_label="Wejście",
            interaction_radius=48,
            properties={"target": "world"},
        )
        collision.add_object(obj)

    def tearDown(self):
        self.directory.cleanup()

    def test_public_schema_and_export_validate(self):
        path = os.path.join(self.base, "public.json")
        self.assertTrue(
            ProjectIO.export_public_json(
                self.project, self.assets, path
            )
        )
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(schema_errors(payload), [])
        self.assertEqual(payload["version"], "1.0")
        self.assertEqual(payload["format"], "tileset-map-maker")

    def test_project_asset_paths_are_relative_when_inside_project(self):
        path = os.path.join(self.base, "project.tmmap")
        self.assertTrue(ProjectIO.save_project(
            self.project, self.assets, path
        ))
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(
            payload["assets"]["assets"][0]["file_path"],
            "terrain.png",
        )
        restored_assets = AssetManager()
        restored = ProjectIO.load_project(path, restored_assets)
        self.assertIsNotNone(restored)
        self.assertEqual(
            restored_assets.get_asset(self.asset.id).file_path,
            os.path.abspath(self.image_path),
        )

    def test_relative_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_safe_asset_path(
                self.base, "../outside.png", allow_absolute=False
            )
        with self.assertRaises(ValueError):
            resolve_safe_asset_path(
                self.base, "/tmp/outside.png", allow_absolute=False
            )

    def test_tmx_roundtrip_preserves_tiles_objects_and_collisions(self):
        path = os.path.join(self.base, "roundtrip.tmx")
        self.assertTrue(ProjectIO.export_tmx(
            self.project, self.assets, path
        ))
        imported_assets = AssetManager()
        imported = ProjectIO.import_tmx(path, imported_assets)
        self.assertIsNotNone(imported)
        ground = next(layer for layer in imported.layers if layer.name == "Ground")
        item = ground.get_tile(1, 1)
        self.assertIsNotNone(item)
        self.assertTrue(item.flip_x)
        gameplay = next(
            layer for layer in imported.layers if layer.name == "Gameplay Objects"
        )
        self.assertEqual(len(gameplay.collisions), 1)
        self.assertTrue(gameplay.collisions[0].trigger)
        self.assertFalse(gameplay.collisions[0].blocking)
        self.assertEqual(gameplay.collisions[0].shape, CollisionShape.ELLIPSE)
        self.assertEqual(len(gameplay.objects), 1)
        self.assertEqual(gameplay.objects[0].properties["target"], "world")

    def test_tmx_external_tsx_import_uses_safe_relative_paths(self):
        tmx_path = os.path.join(self.base, "external.tmx")
        tsx_path = os.path.join(self.base, "terrain.tsx")
        with open(tsx_path, "w", encoding="utf-8") as handle:
            handle.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<tileset version="1.10" name="Terrain" tilewidth="32" '
                'tileheight="32" tilecount="2" columns="2">'
                '<image source="terrain.png" width="64" height="32"/>'
                "</tileset>"
            )
        csv = ",".join(["1"] + ["0"] * 11)
        with open(tmx_path, "w", encoding="utf-8") as handle:
            handle.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<map version="1.10" orientation="orthogonal" '
                'renderorder="right-down" width="4" height="3" '
                'tilewidth="32" tileheight="32">'
                '<tileset firstgid="1" source="terrain.tsx"/>'
                '<layer id="1" name="External" width="4" height="3">'
                f'<data encoding="csv">{csv}</data></layer></map>'
            )
        imported = ProjectIO.import_tmx(tmx_path, AssetManager())
        self.assertIsNotNone(imported)
        self.assertIsNotNone(imported.get_active_layer().get_tile(0, 0))

    def test_tmx_rejects_escaping_external_tileset_path(self):
        path = os.path.join(self.base, "escape.tmx")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                '<map version="1.10" orientation="orthogonal" '
                'width="1" height="1" tilewidth="32" tileheight="32">'
                '<tileset firstgid="1" source="../outside.tsx"/>'
                '<layer name="Unsafe" width="1" height="1">'
                '<data encoding="csv">0</data></layer></map>'
            )
        self.assertIsNone(ProjectIO.import_tmx(path, AssetManager()))
        self.assertIn("Niebezpieczna ścieżka", ProjectIO.get_last_error())

    def test_bundle_contains_manifest_maps_gameplay_and_assets(self):
        output = os.path.join(self.base, "bundle")
        self.assertTrue(
            ProjectIO.export_bundle(
                self.project,
                self.assets,
                RenderEngine(self.assets),
                output,
            )
        )
        self.assertTrue(os.path.isfile(os.path.join(output, "project.json")))
        self.assertTrue(os.path.isfile(os.path.join(output, "gameplay.json")))
        self.assertGreaterEqual(len(os.listdir(os.path.join(output, "maps"))), 1)
        manifest_assets = os.path.join(output, "assets")
        self.assertGreaterEqual(len(os.listdir(manifest_assets)), 1)
        with open(os.path.join(output, "project.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertTrue(
            manifest["assets"][0]["file_path"].startswith("assets/")
        )

    def test_export_validation_blocks_out_of_range_tiles(self):
        invalid = self.layer.tiles[(1, 1)].clone()
        self.layer.tiles[(99, 99)] = invalid
        errors = ProjectIO.validate_project(self.project, self.assets)
        self.assertTrue(any("poza zakresem" in error for error in errors))
        self.assertFalse(
            ProjectIO.export_public_json(
                self.project,
                self.assets,
                os.path.join(self.base, "invalid.json"),
            )
        )


if __name__ == "__main__":
    unittest.main()
