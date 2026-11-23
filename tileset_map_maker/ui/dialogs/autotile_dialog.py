import os
from typing import Optional, Dict, Tuple
from PyQt6.QtCore import Qt, QRect, QAbstractTableModel, QModelIndex
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QSpinBox,
    QLabel,
    QMessageBox,
    QWidget,
    QGroupBox,
    QFrame,
    QTableView,
    QHeaderView,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen

from ...core.autotile_engine import AutoTileEngine
from ...models.autotile import (
    AutoTileRuleSet,
    CARD_CORNER_TL,
    CARD_EDGE_TOP,
    CARD_CORNER_TR,
    CARD_EDGE_LEFT,
    CARD_CENTER,
    CARD_EDGE_RIGHT,
    CARD_CORNER_BL,
    CARD_EDGE_BOTTOM,
    CARD_CORNER_BR,
)
from ...core.asset_manager import AssetManager
from ...models.asset import Asset, AssetType, SelectedSubTile
from ...core.config_manager import ConfigManager
from ..icons import IconFactory
from ...core.localization import tr


PATTERN_MASKS = (
    (CARD_CORNER_TL, CARD_EDGE_TOP, CARD_CORNER_TR),
    (CARD_EDGE_LEFT, CARD_CENTER, CARD_EDGE_RIGHT),
    (CARD_CORNER_BL, CARD_EDGE_BOTTOM, CARD_CORNER_BR),
)


class PatternModel(QAbstractTableModel):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.ruleset = None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or not isinstance(self.ruleset, AutoTileRuleSet) else self.ruleset.pattern_height

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or not isinstance(self.ruleset, AutoTileRuleSet) else self.ruleset.pattern_width

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not isinstance(self.ruleset, AutoTileRuleSet):
            return None
        x, y = index.column(), index.row()
        tile = self.ruleset.pattern_tiles.get((x, y))
        if not self.ruleset.pattern_enabled and x < 3 and y < 3:
            tile = self.ruleset.tile_mappings.get(PATTERN_MASKS[y][x])
        if role == Qt.ItemDataRole.DecorationRole and tile:
            return self.dialog.asset_manager.get_tile_pixmap(*tile)
        if role == Qt.ItemDataRole.DisplayRole and not tile:
            return "—"
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{x}, {y}"
        return None

    def refresh(self, ruleset):
        self.beginResetModel()
        self.ruleset = ruleset
        self.endResetModel()


class AutoTileDialog(QDialog):
    """Configuration dialog for Auto-Tiling rules, 3x3 visual mappings and terrain connections."""

    def __init__(
        self,
        autotile_engine: AutoTileEngine,
        asset_manager: AssetManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.autotile_engine = autotile_engine
        self.asset_manager = asset_manager
        self.setWindowTitle(tr("dialog.autotile.title"))
        self.resize(600, 620)
        self.preview_labels: Dict[Tuple[int, int], QLabel] = {}
        self.variant_test_round = 0

        self._ensure_initial_rule()
        self._init_ui()
        self._load_current_rule()

    def _ensure_initial_rule(self) -> None:
        """Ensures at least one rule exists if the library was empty."""
        if not self.autotile_engine.rulesets:
            default_rule = AutoTileRuleSet(
                name=tr("dialog.autotile.default_rule"),
                terrain_type="Grass",
                connects_with=["Grass"],
            )
            self.autotile_engine.register_ruleset(default_rule)
            self.autotile_engine.active_ruleset_id = default_rule.id

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Ruleset selector & Management Header
        group_rule = QGroupBox(tr("dialog.autotile.rule_group"))
        rule_layout = QVBoxLayout(group_rule)
        rule_layout.setSpacing(8)

        top_rule_bar = QHBoxLayout()
        self.combo_rules = QComboBox()
        self._populate_rules_combo()
        self.combo_rules.currentIndexChanged.connect(self._load_current_rule)
        top_rule_bar.addWidget(self.combo_rules, 1)

        btn_new_rule = QPushButton(f" {tr('dialog.autotile.new')}")
        btn_new_rule.setIcon(IconFactory.get_icon("plus", 14))
        btn_new_rule.setToolTip(tr("autotile.new_tooltip"))
        btn_new_rule.clicked.connect(self._create_new_rule)
        top_rule_bar.addWidget(btn_new_rule)

        btn_del_rule = QPushButton(f" {tr('dialog.autotile.delete')}")
        btn_del_rule.setIcon(IconFactory.get_icon("trash", 14))
        btn_del_rule.setToolTip(tr("autotile.delete_tooltip"))
        btn_del_rule.clicked.connect(self._delete_current_rule)
        top_rule_bar.addWidget(btn_del_rule)

        rule_layout.addLayout(top_rule_bar)

        form = QFormLayout()
        form.setSpacing(6)

        self.txt_name = QLineEdit(tr("dialog.autotile.default_rule"))
        form.addRow(tr("dialog.autotile.set_name"), self.txt_name)

        self.txt_terrain = QLineEdit("Grass")
        form.addRow(tr("dialog.autotile.main_terrain"), self.txt_terrain)

        self.txt_connects = QLineEdit("Grass")
        self.txt_connects.setToolTip(tr("autotile.connects_tooltip"))
        form.addRow(tr("dialog.autotile.connects"), self.txt_connects)

        rule_layout.addLayout(form)

        preset_bar = QHBoxLayout()
        self.combo_presets = QComboBox()
        self._populate_presets_combo()
        preset_bar.addWidget(self.combo_presets, 1)
        btn_load_preset = QPushButton("Wczytaj preset")
        btn_load_preset.clicked.connect(self._load_preset)
        preset_bar.addWidget(btn_load_preset)
        btn_save_preset = QPushButton("Zapisz jako preset")
        btn_save_preset.clicked.connect(self._save_preset)
        preset_bar.addWidget(btn_save_preset)
        rule_layout.addLayout(preset_bar)
        layout.addWidget(group_rule)

        # 2. Template Setup Group
        group_template = QGroupBox(tr("dialog.autotile.tileset_group"))
        tpl_layout = QVBoxLayout(group_template)
        tpl_layout.setSpacing(8)

        form_tpl = QFormLayout()
        form_tpl.setSpacing(6)

        self.combo_tileset = QComboBox()
        tilesets = [a for a in self.asset_manager.assets.values() if a.asset_type == AssetType.TILESET]
        for ts in tilesets:
            self.combo_tileset.addItem(IconFactory.get_icon("map", 16), f"{ts.name} ({ts.width}x{ts.height})", ts.id)
        form_tpl.addRow(tr("dialog.autotile.tileset"), self.combo_tileset)

        coords_bar = QHBoxLayout()
        coords_bar.setSpacing(8)

        lbl_col = QLabel(tr("dialog.autotile.start_col"))
        self.spin_col = QSpinBox()
        self.spin_col.setRange(0, 2_147_483_647)
        self.spin_col.setValue(0)
        coords_bar.addWidget(lbl_col)
        coords_bar.addWidget(self.spin_col)

        lbl_row = QLabel(tr("dialog.autotile.start_row"))
        self.spin_row = QSpinBox()
        self.spin_row.setRange(0, 2_147_483_647)
        self.spin_row.setValue(0)
        coords_bar.addWidget(lbl_row)
        coords_bar.addWidget(self.spin_row)

        btn_use_sel = QPushButton(f" {tr('dialog.autotile.selection')}")
        btn_use_sel.setIcon(IconFactory.get_icon("select", 14))
        btn_use_sel.setToolTip(tr("autotile.selection_tooltip"))
        btn_use_sel.clicked.connect(self._use_palette_selection)
        coords_bar.addWidget(btn_use_sel)

        form_tpl.addRow(tr("dialog.autotile.block_start"), coords_bar)
        self.spin_pattern_width = QSpinBox()
        self.spin_pattern_height = QSpinBox()
        for spin in (self.spin_pattern_width, self.spin_pattern_height):
            spin.setRange(1, 2_147_483_647)
            spin.setValue(3)
            spin.setKeyboardTracking(False)
            spin.setToolTip(tr("autotile.resize_tooltip"))
            spin.valueChanged.connect(self._resize_pattern)
        form_tpl.addRow(tr("autotile.pattern_width"), self.spin_pattern_width)
        form_tpl.addRow(tr("autotile.pattern_height"), self.spin_pattern_height)
        tpl_layout.addLayout(form_tpl)

        btn_apply = QPushButton(f" {tr('dialog.autotile.apply_template')}")
        btn_apply.setIcon(IconFactory.get_icon("grid-3x3-template", 16))
        btn_apply.setStyleSheet("font-weight: bold; background-color: #2563eb; color: white; padding: 6px;")
        btn_apply.clicked.connect(self._apply_template)
        tpl_layout.addWidget(btn_apply)

        layout.addWidget(group_template)

        # 3. Visual 3x3 Layout Preview
        group_preview = QGroupBox(tr("dialog.autotile.preview_group"))
        prev_layout = QVBoxLayout(group_preview)
        prev_layout.setSpacing(6)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        grid.setAlignment(Qt.AlignmentFlag.AlignCenter)

        slot_names = [
            ("dialog.autotile.role.corner_tl", 0, 0),
            ("dialog.autotile.role.edge_top", 1, 0),
            ("dialog.autotile.role.corner_tr", 2, 0),
            ("dialog.autotile.role.edge_left", 0, 1),
            ("dialog.autotile.role.center", 1, 1),
            ("dialog.autotile.role.edge_right", 2, 1),
            ("dialog.autotile.role.corner_bl", 0, 2),
            ("dialog.autotile.role.edge_bottom", 1, 2),
            ("dialog.autotile.role.corner_br", 2, 2),
        ]

        for title_key, cx, cy in slot_names:
            slot_box = QVBoxLayout()
            slot_box.setSpacing(2)
            slot_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_thumb = QLabel()
            lbl_thumb.setFixedSize(48, 48)
            lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_thumb.setStyleSheet("background-color: #121214; border: 1px solid #3f3f46; border-radius: 4px;")

            lbl_sub = QLabel(tr(title_key))
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_sub.setStyleSheet("font-size: 10px; color: #a1a1aa;")

            slot_box.addWidget(lbl_thumb)
            slot_box.addWidget(lbl_sub)

            container = QWidget()
            container.setLayout(slot_box)
            grid.addWidget(container, cy, cx)

            self.preview_labels[(cx, cy)] = lbl_thumb

        prev_layout.addWidget(grid_widget)
        self.legacy_grid_widget = grid_widget
        self.pattern_view = QTableView()
        self.pattern_model = PatternModel(self)
        self.pattern_view.setModel(self.pattern_model)
        self.pattern_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.pattern_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.pattern_view.horizontalHeader().setDefaultSectionSize(54)
        self.pattern_view.verticalHeader().setDefaultSectionSize(54)
        self.pattern_view.setIconSize(QPixmap(44, 44).size())
        self.pattern_view.setToolTip(tr("autotile.assign_tooltip"))
        self.pattern_view.doubleClicked.connect(self._assign_pattern_tile)
        prev_layout.addWidget(self.pattern_view)
        btn_test_variants = QPushButton("Podgląd kolejnego wariantu")
        btn_test_variants.clicked.connect(self._test_variants)
        prev_layout.addWidget(btn_test_variants)
        layout.addWidget(group_preview)

        # 4. Action Buttons
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        btn_save = QPushButton(f" {tr('dialog.autotile.save_rule')}")
        btn_save.setIcon(IconFactory.get_icon("save", 16))
        btn_save.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 6px 16px;")
        btn_save.clicked.connect(self._save_rule)
        btn_bar.addWidget(btn_save)

        btn_close = QPushButton(f" {tr('dialog.autotile.close')}")
        btn_close.setIcon(IconFactory.get_icon("close", 14))
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def _populate_rules_combo(self) -> None:
        self.combo_rules.blockSignals(True)
        self.combo_rules.clear()
        active_idx = 0
        for i, (rid, r) in enumerate(self.autotile_engine.rulesets.items()):
            self.combo_rules.addItem(f"{r.name} ({r.terrain_type})", rid)
            if rid == self.autotile_engine.active_ruleset_id:
                active_idx = i
        if self.combo_rules.count() > 0:
            self.combo_rules.setCurrentIndex(active_idx)
        self.combo_rules.blockSignals(False)

    def _populate_presets_combo(self) -> None:
        self.combo_presets.clear()
        self.combo_presets.addItem("Brak presetu", "")
        for preset_id, data in self.autotile_engine.presets.items():
            self.combo_presets.addItem(
                data.get("name", preset_id), preset_id
            )

    def _save_preset(self) -> None:
        if not self._save_rule(show_msg=False):
            return
        ruleset = self.autotile_engine.get_ruleset(
            self.combo_rules.currentData()
        )
        if ruleset:
            self.autotile_engine.save_ruleset_preset(ruleset.name, ruleset)
            if not ConfigManager().save_autotile_rules(self.autotile_engine):
                QMessageBox.warning(self, tr("dialog.autotile.error_title"), tr("autotile.save_failed"))
                return
            self._populate_presets_combo()
            QMessageBox.information(
                self, "Preset zapisany", f"Zapisano preset '{ruleset.name}'."
            )

    def _load_preset(self) -> None:
        preset_id = self.combo_presets.currentData()
        if not preset_id:
            return
        ruleset = self.autotile_engine.create_ruleset_from_preset(preset_id)
        if ruleset:
            self.autotile_engine.active_ruleset_id = ruleset.id
            self._populate_rules_combo()
            self._load_current_rule()

    def _test_variants(self) -> None:
        ruleset = self.autotile_engine.get_ruleset(
            self.combo_rules.currentData()
        )
        if not ruleset or not hasattr(ruleset, "get_weighted_tile_for_mask"):
            return
        self.variant_test_round += 1
        for (cx, cy), mask in {
            (0, 0): CARD_CORNER_TL,
            (1, 0): CARD_EDGE_TOP,
            (2, 0): CARD_CORNER_TR,
            (0, 1): CARD_EDGE_LEFT,
            (1, 1): CARD_CENTER,
            (2, 1): CARD_EDGE_RIGHT,
            (0, 2): CARD_CORNER_BL,
            (1, 2): CARD_EDGE_BOTTOM,
            (2, 2): CARD_CORNER_BR,
        }.items():
            tile = ruleset.get_weighted_tile_for_mask(
                mask, cx, cy, self.variant_test_round
            )
            if tile:
                pixmap = self.asset_manager.get_tile_pixmap(*tile)
                if pixmap:
                    self.preview_labels[(cx, cy)].setPixmap(
                        pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)
                    )

    def _load_current_rule(self) -> None:
        rid = self.combo_rules.currentData()
        r = self.autotile_engine.get_ruleset(rid)
        if r:
            self.txt_name.setText(r.name)
            self.txt_terrain.setText(r.terrain_type)
            self.txt_connects.setText(", ".join(r.connects_with))
            for spin, value in ((self.spin_pattern_width, getattr(r, "pattern_width", 3)),
                                (self.spin_pattern_height, getattr(r, "pattern_height", 3))):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
            self._update_preview_grid(r)

    def _enable_pattern(self, ruleset: AutoTileRuleSet) -> None:
        if not ruleset.pattern_enabled:
            ruleset.pattern_tiles = {
                (x, y): ruleset.tile_mappings[mask]
                for y, row in enumerate(PATTERN_MASKS)
                for x, mask in enumerate(row)
                if mask in ruleset.tile_mappings
            }
            ruleset.pattern_enabled = True

    def _resize_pattern(self) -> None:
        ruleset = self.autotile_engine.get_ruleset(self.combo_rules.currentData())
        if not isinstance(ruleset, AutoTileRuleSet):
            return
        self._enable_pattern(ruleset)
        ruleset.resize_pattern(self.spin_pattern_width.value(), self.spin_pattern_height.value())
        self._update_preview_grid(ruleset)

    def _assign_pattern_tile(self, index: QModelIndex) -> None:
        ruleset = self.autotile_engine.get_ruleset(self.combo_rules.currentData())
        asset = self.asset_manager.get_asset(self.combo_tileset.currentData())
        if not isinstance(ruleset, AutoTileRuleSet) or not asset or not asset.tileset_config:
            QMessageBox.information(self, tr("dialog.autotile.info_title"), tr("autotile.assign_select"))
            return
        col, row = self.spin_col.value(), self.spin_row.value()
        grid = asset.tileset_config.compute_grid(asset.width, asset.height)
        if col >= grid["cols"] or row >= grid["rows"]:
            QMessageBox.warning(self, tr("dialog.autotile.error_title"), tr("autotile.pattern_outside"))
            return
        self._enable_pattern(ruleset)
        ruleset.set_pattern_tile(index.column(), index.row(), (asset.id, *asset.tileset_config.get_tile_rect(col, row)))
        self._update_preview_grid(ruleset)

    def _create_new_rule(self) -> None:
        new_r = AutoTileRuleSet(
            name=tr("dialog.autotile.default_name"),
            terrain_type=tr("dialog.autotile.default_type"),
        )
        self.autotile_engine.register_ruleset(new_r)
        self.autotile_engine.active_ruleset_id = new_r.id
        self._populate_rules_combo()
        self._load_current_rule()

    def _delete_current_rule(self) -> None:
        rid = self.combo_rules.currentData()
        if not rid:
            return
        if len(self.autotile_engine.rulesets) <= 1:
            QMessageBox.warning(
                self, tr("dialog.autotile.error_title"), tr("dialog.autotile.cannot_delete_last")
            )
            return

        confirm = QMessageBox.question(
            self,
            tr("dialog.autotile.delete_title"),
            tr("dialog.autotile.delete_confirm", name=self.txt_name.text()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            del self.autotile_engine.rulesets[rid]
            self.autotile_engine.active_ruleset_id = next(iter(self.autotile_engine.rulesets.keys()))
            self._populate_rules_combo()
            self._load_current_rule()
            ConfigManager().save_autotile_rules(self.autotile_engine)

    def _use_palette_selection(self) -> None:
        sel = self.asset_manager.selected_item
        if isinstance(sel, SelectedSubTile):
            self.spin_col.setValue(sel.col)
            self.spin_row.setValue(sel.row)
            for spin, value in ((self.spin_pattern_width, sel.cols_count),
                                (self.spin_pattern_height, sel.rows_count)):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
            self._resize_pattern()
            # Find tileset in combo
            for i in range(self.combo_tileset.count()):
                if self.combo_tileset.itemData(i) == sel.asset_id:
                    self.combo_tileset.setCurrentIndex(i)
                    break
        else:
            QMessageBox.information(
                self,
                tr("dialog.autotile.info_title"),
                tr("dialog.autotile.select_3x3"),
            )

    def _apply_template(self) -> None:
        ts_id = self.combo_tileset.currentData()
        if not ts_id:
            QMessageBox.warning(
                self, tr("dialog.autotile.error_title"), tr("dialog.autotile.no_tileset")
            )
            return

        ts_asset = self.asset_manager.get_asset(ts_id)
        if not ts_asset or not ts_asset.tileset_config:
            QMessageBox.warning(
                self, tr("dialog.autotile.error_title"), tr("dialog.autotile.no_tileset_config")
            )
            return

        rid = self.combo_rules.currentData()
        r = self.autotile_engine.get_ruleset(rid)
        if not isinstance(r, AutoTileRuleSet):
            return

        cfg = ts_asset.tileset_config
        start_col = self.spin_col.value()
        start_row = self.spin_row.value()

        sx, sy, _, _ = cfg.get_tile_rect(start_col, start_row)
        width, height = self.spin_pattern_width.value(), self.spin_pattern_height.value()
        grid = cfg.compute_grid(ts_asset.width, ts_asset.height)
        if start_col + width > grid["cols"] or start_row + height > grid["rows"]:
            QMessageBox.warning(self, tr("dialog.autotile.error_title"), tr("autotile.pattern_outside"))
            return
        if width == 3 and height == 3 and not r.pattern_enabled:
            r.setup_standard_3x3_box(
                asset_id=ts_asset.id,
                start_x=sx,
                start_y=sy,
                tile_w=cfg.tile_width,
                tile_h=cfg.tile_height,
                spacing_x=cfg.spacing_x,
                spacing_y=cfg.spacing_y,
            )
        else:
            r.resize_pattern(width, height)
            r.pattern_tiles.clear()
            for y in range(height):
                for x in range(width):
                    r.set_pattern_tile(x, y, (ts_asset.id, *cfg.get_tile_rect(start_col + x, start_row + y)))
            r.default_tile = r.pattern_tiles[(width // 2, height // 2)]

        self._update_preview_grid(r)
        if not self._save_rule(show_msg=False):
            return
        QMessageBox.information(
            self,
            tr("dialog.autotile.success_title"),
            tr(
                "dialog.autotile.applied",
                name=ts_asset.name,
                col=start_col,
                row=start_row,
            ),
        )

    def _update_preview_grid(self, ruleset: AutoTileRuleSet) -> None:
        self.pattern_model.refresh(ruleset)
        self.legacy_grid_widget.setVisible(not getattr(ruleset, "pattern_enabled", False))
        pos_to_mask = {
            (0, 0): CARD_CORNER_TL,
            (1, 0): CARD_EDGE_TOP,
            (2, 0): CARD_CORNER_TR,
            (0, 1): CARD_EDGE_LEFT,
            (1, 1): CARD_CENTER,
            (2, 1): CARD_EDGE_RIGHT,
            (0, 2): CARD_CORNER_BL,
            (1, 2): CARD_EDGE_BOTTOM,
            (2, 2): CARD_CORNER_BR,
        }

        for (cx, cy), mask in pos_to_mask.items():
            lbl = self.preview_labels.get((cx, cy))
            if not lbl:
                continue

            tile_data = ruleset.get_tile_for_mask(mask)
            if tile_data:
                aid, sx, sy, sw, sh = tile_data
                cropped = self.asset_manager.get_tile_pixmap(
                    aid, sx, sy, sw, sh
                )
                if cropped and not cropped.isNull():
                    scaled = cropped.scaled(
                        44,
                        44,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                    pix = QPixmap(48, 48)
                    pix.fill(QColor("#18181b"))
                    p = QPainter(pix)
                    # Checkerboard background
                    for by in range(0, 48, 6):
                        for bx in range(0, 48, 6):
                            col = QColor("#24242a") if ((bx // 6 + by // 6) % 2 == 0) else QColor("#1a1a20")
                            p.fillRect(bx, by, 6, 6, col)

                    ox = (48 - scaled.width()) // 2
                    oy = (48 - scaled.height()) // 2
                    p.drawPixmap(ox, oy, scaled)
                    p.setPen(QColor("#3b82f6"))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(ox - 1, oy - 1, scaled.width() + 1, scaled.height() + 1)
                    p.end()
                    lbl.setPixmap(pix)
                    continue

            # Empty slot fallback
            pix = QPixmap(48, 48)
            pix.fill(QColor("#18181b"))
            p = QPainter(pix)
            p.setPen(QColor("#52525b"))
            p.drawText(QRect(0, 0, 48, 48), Qt.AlignmentFlag.AlignCenter, "—")
            p.end()
            lbl.setPixmap(pix)

    def _save_rule(self, show_msg: bool = True) -> bool:
        rid = self.combo_rules.currentData()
        r = self.autotile_engine.get_ruleset(rid)
        if not r:
            return False

        r.name = self.txt_name.text().strip() or tr("dialog.autotile.default_name")
        r.terrain_type = self.txt_terrain.text().strip() or "Grass"
        connects = [c.strip() for c in self.txt_connects.text().split(",") if c.strip()]
        r.connects_with = connects or [r.terrain_type]
        self.autotile_engine.active_ruleset_id = r.id

        # Persist to ConfigManager
        if not ConfigManager().save_autotile_rules(self.autotile_engine):
            QMessageBox.warning(self, tr("dialog.autotile.error_title"), tr("autotile.save_failed"))
            return False
        self._populate_rules_combo()

        if show_msg:
            QMessageBox.information(
                self,
                tr("dialog.autotile.saved_title"),
                tr("dialog.autotile.saved", name=r.name),
            )
        return True
