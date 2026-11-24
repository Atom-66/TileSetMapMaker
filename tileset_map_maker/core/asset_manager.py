import os
import time
import logging
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QObject, pyqtSignal, Qt

from ..models.asset import Asset, AssetType, TilesetConfig, SelectedSubTile
from ..models.category import CategoryTree, CategoryNode

logger = logging.getLogger("AssetManager")


class AssetManager(QObject):
    """
    Manages asset loading, category hierarchy, importing,
    duplicate detection, search, and thumbnail caching.
    """
    assets_changed = pyqtSignal()
    categories_changed = pyqtSignal()
    asset_selected = pyqtSignal(object)  # Selected Asset or SelectedSubTile

    def __init__(self):
        super().__init__()
        self.assets: Dict[str, Asset] = {}  # asset_id -> Asset
        self.hash_to_id: Dict[str, str] = {}  # sha256 -> asset_id
        self.category_tree = CategoryTree()
        self.selected_item: Optional[Any] = None  # Asset or SelectedSubTile
        self.recent_asset_ids: List[str] = []

        # In-memory pixmap and image cache for fast drawing, thumbnails and hit-testing
        self._pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._image_cache: OrderedDict[str, QImage] = OrderedDict()
        self._thumbnail_cache: OrderedDict[Tuple[str, int], QPixmap] = OrderedDict()
        self._tile_region_cache: OrderedDict[
            Tuple[str, int, int, int, int], QPixmap
        ] = OrderedDict()
        self._texture_cache_limit_bytes = 128 * 1024 * 1024
        self._search_index: Dict[str, str] = {}
        self._search_index_dirty = True
        self._missing_asset_ids: Set[str] = set()

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        return self.assets.get(asset_id)

    def invalidate_search_index(self) -> None:
        self._search_index_dirty = True
        self._search_index.clear()

    def _ensure_search_index(self) -> None:
        if not self._search_index_dirty:
            return
        self._search_index = {
            asset_id: f"{asset.name}\n{asset.category_path}".casefold()
            for asset_id, asset in self.assets.items()
        }
        self._search_index_dirty = False

    def select_asset(self, asset: Optional[Asset], sub_tile: Optional[SelectedSubTile] = None) -> None:
        if sub_tile is not None:
            self.selected_item = sub_tile
            if asset:
                asset.last_used_time = time.time()
                self._touch_recent(asset.id)
            self.asset_selected.emit(sub_tile)
        elif asset is not None:
            if asset.asset_type == AssetType.TILESET:
                # A tileset must NEVER be treated as a single whole-image object!
                # Always resolve to a regular grid cell (defaulting to 0,0 if not specified).
                cfg = asset.tileset_config or TilesetConfig(tile_width=32, tile_height=32)
                sub_tile = SelectedSubTile(
                    asset_id=asset.id,
                    col=0,
                    row=0,
                    cols_count=1,
                    rows_count=1,
                    sub_x=cfg.start_x + cfg.margin_x,
                    sub_y=cfg.start_y + cfg.margin_y,
                    sub_w=cfg.tile_width,
                    sub_h=cfg.tile_height,
                    tile_width=cfg.tile_width,
                    tile_height=cfg.tile_height,
                    spacing_x=cfg.spacing_x,
                    spacing_y=cfg.spacing_y,
                    asset_name=asset.name,
                )
                self.selected_item = sub_tile
                asset.last_used_time = time.time()
                self._touch_recent(asset.id)
                self.asset_selected.emit(sub_tile)
            else:
                self.selected_item = asset
                asset.last_used_time = time.time()
                self._touch_recent(asset.id)
                self.asset_selected.emit(asset)
        else:
            self.selected_item = None
            self.asset_selected.emit(None)

    def _touch_recent(self, asset_id: str) -> None:
        if asset_id in self.recent_asset_ids:
            self.recent_asset_ids.remove(asset_id)
        self.recent_asset_ids.insert(0, asset_id)
        if len(self.recent_asset_ids) > 50:
            self.recent_asset_ids = self.recent_asset_ids[:50]

    def get_pixmap(self, asset_id: str) -> Optional[QPixmap]:
        if asset_id in self._pixmap_cache:
            pixmap = self._pixmap_cache.pop(asset_id)
            self._pixmap_cache[asset_id] = pixmap
            return pixmap
        if asset_id in self._missing_asset_ids:
            return None

        asset = self.get_asset(asset_id)
        if not asset or not os.path.exists(asset.file_path):
            logger.warning(f"get_pixmap: asset {asset_id} not found or file does not exist: {getattr(asset, 'file_path', None)}")
            self._missing_asset_ids.add(asset_id)
            if len(self._missing_asset_ids) > 4096:
                self._missing_asset_ids.pop()
            return None

        # 1. Try native Qt QPixmap load
        pixmap = QPixmap(asset.file_path)

        # 2. If native load fails, fallback to PIL loader (handles complex/indexed PNGs, CMYK, etc.)
        if pixmap.isNull():
            logger.warning(f"QPixmap native load returned null for {asset.file_path}. Attempting PIL fallback...")
            try:
                from PIL import Image
                with Image.open(asset.file_path) as im:
                    im_rgba = im.convert("RGBA")
                    raw_data = im_rgba.tobytes("raw", "RGBA")
                    qimg = QImage(
                        raw_data,
                        im_rgba.width,
                        im_rgba.height,
                        im_rgba.width * 4,
                        QImage.Format.Format_RGBA8888,
                    )
                    pixmap = QPixmap.fromImage(qimg.copy())
                    logger.info(f"PIL fallback successfully loaded {asset.file_path} ({im_rgba.width}x{im_rgba.height})")
            except Exception as e:
                logger.error(f"Failed to load image via PIL fallback for {asset.file_path}: {e}")

        if not pixmap.isNull():
            self._pixmap_cache[asset_id] = pixmap
            self._evict_texture_cache(
                self._pixmap_cache,
                lambda cached: cached.width() * cached.height() * 4,
            )
            logger.info(
                f"[TEXTURE_LOADED] Asset '{asset.name}' (id: {asset.id[:8]}...): "
                f"Path: {asset.file_path} | Size: {pixmap.width()}x{pixmap.height()} px | HasAlpha: {pixmap.hasAlpha()}"
            )
            return pixmap

        logger.error(f"[TEXTURE_FAILED] Could not load texture for asset '{asset.name}' from {asset.file_path}")
        self._missing_asset_ids.add(asset_id)
        if len(self._missing_asset_ids) > 4096:
            self._missing_asset_ids.pop()
        return None

    def get_tile_pixmap(
        self, asset_id: str, x: int, y: int, width: int, height: int
    ) -> Optional[QPixmap]:
        """Return a cached source rectangle, avoiding repeated tileset copies."""
        cache_key = (asset_id, x, y, width, height)
        if cache_key in self._tile_region_cache:
            pixmap = self._tile_region_cache.pop(cache_key)
            self._tile_region_cache[cache_key] = pixmap
            return pixmap
        source = self.get_pixmap(asset_id)
        if not source or source.isNull():
            return None
        tile = source.copy(x, y, width, height)
        if tile.isNull():
            return None
        self._tile_region_cache[cache_key] = tile
        while len(self._tile_region_cache) > 4096:
            self._tile_region_cache.popitem(last=False)
        return tile

    def get_image(self, asset_id: str) -> Optional[QImage]:
        """Returns QImage for pixel-level sampling and alpha hit-testing."""
        if asset_id in self._image_cache:
            image = self._image_cache.pop(asset_id)
            self._image_cache[asset_id] = image
            return image
        pixmap = self.get_pixmap(asset_id)
        if pixmap and not pixmap.isNull():
            img = pixmap.toImage()
            self._image_cache[asset_id] = img
            self._evict_texture_cache(
                self._image_cache,
                lambda cached: cached.width() * cached.height() * 4,
            )
            return img
        return None

    def get_thumbnail(self, asset_id: str, size: int = 64) -> Optional[QPixmap]:
        cache_key = (asset_id, size)
        if cache_key in self._thumbnail_cache:
            return self._thumbnail_cache[cache_key]

        pixmap = self.get_pixmap(asset_id)
        if not pixmap or pixmap.isNull():
            return None

        thumb = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_cache[cache_key] = thumb
        return thumb

    def _evict_texture_cache(self, cache, size_of) -> None:
        while (
            len(cache) > 1
            and sum(size_of(value) for value in cache.values())
            > self._texture_cache_limit_bytes
        ):
            cache.popitem(last=False)

    def auto_detect_tileset_config(self, asset: Asset) -> TilesetConfig:
        """
        Auto-detects typical tile dimensions (32, 16, 48, 64)
        if dimensions cleanly divide by them.
        """
        w, h = asset.width, asset.height
        candidates = [32, 16, 48, 64, 24]
        for size in candidates:
            if w >= size and h >= size and (w % size == 0) and (h % size == 0):
                if w > size or h > size:  # At least 2 tiles total
                    return TilesetConfig(
                        tile_width=size,
                        tile_height=size,
                        margin=0,
                        spacing=0,
                        auto_detected=True,
                    )
        return TilesetConfig(tile_width=32, tile_height=32, auto_detected=False)

    def import_single_file(
        self,
        file_path: str,
        target_category_path: str = "Custom",
        skip_duplicates: bool = True,
        force_asset_type: Optional[AssetType] = None,
    ) -> Tuple[Optional[Asset], bool, str]:
        """
        Imports a single PNG file.
        Returns (Asset or None, is_duplicate: bool, error_message: str).
        """
        if not os.path.exists(file_path):
            return None, False, f"Plik nie istnieje: {file_path}"

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            return None, False, f"Nieobsługiwany format pliku: {ext}"

        content_hash = Asset.calculate_hash(file_path)
        if content_hash in self.hash_to_id:
            existing_id = self.hash_to_id[content_hash]
            existing_asset = self.assets.get(existing_id)
            if skip_duplicates:
                return existing_asset, True, "Plik jest duplikatem (pominięto)."

        category_path = target_category_path.strip("/") or "Custom"
        cat_node = self.category_tree.add_category_path(category_path)

        asset = Asset(
            file_path=file_path,
            category_path=category_path,
            content_hash=content_hash,
        )

        if force_asset_type is not None:
            asset.asset_type = force_asset_type
            if force_asset_type == AssetType.TILESET and not asset.tileset_config:
                asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
        else:
            # Default to TILESET if image dimensions suggest an image sheet or multi-tile asset
            if (asset.width >= 64 or asset.height >= 64 or (asset.width > 32 and asset.height > 32)):
                asset.asset_type = AssetType.TILESET
                asset.tileset_config = TilesetConfig(tile_width=32, tile_height=32)
            else:
                asset.asset_type = AssetType.SINGLE_IMAGE

        self.assets[asset.id] = asset
        self.invalidate_search_index()
        self.hash_to_id[content_hash] = asset.id
        cat_node.asset_ids.append(asset.id)

        self.assets_changed.emit()
        self.categories_changed.emit()
        return asset, False, ""

    def import_multiple_files(
        self,
        file_paths: List[str],
        target_category_path: str = "Custom",
        skip_duplicates: bool = True,
    ) -> Dict[str, Any]:
        """Imports a list of files."""
        imported = []
        duplicates = []
        errors = []

        for p in file_paths:
            asset, is_dup, err = self.import_single_file(
                p, target_category_path=target_category_path, skip_duplicates=skip_duplicates
            )
            if asset and not is_dup:
                imported.append(asset)
            elif is_dup:
                duplicates.append(p)
            elif err:
                errors.append(f"{os.path.basename(p)}: {err}")

        return {
            "imported_count": len(imported),
            "duplicates_count": len(duplicates),
            "errors": errors,
            "imported": imported,
        }

    def import_folder(
        self,
        folder_path: str,
        parent_category: str = "",
        skip_duplicates: bool = True,
        default_tileset_config: Optional[TilesetConfig] = None,
        force_asset_type: Optional[AssetType] = None,
        target_category_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recursively scans a folder and maps directory structure
        into categories and subcategories in the library.
        Preserves complete nested hierarchy.
        """
        if target_category_path is not None:
            parent_category = target_category_path

        if not os.path.isdir(folder_path):
            return {
                "imported_count": 0,
                "duplicates_count": 0,
                "skipped_count": 0,
                "error_count": 1,
                "errors": [f"Ścieżka nie jest katalogiem: {folder_path}"],
                "imported": [],
                "skipped_files": [],
            }

        root_name = os.path.basename(folder_path.rstrip(os.sep))
        base_cat = (
            f"{parent_category}/{root_name}".strip("/")
            if parent_category
            else root_name
        )

        imported = []
        duplicates = []
        errors = []
        skipped_files = []

        # Supported image file extensions
        valid_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

        for dirpath, _, filenames in os.walk(folder_path):
            # Calculate relative category path matching folder hierarchy
            rel_dir = os.path.relpath(dirpath, folder_path)
            if rel_dir == ".":
                cat_path = base_cat
            else:
                cat_path = f"{base_cat}/{rel_dir}".replace(os.sep, "/")

            # Ensure category node exists even if folder is empty
            self.category_tree.add_category_path(cat_path)

            for filename in sorted(filenames):
                ext = os.path.splitext(filename)[1].lower()
                full_path = os.path.join(dirpath, filename)

                if ext in valid_extensions:
                    asset, is_dup, err = self.import_single_file(
                        full_path,
                        target_category_path=cat_path,
                        skip_duplicates=skip_duplicates,
                        force_asset_type=force_asset_type,
                    )
                    if asset and not is_dup:
                        if default_tileset_config:
                            asset.tileset_config = TilesetConfig(
                                tile_width=default_tileset_config.tile_width,
                                tile_height=default_tileset_config.tile_height,
                                margin_x=default_tileset_config.margin_x,
                                margin_y=default_tileset_config.margin_y,
                                spacing_x=default_tileset_config.spacing_x,
                                spacing_y=default_tileset_config.spacing_y,
                                start_x=default_tileset_config.start_x,
                                start_y=default_tileset_config.start_y,
                            )
                        imported.append(asset)
                    elif is_dup:
                        duplicates.append(full_path)
                    elif err:
                        errors.append(f"{filename}: {err}")
                else:
                    skipped_files.append(full_path)

        self.categories_changed.emit()
        self.assets_changed.emit()

        return {
            "imported_count": len(imported),
            "duplicates_count": len(duplicates),
            "skipped_count": len(skipped_files),
            "error_count": len(errors),
            "errors": errors,
            "imported": imported,
            "skipped_files": skipped_files,
        }

    def rename_asset(self, asset_id: str, new_name: str) -> bool:
        """Renames an asset label in the library without altering disk file."""
        asset = self.get_asset(asset_id)
        if not asset or not new_name.strip():
            return False
        asset.name = new_name.strip()
        self.invalidate_search_index()
        self.assets_changed.emit()
        return True

    def rename_category(self, old_path: str, new_name: str) -> Optional[str]:
        """Renames a category folder and updates paths of all containing assets."""
        new_path = self.category_tree.rename_category(old_path, new_name)
        if not new_path:
            return None

        # Update all assets belonging to this category or subcategories
        for asset in self.assets.values():
            if asset.category_path == old_path:
                asset.category_path = new_path
            elif asset.category_path.startswith(old_path + "/"):
                suffix = asset.category_path[len(old_path):]
                asset.category_path = new_path + suffix
        self.invalidate_search_index()

        self.categories_changed.emit()
        self.assets_changed.emit()
        return new_path

    def delete_category(self, category_path: str, delete_assets: bool = False) -> bool:
        """
        Deletes a category folder. If delete_assets is True, removes assets from library.
        If delete_assets is False, safely moves assets to the parent category.
        Never touches or deletes source files on disk.
        """
        node = self.category_tree.get_node(category_path)
        if not node or node == self.category_tree.root:
            return False

        parent_path = node.parent.path if (node.parent and node.parent != self.category_tree.root) else ""
        all_child_asset_ids = node.get_all_asset_ids()

        for aid in all_child_asset_ids:
            if delete_assets:
                self.remove_asset(aid)
            else:
                self.move_asset(aid, parent_path)

        success = self.category_tree.delete_category(category_path)
        if success:
            self.categories_changed.emit()
            self.assets_changed.emit()
        return success

    def set_asset_type(
        self,
        asset_id: str,
        new_type: AssetType,
        tile_width: int = 32,
        tile_height: int = 32,
    ) -> bool:
        """Switches an asset between TILESET and SINGLE_IMAGE mode."""
        asset = self.get_asset(asset_id)
        if not asset:
            return False
        asset.asset_type = new_type
        if new_type == AssetType.TILESET:
            if not asset.tileset_config:
                asset.tileset_config = TilesetConfig(tile_width=tile_width, tile_height=tile_height)
        self.assets_changed.emit()
        return True

    def remove_asset(self, asset_id: str) -> bool:
        asset = self.assets.pop(asset_id, None)
        if not asset:
            return False
        self.invalidate_search_index()
        if asset.content_hash in self.hash_to_id:
            del self.hash_to_id[asset.content_hash]
        if asset_id in self.recent_asset_ids:
            self.recent_asset_ids.remove(asset_id)

        # Remove from category node
        node = self.category_tree.get_node(asset.category_path)
        if node and asset_id in node.asset_ids:
            node.asset_ids.remove(asset_id)

        # Clear caches
        self._pixmap_cache.pop(asset_id, None)
        self._image_cache.pop(asset_id, None)
        for key in [
            key for key in self._tile_region_cache if key[0] == asset_id
        ]:
            self._tile_region_cache.pop(key, None)
        self._missing_asset_ids.discard(asset_id)
        for (aid, size) in list(self._thumbnail_cache.keys()):
            if aid == asset_id:
                del self._thumbnail_cache[(aid, size)]

        if self.selected_item == asset or (
            isinstance(self.selected_item, SelectedSubTile)
            and self.selected_item.asset_id == asset_id
        ):
            self.select_asset(None)

        self.assets_changed.emit()
        return True

    def move_asset(self, asset_id: str, new_category_path: str) -> bool:
        asset = self.get_asset(asset_id)
        if not asset:
            return False
        old_cat = asset.category_path
        old_node = self.category_tree.get_node(old_cat)
        if old_node and asset_id in old_node.asset_ids:
            old_node.asset_ids.remove(asset_id)

        new_cat = new_category_path.strip("/")
        new_node = self.category_tree.add_category_path(new_cat)
        if asset_id not in new_node.asset_ids:
            new_node.asset_ids.append(asset_id)
        asset.category_path = new_cat
        self.invalidate_search_index()

        self.assets_changed.emit()
        self.categories_changed.emit()
        return True

    def move_library_items(
        self,
        items: List[Tuple[str, str]],
        destination: str,
        persist: Callable[[Dict[str, str]], bool],
    ) -> Dict[str, str]:
        """Move a selection as one transaction, persisting before notifying views."""
        tree = CategoryTree.from_dict(self.category_tree.to_dict())
        target = tree.get_node(destination)
        if target is None or target.path != destination:
            raise ValueError("Destination folder does not exist.")
        if not items or len(set(items)) != len(items):
            raise ValueError("Invalid or duplicate selection.")

        folders = []
        assets = []
        for kind, value in items:
            if kind == "folder":
                node = tree.get_node(value)
                if not value or node is None or node.path != value:
                    raise ValueError("Source folder does not exist.")
                folders.append(value)
            elif kind == "tileset":
                asset = self.get_asset(value)
                if asset is None:
                    raise ValueError("Source tileset does not exist.")
                node = tree.get_node(asset.category_path)
                if node is None or node.asset_ids.count(value) != 1:
                    raise ValueError("Source tileset is not registered in its folder.")
                assets.append(value)
            else:
                raise ValueError("Unknown library item.")

        folders = [p for p in folders if not any(
            p.startswith(other + "/") for other in folders if other != p
        )]
        if any(destination == p or destination.startswith(p + "/") for p in folders):
            raise ValueError("Cannot move a folder into itself or its descendant.")

        path_map: Dict[str, str] = {}
        for path in folders:
            node = tree.get_node(path)
            assert node is not None
            if node.parent == target:
                continue
            if node.name in target.children:
                raise ValueError(f"A folder named '{node.name}' already exists at the destination.")
            new_path = tree.move_category(path, destination)
            if new_path is None:
                raise ValueError("Unable to move folder.")
            path_map[path] = new_path

        new_paths = {}
        for asset in self.assets.values():
            path = asset.category_path
            for old, new in path_map.items():
                if path == old or path.startswith(old + "/"):
                    path = new + path[len(old):]
                    break
            new_paths[asset.id] = path

        for asset_id in assets:
            asset = self.assets[asset_id]
            if any(asset.category_path == p or asset.category_path.startswith(p + "/") for p in folders):
                continue
            node = tree.get_node(asset.category_path)
            assert node is not None
            if node != target:
                node.asset_ids.remove(asset_id)
                if asset_id in target.asset_ids:
                    raise ValueError("Tileset already exists in destination.")
                target.asset_ids.append(asset_id)
                new_paths[asset_id] = destination

        old_tree = self.category_tree
        old_paths = {aid: asset.category_path for aid, asset in self.assets.items()}
        self.category_tree = tree
        for aid, path in new_paths.items():
            self.assets[aid].category_path = path
        try:
            if not persist(path_map):
                raise OSError("Could not save the tileset library.")
        except Exception:
            self.category_tree = old_tree
            for aid, path in old_paths.items():
                self.assets[aid].category_path = path
            raise
        self.invalidate_search_index()
        return path_map

    def search_assets(
        self,
        query: str = "",
        category_path: Optional[str] = None,
        only_favorites: bool = False,
        only_recent: bool = False,
        asset_type: Optional[AssetType] = None,
    ) -> List[Asset]:
        """Filters and searches assets."""
        q = query.strip().casefold()

        if only_recent:
            results = [
                self.assets[aid] for aid in self.recent_asset_ids if aid in self.assets
            ]
        elif category_path is not None and category_path != "":
            node = self.category_tree.get_node(category_path)
            if node:
                all_ids = set(node.get_all_asset_ids())
                results = [self.assets[aid] for aid in all_ids if aid in self.assets]
            else:
                results = []
        else:
            results = list(self.assets.values())

        filtered = []
        self._ensure_search_index()
        for asset in results:
            if q and q not in self._search_index.get(asset.id, ""):
                continue
            if only_favorites and not asset.is_favorite:
                continue
            if asset_type is not None and asset.asset_type != asset_type:
                continue
            filtered.append(asset)

        return filtered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assets": [a.to_dict() for a in self.assets.values()],
            "category_tree": self.category_tree.to_dict(),
            "recent_asset_ids": self.recent_asset_ids,
        }

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self.assets.clear()
        self.hash_to_id.clear()
        self._pixmap_cache.clear()
        self._thumbnail_cache.clear()
        self._tile_region_cache.clear()
        self._missing_asset_ids.clear()

        if "category_tree" in data:
            self.category_tree = CategoryTree.from_dict(data["category_tree"])
        else:
            self.category_tree = CategoryTree()

        for a_data in data.get("assets", []):
            asset = Asset.from_dict(a_data)
            self.assets[asset.id] = asset
            if asset.content_hash:
                self.hash_to_id[asset.content_hash] = asset.id

            # Ensure category node exists and registers asset
            node = self.category_tree.add_category_path(asset.category_path)
            if asset.id not in node.asset_ids:
                node.asset_ids.append(asset.id)

        self.invalidate_search_index()
        self.recent_asset_ids = list(data.get("recent_asset_ids", []))
        self.assets_changed.emit()
        self.categories_changed.emit()
