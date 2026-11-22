from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QLabel,
    QMessageBox,
    QWidget,
    QGroupBox,
)
from ...core.autotile_engine import AutoTileEngine
from ...models.autotile import AutoTileRuleSet
from ...core.asset_manager import AssetManager
from ...models.asset import Asset, AssetType


class AutoTileDialog(QDialog):
    """Configuration dialog for Auto-Tiling rules and terrain connections."""

    def __init__(
        self,
        autotile_engine: AutoTileEngine,
        asset_manager: AssetManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.autotile_engine = autotile_engine
        self.asset_manager = asset_manager
        self.setWindowTitle("Konfigurator Auto-Tiling")
        self.resize(520, 440)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Aktywny zestaw reguł Auto-Tiling")
        form = QFormLayout(group)

        self.combo_rules = QComboBox()
        for rid, r in self.autotile_engine.rulesets.items():
            self.combo_rules.addItem(f"{r.name} ({r.terrain_type})", rid)
        form.addRow("Wybierz regułę:", self.combo_rules)

        self.txt_name = QLineEdit("Trawa – Brzegi")
        form.addRow("Nazwa reguły:", self.txt_name)

        self.txt_terrain = QLineEdit("Grass")
        form.addRow("Główny typ terenu:", self.txt_terrain)

        self.txt_connects = QLineEdit("Grass")
        self.txt_connects.setToolTip("Typy terenu, z którymi ten kafel ma się płynnie łączyć (oddzielone przecinkami)")
        form.addRow("Łączy się z (tereny):", self.txt_connects)

        layout.addWidget(group)

        # Quick Template Setup
        tpl_group = QGroupBox("Szablon kafelków (Standard 3x3)")
        tpl_layout = QVBoxLayout(tpl_group)

        self.lbl_tpl_info = QLabel(
            "Wybierz tileset z biblioteki jako źródło krawędzi i narożników dla wybranego terenu."
        )
        self.lbl_tpl_info.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        tpl_layout.addWidget(self.lbl_tpl_info)

        self.combo_tileset = QComboBox()
        tilesets = [a for a in self.asset_manager.assets.values() if a.asset_type == AssetType.TILESET]
        for ts in tilesets:
            self.combo_tileset.addItem(ts.name, ts.id)
        tpl_layout.addWidget(self.combo_tileset)

        btn_apply_template = QPushButton("⚡ Zastosuj układ 3x3 z wybranego tilesetu")
        btn_apply_template.clicked.connect(self._apply_template)
        tpl_layout.addWidget(btn_apply_template)

        layout.addWidget(tpl_group)
        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_create = QPushButton("➕ Nowa reguła")
        btn_create.clicked.connect(self._create_new_rule)

        btn_save = QPushButton("Zapisz regułę")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save_rule)

        btn_close = QPushButton("Zamknij")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_create)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        # Load active ruleset if exists
        self._load_current_rule()
        self.combo_rules.currentIndexChanged.connect(self._load_current_rule)

    def _load_current_rule(self) -> None:
        rid = self.combo_rules.currentData()
        r = self.autotile_engine.get_ruleset(rid)
        if r:
            self.txt_name.setText(r.name)
            self.txt_terrain.setText(r.terrain_type)
            self.txt_connects.setText(", ".join(r.connects_with))

    def _create_new_rule(self) -> None:
        new_r = AutoTileRuleSet(name="Nowa reguła terenu", terrain_type="Custom")
        self.autotile_engine.register_ruleset(new_r)
        self.combo_rules.addItem(f"{new_r.name} ({new_r.terrain_type})", new_r.id)
        self.combo_rules.setCurrentIndex(self.combo_rules.count() - 1)

    def _apply_template(self) -> None:
        ts_id = self.combo_tileset.currentData()
        if not ts_id:
            QMessageBox.warning(self, "Uwaga", "Brak tilesetów w bibliotece.")
            return

        ts_asset = self.asset_manager.get_asset(ts_id)
        if not ts_asset or not ts_asset.tileset_config:
            QMessageBox.warning(self, "Uwaga", "Wybrany zasób nie jest poprawnym tilesetem.")
            return

        rid = self.combo_rules.currentData()
        r = self.autotile_engine.get_ruleset(rid)
        if not r:
            return

        cfg = ts_asset.tileset_config
        r.setup_standard_3x3_box(
            asset_id=ts_asset.id,
            start_x=0,
            start_y=0,
            tile_w=cfg.tile_width,
            tile_h=cfg.tile_height,
        )
        QMessageBox.information(self, "Sukces", f"Skonfigurowano układ 3x3 dla reguły '{r.name}'!")

    def _save_rule(self) -> None:
        rid = self.combo_rules.currentData()
        r = self.autotile_engine.get_ruleset(rid)
        if not r:
            return

        r.name = self.txt_name.text().strip() or "Reguła"
        r.terrain_type = self.txt_terrain.text().strip() or "Grass"
        connects = [c.strip() for c in self.txt_connects.text().split(",") if c.strip()]
        r.connects_with = connects or [r.terrain_type]
        self.autotile_engine.active_ruleset_id = r.id

        QMessageBox.information(self, "Zapisano", f"Zapisano regułę Auto-Tiling '{r.name}'.")
