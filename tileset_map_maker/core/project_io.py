import json
import logging
import os
import copy
import shutil
import tempfile
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtCore import Qt

from ..models.project import Project
from .asset_manager import AssetManager
from .render_engine import RenderEngine, RenderOptions
from .external_formats import (
    ExternalFormatError,
    TiledTMX,
    resolve_safe_asset_path,
    safe_relative_asset_path,
)
from .schema import PROJECT_JSON_SCHEMA, schema_errors
from ..version import PROJECT_SCHEMA_VERSION


class ProjectIO:
    """Handles project file serialization/deserialization and PNG exports."""

    FILE_VERSION = PROJECT_SCHEMA_VERSION
    BACKUP_SUFFIX = ".bak"
    _last_error: Optional[str] = None

    @classmethod
    def get_last_error(cls) -> Optional[str]:
        """Return the most recent actionable project I/O error."""
        return cls._last_error

    @classmethod
    def _set_error(cls, message: str) -> None:
        cls._last_error = message
        logging.getLogger(__name__).error(message)

    @staticmethod
    def _validate_and_migrate(data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Plik projektu musi zawierać obiekt JSON.")

        version = data.get("version")
        if version not in (None, ProjectIO.FILE_VERSION, "2.0"):
            raise ValueError(f"Nieobsługiwana wersja pliku projektu: {version!r}.")

        # Older files may contain the project payload at the top level.
        if "project" not in data and ("maps" in data or "layers" in data):
            data = {"version": ProjectIO.FILE_VERSION, "project": data}

        project_data = data.get("project")
        if not isinstance(project_data, dict):
            raise ValueError("Brak sekcji 'project' w pliku projektu.")
        if not (isinstance(project_data.get("maps"), list) or
                isinstance(project_data.get("layers"), list)):
            raise ValueError("Sekcja 'project' nie zawiera map ani warstw.")
        return data

    @staticmethod
    def _atomic_write(file_path: str, data: Dict[str, Any]) -> None:
        base_dir = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(base_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=base_dir, prefix=f".{os.path.basename(file_path)}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())

            if os.path.exists(file_path):
                shutil.copy2(file_path, f"{file_path}{ProjectIO.BACKUP_SUFFIX}")
            os.replace(temp_path, file_path)
            try:
                dir_fd = os.open(base_dir, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def save_project(
        project: Project,
        asset_manager: AssetManager,
        file_path: str,
        autotile_engine: Optional[Any] = None,
    ) -> bool:
        """Saves project, asset library metadata, and autotile rules to a JSON .tmmap file."""
        try:
            asset_data = copy.deepcopy(asset_manager.to_dict())
            base_dir = os.path.dirname(os.path.abspath(file_path))
            referenced_asset_ids = {
                item.asset_id
                for map_model in project.maps.values()
                for layer in map_model.layers
                for item in list(layer.tiles.values()) + layer.objects
            }
            if autotile_engine:
                for autotile in autotile_engine.rpg_autotiles.values():
                    if autotile.source_asset_id:
                        referenced_asset_ids.add(autotile.source_asset_id)
                    referenced_asset_ids.update(
                        variant.source_asset_id
                        for variant in autotile.custom_variants
                        if variant.source_asset_id
                    )

            for index, asset in enumerate(asset_data.get("assets", [])):
                stored_path = asset.get("file_path")
                if stored_path:
                    relative_path = safe_relative_asset_path(base_dir, stored_path)
                    if (
                        os.path.isabs(relative_path)
                        and asset.get("id") in referenced_asset_ids
                        and os.path.isfile(stored_path)
                    ):
                        extension = os.path.splitext(stored_path)[1]
                        asset_id = "".join(
                            char if char.isalnum() or char in ("-", "_") else "_"
                            for char in str(asset.get("id", ""))
                        )
                        relative_path = os.path.join(
                            "assets", f"asset_{index}_{asset_id}{extension}"
                        )
                        destination = os.path.join(base_dir, relative_path)
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        if os.path.abspath(stored_path) != os.path.abspath(destination):
                            fd, temporary_path = tempfile.mkstemp(
                                dir=os.path.dirname(destination),
                                prefix=f".{os.path.basename(destination)}.",
                                suffix=".tmp",
                            )
                            os.close(fd)
                            try:
                                shutil.copy2(stored_path, temporary_path)
                                os.replace(temporary_path, destination)
                            finally:
                                if os.path.exists(temporary_path):
                                    os.remove(temporary_path)
                    asset["file_path"] = relative_path
            data = {
                "format": "tileset-map-maker",
                "version": ProjectIO.FILE_VERSION,
                "project": project.to_dict(),
                "assets": asset_data,
            }
            if autotile_engine:
                data["autotile"] = autotile_engine.to_dict()

            ProjectIO._atomic_write(file_path, data)
            project.file_path = file_path
            project.is_modified = False
            ProjectIO._last_error = None
            return True
        except Exception as e:
            ProjectIO._set_error(f"Błąd zapisu projektu '{file_path}': {e}")
            return False

    @staticmethod
    def load_project(
        file_path: str,
        asset_manager: AssetManager,
        autotile_engine: Optional[Any] = None,
    ) -> Optional[Project]:
        """Loads project from .tmmap file and restores asset library, layers, and autotile rules."""
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = ProjectIO._validate_and_migrate(json.load(f))

            if "assets" in data:
                assets_data = copy.deepcopy(data["assets"])
                if isinstance(assets_data, dict):
                    assets = assets_data.get("assets", [])
                else:
                    assets = assets_data
                base_dir = os.path.dirname(os.path.abspath(file_path))
                for asset in assets:
                    stored_path = asset.get("file_path")
                    if stored_path:
                        asset["file_path"] = resolve_safe_asset_path(
                            base_dir, stored_path
                        )
                if isinstance(data["assets"], dict):
                    asset_manager.load_from_dict(assets_data)
                else:
                    asset_manager.load_from_dict({"assets": assets})

            if autotile_engine and "autotile" in data:
                autotile_engine.load_from_dict(data["autotile"], asset_manager=asset_manager)

            project_data = data.get("project", {})
            project = Project.from_dict(project_data)
            project.file_path = file_path
            project.is_modified = False
            ProjectIO._last_error = None
            return project
        except Exception as e:
            ProjectIO._set_error(f"Błąd odczytu projektu '{file_path}': {e}")
            return None

    @staticmethod
    def export_png(
        project: Project,
        render_engine: RenderEngine,
        file_path: str,
        transparent_bg: bool = False,
        custom_bg_color: Optional[str] = None,
        only_layer_ids: Optional[List[str]] = None,
        crop_to_content: bool = False,
        scale: float = 1.0,
    ) -> bool:
        """
        Exports the map to a clean, high-resolution PNG file.
        Respects layer visibility and custom background settings.
        """
        try:
            bg_col = QColor(custom_bg_color) if custom_bg_color else None

            options = RenderOptions(
                show_grid=False,
                show_selection=False,
                preview_items=[],
                render_checkerboard=False,
                ignore_hidden_layers=True,
                transparent_bg=transparent_bg,
                custom_bg_color=bg_col,
                only_layer_ids=only_layer_ids,
                scale=scale,
            )

            qimg = render_engine.export_to_image(
                project=project,
                options=options,
                crop_to_content=crop_to_content,
            )

            if scale != 1.0 and scale > 0.1:
                target_w = int(qimg.width() * scale)
                target_h = int(qimg.height() * scale)
                qimg = qimg.scaled(
                    target_w,
                    target_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )

            dir_path = os.path.dirname(os.path.abspath(file_path))
            os.makedirs(dir_path, exist_ok=True)

            return qimg.save(file_path, "PNG")
        except Exception as e:
            print(f"Błąd eksportu PNG: {e}")
            return False

    @staticmethod
    def validate_project_assets(project: Project, asset_manager: AssetManager) -> List[str]:
        referenced = {
            item.asset_id
            for map_model in project.maps.values()
            for layer in map_model.layers
            for item in list(layer.tiles.values()) + layer.objects
            if item.asset_id
        }
        return sorted(
            asset_id
            for asset_id in referenced
            if asset_manager.get_asset(asset_id) is None
        )

    @classmethod
    def validate_project(
        cls, project: Project, asset_manager: AssetManager
    ) -> List[str]:
        errors = cls.validate_project_assets(project, asset_manager)
        for map_model in project.maps.values():
            if map_model.map_width <= 0 or map_model.map_height <= 0:
                errors.append(f"Mapa {map_model.name!r} ma niepoprawne wymiary.")
            for layer in map_model.layers:
                for (col, row), item in layer.tiles.items():
                    if not (
                        0 <= col < map_model.map_width
                        and 0 <= row < map_model.map_height
                    ):
                        errors.append(
                            f"Warstwa {layer.name!r}: kafelek poza zakresem ({col}, {row})."
                        )
                    if not item.asset_id:
                        errors.append(
                            f"Warstwa {layer.name!r}: kafelek bez asset_id."
                        )
                for obj in layer.objects:
                    x, y = obj.get_pixel_pos(map_model.tile_size)
                    if (
                        x < 0
                        or y < 0
                        or x >= map_model.map_width * map_model.tile_size
                        or y >= map_model.map_height * map_model.tile_size
                    ):
                        errors.append(
                            f"Obiekt {obj.id!r} znajduje się poza mapą."
                        )
        return errors

    @classmethod
    def export_maps_png(
        cls,
        project: Project,
        render_engine: RenderEngine,
        output_dir: str,
        **options: Any,
    ) -> bool:
        """Export every project map to a separate PNG without changing the active map."""
        os.makedirs(output_dir, exist_ok=True)
        previous_map_id = project.active_map_id
        try:
            for map_model in project.maps.values():
                project.active_map_id = map_model.id
                safe_name = "".join(
                    ch if ch.isalnum() or ch in ("-", "_") else "_"
                    for ch in map_model.name
                ).strip("_") or map_model.id
                if not cls.export_png(
                    project,
                    render_engine,
                    os.path.join(output_dir, f"{safe_name}.png"),
                    **options,
                ):
                    return False
            return True
        finally:
            project.active_map_id = previous_map_id

    @staticmethod
    def export_collision_json(project: Project, file_path: str) -> bool:
        """Export collision, trigger and interaction data for every map."""
        try:
            payload = {
                "version": "1.0",
                "tile_size": project.tile_size,
                "maps": [
                    {
                        "id": map_model.id,
                        "name": map_model.name,
                        "width": map_model.map_width,
                        "height": map_model.map_height,
                        "tile_size": map_model.tile_size,
                        "layers": [
                            {
                                "id": layer.id,
                                "name": layer.name,
                                "type": layer.layer_type,
                                "collisions": [
                                    collision.to_dict()
                                    for collision in layer.collisions
                                ],
                                "objects": [
                                    {
                                        "id": obj.id,
                                        "x": obj.get_pixel_pos(map_model.tile_size)[0],
                                        "y": obj.get_pixel_pos(map_model.tile_size)[1],
                                        "type": obj.object_type,
                                        "z_index": obj.z_index,
                                        "interaction_label": obj.interaction_label,
                                        "interaction_radius": obj.interaction_radius,
                                        "properties": obj.properties,
                                        "property_types": obj.property_types,
                                    }
                                    for obj in layer.objects
                                    if (
                                        obj.interaction_label
                                        or obj.interaction_radius > 0
                                        or layer.layer_type == "object"
                                    )
                                ],
                            }
                            for layer in map_model.layers
                            if layer.layer_type in ("object", "collision")
                        ],
                    }
                    for map_model in project.maps.values()
                ],
            }
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            ProjectIO._atomic_write(file_path, payload)
            ProjectIO._last_error = None
            return True
        except Exception as exc:
            ProjectIO._set_error(
                f"Błąd eksportu kolizji '{file_path}': {exc}"
            )
            return False

    @classmethod
    def export_public_json(
        cls,
        project: Project,
        asset_manager: AssetManager,
        file_path: str,
        autotile_engine: Optional[Any] = None,
    ) -> bool:
        try:
            errors = cls.validate_project(project, asset_manager)
            if errors:
                cls._set_error("Eksport zablokowany: " + "; ".join(errors))
                return False
            base_dir = os.path.dirname(os.path.abspath(file_path))
            assets = []
            for asset in copy.deepcopy(asset_manager.to_dict().get("assets", [])):
                asset["file_path"] = safe_relative_asset_path(
                    base_dir, asset.get("file_path", "")
                )
                assets.append(asset)
            payload = {
                "format": "tileset-map-maker",
                "version": cls.FILE_VERSION,
                "project": project.to_dict(),
                "assets": assets,
            }
            if autotile_engine:
                payload["autotile"] = autotile_engine.to_dict()
            errors = schema_errors(payload)
            if errors:
                cls._set_error("Eksport narusza schemat: " + "; ".join(errors))
                return False
            cls._atomic_write(file_path, payload)
            cls._last_error = None
            return True
        except Exception as exc:
            cls._set_error(f"Błąd eksportu JSON '{file_path}': {exc}")
            return False

    @classmethod
    def export_bundle(
        cls,
        project: Project,
        asset_manager: AssetManager,
        render_engine: RenderEngine,
        output_dir: str,
        autotile_engine: Optional[Any] = None,
    ) -> bool:
        try:
            if cls.validate_project(project, asset_manager):
                cls._set_error("Eksport pakietu zablokowany przez walidację.")
                return False
            os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)
            map_dir = os.path.join(output_dir, "maps")
            os.makedirs(map_dir, exist_ok=True)
            for asset in asset_manager.assets.values():
                if not os.path.isfile(asset.file_path):
                    continue
                extension = os.path.splitext(asset.file_path)[1]
                destination = os.path.join(
                    output_dir,
                    "assets",
                    f"{asset.id}{extension}",
                )
                shutil.copy2(asset.file_path, destination)
            if not cls.export_maps_png(
                project, render_engine, map_dir, transparent_bg=True
            ):
                return False
            public_path = os.path.join(output_dir, "project.json")
            if not cls.export_public_json(
                project, asset_manager, public_path, autotile_engine
            ):
                return False
            with open(public_path, "r", encoding="utf-8") as handle:
                bundle_manifest = json.load(handle)
            for manifest_asset in bundle_manifest["assets"]:
                source = asset_manager.get_asset(manifest_asset["id"])
                if source and os.path.isfile(source.file_path):
                    extension = os.path.splitext(source.file_path)[1]
                    manifest_asset["file_path"] = (
                        f"assets/{source.id}{extension}"
                    )
            cls._atomic_write(public_path, bundle_manifest)
            if not cls.export_collision_json(
                project, os.path.join(output_dir, "gameplay.json")
            ):
                return False
            return True
        except Exception as exc:
            cls._set_error(f"Błąd eksportu pakietu '{output_dir}': {exc}")
            return False

    @classmethod
    def export_tmx(
        cls,
        project: Project,
        asset_manager: AssetManager,
        file_path: str,
    ) -> bool:
        try:
            TiledTMX.export_project(project, asset_manager, file_path)
            cls._last_error = None
            return True
        except (ExternalFormatError, OSError, ValueError) as exc:
            cls._set_error(f"Błąd eksportu TMX '{file_path}': {exc}")
            return False

    @classmethod
    def import_tmx(
        cls, file_path: str, asset_manager: AssetManager
    ) -> Optional[Project]:
        try:
            project = TiledTMX.import_project(file_path, asset_manager)
            project.file_path = None
            project.is_modified = True
            cls._last_error = None
            return project
        except (ET.ParseError, ExternalFormatError, OSError, ValueError) as exc:
            cls._set_error(f"Błąd importu TMX '{file_path}': {exc}")
            return None

    @classmethod
    def get_last_warnings(cls) -> List[str]:
        return list(TiledTMX.last_warnings)

    @classmethod
    def import_png_as_map(
        cls,
        file_path: str,
        asset_manager: AssetManager,
        mode: str = "reference",
        tile_size: int = 32,
        opacity: float = 0.55,
        target_project: Optional[Project] = None,
    ) -> Optional[Project]:
        """
        Imports a PNG image directly as a 1:1 raster map or reference underlay.
        Preserves original resolution and alpha transparency without modifying the source PNG.
        """
        import math
        from ..models.asset import AssetType
        from ..models.layer import MapItem, ItemType

        try:
            if not os.path.isfile(file_path):
                cls._set_error(f"Plik PNG nie istnieje: '{file_path}'")
                return None

            asset, _, err = asset_manager.import_single_file(
                file_path,
                target_category_path="Mapy PNG",
                force_asset_type=AssetType.SINGLE_IMAGE,
            )
            if not asset:
                cls._set_error(err or f"Nie udało się wczytać pliku PNG: '{file_path}'")
                return None

            pm = asset_manager.get_pixmap(asset.id)
            if not pm or pm.isNull():
                cls._set_error(f"Uszkodzony lub nieprawidłowy obraz PNG: '{file_path}'")
                return None

            img_w = pm.width()
            img_h = pm.height()
            ts = max(8, int(tile_size))
            cols = max(1, math.ceil(img_w / ts))
            rows = max(1, math.ceil(img_h / ts))
            map_name = os.path.splitext(os.path.basename(file_path))[0]

            if target_project is not None:
                project = target_project
                new_map = project.add_map(
                    name=map_name, width=cols, height=rows, tile_size=ts
                )
                project.set_active_map(new_map.id)
            else:
                project = Project(
                    name=map_name,
                    map_width=cols,
                    map_height=rows,
                    tile_size=ts,
                )
                project.is_bg_transparent = True

            project.layers.clear()
            is_ref = (mode == "reference")
            img_layer_name = "Podkład referencyjny (PNG)" if is_ref else "Mapa rastrowa (PNG)"
            img_layer = project.add_layer(img_layer_name, layer_type="object")
            img_layer.opacity = max(0.05, min(1.0, float(opacity if is_ref else 1.0)))
            img_layer.locked = True

            raster_item = MapItem(
                asset_id=asset.id,
                col=0,
                row=0,
                item_type=ItemType.OBJECT,
                source_x=0,
                source_y=0,
                source_w=img_w,
                source_h=img_h,
                dest_w=img_w,
                dest_h=img_h,
                object_type="png_map_reference" if is_ref else "png_map_raster",
            )
            img_layer.add_object(raster_item)

            # Add an editable tile layer on top so the user can paint tiles immediately
            tile_layer = project.add_layer("Warstwa kafelków 1", layer_type="tile")
            project.active_layer_id = tile_layer.id
            project.is_modified = True
            cls._last_error = None
            return project
        except Exception as exc:
            cls._set_error(f"Błąd importu mapy PNG '{file_path}': {exc}")
            return None

    @staticmethod
    def get_public_schema() -> Dict[str, Any]:
        return copy.deepcopy(PROJECT_JSON_SCHEMA)
