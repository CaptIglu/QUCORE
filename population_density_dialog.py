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
    NULL
)
from qgis.analysis import QgsZonalStatistics

class PopulationDensityDialog(QDialog):
    def __init__(self, parent=None, lyr_aga=None, current_params=None):
        super(PopulationDensityDialog, self).__init__(parent)
        self.resize(520, 480)
        self.setModal(True)
        self.lyr_aga = lyr_aga
        self.params = current_params if current_params is not None else {}
        
        # Load translations
        self.tr_strings = {}
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        tr_path = os.path.join(plugin_dir, "translations.json")
        if os.path.exists(tr_path):
            try:
                with open(tr_path, 'r', encoding='utf-8') as f:
                    self.tr_strings = json.load(f)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Fehler beim Laden von translations.json in PopulationDensityDialog: {e}",
                    "QUCORE", Qgis.Warning
                )
                
        self.setWindowTitle(self.tr("dialog_pop_title", "Bevölkerungsdichte im Adjacent Area (AA) Bereich"))
        self.init_ui()
        self.populate_raster_layers()
        self.update_aa_area_display()

    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return self.tr_strings.get(key, {}).get(lang, default)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Description Header
        info_label = QLabel(
            self.tr("pop_desc", 
                    "Berechnung der durchschnittlichen Bevölkerungsdichte innerhalb der Adjacent Ground Area (AA) "
                    "basierend auf dem Global Human Settlement Layer (GHSL) GHS-POP GeoTIFF gemäß SORA Step #8.")
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
        
        # Group 2: AA Properties
        aa_group = QGroupBox(self.tr("grp_aa_details", "Adjacent Ground Area (AA) Eigenschaften"))
        aa_layout = QFormLayout(aa_group)
        aa_layout.setSpacing(8)
        
        self.lbl_aa_area = QLabel("---")
        self.lbl_aa_area.setStyleSheet("font-weight: bold; color: #1e293b;")
        aa_layout.addRow(self.tr("label_aa_area", "AA-Fläche:"), self.lbl_aa_area)
        
        layout.addWidget(aa_group)
        
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
        res_layout.addRow(self.tr("label_total_pop", "Gesamtbevölkerung im AA-Bereich:"), self.lbl_total_pop)
        
        self.lbl_avg_density = QLabel("---")
        self.lbl_avg_density.setStyleSheet("font-weight: bold; font-size: 15px; color: #16a34a;")
        res_layout.addRow(self.tr("label_avg_density", "Durchschnittliche Bevölkerungsdichte:"), self.lbl_avg_density)
        
        layout.addWidget(results_group)
        
        # SORA Step 8 Note Box
        self.lbl_sora_note = QLabel(
            self.tr("sora_containment_info", 
                    "<b>SORA Step #8 Hinweis:</b> Der ermittelte Dichtewert (Einwohner/km²) dient zur Einstufung der "
                    "Containment-Anforderungen (z.B. Enhanced Containment bei Dichten > 25/km² in bestimmten Szenarien). "
                    "Bitte prüfen Sie die Grenzwerte gemäß den EASA-Richtlinien. Assemblies of People "
                    "(Menschenansammlungen) müssen manuell ausgeschlossen werden.")
        )
        self.lbl_sora_note.setWordWrap(True)
        self.lbl_sora_note.setStyleSheet("color: #475569; background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; font-size: 11px; line-height: 1.4;")
        layout.addWidget(self.lbl_sora_note)
        
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
            
        # Add to project so QGIS keeps it loaded and we can perform statistics on it
        QgsProject.instance().addMapLayer(raster_layer)
        
        # Repopulate and select it
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

    def update_aa_area_display(self):
        if not self.lyr_aga:
            self.lbl_aa_area.setText("---")
            return
            
        da = QgsDistanceArea()
        da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")
        
        total_area_m2 = 0.0
        feature_count = 0
        for feature in self.lyr_aga.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                total_area_m2 += da.measureArea(feature.geometry())
                feature_count += 1
                
        if feature_count == 0:
            self.lbl_aa_area.setText(self.tr("empty_aa_geometry", "AA-Geometrie ist leer"))
            self.btn_calculate.setEnabled(False)
            return
            
        total_area_km2 = total_area_m2 / 1000000.0
        self.lbl_aa_area.setText(f"{total_area_km2:.3f} km²")
        self.btn_calculate.setEnabled(True)

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
            
        # 1. Ellipsoidal Area of AA
        da = QgsDistanceArea()
        da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
        da.setEllipsoid("WGS84")
        
        total_area_m2 = 0.0
        for feature in self.lyr_aga.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                total_area_m2 += da.measureArea(feature.geometry())
                
        total_area_km2 = total_area_m2 / 1000000.0
        if total_area_km2 <= 0.0:
            QMessageBox.warning(
                self,
                self.tr("error_empty_aa_title", "Berechnungsfehler"),
                self.tr("error_empty_aa_text", "Die Adjacent Ground Area (AA) besitzt keine gültige Fläche.")
            )
            return
            
        # UI updates: disable calculation button and set wait status
        self.btn_calculate.setEnabled(False)
        self.btn_calculate.setText(self.tr("btn_calculating", "Berechnung läuft..."))
        self.setCursor(Qt.WaitCursor)
        
        raster_path = raster_layer.source()
        raster_name = raster_layer.name()
        
        # Clone geometries as WKT to safely pass to the background thread
        geoms_wkt = []
        for feature in self.lyr_aga.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                geoms_wkt.append(feature.geometry().asWkt())
                
        from qgis.core import QgsTask, QgsApplication
        
        def run_zstats_async(task):
            try:
                from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsRasterLayer, QgsField
                from qgis.analysis import QgsZonalStatistics
                from PyQt5.QtCore import QVariant
                
                # 1. Create a local in-memory vector layer inside the worker thread
                temp_lyr = QgsVectorLayer("Polygon?crs=EPSG:4326", "temp_zstats", "memory")
                dp = temp_lyr.dataProvider()
                dp.addAttributes([QgsField("fid", QVariant.Int)])
                temp_lyr.updateFields()
                
                # Add features safely
                temp_features = []
                for idx, wkt in enumerate(geoms_wkt):
                    f = QgsFeature(temp_lyr.fields())
                    f.setGeometry(QgsGeometry.fromWkt(wkt))
                    f.setAttribute(0, idx)
                    temp_features.append(f)
                dp.addFeatures(temp_features)
                
                # 2. Instantiate raster layer locally in worker thread
                local_raster = QgsRasterLayer(raster_path, raster_name)
                if not local_raster.isValid():
                    return False, "Raster-Layer konnte im Hintergrund-Thread nicht geladen werden."
                    
                # Determine stats enum constants
                try:
                    from qgis.core import Qgis
                    stat_sum = Qgis.ZonalStatistic.Sum
                    stat_count = Qgis.ZonalStatistic.Count
                except ImportError:
                    stat_sum = QgsZonalStatistics.Sum
                    stat_count = QgsZonalStatistics.Count
                    
                # 3. Create Zonal Statistics inside worker thread
                zonal_stats = QgsZonalStatistics(
                    temp_lyr,
                    local_raster,
                    "pop_",
                    1,
                    stat_sum | stat_count
                )
                
                # Run computation asynchronously
                zonal_stats.calculateStatistics(None)
                
                # Parse results
                results = []
                from qgis.core import NULL
                for feature in temp_lyr.getFeatures():
                    pop_sum = feature["pop_sum"]
                    pop_count = feature["pop_count"]
                    
                    val_sum = float(pop_sum) if pop_sum != NULL and pop_sum is not None else 0.0
                    val_count = int(pop_count) if pop_count != NULL and pop_count is not None else 0
                    results.append((val_sum, val_count))
                    
                return True, results
            except Exception as e:
                return False, str(e)
                
        # Define task finished handler
        def on_task_completed(success, results_or_error):
            self.setCursor(Qt.ArrowCursor)
            self.btn_calculate.setEnabled(True)
            self.btn_calculate.setText(self.tr("btn_calculate_pop", "Berechnung starten"))
            
            if not success:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Fehler bei der Zonalstatistik-Berechnung in PopulationDensityDialog: {results_or_error}",
                    "QUCORE", Qgis.Critical
                )
                QMessageBox.critical(
                    self,
                    self.tr("error_calc_failed_title", "Fehler bei Berechnung"),
                    self.tr("error_calc_failed_text", "Zonalstatistik-Berechnung fehlgeschlagen:\n{error}").format(error=str(results_or_error))
                )
                return
                
            # Process results safely on main GUI thread
            total_population = 0.0
            for val_sum, val_count in results_or_error:
                total_population += val_sum
                
            # Display results
            self.lbl_total_pop.setText(f"{total_population:,.0f} {self.tr('people', 'Personen')}")
            
            density = total_population / total_area_km2
            self.lbl_avg_density.setText(f"{density:.2f} {self.tr('people_per_km2', 'Einwohner / km²')}")
            
            # Store results in params for Word Export
            if self.params is not None:
                self.params["aa_area_km2"] = total_area_km2
                self.params["aa_population"] = total_population
                self.params["aa_density"] = density
                
        # Create and start the QgsTask
        task = QgsTask.fromFunction("QUCORE Zonal Statistics AA", run_zstats_async)
        task.taskCompleted.connect(lambda: on_task_completed(*task.returned_values))
        QgsApplication.taskManager().addTask(task)
