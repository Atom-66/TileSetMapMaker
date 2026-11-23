from typing import Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool, pyqtSlot
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.autotile_engine import AutoTileEngine
from ...core.terrain_generator import TerrainApplyCommand
from ...models.project import Project
from ...models.terrain import (
    TerrainConfig,
    TerrainGenerator,
    TerrainResult,
    TerrainType,
)


class GenerationSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class TerrainGenerationTask(QRunnable):
    def __init__(
        self,
        generator: TerrainGenerator,
        width: int,
        height: int,
        config: TerrainConfig,
    ):
        super().__init__()
        self.generator = generator
        self.width = width
        self.height = height
        self.config = config
        self.signals = GenerationSignals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.generator.generate(
                self.width, self.height, self.config
            )
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class TerrainPreview(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setMinimumHeight(240)

    def set_result(self, result: Optional[TerrainResult]) -> None:
        if result is None:
            self.label.clear()
            return
        colors = {
            TerrainType.GRASS: (102, 170, 78),
            TerrainType.FOREST: (36, 111, 58),
            TerrainType.WATER: (58, 126, 210),
            TerrainType.LAKE: (65, 105, 185),
            TerrainType.MOUNTAIN: (132, 128, 124),
            TerrainType.ROAD: (173, 142, 91),
        }
        preview_scale = max(result.width, result.height, 1) / 480
        sample_step = max(1, int(preview_scale))
        preview_width = (result.width + sample_step - 1) // sample_step
        preview_height = (result.height + sample_step - 1) // sample_step
        image = QImage(
            preview_width, preview_height, QImage.Format.Format_RGB32
        )
        for py, y in enumerate(range(0, result.height, sample_step)):
            for px, x in enumerate(range(0, result.width, sample_step)):
                image.setPixelColor(
                    px, py, QColor(*colors[result.get(x, y)])
                )
        self.label.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.width(),
                self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )


class TerrainGeneratorDialog(QDialog):
    generated = pyqtSignal(object)

    def __init__(
        self,
        project: Project,
        autotile_engine: AutoTileEngine,
        generator: TerrainGenerator,
        history_manager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.autotile_engine = autotile_engine
        self.generator = generator
        self.history_manager = history_manager
        self.result: Optional[TerrainResult] = None
        self._generation_running = False
        self.setWindowTitle("Generator terenu")
        self.resize(760, 620)
        self._init_ui()
        self._load_config(generator.last_config)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.combo_preset = QComboBox()
        for key, preset in self.generator.presets.items():
            self.combo_preset.addItem(preset.name, key)
        self.combo_preset.currentIndexChanged.connect(self._preset_changed)
        top.addWidget(QLabel("Preset:"))
        top.addWidget(self.combo_preset, 1)
        save_preset = QPushButton("Zapisz preset")
        save_preset.clicked.connect(self._save_preset)
        top.addWidget(save_preset)
        root.addLayout(top)

        form = QFormLayout()
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 2_147_483_647)
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(2, 1000)
        self.spin_water = QDoubleSpinBox()
        self.spin_water.setRange(0.05, 0.49)
        self.spin_water.setSingleStep(0.01)
        self.spin_mountain = QDoubleSpinBox()
        self.spin_mountain.setRange(0.51, 0.95)
        self.spin_mountain.setSingleStep(0.01)
        self.spin_forest = QDoubleSpinBox()
        self.spin_forest.setRange(0.51, 0.95)
        self.spin_forest.setSingleStep(0.01)
        self.spin_rivers = QSpinBox()
        self.spin_rivers.setRange(0, 12)
        self.spin_river_width = QSpinBox()
        self.spin_river_width.setRange(1, 9)
        self.spin_roads = QSpinBox()
        self.spin_roads.setRange(0, 12)
        self.spin_road_width = QSpinBox()
        self.spin_road_width.setRange(1, 7)
        for label, widget in (
            ("Seed:", self.spin_seed),
            ("Skala szumu:", self.spin_scale),
            ("Poziom wody:", self.spin_water),
            ("Poziom gór:", self.spin_mountain),
            ("Próg lasu:", self.spin_forest),
            ("Rzeki:", self.spin_rivers),
            ("Szerokość rzek:", self.spin_river_width),
            ("Drogi:", self.spin_roads),
            ("Szerokość dróg:", self.spin_road_width),
        ):
            form.addRow(label, widget)
        root.addLayout(form)

        rules_label = QLabel("Reguły terenu")
        rules_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        root.addWidget(rules_label)
        self.rule_combos: Dict[str, QComboBox] = {}
        for terrain in TerrainType:
            combo = QComboBox()
            combo.addItem("Brak mapowania", "")
            for ruleset in self.autotile_engine.rulesets.values():
                combo.addItem(
                    f"{ruleset.name} ({ruleset.terrain_type})",
                    ruleset.id,
                )
            self.rule_combos[terrain.name.casefold()] = combo
            form.addRow(f"{terrain.name.title()}:", combo)

        self.preview = TerrainPreview()
        root.addWidget(self.preview, 1)

        buttons = QHBoxLayout()
        preview_button = QPushButton("Generuj podgląd")
        preview_button.clicked.connect(self.preview_generation)
        buttons.addWidget(preview_button)
        restore_button = QPushButton("Przywróć poprzedni")
        restore_button.clicked.connect(self.restore_previous)
        buttons.addWidget(restore_button)
        buttons.addStretch()
        apply_button = QPushButton("Zastosuj na aktywnej warstwie")
        apply_button.clicked.connect(self.apply_generation)
        buttons.addWidget(apply_button)
        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    def _load_config(self, config: TerrainConfig) -> None:
        self.spin_seed.setValue(config.seed)
        self.spin_scale.setValue(config.scale)
        self.spin_water.setValue(config.water_level)
        self.spin_mountain.setValue(config.mountain_level)
        self.spin_forest.setValue(config.forest_threshold)
        self.spin_rivers.setValue(config.river_count)
        self.spin_river_width.setValue(config.river_width)
        self.spin_roads.setValue(config.road_count)
        self.spin_road_width.setValue(config.road_width)
        for key, combo in self.rule_combos.items():
            index = combo.findData(config.ruleset_ids.get(key, ""))
            combo.setCurrentIndex(max(0, index))

    def _config(self) -> TerrainConfig:
        return TerrainConfig(
            seed=self.spin_seed.value(),
            scale=self.spin_scale.value(),
            water_level=self.spin_water.value(),
            mountain_level=self.spin_mountain.value(),
            forest_threshold=self.spin_forest.value(),
            river_count=self.spin_rivers.value(),
            river_width=self.spin_river_width.value(),
            road_count=self.spin_roads.value(),
            road_width=self.spin_road_width.value(),
            ruleset_ids={
                key: combo.currentData()
                for key, combo in self.rule_combos.items()
                if combo.currentData()
            },
        )

    def _preset_changed(self, _index: int) -> None:
        preset = self.generator.presets.get(
            self.combo_preset.currentData()
        )
        if preset:
            self._load_config(preset.config)

    def _save_preset(self) -> None:
        key = f"custom_{len(self.generator.presets) + 1}"
        config = self._config()
        self.generator.presets[key] = type(
            self.generator.presets["temperate"]
        )(f"Preset {len(self.generator.presets) + 1}", config)
        self.combo_preset.addItem(f"Preset {len(self.generator.presets)}", key)
        self.combo_preset.setCurrentIndex(self.combo_preset.count() - 1)

    def preview_generation(self) -> None:
        if self._generation_running:
            return
        config = self._config()
        self._generation_running = True
        task = TerrainGenerationTask(
            self.generator,
            self.project.map_width,
            self.project.map_height,
            config,
        )
        task.signals.finished.connect(self._generation_finished)
        task.signals.failed.connect(self._generation_failed)
        self._generation_task = task
        QThreadPool.globalInstance().start(task)

    def _generation_finished(self, result: TerrainResult) -> None:
        self._generation_running = False
        self._generation_task = None
        self.result = result
        self.preview.set_result(result)

    def _generation_failed(self, message: str) -> None:
        self._generation_running = False
        self._generation_task = None
        QMessageBox.critical(
            self, "Błąd generatora", f"Nie udało się wygenerować terenu:\n{message}"
        )

    def restore_previous(self) -> None:
        self.result = self.generator.restore_previous()
        if self.result is None:
            QMessageBox.information(
                self, "Brak wyniku", "Nie ma poprzedniego podglądu do przywrócenia."
            )
            return
        self.preview.set_result(self.result)

    def apply_generation(self) -> None:
        if self.result is None:
            self.preview_generation()
        config = self._config()
        if not config.ruleset_ids:
            QMessageBox.warning(
                self,
                "Brak reguł",
                "Przypisz co najmniej jedną regułę terenu przed zastosowaniem.",
            )
            return
        layer = self.project.get_active_layer()
        if not layer or layer.locked:
            QMessageBox.warning(
                self, "Nieaktywna warstwa", "Wybierz edytowalną warstwę."
            )
            return
        command = TerrainApplyCommand(
            self.project,
            layer.id,
            self.result,
            config,
            self.autotile_engine,
        )
        command.execute()
        self.history_manager.push(command)
        self.project.is_modified = True
        self.generated.emit(self.result)
