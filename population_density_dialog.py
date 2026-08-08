# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView
)
from qgis.core import (
    QgsProject,
    QgsMapLayerType,
    QgsRasterLayer,
    QgsDistanceArea,
    QgsCoordinateReferenceSystem
)

from .config_manager import ConfigManager
from .translation_manager import TranslationManager
from .zonal_stats_calculator import ZonalStatsCalculator

class PopulationDensityDialog(QDialog):
    def __init__(self, parent=None, lyr_aga=None, lyr_grb=None, lyr_cv=None, lyr_fg=None, current_params=None):
        super(PopulationDensityDialog, self).__init__(parent)
        self.resize(750, 580)
        self.setModal(True)
        self.lyr_aga = lyr_aga
        self.lyr_grb = lyr_grb
        self.lyr_cv = lyr_cv
        self.lyr_fg = lyr_fg
        self.params = current_params if current_params is not None else {}
        self.active_tasks = set()
        self.calculators = []
        
        # Determine which layers are active and contain valid features
        self.aa_active = self._is_layer_active(self.lyr_aga)
        self.grb_active = self._is_layer_active(self.lyr_grb)
        self.cv_active = self._is_layer_active(self.lyr_cv)
        self.fg_active = self._is_layer_active(self.lyr_fg)

        self.setWindowTitle(self.tr("dialog_pop_title", "Bevölkerungsdichte- & Bodenrisiko-Analyse (AA / GRB)"))
        self.init_ui()
        self.populate_raster_layers()
        self.update_areas_display()

    def tr(self, key, default=""):
        lang = ConfigManager.get_param(self.params, "language")
        return TranslationManager.tr(key, lang, default)

    def _is_layer_active(self, layer):
        if not layer or not layer.isValid():
            return False
        has_features = False
        for feature in layer.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                has_features = True
                break
        return has_features

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Description Header
        info_label = QLabel(
            self.tr("pop_desc_combined", 
                    "Berechnung der durchschnittlichen und maximalen Bevölkerungsdichte im Adjacent Area (AA) "
                    "und Ground Risk Buffer (GRB) basierend auf GHS-POP Daten gemäss SORA Step #8.")
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #444; margin-bottom: 5px; font-style: italic;")
        layout.addWidget(info_label)
        
        # Group 1: Inputs (Shared)
        input_group = QGroupBox(self.tr("group_inputs", "Datenquellen & Einstellungen"))
        form_layout = QFormLayout(input_group)
        form_layout.setSpacing(10)
        
        # Raster combo with Browse button
        raster_layout = QHBoxLayout()
        self.cmb_raster_layers = QComboBox()
        self.cmb_raster_layers.currentIndexChanged.connect(self.on_raster_changed)
        raster_layout.addWidget(self.cmb_raster_layers, 1)
        
        self.btn_browse = QPushButton(self.tr("btn_browse", "Durchsuchen..."))
        self.btn_browse.clicked.connect(self.browse_raster_file)
        raster_layout.addWidget(self.btn_browse)
        
        form_layout.addRow(self.tr("label_raster_layer", "GHS-POP Raster-Layer:"), raster_layout)
        
        # Raster Info Display
        self.lbl_raster_info = QLabel(self.tr("no_raster_selected", "Kein Raster ausgewählt"))
        self.lbl_raster_info.setWordWrap(True)
        self.lbl_raster_info.setStyleSheet("color: #555; font-size: 11px; background-color: #f1f5f9; padding: 6px; border-radius: 4px;")
        form_layout.addRow(self.tr("label_raster_info", "Raster Info:"), self.lbl_raster_info)
        
        layout.addWidget(input_group)
        
        # Results Table
        self.results_group = QGroupBox(self.tr("grp_results", "Ergebnisse: Bevölkerungsdichte"))
        results_layout = QVBoxLayout(self.results_group)
        
        self.table_widget = QTableWidget(4, 5)
        self.table_widget.setHorizontalHeaderLabels([
            self.tr("col_zone", "Zone"),
            self.tr("col_area", "Fläche (km²)"),
            self.tr("col_pop", "Gesamtbevölkerung"),
            self.tr("col_avg_dens", "Ø Dichte (Einw./km²)"),
            self.tr("col_max_dens", "Max. Dichte (Einw./km²)")
        ])
        
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setStyleSheet("QTableWidget { background-color: #ffffff; }")
        self.table_widget.setMinimumHeight(160)
        
        zones = [
            self.tr("zone_aa", "Adjacent Area (AA)"), 
            self.tr("zone_grb", "Ground Risk Buffer (GRB)"), 
            self.tr("zone_cv", "Contingency Volume (CV)"), 
            self.tr("zone_fg", "Flight Geography (FG)")
        ]
        
        for row, zone_name in enumerate(zones):
            item_zone = QTableWidgetItem(zone_name)
            item_zone.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.table_widget.setItem(row, 0, item_zone)
            for col in range(1, 5):
                item = QTableWidgetItem("---")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_widget.setItem(row, col, item)
                
        results_layout.addWidget(self.table_widget)
        layout.addWidget(self.results_group)
        
        # Calculation Action Button
        self.btn_calculate = QPushButton(self.tr("btn_calculate_pop", "Berechnung starten"))
        self.btn_calculate.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 8px; border-radius: 4px; font-size: 13px;")
        self.btn_calculate.clicked.connect(self.calculate_density)
        layout.addWidget(self.btn_calculate)
        
        if not self.aa_active and not self.grb_active and not self.cv_active and not self.fg_active:
            self.btn_calculate.setEnabled(False)
            self.btn_calculate.setText(self.tr("no_active_layers_warn", "Keine gültigen Planungsdaten geladen"))
        
        # SORA & EASA Dynamic Combined Note Box
        self.lbl_combined_note = QLabel()
        self.lbl_combined_note.setWordWrap(True)
        self.lbl_combined_note.setStyleSheet("color: #475569; background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; font-size: 11px; line-height: 1.4;")
        
        note_text_de = (
            "<b>SORA & EASA Bewertungshinweise:</b><br>"
            "• <b>SORA Step #8 (AA):</b> Die durchschnittliche Dichte im Adjacent Area dient zur Einstufung der "
            "Containment-Anforderungen (z.B. Enhanced Containment bei Dichten > 25/km²).<br>"
            "• <b>Bodenrisiko (GRB):</b> Für den Maximalwert wird ein konservativer EASA-Ansatz gewählt. "
            "Jede Rasterzelle, die das GRB-Polygon auch nur schneidet, wird voll berücksichtigt."
        )
        note_text_en = (
            "<b>SORA & EASA Assessment Notes:</b><br>"
            "• <b>SORA Step #8 (AA):</b> The average density in the Adjacent Area is used to classify containment "
            "requirements (e.g., Enhanced Containment for densities > 25/km²).<br>"
            "• <b>Ground Risk (GRB):</b> A conservative EASA approach is selected for the maximum value. "
            "Any raster cell intersecting the GRB polygon is fully included."
        )
        self.lbl_combined_note.setText(note_text_en if ConfigManager.get_param(self.params, "language") == "en" else note_text_de)
        layout.addWidget(self.lbl_combined_note)
        
        # Bottom Close Button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_raster_layers(self):
        self.cmb_raster_layers.blockSignals(True)
        self.cmb_raster_layers.clear()
        
        raster_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayerType.RasterLayer:
                raster_layers.append(layer)
                
        if not raster_layers:
            self.cmb_raster_layers.addItem(self.tr("no_rasters_in_project", "Keine Raster-Layer im Projekt geladen"), None)
            self.lbl_raster_info.setText(self.tr("no_raster_selected", "Kein Raster ausgewählt"))
            self.btn_calculate.setEnabled(False)
        else:
            # Enable calculate button if we have raster and at least one active vector layer
            if self.aa_active or self.grb_active or self.cv_active or self.fg_active:
                self.btn_calculate.setEnabled(True)
            for layer in raster_layers:
                self.cmb_raster_layers.addItem(layer.name(), layer.id())
                
        self.cmb_raster_layers.blockSignals(False)
        self.on_raster_changed()

    def browse_raster_file(self):
        from qgis.core import QgsSettings
        settings = QgsSettings()
        last_dir = settings.value("/QUCORE/last_import_dir", "")

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("dialog_select_raster", "GHS-POP GeoTIFF-Datei auswählen"),
            last_dir,
            "GeoTIFF (*.tif *.tiff);;All Files (*.*)"
        )
        if not file_path:
            return

        settings.setValue("/QUCORE/last_import_dir", os.path.dirname(file_path))
            
        base_name = os.path.basename(file_path)
        raster_layer = QgsRasterLayer(file_path, base_name)
        if not raster_layer.isValid():
            QMessageBox.critical(
                self,
                self.tr("error_invalid_raster_title", "Ungültiges Raster"),
                self.tr("error_invalid_raster_text", "Die ausgewählte Datei konnte nicht als Raster-Layer geladen werden.")
            )
            return
            
        QgsProject.instance().addMapLayer(raster_layer)
        self.populate_raster_layers()
        idx = self.cmb_raster_layers.findData(raster_layer.id())
        if idx != -1:
            self.cmb_raster_layers.setCurrentIndex(idx)

    def on_raster_changed(self):
        layer_id = self.cmb_raster_layers.currentData()
        if not layer_id:
            download_url = "https://ghsl.jrc.ec.europa.eu/download.php?ds=pop"
            msg = (
                f"<span style='color: #b91c1c; font-weight: bold;'>{self.tr('no_raster_loaded_warn', 'Achtung: Kein Bevölkerungsraster geladen!')}</span><br>"
                f"{self.tr('download_hint', 'Für die SORA-Analyse wird das offizielle GHS-POP GeoTIFF-Raster benötigt.')}<br><br>"
                f"<b>{self.tr('download_link_label', 'Hier kostenfrei herunterladen:')}</b><br>"
                f"<a href='{download_url}' style='color: #2563eb; text-decoration: underline;'>ghsl.jrc.ec.europa.eu (GHS-POP Download)</a><br><br>"
                f"<span style='font-style: italic; color: #475569;'>{self.tr('download_tip', 'Tipp: Wählen Sie die 100m-Auflösung (WGS84) für optimale Ergebnisse.')}</span>"
            )
            self.lbl_raster_info.setText(msg)
            self.lbl_raster_info.setOpenExternalLinks(True)
            self.btn_calculate.setEnabled(False)
            return
            
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer or not layer.isValid():
            self.lbl_raster_info.setText(self.tr("error_invalid_raster_text", "Raster-Layer ist ungültig"))
            return
            
        crs_name = layer.crs().authid()
        res_x = layer.rasterUnitsPerPixelX()
        res_y = layer.rasterUnitsPerPixelY()
        extent = layer.extent()
        
        info_text = (
            f"<b>CRS:</b> {crs_name}<br>"
            f"<b>Resolution:</b> {res_x:.2f} x {res_y:.2f} m/px<br>"
            f"<b>Extent:</b> X: [{extent.xMinimum():.1f}, {extent.xMaximum():.1f}], "
            f"Y: [{extent.yMinimum():.1f}, {extent.yMaximum():.1f}]"
        )
        self.lbl_raster_info.setText(info_text)
        if self.aa_active or self.grb_active:
            self.btn_calculate.setEnabled(True)

    def update_areas_display(self):
        da = QgsDistanceArea()
        da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")
        
        layers_info = [
            (0, self.aa_active, self.lyr_aga),
            (1, self.grb_active, self.lyr_grb),
            (2, self.cv_active, self.lyr_cv),
            (3, self.fg_active, self.lyr_fg)
        ]
        
        for row, is_active, layer in layers_info:
            if is_active and layer:
                total_area_m2 = 0.0
                for feature in layer.getFeatures():
                    if feature.hasGeometry() and not feature.geometry().isEmpty():
                        total_area_m2 += da.measureArea(feature.geometry())
                total_area_km2 = total_area_m2 / 1000000.0
                self.set_table_item(row, 1, f"{total_area_km2:.3f}")
            else:
                self.set_table_item(row, 1, self.tr("empty_geom", "N/A"))

    def check_and_restore_ui(self):
        """Restores cursor and calculation button once all active tasks are completed or failed."""
        if not self.active_tasks:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.btn_calculate.setEnabled(True)
            self.btn_calculate.setText(self.tr("btn_calculate_pop", "Berechnung starten"))

    def calculate_density(self):
        layer_id = self.cmb_raster_layers.currentData()
        if not layer_id:
            QMessageBox.warning(
                self,
                self.tr("msg_no_raster_title", "Kein Raster"),
                self.tr("msg_no_raster_text", "Bitte wählen Sie zuerst einen gültigen GHS-POP Raster-Layer aus.")
            )
            return
            
        raster_layer = QgsProject.instance().mapLayer(layer_id)
        if not raster_layer or not raster_layer.isValid():
            QMessageBox.warning(
                self,
                self.tr("error_invalid_raster_title", "Ungültiges Raster"),
                self.tr("error_invalid_raster_text", "Der ausgewählte Raster-Layer ist ungültig oder nicht geladen.")
            )
            return
            
        # Store raster metadata in self.params for Word export
        if self.params is not None:
            self.params["pop_raster_name"] = raster_layer.name()
            self.params["pop_raster_crs"] = raster_layer.crs().authid()
            res_x = raster_layer.rasterUnitsPerPixelX()
            res_y = raster_layer.rasterUnitsPerPixelY()
            self.params["pop_raster_res"] = f"{res_x:.2f} x {res_y:.2f} m/px"
            
        self.active_tasks.clear()
        self.btn_calculate.setEnabled(False)
        self.btn_calculate.setText(self.tr("btn_calculating", "Berechnung läuft..."))
        self.setCursor(Qt.CursorShape.WaitCursor)
        
        # Determine stats enum constants based on QGIS version API
        try:
            from qgis.core import Qgis
            stat_sum = Qgis.ZonalStatistic.Sum
            stat_count = Qgis.ZonalStatistic.Count
            stat_max = Qgis.ZonalStatistic.Max
        except ImportError:
            stat_sum = QgsZonalStatistics.Sum
            stat_count = QgsZonalStatistics.Count
            stat_max = QgsZonalStatistics.Max

        def create_task(zone_id, row, layer, is_active, prefix, stat_flags):
            if not is_active:
                return
                
            self.active_tasks.add(zone_id)
            self.set_table_item(row, 2, "...")
            self.set_table_item(row, 3, "...")
            self.set_table_item(row, 4, "...")
            
            def on_completed(total_area_km2, cell_area_km2, results):
                try:
                    total_population = sum(r[0] for r in results)
                    max_pixel_val = max(r[2] for r in results) if results and len(results[0]) > 2 else 0.0
                    
                    self.set_table_item(row, 2, f"{total_population:,.0f}")
                    
                    avg_density = total_population / total_area_km2 if total_area_km2 > 0 else 0.0
                    self.set_table_item(row, 3, f"{avg_density:.2f}")
                    
                    if stat_flags & stat_max:
                        max_density = max_pixel_val / cell_area_km2 if cell_area_km2 > 0 else 0.0
                        self.set_table_item(row, 4, f"{max_density:.2f}")
                    else:
                        max_density = 0.0
                        self.set_table_item(row, 4, "N/A")
                    
                    if self.params is not None:
                        lower_id = zone_id.lower()
                        self.params[f"{lower_id}_area_km2"] = total_area_km2
                        self.params[f"{lower_id}_population"] = total_population
                        self.params[f"{lower_id}_avg_density"] = avg_density
                        if stat_flags & stat_max:
                            self.params[f"{lower_id}_max_density"] = max_density
                            self.params[f"{lower_id}_max_raw_value"] = max_pixel_val
                            
                    self.active_tasks.discard(zone_id)
                    self.check_and_restore_ui()
                except RuntimeError:
                    pass

            def on_failed(error_msg):
                try:
                    QMessageBox.critical(
                        self,
                        self.tr("error_calc_failed_title", "Fehler bei Berechnung") + f" ({zone_id})",
                        self.tr("error_calc_failed_text", "Zonalstatistik-Berechnung fehlgeschlagen:\n{error}").format(error=error_msg)
                    )
                    self.active_tasks.discard(zone_id)
                    self.check_and_restore_ui()
                except RuntimeError:
                    pass

            def on_terminated():
                try:
                    QMessageBox.warning(
                        self,
                        self.tr("error_calc_terminated_title", "Berechnung abgebrochen") + f" ({zone_id})",
                        self.tr("error_calc_terminated_text", "Die Zonalstatistik-Berechnung wurde abgebrochen.")
                    )
                    self.active_tasks.discard(zone_id)
                    self.check_and_restore_ui()
                except RuntimeError:
                    pass

            calc = ZonalStatsCalculator(layer, raster_layer, prefix, stat_flags, parent=self)
            self.calculators.append(calc)
            calc.calculate_async(on_completed, on_failed, on_terminated)

        # Start all tasks
        create_task("AA", 0, self.lyr_aga, self.aa_active, "pop_", stat_sum | stat_count)
        create_task("GRB", 1, self.lyr_grb, self.grb_active, "grb_", stat_sum | stat_count | stat_max)
        create_task("CV", 2, self.lyr_cv, self.cv_active, "cv_", stat_sum | stat_count | stat_max)
        create_task("FG", 3, self.lyr_fg, self.fg_active, "fg_", stat_sum | stat_count | stat_max)

    def set_table_item(self, row, col, txt):
        item = self.table_widget.item(row, col)
        if item:
            item.setText(str(txt))

    def closeEvent(self, event):
        for calc in getattr(self, 'calculators', []):
            try:
                calc.cancel()
            except Exception:
                pass
        super(PopulationDensityDialog, self).closeEvent(event)
