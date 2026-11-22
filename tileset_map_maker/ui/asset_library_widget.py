import os
from typing import Optional, List, Dict
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QSlider,
    QFileDialog,
    QMenu,
    QInputDialog,
    QMessageBox,
    QSplitter,
    QComboBox,
    QToolButton,
    QTabWidget,
)
from PyQt6.QtGui import QIcon, QPixmap, QAction

from ..models.asset import Asset, AssetType, SelectedSubTile
from ..models.category import CategoryNode
from ..models.asset_set import AssetSet
from ..core.asset_manager import AssetManager
from ..core.set_manager import SetManager
from ..core.stamp_manager import StampManager
from .tileset_slicer_dialog import TilesetSlicerDialog


class AssetLibraryWidget(QWidget):
    """
    Comprehensive Asset Library supporting categories, logical asset sets (palettes),
    saved stamp presets, search, filtering, and brush variant assignments.
    """
    variant_added = pyqtSignal(object)  # Asset or SubTile

    def __init__(
        self,
        asset_manager: AssetManager,
        set_manager: Optional[SetManager] = None,
        stamp_manager: Optional[StampManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.asset_manager = asset_manager
        self.set_manager = set_manager or SetManager()
        self.stamp_manager = stamp_manager or StampManager()

        self.current_filter_mode = "all"  # "all", "favorites", "recent"
        self.selected_category_path: Optional[str] = None
        self.active_tab_index = 0  # 0 = Categories, 1 = Sets, 2 = Saved Stamps
        self.thumb_size = 64

        self._init_ui()
        self._connect_signals()
        self.refresh_categories()
        self.refresh_sets_list()
        self.refresh_assets_list()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Search Bar and Filter Selector
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Szukaj zasobów...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_edit)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Wszystkie", "⭐ Ulubione", "🕒 Ostatnie"])
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        search_layout.addWidget(self.filter_combo)
        layout.addLayout(search_layout)

        # 2. Action buttons (Import)
        import_layout = QHBoxLayout()
        btn_import_files = QPushButton("➕ Dodaj pliki")
        btn_import_files.setToolTip("Importuj pojedynczy lub wiele plików PNG")
        btn_import_files.clicked.connect(self._import_files_dialog)

        btn_import_folder = QPushButton("📁 Importuj folder")
        btn_import_folder.setToolTip("Importuj cały folder zachowując podkategorie")
        btn_import_folder.clicked.connect(self._import_folder_dialog)

        import_layout.addWidget(btn_import_files)
        import_layout.addWidget(btn_import_folder)
        layout.addLayout(import_layout)

        # 3. Main Splitter: Top (Categories / Sets / Stamps Tabs) + Bottom (Assets Grid)
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Tabs
        self.top_tabs = QTabWidget()

        # Tab 1: Categories Tree
        cat_container = QWidget()
        cat_layout = QVBoxLayout(cat_container)
        cat_layout.setContentsMargins(2, 2, 2, 2)
        cat_layout.setSpacing(2)

        cat_header = QHBoxLayout()
        cat_title = QLabel("KATEGORIE")
        cat_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #a1a1aa;")
        cat_header.addWidget(cat_title)
        cat_header.addStretch()

        btn_add_cat = QToolButton()
        btn_add_cat.setText("➕")
        btn_add_cat.setToolTip("Nowa kategoria")
        btn_add_cat.clicked.connect(self._create_category_dialog)
        cat_header.addWidget(btn_add_cat)
        cat_layout.addLayout(cat_header)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.category_tree.customContextMenuRequested.connect(self._on_category_context_menu)
        self.category_tree.itemClicked.connect(self._on_category_clicked)
        cat_layout.addWidget(self.category_tree)
        self.top_tabs.addTab(cat_container, "Kategorie")

        # Tab 2: Logical Sets (Palettes)
        sets_container = QWidget()
        sets_layout = QVBoxLayout(sets_container)
        sets_layout.setContentsMargins(2, 2, 2, 2)
        sets_layout.setSpacing(2)

        sets_header = QHBoxLayout()
        sets_title = QLabel("ZESTAWY (KOLEKCJE)")
        sets_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #a1a1aa;")
        sets_header.addWidget(sets_title)
        sets_header.addStretch()

        btn_add_set = QToolButton()
        btn_add_set.setText("➕")
        btn_add_set.setToolTip("Utwórz nowy zestaw zasobów")
        btn_add_set.clicked.connect(self._create_set_dialog)
        sets_header.addWidget(btn_add_set)
        sets_layout.addLayout(sets_header)

        self.sets_list = QListWidget()
        self.sets_list.itemClicked.connect(self._on_set_clicked)
        self.sets_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sets_list.customContextMenuRequested.connect(self._on_set_context_menu)
        sets_layout.addWidget(self.sets_list)
        self.top_tabs.addTab(sets_container, "Zestawy")

        # Tab 3: Saved Stamps
        stamps_container = QWidget()
        stamps_layout = QVBoxLayout(stamps_container)
        stamps_layout.setContentsMargins(2, 2, 2, 2)
        stamps_layout.setSpacing(2)

        stamps_header = QHBoxLayout()
        stamps_title = QLabel("ZAPISANE STEMPLE")
        stamps_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #a1a1aa;")
        stamps_header.addWidget(stamps_title)
        stamps_header.addStretch()
        stamps_layout.addLayout(stamps_header)

        self.stamps_list = QListWidget()
        self.stamps_list.itemClicked.connect(self._on_stamp_clicked)
        self.stamps_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.stamps_list.customContextMenuRequested.connect(self._on_stamp_context_menu)
        stamps_layout.addWidget(self.stamps_list)
        self.top_tabs.addTab(stamps_container, "Stemple")

        self.splitter.addWidget(self.top_tabs)

        # Assets Thumbnail Grid
        asset_container = QWidget()
        asset_layout = QVBoxLayout(asset_container)
        asset_layout.setContentsMargins(0, 0, 0, 0)
        asset_layout.setSpacing(4)

        grid_header = QHBoxLayout()
        self.lbl_asset_count = QLabel("0 grafik")
        self.lbl_asset_count.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        grid_header.addWidget(self.lbl_asset_count)
        grid_header.addStretch()

        lbl_zoom = QLabel("Rozmiar:")
        lbl_zoom.setStyleSheet("font-size: 11px; color: #71717a;")
        grid_header.addWidget(lbl_zoom)

        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(32, 128)
        self.slider_size.setValue(self.thumb_size)
        self.slider_size.setFixedWidth(80)
        self.slider_size.valueChanged.connect(self._on_thumb_size_changed)
        grid_header.addWidget(self.slider_size)
        asset_layout.addLayout(grid_header)

        self.asset_list = QListWidget()
        self.asset_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.asset_list.setIconSize(QSize(self.thumb_size, self.thumb_size))
        self.asset_list.setGridSize(QSize(self.thumb_size + 24, self.thumb_size + 36))
        self.asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.asset_list.setMovement(QListWidget.Movement.Static)
        self.asset_list.setSpacing(6)
        self.asset_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.asset_list.customContextMenuRequested.connect(self._on_asset_context_menu)
        self.asset_list.itemClicked.connect(self._on_asset_clicked)
        self.asset_list.itemDoubleClicked.connect(self._on_asset_double_clicked)
        asset_layout.addWidget(self.asset_list)

        self.splitter.addWidget(asset_container)
        self.splitter.setSizes([200, 320])

        layout.addWidget(self.splitter)

    def _connect_signals(self) -> None:
        self.top_tabs.currentChanged.connect(self._on_tab_changed)
        self.asset_manager.assets_changed.connect(self.refresh_assets_list)
        self.asset_manager.categories_changed.connect(self.refresh_categories)
        self.set_manager.sets_changed.connect(self.refresh_sets_list)
        self.stamp_manager.stamps_changed.connect(self.refresh_stamps_list)

    def _on_tab_changed(self, idx: int) -> None:
        self.active_tab_index = idx
        if hasattr(self, "asset_list"):
            self.refresh_assets_list()

    def refresh_categories(self) -> None:
        self.category_tree.clear()
        root_node = self.asset_manager.category_tree.root

        all_item = QTreeWidgetItem(self.category_tree, ["🌐 Wszystkie kategorie"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, "")

        def _populate(node: CategoryNode, parent_item: QTreeWidgetItem):
            for child_name in sorted(node.children.keys()):
                child_node = node.children[child_name]
                item = QTreeWidgetItem(parent_item, [f"📁 {child_name} ({len(child_node.asset_ids)})"])
                item.setData(0, Qt.ItemDataRole.UserRole, child_node.path)
                _populate(child_node, item)

        _populate(root_node, all_item)
        self.category_tree.expandAll()

    def refresh_sets_list(self) -> None:
        self.sets_list.clear()
        for s in self.set_manager.sets.values():
            prefix = "⭐ " if s.is_favorite else "📦 "
            item = QListWidgetItem(f"{prefix}{s.name} ({len(s.asset_ids)} el.)")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            if s.id == self.set_manager.active_set_id:
                self.sets_list.setCurrentItem(item)
            self.sets_list.addItem(item)

    def refresh_stamps_list(self) -> None:
        self.stamps_list.clear()
        for stamp in self.stamp_manager.stamps.values():
            item = QListWidgetItem(f"📑 {stamp.name} ({stamp.width}x{stamp.height})")
            item.setData(Qt.ItemDataRole.UserRole, stamp.id)
            if stamp.id == self.stamp_manager.active_stamp_id:
                self.stamps_list.setCurrentItem(item)
            self.stamps_list.addItem(item)

    def refresh_assets_list(self) -> None:
        self.asset_list.clear()

        query = self.search_edit.text()
        only_fav = self.current_filter_mode == "favorites"
        only_rec = self.current_filter_mode == "recent"

        if self.active_tab_index == 1:
            # Active Set items
            active_set = self.set_manager.get_active_set()
            if active_set:
                assets = [self.asset_manager.get_asset(aid) for aid in active_set.asset_ids if self.asset_manager.get_asset(aid)]
            else:
                assets = []
        else:
            assets = self.asset_manager.search_assets(
                query=query,
                category_path=self.selected_category_path,
                only_favorites=only_fav,
                only_recent=only_rec,
            )

        self.lbl_asset_count.setText(f"{len(assets)} grafik")

        for asset in assets:
            thumb = self.asset_manager.get_thumbnail(asset.id, self.thumb_size)
            icon = QIcon(thumb) if thumb else QIcon()

            label_text = asset.name
            if asset.is_favorite:
                label_text = f"⭐ {label_text}"

            item = QListWidgetItem(icon, label_text)
            item.setToolTip(
                f"Nazwa: {asset.name}\n"
                f"Typ: {'Tileset' if asset.asset_type == AssetType.TILESET else 'Pojedyncza grafika'}\n"
                f"Wymiary: {asset.width}x{asset.height} px\n"
                f"Kategoria: {asset.category_path}"
            )
            item.setData(Qt.ItemDataRole.UserRole, asset.id)
            self.asset_list.addItem(item)

    def _on_search_changed(self, text: str) -> None:
        self.refresh_assets_list()

    def _on_filter_changed(self, idx: int) -> None:
        modes = ["all", "favorites", "recent"]
        self.current_filter_mode = modes[idx]
        self.refresh_assets_list()

    def _on_thumb_size_changed(self, val: int) -> None:
        self.thumb_size = val
        self.asset_list.setIconSize(QSize(val, val))
        self.asset_list.setGridSize(QSize(val + 24, val + 36))
        self.refresh_assets_list()

    def _on_category_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        self.selected_category_path = path if path else None
        self.refresh_assets_list()

    def _on_set_clicked(self, item: QListWidgetItem) -> None:
        set_id = item.data(Qt.ItemDataRole.UserRole)
        self.set_manager.set_active_set(set_id)
        self.refresh_assets_list()

    def _on_stamp_clicked(self, item: QListWidgetItem) -> None:
        stamp_id = item.data(Qt.ItemDataRole.UserRole)
        self.stamp_manager.set_active_stamp(stamp_id)

    def _on_asset_clicked(self, item: QListWidgetItem) -> None:
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        asset = self.asset_manager.get_asset(asset_id)
        if asset:
            self.asset_manager.select_asset(asset)

    def _on_asset_double_clicked(self, item: QListWidgetItem) -> None:
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        asset = self.asset_manager.get_asset(asset_id)
        if asset:
            self._open_tileset_slicer(asset)

    def _open_tileset_slicer(self, asset: Asset) -> None:
        dialog = TilesetSlicerDialog(asset, self.asset_manager, self)
        if dialog.exec():
            self.refresh_assets_list()

    def _on_asset_context_menu(self, pos: QPoint) -> None:
        item = self.asset_list.itemAt(pos)
        if not item:
            return
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        asset = self.asset_manager.get_asset(asset_id)
        if not asset:
            return

        menu = QMenu(self)
        menu.addAction("✂️ Konfiguruj kafelki (Slicer)...", lambda: self._open_tileset_slicer(asset))

        fav_text = "❌ Usuń z ulubionych" if asset.is_favorite else "⭐ Dodaj do ulubionych"
        menu.addAction(fav_text, lambda: self._toggle_favorite(asset))

        # Add to set submenu
        set_menu = menu.addMenu("📦 Dodaj do zestawu...")
        for s in self.set_manager.sets.values():
            set_menu.addAction(s.name, lambda s_obj=s: self._add_asset_to_set(asset.id, s_obj))

        menu.addAction("🎲 Dodaj do wariantów pędzla", lambda: self.variant_added.emit(asset))
        menu.addAction("📂 Przenieś do kategorii...", lambda: self._move_asset_dialog(asset))
        menu.addSeparator()
        menu.addAction("🗑️ Usuń z biblioteki", lambda: self._delete_asset(asset))

        menu.exec(self.asset_list.mapToGlobal(pos))

    def _add_asset_to_set(self, asset_id: str, asset_set: AssetSet) -> None:
        asset_set.add_asset(asset_id)
        self.set_manager.save_to_disk()
        self.refresh_sets_list()

    def _create_set_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "Nowy zestaw zasobów", "Nazwa zestawu (np. 'Leśna lokacja'):")
        if ok and name.strip():
            self.set_manager.create_set(name.strip())

    def _on_set_context_menu(self, pos: QPoint) -> None:
        item = self.sets_list.itemAt(pos)
        if not item:
            return
        set_id = item.data(Qt.ItemDataRole.UserRole)
        asset_set = self.set_manager.get_set(set_id)
        if not asset_set:
            return

        menu = QMenu(self)
        fav_text = "❌ Usuń z ulubionych" if asset_set.is_favorite else "⭐ Dodaj do ulubionych"
        menu.addAction(fav_text, lambda: self._toggle_set_favorite(asset_set))
        menu.addAction("🗑️ Usuń zestaw", lambda: self.set_manager.remove_set(set_id))
        menu.exec(self.sets_list.mapToGlobal(pos))

    def _toggle_set_favorite(self, asset_set: AssetSet) -> None:
        asset_set.is_favorite = not asset_set.is_favorite
        self.set_manager.save_to_disk()
        self.refresh_sets_list()

    def _on_stamp_context_menu(self, pos: QPoint) -> None:
        item = self.stamps_list.itemAt(pos)
        if not item:
            return
        stamp_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("🔄 Obróć o 90°", lambda: self._rotate_stamp(stamp_id))
        menu.addAction("↔️ Odbij w poziomie", lambda: self._flip_stamp_h(stamp_id))
        menu.addAction("↕️ Odbij w pionie", lambda: self._flip_stamp_v(stamp_id))
        menu.addSeparator()
        menu.addAction("🗑️ Usuń stempel", lambda: self.stamp_manager.remove_stamp(stamp_id))
        menu.exec(self.stamps_list.mapToGlobal(pos))

    def _rotate_stamp(self, stamp_id: str) -> None:
        stamp = self.stamp_manager.get_stamp(stamp_id)
        if stamp:
            stamp.rotate_90()
            self.stamp_manager.save_to_disk()
            self.refresh_stamps_list()

    def _flip_stamp_h(self, stamp_id: str) -> None:
        stamp = self.stamp_manager.get_stamp(stamp_id)
        if stamp:
            stamp.flip_horizontal()
            self.stamp_manager.save_to_disk()

    def _flip_stamp_v(self, stamp_id: str) -> None:
        stamp = self.stamp_manager.get_stamp(stamp_id)
        if stamp:
            stamp.flip_vertical()
            self.stamp_manager.save_to_disk()

    def _toggle_favorite(self, asset: Asset) -> None:
        asset.is_favorite = not asset.is_favorite
        self.refresh_assets_list()

    def _move_asset_dialog(self, asset: Asset) -> None:
        all_paths = self.asset_manager.category_tree.get_all_paths()
        if not all_paths:
            all_paths = ["Custom"]
        cat, ok = QInputDialog.getItem(
            self,
            "Przenieś zasób",
            "Wybierz kategorię docelową:",
            all_paths,
            editable=True,
        )
        if ok and cat:
            self.asset_manager.move_asset(asset.id, cat)
            self.refresh_categories()
            self.refresh_assets_list()

    def _delete_asset(self, asset: Asset) -> None:
        confirm = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć zasób '{asset.name}' z biblioteki?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.asset_manager.remove_asset(asset.id)
            self.refresh_categories()
            self.refresh_assets_list()

    def _on_category_context_menu(self, pos: QPoint) -> None:
        item = self.category_tree.itemAt(pos)
        if not item:
            return
        cat_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not cat_path:
            return

        menu = QMenu(self)
        menu.addAction("➕ Nowa podkategoria...", lambda: self._create_subcategory(cat_path))
        menu.addAction("✏️ Zmień nazwę...", lambda: self._rename_category(cat_path))
        menu.addAction("🗑️ Usuń kategorię", lambda: self._delete_category(cat_path))
        menu.exec(self.category_tree.mapToGlobal(pos))

    def _create_category_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "Nowa kategoria", "Nazwa nowej kategorii:")
        if ok and name.strip():
            self.asset_manager.category_tree.add_category_path(name.strip())
            self.refresh_categories()

    def _create_subcategory(self, parent_path: str) -> None:
        name, ok = QInputDialog.getText(self, "Nowa podkategoria", f"Nazwa podkategorii w '{parent_path}':")
        if ok and name.strip():
            full_path = f"{parent_path}/{name.strip()}"
            self.asset_manager.category_tree.add_category_path(full_path)
            self.refresh_categories()

    def _rename_category(self, cat_path: str) -> None:
        current_name = cat_path.split("/")[-1]
        new_name, ok = QInputDialog.getText(
            self,
            "Zmień nazwę kategorii",
            "Nowa nazwa:",
            text=current_name,
        )
        if ok and new_name.strip() and new_name.strip() != current_name:
            self.asset_manager.category_tree.rename_category(cat_path, new_name.strip())
            self.refresh_categories()
            self.refresh_assets_list()

    def _delete_category(self, cat_path: str) -> None:
        confirm = QMessageBox.question(
            self,
            "Usuń kategorię",
            f"Czy na pewno chcesz usunąć kategorię '{cat_path}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.asset_manager.category_tree.delete_category(cat_path)
            self.refresh_categories()
            self.refresh_assets_list()

    def _import_files_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Importuj grafiki PNG",
            "",
            "Grafiki (*.png *.jpg *.jpeg *.bmp *.webp);;Wszystkie pliki (*.*)",
        )
        if files:
            target_cat = self.selected_category_path or "Custom"
            res = self.asset_manager.import_multiple_files(files, target_category_path=target_cat)
            msg = f"Zaimportowano: {res['imported_count']} grafik."
            if res['duplicates_count'] > 0:
                msg += f"\nPominięto duplikatów: {res['duplicates_count']}."
            QMessageBox.information(self, "Podsumowanie importu", msg)
            self.refresh_categories()
            self.refresh_assets_list()

    def _import_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder do zaimportowania")
        if folder:
            res = self.asset_manager.import_folder(folder, skip_duplicates=True)
            msg = f"Zaimportowano: {res['imported_count']} grafik z podfolderów."
            if res['duplicates_count'] > 0:
                msg += f"\nPominięto duplikatów: {res['duplicates_count']}."
            if res['errors']:
                msg += f"\nBłędy: {len(res['errors'])}"
            QMessageBox.information(self, "Podsumowanie importu folderu", msg)
            self.refresh_categories()
            self.refresh_assets_list()
