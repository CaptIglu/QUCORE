# -*- coding: utf-8 -*-
import os
from PyQt5.QtCore import Qt
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsDistanceArea,
    QgsRectangle,
    QgsTask,
    QgsApplication
)

class ZonalStatsCalculator:
    """
    Service helper class to execute QgsZonalStatistics asynchronously.
    Separates GIS calculation logic from PyQt dialog code.
    """
    def __init__(self, vector_layer, raster_layer, stats_prefix, stats_flags, parent=None):
        self.vector_layer = vector_layer
        self.raster_layer = raster_layer
        self.stats_prefix = stats_prefix
        self.stats_flags = stats_flags
        self.parent = parent
        
    def get_raster_cell_area_km2(self):
        """
        Calculates the area of a single raster cell in square kilometers.
        Must be called on the main thread because it accesses raster_layer and transformContext.
        """
        if not self.raster_layer or not self.raster_layer.isValid():
            return 0.0
            
        try:
            extent = self.raster_layer.extent()
            cx = extent.center().x()
            cy = extent.center().y()
            
            res_x = self.raster_layer.rasterUnitsPerPixelX()
            res_y = self.raster_layer.rasterUnitsPerPixelY()
            
            rect = QgsRectangle(cx, cy, cx + res_x, cy + res_y)
            
            da = QgsDistanceArea()
            da.setSourceCrs(self.raster_layer.crs(), QgsProject.instance().transformContext())
            da.setEllipsoid("WGS84")
            
            geom = QgsGeometry.fromRect(rect)
            area_m2 = da.measureArea(geom)
            
            return area_m2 / 1000000.0
        except Exception:
            return 0.0

    def calculate_async(self, on_completed, on_failed, on_terminated):
        """
        Prepares data on the main thread and spawns a background QgsTask for statistics calculation.
        
        on_completed: callback function taking (total_area_km2, cell_area_km2, results_list)
        on_failed: callback function taking (error_message_string)
        on_terminated: callback function taking no arguments
        """
        if not self.vector_layer or not self.vector_layer.isValid():
            on_failed("Vektor-Layer ist ungültig oder nicht geladen.")
            return
            
        if not self.raster_layer or not self.raster_layer.isValid():
            on_failed("Raster-Layer ist ungültig oder nicht geladen.")
            return
            
        try:
            # 1. Calculate ellipsoidal area of the vector layer (assumed to be in EPSG:4326)
            da = QgsDistanceArea()
            da.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance().transformContext())
            da.setEllipsoid("WGS84")
            
            total_area_m2 = 0.0
            for feature in self.vector_layer.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    total_area_m2 += da.measureArea(feature.geometry())
                    
            total_area_km2 = total_area_m2 / 1000000.0
            if total_area_km2 <= 0.0:
                on_failed("Die Geometrie besitzt keine gültige Fläche.")
                return
                
            # 2. Get cell area
            cell_area_km2 = self.get_raster_cell_area_km2()
            
            # 3. Transform geometries from EPSG:4326 to raster CRS on main thread
            raster_crs = self.raster_layer.crs()
            raster_crs_auth = raster_crs.authid()
            vector_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(vector_crs, raster_crs, QgsProject.instance())
            
            geoms_wkt = []
            for feature in self.vector_layer.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    geom = QgsGeometry(feature.geometry())
                    geom.transform(transform)
                    geoms_wkt.append(geom.asWkt())
                    
            if not geoms_wkt:
                on_failed("Keine gültigen Geometrien für die Berechnung gefunden.")
                return
                
            raster_path = self.raster_layer.source()
            raster_name = self.raster_layer.name()
            
        except Exception as e:
            on_failed(f"Fehler bei der Vorbereitung der Berechnung: {str(e)}")
            return
            
        # 4. Define background worker function
        def run_zstats_worker(task):
            try:
                from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsRasterLayer, QgsField
                from qgis.analysis import QgsZonalStatistics
                from PyQt5.QtCore import QVariant
                
                # Create a local in-memory vector layer inside worker thread
                temp_lyr = QgsVectorLayer(f"Polygon?crs={raster_crs_auth}", "temp_zstats", "memory")
                dp = temp_lyr.dataProvider()
                dp.addAttributes([QgsField("fid", QVariant.Int)])
                temp_lyr.updateFields()
                
                temp_features = []
                for idx, wkt in enumerate(geoms_wkt):
                    if task.isCanceled():
                        return False, "Abgebrochen"
                    f = QgsFeature(temp_lyr.fields())
                    f.setGeometry(QgsGeometry.fromWkt(wkt))
                    f.setAttribute(0, idx)
                    temp_features.append(f)
                dp.addFeatures(temp_features)
                
                if task.isCanceled():
                    return False, "Abgebrochen"
                    
                local_raster = QgsRasterLayer(raster_path, raster_name)
                if not local_raster.isValid():
                    return False, "Raster-Layer konnte im Hintergrund-Thread nicht geladen werden."
                    
                # Determine stats enum constants
                try:
                    from qgis.core import Qgis
                    stat_sum = Qgis.ZonalStatistic.Sum
                    stat_count = Qgis.ZonalStatistic.Count
                    stat_max = Qgis.ZonalStatistic.Max
                except ImportError:
                    stat_sum = QgsZonalStatistics.Sum
                    stat_count = QgsZonalStatistics.Count
                    stat_max = QgsZonalStatistics.Max
                    
                # Setup stats
                zonal_stats = QgsZonalStatistics(
                    temp_lyr,
                    local_raster,
                    self.stats_prefix,
                    1,
                    self.stats_flags
                )
                
                if task.isCanceled():
                    return False, "Abgebrochen"
                    
                # Run calculation
                zonal_stats.calculateStatistics(None)
                
                if task.isCanceled():
                    return False, "Abgebrochen"
                    
                # Parse results
                results = []
                from qgis.core import NULL
                
                has_sum = bool(self.stats_flags & stat_sum)
                has_count = bool(self.stats_flags & stat_count)
                has_max = bool(self.stats_flags & stat_max)
                
                for feature in temp_lyr.getFeatures():
                    val_sum = 0.0
                    val_count = 0
                    val_max = 0.0
                    
                    if has_sum:
                        pop_sum = feature[f"{self.stats_prefix}sum"]
                        val_sum = float(pop_sum) if pop_sum != NULL and pop_sum is not None else 0.0
                    if has_count:
                        pop_count = feature[f"{self.stats_prefix}count"]
                        val_count = int(pop_count) if pop_count != NULL and pop_count is not None else 0
                    if has_max:
                        pop_max = feature[f"{self.stats_prefix}max"]
                        val_max = float(pop_max) if pop_max != NULL and pop_max is not None else 0.0
                        
                    results.append((val_sum, val_count, val_max))
                    
                return True, results
            except Exception as e:
                return False, str(e)
                
        # 5. Define handlers for QgsTask
        def on_task_completed(success, results_or_error):
            if not success:
                on_failed(str(results_or_error))
            else:
                on_completed(total_area_km2, cell_area_km2, results_or_error)
                
        def on_task_terminated():
            on_terminated()
            
        # 6. Create and start task
        task_name = f"QUCORE Zonal Stats ({self.stats_prefix})"
        task = QgsTask.fromFunction(task_name, run_zstats_worker)
        task.taskCompleted.connect(lambda: on_task_completed(*task.returned_values))
        task.taskTerminated.connect(on_task_terminated)
        
        try:
            QgsApplication.taskManager().addTask(task)
        except Exception as e:
            on_failed(f"Fehler beim Starten des Hintergrund-Tasks: {str(e)}")
