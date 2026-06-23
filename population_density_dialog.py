# -*- coding: utf-8 -*-
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
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
    QMessageBox
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
    def __init__(self, parent=None, lyr_aga=None, lyr_grb=None, current_params=None):
        super(PopulationDensityDialog, self).__init__(parent)
        self.resize(720, 500)
        self.setModal(True)
        self.lyr_aga = lyr_aga
        self.lyr_grb = lyr_grb
        self.params = current_params if current_params is not None else {}
        self.active_tasks = set()
        
        # Determine which layers are active and contain valid features
        self.aa_active = self._is_layer_active(self.lyr_aga)
        self.grb_active = self._is_layer_active(self.lyr_grb)

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
        
        # Side-by-Side Area & Results Display
        sections_layout = QHBoxLayout()
        
        # Card 1: AA (Adjacent Ground Area)
        self.aa_group = QGroupBox(self.tr("grp_aa_details", "Adjacent Ground Area (AA) Eigenschaften"))
        aa_card_layout = QFormLayout(self.aa_group)
        aa_card_layout.setSpacing(8)
        
        self.lbl_aa_area = QLabel("---")
        self.lbl_aa_area.setStyleSheet("font-weight: bold; color: #1e293b;")
        aa_card_layout.addRow(self.tr("label_aa_area", "AA-Fläche:"), self.lbl_aa_area)
        
        self.lbl_aa_total_pop = QLabel("---")
        self.lbl_aa_total_pop.setStyleSheet("font-weight: bold; color: #0f172a;")
        aa_card_layout.addRow(self.tr("label_total_pop", "Gesamtbevölkerung:"), self.lbl_aa_total_pop)
        
        self.lbl_aa_avg_density = QLabel("---")
        self.lbl_aa_avg_density.setStyleSheet("font-weight: bold; color: #0f172a;")
        aa_card_layout.addRow(self.tr("label_avg_density", "Durchschnittliche Dichte:"), self.lbl_aa_avg_density)
        
        sections_layout.addWidget(self.aa_group, 1)
        
        # Card 2: GRB (Ground Risk Buffer)
        self.grb_group = QGroupBox(self.tr("grp_grb_details", "Ground Risk Buffer (GRB) Eigenschaften"))
        grb_card_layout = QFormLayout(self.grb_group)
        grb_card_layout.setSpacing(8)
        
        self.lbl_grb_area = QLabel("---")
        self.lbl_grb_area.setStyleSheet("font-weight: bold; color: #1e293b;")
        grb_card_layout.addRow(self.tr("label_grb_area", "GRB-Gesamtfläche:"), self.lbl_grb_area)
        
        self.lbl_grb_total_pop = QLabel("---")
        self.lbl_grb_total_pop.setStyleSheet("font-weight: bold; color: #0f172a;")
        grb_card_layout.addRow(self.tr("label_total_pop_grb", "Gesamtbevölkerung:"), self.lbl_grb_total_pop)
        
        self.lbl_grb_avg_density = QLabel("---")
        self.lbl_grb_avg_density.setStyleSheet("font-weight: bold; color: #1e293b;")
        grb_card_layout.addRow(self.tr("label_avg_density_grb", "Durchschnittliche Dichte:"), self.lbl_grb_avg_density)

        self.lbl_grb_max_density = QLabel("---")
        self.lbl_grb_max_density.setStyleSheet("font-weight: bold; color: #0f172a;")
        grb_card_layout.addRow(self.tr("label_max_density_grb", "Maximale Dichte:"), self.lbl_grb_max_density)
        
        sections_layout.addWidget(self.grb_group, 1)
        
        layout.addLayout(sections_layout)
        
        # Manage enabling/disabling states based on whether vectors exist
        if not self.aa_active:
            self.aa_group.setEnabled(False)
            self.lbl_aa_area.setText(self.tr("empty_aa_geometry", "AA-Geometrie leer / nicht geladen"))
            
        if not self.grb_active:
            self.grb_group.setEnabled(False)
            self.lbl_grb_area.setText(self.tr("empty_grb_geometry", "GRB-Geometrie leer / nicht geladen"))
            
        # Calculation Action Button
        self.btn_calculate = QPushButton(self.tr("btn_calculate_pop", "Berechnung starten"))
        self.btn_calculate.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 8px; border-radius: 4px; font-size: 13px;")
        self.btn_calculate.clicked.connect(self.calculate_density)
        layout.addWidget(self.btn_calculate)
        
        if not self.aa_active and not self.grb_active:
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
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
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
            if self.aa_active or self.grb_active:
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
        
        if self.aa_active:
            total_area_m2 = 0.0
            for feature in self.lyr_aga.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    total_area_m2 += da.measureArea(feature.geometry())
            total_area_km2 = total_area_m2 / 1000000.0
            self.lbl_aa_area.setText(f"{total_area_km2:.3f} km²")
            
        if self.grb_active:
            total_area_m2 = 0.0
            for feature in self.lyr_grb.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    total_area_m2 += da.measureArea(feature.geometry())
            total_area_km2 = total_area_m2 / 1000000.0
            self.lbl_grb_area.setText(f"{total_area_km2:.3f} km²")

    def check_and_restore_ui(self):
        """Restores cursor and calculation button once all active tasks are completed or failed."""
        if not self.active_tasks:
            self.setCursor(Qt.ArrowCursor)
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
        self.setCursor(Qt.WaitCursor)
        
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

        # ----------------------------------------------------
        # 1. AA Zonal Statistics
        # ----------------------------------------------------
        if self.aa_active:
            self.active_tasks.add("AA")
            self.lbl_aa_total_pop.setText("...")
            self.lbl_aa_avg_density.setText("...")
            
            def on_aa_completed(total_area_km2, cell_area_km2, results):
                try:
                    total_population = sum(r[0] for r in results)
                    self.lbl_aa_total_pop.setText(f"{total_population:,.0f} {self.tr('people', 'Personen')}")
                    
                    density = total_population / total_area_km2 if total_area_km2 > 0 else 0.0
                    self.lbl_aa_avg_density.setText(f"{density:.2f} {self.tr('people_per_km2', 'Einwohner / km²')}")
                    
                    if self.params is not None:
                        self.params["aa_area_km2"] = total_area_km2
                        self.params["aa_population"] = total_population
                        self.params["aa_density"] = density
                finally:
                    self.active_tasks.discard("AA")
                    self.check_and_restore_ui()

            def on_aa_failed(error_msg):
                try:
                    QMessageBox.critical(
                        self,
                        self.tr("error_calc_failed_title", "Fehler bei Berechnung") + " (AA)",
                        self.tr("error_calc_failed_text", "Zonalstatistik-Berechnung fehlgeschlagen:\n{error}").format(error=error_msg)
                    )
                finally:
                    self.active_tasks.discard("AA")
                    self.check_and_restore_ui()

            def on_aa_terminated():
                try:
                    QMessageBox.warning(
                        self,
                        self.tr("error_calc_terminated_title", "Berechnung abgebrochen") + " (AA)",
                        self.tr("error_calc_terminated_text", "Die Zonalstatistik-Berechnung wurde abgebrochen.")
                    )
                finally:
                    self.active_tasks.discard("AA")
                    self.check_and_restore_ui()

            calc_aa = ZonalStatsCalculator(self.lyr_aga, raster_layer, "pop_", stat_sum | stat_count, parent=self)
            calc_aa.calculate_async(on_aa_completed, on_aa_failed, on_aa_terminated)

        # ----------------------------------------------------
        # 2. GRB Zonal Statistics
        # ----------------------------------------------------
        if self.grb_active:
            self.active_tasks.add("GRB")
            self.lbl_grb_total_pop.setText("...")
            self.lbl_grb_avg_density.setText("...")
            self.lbl_grb_max_density.setText("...")
            
            def on_grb_completed(total_area_km2, cell_area_km2, results):
                try:
                    total_population = sum(r[0] for r in results)
                    max_pixel_val = max(r[2] for r in results) if results else 0.0
                    
                    self.lbl_grb_total_pop.setText(f"{total_population:,.1f} {self.tr('people', 'Personen')}")
                    
                    avg_density = total_population / total_area_km2 if total_area_km2 > 0 else 0.0
                    self.lbl_grb_avg_density.setText(f"{avg_density:.2f} {self.tr('people_per_km2', 'Einwohner / km²')}")
                    
                    max_density = max_pixel_val / cell_area_km2 if cell_area_km2 > 0 else 0.0
                    self.lbl_grb_max_density.setText(
                        f"{max_density:.2f} {self.tr('people_per_km2', 'Einwohner / km²')} "
                        f"({self.tr('raw_value', 'Rohwert')}: {max_pixel_val:.6f} {self.tr('people_per_cell', 'Personen/Zelle')})"
                    )
                    
                    if self.params is not None:
                        self.params["grb_area_km2"] = total_area_km2
                        self.params["grb_population"] = total_population
                        self.params["grb_avg_density"] = avg_density
                        self.params["grb_max_density"] = max_density
                        self.params["grb_max_raw_value"] = max_pixel_val
                finally:
                    self.active_tasks.discard("GRB")
                    self.check_and_restore_ui()

            def on_grb_failed(error_msg):
                try:
                    QMessageBox.critical(
                        self,
                        self.tr("error_calc_failed_title", "Fehler bei Berechnung") + " (GRB)",
                        self.tr("error_calc_failed_text", "Zonalstatistik-Berechnung fehlgeschlagen:\n{error}").format(error=error_msg)
                    )
                finally:
                    self.active_tasks.discard("GRB")
                    self.check_and_restore_ui()

            def on_grb_terminated():
                try:
                    QMessageBox.warning(
                        self,
                        self.tr("error_calc_terminated_title", "Berechnung abgebrochen") + " (GRB)",
                        self.tr("error_calc_terminated_text", "Die Zonalstatistik-Berechnung wurde abgebrochen.")
                    )
                finally:
                    self.active_tasks.discard("GRB")
                    self.check_and_restore_ui()

            calc_grb = ZonalStatsCalculator(self.lyr_grb, raster_layer, "grb_", stat_sum | stat_count | stat_max, parent=self)
            calc_grb.calculate_async(on_grb_completed, on_grb_failed, on_grb_terminated)
