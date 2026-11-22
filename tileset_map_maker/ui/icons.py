import math
from typing import Dict, Optional
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QIcon,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPainterPath,
    QPolygonF,
)


class IconFactory:
    """
    Generates crisp, high-contrast, scalable vector icons using QPainter
    for all tools, actions, and toolbar buttons in the application.
    Includes state rendering (normal, hover, selected) and reliable fallbacks.
    """

    _cache: Dict[str, QIcon] = {}

    @classmethod
    def get_icon(cls, name: str, size: int = 24) -> QIcon:
        cache_key = f"{name}_{size}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        icon = QIcon()

        # Generate pixmaps for Normal, Active, and Selected states
        pix_normal = cls._render_vector_pixmap(name, size, QColor("#d4d4d8"), QColor("#3f404d"))
        pix_active = cls._render_vector_pixmap(name, size, QColor("#ffffff"), QColor("#4f80ff"))
        pix_selected = cls._render_vector_pixmap(name, size, QColor("#ffffff"), QColor("#2563eb"))
        pix_disabled = cls._render_vector_pixmap(name, size, QColor("#52525b"), QColor("#27272a"))

        icon.addPixmap(pix_normal, QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(pix_selected, QIcon.Mode.Normal, QIcon.State.On)
        icon.addPixmap(pix_active, QIcon.Mode.Active, QIcon.State.Off)
        icon.addPixmap(pix_selected, QIcon.Mode.Active, QIcon.State.On)
        icon.addPixmap(pix_selected, QIcon.Mode.Selected, QIcon.State.Off)
        icon.addPixmap(pix_disabled, QIcon.Mode.Disabled, QIcon.State.Off)

        cls._cache[cache_key] = icon
        return icon

    @classmethod
    def _render_vector_pixmap(
        cls,
        name: str,
        size: int,
        primary_color: QColor,
        secondary_color: QColor,
    ) -> QPixmap:
        # Scale 2x for sharp rendering on High DPI displays
        scale = 2
        pix_size = size * scale
        pixmap = QPixmap(pix_size, pix_size)
        pixmap.fill(Qt.GlobalColor.transparent)

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
