import os
import shutil
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from ..models.asset import AssetType, TilesetConfig
from ..models.layer import CollisionObject, CollisionShape, ItemType, MapItem
from ..models.project import Project
from .asset_manager import AssetManager


class ExternalFormatError(ValueError):
    pass


def resolve_safe_asset_path(
    base_dir: str, stored_path: str, allow_absolute: bool = True
) -> str:
    if os.path.isabs(stored_path):
        if not allow_absolute:
            raise ExternalFormatError(
                "Ścieżka zasobu w formacie zewnętrznym musi być relatywna."
            )
        return os.path.abspath(stored_path)
    base = os.path.realpath(base_dir)
    resolved = os.path.realpath(os.path.join(base, stored_path))
    try:
        common = os.path.commonpath((base, resolved))
    except ValueError as exc:
        raise ExternalFormatError("Ścieżka zasobu wychodzi poza katalog projektu.") from exc
    if common != base:
        raise ExternalFormatError(f"Niebezpieczna ścieżka zasobu: {stored_path!r}")
    return resolved


def safe_relative_asset_path(base_dir: str, asset_path: str) -> str:
    asset_path = os.path.abspath(asset_path)
    base_dir = os.path.abspath(base_dir)
    try:
        relative = os.path.relpath(asset_path, base_dir)
    except ValueError:
        return asset_path
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return asset_path
    return relative


class TiledTMX:
    """Orthogonal TMX 1.10 CSV import/export for the documented subset."""

    FLIP_H = 0x80000000
    FLIP_V = 0x40000000

    @staticmethod
    def _safe_filename(name: str, fallback: str) -> str:
        result = "".join(
            character if character.isalnum() or character in ("-", "_") else "_"
            for character in name
        ).strip("_")
        return result or fallback

    @classmethod
    def export_project(
        cls,
        project: Project,
        asset_manager: AssetManager,
        file_path: str,
    ) -> None:
        base_dir = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(base_dir, exist_ok=True)
        assets = [
            asset for asset in asset_manager.assets.values()
            if asset.asset_type in (AssetType.TILESET, AssetType.SINGLE_IMAGE)
        ]
        referenced_ids = {
            item.asset_id
            for map_model in project.maps.values()
            for layer in map_model.layers
            for item in list(layer.tiles.values()) + layer.objects
        }
        assets = [asset for asset in assets if asset.id in referenced_ids]
        map_model = project.get_active_map()
        root = ET.Element(
            "map",
            version="1.10",
            tiledversion="1.10.2",
            orientation="orthogonal",
            renderorder="right-down",
            width=str(map_model.map_width),
            height=str(map_model.map_height),
            tilewidth=str(map_model.tile_size),
            tileheight=str(map_model.tile_size),
            infinite="0",
        )
        cls._add_properties(
            root,
            {
                "tileset_map_maker.project_id": project.id,
                "tileset_map_maker.map_id": map_model.id,
            },
        )
        first_gid = 1
        gid_lookup: Dict[Tuple[str, int, int], int] = {}
        assets_dir = os.path.join(base_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        for asset_index, asset in enumerate(assets):
            columns, rows = asset.get_tileset_dimensions()
            if asset.asset_type == AssetType.SINGLE_IMAGE:
                columns = rows = 1
            if columns <= 0 or rows <= 0:
                continue
            tile_w = asset.tileset_config.tile_width if asset.tileset_config else map_model.tile_size
            tile_h = asset.tileset_config.tile_height if asset.tileset_config else map_model.tile_size
            tileset = ET.SubElement(
                root,
                "tileset",
                firstgid=str(first_gid),
                name=asset.name,
                tilewidth=str(tile_w),
                tileheight=str(tile_h),
                tilecount=str(columns * rows),
                columns=str(columns),
            )
            extension = os.path.splitext(asset.file_path)[1] or ".png"
            filename = f"{cls._safe_filename(asset.name, f'asset_{asset_index}')}_{asset.id[:8]}{extension}"
            copied_path = os.path.join(assets_dir, filename)
            shutil.copy2(asset.file_path, copied_path)
            image = ET.SubElement(
                tileset,
                "image",
                source=os.path.relpath(copied_path, base_dir).replace(os.sep, "/"),
                width=str(asset.width),
                height=str(asset.height),
            )
            image.set("tileset-map-maker.asset_id", asset.id)
            for row in range(rows):
                for col in range(columns):
                    source = asset.get_tile_rect(col, row)
                    gid_lookup[(asset.id, source[0], source[1])] = (
                        first_gid + row * columns + col
                    )
            first_gid += columns * rows

        next_object_id = 1
        for layer in map_model.layers:
            if layer.is_group:
                continue
            if layer.tiles:
                layer_node = ET.SubElement(
                    root,
                    "layer",
                    id=str(map_model.layers.index(layer) + 1),
                    name=layer.name,
                    width=str(map_model.map_width),
                    height=str(map_model.map_height),
                    visible="1" if layer.visible else "0",
                    opacity=str(layer.opacity),
                )
                cls._add_properties(
                    layer_node,
                    {
                        "tileset_map_maker.layer_type": layer.layer_type,
                        "tileset_map_maker.layer_id": layer.id,
                    },
                )
                values: List[int] = [0] * (
                    map_model.map_width * map_model.map_height
                )
                for (col, row), item in layer.tiles.items():
                    gid = gid_lookup.get((item.asset_id, item.source_x, item.source_y), 0)
                    if item.flip_x:
                        gid |= cls.FLIP_H
                    if item.flip_y:
                        gid |= cls.FLIP_V
                    if 0 <= col < map_model.map_width and 0 <= row < map_model.map_height:
                        values[row * map_model.map_width + col] = gid
                data = ET.SubElement(layer_node, "data", encoding="csv")
                data.text = ",".join(str(value) for value in values)

            object_group = ET.SubElement(
                root,
                "objectgroup",
                name=f"{layer.name} Objects",
                visible="1" if layer.visible else "0",
            )
            cls._add_properties(
                object_group,
                {
                    "tileset_map_maker.layer_type": layer.layer_type,
                    "tileset_map_maker.layer_id": layer.id,
                },
            )
            for obj in layer.objects:
                x, y = obj.get_pixel_pos(map_model.tile_size)
                object_node = ET.SubElement(
                    object_group,
                    "object",
                    id=str(next_object_id),
                    name=obj.object_type or obj.id,
                    type=obj.object_type,
                    x=str(x),
                    y=str(y),
                    width=str(obj.dest_w * abs(obj.scale_x)),
                    height=str(obj.dest_h * abs(obj.scale_y)),
                    rotation=str(obj.rotation),
                )
                next_object_id += 1
                props = dict(obj.properties)
                props.update(
                    {
                        "tileset_map_maker.object_id": obj.id,
                        "tileset_map_maker.asset_id": obj.asset_id,
                        "tileset_map_maker.source_x": obj.source_x,
                        "tileset_map_maker.source_y": obj.source_y,
                        "tileset_map_maker.interaction_label": obj.interaction_label,
                        "tileset_map_maker.interaction_radius": obj.interaction_radius,
                    }
                )
                cls._add_properties(object_node, props)
            for collision in layer.collisions:
                object_node = ET.SubElement(
                    object_group,
                    "object",
                    id=str(next_object_id),
                    name=collision.interaction_label or "Collision",
                    type="collision",
                    x=str(collision.x),
                    y=str(collision.y),
                    width=str(collision.width),
                    height=str(collision.height),
                )
                next_object_id += 1
                if collision.shape == CollisionShape.ELLIPSE:
                    ET.SubElement(object_node, "ellipse")
                cls._add_properties(
                    object_node,
                    {
                        **collision.properties,
                        "tileset_map_maker.blocking": collision.blocking,
                        "tileset_map_maker.trigger": collision.trigger,
                        "tileset_map_maker.collision_id": collision.id,
                    },
                )
            if len(object_group) == 0:
                root.remove(object_group)

        ET.indent(root, space="  ")
        ET.ElementTree(root).write(file_path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _add_properties(node: ET.Element, properties: Dict[str, object]) -> None:
        if not properties:
            return
        properties_node = ET.SubElement(node, "properties")
        for key, value in properties.items():
            if isinstance(value, bool):
                value_type = "bool"
                rendered = "true" if value else "false"
            elif isinstance(value, int):
                value_type = "int"
                rendered = str(value)
            elif isinstance(value, float):
                value_type = "float"
                rendered = str(value)
            else:
                value_type = "string"
                rendered = str(value)
            ET.SubElement(
                properties_node,
                "property",
                name=str(key),
                type=value_type,
                value=rendered,
            )

    @staticmethod
    def _properties(node: ET.Element) -> Dict[str, object]:
        values: Dict[str, object] = {}
        for prop in node.findall("./properties/property"):
            raw = prop.get("value", "")
            kind = prop.get("type", "string")
            if kind == "bool":
                values[prop.get("name", "")] = raw.casefold() == "true"
            elif kind == "int":
                values[prop.get("name", "")] = int(raw)
            elif kind == "float":
                values[prop.get("name", "")] = float(raw)
            else:
                values[prop.get("name", "")] = raw
        return values

    @classmethod
    def import_project(
        cls, file_path: str, asset_manager: AssetManager
    ) -> Project:
        root = ET.parse(file_path).getroot()
        if root.tag != "map" or root.get("orientation") != "orthogonal":
            raise ExternalFormatError("Obsługiwany jest wyłącznie ortogonalny TMX.")
        width = int(root.get("width", "0"))
        height = int(root.get("height", "0"))
        tile_width = int(root.get("tilewidth", "32"))
        tile_height = int(root.get("tileheight", "32"))
        if width <= 0 or height <= 0 or tile_width != tile_height:
            raise ExternalFormatError(
                "TMX musi mieć dodatnie wymiary i jednakowy rozmiar X/Y kafelka."
            )
        project = Project(
            name=os.path.splitext(os.path.basename(file_path))[0],
            map_width=width,
            map_height=height,
            tile_size=tile_width,
        )
        base_dir = os.path.dirname(os.path.abspath(file_path))
        gid_tiles: Dict[int, Tuple[str, int, int, int, int]] = {}
        for tileset_node in root.findall("tileset"):
            source = tileset_node.get("source")
            if source:
                source_path = resolve_safe_asset_path(
                    base_dir, source, allow_absolute=False
                )
                ts_root = ET.parse(source_path).getroot()
                image_node = ts_root.find("image")
                effective = ts_root
                first_gid = int(tileset_node.get("firstgid", "1"))
            else:
                image_node = tileset_node.find("image")
                effective = tileset_node
                first_gid = int(tileset_node.get("firstgid", "1"))
            if image_node is None:
                continue
            image_source = image_node.get("source")
            if not image_source:
                continue
            source_dir = base_dir
            if source:
                source_dir = os.path.dirname(source_path)
            image_path = resolve_safe_asset_path(
                source_dir, image_source, allow_absolute=False
            )
            if not os.path.isfile(image_path):
                continue
            asset, _, error = asset_manager.import_single_file(
                image_path, target_category_path="Tiled", force_asset_type=AssetType.TILESET
            )
            if not asset:
                raise ExternalFormatError(error or f"Nie udało się zaimportować: {image_path}")
            tw = int(effective.get("tilewidth", tile_width))
            th = int(effective.get("tileheight", tile_height))
            columns = int(effective.get("columns", "1"))
            tile_count = int(
                effective.get("tilecount", str(max(1, asset.width // tw * asset.height // th)))
            )
            asset.tileset_config = TilesetConfig(tile_width=tw, tile_height=th)
            for local_id in range(tile_count):
                col = local_id % max(1, columns)
                row = local_id // max(1, columns)
                gid_tiles[first_gid + local_id] = (
                    asset.id, col * tw, row * th, tw, th
                )

        project.layers.clear()
        layer_lookup: Dict[str, object] = {}
        for layer_node in root.findall("layer"):
            props = cls._properties(layer_node)
            layer = project.add_layer(
                layer_node.get("name", "Tiled Layer"),
                layer_type=str(
                    props.get("tileset_map_maker.layer_type", "tile")
                ),
            )
            layer.id = str(props.get("tileset_map_maker.layer_id", layer.id))
            layer.visible = layer_node.get("visible", "1") == "1"
            layer.opacity = float(layer_node.get("opacity", "1"))
            layer_lookup[layer.id] = layer
            data_node = layer_node.find("data")
            if data_node is None or data_node.get("encoding") != "csv":
                raise ExternalFormatError("Obsługiwane są tylko warstwy CSV.")
            values = [
                int(value.strip())
                for value in (data_node.text or "").replace("\n", "").split(",")
                if value.strip()
            ]
            if len(values) != width * height:
                raise ExternalFormatError("Liczba komórek CSV nie zgadza się z wymiarami mapy.")
            for index, gid_value in enumerate(values):
                flip_x = bool(gid_value & cls.FLIP_H)
                flip_y = bool(gid_value & cls.FLIP_V)
                gid = gid_value & ~(cls.FLIP_H | cls.FLIP_V)
                if gid == 0:
                    continue
                tile = gid_tiles.get(gid)
                if not tile:
                    continue
                item = MapItem(
                    tile[0],
                    index % width,
                    index // width,
                    source_x=tile[1],
                    source_y=tile[2],
                    source_w=tile[3],
                    source_h=tile[4],
                    dest_w=tile_width,
                    dest_h=tile_height,
                    flip_x=flip_x,
                    flip_y=flip_y,
                )
                layer.set_tile(item.col, item.row, item)

        for group in root.findall("objectgroup"):
            props = cls._properties(group)
            requested_id = str(props.get("tileset_map_maker.layer_id", ""))
            layer = layer_lookup.get(requested_id)
            if not layer:
                layer = project.add_layer(
                    group.get("name", "Objects"),
                    layer_type=str(
                        props.get("tileset_map_maker.layer_type", "object")
                    ),
                )
                if requested_id:
                    layer.id = requested_id
            for object_node in group.findall("object"):
                object_props = cls._properties(object_node)
                x = float(object_node.get("x", "0"))
                y = float(object_node.get("y", "0"))
                w = float(object_node.get("width", "1"))
                h = float(object_node.get("height", "1"))
                if object_node.get("type") == "collision":
                    collision = CollisionObject(
                        x, y, w, h,
                        shape=(
                            CollisionShape.ELLIPSE
                            if object_node.find("ellipse") is not None
                            else CollisionShape.RECTANGLE
                        ),
                        collision_id=str(
                            object_props.pop(
                                "tileset_map_maker.collision_id", ""
                            )
                        ) or None,
                        blocking=bool(
                            object_props.pop(
                                "tileset_map_maker.blocking", True
                            )
                        ),
                        trigger=bool(
                            object_props.pop("tileset_map_maker.trigger", False)
                        ),
                        interaction_label=object_node.get("name", ""),
                        properties=object_props,
                    )
                    layer.add_collision(collision)
                    continue
                asset_id = str(
                    object_props.pop("tileset_map_maker.asset_id", "")
                )
                item = MapItem(
                    asset_id,
                    int(x // tile_width),
                    int(y // tile_height),
                    item_type=ItemType.OBJECT,
                    free_x=x,
                    free_y=y,
                    source_x=int(
                        object_props.pop("tileset_map_maker.source_x", 0)
                    ),
                    source_y=int(
                        object_props.pop("tileset_map_maker.source_y", 0)
                    ),
                    source_w=int(w),
                    source_h=int(h),
                    dest_w=max(1, int(w)),
                    dest_h=max(1, int(h)),
                    rotation=float(object_node.get("rotation", "0")),
                    item_id=str(
                        object_props.pop("tileset_map_maker.object_id", "")
                    ) or None,
                    object_type=object_node.get(
                        "type", object_node.get("name", "")
                    ),
                    interaction_label=str(
                        object_props.pop(
                            "tileset_map_maker.interaction_label", ""
                        )
                    ),
                    interaction_radius=float(
                        object_props.pop(
                            "tileset_map_maker.interaction_radius", 0.0
                        )
                    ),
                    properties=object_props,
                )
                layer.add_object(item)
        project.active_map_id = project.get_active_map().id
        if not project.layers:
            project.add_layer("Imported")
        return project
