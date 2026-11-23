from typing import Optional, Any
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QGroupBox,
    QScrollArea,
    QFrame,
    QLineEdit,
    QDoubleSpinBox,
)
from PyQt6.QtCore import pyqtSignal
from ..models.project import Project
from ..models.layer import MapItem
from ..models.asset import Asset, AssetType, SelectedSubTile
from ..core.asset_manager import AssetManager
from ..core.localization import tr, get_localization


def create_checkerboard_preview(
    pixmap: Optional[QPixmap],
    target_w: int = 120,
    target_h: int = 120,
    cell_size: int = 8,
) -> QPixmap:
    """
    Renders a crisp preview pixmap with a dark checkerboard background
    (transparency pattern) and nearest-neighbor scaling for pixel art.
    """
    out = QPixmap(target_w, target_h)
    out.fill(QColor("#18181b"))
    p = QPainter(out)

    # 1. Dark transparency checkerboard
    c1 = QColor("#222226")
    c2 = QColor("#18181c")
    for y in range(0, target_h, cell_size):
        for x in range(0, target_w, cell_size):
            p.fillRect(
                x,
                y,
                cell_size,
                cell_size,
                c1 if ((x // cell_size + y // cell_size) % 2 == 0) else c2,
            )

    # 2. Draw scaled pixmap if available
    if pixmap and not pixmap.isNull():
        max_draw_w = max(1, target_w - 8)
        max_draw_h = max(1, target_h - 8)
        scaled = pixmap.scaled(
            max_draw_w,
            max_draw_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        ox = (target_w - scaled.width()) // 2
        oy = (target_h - scaled.height()) // 2
        p.drawPixmap(ox, oy, scaled)

        # High-contrast outline around the cropped tile
        p.setPen(QColor("#3b82f6"))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(ox - 1, oy - 1, scaled.width() + 1, scaled.height() + 1)
    else:
        p.setPen(QColor("#71717a"))
        p.drawText(QRect(0, 0, target_w, target_h), Qt.AlignmentFlag.AlignCenter, tr("properties.no_preview"))

    p.end()
    return out


class PropertiesPanel(QWidget):
    """
    Inspector / Properties dock displaying live parameters of active map,
    active layer, and selected tile/object with an interactive visual preview.
    """

    def __init__(
        self,
        project: Project,
        asset_manager: Optional[AssetManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.project = project
        self.asset_manager = asset_manager
        self.selected_item: Optional[Any] = None

        self._init_ui()
        get_localization().languageChanged.connect(self._retranslate)
        self._retranslate()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(8)

        # 1. Map Properties
        self.grp_map = QGroupBox()
        self.form_map = QFormLayout(self.grp_map)
        self.form_map.setContentsMargins(8, 8, 8, 8)
        self.lbl_map_name = QLabel()
        self.lbl_map_dim = QLabel()
        self.lbl_tile_dim = QLabel()
        self.lbl_layers_cnt = QLabel()
        self.form_map.addRow("Nazwa:", self.lbl_map_name)
        self.form_map.addRow("Wymiary mapy:", self.lbl_map_dim)
        self.form_map.addRow("Rozmiar kafelka:", self.lbl_tile_dim)
        self.form_map.addRow("Liczba warstw:", self.lbl_layers_cnt)
        c_layout.addWidget(self.grp_map)

        # 2. Active Layer Properties
        self.grp_layer = QGroupBox()
        self.form_layer = QFormLayout(self.grp_layer)
        self.form_layer.setContentsMargins(8, 8, 8, 8)
        self.lbl_layer_name = QLabel()
        self.lbl_layer_status = QLabel()
        self.lbl_layer_opacity = QLabel()
        self.form_layer.addRow("Nazwa:", self.lbl_layer_name)
        self.form_layer.addRow("Status:", self.lbl_layer_status)
        self.form_layer.addRow("Przezroczystość:", self.lbl_layer_opacity)
        c_layout.addWidget(self.grp_layer)

        # 3. Selection Properties & Sliced Preview
        self.grp_sel = QGroupBox()
        v_sel_layout = QVBoxLayout(self.grp_sel)
        v_sel_layout.setContentsMargins(8, 8, 8, 8)
        v_sel_layout.setSpacing(6)

        # Visual Thumbnail Container
        preview_container = QFrame()
        preview_container.setStyleSheet("""
            QFrame {
                background-color: #141417;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        pc_layout = QHBoxLayout(preview_container)
        pc_layout.setContentsMargins(2, 2, 2, 2)
        pc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_preview_img = QLabel()
        self.lbl_preview_img.setFixedSize(120, 120)
        self.lbl_preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_img.setStyleSheet("""
            QLabel {
                background: #18181b;
                border: 1px solid #3f3f46;
                border-radius: 4px;
            }
        """)
        pc_layout.addWidget(self.lbl_preview_img)
        v_sel_layout.addWidget(preview_container)

        self.form_sel = QFormLayout()
        self.form_sel.setContentsMargins(0, 0, 0, 0)
        self.lbl_sel_type = QLabel()
        self.lbl_sel_name = QLabel("-")
        self.lbl_sel_pos = QLabel("-")
        self.lbl_sel_size = QLabel("-")
        self.form_sel.addRow("Typ:", self.lbl_sel_type)
        self.form_sel.addRow("Zasób:", self.lbl_sel_name)
        self.form_sel.addRow("Pozycja źródłowa:", self.lbl_sel_pos)
        self.form_sel.addRow("Rozmiar źródłowy:", self.lbl_sel_size)
        self.txt_object_type = QLineEdit()
        self.txt_interaction = QLineEdit()
        self.spin_interaction_radius = QDoubleSpinBox()
        self.spin_interaction_radius.setRange(0.0, 10000.0)
        self.spin_interaction_radius.setSuffix(" px")
        self.txt_object_properties = QLineEdit()
        self.txt_object_properties.setPlaceholderText(
            "hp=100:integer, name=Goblin:string"
        )
        for label, field in (
            ("Typ obiektu:", self.txt_object_type),
            ("Interakcja:", self.txt_interaction),
            ("Promień:", self.spin_interaction_radius),
            ("Właściwości:", self.txt_object_properties),
        ):
            self.form_sel.addRow(label, field)
        self.txt_object_type.editingFinished.connect(self._save_object_properties)
        self.txt_interaction.editingFinished.connect(self._save_object_properties)
        self.spin_interaction_radius.editingFinished.connect(
            self._save_object_properties
        )
        self.txt_object_properties.editingFinished.connect(
            self._save_object_properties
        )
        v_sel_layout.addLayout(self.form_sel)

        c_layout.addWidget(self.grp_sel)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def set_project(self, project: Project) -> None:
        self.project = project
        self.refresh()

    def set_asset_manager(self, asset_manager: AssetManager) -> None:
        self.asset_manager = asset_manager
        self.refresh()

    def set_selected_item(self, item: Any) -> None:
        self.selected_item = item
        self.refresh()

    def _retranslate(self, *_args) -> None:
        self.grp_map.setTitle(tr("properties.map_title"))
        self.grp_layer.setTitle(tr("properties.layer_title"))
        self.grp_sel.setTitle(tr("properties.selection_title"))
        for form, fields, keys in (
            (
                self.form_map,
                (self.lbl_map_name, self.lbl_map_dim, self.lbl_tile_dim, self.lbl_layers_cnt),
                ("properties.name", "properties.map_dimensions", "properties.tile_size", "properties.layer_count"),
            ),
            (
                self.form_layer,
                (self.lbl_layer_name, self.lbl_layer_status, self.lbl_layer_opacity),
                ("properties.name", "properties.status", "properties.opacity"),
            ),
            (
                self.form_sel,
                (self.lbl_sel_type, self.lbl_sel_name, self.lbl_sel_pos, self.lbl_sel_size),
                ("properties.type", "properties.asset", "properties.source_position", "properties.source_size"),
            ),
        ):
            for field, key in zip(fields, keys):
                label = form.labelForField(field)
                if label is not None:
                    label.setText(tr(key))
        self.refresh()

    def refresh(self) -> None:
        active_map = self.project.get_active_map()
        self.lbl_map_name.setText(active_map.name)
        self.lbl_map_dim.setText(
            f"{active_map.map_width} × {active_map.map_height} {tr('properties.cells')}"
        )
        self.lbl_tile_dim.setText(f"{active_map.tile_size} × {active_map.tile_size} px")
        self.lbl_layers_cnt.setText(f"{len(active_map.layers)} {tr('properties.layers')}")

        layer = active_map.get_active_layer()
        if layer:
            self.lbl_layer_name.setText(layer.name)
            vis = tr("properties.visible") if layer.visible else tr("properties.hidden")
            lock = tr("properties.locked") if layer.locked else tr("properties.editable")
            self.lbl_layer_status.setText(f"{vis}, {lock}")
            self.lbl_layer_opacity.setText(f"{int(layer.opacity * 100)}%")
        else:
            self.lbl_layer_name.setText(tr("properties.none"))
            self.lbl_layer_status.setText("-")
            self.lbl_layer_opacity.setText("-")

        # Update preview pixmap and text labels
        sub_pixmap: Optional[QPixmap] = None

        if isinstance(self.selected_item, SelectedSubTile):
            sub = self.selected_item
            name_prefix = f"{sub.asset_name} – " if getattr(sub, "asset_name", None) else ""
            if sub.is_multi_tile():
                self.lbl_sel_type.setText(tr("properties.tileset_block"))
                self.lbl_sel_name.setText(
                    f"{name_prefix}{sub.cols_count} × {sub.rows_count} {tr('properties.tiles')}"
                )
            else:
                self.lbl_sel_type.setText(tr("properties.single_tile"))
                self.lbl_sel_name.setText(
                    f"{name_prefix}{tr('properties.cell', col=sub.col, row=sub.row)}"
                )
            self.lbl_sel_pos.setText(f"X: {sub.sub_x} px, Y: {sub.sub_y} px")
            self.lbl_sel_size.setText(f"{sub.sub_w} × {sub.sub_h} px")

            # Extract exact slice from AssetManager
            if self.asset_manager:
                full_pix = self.asset_manager.get_pixmap(sub.asset_id)
                if full_pix and not full_pix.isNull():
                    sub_pixmap = full_pix.copy(sub.sub_x, sub.sub_y, sub.sub_w, sub.sub_h)

        elif isinstance(self.selected_item, Asset):
            asset = self.selected_item
            is_ts = (asset.asset_type == AssetType.TILESET)
            self.lbl_sel_type.setText(
                tr("properties.tileset_sheet") if is_ts else tr("properties.png_object")
            )
            self.lbl_sel_name.setText(asset.name)
            self.lbl_sel_pos.setText("0, 0")
            self.lbl_sel_size.setText(f"{asset.width} × {asset.height} px")

            if self.asset_manager:
                sub_pixmap = self.asset_manager.get_pixmap(asset.id)
        elif isinstance(self.selected_item, MapItem):
            obj = self.selected_item
            self.lbl_sel_type.setText(obj.object_type or "Obiekt")
            self.lbl_sel_name.setText(obj.id)
            self.lbl_sel_pos.setText(
                f"X: {obj.free_x if obj.free_x is not None else obj.col}, "
                f"Y: {obj.free_y if obj.free_y is not None else obj.row}"
            )
            self.lbl_sel_size.setText(
                f"{obj.dest_w * abs(obj.scale_x):.1f} × "
                f"{obj.dest_h * abs(obj.scale_y):.1f}"
            )
            self.txt_object_type.setText(obj.object_type)
            self.txt_interaction.setText(obj.interaction_label)
            self.spin_interaction_radius.setValue(obj.interaction_radius)
            self.txt_object_properties.setText(
                self._format_properties(obj.properties, obj.property_types)
            )
        else:
            self.lbl_sel_type.setText(tr("properties.no_selection"))
            self.lbl_sel_name.setText("-")
            self.lbl_sel_pos.setText("-")
            self.lbl_sel_size.setText("-")

        preview_pix = create_checkerboard_preview(sub_pixmap, 120, 120)
        self.lbl_preview_img.setPixmap(preview_pix)
        is_object = isinstance(self.selected_item, MapItem)
        for field in (
            self.txt_object_type,
            self.txt_interaction,
            self.spin_interaction_radius,
            self.txt_object_properties,
        ):
            field.setEnabled(is_object)

    @staticmethod
    def _format_properties(
        properties: dict, property_types: dict
    ) -> str:
        return ", ".join(
            f"{key}={value}:{property_types.get(key, 'string')}"
            for key, value in properties.items()
        )

    def _save_object_properties(self) -> None:
        if not isinstance(self.selected_item, MapItem):
            return
        obj = self.selected_item
        obj.object_type = self.txt_object_type.text().strip()
        obj.interaction_label = self.txt_interaction.text().strip()
        obj.interaction_radius = self.spin_interaction_radius.value()
        properties = {}
        property_types = {}
        for entry in self.txt_object_properties.text().split(","):
            entry = entry.strip()
            if not entry or "=" not in entry:
                continue
            name, raw_value = entry.split("=", 1)
            value_text = raw_value.strip()
            property_type = "string"
            if ":" in value_text:
                value_text, property_type = value_text.rsplit(":", 1)
                property_type = property_type.strip().lower()
            try:
                if property_type == "integer":
                    value = int(value_text)
                elif property_type == "float":
                    value = float(value_text)
                elif property_type == "boolean":
                    value = value_text.casefold() in ("true", "1", "yes")
                else:
                    property_type = "string"
                    value = value_text
            except ValueError:
                property_type = "string"
                value = value_text
            properties[name.strip()] = value
            property_types[name.strip()] = property_type
        obj.properties = properties
        obj.property_types = property_types
        self.project.is_modified = True
        self.object_changed.emit()
    object_changed = pyqtSignal()
