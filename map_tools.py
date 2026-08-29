# -*- coding: utf-8 -*-
import math
import weakref
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapTool, QgsMapMouseEvent, QgsVertexMarker
from qgis.core import QgsPointXY
from .config_manager import ConfigManager

class WaypointMapTool(QgsMapTool):
    def __init__(self, canvas, plugin):
        super(WaypointMapTool, self).__init__(canvas)
        self.canvas = canvas
        self._plugin_ref = weakref.ref(plugin)
        self.dragging_idx = -1
        self.midpoint_markers = []

    @property
    def plugin(self):
        return self._plugin_ref() if self._plugin_ref else None
        
    def activate(self):
        super(WaypointMapTool, self).activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.update_midpoint_markers()
        
    def deactivate(self):
        super(WaypointMapTool, self).deactivate()
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self.clear_midpoint_markers()
        
    def clear_midpoint_markers(self):
        """Removes all midpoint markers from the map canvas."""
        if hasattr(self, 'midpoint_markers'):
            from qgis.PyQt import sip
            for marker_info in self.midpoint_markers:
                marker = marker_info.get('marker')
                if marker and not sip.isdeleted(marker):
                    try:
                        if self.canvas and self.canvas.scene():
                            self.canvas.scene().removeItem(marker)
                        if not sip.isdeleted(marker):
                            sip.delete(marker)
                    except Exception as e:
                        from qgis.core import QgsMessageLog, Qgis
                        import traceback
                        QgsMessageLog.logMessage(f"Silent exception caught in plugin.py (line 81): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.MessageLevel.Warning)
            self.midpoint_markers = []

    def cleanup(self):
        """Breaks circular references to allow clean garbage collection."""
        self.clear_midpoint_markers()
        self._plugin_ref = None
        self.canvas = None

    def update_midpoint_markers(self):
        """Creates or updates markers at the midpoints between waypoints."""
        self.clear_midpoint_markers()
        
        # Midpoint markers are only relevant for Corridor (>=2 waypoints) or Polygon (>=3 waypoints)
        num_wps = len(self.plugin.waypoints)
        if num_wps < 2:
            return
        if self.plugin.geometry_type == "Circle":
            return
            
        # Determine the segments
        segments = []
        for i in range(num_wps - 1):
            segments.append((i, i + 1))
            
        if self.plugin.geometry_type == "Polygon" and num_wps >= 3:
            segments.append((num_wps - 1, 0))
            
        # Draw a marker at the midpoint of each segment
        for idx1, idx2 in segments:
            w1 = self.plugin.waypoints[idx1]
            w2 = self.plugin.waypoints[idx2]
            
            # WGS84 coordinates
            lon1, lat1 = w1[0], w1[1]
            lon2, lat2 = w2[0], w2[1]
            
            # Midpoint calculation in WGS84
            mid_lon = (lon1 + lon2) / 2.0
            mid_lat = (lat1 + lat2) / 2.0
            
            pt_wgs = QgsPointXY(mid_lon, mid_lat)
            pt_canvas = self.plugin.transform_from_wgs84(pt_wgs)
            
            # Create a QgsVertexMarker
            marker = QgsVertexMarker(self.canvas)
            marker.setCenter(pt_canvas)
            marker.setIconType(QgsVertexMarker.IconType.ICON_CROSS)
            marker.setIconSize(10)
            marker.setPenWidth(2)
            marker.setColor(QColor(235, 87, 87)) # Premium coral red matching theme colors
            
            self.midpoint_markers.append({
                'marker': marker,
                'idx1': idx1,
                'idx2': idx2,
                'coords': pt_wgs
            })

    def canvasPressEvent(self, e: QgsMapMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            # Check if we clicked close to an existing waypoint (in pixel coordinates)
            click_pixel = e.pixelPoint()
            closest_idx = -1
            min_dist = 15.0 # pixel threshold for drag selection
            
            for idx, w in enumerate(self.plugin.waypoints):
                pt_wgs = QgsPointXY(w[0], w[1])
                pt_canvas = self.plugin.transform_from_wgs84(pt_wgs)
                pt_pixel = self.toCanvasCoordinates(pt_canvas)
                
                dx = pt_pixel.x() - click_pixel.x()
                dy = pt_pixel.y() - click_pixel.y()
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx
                    
            if closest_idx != -1:
                # Enter drag-and-drop mode
                if self.plugin: self.plugin.on_clear_focus()
                self.plugin.push_undo() # Push state before dragging
                self.dragging_idx = closest_idx
                self.plugin.is_dragging = True
                self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.clear_midpoint_markers() # Hide midpoint crosses during active drag
            else:
                # Check if we clicked close to a midpoint marker
                closest_midpoint = None
                min_midpoint_dist = 12.0 # pixel threshold for clicking a midpoint marker
                
                if hasattr(self, 'midpoint_markers'):
                    for m_info in self.midpoint_markers:
                        pt_canvas = self.plugin.transform_from_wgs84(m_info['coords'])
                        pt_pixel = self.toCanvasCoordinates(pt_canvas)
                        
                        dx = pt_pixel.x() - click_pixel.x()
                        dy = pt_pixel.y() - click_pixel.y()
                        dist = math.sqrt(dx*dx + dy*dy)
                        if dist < min_midpoint_dist:
                            min_midpoint_dist = dist
                            closest_midpoint = m_info
                
                if closest_midpoint is not None:
                    # Yes! Insert a new waypoint at the clicked location between idx1 and idx2
                    idx1 = closest_midpoint['idx1']
                    idx2 = closest_midpoint['idx2']
                    
                    if idx1 == len(self.plugin.waypoints) - 1 and idx2 == 0:
                        insert_idx = len(self.plugin.waypoints)
                    else:
                        insert_idx = max(idx1, idx2)
                        
                    pt_wgs = self.plugin.transform_to_wgs84(e.mapPoint())
                    
                    # Interpolate values (altitude, speed, corridor width) from neighbor waypoints
                    w1 = self.plugin.waypoints[idx1]
                    w2 = self.plugin.waypoints[idx2]
                    
                    alt1 = w1[2] if len(w1) > 2 else float(ConfigManager.get_param(self.plugin.params, "maxFlightHeight"))
                    alt2 = w2[2] if len(w2) > 2 else float(ConfigManager.get_param(self.plugin.params, "maxFlightHeight"))
                    
                    spd1 = w1[3] if len(w1) > 3 else float(ConfigManager.get_param(self.plugin.params, "maxOpsSpeedV0"))
                    spd2 = w2[3] if len(w2) > 3 else float(ConfigManager.get_param(self.plugin.params, "maxOpsSpeedV0"))
                    
                    fg1 = w1[4] if len(w1) > 4 else float(ConfigManager.get_param(self.plugin.params, "corridorWidth"))
                    fg2 = w2[4] if len(w2) > 4 else float(ConfigManager.get_param(self.plugin.params, "corridorWidth"))
                    
                    new_alt = (alt1 + alt2) / 2.0
                    new_spd = (spd1 + spd2) / 2.0
                    new_fg = (fg1 + fg2) / 2.0
                    
                    if self.plugin: self.plugin.on_clear_focus()
                    self.plugin.push_undo() # Push state before adding waypoint
                    
                    # Insert the new waypoint
                    self.plugin.waypoints.insert(insert_idx, (pt_wgs.x(), pt_wgs.y(), new_alt, new_spd, new_fg))
                    
                    # Immediately enter drag mode on this new waypoint for fluid UX
                    self.dragging_idx = insert_idx
                    self.plugin.is_dragging = True
                    self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
                    self.clear_midpoint_markers() # Hide midpoint crosses during active drag
                    
                    self.plugin.rebuild_and_calculate()
                else:
                    # If Circle, enforce exactly 1 waypoint (center)
                    if self.plugin.geometry_type == "Circle" and len(self.plugin.waypoints) >= 1:
                        return
                        
                    # Not close to any existing waypoint -> add a new waypoint
                    pt_wgs = self.plugin.transform_to_wgs84(e.mapPoint())
                    def_alt = float(ConfigManager.get_param(self.plugin.params, "maxFlightHeight"))
                    def_spd = float(ConfigManager.get_param(self.plugin.params, "maxOpsSpeedV0"))
                    
                    if self.plugin.geometry_type == "Circle":
                        def_fg = self.plugin.spn_circle_radius.value()
                    else:
                        def_fg = float(ConfigManager.get_param(self.plugin.params, "corridorWidth"))
                        
                    if self.plugin: self.plugin.on_clear_focus()
                    self.plugin.push_undo() # Push state before adding waypoint
                    self.plugin.waypoints.append((pt_wgs.x(), pt_wgs.y(), def_alt, def_spd, def_fg))
                    self.plugin.rebuild_and_calculate()
                
        elif e.button() == Qt.MouseButton.RightButton:
            # Right-click exits waypoint editing mode
            self.plugin.btn_draw_wp.setChecked(False)
            self.canvas.unsetMapTool(self)
            
    def canvasMoveEvent(self, e: QgsMapMouseEvent):
        if self.dragging_idx != -1:
            # Dragging: update coordinates of the selected waypoint
            pt_wgs = self.plugin.transform_to_wgs84(e.mapPoint())
            w = self.plugin.waypoints[self.dragging_idx]
            alt = w[2] if len(w) > 2 else float(ConfigManager.get_param(self.plugin.params, "maxFlightHeight"))
            spd = w[3] if len(w) > 3 else float(ConfigManager.get_param(self.plugin.params, "maxOpsSpeedV0"))
            fg = w[4] if len(w) > 4 else float(ConfigManager.get_param(self.plugin.params, "corridorWidth"))
            
            self.plugin.waypoints[self.dragging_idx] = (pt_wgs.x(), pt_wgs.y(), alt, spd, fg)
            
            # Recalculate in real time to morph the corridor live
            self.plugin.rebuild_and_calculate()
        else:
            # Check if hovering near a waypoint
            hover_pixel = e.pixelPoint()
            hover_idx = -1
            min_dist = 15.0
            
            for idx, w in enumerate(self.plugin.waypoints):
                pt_wgs = QgsPointXY(w[0], w[1])
                pt_canvas = self.plugin.transform_from_wgs84(pt_wgs)
                pt_pixel = self.toCanvasCoordinates(pt_canvas)
                
                dx = pt_pixel.x() - hover_pixel.x()
                dy = pt_pixel.y() - hover_pixel.y()
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < min_dist:
                    min_dist = dist
                    hover_idx = idx
                    
            if hover_idx != -1:
                self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                # Check if hovering near a midpoint marker
                hover_midpoint = False
                min_midpoint_dist = 12.0
                
                if hasattr(self, 'midpoint_markers'):
                    for m_info in self.midpoint_markers:
                        pt_canvas = self.plugin.transform_from_wgs84(m_info['coords'])
                        pt_pixel = self.toCanvasCoordinates(pt_canvas)
                        
                        dx = pt_pixel.x() - hover_pixel.x()
                        dy = pt_pixel.y() - hover_pixel.y()
                        dist = math.sqrt(dx*dx + dy*dy)
                        if dist < min_midpoint_dist:
                            min_midpoint_dist = dist
                            hover_midpoint = True
                            
                if hover_midpoint:
                    self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.canvas.setCursor(Qt.CursorShape.CrossCursor)
            
    def canvasReleaseEvent(self, e: QgsMapMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton and self.dragging_idx != -1:
            # Finish dragging
            self.dragging_idx = -1
            self.plugin.is_dragging = False
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            self.plugin.rebuild_and_calculate()

    def canvasDoubleClickEvent(self, e: QgsMapMouseEvent):
        """Double-click on a waypoint to delete it."""
        if e.button() == Qt.MouseButton.LeftButton:
            click_pixel = e.pixelPoint()
            closest_idx = -1
            min_dist = 15.0
            
            for idx, w in enumerate(self.plugin.waypoints):
                pt_wgs = QgsPointXY(w[0], w[1])
                pt_canvas = self.plugin.transform_from_wgs84(pt_wgs)
                pt_pixel = self.toCanvasCoordinates(pt_canvas)
                
                dx = pt_pixel.x() - click_pixel.x()
                dy = pt_pixel.y() - click_pixel.y()
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx
                    
            if closest_idx != -1:
                if self.plugin: self.plugin.on_clear_focus()
                self.plugin.push_undo()
                self.plugin.waypoints.pop(closest_idx)
                self.plugin.rebuild_and_calculate()

