import os
import sys
import json
import logging
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from PyQt6.QtCore import QStandardPaths

logger = logging.getLogger("ConfigManager")

CONFIG_VERSION = 1


def get_config_dir() -> str:
    """Returns directory where persistent application configuration is stored."""
    env_dir = os.environ.get("TILESET_CONFIG_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir
    if "unittest" in sys.modules or "pytest" in sys.modules:
        test_dir = os.path.join(tempfile.gettempdir(), "tileset_map_maker_test_config")
        os.makedirs(test_dir, exist_ok=True)
        return test_dir
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not base or base == os.path.expanduser("~/.config"):
        base = os.path.expanduser("~/.config/tileset_map_maker")
    os.makedirs(base, exist_ok=True)
    return base


def get_default_config() -> Dict[str, Any]:
    """Returns safe default configuration for the application and tileset library."""
    return {
        "version": CONFIG_VERSION,
        "import_settings": {
            "default_tile_width": 32,
            "default_tile_height": 32,
            "default_margin_x": 0,
            "default_margin_y": 0,
            "default_spacing_x": 0,
            "default_spacing_y": 0,
            "default_start_x": 0,
            "default_start_y": 0,
            "skip_dialog_on_single": False,
        },
        "app_settings": {
            "language": "en",
            "theme": "Ciemny profesjonalny (Domyślny)",
            "accent": "Błękit królewski (#3b82f6)",
            "font_size": "Standardowy (12 pt)",
            "tile_size": "32x32",
            "show_grid": True,
            "show_hud": True,
            "checkerboard": True,
            "grid_opacity": 35,
            "brush_size": 1,
            "rotation_step": "90°",
            "snap_default": False,
            "autosave_interval": 3,
            "last_project_path": "",
        },
        "tileset_library": {
            "assets": [],
            "category_tree": {"name": "", "children": {}, "asset_ids": []},
            "active_asset_id": None,
            "expanded_folders": [],
        },
        "window_state": {
            "geometry": "",
            "state": "",
            "splitter_state": "",
        },
        "toolbar_layout": None,
    }


class ConfigManager:
    """
    Central manager for saving and loading application configuration,
    window layouts, global tileset import settings, and the persistent
    tileset library hierarchy.
    """

    def __init__(self, custom_config_path: Optional[str] = None, config_path: Optional[str] = None):
        target_path = custom_config_path or config_path
        if target_path:
            self.config_path = target_path
        else:
            self.config_path = os.path.join(get_config_dir(), "app_config.json")
        self.config_data = self.load()

    def load(self) -> Dict[str, Any]:
        """Loads configuration from JSON file safely with fallback to defaults."""
        defaults = get_default_config()
        if not os.path.exists(self.config_path):
            return defaults

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.warning("Config file invalid, restoring defaults.")
                return defaults

            # Merge with defaults
            merged = defaults.copy()
            for k, v in data.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
            return merged
        except Exception as e:
            logger.error(f"Error reading configuration file ({e}), using default values.")
            return defaults

    def save(self) -> bool:
        """Atomically saves configuration to disk."""
        try:
            parent_dir = os.path.dirname(self.config_path)
            os.makedirs(parent_dir, exist_ok=True)

            tmp_fd, tmp_path = tempfile.mkstemp(dir=parent_dir, prefix="cfg_", suffix=".tmp")
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            os.replace(tmp_path, self.config_path)
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to {self.config_path}: {e}")
            return False

    # -------------------------------------------------------------
    # Import Settings Accessors
    # -------------------------------------------------------------

    def get_import_settings(self) -> Dict[str, Any]:
        return self.config_data.get("import_settings", get_default_config()["import_settings"])

    def set_import_settings(
        self,
        tile_width: int = 32,
        tile_height: int = 32,
        margin_x: int = 0,
        margin_y: int = 0,
        spacing_x: int = 0,
        spacing_y: int = 0,
        start_x: int = 0,
        start_y: int = 0,
        skip_dialog_on_single: bool = False,
    ) -> None:
        self.config_data["import_settings"] = {
            "default_tile_width": max(4, tile_width),
            "default_tile_height": max(4, tile_height),
            "default_margin_x": max(0, margin_x),
            "default_margin_y": max(0, margin_y),
            "default_spacing_x": max(0, spacing_x),
            "default_spacing_y": max(0, spacing_y),
            "default_start_x": max(0, start_x),
            "default_start_y": max(0, start_y),
            "skip_dialog_on_single": skip_dialog_on_single,
        }
        self.save()

    # -------------------------------------------------------------
    # App Settings Accessors
    # -------------------------------------------------------------

    def get_app_settings(self) -> Dict[str, Any]:
        return self.config_data.get("app_settings", get_default_config()["app_settings"])

    def update_app_settings(self, updates: Dict[str, Any]) -> None:
        if "app_settings" not in self.config_data:
            self.config_data["app_settings"] = {}
        self.config_data["app_settings"].update(updates)
        self.save()

    def get_last_project_path(self) -> str:
        path = self.get_app_settings().get("last_project_path", "")
        return path if isinstance(path, str) else ""

    def set_last_project_path(self, path: str) -> None:
        self.update_app_settings({"last_project_path": path or ""})

    # -------------------------------------------------------------
    # Window State Accessors
    # -------------------------------------------------------------

    def get_window_state(self) -> Dict[str, Any]:
        return self.config_data.get("window_state", get_default_config()["window_state"])

    def save_window_state(self, geometry_b64: str, state_b64: str, splitter_state_b64: str = "") -> None:
        self.config_data["window_state"] = {
            "geometry": geometry_b64,
            "state": state_b64,
            "splitter_state": splitter_state_b64,
        }
        self.save()

    # -------------------------------------------------------------
    # Toolbar Layout Persistence
    # -------------------------------------------------------------

    def get_toolbar_layout(self) -> Optional[Dict[str, Any]]:
        """Returns saved toolbar layout configuration or None."""
        return self.config_data.get("toolbar_layout")

    def save_toolbar_layout(self, layout_data: Dict[str, Any]) -> bool:
        """Saves toolbar layout configuration to persistent settings."""
        self.config_data["toolbar_layout"] = layout_data
        return self.save()

    # -------------------------------------------------------------
    # Tileset Library Persistence
    # -------------------------------------------------------------

    def save_tileset_library(
        self,
        asset_manager: Any,
        active_asset_id: Optional[str] = None,
        expanded_folders: Optional[List[str]] = None,
    ) -> bool:
        """Serializes all tileset assets, category tree and UI tree state."""
        from ..models.asset import AssetType

        tileset_assets = [
            a.to_dict()
            for a in asset_manager.assets.values()
            if a.asset_type == AssetType.TILESET
        ]

        previous = self.config_data.get("tileset_library")
        self.config_data["tileset_library"] = {
            "assets": tileset_assets,
            "category_tree": asset_manager.category_tree.to_dict(),
            "active_asset_id": active_asset_id,
            "expanded_folders": expanded_folders or [],
        }
        saved = False
        try:
            saved = self.save()
            return saved
        finally:
            if not saved:
                if previous is None:
                    self.config_data.pop("tileset_library", None)
                else:
                    self.config_data["tileset_library"] = previous

    def restore_tileset_library(
        self,
        asset_manager: Any,
    ) -> Tuple[Optional[str], List[str]]:
        """
        Restores saved tileset assets and category hierarchy into AssetManager.
        Returns (active_asset_id, expanded_folders).
        """
        from ..models.asset import Asset, AssetType
        from ..models.category import CategoryTree

        lib_data = self.config_data.get("tileset_library", {})
        assets_data = lib_data.get("assets", [])
        cat_data = lib_data.get("category_tree", {})
        active_id = lib_data.get("active_asset_id")
        expanded = lib_data.get("expanded_folders", [])

        # Restore categories
        if cat_data:
            asset_manager.category_tree = CategoryTree.from_dict(cat_data)
        else:
            asset_manager.category_tree = CategoryTree(seed_defaults=False)

        # Restore tileset assets (only those whose files still exist on disk)
        for a_data in assets_data:
            fpath = a_data.get("file_path", "")
            if not fpath or not os.path.exists(fpath):
                continue
            asset = Asset.from_dict(a_data)
            asset.asset_type = AssetType.TILESET
            asset_manager.assets[asset.id] = asset
            if asset.content_hash:
                asset_manager.hash_to_id[asset.content_hash] = asset.id

            # Ensure category node registers this asset ID
            node = asset_manager.category_tree.add_category_path(asset.category_path)
            if asset.id not in node.asset_ids:
                node.asset_ids.append(asset.id)

        asset_manager.assets_changed.emit()
        asset_manager.categories_changed.emit()

        # Check if saved active asset actually exists
        if active_id and active_id not in asset_manager.assets:
            active_id = next(iter(asset_manager.assets.keys()), None)

        return active_id, expanded

    # -------------------------------------------------------------
    # AutoTile Ruleset Persistence
    # -------------------------------------------------------------

    def save_autotile_rules(self, autotile_engine: Any) -> bool:
        """Saves configured AutoTile rulesets to persistent configuration."""
        self.config_data["autotile_library"] = autotile_engine.to_dict()
        return self.save()

    def restore_autotile_rules(self, autotile_engine: Any) -> None:
        """Restores configured AutoTile rulesets from configuration."""
        data = self.config_data.get("autotile_library")
        if data:
            autotile_engine.load_from_dict(data)

    # -------------------------------------------------------------
    # Brush Variants & Randomizer Persistence
    # -------------------------------------------------------------

    def save_brush_settings(self, brush_settings: Any) -> bool:
        """Saves brush randomizer configuration and variants to persistent settings."""
        if hasattr(brush_settings, "to_dict"):
            self.config_data["brush_settings"] = brush_settings.to_dict()
            return self.save()
        return False

    def restore_brush_settings(self, brush_settings: Any) -> None:
        """Restores brush randomizer configuration and variants from persistent settings."""
        data = self.config_data.get("brush_settings")
        if data and hasattr(brush_settings, "load_from_dict"):
            brush_settings.load_from_dict(data)
            brush_settings.auto_tile_enabled = False

    def save_terrain_generator(self, generator: Any) -> bool:
        self.config_data["terrain_generator"] = generator.to_dict()
        return self.save()

    def restore_terrain_generator(self, generator: Any) -> None:
        data = self.config_data.get("terrain_generator")
        if isinstance(data, dict):
            generator.load_from_dict(data)
