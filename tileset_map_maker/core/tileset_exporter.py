import io
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Tuple

from PIL import Image

from ..models.asset import Asset, TilesetConfig


class TilesetExportError(Exception):
    """Raised when exporting a tileset to ZIP fails."""


@dataclass(frozen=True)
class TilesetExportResult:
    """Summary of a completed (or cancelled) tileset-to-ZIP export."""

    output_path: str
    total_cells: int
    exported_count: int
    skipped_empty_count: int
    cols: int
    rows: int
    tile_width: int
    tile_height: int
    cancelled: bool = False


_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def sanitize_export_name(name: str, fallback: str = "tileset") -> str:
    """Returns a filesystem- and ZIP-safe base name derived from the tileset name."""
    cleaned = _INVALID_FILENAME_CHARS_RE.sub("_", (name or "").strip())
    cleaned = cleaned.strip(" .")
    return cleaned or fallback


def default_zip_filename(tileset_name: str, selected_only: bool = False) -> str:
    """Returns the default archive filename for a tileset (e.g. 'Forest.zip' or 'Forest_selected.zip')."""
    base = sanitize_export_name(tileset_name)
    suffix = "_selected" if selected_only else ""
    return f"{base}{suffix}.zip"


def is_tile_completely_transparent(tile: Image.Image) -> bool:
    """
    Returns True if every pixel in the tile has alpha == 0.
    Images without an alpha channel are never completely transparent.
    """
    if tile.mode == "RGBA":
        _, max_alpha = tile.getchannel("A").getextrema()
        return max_alpha == 0
    if "A" in tile.getbands():
        _, max_alpha = tile.getchannel("A").getextrema()
        return max_alpha == 0
    return False


def export_tileset_to_zip(
    source_path: str,
    tileset_name: str,
    tileset_config: Optional[TilesetConfig],
    output_zip_path: str,
    *,
    selected_cells: Optional[Iterable[Tuple[int, int]]] = None,
    include_empty: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> TilesetExportResult:
    """
    Slices the source tileset image using the exact TilesetConfig grid and packs
    each individual tile as a lossless PNG into a single ZIP archive.

    - If `selected_cells` is None, exports all cells in the tileset sheet.
    - If `selected_cells` is provided (iterable of `(col, row)` pairs), exports
      only those cells as separate PNG files while preserving their original
      1-based sheet indices (left-to-right, top-to-bottom).
    - Never modifies the source image file.
    - Preserves original tile size, pixel values, colors, and transparency.
    - Writes atomically via a temporary file in the target directory so errors
      or cancellation never leave a corrupted archive behind.
    """
    if not source_path or not os.path.isfile(source_path):
        raise TilesetExportError(f"Source tileset file not found: {source_path}")

    if not output_zip_path:
        raise TilesetExportError("Output ZIP path is empty.")

    cfg = (
        TilesetConfig.from_dict(tileset_config.to_dict())
        if tileset_config is not None
        else TilesetConfig(tile_width=32, tile_height=32)
    )

    try:
        with Image.open(source_path) as src_img:
            img_w, img_h = src_img.size
            rgba_img = src_img.convert("RGBA")
    except Exception as exc:
        raise TilesetExportError(f"Could not open source image: {exc}") from exc

    grid = cfg.compute_grid(img_w, img_h)
    cols = int(grid["cols"])
    rows = int(grid["rows"])
    sheet_total_cells = int(grid["total_cells"])

    if sheet_total_cells <= 0:
        raise TilesetExportError(
            f"Tileset grid has no valid tiles ({cols}x{rows}) for image {img_w}x{img_h}px."
        )

    if selected_cells is None:
        cells_to_export: List[Tuple[int, int]] = [
            (c, r) for r in range(rows) for c in range(cols)
        ]
    else:
        valid_unique = {
            (int(c), int(r))
            for c, r in selected_cells
            if 0 <= int(c) < cols and 0 <= int(r) < rows
        }
        cells_to_export = sorted(valid_unique, key=lambda cr: (cr[1], cr[0]))
        if not cells_to_export:
            raise TilesetExportError("No selected tiles to export.")

    total_cells = len(cells_to_export)
    safe_prefix = sanitize_export_name(tileset_name)
    pad_width = max(4, len(str(sheet_total_cells)))

    output_abs = os.path.abspath(output_zip_path)
    output_dir = os.path.dirname(output_abs)
    if output_dir and not os.path.isdir(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            raise TilesetExportError(f"Cannot create output directory: {exc}") from exc

    tmp_path: Optional[str] = None
    exported_count = 0
    skipped_empty_count = 0

    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=".tileset_export_",
            suffix=".zip.tmp",
            dir=output_dir or None,
        )
        os.close(fd)

        if progress_callback is not None:
            progress_callback(0, total_cells)

        with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for processed, (c, r) in enumerate(cells_to_export, start=1):
                if cancel_check is not None and cancel_check():
                    zf.close()
                    _safe_remove(tmp_path)
                    return TilesetExportResult(
                        output_path=output_abs,
                        total_cells=total_cells,
                        exported_count=exported_count,
                        skipped_empty_count=skipped_empty_count,
                        cols=cols,
                        rows=rows,
                        tile_width=cfg.tile_width,
                        tile_height=cfg.tile_height,
                        cancelled=True,
                    )

                tile_index = r * cols + c + 1
                sx, sy, tw, th = cfg.get_tile_rect(c, r)
                tile = rgba_img.crop((sx, sy, sx + tw, sy + th))

                if not include_empty and is_tile_completely_transparent(tile):
                    skipped_empty_count += 1
                else:
                    buf = io.BytesIO()
                    tile.save(buf, format="PNG")
                    arcname = f"{safe_prefix}_{tile_index:0{pad_width}d}.png"
                    zf.writestr(arcname, buf.getvalue())
                    exported_count += 1

                if progress_callback is not None:
                    progress_callback(processed, total_cells)

        os.replace(tmp_path, output_abs)
        tmp_path = None
    except TilesetExportError:
        _safe_remove(tmp_path)
        raise
    except Exception as exc:
        _safe_remove(tmp_path)
        raise TilesetExportError(f"Failed to write ZIP archive: {exc}") from exc

    return TilesetExportResult(
        output_path=output_abs,
        total_cells=total_cells,
        exported_count=exported_count,
        skipped_empty_count=skipped_empty_count,
        cols=cols,
        rows=rows,
        tile_width=cfg.tile_width,
        tile_height=cfg.tile_height,
        cancelled=False,
    )


def export_asset_tiles_to_zip(
    asset: Asset,
    output_zip_path: str,
    *,
    selected_cells: Optional[Iterable[Tuple[int, int]]] = None,
    include_empty: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> TilesetExportResult:
    """Convenience wrapper exporting an Asset instance (all or selected tiles) to a ZIP archive."""
    return export_tileset_to_zip(
        source_path=asset.file_path,
        tileset_name=asset.name,
        tileset_config=asset.tileset_config,
        output_zip_path=output_zip_path,
        selected_cells=selected_cells,
        include_empty=include_empty,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )


def _safe_remove(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
