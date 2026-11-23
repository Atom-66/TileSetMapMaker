from typing import Optional, List, Dict, Any, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QGroupBox,
    QSplitter,
    QScrollArea,
    QDialogButtonBox,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen

from ...models.path_ruleset import (
    PathRuleSet,
    ROLE_STRAIGHT_H,
    ROLE_STRAIGHT_V,
    ROLE_CORNER_TL,
    ROLE_CORNER_TR,
    ROLE_CORNER_BL,
    ROLE_CORNER_BR,
    ROLE_CORNER_GENERIC,
    ROLE_T_JUNCTION,
    ROLE_CROSS,
    ROLE_END,
    ROLE_CENTER,
    TEMPLATE_4_TILE,
    TEMPLATE_6_TILE,
    TEMPLATE_CUSTOM,
    TEMPLATE_3X3,
    ROLE_EDGE_TOP,
    ROLE_EDGE_BOTTOM,
    ROLE_EDGE_LEFT,
    ROLE_EDGE_RIGHT,
    ROLE_START,
)
from ...models.asset import SelectedSubTile, AssetType
from ...core.asset_manager import AssetManager
from ...core.autotile_engine import AutoTileEngine
from ..icons import IconFactory
from ...core.localization import get_localization, tr


class PathPreviewWidget(QWidget):
    """
    Renders live sample layouts of the configured path using real assigned PNG tiles:
    - Horizontal straight path
    - Vertical straight path
    - Turns (corners)
    - T-junction or Cross intersection
    - Endpoints / Dead ends
    """

    def __init__(self, ruleset: Optional[PathRuleSet] = None, asset_manager: Optional[AssetManager] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ruleset = ruleset
        self.asset_manager = asset_manager
        self.setMinimumSize(260, 360)
        self.setStyleSheet("background-color: #121214; border: 1px solid #27272a; border-radius: 6px;")

    def set_ruleset(self, ruleset: PathRuleSet) -> None:
        self.ruleset = ruleset
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background
        painter.fillRect(self.rect(), QColor("#121214"))

        ts = 32  # Render preview tiles at 32x32

        # Header font
        font = QFont("Sans-Serif", 9)
        font.setBold(True)
        painter.setFont(font)

        # 1. Horizontal straight path
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(16, 22, tr("dialog.path.preview_straight_h"))
        y_h = 32
        for i in range(5):
            self._draw_role_or_missing(painter, ROLE_STRAIGHT_H, 20 + i * ts, y_h, ts)

        # 2. Vertical straight path
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(16, 88, tr("dialog.path.preview_straight_v"))
        x_v = 20
        for i in range(3):
            self._draw_role_or_missing(painter, ROLE_STRAIGHT_V, x_v, 98 + i * ts, ts)

        # 3. Turns / Bends (S-shape curve)
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(90, 88, tr("dialog.path.preview_turn"))
        # Horizontal approaching from left, turn down (TL), then vertical, turn right (BL), horizontal
        # (90, 98) -> H
        # (122, 98) -> Corner TR
        # (122, 130) -> Vertical
        # (122, 162) -> Corner BL
        # (154, 162) -> H
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_H, 90, 98, ts)
        self._draw_role_or_missing(painter, ROLE_CORNER_TR, 122, 98, ts)
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_V, 122, 130, ts)
        self._draw_role_or_missing(painter, ROLE_CORNER_BL, 122, 162, ts)
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_H, 154, 162, ts)

        # 4. Cross or T-Junction
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(16, 218, tr("dialog.path.preview_junction"))
        # Cross center at (52, 230)
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_V, 52, 230 - ts, ts)
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_H, 52 - ts, 230, ts)
        # Center role: cross or t_junction or generic
        cross_role = ROLE_CROSS if self.ruleset.roles.get(ROLE_CROSS) else (ROLE_T_JUNCTION if self.ruleset.roles.get(ROLE_T_JUNCTION) else ROLE_STRAIGHT_H)
        self._draw_role_or_missing(painter, cross_role, 52, 230, ts)
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_H, 52 + ts, 230, ts)
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_V, 52, 230 + ts, ts)

        # 5. Endpoints
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(160, 218, tr("dialog.path.preview_end"))
        self._draw_role_or_missing(painter, ROLE_STRAIGHT_H, 160, 230, ts)
        self._draw_role_or_missing(painter, ROLE_END if self.ruleset.roles.get(ROLE_END) else ROLE_STRAIGHT_H, 160 + ts, 230, ts)

    def _draw_role_or_missing(self, painter: QPainter, role: str, x: int, y: int, size: int) -> None:
        tile = self.ruleset.roles.get(role)
        if not tile and role in (ROLE_CORNER_TL, ROLE_CORNER_TR, ROLE_CORNER_BL, ROLE_CORNER_BR):
            tile = self.ruleset.roles.get(ROLE_CORNER_GENERIC)

        if tile:
            if hasattr(tile, "asset_id"):
                aid, sx, sy, sw, sh = tile.asset_id, tile.sub_x, tile.sub_y, tile.sub_w, tile.sub_h
            else:
                aid, sx, sy, sw, sh = tile
            pix = self.asset_manager.get_pixmap(aid)
            if pix and not pix.isNull():
                cropped = pix.copy(sx, sy, sw, sh)
                painter.drawPixmap(x, y, size, size, cropped)
                # Subtle border
                painter.setPen(QColor(255, 255, 255, 30))
                painter.drawRect(x, y, size, size)
                return

        # Missing tile placeholder
        painter.fillRect(x, y, size, size, QColor("#271212"))
        pen = QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(x, y, size - 1, size - 1)
        font = QFont("Sans-Serif", 7)
        painter.setFont(font)
        painter.setPen(QColor("#f87171"))
        painter.drawText(
            x, y, size, size, Qt.AlignmentFlag.AlignCenter, tr("dialog.path.missing_tile")
        )


class PathGeneratorDialog(QDialog):
    """
    Dedicated configurator for Path Generator rulesets.
    Allows manual slot-by-slot assignment of arbitrary tiles to path elements,
    supports 4-tile, 6-tile, and custom templates, and displays a live connection preview.
    """
    path_rulesets_changed = pyqtSignal()

    def __init__(
        self,
        autotile_engine: AutoTileEngine,
        asset_manager: AssetManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.path.title"))
        self.setMinimumSize(780, 560)
        self.resize(840, 600)

        self.engine = autotile_engine
        self.asset_manager = asset_manager

        # Active ruleset being edited
        self.current_ruleset: Optional[PathRuleSet] = None
        self._init_ui()
        self._populate_ruleset_selector()
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, _language: str) -> None:
        self.setWindowTitle(tr("dialog.path.title"))
        self._populate_roles_table()
        self.preview_widget.update()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Top Bar: Set selector & actions
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_set = QLabel(tr("dialog.path.set_label"))
        lbl_set.setStyleSheet("font-weight: bold; color: #e4e4e7;")
        top_bar.addWidget(lbl_set)

        self.combo_sets = QComboBox()
        self.combo_sets.setMinimumWidth(200)
        self.combo_sets.currentIndexChanged.connect(self._on_set_selected)
        top_bar.addWidget(self.combo_sets)

        self.btn_new = QPushButton(f" {tr('dialog.path.new_set')}")
        self.btn_new.setIcon(IconFactory.get_icon("plus", 14))
        self.btn_new.clicked.connect(self._create_new_set)
        top_bar.addWidget(self.btn_new)

        self.btn_delete = QPushButton(f" {tr('dialog.path.delete')}")
        self.btn_delete.setIcon(IconFactory.get_icon("trash", 14))
        self.btn_delete.clicked.connect(self._delete_current_set)
        top_bar.addWidget(self.btn_delete)

        top_bar.addStretch()

        # Template Type Selector
        lbl_tmpl = QLabel(tr("dialog.path.template"))
        lbl_tmpl.setStyleSheet("font-weight: bold; color: #e4e4e7;")
        top_bar.addWidget(lbl_tmpl)

        self.combo_template = QComboBox()
        self.combo_template.addItem(tr("dialog.path.template_6"), "6_tile")
        self.combo_template.addItem(tr("dialog.path.template_4"), "4_tile")
        self.combo_template.addItem(tr("dialog.path.template_custom"), "custom")
        self.combo_template.addItem("3×3 — pełny zestaw", "3x3")
        self.combo_template.currentIndexChanged.connect(self._on_template_changed)
        top_bar.addWidget(self.combo_template)

        main_layout.addLayout(top_bar)

        # Name and terrain bar
        name_bar = QHBoxLayout()
        name_bar.setSpacing(8)

        lbl_name = QLabel(tr("dialog.path.name"))
        name_bar.addWidget(lbl_name)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText(tr("dialog.path.name_placeholder"))
        self.txt_name.textChanged.connect(self._on_name_changed)
        name_bar.addWidget(self.txt_name, 1)

        main_layout.addLayout(name_bar)

        # 2. Main Content Splitter: Left (Slot Assignment Table), Right (Live Preview)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Role Slots
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_header = QHBoxLayout()
        lbl_roles = QLabel(tr("dialog.path.roles"))
        lbl_roles.setStyleSheet("font-weight: bold; color: #93c5fd;")
        left_header.addWidget(lbl_roles)

        self.lbl_status = QLabel(tr("dialog.path.incomplete", assigned=0, total=6))
        self.lbl_status.setStyleSheet("color: #f87171; font-weight: bold;")
        left_header.addWidget(self.lbl_status)
        left_header.addStretch()
        left_layout.addLayout(left_header)

        # Roles Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [
                tr("dialog.path.table_thumbnail"),
                tr("dialog.path.table_role"),
                tr("dialog.path.table_assigned"),
                tr("dialog.path.table_actions"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 4px;
                color: #e4e4e7;
            }
            QTableWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        left_layout.addWidget(self.table, 1)

        splitter.addWidget(left_widget)

        # Right Column: Live Connection Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        lbl_prev = QLabel(tr("dialog.path.preview"))
        lbl_prev.setStyleSheet("font-weight: bold; color: #93c5fd;")
        right_layout.addWidget(lbl_prev)

        # Create dummy initial PathRuleSet for preview
        dummy_ruleset = PathRuleSet(name=tr("dialog.path.preview"))
        self.preview_widget = PathPreviewWidget(dummy_ruleset, self.asset_manager)
        right_layout.addWidget(self.preview_widget, 1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter, 1)

        # 3. Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_auto_from_3x3 = QPushButton(f" {tr('dialog.path.autofill')}")
        self.btn_auto_from_3x3.setIcon(IconFactory.get_icon("grid-3x3-template", 16))
        self.btn_auto_from_3x3.setToolTip(tr("path.autofill_tooltip"))
        self.btn_auto_from_3x3.clicked.connect(self._auto_fill_from_palette_3x3)
        bottom_bar.addWidget(self.btn_auto_from_3x3)

        bottom_bar.addStretch()

        self.btn_save = QPushButton(f" {tr('dialog.path.save')}")
        self.btn_save.setIcon(IconFactory.get_icon("save", 16))
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 6px 16px;")
        self.btn_save.clicked.connect(self._save_and_close)
        bottom_bar.addWidget(self.btn_save)

        self.btn_cancel = QPushButton(f" {tr('dialog.path.close')}")
        self.btn_cancel.setIcon(IconFactory.get_icon("close", 14))
        self.btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(self.btn_cancel)

        main_layout.addLayout(bottom_bar)

    def _populate_ruleset_selector(self) -> None:
        self.combo_sets.blockSignals(True)
        self.combo_sets.clear()

        # Find existing PathRuleSets registered in AutoTileEngine
        path_sets = [r for r in self.engine.rulesets.values() if getattr(r, "is_path_ruleset", False)]
        for r in path_sets:
            self.combo_sets.addItem(IconFactory.get_icon("path", 16), r.name, r.id)

        if not path_sets:
            # Create a default path ruleset if none exists
            default_set = PathRuleSet(name=tr("dialog.path.default_name"), template_type="6_tile")
            self.engine.register_ruleset(default_set)
            self.combo_sets.addItem(IconFactory.get_icon("path", 16), default_set.name, default_set.id)

        self.combo_sets.setCurrentIndex(0)
        self.combo_sets.blockSignals(False)
        self._on_set_selected(0)

    def _on_set_selected(self, index: int) -> None:
        rid = self.combo_sets.currentData()
        if not rid:
            return
        ruleset = self.engine.get_ruleset(rid)
        if isinstance(ruleset, PathRuleSet):
            self.current_ruleset = ruleset
            self.txt_name.blockSignals(True)
            self.txt_name.setText(ruleset.name)
            self.txt_name.blockSignals(False)

            self.combo_template.blockSignals(True)
            idx = self.combo_template.findData(ruleset.template_type)
            if idx >= 0:
                self.combo_template.setCurrentIndex(idx)
            self.combo_template.blockSignals(False)

            self._populate_roles_table()
            self.preview_widget.set_ruleset(ruleset)

    def _create_new_set(self) -> None:
        new_set = PathRuleSet(
            name=f"{tr('dialog.path.default_name')} #{len(self.engine.rulesets) + 1}",
            template_type=self.combo_template.currentData() or "6_tile",
        )
        self.engine.register_ruleset(new_set)
        self.combo_sets.addItem(f"🛣️ {new_set.name}", new_set.id)
        self.combo_sets.setCurrentIndex(self.combo_sets.count() - 1)

    def _delete_current_set(self) -> None:
        if not self.current_ruleset:
            return
        if len(self.combo_sets) <= 1:
            QMessageBox.warning(
                self, tr("dialog.path.confirm"), tr("dialog.path.no_delete_last")
            )
            return

        res = QMessageBox.question(
            self,
            tr("dialog.path.confirm"),
            tr("dialog.path.delete_confirm", name=self.current_ruleset.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            rid = self.current_ruleset.id
            if rid in self.engine.rulesets:
                del self.engine.rulesets[rid]
            self._populate_ruleset_selector()
            self.path_rulesets_changed.emit()

    def _on_template_changed(self, index: int) -> None:
        if not self.current_ruleset:
            return
        new_template = self.combo_template.currentData()
        self.current_ruleset.template_type = new_template
        self._populate_roles_table()
        self.preview_widget.update()

    def _on_name_changed(self, text: str) -> None:
        if not self.current_ruleset:
            return
        self.current_ruleset.name = text.strip() or tr("dialog.path.default_name")
        cur_idx = self.combo_sets.currentIndex()
        if cur_idx >= 0:
            self.combo_sets.setItemText(cur_idx, f"🛣️ {self.current_ruleset.name}")

    def _create_subtile_thumbnail(self, subtile: SelectedSubTile, size: int = 32) -> QPixmap:
        """Helper to create a scaled QPixmap thumbnail for a given SelectedSubTile."""
        if not self.asset_manager or not subtile:
            pm = QPixmap(size, size)
            pm.fill(QColor(0, 0, 0, 0))
            return pm
        pix = self.asset_manager.get_pixmap(subtile.asset_id)
        if pix and not pix.isNull():
            cropped = pix.copy(subtile.sub_x, subtile.sub_y, subtile.sub_w, subtile.sub_h)
            return cropped.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pm = QPixmap(size, size)
        pm.fill(QColor(50, 50, 50))
        return pm

    def _populate_roles_table(self) -> None:
        if not self.current_ruleset:
            return

        roles = self.current_ruleset.get_template_roles()
        self.table.setRowCount(len(roles))

        assigned_count = 0
        for row, role_key in enumerate(roles):
            tile = self.current_ruleset.roles.get(role_key)
            if tile:
                assigned_count += 1

            # Column 0: Thumbnail
            lbl_thumb = QLabel()
            lbl_thumb.setFixedSize(36, 36)
            lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if tile:
                aid, sx, sy, sw, sh = tile
                pix = self.asset_manager.get_pixmap(aid)
                if pix and not pix.isNull():
                    cropped = pix.copy(sx, sy, sw, sh)
                    lbl_thumb.setPixmap(cropped.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                lbl_thumb.setText("—")
            self.table.setCellWidget(row, 0, lbl_thumb)

            # Column 1: Role Name
            role_title = tr(f"dialog.path.role.{role_key}")
            item_role = QTableWidgetItem(role_title)
            item_role.setData(Qt.ItemDataRole.UserRole, role_key)
            item_role.setFlags(item_role.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item_role)

            # Column 2: Tile Info
            if tile:
                aid, sx, sy, sw, sh = tile
                asset = self.asset_manager.get_asset(aid)
                name = asset.name if asset else "Tileset"
                txt = f"📦 {name} [{sx}, {sy}] ({sw}x{sh})"
                item_info = QTableWidgetItem(txt)
                item_info.setForeground(QColor("#a7f3d0"))
            else:
                item_info = QTableWidgetItem(tr("dialog.path.unassigned"))
                item_info.setForeground(QColor("#f87171"))
            item_info.setFlags(item_info.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, item_info)

            # Column 3: Action Buttons (Assign from Palette, Clear)
            cell_box = QWidget()
            box_layout = QHBoxLayout(cell_box)
            box_layout.setContentsMargins(2, 2, 2, 2)
            box_layout.setSpacing(4)

            btn_pick = QToolButton()
            btn_pick.setIcon(IconFactory.get_icon("select", 14))
            btn_pick.setText(f" {tr('dialog.path.pick')}")
            btn_pick.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn_pick.setToolTip(tr("path.pick_tooltip"))
            btn_pick.clicked.connect(lambda ch, rk=role_key: self._pick_role_tile(rk))
            box_layout.addWidget(btn_pick)

            btn_del = QToolButton()
            btn_del.setIcon(IconFactory.get_icon("trash", 14))
            btn_del.setToolTip(tr("path.delete_assignment_tooltip"))
            btn_del.clicked.connect(lambda ch, rk=role_key: self._clear_role_tile(rk))
            box_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 3, cell_box)

        # Status summary
        total = len(roles)
        if assigned_count == total:
            self.lbl_status.setText(
                tr("dialog.path.complete", assigned=assigned_count, total=total)
            )
            self.lbl_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        else:
            self.lbl_status.setText(
                tr("dialog.path.incomplete", assigned=assigned_count, total=total)
            )
            self.lbl_status.setStyleSheet("color: #f87171; font-weight: bold;")

    def _assign_from_current_selection(self, role_key: str) -> None:
        """Assigns current palette selection to the given role slot."""
        if not self.current_ruleset:
            return

        sel = self.asset_manager.selected_item
        if not sel:
            QMessageBox.information(
                self,
                tr("dialog.path.no_selection_title"),
                tr("dialog.path.no_selection"),
            )
            return

        if isinstance(sel, SelectedSubTile):
            tile_data = (sel.asset_id, sel.sub_x, sel.sub_y, sel.tile_width, sel.tile_height)
        else:
            aid = getattr(sel, "id", "")
            tile_data = (aid, 0, 0, 32, 32)

        self.current_ruleset.set_role_tile(role_key, tile_data)
        self._populate_roles_table()
        self.preview_widget.update()

    def _pick_role_tile(self, role_key: str) -> None:
        picker = PathTilePickerDialog(self.asset_manager, self)
        picker.selection_picked.connect(
            lambda selection: self._assign_selection(role_key, selection)
        )
        picker.exec()

    def _assign_selection(self, role_key: str, sel) -> None:
        if not isinstance(sel, SelectedSubTile):
            return
        self.current_ruleset.set_role_tile(
            role_key,
            (
                sel.asset_id,
                sel.sub_x,
                sel.sub_y,
                sel.tile_width,
                sel.tile_height,
            ),
        )
        self._populate_roles_table()
        self.preview_widget.update()

    def _clear_role_tile(self, role_key: str) -> None:
        if not self.current_ruleset:
            return
        self.current_ruleset.set_role_tile(role_key, None)
        self._populate_roles_table()
        self.preview_widget.update()

    def _auto_fill_from_palette_3x3(self) -> None:
        """Auto-fills roles if a 3x3 block is selected in the palette."""
        if not self.current_ruleset:
            return
        sel = self.asset_manager.selected_item
        if not isinstance(sel, SelectedSubTile) or sel.cols_count < 3 or sel.rows_count < 3:
            QMessageBox.information(
                self,
                tr("dialog.path.need_3x3_title"),
                tr("dialog.path.need_3x3"),
            )
            return

        # Map standard 3x3 positions to path roles:
        # (1, 0) = top/V, (1, 2) = bottom/V -> straight_v
        # (0, 1) = left/H, (2, 1) = right/H -> straight_h
        # (0, 0) = TL bend, (2, 0) = TR bend, (0, 2) = BL bend, (2, 2) = BR bend
        # (1, 1) = Cross / Center
        aid = sel.asset_id
        def _slice(c, r):
            sx, sy, sw, sh = sel.get_tile_slice(c, r)
            return (aid, sx, sy, sw, sh)

        self.current_ruleset.set_role_tile(ROLE_STRAIGHT_H, _slice(1, 1))  # or (0, 1)
        self.current_ruleset.set_role_tile(ROLE_STRAIGHT_V, _slice(1, 1))  # or (1, 0)
        self.current_ruleset.set_role_tile(ROLE_CORNER_TL, _slice(0, 0))
        self.current_ruleset.set_role_tile(ROLE_CORNER_TR, _slice(2, 0))
        self.current_ruleset.set_role_tile(ROLE_CORNER_BL, _slice(0, 2))
        self.current_ruleset.set_role_tile(ROLE_CORNER_BR, _slice(2, 2))
        self.current_ruleset.set_role_tile(ROLE_CORNER_GENERIC, _slice(0, 0))
        self.current_ruleset.set_role_tile(ROLE_CROSS, _slice(1, 1))
        self.current_ruleset.set_role_tile(ROLE_T_JUNCTION, _slice(1, 0))
        self.current_ruleset.set_role_tile(ROLE_END, _slice(1, 2))
        self.current_ruleset.set_role_tile(ROLE_CENTER, _slice(1, 1))
        self.current_ruleset.set_role_tile(ROLE_EDGE_TOP, _slice(1, 0))
        self.current_ruleset.set_role_tile(ROLE_EDGE_LEFT, _slice(0, 1))
        self.current_ruleset.set_role_tile(ROLE_EDGE_RIGHT, _slice(2, 1))
        self.current_ruleset.set_role_tile(ROLE_EDGE_BOTTOM, _slice(1, 2))
        self.current_ruleset.set_role_tile(ROLE_START, _slice(0, 1))

        self._populate_roles_table()
        self.preview_widget.update()

    def _save_and_close(self) -> None:
        if self.current_ruleset:
            self.engine.active_ruleset_id = self.current_ruleset.id
        self.path_rulesets_changed.emit()
        self.accept()


class PathTilePickerDialog(QDialog):
    selection_picked = pyqtSignal(object)

    def __init__(self, asset_manager: AssetManager, parent=None):
        super().__init__(parent)
        from ..tileset_palette_widget import TilesetCanvas

        self.setWindowTitle("Wybierz pojedynczą kratkę")
        self.resize(760, 540)
        self.asset_manager = asset_manager
        self.selection = asset_manager.selected_item
        layout = QVBoxLayout(self)
        self.combo = QComboBox()
        for asset in asset_manager.assets.values():
            if asset.asset_type == AssetType.TILESET:
                self.combo.addItem(asset.name, asset.id)
        layout.addWidget(self.combo)
        self.canvas = TilesetCanvas(asset_manager, self)
        self.canvas.selection_changed.connect(self._on_selection)
        layout.addWidget(self.canvas, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.combo.currentIndexChanged.connect(self._load_asset)
        selected_id = getattr(self.selection, "asset_id", "")
        index = self.combo.findData(selected_id)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        self._load_asset()

    def _load_asset(self, *_args) -> None:
        asset = self.asset_manager.get_asset(self.combo.currentData())
        self.canvas.set_asset(asset)

    def _on_selection(self, selection) -> None:
        self.selection = selection

    def _accept_selection(self) -> None:
        if not isinstance(self.selection, SelectedSubTile):
            QMessageBox.warning(
                self, "Brak wyboru", "Kliknij pojedynczą kratkę w tilesecie."
            )
            return
        self.selection_picked.emit(self.selection)
        self.accept()
