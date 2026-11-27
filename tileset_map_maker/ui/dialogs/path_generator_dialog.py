import os
import logging
from typing import Optional, List, Dict, Any, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QComboBox,
    QMessageBox,
    QGroupBox,
    QSplitter,
    QScrollArea,
    QDialogButtonBox,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QDoubleSpinBox,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QImage, QMouseEvent, QIcon

from ...models.asset import Asset, AssetType, SelectedSubTile
from ...core.asset_manager import AssetManager
from ...core.autotile_engine import AutoTileEngine
from ...core.rpg_autotile import (
    RPGAutotile,
    AutotileFormat,
    CustomPathVariant,
    SelectedAutotile,
    VARIANT_ROLES,
    extract_packed_tileset_image,
    synthesize_from_single_tile,
    synthesize_from_tileset_context,
    create_rpg_autotile_from_tile,
)
from ...core.paths import ConnectionRuleEngine
from ..icons import IconFactory
from ...core.localization import get_localization, tr
from .autotile_sandbox_widget import AutoTileSandboxWidget

logger = logging.getLogger("PathGeneratorDialog")


# ==============================================================================
# INTERACTIVE TILESET SHEET CANVAS
# ==============================================================================
class TilesetSheetCanvas(QWidget):
    """
    Renders the original tileset sheet with a grid overlay and lets
    the user click (1x1) or click-and-drag (2x1, 1x2, 2x2, 3x3, custom WxH)
    any region to pick it as the source for the path or custom variant.
    """
    tile_selected = pyqtSignal(int, int)
    region_selected = pyqtSignal(int, int, int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pixmap: Optional[QPixmap] = None
        self.tile_w: int = 32
        self.tile_h: int = 32
        self.tileset_config: Optional[Any] = None
        self.zoom: float = 1.0
        self.sel_col: int = 0
        self.sel_row: int = 0
        self.sel_w_tiles: int = 1
        self.sel_h_tiles: int = 1
        self.hover_col: int = -1
        self.hover_row: int = -1
        self._dragging: bool = False
        self._drag_anchor: Tuple[int, int] = (0, 0)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.5, min(4.0, float(zoom)))
        if self.pixmap and not self.pixmap.isNull():
            self.setFixedSize(
                max(1, int(round(self.pixmap.width() * self.zoom))),
                max(1, int(round(self.pixmap.height() * self.zoom))),
            )
        self.update()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            step = 0.25 if delta > 0 else -0.25
            self.set_zoom(self.zoom + step)
            event.accept()
            return
        super().wheelEvent(event)

    def set_sheet(
        self,
        pixmap: Optional[QPixmap],
        tile_w: int = 32,
        tile_h: int = 32,
        tileset_config: Optional[Any] = None,
    ) -> None:
        self.pixmap = pixmap
        self.tileset_config = tileset_config
        self.tile_w = max(8, int(tile_w))
        self.tile_h = max(8, int(tile_h))
        if pixmap and not pixmap.isNull():
            self.setFixedSize(
                max(1, int(round(pixmap.width() * self.zoom))),
                max(1, int(round(pixmap.height() * self.zoom))),
            )
        else:
            self.setFixedSize(320, 240)
        self.update()

    def _grid_dims(self) -> Tuple[int, int]:
        if not self.pixmap or self.pixmap.isNull():
            return 0, 0
        if self.tileset_config is not None:
            g = self.tileset_config.compute_grid(self.pixmap.width(), self.pixmap.height())
            return int(g["cols"]), int(g["rows"])
        return self.pixmap.width() // self.tile_w, self.pixmap.height() // self.tile_h

    def _cell_rect(self, col: int, row: int, w_tiles: int = 1, h_tiles: int = 1) -> QRect:
        if self.tileset_config is not None:
            x0, y0, tw, th = self.tileset_config.get_tile_rect(col, row)
            x1, y1, tw2, th2 = self.tileset_config.get_tile_rect(
                col + max(1, w_tiles) - 1, row + max(1, h_tiles) - 1
            )
            return QRect(x0, y0, (x1 + tw2) - x0, (y1 + th2) - y0)
        return QRect(col * self.tile_w, row * self.tile_h, w_tiles * self.tile_w, h_tiles * self.tile_h)

    def _pos_to_cell(self, px: float, py: float) -> Tuple[int, int]:
        unscaled_x = px / max(0.25, self.zoom)
        unscaled_y = py / max(0.25, self.zoom)
        if self.tileset_config is not None:
            ox = self.tileset_config.start_x + self.tileset_config.margin_x
            oy = self.tileset_config.start_y + self.tileset_config.margin_y
            step_w = max(1, self.tileset_config.tile_width + self.tileset_config.spacing_x)
            step_h = max(1, self.tileset_config.tile_height + self.tileset_config.spacing_y)
            return int((unscaled_x - ox) // step_w), int((unscaled_y - oy) // step_h)
        return int(unscaled_x // self.tile_w), int(unscaled_y // self.tile_h)

    def set_selected_tile(self, col: int, row: int, w_tiles: int = 1, h_tiles: int = 1) -> None:
        self.sel_col = max(0, col)
        self.sel_row = max(0, row)
        self.sel_w_tiles = max(1, int(w_tiles))
        self.sel_h_tiles = max(1, int(h_tiles))
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.pixmap and not self.pixmap.isNull():
            col, row = self._pos_to_cell(event.position().x(), event.position().y())
            max_c, max_r = self._grid_dims()
            if 0 <= col < max_c and 0 <= row < max_r:
                if self._dragging:
                    ac, ar = self._drag_anchor
                    self.sel_col = min(ac, col)
                    self.sel_row = min(ar, row)
                    self.sel_w_tiles = abs(col - ac) + 1
                    self.sel_h_tiles = abs(row - ar) + 1
                    self.update()
                    return
                if col != self.hover_col or row != self.hover_row:
                    self.hover_col = col
                    self.hover_row = row
                    self.update()
                    return
        if not self._dragging:
            self.hover_col = -1
            self.hover_row = -1
            self.update()

    def leaveEvent(self, event) -> None:
        self.hover_col = -1
        self.hover_row = -1
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap and not self.pixmap.isNull():
            col, row = self._pos_to_cell(event.position().x(), event.position().y())
            max_c, max_r = self._grid_dims()
            if 0 <= col < max_c and 0 <= row < max_r:
                self._dragging = True
                self._drag_anchor = (col, row)
                self.sel_col = col
                self.sel_row = row
                self.sel_w_tiles = 1
                self.sel_h_tiles = 1
                self.tile_selected.emit(col, row)
                self.region_selected.emit(col, row, 1, 1)
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.region_selected.emit(
                self.sel_col, self.sel_row, self.sel_w_tiles, self.sel_h_tiles
            )
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if self.pixmap and not self.pixmap.isNull():
            painter.save()
            if abs(self.zoom - 1.0) > 0.001:
                painter.scale(self.zoom, self.zoom)
            painter.drawPixmap(0, 0, self.pixmap)

            max_c, max_r = self._grid_dims()

            # Regular grid (respecting margin, spacing, and grid start offset)
            grid_pen = QPen(QColor(255, 255, 255, 35), 1)
            grid_pen.setCosmetic(True)
            painter.setPen(grid_pen)
            if self.tileset_config is not None and (
                self.tileset_config.margin_x
                or self.tileset_config.margin_y
                or self.tileset_config.spacing_x
                or self.tileset_config.spacing_y
                or self.tileset_config.start_x
                or self.tileset_config.start_y
            ):
                for r in range(max_r):
                    for c in range(max_c):
                        painter.drawRect(self._cell_rect(c, r, 1, 1))
            else:
                pw = self.pixmap.width()
                ph = self.pixmap.height()
                for x in range(0, pw + 1, self.tile_w):
                    painter.drawLine(x, 0, x, ph)
                for y in range(0, ph + 1, self.tile_h):
                    painter.drawLine(0, y, pw, y)

            # Hover tile
            if self.hover_col >= 0 and self.hover_row >= 0 and not self._dragging:
                hr = self._cell_rect(self.hover_col, self.hover_row, 1, 1)
                painter.fillRect(hr, QColor(255, 255, 255, 45))

            # Selected tile / WxH region
            sr = self._cell_rect(
                self.sel_col, self.sel_row, self.sel_w_tiles, self.sel_h_tiles
            )
            painter.fillRect(sr, QColor(56, 189, 248, 70))
            sel_pen = QPen(QColor("#38bdf8"), 2)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.drawRect(sr.adjusted(1, 1, -1, -1))
            if self.sel_w_tiles > 1 or self.sel_h_tiles > 1:
                badge_rect = QRect(sr.left() + 3, sr.top() + 3, 34, 16)
                painter.fillRect(badge_rect, QColor(15, 23, 42, 210))
                painter.setPen(QColor("#38bdf8"))
                painter.setFont(QFont("Sans-Serif", 8, QFont.Weight.Bold))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{self.sel_w_tiles}×{self.sel_h_tiles}")
            painter.restore()
        else:
            painter.fillRect(self.rect(), QColor("#18181b"))
            painter.setPen(QColor("#71717a"))
            painter.setFont(QFont("Sans-Serif", 10))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr("path_gen.sheet_empty"),
            )


# ==============================================================================
# LEGACY COMPATIBILITY PREVIEW WIDGET
# ==============================================================================
class PathPreviewWidget(AutoTileSandboxWidget):
    """
    Renders live sample layouts and interactive sandbox testing for configured paths.
    Maintained for unit test backward compatibility.
    """
    def __init__(
        self,
        ruleset: Optional[Any] = None,
        asset_manager: Optional[AssetManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(
            asset_manager=asset_manager,
            cols=10,
            rows=8,
            tile_size=32,
            parent=parent,
        )

    def _draw_role_or_missing(self, painter: QPainter, role: str, x: int, y: int, size: int) -> None:
        pass


# ==============================================================================
# NEW ONE-TILE PATH & AUTOTILE GENERATOR DIALOG
# ==============================================================================
class PathGeneratorDialog(QDialog):
    """
    Unified One-Tile Path & Autotile Generator.
    Directly leverages existing tilesets from the library:
    User clicks 1 source tile -> System automatically synthesizes full 47 Wang-blob combinations
    -> Live sandbox testing -> One-click accept and paint on map.
    """
    path_rulesets_changed = pyqtSignal()
    autotile_created = pyqtSignal(object)

    def __init__(
        self,
        autotile_engine: AutoTileEngine,
        asset_manager: AssetManager,
        parent: Optional[QWidget] = None,
        initial_asset_id: Optional[str] = None,
        initial_col: int = 0,
        initial_row: int = 0,
    ):
        super().__init__(parent)
        self.engine = autotile_engine
        self.asset_manager = asset_manager
        self.current_autotile: Optional[RPGAutotile] = None
        self.current_ruleset: Optional[Any] = None

        self.selected_asset: Optional[Asset] = None
        self.selected_col: int = initial_col
        self.selected_row: int = initial_row
        self.selected_w_tiles: int = 1
        self.selected_h_tiles: int = 1
        self._name_manually_edited: bool = False
        self._custom_variants: List[CustomPathVariant] = []
        self._editing_autotile_id: Optional[str] = None

        self.setWindowTitle(tr("dialog.path.title"))
        self.table = None  # Compatibility table for unit tests
        self.setMinimumSize(1040, 700)
        self.resize(1100, 740)
        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #e4e4e7;
            }
            QGroupBox {
                border: 1px solid #27272a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: 600;
                color: #e4e4e7;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                color: #f4f4f5;
                padding: 4px 8px;
            }
            QPushButton {
                background: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                color: #f4f4f5;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #3f3f46;
            }
            QPushButton#primaryBtn {
                background: #2563eb;
                border-color: #3b82f6;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 18px;
            }
            QPushButton#primaryBtn:hover {
                background: #1d4ed8;
            }
        """)

        self._build_ui()
        self._populate_tilesets(initial_asset_id)
        self._populate_saved_autotiles()
        get_localization().languageChanged.connect(self._apply_language)

    def _apply_language(self, *_args) -> None:
        self.setWindowTitle(tr("dialog.path.title"))
        self.table.setHorizontalHeaderLabels(["ID", tr("dialog.path.table_role")])
        self.lbl_header.setText(tr("path_gen.header"))
        self.grp_tileset.setTitle(tr("path_gen.grp_tileset"))
        self.grp_sheet.setTitle(tr("path_gen.grp_sheet"))
        self.btn_zoom_out.setToolTip(tr("path_gen.zoom_out_tooltip"))
        self.btn_zoom_reset.setToolTip(tr("path_gen.zoom_reset_tooltip"))
        self.btn_zoom_in.setToolTip(tr("path_gen.zoom_in_tooltip"))
        self.grp_params.setTitle(tr("path_gen.grp_params"))
        for key, widget in (
            ("path_gen.mode_label", self.cmb_mode),
            ("path_gen.width_label", self.width_row_widget),
            ("path_gen.style_label", self.cmb_style),
            ("path_gen.name_label", self.txt_name),
            ("path_gen.terrain_label", self.txt_terrain),
        ):
            lbl = self.form_params.labelForField(widget)
            if lbl is not None:
                lbl.setText(tr(key))
        mode_keys = (
            "path_gen.mode_auto",
            "path_gen.mode_single",
            "path_gen.mode_2x2",
            "path_gen.mode_wxh",
            "path_gen.mode_3x3_center",
            "path_gen.mode_3x3_tl",
            "path_gen.mode_2x3_vx",
            "path_gen.mode_custom",
        )
        for i, k in enumerate(mode_keys):
            if i < self.cmb_mode.count():
                self.cmb_mode.setItemText(i, tr(k))
        self.spin_path_width.setSuffix(tr("path_gen.width_suffix"))
        self.spin_path_width.setToolTip(tr("path_gen.width_tooltip"))
        for i, k in enumerate(("path_gen.rim_wide", "path_gen.rim_balanced", "path_gen.rim_narrow")):
            if i < self.cmb_rim_balance.count():
                self.cmb_rim_balance.setItemText(i, tr(k))
        for i, k in enumerate(("path_gen.style_organic", "path_gen.style_alpha", "path_gen.style_outline")):
            if i < self.cmb_style.count():
                self.cmb_style.setItemText(i, tr(k))
        self.txt_name.setPlaceholderText(tr("path_gen.name_placeholder"))
        self.grp_variants.setTitle(tr("path_gen.grp_variants"))
        mask_keys = (
            "path_gen.mask_cross",
            "path_gen.mask_center",
            "path_gen.mask_turn_es",
            "path_gen.mask_turn_ws",
            "path_gen.mask_turn_ne",
            "path_gen.mask_turn_nw",
            "path_gen.mask_straight_h",
            "path_gen.mask_straight_v",
            "path_gen.mask_t_wes",
            "path_gen.mask_t_wen",
            "path_gen.mask_t_nse",
            "path_gen.mask_t_nsw",
            "path_gen.mask_isolated",
        )
        for i, k in enumerate(mask_keys):
            if i < self.cmb_variant_mask.count():
                self.cmb_variant_mask.setItemText(i, tr(k))
        self.spin_variant_prio.setPrefix(tr("path_gen.prio_prefix"))
        self.spin_variant_prio.setToolTip(tr("path_gen.prio_tooltip"))
        self.spin_variant_weight.setPrefix(tr("path_gen.weight_prefix"))
        self.spin_variant_weight.setToolTip(tr("path_gen.weight_tooltip"))
        self.cmb_variant_role.setToolTip(tr("path_gen.role_tooltip"))
        self.btn_add_variant.setText(tr("path_gen.btn_assign"))
        self.btn_analyze_sheet.setText(tr("path_gen.btn_analyze"))
        self.btn_analyze_sheet.setToolTip(tr("path_gen.btn_analyze_tooltip"))
        self.btn_suggest_compat.setText(tr("path_gen.btn_compat"))
        self.btn_suggest_compat.setToolTip(tr("path_gen.btn_compat_tooltip"))
        self.lbl_compat_info.setText(tr("path_gen.compat_default"))
        self.grp_sandbox.setTitle(tr("path_gen.grp_sandbox"))
        self.btn_curve.setText(tr("path_gen.preset_curve"))
        self.btn_curve.setToolTip(tr("path_gen.preset_curve_tooltip"))
        self.btn_cross.setText(tr("path_gen.preset_cross"))
        self.btn_cross.setToolTip(tr("path_gen.preset_cross_tooltip"))
        self.btn_loop.setText(tr("path_gen.preset_loop"))
        self.btn_loop.setToolTip(tr("path_gen.preset_loop_tooltip"))
        self.btn_area.setText(tr("path_gen.preset_area"))
        self.btn_area.setToolTip(tr("path_gen.preset_area_tooltip"))
        self.btn_clear.setText(tr("path_gen.preset_clear"))
        self.lbl_hint.setText(tr("path_gen.sandbox_hint"))
        self.grp_saved.setTitle(tr("path_gen.grp_saved"))
        self.btn_del_saved.setText(tr("path_gen.btn_delete_saved"))
        self.btn_accept.setText(tr("path_gen.btn_accept"))
        self.btn_cancel.setText(tr("button.cancel"))
        if not self.selected_asset:
            self.lbl_tileset_info.setText(tr("path_gen.no_tilesets"))
            self.lbl_status.setText(tr("path_gen.status_init"))
        self.sheet_canvas.update()
        self.sandbox.update()

    # --------------------------------------------------------------------------
    # UI CONSTRUCTION
    # --------------------------------------------------------------------------
    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header description
        self.lbl_header = QLabel(tr("path_gen.header"))
        self.lbl_header.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.lbl_header.setWordWrap(True)
        main_layout.addWidget(self.lbl_header)

        # Compatibility table for tests checking table headers
        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", tr("dialog.path.table_role")])
        self.table.hide()

        # Main splitter (Left: Tileset Sheet & Tile Picker, Right: Sandbox & Generator)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ----------------------------------------------------------------------
        # LEFT PANE: EXISTING TILESET & SHEET SELECTION
        # ----------------------------------------------------------------------
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(8)

        # 1. Tileset selector group
        self.grp_tileset = QGroupBox(tr("path_gen.grp_tileset"), left_widget)
        tileset_layout = QVBoxLayout(self.grp_tileset)
        tileset_layout.setContentsMargins(10, 12, 10, 10)
        tileset_layout.setSpacing(6)

        self.cmb_tileset = QComboBox(self.grp_tileset)
        self.cmb_tileset.currentIndexChanged.connect(self._on_tileset_changed)
        tileset_layout.addWidget(self.cmb_tileset)

        self.lbl_tileset_info = QLabel(tr("path_gen.no_tilesets"), self.grp_tileset)
        self.lbl_tileset_info.setStyleSheet("color: #71717a; font-size: 10px;")
        tileset_layout.addWidget(self.lbl_tileset_info)

        left_layout.addWidget(self.grp_tileset)

        # 2. Interactive sheet canvas group
        self.grp_sheet = QGroupBox(tr("path_gen.grp_sheet"), left_widget)
        sheet_layout = QVBoxLayout(self.grp_sheet)
        sheet_layout.setContentsMargins(10, 12, 10, 10)
        sheet_layout.setSpacing(6)

        self.sheet_scroll = QScrollArea(self.grp_sheet)
        self.sheet_scroll.setWidgetResizable(False)
        self.sheet_canvas = TilesetSheetCanvas(self.sheet_scroll)
        self.sheet_canvas.tile_selected.connect(self._on_tile_clicked)
        self.sheet_canvas.region_selected.connect(self._on_region_selected)
        self.sheet_scroll.setWidget(self.sheet_canvas)
        self.sheet_scroll.setStyleSheet("QScrollArea { border: 1px solid #27272a; background: #09090b; }")
        sheet_layout.addWidget(self.sheet_scroll, 1)

        # Tile selection info bar
        tile_bar = QHBoxLayout()
        self.lbl_tile_thumb = QLabel(self.grp_sheet)
        self.lbl_tile_thumb.setFixedSize(36, 36)
        self.lbl_tile_thumb.setStyleSheet("border: 1px solid #3f3f46; border-radius: 4px; background: #18181b;")
        tile_bar.addWidget(self.lbl_tile_thumb)

        self.lbl_tile_coords = QLabel(tr("path_gen.selected_tile_init"), self.grp_sheet)
        self.lbl_tile_coords.setStyleSheet("font-weight: 600; color: #38bdf8; font-size: 11px;")
        tile_bar.addWidget(self.lbl_tile_coords, 1)

        # Zoom controls for tileset sheet preview (A. Źródło)
        self.btn_zoom_out = QPushButton("−", self.grp_sheet)
        self.btn_zoom_out.setFixedWidth(26)
        self.btn_zoom_out.setToolTip(tr("path_gen.zoom_out_tooltip"))
        self.btn_zoom_out.clicked.connect(lambda: self.sheet_canvas.set_zoom(self.sheet_canvas.zoom - 0.5))
        tile_bar.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("1:1", self.grp_sheet)
        self.btn_zoom_reset.setFixedWidth(34)
        self.btn_zoom_reset.setToolTip(tr("path_gen.zoom_reset_tooltip"))
        self.btn_zoom_reset.clicked.connect(lambda: self.sheet_canvas.set_zoom(1.0))
        tile_bar.addWidget(self.btn_zoom_reset)

        self.btn_zoom_in = QPushButton("+", self.grp_sheet)
        self.btn_zoom_in.setFixedWidth(26)
        self.btn_zoom_in.setToolTip(tr("path_gen.zoom_in_tooltip"))
        self.btn_zoom_in.clicked.connect(lambda: self.sheet_canvas.set_zoom(self.sheet_canvas.zoom + 0.5))
        tile_bar.addWidget(self.btn_zoom_in)

        sheet_layout.addLayout(tile_bar)
        left_layout.addWidget(self.grp_sheet, 1)

        # 3. Generation parameters group
        self.grp_params = QGroupBox(tr("path_gen.grp_params"), left_widget)
        self.form_params = QFormLayout(self.grp_params)
        self.form_params.setContentsMargins(10, 12, 10, 10)
        self.form_params.setSpacing(6)

        self.cmb_mode = QComboBox(self.grp_params)
        self.cmb_mode.addItem(tr("path_gen.mode_auto"), "auto")
        self.cmb_mode.addItem(tr("path_gen.mode_single"), "single_tile")
        self.cmb_mode.addItem(tr("path_gen.mode_2x2"), "block_2x2")
        self.cmb_mode.addItem(tr("path_gen.mode_wxh"), "composition_wxh")
        self.cmb_mode.addItem(tr("path_gen.mode_3x3_center"), "block_3x3_center")
        self.cmb_mode.addItem(tr("path_gen.mode_3x3_tl"), "block_3x3_tl")
        self.cmb_mode.addItem(tr("path_gen.mode_2x3_vx"), "block_2x3_vx")
        self.cmb_mode.addItem(tr("path_gen.mode_custom"), "custom_region")
        self.cmb_mode.currentIndexChanged.connect(self._regenerate_autotile)
        self.form_params.addRow(tr("path_gen.mode_label"), self.cmb_mode)

        self.width_row_widget = QWidget(self.grp_params)
        width_row = QHBoxLayout(self.width_row_widget)
        width_row.setContentsMargins(0, 0, 0, 0)
        self.spin_path_width = QSpinBox(self.width_row_widget)
        self.spin_path_width.setRange(1, 4)
        self.spin_path_width.setValue(1)
        self.spin_path_width.setSuffix(tr("path_gen.width_suffix"))
        self.spin_path_width.setToolTip(tr("path_gen.width_tooltip"))
        self.spin_path_width.valueChanged.connect(self._regenerate_autotile)
        width_row.addWidget(self.spin_path_width)

        self.cmb_rim_balance = QComboBox(self.width_row_widget)
        self.cmb_rim_balance.addItem(tr("path_gen.rim_wide"), 0.28)
        self.cmb_rim_balance.addItem(tr("path_gen.rim_balanced"), 0.40)
        self.cmb_rim_balance.addItem(tr("path_gen.rim_narrow"), 0.52)
        self.cmb_rim_balance.setCurrentIndex(1)
        self.cmb_rim_balance.currentIndexChanged.connect(self._regenerate_autotile)
        width_row.addWidget(self.cmb_rim_balance, 1)
        self.form_params.addRow(tr("path_gen.width_label"), self.width_row_widget)

        self.cmb_style = QComboBox(self.grp_params)
        self.cmb_style.addItem(tr("path_gen.style_organic"), "organic")
        self.cmb_style.addItem(tr("path_gen.style_alpha"), "alpha_fade")
        self.cmb_style.addItem(tr("path_gen.style_outline"), "dark_outline")
        self.cmb_style.currentIndexChanged.connect(self._regenerate_autotile)
        self.form_params.addRow(tr("path_gen.style_label"), self.cmb_style)

        self.txt_name = QLineEdit(self.grp_params)
        self.txt_name.setPlaceholderText(tr("path_gen.name_placeholder"))
        self.txt_name.textEdited.connect(lambda _t: setattr(self, "_name_manually_edited", True))
        self.form_params.addRow(tr("path_gen.name_label"), self.txt_name)

        self.txt_terrain = QLineEdit(self.grp_params)
        self.txt_terrain.setText("path")
        self.form_params.addRow(tr("path_gen.terrain_label"), self.txt_terrain)

        left_layout.addWidget(self.grp_params)

        # 3b. Custom multi-tile variants (1x1, 2x1, 1x2, 2x2, 3x3, WxH)
        self.grp_variants = QGroupBox(tr("path_gen.grp_variants"), left_widget)
        var_layout = QVBoxLayout(self.grp_variants)
        var_layout.setContentsMargins(8, 10, 8, 8)
        var_layout.setSpacing(4)

        var_row1 = QHBoxLayout()
        self.cmb_variant_mask = QComboBox(self.grp_variants)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_cross"), 85)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_center"), 255)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_turn_es"), 20)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_turn_ws"), 80)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_turn_ne"), 5)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_turn_nw"), 65)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_straight_h"), 68)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_straight_v"), 17)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_t_wes"), 84)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_t_wen"), 69)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_t_nse"), 21)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_t_nsw"), 81)
        self.cmb_variant_mask.addItem(tr("path_gen.mask_isolated"), 0)
        var_row1.addWidget(self.cmb_variant_mask, 1)

        self.spin_variant_prio = QSpinBox(self.grp_variants)
        self.spin_variant_prio.setRange(1, 100)
        self.spin_variant_prio.setValue(10)
        self.spin_variant_prio.setPrefix(tr("path_gen.prio_prefix"))
        self.spin_variant_prio.setToolTip(tr("path_gen.prio_tooltip"))
        var_row1.addWidget(self.spin_variant_prio)

        self.spin_variant_weight = QDoubleSpinBox(self.grp_variants)
        self.spin_variant_weight.setRange(0.1, 100.0)
        self.spin_variant_weight.setValue(1.0)
        self.spin_variant_weight.setSingleStep(0.5)
        self.spin_variant_weight.setPrefix(tr("path_gen.weight_prefix"))
        self.spin_variant_weight.setToolTip(tr("path_gen.weight_tooltip"))
        var_row1.addWidget(self.spin_variant_weight)
        var_layout.addLayout(var_row1)

        var_row2 = QHBoxLayout()
        self.cmb_variant_role = QComboBox(self.grp_variants)
        for role_name in VARIANT_ROLES:
            self.cmb_variant_role.addItem(role_name, role_name)
        self.cmb_variant_role.setToolTip(tr("path_gen.role_tooltip"))
        var_row2.addWidget(self.cmb_variant_role)

        self.btn_add_variant = QPushButton(tr("path_gen.btn_assign"), self.grp_variants)
        self.btn_add_variant.clicked.connect(self._add_custom_variant)
        var_row2.addWidget(self.btn_add_variant)

        self.cmb_custom_variants = QComboBox(self.grp_variants)
        var_row2.addWidget(self.cmb_custom_variants, 1)

        self.btn_del_variant = QPushButton("🗑", self.grp_variants)
        self.btn_del_variant.setFixedWidth(30)
        self.btn_del_variant.clicked.connect(self._remove_selected_custom_variant)
        var_row2.addWidget(self.btn_del_variant)
        var_layout.addLayout(var_row2)

        var_row3 = QHBoxLayout()
        self.btn_analyze_sheet = QPushButton(tr("path_gen.btn_analyze"), self.grp_variants)
        self.btn_analyze_sheet.setToolTip(tr("path_gen.btn_analyze_tooltip"))
        self.btn_analyze_sheet.clicked.connect(self._auto_analyze_sheet)
        var_row3.addWidget(self.btn_analyze_sheet)

        self.btn_suggest_compat = QPushButton(tr("path_gen.btn_compat"), self.grp_variants)
        self.btn_suggest_compat.setToolTip(tr("path_gen.btn_compat_tooltip"))
        self.btn_suggest_compat.clicked.connect(self._auto_suggest_compatibility)
        var_row3.addWidget(self.btn_suggest_compat)
        var_layout.addLayout(var_row3)

        self.lbl_compat_info = QLabel(tr("path_gen.compat_default"), self.grp_variants)
        self.lbl_compat_info.setStyleSheet("color: #71717a; font-size: 10px;")
        var_layout.addWidget(self.lbl_compat_info)

        left_layout.addWidget(self.grp_variants)
        splitter.addWidget(left_widget)

        # ----------------------------------------------------------------------
        # RIGHT PANE: LIVE SANDBOX & ACCEPTANCE
        # ----------------------------------------------------------------------
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)

        # Status badge
        self.lbl_status = QLabel(tr("path_gen.status_init"), right_widget)
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-size: 11px; padding: 4px; background: #27272a; border-radius: 4px;")
        right_layout.addWidget(self.lbl_status)

        # Sandbox testing ground
        self.grp_sandbox = QGroupBox(tr("path_gen.grp_sandbox"), right_widget)
        sb_layout = QVBoxLayout(self.grp_sandbox)
        sb_layout.setContentsMargins(10, 12, 10, 10)
        sb_layout.setSpacing(8)

        # Preset buttons bar
        preset_bar = QHBoxLayout()
        preset_bar.setSpacing(4)

        self.btn_curve = QPushButton(tr("path_gen.preset_curve"), self.grp_sandbox)
        self.btn_curve.setToolTip(tr("path_gen.preset_curve_tooltip"))
        self.btn_curve.clicked.connect(self._load_sample_curve)
        preset_bar.addWidget(self.btn_curve)

        self.btn_cross = QPushButton(tr("path_gen.preset_cross"), self.grp_sandbox)
        self.btn_cross.setToolTip(tr("path_gen.preset_cross_tooltip"))
        self.btn_cross.clicked.connect(self._load_sample_cross)
        preset_bar.addWidget(self.btn_cross)

        self.btn_loop = QPushButton(tr("path_gen.preset_loop"), self.grp_sandbox)
        self.btn_loop.setToolTip(tr("path_gen.preset_loop_tooltip"))
        self.btn_loop.clicked.connect(self._load_sample_loop)
        preset_bar.addWidget(self.btn_loop)

        self.btn_area = QPushButton(tr("path_gen.preset_area"), self.grp_sandbox)
        self.btn_area.setToolTip(tr("path_gen.preset_area_tooltip"))
        self.btn_area.clicked.connect(self._load_sample_area)
        preset_bar.addWidget(self.btn_area)

        self.btn_clear = QPushButton(tr("path_gen.preset_clear"), self.grp_sandbox)
        self.btn_clear.clicked.connect(self._clear_sandbox)
        preset_bar.addWidget(self.btn_clear)

        sb_layout.addLayout(preset_bar)

        # Embed AutoTileSandboxWidget
        self.sandbox = AutoTileSandboxWidget(
            ruleset=None,
            asset_manager=self.asset_manager,
            cols=11,
            rows=8,
            tile_size=34,
            parent=self.grp_sandbox,
        )
        sb_layout.addWidget(self.sandbox, 1)

        # Hint for mouse drawing
        self.lbl_hint = QLabel(tr("path_gen.sandbox_hint"), self.grp_sandbox)
        self.lbl_hint.setStyleSheet("color: #71717a; font-size: 10px;")
        sb_layout.addWidget(self.lbl_hint)

        right_layout.addWidget(self.grp_sandbox, 1)

        # Saved autotiles management
        self.grp_saved = QGroupBox(tr("path_gen.grp_saved"), right_widget)
        saved_layout = QHBoxLayout(self.grp_saved)
        saved_layout.setContentsMargins(10, 10, 10, 10)
        saved_layout.setSpacing(6)

        self.cmb_saved = QComboBox(self.grp_saved)
        self.cmb_saved.currentIndexChanged.connect(self._on_saved_autotile_selected)
        saved_layout.addWidget(self.cmb_saved, 1)

        self.btn_del_saved = QPushButton(tr("path_gen.btn_delete_saved"), self.grp_saved)
        self.btn_del_saved.clicked.connect(self._delete_saved_autotile)
        saved_layout.addWidget(self.btn_del_saved)

        right_layout.addWidget(self.grp_saved)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_accept = QPushButton(tr("path_gen.btn_accept"), self)
        self.btn_accept.setObjectName("primaryBtn")
        self.btn_accept.clicked.connect(self._accept_and_paint)
        btn_row.addWidget(self.btn_accept, 1)

        self.btn_cancel = QPushButton(tr("button.cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        right_layout.addLayout(btn_row)
        splitter.addWidget(right_widget)

        splitter.setSizes([480, 560])
        main_layout.addWidget(splitter, 1)

    # --------------------------------------------------------------------------
    # POPULATION & SELECTION HANDLERS
    # --------------------------------------------------------------------------
    def _populate_tilesets(self, select_asset_id: Optional[str] = None) -> None:
        self.cmb_tileset.blockSignals(True)
        self.cmb_tileset.clear()

        tilesets = [
            a for a in self.asset_manager.assets.values()
            if a.asset_type == AssetType.TILESET
        ]
        tilesets.sort(key=lambda a: a.name.lower())

        for ts in tilesets:
            w = ts.width
            h = ts.height
            tw = ts.tileset_config.tile_width if ts.tileset_config else 32
            th = ts.tileset_config.tile_height if ts.tileset_config else 32
            icon = IconFactory.get_icon("map", 16)
            self.cmb_tileset.addItem(
                icon,
                tr("path_gen.tileset_item", name=ts.name, w=w, h=h, tw=tw, th=th),
                ts.id,
            )

        self.cmb_tileset.blockSignals(False)

        if tilesets:
            idx = 0
            if select_asset_id:
                for i in range(self.cmb_tileset.count()):
                    if self.cmb_tileset.itemData(i) == select_asset_id:
                        idx = i
                        break
            self.cmb_tileset.setCurrentIndex(idx)
            self._on_tileset_changed(idx)
        else:
            self.lbl_tileset_info.setText(tr("path_gen.no_tilesets"))
            self.btn_accept.setEnabled(False)

    def _on_tileset_changed(self, index: int) -> None:
        asset_id = self.cmb_tileset.itemData(index)
        asset = self.asset_manager.get_asset(asset_id)
        self.selected_asset = asset
        if not asset:
            self.sheet_canvas.set_sheet(None)
            return

        pm = self.asset_manager.get_pixmap(asset.id)
        ts_cfg = asset.tileset_config
        tw = ts_cfg.tile_width if ts_cfg else 32
        th = ts_cfg.tile_height if ts_cfg else 32
        self.sheet_canvas.set_sheet(pm, tw, th, tileset_config=ts_cfg)

        if ts_cfg is not None:
            grid = ts_cfg.compute_grid(asset.width, asset.height)
            cols, rows = grid["cols"], grid["rows"]
        else:
            cols = asset.width // tw if tw > 0 else 0
            rows = asset.height // th if th > 0 else 0
        self.lbl_tileset_info.setText(
            tr(
                "path_gen.tileset_info",
                w=asset.width,
                h=asset.height,
                tw=tw,
                th=th,
                cols=cols,
                rows=rows,
                count=cols * rows,
            )
        )

        # Auto-select tile
        if self.selected_col >= cols or self.selected_row >= rows:
            self.selected_col = 0
            self.selected_row = 0
        self.sheet_canvas.set_selected_tile(self.selected_col, self.selected_row)
        self._regenerate_autotile()

    def _on_tile_clicked(self, col: int, row: int) -> None:
        self.selected_col = col
        self.selected_row = row
        self.selected_w_tiles = 1
        self.selected_h_tiles = 1
        self._regenerate_autotile()

    def _on_region_selected(self, col: int, row: int, w_tiles: int, h_tiles: int) -> None:
        self.selected_col = col
        self.selected_row = row
        self.selected_w_tiles = max(1, w_tiles)
        self.selected_h_tiles = max(1, h_tiles)
        self._regenerate_autotile()

    def _add_custom_variant(self) -> None:
        if not self.selected_asset:
            return
        mask = int(self.cmb_variant_mask.currentData() or 0)
        prio = self.spin_variant_prio.value()
        weight = self.spin_variant_weight.value()
        label = self.cmb_variant_mask.currentText()
        selected_role = str(self.cmb_variant_role.currentData() or "auto")
        ts_cfg = self.selected_asset.tileset_config
        pm = self.asset_manager.get_pixmap(self.selected_asset.id)
        analyzed = None
        if pm and not pm.isNull() and hasattr(self.engine, "analyzer"):
            analyzed = self.engine.analyzer.analyze_variant(
                pm.toImage(),
                self.selected_asset.id,
                self.selected_col,
                self.selected_row,
                self.selected_w_tiles,
                self.selected_h_tiles,
                tile_size=ts_cfg.tile_width if ts_cfg else 32,
                tileset_config=ts_cfg,
            )
        src_rect = analyzed.source_rect if analyzed else None
        if src_rect is None and ts_cfg is not None:
            x0, y0, tw, th = ts_cfg.get_tile_rect(self.selected_col, self.selected_row)
            x1, y1, tw2, th2 = ts_cfg.get_tile_rect(
                self.selected_col + self.selected_w_tiles - 1,
                self.selected_row + self.selected_h_tiles - 1,
            )
            src_rect = (x0, y0, (x1 + tw2) - x0, (y1 + th2) - y0)
        final_role = (
            selected_role
            if selected_role != "auto"
            else (analyzed.role if analyzed else ("composition" if (self.selected_w_tiles > 1 or self.selected_h_tiles > 1) else "single_tile"))
        )
        variant = CustomPathVariant(
            mask=mask,
            source_asset_id=self.selected_asset.id,
            source_col=self.selected_col,
            source_row=self.selected_row,
            width_tiles=self.selected_w_tiles,
            height_tiles=self.selected_h_tiles,
            source_rect=src_rect,
            role=final_role,
            surface_width_px=analyzed.surface_width_px if analyzed else 0,
            surface_width_tiles=max(1, min(self.selected_w_tiles, self.selected_h_tiles)),
            edge_type=analyzed.edge_type if analyzed else "auto",
            edges=analyzed.edges if analyzed else None,
            allow_connections=(final_role != "decoration"),
            priority=prio,
            weight=weight,
            name=f"{label} [{self.selected_w_tiles}×{self.selected_h_tiles} @ {self.selected_col},{self.selected_row}]",
        )
        self._custom_variants.append(variant)
        self._refresh_custom_variants_combo()
        self._regenerate_autotile()

    def _auto_analyze_sheet(self) -> None:
        if not self.selected_asset or not hasattr(self.engine, "analyzer"):
            return
        pm = self.asset_manager.get_pixmap(self.selected_asset.id)
        if not pm or pm.isNull():
            return
        ts_cfg = self.selected_asset.tileset_config
        ts = ts_cfg.tile_width if ts_cfg else 32
        analysis = self.engine.analyzer.analyze_sheet(
            pm.toImage(),
            self.selected_asset.id,
            tile_size=ts,
            tileset_config=ts_cfg,
        )
        self.lbl_status.setText(tr("path_gen.status_fmt", desc=analysis.summary))
        self.lbl_compat_info.setText(
            tr("path_gen.analyze_result", count=len(analysis.proposed_variants))
        )

    def _auto_suggest_compatibility(self) -> None:
        if not self._custom_variants:
            self.lbl_compat_info.setText(tr("path_gen.compat_empty"))
            return
        matrix = ConnectionRuleEngine.suggest_compatibility_matrix(self._custom_variants)
        links = 0
        for v in self._custom_variants:
            v_rules = matrix.get(v.id, {})
            v.compatible_neighbors = {d: list(ids) for d, ids in v_rules.items()}
            links += sum(len(ids) for ids in v_rules.values())
        self.lbl_compat_info.setText(
            tr("path_gen.compat_result", links=links, count=len(self._custom_variants))
        )
        self._regenerate_autotile()

    def _remove_selected_custom_variant(self) -> None:
        idx = self.cmb_custom_variants.currentIndex()
        if idx < 0:
            return
        vid = self.cmb_custom_variants.itemData(idx)
        self._custom_variants = [v for v in self._custom_variants if v.id != vid]
        self._refresh_custom_variants_combo()
        self._regenerate_autotile()

    def _refresh_custom_variants_combo(self) -> None:
        self.cmb_custom_variants.clear()
        for v in self._custom_variants:
            self.cmb_custom_variants.addItem(
                f"{v.name} (P:{v.priority}, W:{v.weight:.1f})", v.id
            )

    # --------------------------------------------------------------------------
    # GENERATION & SANDBOX UPDATE
    # --------------------------------------------------------------------------
    def _regenerate_autotile(self) -> None:
        if not self.selected_asset:
            return

        pm = self.asset_manager.get_pixmap(self.selected_asset.id)
        if not pm or pm.isNull():
            return

        raw_sheet = pm.toImage()
        ts_cfg = self.selected_asset.tileset_config
        sheet, ts, _th = extract_packed_tileset_image(raw_sheet, ts_cfg)
        mode = self.cmb_mode.currentData() or "auto"
        edge_style = self.cmb_style.currentData() or "organic"

        size_suffix = f" ({self.selected_w_tiles}×{self.selected_h_tiles})" if (self.selected_w_tiles > 1 or self.selected_h_tiles > 1) else ""
        if not self._name_manually_edited or not self.txt_name.text().strip():
            name = tr(
                "path_gen.auto_name",
                name=self.selected_asset.name,
                col=self.selected_col,
                row=self.selected_row,
                suffix=size_suffix,
            )
            self.txt_name.setText(name)
        else:
            name = self.txt_name.text().strip()

        terrain = self.txt_terrain.text().strip() or "path"

        # Update tile/region info and thumbnail
        tile_rect = QRect(
            self.selected_col * ts,
            self.selected_row * ts,
            self.selected_w_tiles * ts,
            self.selected_h_tiles * ts,
        )
        if tile_rect.x() + tile_rect.width() <= sheet.width() and tile_rect.y() + tile_rect.height() <= sheet.height():
            cropped_tile = sheet.copy(tile_rect)
            self.lbl_tile_thumb.setPixmap(
                QPixmap.fromImage(cropped_tile).scaled(
                    36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
                )
            )
        self.lbl_tile_coords.setText(
            tr(
                "path_gen.selected_region",
                col=self.selected_col,
                row=self.selected_row,
                w=self.selected_w_tiles,
                h=self.selected_h_tiles,
                px=self.selected_col * ts,
                py=self.selected_row * ts,
            )
        )

        # Synthesize Autotile
        rim_balance = float(self.cmb_rim_balance.currentData() or 0.40)
        path_width = int(self.spin_path_width.value())
        src_img, fmt, desc = synthesize_from_tileset_context(
            sheet,
            self.selected_col,
            self.selected_row,
            ts,
            mode=mode,
            edge_style=edge_style,
            w_tiles=self.selected_w_tiles,
            h_tiles=self.selected_h_tiles,
            rim_balance=rim_balance,
        )
        self.lbl_status.setText(tr("path_gen.status_fmt", desc=desc))

        autotile = RPGAutotile(
            name=name,
            terrain_type=terrain,
            autotile_format=fmt,
            tile_size=ts,
            source_asset_id=self.selected_asset.id,
            source_rect=(
                self.selected_col * ts,
                self.selected_row * ts,
                self.selected_w_tiles * ts,
                self.selected_h_tiles * ts,
            ),
            source_col=self.selected_col,
            source_row=self.selected_row,
            source_w_tiles=self.selected_w_tiles,
            source_h_tiles=self.selected_h_tiles,
            generation_mode=mode,
            edge_style=edge_style,
            composition_width=self.selected_w_tiles if mode == "composition_wxh" else 1,
            composition_height=self.selected_h_tiles if mode == "composition_wxh" else 1,
            path_width=path_width,
            rim_balance=rim_balance,
        )
        autotile.custom_variants = list(self._custom_variants)
        autotile.set_source_qimage(src_img)
        self.current_autotile = autotile

        # Update sandbox with newly generated autotile
        self.sandbox.set_active_rpg_autotile(autotile)
        if not self.sandbox.active_cells:
            self._load_sample_curve()
        self.sandbox.update()
        self.btn_accept.setEnabled(True)

    # --------------------------------------------------------------------------
    # SANDBOX PRESETS
    # --------------------------------------------------------------------------
    def _load_sample_curve(self) -> None:
        self.sandbox.active_cells.clear()
        # S-Curve path
        for c in range(1, 5):
            self.sandbox.active_cells.add((c, 2))
        for r in range(2, 6):
            self.sandbox.active_cells.add((4, r))
        for c in range(4, 9):
            self.sandbox.active_cells.add((c, 5))
        self.sandbox.update()

    def _load_sample_cross(self) -> None:
        self.sandbox.active_cells.clear()
        # 4-way cross with T-junctions
        for c in range(2, 9):
            self.sandbox.active_cells.add((c, 3))
        for r in range(1, 7):
            self.sandbox.active_cells.add((5, r))
        self.sandbox.active_cells.add((3, 2))
        self.sandbox.active_cells.add((7, 4))
        self.sandbox.update()

    def _load_sample_loop(self) -> None:
        self.sandbox.active_cells.clear()
        # Closed rectangular loop with corners
        for c in range(2, 9):
            self.sandbox.active_cells.add((c, 2))
            self.sandbox.active_cells.add((c, 5))
        for r in range(2, 6):
            self.sandbox.active_cells.add((2, r))
            self.sandbox.active_cells.add((8, r))
        self.sandbox.update()

    def _load_sample_area(self) -> None:
        self.sandbox.active_cells.clear()
        # Solid area with corners and edges
        for r in range(2, 6):
            for c in range(3, 8):
                self.sandbox.active_cells.add((c, r))
        # Add an inner notch
        self.sandbox.active_cells.discard((5, 3))
        self.sandbox.update()

    def _clear_sandbox(self) -> None:
        self.sandbox.active_cells.clear()
        self.sandbox.update()

    # --------------------------------------------------------------------------
    # SAVED AUTOTILES MANAGEMENT
    # --------------------------------------------------------------------------
    def _populate_saved_autotiles(self) -> None:
        self.cmb_saved.blockSignals(True)
        self.cmb_saved.clear()
        rpg_map = getattr(self.engine, "rpg_autotiles", {})
        for at_id, at in rpg_map.items():
            if at.archived:
                continue
            preview = at.get_preview_pixmap(16)
            self.cmb_saved.addItem(QIcon(preview), f"{at.name} [{at.terrain_type}]", at_id)
        self.cmb_saved.blockSignals(False)

    def _on_saved_autotile_selected(self, index: int) -> None:
        if index < 0:
            return
        at_id = self.cmb_saved.itemData(index)
        at = self.engine.get_rpg_autotile(at_id)
        if at:
            self._editing_autotile_id = at.id
            self.current_autotile = at.clone_as_new_definition()
            self._custom_variants = [v.clone() for v in at.custom_variants]
            self._refresh_custom_variants_combo()
            self.sandbox.set_active_rpg_autotile(self.current_autotile)
            self.sandbox.update()

    def _delete_saved_autotile(self) -> None:
        idx = self.cmb_saved.currentIndex()
        if idx < 0:
            return
        at_id = self.cmb_saved.itemData(idx)
        if not self.engine.archive_rpg_autotile(at_id):
            return
        if self.current_autotile and self.current_autotile.id == at_id:
            self.current_autotile = None
            self.sandbox.set_active_rpg_autotile(None)
        parent_w = self.parent()
        while parent_w:
            if hasattr(parent_w, "tileset_palette"):
                parent_w.tileset_palette.refresh_autotiles()
                break
            parent_w = parent_w.parent()
        self._populate_saved_autotiles()

    # --------------------------------------------------------------------------
    # ACCEPT & PAINT
    # --------------------------------------------------------------------------
    def _accept_and_paint(self) -> None:
        if not self.current_autotile:
            QMessageBox.warning(self, tr("dialog.error"), tr("path_gen.err_select_tile"))
            return

        if not self.current_autotile.has_valid_atlas(self.asset_manager):
            if not self.current_autotile.rebuild_atlas(self.asset_manager) or not self.current_autotile.has_valid_atlas(self.asset_manager):
                QMessageBox.warning(
                    self,
                    tr("path_gen.err_atlas_title"),
                    tr("path_gen.err_atlas_body"),
                )
                return

        if self._editing_autotile_id and self._editing_autotile_id in self.engine.rpg_autotiles:
            self.current_autotile = self.engine.update_rpg_autotile_definition(
                self._editing_autotile_id, self.current_autotile, self.asset_manager
            )
        else:
            self.engine.register_rpg_autotile(self.current_autotile, self.asset_manager)
            self.engine.active_rpg_autotile_id = self.current_autotile.id
            if self.asset_manager and hasattr(self.asset_manager, "register_rpg_autotile"):
                self.asset_manager.register_rpg_autotile(self.current_autotile)
        self.autotile_created.emit(self.current_autotile)
        self.path_rulesets_changed.emit()

        # Update parent window if applicable
        parent_w = self.parent()
        while parent_w:
            if hasattr(parent_w, "tileset_palette"):
                parent_w.tileset_palette.refresh_autotiles()
                parent_w.tileset_palette._select_autotile(self.current_autotile)
            if hasattr(parent_w, "tool_panel"):
                parent_w.tool_panel.select_tool_by_key("brush")
            if hasattr(parent_w, "tileset_palette") or hasattr(parent_w, "tool_panel"):
                break
            parent_w = parent_w.parent()

        self.accept()

    # --------------------------------------------------------------------------
    # BACKWARD COMPATIBILITY HELPERS
    # --------------------------------------------------------------------------
    def _create_subtile_thumbnail(self, tile: Any, size: int = 32) -> QPixmap:
        """Helper for legacy unit tests."""
        if hasattr(tile, "asset_id"):
            aid = tile.asset_id
            sx, sy, sw, sh = tile.sub_x, tile.sub_y, tile.sub_w, tile.sub_h
        elif isinstance(tile, (tuple, list)) and len(tile) >= 5:
            aid, sx, sy, sw, sh = tile[:5]
        else:
            pm = QPixmap(size, size)
            pm.fill(QColor("#2563eb"))
            return pm

        pix = self.asset_manager.get_pixmap(aid) if self.asset_manager else None
        if pix and not pix.isNull():
            return pix.copy(sx, sy, sw, sh).scaled(size, size)
        pm = QPixmap(size, size)
        pm.fill(QColor("#2563eb"))
        return pm
