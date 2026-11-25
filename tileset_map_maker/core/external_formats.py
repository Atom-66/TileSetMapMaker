import base64
import gzip
import os
import shutil
import struct
import xml.etree.ElementTree as ET
import zlib
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
    """Full orthogonal TMX 1.10 import/export (XML, CSV, Base64 raw/zlib/gzip, TSX, flips & rotations)."""

    FLIP_H = 0x80000000
    FLIP_V = 0x40000000
    FLIP_D = 0x20000000
    ALL_FLIP_FLAGS = FLIP_H | FLIP_V | FLIP_D

    last_warnings: List[str] = []

    @classmethod
    def decode_gid_flags(cls, raw_gid: int) -> Tuple[int, float, bool, bool]:
        """Decodes a Tiled GID into (clean_gid, rotation_deg, flip_x, flip_y)."""
        fh = bool(raw_gid & cls.FLIP_H)
        fv = bool(raw_gid & cls.FLIP_V)
        fd = bool(raw_gid & cls.FLIP_D)
        gid = raw_gid & ~cls.ALL_FLIP_FLAGS
        if not fd:
            if fh and fv:
                return gid, 180.0, False, False
            return gid, 0.0, fh, fv
        # Anti-diagonal flip present
        if fh and not fv:
            return gid, 90.0, False, False
        if fv and not fh:
            return gid, 270.0, False, False
        if fh and fv:
            return gid, 90.0, True, False
        return gid, 90.0, False, True

    @classmethod
    def encode_gid_flags(
        cls, gid: int, rotation: float = 0.0, flip_x: bool = False, flip_y: bool = False
    ) -> int:
        """Encodes (gid, rotation, flip_x, flip_y) into a Tiled GID with H/V/D flags."""
        if gid <= 0:
            return 0
        rot = int(round(rotation)) % 360
        flags = 0
        if rot == 90:
            if flip_x and not flip_y:
                flags = cls.FLIP_H | cls.FLIP_V | cls.FLIP_D
            elif flip_y and not flip_x:
                flags = cls.FLIP_D
            elif flip_x and flip_y:
                flags = cls.FLIP_V | cls.FLIP_D
            else:
                flags = cls.FLIP_H | cls.FLIP_D
        elif rot == 180:
            if not flip_x:
                flags |= cls.FLIP_H
            if not flip_y:
                flags |= cls.FLIP_V
        elif rot == 270:
            if flip_x and not flip_y:
                flags = cls.FLIP_D
            elif flip_y and not flip_x:
                flags = cls.FLIP_H | cls.FLIP_V | cls.FLIP_D
            elif flip_x and flip_y:
                flags = cls.FLIP_H | cls.FLIP_D
            else:
                flags = cls.FLIP_V | cls.FLIP_D
        else:
            if flip_x:
                flags |= cls.FLIP_H
            if flip_y:
                flags |= cls.FLIP_V
        return gid | flags

    @classmethod
    def _decode_layer_data(cls, data_node: ET.Element, expected_count: int) -> List[int]:
        """Decodes TMX <data> from CSV, XML <tile/>, or Base64 (raw, zlib, gzip, zstd)."""
        encoding = (data_node.get("encoding") or "").strip().lower()
        compression = (data_node.get("compression") or "").strip().lower()

        if encoding == "csv":
            values = [
                int(v.strip())
                for v in (data_node.text or "").replace("\n", "").replace("\r", "").split(",")
                if v.strip()
            ]
        elif encoding == "base64":
            raw_b64 = (data_node.text or "").strip()
            raw_bytes = base64.b64decode(raw_b64) if raw_b64 else b""
            if compression == "zlib":
                raw_bytes = zlib.decompress(raw_bytes)
            elif compression == "gzip":
                raw_bytes = gzip.decompress(raw_bytes)
            elif compression == "zstd":
                try:
                    import zstandard
                    raw_bytes = zstandard.ZstdDecompressor().decompress(raw_bytes)
                except ImportError as exc:
                    raise ExternalFormatError(
                        "Kompresja Base64 zstd wymaga pakietu 'zstandard'."
                    ) from exc
            elif compression:
                raise ExternalFormatError(f"Nieobsługiwana kompresja TMX: {compression!r}")
            if len(raw_bytes) % 4 != 0:
                raise ExternalFormatError("Uszkodzony strumień Base64 w warstwie TMX.")
            count = len(raw_bytes) // 4
            values = list(struct.unpack(f"<{count}I", raw_bytes))
        elif encoding == "":
            # Plain XML <tile gid="..."/>
            values = [int(t.get("gid", "0")) for t in data_node.findall("tile")]
        else:
            raise ExternalFormatError(f"Nieobsługiwane kodowanie warstwy TMX: {encoding!r}")

        if len(values) != expected_count:
            raise ExternalFormatError(
                f"Liczba komórek warstwy ({len(values)}) nie zgadza się z wymiarami mapy ({expected_count})."
            )
        return values

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
        assets = [
            asset
            for asset in assets
            if asset.id in referenced_ids
            or (
                asset.tileset_config
                and asset.tileset_config.tiled_first_gid is not None
            )
        ]
        assets.sort(
            key=lambda asset: (
                asset.tileset_config.tiled_first_gid
                if asset.tileset_config
                and asset.tileset_config.tiled_first_gid is not None
                else float("inf"),
                asset.name.casefold(),
            )
        )
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
        if not map_model.is_bg_transparent:
            root.set("backgroundcolor", map_model.background_color)
        map_properties = dict(map_model.properties)
        map_properties.update({
                "tileset_map_maker.project_id": project.id,
                "tileset_map_maker.map_id": map_model.id,
            })
        cls._add_properties(root, map_properties)
        first_gid = 1
        gid_lookup: Dict[Tuple[str, int, int], int] = {}
        gid_to_tileset: Dict[int, ET.Element] = {}
        assets_dir = os.path.join(base_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        for asset_index, asset in enumerate(assets):
            columns, rows = asset.get_tileset_dimensions()
            if asset.asset_type == AssetType.SINGLE_IMAGE:
                columns = rows = 1
            if columns <= 0 or rows <= 0:
                continue
            config = asset.tileset_config
            tile_w = config.tile_width if config else map_model.tile_size
            tile_h = config.tile_height if config else map_model.tile_size
            columns = config.tiled_columns or columns if config else columns
            tile_count = (
                config.tiled_tile_count
                if config and config.tiled_tile_count is not None
                else columns * rows
            )
            tile_count = max(tile_count, 1)
            asset_first_gid = (
                config.tiled_first_gid
                if config and config.tiled_first_gid is not None
                else first_gid
            )
            if asset_first_gid < first_gid:
                raise ExternalFormatError(
                    f"Tileset '{asset.name}' ma firstgid {asset_first_gid}, który koliduje z wcześniejszym tilesetem."
                )
            tileset = ET.SubElement(
                root,
                "tileset",
                firstgid=str(asset_first_gid),
                name=(config.tiled_name if config and config.tiled_name else asset.name),
                tilewidth=str(tile_w),
                tileheight=str(tile_h),
                tilecount=str(tile_count),
                columns=str(columns),
            )
            if config:
                if config.margin_x:
                    tileset.set("margin", str(config.margin_x))
                if config.spacing_x:
                    tileset.set("spacing", str(config.spacing_x))
            if config and (config.tile_offset_x or config.tile_offset_y):
                ET.SubElement(
                    tileset,
                    "tileoffset",
                    x=str(config.tile_offset_x),
                    y=str(config.tile_offset_y),
                )
            if config:
                for local_id, tile_properties in sorted(
                    config.tiled_tile_properties.items(),
                    key=lambda entry: int(entry[0]),
                ):
                    tile_node = ET.SubElement(
                        tileset, "tile", id=str(int(local_id))
                    )
                    cls._add_properties(tile_node, tile_properties)
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
            for local_id in range(tile_count):
                col = local_id % columns
                row = local_id // columns
                source = asset.get_tile_rect(col, row)
                gid = asset_first_gid + local_id
                gid_lookup[(asset.id, source[0], source[1])] = gid
                gid_to_tileset[gid] = tileset
            first_gid = asset_first_gid + tile_count

        next_object_id = 1
        tile_properties_by_gid: Dict[int, Dict[str, object]] = {}
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
                    offsetx=str(layer.offset_x),
                    offsety=str(layer.offset_y),
                )
                layer_properties = dict(layer.properties)
                layer_properties.update({
                        "tileset_map_maker.layer_type": layer.layer_type,
                        "tileset_map_maker.layer_id": layer.id,
                    })
                cls._add_properties(layer_node, layer_properties)
                values: List[int] = [0] * (
                    map_model.map_width * map_model.map_height
                )
                for (col, row), item in layer.tiles.items():
                    gid = gid_lookup.get((item.asset_id, item.source_x, item.source_y), 0)
                    tile_properties = item.properties.get("tiled_tile_properties")
                    if gid and isinstance(tile_properties, dict) and tile_properties:
                        existing = tile_properties_by_gid.get(gid)
                        if existing is not None and existing != tile_properties:
                            raise ExternalFormatError(
                                f"Tileset GID {gid} ma sprzeczne właściwości kafelka."
                            )
                        tile_properties_by_gid[gid] = dict(tile_properties)
                    gid = cls.encode_gid_flags(gid, item.rotation, item.flip_x, item.flip_y)
                    if 0 <= col < map_model.map_width and 0 <= row < map_model.map_height:
                        values[row * map_model.map_width + col] = gid
                data = ET.SubElement(layer_node, "data", encoding="csv")
                data.text = ",".join(str(value) for value in values)

            object_group = ET.SubElement(
                root,
                "objectgroup",
                name=f"{layer.name} Objects",
                visible="1" if layer.visible else "0",
                opacity=str(layer.opacity),
                offsetx=str(layer.offset_x),
                offsety=str(layer.offset_y),
            )
            object_group_properties = dict(layer.properties)
            object_group_properties.update({
                    "tileset_map_maker.layer_type": layer.layer_type,
                    "tileset_map_maker.layer_id": layer.id,
                })
            cls._add_properties(object_group, object_group_properties)
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

        for gid, properties in tile_properties_by_gid.items():
            tileset = gid_to_tileset.get(gid)
            if tileset is None:
                continue
            firstgid = int(tileset.get("firstgid", "1"))
            local_id = gid - firstgid
            tile_node = next(
                (
                    child
                    for child in tileset.findall("tile")
                    if int(child.get("id", "-1")) == local_id
                ),
                None,
            )
            if tile_node is not None:
                configured_properties = cls._properties(tile_node)
                if configured_properties != properties:
                    raise ExternalFormatError(
                        f"Tileset GID {gid} ma właściwości kafelka niezgodne z zapisanym tilesetem."
                    )
                continue
            tile_node = ET.Element("tile", id=str(local_id))
            cls._add_properties(tile_node, properties)
            image_node = tileset.find("image")
            insertion_index = (
                list(tileset).index(image_node)
                if image_node is not None
                else len(tileset)
            )
            tileset.insert(insertion_index, tile_node)

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
            raw = prop.get("value", prop.text or "")
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
        cls.last_warnings = []
        root = ET.parse(file_path).getroot()
        if root.tag != "map":
            raise ExternalFormatError("Plik TMX nie zawiera głównego elementu <map>.")
        orientation = root.get("orientation", "orthogonal")
        if orientation != "orthogonal":
            raise ExternalFormatError(
                f"Obsługiwany jest wyłącznie ortogonalny TMX (otrzymano: {orientation!r})."
            )
        render_order = root.get("renderorder", "right-down")
        if render_order != "right-down":
            cls.last_warnings.append(
                f"Kolejność renderowania '{render_order}' nie jest odtwarzana; użyto kolejności right-down."
            )
        if root.get("infinite") == "1" and root.findall(".//chunk"):
            raise ExternalFormatError(
                "Mapy nieskończone TMX z chunkami nie są obsługiwane; wyeksportuj mapę jako skończoną w Tiled."
            )
        width = int(root.get("width", "0"))
        height = int(root.get("height", "0"))
        tile_width = int(root.get("tilewidth", "32"))
        tile_height = int(root.get("tileheight", "32"))
        if width <= 0 or height <= 0 or tile_width <= 0 or tile_height <= 0:
            raise ExternalFormatError(
                "TMX musi mieć dodatnie wymiary mapy i kafelków."
            )
        if tile_width != tile_height:
            cls.last_warnings.append(
                f"Niekwardratowe kafelki TMX ({tile_width}×{tile_height} px) — użyto rozmiaru siatki {tile_width} px."
            )
        project = Project(
            name=os.path.splitext(os.path.basename(file_path))[0],
            map_width=width,
            map_height=height,
            tile_size=tile_width,
            background_color=root.get("backgroundcolor", "#22242a"),
        )
        project.get_active_map().is_bg_transparent = not bool(
            root.get("backgroundcolor")
        )
        map_props = cls._properties(root)
        if map_props:
            project.get_active_map().properties = dict(map_props)

        base_dir = os.path.dirname(os.path.abspath(file_path))
        gid_tiles: Dict[
            int, Tuple[str, int, int, int, int, int, int, int, int, Dict[str, object]]
        ] = {}
        for tileset_node in root.findall("tileset"):
            source = tileset_node.get("source")
            first_gid = int(tileset_node.get("firstgid", "1"))
            if source:
                source_path = resolve_safe_asset_path(
                    base_dir, source, allow_absolute=False
                )
                if not os.path.isfile(source_path):
                    cls.last_warnings.append(f"Brakujący plik tilesetu TSX: {source}")
                    continue
                ts_root = ET.parse(source_path).getroot()
                image_node = ts_root.find("image")
                effective = ts_root
                source_dir = os.path.dirname(source_path)
            else:
                image_node = tileset_node.find("image")
                effective = tileset_node
                source_dir = base_dir

            # Support collection-of-images tilesets (<tile id="..."><image source="..."/></tile>)
            tile_offset = effective.find("tileoffset")
            tile_offset_x = int(tile_offset.get("x", "0")) if tile_offset is not None else 0
            tile_offset_y = int(tile_offset.get("y", "0")) if tile_offset is not None else 0
            tile_properties = {
                int(tnode.get("id", "0")): cls._properties(tnode)
                for tnode in effective.findall("tile")
                if tnode.find("./properties/property") is not None
            }
            if image_node is None:
                tile_nodes = effective.findall("tile")
                if tile_nodes:
                    for tnode in tile_nodes:
                        t_img = tnode.find("image")
                        if t_img is None or not t_img.get("source"):
                            continue
                        local_id = int(tnode.get("id", "0"))
                        img_src = t_img.get("source", "")
                        img_path = resolve_safe_asset_path(source_dir, img_src, allow_absolute=False)
                        if not os.path.isfile(img_path):
                            cls.last_warnings.append(f"Brakujący obraz kafelka TMX: {img_src}")
                            continue
                        asset, _, err = asset_manager.import_single_file(
                            img_path, target_category_path="Tiled", force_asset_type=AssetType.SINGLE_IMAGE
                        )
                        if asset:
                            asset.tileset_config = TilesetConfig(
                                tile_width=asset.width,
                                tile_height=asset.height,
                                tile_offset_x=tile_offset_x,
                                tile_offset_y=tile_offset_y,
                                tiled_first_gid=first_gid + local_id,
                                tiled_tile_count=1,
                                tiled_columns=1,
                                tiled_name=f"{effective.get('name', asset.name)}_{local_id}",
                                tiled_tile_properties=(
                                    {"0": tile_properties[local_id]}
                                    if local_id in tile_properties
                                    else {}
                                ),
                            )
                            gid_tiles[first_gid + local_id] = (
                                asset.id,
                                0,
                                0,
                                asset.width,
                                asset.height,
                                asset.width,
                                asset.height,
                                tile_offset_x,
                                tile_offset_y,
                                tile_properties.get(local_id, {}),
                            )
                else:
                    cls.last_warnings.append(f"Tileset (firstgid={first_gid}) nie zawiera definicji obrazu.")
                continue

            image_source = image_node.get("source")
            if not image_source:
                continue
            image_path = resolve_safe_asset_path(
                source_dir, image_source, allow_absolute=False
            )
            if not os.path.isfile(image_path):
                cls.last_warnings.append(f"Brakujący plik grafiki tilesetu: {image_source}")
                continue
            asset, _, error = asset_manager.import_single_file(
                image_path, target_category_path="Tiled", force_asset_type=AssetType.TILESET
            )
            if not asset:
                cls.last_warnings.append(error or f"Nie udało się zaimportować: {image_path}")
                continue
            tw = int(effective.get("tilewidth", tile_width))
            th = int(effective.get("tileheight", tile_height))
            margin = int(effective.get("margin", "0"))
            spacing = int(effective.get("spacing", "0"))
            columns_raw = int(effective.get("columns", "0"))
            if columns_raw <= 0:
                columns = max(1, (asset.width - 2 * margin + spacing) // max(1, tw + spacing))
            else:
                columns = columns_raw
            rows_calc = max(1, (asset.height - 2 * margin + spacing) // max(1, th + spacing))
            tile_count = int(effective.get("tilecount", str(max(1, columns * rows_calc))))
            asset.tileset_config = TilesetConfig(
                tile_width=tw, tile_height=th, margin_x=margin, margin_y=margin,
                spacing_x=spacing, spacing_y=spacing,
                tile_offset_x=tile_offset_x,
                tile_offset_y=tile_offset_y,
                tiled_first_gid=first_gid,
                tiled_tile_count=tile_count,
                tiled_columns=columns,
                tiled_name=effective.get("name", asset.name),
                tiled_tile_properties={
                    str(local_id): properties
                    for local_id, properties in tile_properties.items()
                },
            )
            for local_id in range(tile_count):
                col = local_id % max(1, columns)
                row = local_id // max(1, columns)
                sx = margin + col * (tw + spacing)
                sy = margin + row * (th + spacing)
                gid_tiles[first_gid + local_id] = (
                    asset.id,
                    sx,
                    sy,
                    tw,
                    th,
                    tw,
                    th,
                    tile_offset_x,
                    tile_offset_y - (th - tile_height),
                    tile_properties.get(local_id, {}),
                )

        if root.findall("group"):
            cls.last_warnings.append("Wykryto zagnieżdżone grupy <group> w TMX.")

        project.layers.clear()
        layer_lookup: Dict[str, object] = {}
        layer_document_order: Dict[str, int] = {}
        for layer_node in root.findall("layer"):
            props = cls._properties(layer_node)
            layer_properties = {
                key: value
                for key, value in props.items()
                if key not in {
                    "tileset_map_maker.layer_type",
                    "tileset_map_maker.layer_id",
                }
            }
            layer_offset_x = (
                float(layer_node.get("x", "0")) * tile_width
                + float(layer_node.get("offsetx", "0"))
            )
            layer_offset_y = (
                float(layer_node.get("y", "0")) * tile_height
                + float(layer_node.get("offsety", "0"))
            )
            layer = project.add_layer(
                layer_node.get("name", "Tiled Layer"),
                layer_type=str(
                    props.get("tileset_map_maker.layer_type", "tile")
                ),
            )
            layer.id = str(props.get("tileset_map_maker.layer_id", layer.id))
            layer.visible = layer_node.get("visible", "1") == "1"
            layer.opacity = float(layer_node.get("opacity", "1"))
            layer.offset_x = layer_offset_x
            layer.offset_y = layer_offset_y
            layer.properties = layer_properties
            layer_lookup[layer.id] = layer
            layer_document_order[layer.id] = list(root).index(layer_node)
            data_node = layer_node.find("data")
            if data_node is None:
                cls.last_warnings.append(f"Warstwa '{layer.name}' nie zawiera węzła <data>.")
                continue
            layer_width = int(layer_node.get("width", str(width)))
            layer_height = int(layer_node.get("height", str(height)))
            if layer_width <= 0 or layer_height <= 0:
                raise ExternalFormatError(
                    f"Warstwa '{layer.name}' ma nieprawidłowe wymiary."
                )
            values = cls._decode_layer_data(
                data_node, layer_width * layer_height
            )
            for index, gid_value in enumerate(values):
                gid, rotation, flip_x, flip_y = cls.decode_gid_flags(gid_value)
                if gid == 0:
                    continue
                tile = gid_tiles.get(gid)
                if not tile:
                    continue
                item = MapItem(
                    tile[0],
                    index % layer_width,
                    index // layer_width,
                    source_x=tile[1],
                    source_y=tile[2],
                    source_w=tile[3],
                    source_h=tile[4],
                    dest_w=tile[5],
                    dest_h=tile[6],
                    offset_x=tile[7],
                    offset_y=tile[8],
                    rotation=rotation,
                    flip_x=flip_x,
                    flip_y=flip_y,
                    properties={"tiled_tile_properties": tile[9]} if tile[9] else {},
                )
                layer.set_tile(item.col, item.row, item)

        for group in root.findall("objectgroup"):
            props = cls._properties(group)
            layer_properties = {
                key: value
                for key, value in props.items()
                if key not in {
                    "tileset_map_maker.layer_type",
                    "tileset_map_maker.layer_id",
                }
            }
            group_offset_x = float(group.get("offsetx", "0"))
            group_offset_y = float(group.get("offsety", "0"))
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
            layer.visible = group.get("visible", "1") == "1"
            layer.opacity = float(group.get("opacity", "1"))
            layer.offset_x = group_offset_x
            layer.offset_y = group_offset_y
            layer.properties = layer_properties
            group_order = list(root).index(group)
            layer_document_order[layer.id] = min(
                layer_document_order.get(layer.id, group_order), group_order
            )
            for object_node in group.findall("object"):
                object_props = cls._properties(object_node)
                x = float(object_node.get("x", "0"))
                y = float(object_node.get("y", "0"))
                w = float(object_node.get("width", "1"))
                h = float(object_node.get("height", "1"))
                if object_node.get("gid"):
                    cls.last_warnings.append(
                        f"Obiekt kafelkowy '{object_node.get('name', object_node.get('id', '?'))}' nie jest obsługiwany."
                    )
                    continue
                if object_node.get("type") == "collision":
                    if any(
                        object_node.find(shape) is not None
                        for shape in ("polygon", "polyline", "point", "text")
                    ):
                        cls.last_warnings.append(
                            f"Obiekt kolizji '{object_node.get('name', object_node.get('id', '?'))}' używa nieobsługiwanego kształtu."
                        )
                        continue
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
        for image_layer in root.findall("imagelayer"):
            image_node = image_layer.find("image")
            if image_node is None or not image_node.get("source"):
                cls.last_warnings.append(
                    f"Warstwa obrazu '{image_layer.get('name', 'Image Layer')}' nie zawiera obrazu."
                )
                continue
            image_source = image_node.get("source", "")
            image_path = resolve_safe_asset_path(
                base_dir, image_source, allow_absolute=False
            )
            if not os.path.isfile(image_path):
                cls.last_warnings.append(
                    f"Brakujący obraz warstwy '{image_layer.get('name', 'Image Layer')}': {image_source}"
                )
                continue
            image_asset, _, error = asset_manager.import_single_file(
                image_path,
                target_category_path="Tiled",
                force_asset_type=AssetType.SINGLE_IMAGE,
            )
            if not image_asset:
                cls.last_warnings.append(error or f"Nie udało się zaimportować obrazu: {image_source}")
                continue
            layer = project.add_layer(
                image_layer.get("name", "Image Layer"), layer_type="object"
            )
            layer.visible = image_layer.get("visible", "1") == "1"
            layer.opacity = float(image_layer.get("opacity", "1"))
            layer.offset_x = float(image_layer.get("offsetx", "0"))
            layer.offset_y = float(image_layer.get("offsety", "0"))
            x = float(image_layer.get("x", "0")) * tile_width
            y = float(image_layer.get("y", "0")) * tile_height
            layer.add_object(
                MapItem(
                    image_asset.id,
                    int(x // tile_width),
                    int(y // tile_height),
                    item_type=ItemType.OBJECT,
                    source_w=image_asset.width,
                    source_h=image_asset.height,
                    dest_w=image_asset.width,
                    dest_h=image_asset.height,
                    free_x=x,
                    free_y=y,
                    object_type="tiled_image_layer",
                )
            )
            layer_document_order[layer.id] = list(root).index(image_layer)
            if image_node.get("trans"):
                cls.last_warnings.append(
                    f"Kolor transparentny warstwy obrazu '{layer.name}' nie jest stosowany."
                )
        project.layers.sort(
            key=lambda layer: layer_document_order.get(layer.id, len(root))
        )
        project.active_map_id = project.get_active_map().id
        if not project.layers:
            project.add_layer("Imported")
        return project
