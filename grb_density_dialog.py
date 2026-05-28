# -*- coding: utf-8 -*-
import os
import json
from PyQt5.QtCore import Qt, QVariant
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
    QgsCoordinateReferenceSystem,
    QgsGeometry,
    QgsRectangle,
    NULL
)
from qgis.analysis import QgsZonalStatistics

class GrbDensityDialog(QDialog):
    def __init__(self, parent=None, lyr_grb=None, current_params=None):
        super(GrbDensityDialog, self).__init__(parent)
        self.resize(520, 520)
        self.setModal(True)
        self.lyr_grb = lyr_grb
        self.params = current_params if current_params is not None else {}
        
        # Load translations
        self.tr_strings = {}
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        tr_path = os.path.join(plugin_dir, "translations.json")
        if os.path.exists(tr_path):
            try:
                with open(tr_path, 'r', encoding='utf-8') as f:
                    self.tr_strings = json.load(f)
            except Exception:
                pass
                
        self.setWindowTitle(self.tr("dialog_grb_pop_title", "Bodenrisiko-Analyse (GRB-Bevölkerungsdichte)"))
        self.init_ui()
        self.populate_raster_layers()
        self.update_grb_area_display()

    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return self.tr_strings.get(key, {}).get(lang, default)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Description Header
        info_label = QLabel(
            self.tr("grb_pop_desc", 
                    "Berechnung der durchschnittlichen und maximalen Bevölkerungsdichte innerhalb des "
                    "Ground Risk Buffers (GRB) basierend auf dem GHS-POP GeoTIFF gemäß EASA SORA-Vorgaben.")
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #444; margin-bottom: 5px; font-style: italic;")
        layout.addWidget(info_label)
        
        # Group 1: Inputs
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
        
        # Group 2: GRB Properties
        grb_group = QGroupBox(self.tr("grp_grb_details", "Ground Risk Buffer (GRB) Eigenschaften"))
        grb_layout = QFormLayout(grb_group)
        grb_layout.setSpacing(8)
        
        self.lbl_grb_area = QLabel("---")
        self.lbl_grb_area.setStyleSheet("font-weight: bold; color: #1e293b;")
        grb_layout.addRow(self.tr("label_grb_area", "GRB-Gesamtfläche:"), self.lbl_grb_area)
        
        layout.addWidget(grb_group)
        
        # Group 3: Calculation & Results
        results_group = QGroupBox(self.tr("group_results", "Berechnete Ergebnisse"))
        res_layout = QFormLayout(results_group)
        res_layout.setSpacing(10)
        
        self.btn_calculate = QPushButton(self.tr("btn_calculate_pop", "Berechnung starten"))
        self.btn_calculate.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_calculate.clicked.connect(self.calculate_density)
        res_layout.addRow("", self.btn_calculate)
        
        self.lbl_total_pop = QLabel("---")
        self.lbl_total_pop.setStyleSheet("font-weight: bold; color: #0f172a;")
        res_layout.addRow(self.tr("label_total_pop_grb", "Gesamtbevölkerung im GRB:"), self.lbl_total_pop)
        
        self.lbl_avg_density = QLabel("---")
        self.lbl_avg_density.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e293b;")
        res_layout.addRow(self.tr("label_avg_density_grb", "Durchschnittliche Bevölkerungsdichte:"), self.lbl_avg_density)

        self.lbl_max_density = QLabel("---")
        self.lbl_max_density.setStyleSheet("font-weight: bold; font-size: 16px; color: #e11d48;")
        res_layout.addRow(self.tr("label_max_density_grb", "Maximale Bevölkerungsdichte (konservativ):"), self.lbl_max_density)
        
        layout.addWidget(results_group)
        
        # EASA Conservative Note Box
        self.lbl_easa_note = QLabel(
            self.tr("easa_grb_info", 
                    "<b>EASA SORA Hinweis (Konservativer Ansatz):</b> Für den Maximalwert der Bevölkerungsdichte im "
                    "GRB wird ein konservativer Ansatz gewählt. Jede Rasterzelle, die das GRB-Polygon auch nur berührt, "
                    "wird voll berücksichtigt, um das maximale Bodenrisiko sicherzustellen.")
        )
        self.lbl_easa_note.setWordWrap(True)
        self.lbl_easa_note.setStyleSheet("color: #9f1239; background-color: #fff1f2; border: 1px solid #fecdd3; padding: 10px; border-radius: 6px; font-size: 11px; line-height: 1.4;")
        layout.addWidget(self.lbl_easa_note)
        
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
            self.lbl_raster_info.setText(self.tr("no_raster_selected", "Kein Raster ausgewählt"))
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

    def update_grb_area_display(self):
        if not self.lyr_grb:
            self.lbl_grb_area.setText("---")
            return
            
        da = QgsDistanceArea()
        da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")
        
        total_area_m2 = 0.0
        feature_count = 0
        for feature in self.lyr_grb.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                total_area_m2 += da.measureArea(feature.geometry())
                feature_count += 1
                
        if feature_count == 0:
            self.lbl_grb_area.setText(self.tr("empty_grb_geometry", "GRB-Geometrie ist leer"))
            self.btn_calculate.setEnabled(False)
            return
            
        total_area_km2 = total_area_m2 / 1000000.0
        self.lbl_grb_area.setText(f"{total_area_km2:.3f} km²")
        self.btn_calculate.setEnabled(True)

    def get_raster_cell_area_km2(self, raster_layer):
        extent = raster_layer.extent()
        cx = extent.center().x()
        cy = extent.center().y()
        
        res_x = raster_layer.rasterUnitsPerPixelX()
        res_y = raster_layer.rasterUnitsPerPixelY()
        
        rect = QgsRectangle(cx, cy, cx + res_x, cy + res_y)
        
        da = QgsDistanceArea()
        da.setSourceCrs(raster_layer.crs(), QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")
        
        geom = QgsGeometry.fromRect(rect)
        area_m2 = da.measureArea(geom)
        
        return area_m2 / 1000000.0

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
            
        da = QgsDistanceArea()
        da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")
        
        total_area_m2 = 0.0
        for feature in self.lyr_grb.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                total_area_m2 += da.measureArea(feature.geometry())
                
        total_area_km2 = total_area_m2 / 1000000.0
        if total_area_km2 <= 0.0:
            QMessageBox.warning(
                self,
                self.tr("error_empty_grb_title", "Berechnungsfehler"),
                self.tr("error_empty_grb_text", "Der Ground Risk Buffer (GRB) besitzt keine gültige Fläche.")
            )
            return
            
        try:
            from qgis.core import Qgis
            stat_sum = Qgis.ZonalStatistic.Sum
            stat_count = Qgis.ZonalStatistic.Count
            stat_max = Qgis.ZonalStatistic.Max
        except ImportError:
            stat_sum = QgsZonalStatistics.Sum
            stat_count = QgsZonalStatistics.Count
            stat_max = QgsZonalStatistics.Max
            
        prefix = "grb_"
        
        zonal_stats = QgsZonalStatistics(
            self.lyr_grb,
            raster_layer,
            prefix,
            1,
            stat_sum | stat_count | stat_max
        )
        
        self.setCursor(Qt.WaitCursor)
        self.btn_calculate.setEnabled(False)
        
        try:
            result = zonal_stats.calculateStatistics(None)
            
            total_population = 0.0
            max_pixel_val = 0.0
            pixel_count = 0
            
            for feature in self.lyr_grb.getFeatures():
                pop_sum = feature["grb_sum"]
                pop_count = feature["grb_count"]
                pop_max = feature["grb_max"]
                
                if pop_sum != NULL and pop_sum is not None:
                    total_population += float(pop_sum)
                if pop_count != NULL and pop_count is not None:
                    pixel_count += int(pop_count)
                if pop_max != NULL and pop_max is not None:
                    if float(pop_max) > max_pixel_val:
                        max_pixel_val = float(pop_max)
                        
            # Clean up added columns
            dp = self.lyr_grb.dataProvider()
            fields = self.lyr_grb.fields()
            sum_idx = fields.indexOf("grb_sum")
            count_idx = fields.indexOf("grb_count")
            max_idx = fields.indexOf("grb_max")
            
            fields_to_delete = []
            if sum_idx != -1:
                fields_to_delete.append(sum_idx)
            if count_idx != -1:
                fields_to_delete.append(count_idx)
            if max_idx != -1:
                fields_to_delete.append(max_idx)
                
            if fields_to_delete:
                self.lyr_grb.startEditing()
                dp.deleteAttributes(fields_to_delete)
                self.lyr_grb.commitChanges()
                self.lyr_grb.updateFields()
                
            # Display results
            self.lbl_total_pop.setText(f"{total_population:,.1f} {self.tr('people', 'Personen')}")
            
            avg_density = total_population / total_area_km2
            self.lbl_avg_density.setText(f"{avg_density:.2f} {self.tr('people_per_km2', 'Einwohner / km²')}")
            
            # Calculate maximum cell density (conservative approach)
            cell_area_km2 = self.get_raster_cell_area_km2(raster_layer)
            if cell_area_km2 > 0.0:
                max_density = max_pixel_val / cell_area_km2
            else:
                max_density = 0.0
            self.lbl_max_density.setText(f"{max_density:.2f} {self.tr('people_per_km2', 'Einwohner / km²')} ({self.tr('raw_value', 'Rohwert')}: {max_pixel_val:.6f} {self.tr('people_per_cell', 'Personen/Zelle')})")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("error_calc_failed_title", "Fehler bei Berechnung"),
                self.tr("error_calc_failed_text", "Zonalstatistik-Berechnung fehlgeschlagen:\n{error}").format(error=str(e))
            )
        finally:
            self.setCursor(Qt.ArrowCursor)
            self.btn_calculate.setEnabled(True)
