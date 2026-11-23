from typing import Optional, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSpinBox,
    QDoubleSpinBox,
    QToolButton,
    QMessageBox,
    QLineEdit,
    QGroupBox,
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor

from ...models.brush_preset import BrushSettings, TileVariant
from ...models.asset import SelectedSubTile
from ...core.asset_manager import AssetManager
from ...models.project import Project
from ...core.history import HistoryManager, TileBatchCommand
from ..widgets.switch_toggle import SwitchToggle
from ..icons import IconFactory
from ...core.localization import tr


class TileRandomizerDialog(QDialog):
    """
    Configuration dialog for Tile Variation Randomizer.
    Allows creating, managing, weighting, and reordering tile variants for brush painting,
    as well as rerandomizing map selections.
    """
    variants_updated = pyqtSignal()

    def __init__(
        self,
        brush_settings: BrushSettings,
        asset_manager: AssetManager,
        project: Optional[Project] = None,
        history_manager: Optional[HistoryManager] = None,
        selected_cells: Optional[List[tuple]] = None,
        parent: Optional[QDialog] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.randomizer.title"))
        self.setMinimumSize(540, 520)
        self.resize(580, 560)

        self.settings = brush_settings
        self.asset_manager = asset_manager
        self.project = project
        self.history_manager = history_manager
        self.selected_cells = selected_cells or []

        self._init_ui()
        self._populate_table()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Top Options Group
        top_group = QGroupBox("Opcje ogólne losowania")
        top_layout = QVBoxLayout(top_group)

        # Enable Randomizer
        self.chk_enable = SwitchToggle("Włącz losowy wybór wariantów kafelków podczas malowania", checked=self.settings.random_variant)
        self.chk_enable.toggled.connect(self._on_enable_toggled)
        top_layout.addWidget(self.chk_enable)

        # Avoid Adjacent Duplicates
        self.chk_avoid = SwitchToggle("Ograniczaj powtarzanie identycznych wariantów bezpośrednio obok siebie", checked=self.settings.avoid_adjacent)
        self.chk_avoid.setToolTip(tr("randomizer.avoid_tooltip"))
        self.chk_avoid.toggled.connect(self._on_avoid_toggled)
        top_layout.addWidget(self.chk_avoid)

        # Seed controls
        seed_layout = QHBoxLayout()
        self.chk_seed = SwitchToggle("Stałe ziarno losowości (Seed):", checked=self.settings.seed is not None)
        self.chk_seed.toggled.connect(self._on_seed_toggled)
        seed_layout.addWidget(self.chk_seed)

        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 999999999)
        self.spin_seed.setValue(self.settings.seed if self.settings.seed is not None else 12345)
        self.spin_seed.setEnabled(self.settings.seed is not None)
        self.spin_seed.valueChanged.connect(self._on_seed_value_changed)
        seed_layout.addWidget(self.spin_seed)
        seed_layout.addStretch()

        top_layout.addLayout(seed_layout)
        layout.addWidget(top_group)

        # 2. Variants Table Group
        var_group = QGroupBox("Kafelki w grupie wariantów")
        var_layout = QVBoxLayout(var_group)

        # Toolbar above table
        tbl_tools = QHBoxLayout()
        self.btn_add_sel = QPushButton(" Dodaj z zaznaczenia palety")
        self.btn_add_sel.setIcon(IconFactory.get_icon("plus", 14))
        self.btn_add_sel.setToolTip(tr("randomizer.add_tooltip"))
        self.btn_add_sel.clicked.connect(self._add_from_palette_selection)
        tbl_tools.addWidget(self.btn_add_sel)

        self.btn_equalize = QPushButton(" Wyrównaj wagi")
        self.btn_equalize.setIcon(IconFactory.get_icon("adjustments", 14))
        self.btn_equalize.setToolTip(tr("randomizer.equalize_tooltip"))
        self.btn_equalize.clicked.connect(self._equalize_weights)
        tbl_tools.addWidget(self.btn_equalize)

        self.btn_up = QToolButton()
        self.btn_up.setIcon(IconFactory.get_icon("arrow-up", 14))
        self.btn_up.setToolTip(tr("randomizer.up_tooltip"))
        self.btn_up.clicked.connect(self._move_up)
        tbl_tools.addWidget(self.btn_up)

        self.btn_down = QToolButton()
        self.btn_down.setIcon(IconFactory.get_icon("arrow-down", 14))
        self.btn_down.setToolTip(tr("randomizer.down_tooltip"))
        self.btn_down.clicked.connect(self._move_down)
        tbl_tools.addWidget(self.btn_down)

        self.btn_del = QPushButton(" Usuń")
        self.btn_del.setIcon(IconFactory.get_icon("trash", 14))
        self.btn_del.setToolTip(tr("randomizer.delete_tooltip"))
        self.btn_del.clicked.connect(self._remove_selected)
        tbl_tools.addWidget(self.btn_del)

        self.btn_clear = QPushButton("Wyczyść wszystko")
        self.btn_clear.setIcon(IconFactory.get_icon("x", 14))
        self.btn_clear.clicked.connect(self._clear_all)
        tbl_tools.addWidget(self.btn_clear)

        var_layout.addLayout(tbl_tools)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Miniatura", "Nazwa / Koordynaty", "Waga (Szansa)", "Szansa %"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
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
        var_layout.addWidget(self.table, 1)

        layout.addWidget(var_group, 1)

        # 3. Area Rerandomize Button (if map available)
        if self.project:
            rerand_box = QHBoxLayout()
            self.btn_rerandomize = QPushButton(" Przelosuj kafelki w zaznaczonym obszarze mapy")
            self.btn_rerandomize.setIcon(IconFactory.get_icon("randomizer", 16))
            self.btn_rerandomize.setToolTip(tr("randomizer.rerandomize_tooltip"))
            self.btn_rerandomize.clicked.connect(self._rerandomize_map_area)
            rerand_box.addWidget(self.btn_rerandomize)
            layout.addLayout(rerand_box)

        # 4. Dialog Bottom Buttons
        bottom_box = QHBoxLayout()
        bottom_box.addStretch()

        self.btn_close = QPushButton(" Zamknij")
        self.btn_close.setIcon(IconFactory.get_icon("close", 14))
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        bottom_box.addWidget(self.btn_close)

        layout.addLayout(bottom_box)

    def _on_enable_toggled(self, checked: bool) -> None:
        self.settings.random_variant = checked
        self.variants_updated.emit()

    def _on_avoid_toggled(self, checked: bool) -> None:
        self.settings.avoid_adjacent = checked
        self.variants_updated.emit()

    def _on_seed_toggled(self, checked: bool) -> None:
        if checked:
            self.spin_seed.setEnabled(True)
            self.settings.set_seed(self.spin_seed.value())
        else:
            self.spin_seed.setEnabled(False)
            self.settings.set_seed(None)
        self.variants_updated.emit()

    def _on_seed_value_changed(self, val: int) -> None:
        if self.chk_seed.isChecked():
            self.settings.set_seed(val)
            self.variants_updated.emit()

    def _populate_table(self) -> None:
        """Renders the list of variants into the table widget."""
        self.table.setRowCount(0)
        total_weight = sum(v.weight for v in self.settings.variants if isinstance(v, TileVariant))
        if total_weight <= 0:
            total_weight = 1.0

        for row_idx, var in enumerate(self.settings.variants):
            if not isinstance(var, TileVariant):
                var = TileVariant(sub_tile=var, weight=10.0)
                self.settings.variants[row_idx] = var

            self.table.insertRow(row_idx)

            # Column 0: Thumbnail
            lbl_thumb = QLabel()
            lbl_thumb.setFixedSize(36, 36)
            lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pm = self._render_thumbnail(var.sub_tile)
            if pm:
                lbl_thumb.setPixmap(pm.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.table.setCellWidget(row_idx, 0, lbl_thumb)

            # Column 1: Name and Coords
            sub = var.sub_tile
            c = getattr(sub, "col", 0)
            r = getattr(sub, "row", 0)
            txt_info = f"{var.name} (Kol: {c}, Wrs: {r})"
            item_info = QTableWidgetItem(txt_info)
            item_info.setFlags(item_info.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 1, item_info)

            # Column 2: Weight Spinbox
            spin_weight = QDoubleSpinBox()
            spin_weight.setRange(0.1, 1000.0)
            spin_weight.setDecimals(1)
            spin_weight.setValue(var.weight)
            spin_weight.setFixedWidth(75)
            spin_weight.valueChanged.connect(lambda val, v=var: self._on_weight_changed(v, val))
            self.table.setCellWidget(row_idx, 2, spin_weight)

            # Column 3: Percentage Chance
            pct = (var.weight / total_weight) * 100.0
            item_pct = QTableWidgetItem(f"{pct:.1f}%")
            item_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_pct.setFlags(item_pct.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 3, item_pct)

    def _render_thumbnail(self, sub_tile: Any) -> Optional[QPixmap]:
        if not sub_tile or not self.asset_manager:
            return None
        aid = getattr(sub_tile, "asset_id", None)
        if not aid:
            return None
        pix = self.asset_manager.get_pixmap(aid)
        if not pix or pix.isNull():
            return None

        sx = getattr(sub_tile, "sub_x", 0)
        sy = getattr(sub_tile, "sub_y", 0)
        sw = getattr(sub_tile, "sub_w", 32)
        sh = getattr(sub_tile, "sub_h", 32)

        cropped = pix.copy(sx, sy, sw, sh)
        return cropped

    def _on_weight_changed(self, variant: TileVariant, new_weight: float) -> None:
        variant.weight = max(0.01, float(new_weight))
        self._update_percentages()
        self.variants_updated.emit()

    def _update_percentages(self) -> None:
        total = sum(v.weight for v in self.settings.variants if isinstance(v, TileVariant))
        if total <= 0:
            total = 1.0
        for row in range(self.table.rowCount()):
            if row < len(self.settings.variants):
                v = self.settings.variants[row]
                pct = (v.weight / total) * 100.0
                item = self.table.item(row, 3)
                if item:
                    item.setText(f"{pct:.1f}%")

    def _add_from_palette_selection(self) -> None:
        """Extracts single tiles from the palette selection and adds them as variants."""
        sel = self.asset_manager.selected_item
        if not sel:
            QMessageBox.information(
                self,
                "Brak zaznaczenia",
                "Najpierw zaznacz jeden lub więcej kafelków w podglądzie tilesetu.",
            )
            return

        added_count = 0
        if isinstance(sel, SelectedSubTile):
            singles = sel.extract_single_tiles()
            for s in singles:
                self.settings.add_variant(s, weight=10.0)
                added_count += 1
        else:
            self.settings.add_variant(sel, weight=10.0)
            added_count += 1

        self._populate_table()
        self.variants_updated.emit()

    def _equalize_weights(self) -> None:
        self.settings.set_equal_weights(10.0)
        self._populate_table()
        self.variants_updated.emit()

    def _move_up(self) -> None:
        row = self.table.currentRow()
        if row > 0:
            self.settings.move_variant(row, row - 1)
            self._populate_table()
            self.table.selectRow(row - 1)
            self.variants_updated.emit()

    def _move_down(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.settings.variants) - 1:
            self.settings.move_variant(row, row + 1)
            self._populate_table()
            self.table.selectRow(row + 1)
            self.variants_updated.emit()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.settings.remove_variant(row)
            self._populate_table()
            self.variants_updated.emit()

    def _clear_all(self) -> None:
        self.settings.clear_variants()
        self._populate_table()
        self.variants_updated.emit()

    def _rerandomize_map_area(self) -> None:
        """Rerandomizes all placed tiles in the selected cells or layer."""
        if not self.project:
            return
        layer = self.project.get_active_layer()
        if not layer or layer.locked:
            QMessageBox.warning(self, "Błąd", "Brak aktywnej lub odblokowanej warstwy.")
            return

        if not self.settings.variants:
            QMessageBox.warning(self, "Brak wariantów", "Dodaj najpierw kafelki do grupy wariantów.")
            return

        # Determine target coordinates
        if self.selected_cells:
            coords = list(self.selected_cells)
        else:
            # If no selection, ask user if they want to rerandomize all tiles on layer
            res = QMessageBox.question(
                self,
                "Potwierdzenie",
                "Brak aktywnego zaznaczenia komórek. Czy chcesz przelosować wszystkie kafelki na bieżącej warstwie?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if res != QMessageBox.StandardButton.Yes:
                return
            coords = list(layer.tiles.keys())

        changes = {}
        for (col, row) in coords:
            prev = layer.get_tile(col, row)
            if not prev:
                continue

            prev_clone = prev.clone()
            adj = None
            if self.settings.avoid_adjacent:
                adj = [
                    layer.get_tile(col - 1, row),
                    layer.get_tile(col + 1, row),
                    layer.get_tile(col, row - 1),
                    layer.get_tile(col, row + 1),
                ]
            chosen_sub = self.settings.pick_variant(self.settings.variants[0].sub_tile, avoid_adjacent_items=adj)

            new_tile = prev.clone()
            new_tile.asset_id = getattr(chosen_sub, "asset_id", prev.asset_id)
            new_tile.source_x = getattr(chosen_sub, "sub_x", getattr(chosen_sub, "source_x", prev.source_x))
            new_tile.source_y = getattr(chosen_sub, "sub_y", getattr(chosen_sub, "source_y", prev.source_y))
            new_tile.source_w = getattr(chosen_sub, "sub_w", getattr(chosen_sub, "source_w", prev.source_w))
            new_tile.source_h = getattr(chosen_sub, "sub_h", getattr(chosen_sub, "source_h", prev.source_h))

            layer.set_tile(col, row, new_tile)
            changes[(col, row)] = (prev_clone, new_tile.clone())

        if changes and self.history_manager:
            cmd = TileBatchCommand(
                self.project,
                layer.id,
                changes,
                description="Przelosowanie wariantów kafelków",
            )
            self.history_manager.push(cmd)

        QMessageBox.information(
            self,
            "Zakończono",
            f"Pomyślnie przelosowano warianty dla {len(changes)} kafelków.",
        )
