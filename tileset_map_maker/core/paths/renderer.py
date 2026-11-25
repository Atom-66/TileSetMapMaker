from typing import Any, Dict, List, Optional, Tuple

from ...models.layer import ItemType, Layer, MapItem
from ...models.project import Project
from .models import Placement


class PathMapRenderer:
    """
    Commits solved Placement objects onto a map Layer while preserving strict
    separation between tileset source rectangles, logical variant/composition
    metadata, and map coordinates — with atomic Undo/Redo state tracking.
    """

    @staticmethod
    def commit_placements(
        layer: Layer,
        placements: List[Placement],
        autotile: Any,
        project: Optional[Project],
        initial_states: Dict[Tuple[int, int], Optional[MapItem]],
        changes: Dict[Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]],
    ) -> None:
        dest_ts = project.tile_size if project else autotile.tile_size

        for pl in placements:
            for (fc, fr), (sx, sy, sw, sh) in pl.cell_slices.items():
                if project and not (0 <= fc < project.map_width and 0 <= fr < project.map_height):
                    continue
                existing = layer.get_tile(fc, fr)
                if (fc, fr) not in initial_states:
                    initial_states[(fc, fr)] = existing.clone() if existing else None

                if existing is None:
                    tile = MapItem(
                        asset_id=pl.source_asset_id,
                        col=fc,
                        row=fr,
                        item_type=ItemType.TILE,
                        source_x=sx,
                        source_y=sy,
                        source_w=sw,
                        source_h=sh,
                        dest_w=dest_ts,
                        dest_h=dest_ts,
                        is_auto_tiled=True,
                        terrain_type=autotile.terrain_type,
                        properties={},
                    )
                    layer.set_tile(fc, fr, tile)
                else:
                    tile = existing
                    tile.asset_id = pl.source_asset_id
                    tile.source_x = sx
                    tile.source_y = sy
                    tile.source_w = sw
                    tile.source_h = sh
                    tile.dest_w = dest_ts
                    tile.dest_h = dest_ts
                    tile.is_auto_tiled = True
                    tile.terrain_type = autotile.terrain_type

                if not isinstance(tile.properties, dict):
                    tile.properties = {}
                tile.properties["autotile_id"] = autotile.id

                if pl.is_composition:
                    tile.properties["composition_origin"] = [pl.origin_col, pl.origin_row]
                    tile.properties["composition_size"] = [pl.width_tiles, pl.height_tiles]
                    tile.properties.pop("variant_origin", None)
                    tile.properties.pop("variant_size", None)
                    tile.properties.pop("variant_id", None)
                elif pl.variant_id is not None:
                    tile.properties["variant_id"] = pl.variant_id
                    tile.properties["variant_origin"] = [pl.origin_col, pl.origin_row]
                    tile.properties["variant_size"] = [pl.width_tiles, pl.height_tiles]
                    tile.properties.pop("composition_origin", None)
                    tile.properties.pop("composition_size", None)
                else:
                    tile.properties.pop("variant_id", None)
                    tile.properties.pop("variant_origin", None)
                    tile.properties.pop("variant_size", None)
                    tile.properties.pop("composition_origin", None)
                    tile.properties.pop("composition_size", None)

                changes[(fc, fr)] = (initial_states.get((fc, fr)), tile.clone())
