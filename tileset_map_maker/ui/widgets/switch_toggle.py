from typing import Optional
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, pyqtProperty, pyqtSignal, QEasingCurve
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPaintEvent, QMouseEvent, QKeyEvent, QIcon


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
            self.toggle()
            event.accept()
        else:
            super().mousePressEvent(event)

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
            self.toggle()
            event.accept()
        else:
            super().mousePressEvent(event)

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
        if not self.isEnabled():
            p.setBrush(QBrush(QColor("#18181b")))
            p.setPen(QPen(QColor("#27272a"), 1))
            p.drawRoundedRect(rect, 4, 4)
        elif self._checked:
            bg_color = QColor("#1d4ed8") if self._hovered else QColor("#2563eb")
            border_color = QColor("#bfdbfe") if self._hovered else QColor("#93c5fd")
            p.setBrush(QBrush(bg_color))
            p.setPen(QPen(border_color, 1))
            p.drawRoundedRect(rect, 4, 4)
        else:
            bg_color = QColor("#3f3f46") if self._hovered else QColor("#27272a")
            border_color = QColor("#60a5fa") if self._hovered else QColor("#3f3f46")
            p.setBrush(QBrush(bg_color))
            p.setPen(QPen(border_color, 1))
            p.drawRoundedRect(rect, 4, 4)
        p.end()

    def _update_style(self) -> None:
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

        if not is_enabled:
            self.setStyleSheet("""
                ToolbarToggleButton {
                    background-color: #18181b;
                    border: 1px solid #27272a;
                    border-radius: 4px;
                }
                QLabel {
                    color: #52525b;
                    font-size: 11px;
                    font-weight: 500;
                    background: transparent;
                    border: none;
                }
            """)
        elif self._checked:
            self.setStyleSheet("""
                ToolbarToggleButton {
                    background-color: #2563eb;
                    border: 1px solid #93c5fd;
                    border-radius: 4px;
                }
                ToolbarToggleButton:hover {
                    background-color: #1d4ed8;
                    border-color: #bfdbfe;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 11px;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet("""
                ToolbarToggleButton {
                    background-color: #27272a;
                    border: 1px solid #3f3f46;
                    border-radius: 4px;
                }
                ToolbarToggleButton:hover {
                    background-color: #3f3f46;
                    border-color: #60a5fa;
                }
                QLabel {
                    color: #d4d4d8;
                    font-size: 11px;
                    font-weight: 500;
                    background: transparent;
                    border: none;
                }
            """)
        self.update()
