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
)
from ..models.project import Project
from ..models.asset import Asset, AssetType, SelectedSubTile
from ..core.asset_manager import AssetManager


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
        p.drawText(QRect(0, 0, target_w, target_h), Qt.AlignmentFlag.AlignCenter, "Brak podglądu")

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
        grp_map = QGroupBox("Aktywna Mapa")
        form_map = QFormLayout(grp_map)
        form_map.setContentsMargins(8, 8, 8, 8)
        self.lbl_map_name = QLabel()
        self.lbl_map_dim = QLabel()
        self.lbl_tile_dim = QLabel()
        self.lbl_layers_cnt = QLabel()
        form_map.addRow("Nazwa:", self.lbl_map_name)
        form_map.addRow("Wymiary mapy:", self.lbl_map_dim)
        form_map.addRow("Rozmiar kafelka:", self.lbl_tile_dim)
        form_map.addRow("Liczba warstw:", self.lbl_layers_cnt)
        c_layout.addWidget(grp_map)

        # 2. Active Layer Properties
        grp_layer = QGroupBox("Aktywna Warstwa")
        form_layer = QFormLayout(grp_layer)
        form_layer.setContentsMargins(8, 8, 8, 8)
        self.lbl_layer_name = QLabel()
        self.lbl_layer_status = QLabel()
        self.lbl_layer_opacity = QLabel()
        form_layer.addRow("Nazwa:", self.lbl_layer_name)
        form_layer.addRow("Status:", self.lbl_layer_status)
        form_layer.addRow("Przezroczystość:", self.lbl_layer_opacity)
        c_layout.addWidget(grp_layer)

        # 3. Selection Properties & Sliced Preview
        grp_sel = QGroupBox("Wybrany Element / Pędzel")
        v_sel_layout = QVBoxLayout(grp_sel)
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

        form_sel = QFormLayout()
        form_sel.setContentsMargins(0, 0, 0, 0)
        self.lbl_sel_type = QLabel("Brak")
        self.lbl_sel_name = QLabel("-")
        self.lbl_sel_pos = QLabel("-")
        self.lbl_sel_size = QLabel("-")
        form_sel.addRow("Typ:", self.lbl_sel_type)
        form_sel.addRow("Zasób:", self.lbl_sel_name)
        form_sel.addRow("Pozycja źródłowa:", self.lbl_sel_pos)
        form_sel.addRow("Rozmiar źródłowy:", self.lbl_sel_size)
        v_sel_layout.addLayout(form_sel)

        c_layout.addWidget(grp_sel)

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

    def refresh(self) -> None:
        active_map = self.project.get_active_map()
        self.lbl_map_name.setText(active_map.name)
        self.lbl_map_dim.setText(f"{active_map.map_width} × {active_map.map_height} komórek")
        self.lbl_tile_dim.setText(f"{active_map.tile_size} × {active_map.tile_size} px")
        self.lbl_layers_cnt.setText(f"{len(active_map.layers)} warstw")

        layer = active_map.get_active_layer()
        if layer:
            self.lbl_layer_name.setText(layer.name)
            vis = "Widoczna" if layer.visible else "Ukryta"
            lock = "Zablokowana" if layer.locked else "Edytowalna"
            self.lbl_layer_status.setText(f"{vis}, {lock}")
            self.lbl_layer_opacity.setText(f"{int(layer.opacity * 100)}%")
        else:
            self.lbl_layer_name.setText("Brak")
            self.lbl_layer_status.setText("-")
            self.lbl_layer_opacity.setText("-")

        # Update preview pixmap and text labels
        sub_pixmap: Optional[QPixmap] = None

        if isinstance(self.selected_item, SelectedSubTile):
            sub = self.selected_item
            name_prefix = f"{sub.asset_name} – " if getattr(sub, "asset_name", None) else ""
            if sub.is_multi_tile():
                self.lbl_sel_type.setText("Blok kafelków tilesetu")
                self.lbl_sel_name.setText(f"{name_prefix}{sub.cols_count} × {sub.rows_count} kafelków")
            else:
                self.lbl_sel_type.setText("Pojedynczy kafelek tilesetu")
                self.lbl_sel_name.setText(f"{name_prefix}Komórka ({sub.col}, {sub.row})")
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
            self.lbl_sel_type.setText("Arkusz tilesetu" if is_ts else "Pojedynczy obiekt PNG")
            self.lbl_sel_name.setText(asset.name)
            self.lbl_sel_pos.setText("0, 0")
            self.lbl_sel_size.setText(f"{asset.width} × {asset.height} px")

            if self.asset_manager:
                sub_pixmap = self.asset_manager.get_pixmap(asset.id)
        else:
            self.lbl_sel_type.setText("Brak wyboru")
            self.lbl_sel_name.setText("-")
            self.lbl_sel_pos.setText("-")
            self.lbl_sel_size.setText("-")

        preview_pix = create_checkerboard_preview(sub_pixmap, 120, 120)
        self.lbl_preview_img.setPixmap(preview_pix)
