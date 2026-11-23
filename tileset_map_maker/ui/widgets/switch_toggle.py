from typing import Optional
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, pyqtProperty, pyqtSignal, QEasingCurve
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPaintEvent, QMouseEvent, QKeyEvent, QIcon


_TOOLBAR_TOGGLE_PALETTES = {
    0: {
        "background": "#27272a",
        "border": "#3f3f46",
        "text": "#d4d4d8",
        "hover_background": "#3f3f46",
        "hover_border": "#60a5fa",
        "checked_background": "#2563eb",
        "checked_border": "#93c5fd",
        "checked_text": "#ffffff",
        "checked_hover_background": "#1d4ed8",
        "checked_hover_border": "#bfdbfe",
        "disabled_background": "#18181b",
        "disabled_border": "#27272a",
        "disabled_text": "#52525b",
        "pressed_background": "#1d4ed8",
        "pressed_border": "#2563eb",
    },
    1: {
        "background": "#e2e8f0",
        "border": "#64748b",
        "text": "#1e293b",
        "hover_background": "#cbd5e1",
        "hover_border": "#1d4ed8",
        "checked_background": "#1d4ed8",
        "checked_border": "#1e40af",
        "checked_text": "#ffffff",
        "checked_hover_background": "#1e40af",
        "checked_hover_border": "#172554",
        "disabled_background": "#ffffff",
        "disabled_border": "#e2e8f0",
        "disabled_text": "#64748b",
        "pressed_background": "#1d4ed8",
        "pressed_border": "#1d4ed8",
    },
    2: {
        "background": "#141414",
        "border": "#666666",
        "text": "#ffffff",
        "hover_background": "#222222",
        "hover_border": "#00e5ff",
        "checked_background": "#0057ff",
        "checked_border": "#00ffff",
        "checked_text": "#ffffff",
        "checked_hover_background": "#00e5ff",
        "checked_hover_border": "#aefcff",
        "disabled_background": "#050505",
        "disabled_border": "#444444",
        "disabled_text": "#a3a3a3",
        "pressed_background": "#0057ff",
        "pressed_border": "#00e5ff",
    },
    3: {
        "background": "#294936",
        "border": "#80683f",
        "text": "#eee2c2",
        "hover_background": "#34543b",
        "hover_border": "#dfc477",
        "checked_background": "#806735",
        "checked_border": "#fff0c8",
        "checked_text": "#fff8df",
        "checked_hover_background": "#60452d",
        "checked_hover_border": "#dfc477",
        "disabled_background": "#12241c",
        "disabled_border": "#34543b",
        "disabled_text": "#8c8a77",
        "pressed_background": "#60452d",
        "pressed_border": "#806735",
    },
}


def _toolbar_toggle_palette(theme_index=None):
    app = QApplication.instance()
    if theme_index is None:
        theme_index = int(app.property("theme_index") or 0) if app else 0
    return _TOOLBAR_TOGGLE_PALETTES.get(theme_index, _TOOLBAR_TOGGLE_PALETTES[0])


class SwitchToggle(QWidget):
    """
    Modern iOS / Material style Toggle Switch control for ON/OFF options.
    Replaces traditional checkboxes for functional mode activation.
    
    Features:
    - Smooth animated thumb slide between OFF and ON states.
    - Distinct visual states: ON (accent green/blue), OFF (zinc/dark gray), hover, disabled.
    - Clickable text label alongside the switch pill.
    - Full keyboard accessibility (Space / Enter triggers toggle).
    - Standard Qt API parity: isChecked(), setChecked(bool), toggled(bool), toggle().
    """
    toggled = pyqtSignal(bool)

    def __init__(
        self,
        text: str = "",
        checked: bool = False,
        parent: Optional[QWidget] = None,
        pill_width: int = 38,
        pill_height: int = 20,
    ):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self._checked = bool(checked)
        self._pill_width = pill_width
        self._pill_height = pill_height
        self._thumb_margin = 2
        self._thumb_radius = (self._pill_height - (self._thumb_margin * 2)) / 2.0
        
        # Normalized position: 0.0 (OFF, left) to 1.0 (ON, right)
        self._thumb_position = 1.0 if self._checked else 0.0
        self._hovered = False

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Layout: Pill on left, text label on right
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Internal widget that draws the pill switch
        self._pill_widget = _PillWidget(self)
        layout.addWidget(self._pill_widget)

        self._label = QLabel(text)
        self._label.setStyleSheet("color: #e4e4e7; font-size: 12px;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._label)

        if not text:
            self._label.setVisible(False)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @pyqtProperty(float)
    def thumb_position(self) -> float:
        return self._thumb_position

    @thumb_position.setter
    def thumb_position(self, pos: float) -> None:
        self._thumb_position = pos
        self._pill_widget.update()

    def text(self) -> str:
        return self._label.text()

    def setText(self, text: str) -> None:
        self._label.setText(text)
        self._label.setVisible(bool(text))

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        
        # Run smooth animation to target state
        self._anim.stop()
        self._anim.setStartValue(self._thumb_position)
        self._anim.setEndValue(1.0 if self._checked else 0.0)
        self._anim.start()

        self._pill_widget.update()
        self.toggled.emit(self._checked)

    def toggle(self) -> None:
        self.setChecked(not self._checked)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, "_pressed", False):
            self._pressed = False
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.rect().contains(pos) and self.isEnabled():
                self.toggle()
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.isEnabled():
            self.toggle()
            event.accept()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._pill_widget.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pill_widget.update()
        super().leaveEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == event.Type.EnabledChange:
            self._pill_widget.update()
            if self.isEnabled():
                self._label.setStyleSheet("color: #e4e4e7; font-size: 12px;")
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self._label.setStyleSheet("color: #71717a; font-size: 12px;")
                self.setCursor(Qt.CursorShape.ArrowCursor)
        super().changeEvent(event)


class _PillWidget(QWidget):
    """Internal canvas drawing the pill background and sliding circular thumb."""

    def __init__(self, owner: SwitchToggle):
        super().__init__(owner)
        self._owner = owner
        self.setFixedSize(owner._pill_width, owner._pill_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pw = self._owner._pill_width
        ph = self._owner._pill_height
        pos = self._owner._thumb_position
        is_enabled = self._owner.isEnabled()
        is_hovered = self._owner._hovered and is_enabled

        # Calculate interpolated background color
        # OFF color: zinc-700 (#3f3f46), Hover: zinc-600 (#52525b)
        # ON color: blue-600 (#2563eb) or emerald-600 (#16a34a)
        if not is_enabled:
            bg_off = QColor("#27272a")
            bg_on = QColor("#3f3f46")
        elif is_hovered:
            bg_off = QColor("#4b4b54")
            bg_on = QColor("#3b82f6")  # Brighter on hover
        else:
            bg_off = QColor("#393a42")
            bg_on = QColor("#2563eb")

        # Blend colors according to pos (0.0 to 1.0)
        r = int(bg_off.red() + (bg_on.red() - bg_off.red()) * pos)
        g = int(bg_off.green() + (bg_on.green() - bg_off.green()) * pos)
        b = int(bg_off.blue() + (bg_on.blue() - bg_off.blue()) * pos)
        bg_color = QColor(r, g, b)

        # Draw Pill Capsule
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        corner_radius = ph / 2.0
        painter.drawRoundedRect(0, 0, pw, ph, corner_radius, corner_radius)

        # Subtle border
        if is_enabled:
            border_col = QColor(255, 255, 255, 40 if is_hovered else 25)
            painter.setPen(QPen(border_col, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(0, 0, pw - 1, ph - 1, corner_radius, corner_radius)

        # Draw Thumb Circle
        margin = self._owner._thumb_margin
        thumb_diameter = ph - (margin * 2)
        min_x = margin
        max_x = pw - margin - thumb_diameter
        thumb_x = min_x + (max_x - min_x) * pos
        thumb_y = margin

        painter.setPen(Qt.PenStyle.NoPen)
        if is_enabled:
            painter.setBrush(QBrush(QColor("#ffffff")))
        else:
            painter.setBrush(QBrush(QColor("#a1a1aa")))

        painter.drawEllipse(int(thumb_x), int(thumb_y), int(thumb_diameter), int(thumb_diameter))


class ToolbarToggleButton(SwitchToggle):
    """
    Toolbar toggle button matching the unified icon button visual system.
    Inherits from SwitchToggle for 100% API compatibility (isChecked, setChecked, toggled).
    
    States:
    - Inactive: standard toolbar button (#27272a, border #3f3f46, text #d4d4d8, normal icon)
    - Active: bright blue (#2563eb, border #93c5fd, text #ffffff, active icon)
    - Hover: #3f3f46 (inactive) or #1d4ed8 (active) with accented border
    - Disabled: muted zinc (#18181b, border #27272a, text #52525b)
    """

    def __init__(
        self,
        text: str = "",
        checked: bool = False,
        icon_name: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text=text, checked=checked, parent=parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._pill_widget.hide()
        self._icon_name = icon_name
        self._hovered = False
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._icon_lbl = QLabel(self)
        self._icon_lbl.setFixedSize(16, 16)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._icon_lbl.setStyleSheet("background: transparent; border: none;")
        self.layout().insertWidget(0, self._icon_lbl)

        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.layout().setContentsMargins(6, 2, 7, 2)
        self.layout().setSpacing(5)
        self._update_style()

    def setIconName(self, icon_name: str) -> None:
        self._icon_name = icon_name
        self._update_style()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._update_style()
        self.update()

    def toggle(self) -> None:
        super().toggle()
        self._update_style()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, "_pressed", False):
            self._pressed = False
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.rect().contains(pos) and self.isEnabled():
                self.toggle()
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == event.Type.EnabledChange:
            self._update_style()
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        # Guarantee visible rounded button background and border in all contexts
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        palette = _toolbar_toggle_palette()
        if not self.isEnabled():
            p.setBrush(QBrush(QColor(palette["disabled_background"])))
            p.setPen(QPen(QColor(palette["disabled_border"]), 1))
            p.drawRoundedRect(rect, 4, 4)
        elif getattr(self, "_pressed", False):
            p.setBrush(QBrush(QColor(palette["pressed_background"])))
            p.setPen(QPen(QColor(palette["pressed_border"]), 1))
            p.drawRoundedRect(rect, 4, 4)
        elif self._checked:
            bg_color = QColor(
                palette["checked_hover_background"]
                if self._hovered
                else palette["checked_background"]
            )
            border_color = QColor(
                palette["checked_hover_border"]
                if self._hovered
                else palette["checked_border"]
            )
            p.setBrush(QBrush(bg_color))
            p.setPen(QPen(border_color, 1))
            p.drawRoundedRect(rect, 4, 4)
        else:
            bg_color = QColor(
                palette["hover_background"] if self._hovered else palette["background"]
            )
            border_color = QColor(
                palette["hover_border"] if self._hovered else palette["border"]
            )
            p.setBrush(QBrush(bg_color))
            p.setPen(QPen(border_color, 1))
            p.drawRoundedRect(rect, 4, 4)
        p.end()

    def _apply_application_theme(self, theme_index: int) -> None:
        self._update_style(theme_index)

    def _update_style(self, theme_index=None) -> None:
        from ..icons import IconFactory

        is_enabled = self.isEnabled()
        if self._icon_name:
            icon = IconFactory.get_icon(self._icon_name, 16)
            if not is_enabled:
                mode = QIcon.Mode.Disabled
                state = QIcon.State.Off
            elif self._checked:
                mode = QIcon.Mode.Active
                state = QIcon.State.On
            else:
                mode = QIcon.Mode.Normal
                state = QIcon.State.Off
            self._icon_lbl.setPixmap(icon.pixmap(16, 16, mode, state))
            self._icon_lbl.show()
        else:
            self._icon_lbl.hide()

        palette = _toolbar_toggle_palette(theme_index)
        if not is_enabled:
            background = palette["disabled_background"]
            border = palette["disabled_border"]
            text = palette["disabled_text"]
            weight = 500
        elif self._checked:
            background = palette["checked_background"]
            border = palette["checked_border"]
            text = palette["checked_text"]
            weight = 600
        else:
            background = palette["background"]
            border = palette["border"]
            text = palette["text"]
            weight = 500

        self.setStyleSheet(f"""
            ToolbarToggleButton {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            ToolbarToggleButton:hover {{
                background-color: {palette["checked_hover_background"] if self._checked else palette["hover_background"]};
                border-color: {palette["checked_hover_border"] if self._checked else palette["hover_border"]};
            }}
            QLabel {{
                color: {text};
                font-size: 11px;
                font-weight: {weight};
                background: transparent;
                border: none;
            }}
        """)
        self._label.setStyleSheet(
            f"color: {text}; font-size: 11px; font-weight: {weight}; "
            "background: transparent; border: none;"
        )
        self.update()
