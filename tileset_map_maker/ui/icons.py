import os
import math
import logging
from typing import Dict, Optional, Tuple
from PyQt6.QtCore import Qt, QRectF, QPointF, QByteArray
from PyQt6.QtGui import (
    QAction,
    QIcon,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPainterPath,
    QPolygonF,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QWidget

logger = logging.getLogger("IconFactory")


class IconFactory:
    """
    Central icon provider for TileSet Map Maker.
    Loads and renders crisp, scalable SVG icons directly from the project's `icons/` folder
    (Tabler Icons collection: outline and filled variants), with automatic state styling
    (normal, active, selected, disabled) and reliable vector fallbacks.
    """

    _cache: Dict[str, QIcon] = {}
    _icon_sources: Dict[int, Tuple[str, int, bool]] = {}
    _svg_cache: Dict[str, str] = {}
    _icons_dir: Optional[str] = None

    # Canonical mapping from semantic UI keys to SVG file names in icons/
    ICON_NAME_MAP: Dict[str, str] = {
        # Tools
        "brush": "brush",
        "eraser": "eraser",
        "fill": "bucket",
        "bucket": "bucket",
        "line": "line",
        "rect": "rectangle",
        "rectangle": "rectangle",
        "select": "marquee-2",
        "wand": "wand",
        "object": "map-object",
        "map-object": "map-object",
        "eyedropper": "color-picker",
        "color-picker": "color-picker",
        "stamp": "rubber-stamp",
        "rubber-stamp": "rubber-stamp",
        
        # Actions & Navigation
        "new": "file-plus",
        "open": "folder-open",
        "save": "device-floppy",
        "save-as": "save-as",
        "save_as": "save-as",
        "undo": "arrow-back-up",
        "redo": "arrow-forward-up",
        "grid": "grid-4x4",
        "fit": "focus-2",
        "autotile": "autotile",
        "bolt": "bolt",
        "path": "path-generator",
        "path-generator": "path-generator",
        "road": "road",
        "randomizer": "tile-variants",
        "tile-variants": "tile-variants",
        "dice": "dice-5",
        "dice-5": "dice-5",
        "save_stamp": "stamp-save",
        "stamp-save": "stamp-save",
        "slicer": "tileset-slice",
        "tileset-slice": "tileset-slice",
        "slice": "slice",
        "grid-3x3": "grid-3x3",
        "grid-3x3-template": "grid-3x3-template",
        "hud": "hud-coords",
        "hud-coords": "hud-coords",
        "settings": "settings",
        "export": "download",
        "download": "download",
        "shortcuts": "keyboard",
        "keyboard": "keyboard",
        "reset_ui": "layout",
        "layout": "layout",
        "history": "history",
        "map-edit": "map-edit",

        # General UI Controls & Clipboard
        "plus": "plus",
        "minus": "minus",
        "trash": "trash",
        "delete": "trash",
        "pencil": "pencil",
        "edit": "pencil",
        "rename": "pencil",
        "folder": "folder",
        "folder-open": "folder-open",
        "folder-plus": "folder-plus",
        "folder_new": "folder-plus",
        "folder-share": "folder-share",
        "file": "file",
        "file-plus": "file-plus",
        "file_add": "file-plus",
        "eye": "eye",
        "eye-off": "eye-off",
        "lock": "lock",
        "lock-open": "lock-open",
        "up": "arrow-up",
        "down": "arrow-down",
        "arrow-up": "arrow-up",
        "arrow-down": "arrow-down",
        "chevron-up": "chevron-up",
        "chevron-down": "chevron-down",
        "zoom-in": "zoom-in",
        "zoom-out": "zoom-out",
        "target": "target",
        "copy": "copy",
        "paste": "clipboard",
        "clipboard": "clipboard",
        "check": "check",
        "close": "x",
        "x": "x",
        "exit": "door-exit",
        "door-exit": "door-exit",
        "about": "info-circle",
        "info-circle": "info-circle",
        "palette": "palette",
        "refresh": "refresh",
        "rot": "rotate",
        "rotate": "rotate",
        "flip": "flip-horizontal",
        "sparkles": "sparkles",
        "adjustments": "adjustments",
        "help": "help",
        "world": "world",
        "map": "map",
        "layers": "layers-intersect",
        "arrows-maximize": "arrows-maximize",
        "fullscreen": "arrows-maximize",
    }

    @classmethod
    def _get_icons_dir(cls) -> str:
        if cls._icons_dir is None:
            # Locate `icons` folder relative to repository root
            curr = os.path.abspath(os.path.dirname(__file__))
            # curr is tileset_map_maker/ui -> repo root is parent of tileset_map_maker
            repo_root = os.path.abspath(os.path.join(curr, "..", ".."))
            cand = os.path.join(repo_root, "icons")
            if os.path.isdir(cand):
                cls._icons_dir = cand
            else:
                cls._icons_dir = "icons"
        return cls._icons_dir

    @classmethod
    def get_icon(cls, name: str, size: int = 24, filled: bool = False) -> QIcon:
        from .styles import get_icon_palette
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        theme_index = int(app.property("theme_index") or 0) if app else 0
        cache_key = f"{name}_{size}_{filled}_{theme_index}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        icon = QIcon()
        sizes = [16, size] if size != 16 else [16]
        for icon_size in sizes:
            for mode, state in (
                (QIcon.Mode.Normal, QIcon.State.Off),
                (QIcon.Mode.Normal, QIcon.State.On),
                (QIcon.Mode.Active, QIcon.State.Off),
                (QIcon.Mode.Active, QIcon.State.On),
                (QIcon.Mode.Selected, QIcon.State.Off),
                (QIcon.Mode.Selected, QIcon.State.On),
                (QIcon.Mode.Disabled, QIcon.State.Off),
            ):
                foreground, secondary = get_icon_palette(theme_index, mode, state)
                pixmap = cls._render_pixmap(
                    name, icon_size, QColor(foreground), QColor(secondary), filled
                )
                icon.addPixmap(pixmap, mode, state)

        cls._cache[cache_key] = icon
        cls._icon_sources[icon.cacheKey()] = (name, size, filled)
        return icon

    @classmethod
    def refresh_widget_icons(cls, root, theme_index: int) -> None:
        """Replace cached icons beneath a widget with versions for the selected theme."""
        owners = [root, *root.findChildren(QWidget)]
        for owner in owners:
            icon_method = getattr(owner, "icon", None)
            set_icon = getattr(owner, "setIcon", None)
            if not callable(icon_method) or not callable(set_icon):
                continue
            source = cls._icon_sources.get(icon_method().cacheKey())
            if source:
                set_icon(cls.get_icon(*source))

        for action in root.findChildren(QAction):
            source = cls._icon_sources.get(action.icon().cacheKey())
            if source:
                action.setIcon(cls.get_icon(*source))

    @classmethod
    def _load_svg_text(cls, name: str, filled: bool = False) -> Optional[str]:
        """Resolves and loads raw SVG XML text from the icons directory."""
        canonical = cls.ICON_NAME_MAP.get(name, name)
        subfolder = "filled" if filled else "outline"
        cache_key = f"{subfolder}/{canonical}"
        if cache_key in cls._svg_cache:
            return cls._svg_cache[cache_key]

        icons_dir = cls._get_icons_dir()
        paths_to_check = [
            os.path.join(icons_dir, subfolder, f"{canonical}.svg"),
            os.path.join(icons_dir, "outline", f"{canonical}.svg"),
            os.path.join(icons_dir, "filled", f"{canonical}.svg"),
        ]

        for p in paths_to_check:
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        text = f.read()
                    cls._svg_cache[cache_key] = text
                    return text
                except Exception as e:
                    logger.debug(f"Failed to read icon SVG at {p}: {e}")

        return None

    @classmethod
    def _render_pixmap(
        cls,
        name: str,
        size: int,
        primary_color: QColor,
        secondary_color: QColor,
        filled: bool = False,
    ) -> QPixmap:
        # Scale 2x for sharp rendering on High DPI displays
        scale = 2
        pix_size = size * scale
        pixmap = QPixmap(pix_size, pix_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        # 1. Try loading and rendering SVG file from icons/
        svg_text = cls._load_svg_text(name, filled)
        if svg_text:
            hex_col = primary_color.name()
            # Replace currentColor with desired state color
            tinted_svg = svg_text.replace("currentColor", hex_col)
            if size <= 20:
                tinted_svg = tinted_svg.replace('stroke-width="2"', 'stroke-width="2.3"')
            # Ensure stroke and fill colors match if hardcoded in SVG
            if filled:
                tinted_svg = tinted_svg.replace('fill="none"', f'fill="{hex_col}"')

            renderer = QSvgRenderer(QByteArray(tinted_svg.encode("utf-8")))
            if renderer.isValid():
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                renderer.render(painter, QRectF(0, 0, pix_size, pix_size))
                painter.end()
                return pixmap

        # 2. Vector QPainter Fallback if SVG not present
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.scale(scale, scale)

        pen = QPen(primary_color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        render_func = getattr(cls, f"_draw_{name}", cls._draw_fallback)
        try:
            render_func(painter, size, primary_color, secondary_color)
        except Exception:
            cls._draw_fallback(painter, size, primary_color, secondary_color)

        painter.end()
        return pixmap

    # --- Tool Icons ---

    @staticmethod
    def _draw_brush(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Angled paint brush handle and bristle tip
        path = QPainterPath()
        path.moveTo(s * 0.72, s * 0.22)
        path.lineTo(s * 0.82, s * 0.32)
        path.lineTo(s * 0.52, s * 0.62)
        path.lineTo(s * 0.42, s * 0.52)
        path.closeSubpath()
        p.setBrush(QBrush(fg))
        p.drawPath(path)

        # Bristles and tip
        tip_path = QPainterPath()
        tip_path.moveTo(s * 0.42, s * 0.52)
        tip_path.lineTo(s * 0.52, s * 0.62)
        tip_path.cubicTo(s * 0.38, s * 0.76, s * 0.22, s * 0.82, s * 0.18, s * 0.82)
        tip_path.cubicTo(s * 0.18, s * 0.78, s * 0.24, s * 0.62, s * 0.42, s * 0.52)
        p.setBrush(QBrush(bg))
        p.drawPath(tip_path)

    @staticmethod
    def _draw_eraser(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Beveled drafting eraser tilted at 45 degrees
        p.save()
        p.translate(s * 0.5, s * 0.5)
        p.rotate(-35)

        w, h = s * 0.58, s * 0.34
        rect = QRectF(-w / 2, -h / 2, w, h)
        p.setBrush(QBrush(QColor(fg.red(), fg.green(), fg.blue(), 40)))
        p.drawRoundedRect(rect, 3, 3)

        # Angled rubber tip highlight
        p.setBrush(QBrush(fg))
        tip_rect = QRectF(-w / 2, -h / 2, w * 0.4, h)
        p.drawRoundedRect(tip_rect, 2, 2)
        p.restore()

    @staticmethod
    def _draw_fill(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Tilted bucket pouring paint droplet
        p.save()
        p.translate(s * 0.42, s * 0.42)
        p.rotate(-25)
        # Bucket body
        body = QPolygonF([
            QPointF(-s * 0.22, -s * 0.18),
            QPointF(s * 0.22, -s * 0.18),
            QPointF(s * 0.16, s * 0.26),
            QPointF(-s * 0.16, s * 0.26),
        ])
        p.setBrush(QBrush(QColor(fg.red(), fg.green(), fg.blue(), 60)))
        p.drawPolygon(body)
        p.restore()

        # Droplet
        p.setBrush(QBrush(fg))
        p.drawEllipse(QPointF(s * 0.76, s * 0.72), s * 0.1, s * 0.12)

    @staticmethod
    def _draw_line(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Diagonal drafting line with precision end caps
        p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.78, s * 0.22))
        p.setBrush(QBrush(fg))
        p.drawEllipse(QPointF(s * 0.22, s * 0.78), 2.5, 2.5)
        p.drawEllipse(QPointF(s * 0.78, s * 0.22), 2.5, 2.5)

    @staticmethod
    def _draw_rect(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Rounded outline rectangle
        rect = QRectF(s * 0.22, s * 0.22, s * 0.56, s * 0.56)
        p.setBrush(QBrush(QColor(fg.red(), fg.green(), fg.blue(), 40)))
        p.drawRoundedRect(rect, 3, 3)

    @staticmethod
    def _draw_select(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Marquee selection with dashed border and corner handles
        pen = p.pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        rect = QRectF(s * 0.24, s * 0.24, s * 0.52, s * 0.52)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect)

        # Handles
        pen.setStyle(Qt.PenStyle.SolidLine)
        p.setPen(pen)
        p.setBrush(QBrush(fg))
        hs = 3.0
        p.drawRect(QRectF(s * 0.24 - hs / 2, s * 0.24 - hs / 2, hs, hs))
        p.drawRect(QRectF(s * 0.76 - hs / 2, s * 0.24 - hs / 2, hs, hs))
        p.drawRect(QRectF(s * 0.24 - hs / 2, s * 0.76 - hs / 2, hs, hs))
        p.drawRect(QRectF(s * 0.76 - hs / 2, s * 0.76 - hs / 2, hs, hs))

    @staticmethod
    def _draw_wand(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Magic wand with star sparkles
        pen = p.pen()
        pen.setWidthF(2.0)
        p.setPen(pen)
        p.drawLine(QPointF(s * 0.25, s * 0.75), QPointF(s * 0.65, s * 0.35))
        # Tip sparkle
        p.setBrush(QBrush(fg))
        tip = QPointF(s * 0.72, s * 0.28)
        p.drawEllipse(tip, 2.5, 2.5)
        # Sparkles around tip
        p.drawPoint(QPointF(s * 0.85, s * 0.20))
        p.drawPoint(QPointF(s * 0.65, s * 0.15))
        p.drawPoint(QPointF(s * 0.82, s * 0.38))

    @staticmethod
    def _draw_object(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Freeform object target crosshair with corner brackets
        cx, cy = s * 0.5, s * 0.5
        r = s * 0.24
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Crosshair lines
        p.drawLine(QPointF(cx - r - 3, cy), QPointF(cx - 3, cy))
        p.drawLine(QPointF(cx + 3, cy), QPointF(cx + r + 3, cy))
        p.drawLine(QPointF(cx, cy - r - 3), QPointF(cx, cy - 3))
        p.drawLine(QPointF(cx, cy + 3), QPointF(cx, cy + r + 3))

    @staticmethod
    def _draw_eyedropper(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Laboratory pipette angled at 45 degrees
        p.save()
        p.translate(s * 0.5, s * 0.5)
        p.rotate(-45)
        # Bulb
        p.setBrush(QBrush(fg))
        p.drawRoundedRect(QRectF(-s * 0.08, -s * 0.38, s * 0.16, s * 0.20), 4, 4)
        # Tube
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(-s * 0.06, -s * 0.18, s * 0.12, s * 0.36))
        # Tip
        p.drawLine(QPointF(-s * 0.06, s * 0.18), QPointF(0, s * 0.36))
        p.drawLine(QPointF(s * 0.06, s * 0.18), QPointF(0, s * 0.36))
        p.restore()

    @staticmethod
    def _draw_stamp(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Rubber stamp with handle and base
        # Handle knob
        p.setBrush(QBrush(fg))
        p.drawEllipse(QPointF(s * 0.5, s * 0.26), s * 0.1, s * 0.1)
        # Neck
        p.drawRect(QRectF(s * 0.44, s * 0.34, s * 0.12, s * 0.22))
        # Base
        base = QPolygonF([
            QPointF(s * 0.26, s * 0.72),
            QPointF(s * 0.74, s * 0.72),
            QPointF(s * 0.68, s * 0.56),
            QPointF(s * 0.32, s * 0.56),
        ])
        p.drawPolygon(base)
        # Ink bottom
        p.drawLine(QPointF(s * 0.22, s * 0.8), QPointF(s * 0.78, s * 0.8))

    # --- Toolbar Action Icons ---

    @staticmethod
    def _draw_new(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Clean document page with folded corner
        path = QPainterPath()
        path.moveTo(s * 0.26, s * 0.18)
        path.lineTo(s * 0.56, s * 0.18)
        path.lineTo(s * 0.74, s * 0.36)
        path.lineTo(s * 0.74, s * 0.82)
        path.lineTo(s * 0.26, s * 0.82)
        path.closeSubpath()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # Fold corner
        p.drawLine(QPointF(s * 0.56, s * 0.18), QPointF(s * 0.56, s * 0.36))
        p.drawLine(QPointF(s * 0.56, s * 0.36), QPointF(s * 0.74, s * 0.36))

    @staticmethod
    def _draw_open(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Folder
        path = QPainterPath()
        path.moveTo(s * 0.2, s * 0.32)
        path.lineTo(s * 0.4, s * 0.32)
        path.lineTo(s * 0.48, s * 0.4)
        path.lineTo(s * 0.8, s * 0.4)
        path.lineTo(s * 0.8, s * 0.76)
        path.lineTo(s * 0.2, s * 0.76)
        path.closeSubpath()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    @staticmethod
    def _draw_save(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Floppy disk
        path = QPainterPath()
        path.moveTo(s * 0.22, s * 0.22)
        path.lineTo(s * 0.68, s * 0.22)
        path.lineTo(s * 0.78, s * 0.32)
        path.lineTo(s * 0.78, s * 0.78)
        path.lineTo(s * 0.22, s * 0.78)
        path.closeSubpath()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # Metal shutter and label
        p.drawRect(QRectF(s * 0.34, s * 0.22, s * 0.32, s * 0.22))
        p.drawRect(QRectF(s * 0.32, s * 0.54, s * 0.36, s * 0.24))

    @staticmethod
    def _draw_undo(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Smooth curved arrow pointing left
        path = QPainterPath()
        path.moveTo(s * 0.72, s * 0.72)
        path.cubicTo(s * 0.72, s * 0.42, s * 0.46, s * 0.38, s * 0.34, s * 0.38)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # Arrowhead
        arrow = QPolygonF([
            QPointF(s * 0.36, s * 0.24),
            QPointF(s * 0.22, s * 0.38),
            QPointF(s * 0.36, s * 0.52),
        ])
        p.setBrush(QBrush(fg))
        p.drawPolygon(arrow)

    @staticmethod
    def _draw_redo(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Smooth curved arrow pointing right
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.72)
        path.cubicTo(s * 0.28, s * 0.42, s * 0.54, s * 0.38, s * 0.66, s * 0.38)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # Arrowhead
        arrow = QPolygonF([
            QPointF(s * 0.64, s * 0.24),
            QPointF(s * 0.78, s * 0.38),
            QPointF(s * 0.64, s * 0.52),
        ])
        p.setBrush(QBrush(fg))
        p.drawPolygon(arrow)

    @staticmethod
    def _draw_grid(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # 3x3 grid lines
        p.drawRect(QRectF(s * 0.22, s * 0.22, s * 0.56, s * 0.56))
        p.drawLine(QPointF(s * 0.41, s * 0.22), QPointF(s * 0.41, s * 0.78))
        p.drawLine(QPointF(s * 0.59, s * 0.22), QPointF(s * 0.59, s * 0.78))
        p.drawLine(QPointF(s * 0.22, s * 0.41), QPointF(s * 0.78, s * 0.41))
        p.drawLine(QPointF(s * 0.22, s * 0.59), QPointF(s * 0.78, s * 0.59))

    @staticmethod
    def _draw_fit(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Target / fit viewfinder
        d = s * 0.16
        # Top-left corner
        p.drawLine(QPointF(s * 0.22, s * 0.22 + d), QPointF(s * 0.22, s * 0.22))
        p.drawLine(QPointF(s * 0.22, s * 0.22), QPointF(s * 0.22 + d, s * 0.22))
        # Top-right corner
        p.drawLine(QPointF(s * 0.78 - d, s * 0.22), QPointF(s * 0.78, s * 0.22))
        p.drawLine(QPointF(s * 0.78, s * 0.22), QPointF(s * 0.78, s * 0.22 + d))
        # Bottom-left corner
        p.drawLine(QPointF(s * 0.22, s * 0.78 - d), QPointF(s * 0.22, s * 0.78))
        p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.22 + d, s * 0.78))
        # Bottom-right corner
        p.drawLine(QPointF(s * 0.78 - d, s * 0.78), QPointF(s * 0.78, s * 0.78))
        p.drawLine(QPointF(s * 0.78, s * 0.78), QPointF(s * 0.78, s * 0.78 - d))
        # Center dot
        p.setBrush(QBrush(fg))
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), 2, 2)

    @staticmethod
    def _draw_autotile(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Sharp dynamic lightning bolt symbol for Auto-Tile
        bolt = QPolygonF([
            QPointF(s * 0.54, s * 0.18),
            QPointF(s * 0.28, s * 0.52),
            QPointF(s * 0.48, s * 0.52),
            QPointF(s * 0.42, s * 0.82),
            QPointF(s * 0.72, s * 0.44),
            QPointF(s * 0.52, s * 0.44),
        ])
        p.setBrush(QBrush(fg))
        p.drawPolygon(bolt)

    @staticmethod
    def _draw_save_stamp(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        IconFactory._draw_stamp(p, s, fg, bg)
        # Small plus badge in corner
        p.setBrush(QBrush(QColor("#22c55e")))
        p.drawEllipse(QPointF(s * 0.75, s * 0.75), 4, 4)
        p.setPen(QPen(QColor("#ffffff"), 1.2))
        p.drawLine(QPointF(s * 0.75, s * 0.67), QPointF(s * 0.75, s * 0.83))
        p.drawLine(QPointF(s * 0.67, s * 0.75), QPointF(s * 0.83, s * 0.75))

    @staticmethod
    def _draw_settings(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Gear / cogwheel
        cx, cy = s * 0.5, s * 0.5
        r_out = s * 0.32
        r_in = s * 0.14
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r_in, r_in)

        # 6 Teeth
        p.setBrush(QBrush(fg))
        for i in range(6):
            angle = i * (math.pi / 3)
            tx = cx + r_out * 0.75 * math.cos(angle)
            ty = cy + r_out * 0.75 * math.sin(angle)
            p.drawEllipse(QPointF(tx, ty), 2.8, 2.8)

    @staticmethod
    def _draw_export(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Frame with export arrow
        rect = QRectF(s * 0.22, s * 0.34, s * 0.56, s * 0.46)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 3, 3)

        # Arrow pointing up out of frame
        p.drawLine(QPointF(s * 0.5, s * 0.56), QPointF(s * 0.5, s * 0.16))
        arrow = QPolygonF([
            QPointF(s * 0.38, s * 0.28),
            QPointF(s * 0.5, s * 0.16),
            QPointF(s * 0.62, s * 0.28),
        ])
        p.setBrush(QBrush(fg))
        p.drawPolygon(arrow)

    @staticmethod
    def _draw_shortcuts(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Keyboard outline
        rect = QRectF(s * 0.18, s * 0.3, s * 0.64, s * 0.42)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 3, 3)
        # Key dots
        p.setBrush(QBrush(fg))
        for x in [s * 0.30, s * 0.43, s * 0.56, s * 0.69]:
            p.drawRect(QRectF(x - 2, s * 0.40, 4, 3))
            p.drawRect(QRectF(x - 2, s * 0.52, 4, 3))
        # Spacebar
        p.drawRect(QRectF(s * 0.35, s * 0.62, s * 0.3, 2))

    @staticmethod
    def _draw_reset_ui(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Circular reload arrow
        cx, cy = s * 0.5, s * 0.5
        r = s * 0.28
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 45 * 16, 270 * 16)
        # Arrowhead
        arrow = QPolygonF([
            QPointF(cx + r - 3, cy - 6),
            QPointF(cx + r + 3, cy),
            QPointF(cx + r + 8, cy - 6),
        ])
        p.setBrush(QBrush(fg))
        p.drawPolygon(arrow)

    @staticmethod
    def _draw_fallback(p: QPainter, s: int, fg: QColor, bg: QColor) -> None:
        # Fallback icon: clean geometric circle with cross
        cx, cy = s * 0.5, s * 0.5
        r = s * 0.28
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.24, s * 0.24, s * 0.52, s * 0.52), 4, 4)
        p.drawLine(QPointF(cx - 3, cy), QPointF(cx + 3, cy))
        p.drawLine(QPointF(cx, cy - 3), QPointF(cx, cy + 3))
