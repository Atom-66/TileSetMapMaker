import sys
import unittest
from PyQt6.QtWidgets import QApplication

from tileset_map_maker.models.project import Project
from tileset_map_maker.models.map_model import MapModel
from tileset_map_maker.ui.map_tab_bar import MapTabBar

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestMultiMap(unittest.TestCase):
    """
    Test suite for Multi-Map Project Architecture and backward compatibility.
    """

    def setUp(self):
        self.project = Project(name="Projekt Map", map_width=25, map_height=20, tile_size=32)

    def test_01_initial_project_has_primary_map(self):
        """Initial project contains one active primary map."""
        self.assertEqual(len(self.project.maps), 1)
        active_m = self.project.get_active_map()
        self.assertIsNotNone(active_m)
        self.assertEqual(active_m.name, "Główna Mapa")
        self.assertEqual(active_m.map_width, 25)
        self.assertEqual(active_m.map_height, 20)

    def test_02_add_and_switch_maps(self):
        """Adding maps, switching active map, and proxy properties."""
        map2 = self.project.add_map(name="Podziemia", width=40, height=30, tile_size=32)
        self.assertEqual(len(self.project.maps), 2)
        self.assertEqual(self.project.active_map_id, map2.id)

        # Proxied dimensions should reflect map2
        self.assertEqual(self.project.map_width, 40)
        self.assertEqual(self.project.map_height, 30)

        # Switch back to first map
        first_id = [mid for mid in self.project.maps.keys() if mid != map2.id][0]
        self.project.set_active_map(first_id)
        self.assertEqual(self.project.active_map_id, first_id)
        self.assertEqual(self.project.map_width, 25)

    def test_03_duplicate_and_rename_map(self):
        """Duplicating a map and renaming."""
        clone = self.project.duplicate_map(self.project.active_map_id, new_name="Główna Kopia")
        self.assertIsNotNone(clone)
        self.assertEqual(clone.name, "Główna Kopia")
        self.assertEqual(len(self.project.maps), 2)

        ok = self.project.rename_map(clone.id, "Zmieniona Nazwa")
        self.assertTrue(ok)
        self.assertEqual(self.project.maps[clone.id].name, "Zmieniona Nazwa")

    def test_04_remove_map_safely(self):
        """Removing a map updates active_map_id; cannot remove last remaining map."""
        m2 = self.project.add_map("Druga")
        self.assertEqual(len(self.project.maps), 2)

        ok = self.project.remove_map(m2.id)
        self.assertTrue(ok)
        self.assertEqual(len(self.project.maps), 1)

        # Cannot remove the only remaining map
        last_id = self.project.active_map_id
        ok2 = self.project.remove_map(last_id)
        self.assertFalse(ok2)
        self.assertEqual(len(self.project.maps), 1)

    def test_05_serialization_and_legacy_compatibility(self):
        """Serialization to/from dict and automatic upgrade of legacy v1.0 files."""
        # 1. Multi-map serialization
        m2 = self.project.add_map("Rynek")

        d = self.project.to_dict()
        self.assertEqual(d["version"], "2.0")
        self.assertEqual(len(d["maps"]), 2)

        # Deserialize
        restored = Project.from_dict(d)
        self.assertEqual(len(restored.maps), 2)

        # 2. Legacy v1.0 format upgrade
        legacy_data = {
            "name": "Stary Projekt Jednomapowy",
            "map_width": 15,
            "map_height": 10,
            "tile_size": 32,
            "layers": [
                {"name": "Ground", "visible": True, "opacity": 1.0, "locked": False, "tiles": {}}
            ],
        }
        upgraded = Project.from_dict(legacy_data)
        self.assertEqual(len(upgraded.maps), 1)
        self.assertEqual(upgraded.map_width, 15)
        self.assertEqual(upgraded.map_height, 10)
        self.assertEqual(upgraded.get_active_map().name, "Stary Projekt Jednomapowy")

    def test_06_map_tab_bar_ui(self):
        """MapTabBar UI integration."""
        tab_bar = MapTabBar(self.project)
        self.assertEqual(tab_bar.tab_bar.count(), len(self.project.maps))


if __name__ == "__main__":
    unittest.main()
