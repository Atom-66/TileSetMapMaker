from typing import Dict, Optional, Tuple

from .autotile_engine import AutoTileEngine
from .history import Command, TileBatchCommand
from ..models.layer import MapItem
from ..models.project import Project
from ..models.terrain import TerrainConfig, TerrainResult, TerrainType


class TerrainApplyCommand(Command):
    """Apply one generated terrain snapshot to a layer using existing history."""

    def __init__(
        self,
        project: Project,
        layer_id: str,
        result: TerrainResult,
        config: TerrainConfig,
        autotile_engine: Optional[AutoTileEngine] = None,
    ):
        super().__init__("Generowanie terenu")
        self.project = project
        self.layer_id = layer_id
        self.autotile_engine = autotile_engine
        self.changes: Dict[
            Tuple[int, int], Tuple[Optional[MapItem], Optional[MapItem]]
        ] = {}
        layer = project.get_layer(layer_id)
        if layer is None:
            return

        rpg_by_name = {
            terrain.name.casefold(): (
                autotile_engine.get_rpg_autotile(
                    config.ruleset_ids.get(terrain.name.casefold())
                )
                if autotile_engine
                else None
            )
            for terrain in TerrainType
        }
        for row in range(min(result.height, project.map_height)):
            for col in range(min(result.width, project.map_width)):
                terrain = result.get(col, row)
                key = terrain.name.casefold()
                mapping = config.tile_mappings.get(key)
                rpg_at = rpg_by_name.get(key)
                if not mapping and not rpg_at:
                    continue
                if mapping:
                    asset_id, source_x, source_y, source_w, source_h = mapping
                elif rpg_at:
                    asset_id = rpg_at.id
                    source_x, source_y, source_w, source_h = rpg_at.get_tile_slice_for_mask(0, col, row)
                after = MapItem(
                    asset_id,
                    col,
                    row,
                    source_x=source_x,
                    source_y=source_y,
                    source_w=source_w,
                    source_h=source_h,
                    dest_w=project.tile_size,
                    dest_h=project.tile_size,
                    terrain_type=terrain.name.title(),
                    is_auto_tiled=rpg_at is not None,
                )
                before = layer.get_tile(col, row)
                self.changes[(col, row)] = (
                    before.clone() if before else None,
                    after,
                )

    def execute(self) -> None:
        TileBatchCommand(
            self.project, self.layer_id, self.changes
        ).execute()
        layer = self.project.get_layer(self.layer_id)
        if layer and self.autotile_engine:
            autotile_changes = self.autotile_engine.recalculate_layer(
                self.project, layer
            )
            for coord, (before, after) in autotile_changes.items():
                if coord in self.changes:
                    original_before, _ = self.changes[coord]
                    self.changes[coord] = (original_before, after)
                else:
                    self.changes[coord] = (before, after)

    def undo(self) -> None:
        TileBatchCommand(
            self.project, self.layer_id, self.changes
        ).undo()
