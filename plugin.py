# -*- coding: utf-8 -*-
import os
import math
import uuid
import tempfile
from PyQt5.QtCore import Qt, QVariant
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import (
    QAction,
    QMessageBox,
    QFileDialog,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QInputDialog,
    QStyle,
    QComboBox,
    QDoubleSpinBox
)
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbol,
    QgsSingleSymbolRenderer
)
from qgis.gui import QgsMapToolEmitPoint, QgsMapTool, QgsMapMouseEvent, QgsVertexMarker

import json
from .buffer_calculator import BufferCalculator
from .parameter_dialog import ParameterDialog
from .altitude_table_dialog import AltitudeTableDialog
from .importer_exporter import ImporterExporter
from .export_settings_dialog import ExportSettingsDialog
from .advanced_settings_dialog import AdvancedSettingsDialog
from .vlos_calculator_dialog import VlosCalculatorDialog
from .sora_volume_widget import SoraVolumeWidget

class WaypointMapTool(QgsMapTool):
    def __init__(self, canvas, plugin):
        super(WaypointMapTool, self).__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        self.dragging_idx = -1
        self.midpoint_markers = []
        
    def activate(self):
        super(WaypointMapTool, self).activate()
        self.canvas.setCursor(Qt.CrossCursor)
        self.update_midpoint_markers()
        
    def deactivate(self):
        super(WaypointMapTool, self).deactivate()
        self.canvas.setCursor(Qt.ArrowCursor)
        self.clear_midpoint_markers()
        
    def clear_midpoint_markers(self):
        """Removes all midpoint markers from the map canvas."""
        if hasattr(self, 'midpoint_markers'):
            import sip
            for marker_info in self.midpoint_markers:
                marker = marker_info.get('marker')
                if marker:
                    try:
                        if self.canvas and self.canvas.scene():
                            self.canvas.scene().removeItem(marker)
                        sip.delete(marker)
                    except Exception:
                        pass
            self.midpoint_markers = []

    def cleanup(self):
        """Breaks circular references to allow clean garbage collection."""
        self.clear_midpoint_markers()
        self.plugin = None
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
            marker.setIconType(QgsVertexMarker.ICON_CROSS)
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
        if e.button() == Qt.LeftButton:
            # Check if we clicked close to an existing waypoint (in pixel coordinates)
            click_pixel = e.pos()
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
                self.plugin.push_undo() # Push state before dragging
                self.dragging_idx = closest_idx
                self.plugin.is_dragging = True
                self.canvas.setCursor(Qt.ClosedHandCursor)
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
                    
                    alt1 = w1[2] if len(w1) > 2 else float(self.plugin.params.get("maxFlightHeight", 100.0))
                    alt2 = w2[2] if len(w2) > 2 else float(self.plugin.params.get("maxFlightHeight", 100.0))
                    
                    spd1 = w1[3] if len(w1) > 3 else float(self.plugin.params.get("maxVelocity", 30.0))
                    spd2 = w2[3] if len(w2) > 3 else float(self.plugin.params.get("maxVelocity", 30.0))
                    
                    fg1 = w1[4] if len(w1) > 4 else float(self.plugin.params.get("corridorWidth", 50.0))
                    fg2 = w2[4] if len(w2) > 4 else float(self.plugin.params.get("corridorWidth", 50.0))
                    
                    new_alt = (alt1 + alt2) / 2.0
                    new_spd = (spd1 + spd2) / 2.0
                    new_fg = (fg1 + fg2) / 2.0
                    
                    self.plugin.push_undo() # Push state before adding waypoint
                    
                    # Insert the new waypoint
                    self.plugin.waypoints.insert(insert_idx, (pt_wgs.x(), pt_wgs.y(), new_alt, new_spd, new_fg))
                    
                    # Immediately enter drag mode on this new waypoint for fluid UX
                    self.dragging_idx = insert_idx
                    self.plugin.is_dragging = True
                    self.canvas.setCursor(Qt.ClosedHandCursor)
                    self.clear_midpoint_markers() # Hide midpoint crosses during active drag
                    
                    self.plugin.rebuild_and_calculate()
                else:
                    # If Circle, enforce exactly 1 waypoint (center)
                    if self.plugin.geometry_type == "Circle" and len(self.plugin.waypoints) >= 1:
                        return
                        
                    # Not close to any existing waypoint -> add a new waypoint
                    pt_wgs = self.plugin.transform_to_wgs84(e.mapPoint())
                    def_alt = float(self.plugin.params.get("maxFlightHeight", 100.0))
                    def_spd = float(self.plugin.params.get("maxVelocity", 30.0))
                    
                    if self.plugin.geometry_type == "Circle":
                        def_fg = self.plugin.spn_circle_radius.value()
                    else:
                        def_fg = float(self.plugin.params.get("corridorWidth", 50.0))
                        
                    self.plugin.push_undo() # Push state before adding waypoint
                    self.plugin.waypoints.append((pt_wgs.x(), pt_wgs.y(), def_alt, def_spd, def_fg))
                    self.plugin.rebuild_and_calculate()
                
        elif e.button() == Qt.RightButton:
            # Right-click exits waypoint editing mode
            self.plugin.btn_draw_wp.setChecked(False)
            self.canvas.unsetMapTool(self)
            
    def canvasMoveEvent(self, e: QgsMapMouseEvent):
        if self.dragging_idx != -1:
            # Dragging: update coordinates of the selected waypoint
            pt_wgs = self.plugin.transform_to_wgs84(e.mapPoint())
            w = self.plugin.waypoints[self.dragging_idx]
            alt = w[2] if len(w) > 2 else float(self.plugin.params.get("maxFlightHeight", 100.0))
            spd = w[3] if len(w) > 3 else float(self.plugin.params.get("maxVelocity", 30.0))
            fg = w[4] if len(w) > 4 else float(self.plugin.params.get("corridorWidth", 50.0))
            
            self.plugin.waypoints[self.dragging_idx] = (pt_wgs.x(), pt_wgs.y(), alt, spd, fg)
            
            # Recalculate in real time to morph the corridor live
            self.plugin.rebuild_and_calculate()
        else:
            # Check if hovering near a waypoint
            hover_pixel = e.pos()
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
                self.canvas.setCursor(Qt.OpenHandCursor)
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
                    self.canvas.setCursor(Qt.PointingHandCursor)
                else:
                    self.canvas.setCursor(Qt.CrossCursor)
            
    def canvasReleaseEvent(self, e: QgsMapMouseEvent):
        if e.button() == Qt.LeftButton and self.dragging_idx != -1:
            # Finish dragging
            self.dragging_idx = -1
            self.plugin.is_dragging = False
            self.canvas.setCursor(Qt.OpenHandCursor)
            self.plugin.rebuild_and_calculate()

    def canvasDoubleClickEvent(self, e: QgsMapMouseEvent):
        """Double-click on a waypoint to delete it."""
        if e.button() == Qt.LeftButton:
            click_pixel = e.pos()
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
                self.plugin.push_undo()
                self.plugin.waypoints.pop(closest_idx)
                self.plugin.rebuild_and_calculate()


class AboutDialog(QDialog):
    def __init__(self, parent, metadata, plugin):
        super(AboutDialog, self).__init__(parent)
        self.metadata = metadata
        self.plugin = plugin
        self.plugin_dir = plugin.plugin_dir
        self.tr = plugin.tr
        
        self.setWindowTitle(self.tr("dialog_about_title", "Über QUCORE"))
        self.resize(550, 530)
        self.setModal(True)
        self.init_ui()
        
    def init_ui(self):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialogButtonBox, QHBoxLayout
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header Layout (Icon + Title & Version)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        
        # Icon
        lbl_icon = QLabel()
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            lbl_icon.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header_layout.addWidget(lbl_icon)
        
        # Title and Version Info
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        
        name = self.metadata.get('name', 'QUCORE (Variable UAS Corridor Planning)')
        version = self.metadata.get('version', '0.5.0')
        
        lbl_name = QLabel(f'<span style="font-size: 16px; font-weight: bold; color: #2c3e50;">{name}</span>')
        lbl_version = QLabel(f'<span style="font-size: 12px; color: #7f8c8d; font-weight: 500;">Version {version}</span>')
        
        title_layout.addWidget(lbl_name)
        title_layout.addWidget(lbl_version)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Description / About text
        description = self.metadata.get('description', '')
        about = self.metadata.get('about', '')
        
        desc_html = f"""
        <div style="font-size: 11.5px; line-height: 1.5; color: #2c3e50;">
            <p style="margin-bottom: 8px;">{description}</p>
            <p style="margin-top: 0px; margin-bottom: 0px;">{about}</p>
        </div>
        """
        lbl_desc = QLabel(desc_html)
        lbl_desc.setWordWrap(True)
        lbl_desc.setTextFormat(Qt.RichText)
        layout.addWidget(lbl_desc)
        
        # Metadata Table
        category = self.metadata.get('category', 'Vector')
        tags = self.metadata.get('tags', '')
        if tags:
            tags = ", ".join([t.strip() for t in tags.split(",")])
        author = self.metadata.get('author', 'Tim Strohbach')
        tracker = self.metadata.get('tracker', 'https://github.com/CaptIglu/QUCORE/issues')
        repository = self.metadata.get('repository', 'https://github.com/CaptIglu/QUCORE')
        
        tr_category = self.tr('about_category', 'Kategorie')
        tr_tags = self.tr('about_tags', 'Tags')
        tr_more_info = self.tr('about_more_info', 'Weitere Informationen')
        tr_tracker = self.tr('about_tracker', 'Fehlerverfolgung')
        tr_repo = self.tr('about_repo', 'Coderepositorium')
        tr_author = self.tr('about_author', 'Autor')
        tr_version = self.tr('about_version', 'Installierte Version')
        
        table_html = f"""
        <table style="border-collapse: collapse; width: 100%; font-size: 11.5px; margin-top: 5px;">
            <tr style="background-color: #fcfcfc;">
                <td style="padding: 6px 8px; font-weight: bold; color: #555555; width: 130px; border-bottom: 1px solid #eaeaea;">{tr_category}</td>
                <td style="padding: 6px 8px; color: #2c3e50; border-bottom: 1px solid #eaeaea;">{category}</td>
            </tr>
            <tr>
                <td style="padding: 6px 8px; font-weight: bold; color: #555555; border-bottom: 1px solid #eaeaea;">{tr_tags}</td>
                <td style="padding: 6px 8px; color: #2980b9; border-bottom: 1px solid #eaeaea;">{tags}</td>
            </tr>
            <tr style="background-color: #fcfcfc;">
                <td style="padding: 6px 8px; font-weight: bold; color: #555555; border-bottom: 1px solid #eaeaea;">{tr_more_info}</td>
                <td style="padding: 6px 8px; border-bottom: 1px solid #eaeaea;">
                    <a href="{tracker}" style="color: #3498db; text-decoration: underline;">{tr_tracker}</a>
                    &nbsp;&nbsp;&nbsp;&nbsp;
                    <a href="{repository}" style="color: #3498db; text-decoration: underline;">{tr_repo}</a>
                </td>
            </tr>
            <tr>
                <td style="padding: 6px 8px; font-weight: bold; color: #555555; border-bottom: 1px solid #eaeaea;">{tr_author}</td>
                <td style="padding: 6px 8px; color: #2c3e50; border-bottom: 1px solid #eaeaea;">{author}</td>
            </tr>
            <tr style="background-color: #fcfcfc;">
                <td style="padding: 6px 8px; font-weight: bold; color: #555555; border-bottom: 1px solid #eaeaea;">{tr_version}</td>
                <td style="padding: 6px 8px; color: #2c3e50; border-bottom: 1px solid #eaeaea; font-weight: bold;">{version}</td>
            </tr>
        </table>
        """
        
        lbl_table = QLabel(table_html)
        lbl_table.setWordWrap(True)
        lbl_table.setTextFormat(Qt.RichText)
        lbl_table.setOpenExternalLinks(True)
        layout.addWidget(lbl_table)
        
        # License Group Box (Dynamic Status & Activation Button)
        self.grp_license = QGroupBox(self.tr("license_status_title", "Lizenzierung und Testzeitraum"))
        lay_lic = QHBoxLayout(self.grp_license)
        lay_lic.setContentsMargins(10, 10, 10, 10)
        lay_lic.setSpacing(10)
        
        self.lbl_license_status = QLabel()
        self.lbl_license_status.setTextFormat(Qt.RichText)
        self.lbl_license_status.setWordWrap(True)
        lay_lic.addWidget(self.lbl_license_status, 1)
        
        self.btn_license = QPushButton()
        self.btn_license.setFixedWidth(180)
        self.btn_license.clicked.connect(self.on_license_button_clicked)
        lay_lic.addWidget(self.btn_license, 0, Qt.AlignVCenter)
        
        layout.addWidget(self.grp_license)
        
        # Initialize/update the license UI details
        self.update_license_ui()
        
        # Compatibility Note
        tr_qgis_compatibility = self.tr('about_qgis_compatibility', 'Entwickelt für QGIS 3.44.10-Solothurn LTR. Nur hier wird die beste Kompatibilität erwartet.')
        tr_note = self.tr('about_note', 'Hinweis')
        
        note_html = f"""
        <div style="padding: 10px 12px; background-color: #fef9e7; border-left: 4px solid #f39c12; border-radius: 4px; color: #7f8c8d; font-size: 11px; line-height: 1.4;">
            <strong style="color: #d35400;">{tr_note}:</strong> {tr_qgis_compatibility}
        </div>
        """
        lbl_note = QLabel(note_html)
        lbl_note.setWordWrap(True)
        lbl_note.setTextFormat(Qt.RichText)
        layout.addWidget(lbl_note)
        
        # Button Box
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

    def update_license_ui(self):
        from PyQt5.QtCore import QSettings, QDateTime
        settings = QSettings()
        
        # Check license activation
        is_commercial_unlocked = self.plugin.params.get("commercial_unlocked", False)
        saved_key = str(settings.value("QUCORE/license_key", ""))
        if verify_license_key(saved_key):
            is_commercial_unlocked = True
            
        # Get trial details
        install_date_str = settings.value("QUCORE/install_date", "")
        if not install_date_str:
            install_date_str = QDateTime.currentDateTime().toString(Qt.ISODate)
            settings.setValue("QUCORE/install_date", install_date_str)
            
        install_date = QDateTime.fromString(install_date_str, Qt.ISODate)
        days_since_install = install_date.daysTo(QDateTime.currentDateTime())
        remaining_days = 30 - days_since_install
        
        if is_commercial_unlocked:
            bg_color = "#e8f8f5"
            border_color = "#2ecc71"
            title_text = self.tr("license_activated", "Aktiviert (Kommerzielle Lizenz)")
            sub_text = f"Registrierte E-Mail: {saved_key.split(':', 1)[0] if ':' in saved_key else 'In Konfigurationsdatei freigeschaltet'}"
            btn_text = self.tr("btn_change_license_key", "Lizenzschlüssel ändern...")
            status_style = "color: #27ae60; font-weight: bold; font-size: 11px;"
        elif remaining_days < 0:
            bg_color = "#fdf2f2"
            border_color = "#ec7063"
            title_text = self.tr("license_expired", "Abgelaufen (Kommerzielle Lizenz erforderlich)")
            sub_text = self.tr("license_expired_desc", "Die 30-tägige Testphase für die kommerzielle Nutzung ist abgelaufen (kommerzielle Nutzung erfordert eine Lizenz). Die private Nutzung ist weiterhin gestattet.")
            btn_text = self.tr("btn_enter_license_key", "Lizenzschlüssel eingeben...")
            status_style = "color: #c0392b; font-weight: bold; font-size: 11px;"
        else:
            bg_color = "#fef9e7"
            border_color = "#f39c12"
            title_text = self.tr("license_not_activated", "Nicht aktiviert (Testphase)")
            days_str = self.tr("license_days", "{days} Tage").format(days=max(0, remaining_days))
            sub_text = f"<b>{days_str}</b> von 30 Tagen verbleibend."
            btn_text = self.tr("btn_enter_license_key", "Lizenzschlüssel eingeben...")
            status_style = "color: #d35400; font-weight: bold; font-size: 11px;"
            
        license_html = f"""
        <div style="padding: 8px; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 4px;">
            <div style="{status_style}">🔑 {title_text}</div>
            <div style="font-size: 10.5px; margin-top: 3px; color: #555555; line-height: 1.3;">{sub_text}</div>
        </div>
        """
        self.lbl_license_status.setText(license_html)
        self.btn_license.setText(btn_text)

    def on_license_button_clicked(self):
        from PyQt5.QtWidgets import QInputDialog, QMessageBox
        from PyQt5.QtCore import QSettings
        
        key, ok = QInputDialog.getText(
            self,
            self.tr("license_prompt_title", "Lizenzschlüssel eingeben"),
            self.tr("license_prompt_label", "Bitte geben Sie Ihren Lizenzschlüssel ein (Format: E-Mail:Schlüssel):"),
            text=""
        )
        if ok:
            key_clean = key.strip()
            if verify_license_key(key_clean):
                # Save key in settings
                settings = QSettings()
                settings.setValue("QUCORE/license_key", key_clean)
                
                # Update plugin params
                self.plugin.params["commercial_unlocked"] = True
                
                # Show success message
                QMessageBox.information(
                    self,
                    self.tr("license_success_title", "Aktivierung erfolgreich"),
                    self.tr("license_success_text", "Lizenz erfolgreich aktiviert! Vielen Dank für die Unterstützung von QUCORE.")
                )
                
                # Refresh our dialog UI
                self.update_license_ui()
                
                # Refresh the main plugin panel if it exists!
                if hasattr(self.plugin, 'lbl_trial_warning') and self.plugin.lbl_trial_warning:
                    self.plugin.lbl_trial_warning.setVisible(False)
            else:
                # Show error message
                QMessageBox.warning(
                    self,
                    self.tr("license_invalid_title", "Ungültiger Lizenzschlüssel"),
                    self.tr("license_invalid_text", "Ungültiger Lizenzschlüssel. Bitte geben Sie den Schlüssel im Format 'E-Mail:Schlüssel' ein. Wenden Sie sich bei Fragen an tim.strohbach@gmx.de.")
                )


def verify_license_key(key_str):
    """
    Verifies if a license key is a valid SHA-256 hash of an email and secret salt.
    Format of license key is expected to be 'email:signature'
    """
    if not key_str or ":" not in key_str:
        return False
    try:
        email, signature = key_str.split(":", 1)
        email = email.strip().lower()
        signature = signature.strip()
        
        import hashlib
        secret_salt = "QUCORE-SALT-2026-SECRET"
        data = f"{email}:{secret_salt}".encode('utf-8')
        expected_sig = hashlib.sha256(data).hexdigest()[:16]
        
        return signature == expected_sig
    except Exception:
        return False


def hex_to_rgba(hex_str, opacity):
    """
    Helper function to convert hex color string and opacity to 'R,G,B,A' format for QGIS styling.
    """
    try:
        h = hex_str.lstrip('#')
        r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        alpha = int(round(float(opacity) * 255 / 100))
        return f"{r},{g},{b},{alpha}"
    except Exception as e:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"Ungültiger Hex-Farbwert '{hex_str}' oder Opazität '{opacity}': {e}",
            "QUCORE", Qgis.Warning
        )
        return "200,200,200,40"

def hex_to_border_rgba(hex_str, default_fallback="100,100,100,255"):
    """
    Helper function to convert hex color string to border 'R,G,B,255' format for QGIS styling.
    """
    try:
        h = hex_str.lstrip('#')
        r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return f"{r},{g},{b},255"
    except Exception as e:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(
            f"Ungültiger Hex-Farbwert für Rahmen '{hex_str}': {e}",
            "QUCORE", Qgis.Warning
        )
        return default_fallback


class DroneCorridorPlanner(object):
    def __init__(self, iface):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.plugin_dir = os.path.dirname(__file__)
        
        # State
        self.waypoints = [] # List of tuples: (lon, lat, height)
        self.pilot_pos = None # QgsPointXY in EPSG:4326
        self.geometry_type = "Corridor" # "Corridor", "Circle", or "Polygon"
        self.is_dragging = False # State flag for drag-and-drop performance optimization
        
        # Setup Default parameters from Helgoland / config.json
        self.config_path = os.path.join(self.plugin_dir, "config.json")
        
        # Load translations
        self.tr_strings = {}
        tr_path = os.path.join(self.plugin_dir, "translations.json")
        if os.path.exists(tr_path):
            try:
                with open(tr_path, 'r', encoding='utf-8') as f:
                    self.tr_strings = json.load(f)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Fehler beim Laden von translations.json: {e}",
                    "QUCORE", Qgis.Warning
                )
                
        self.params = self.load_config_params()
        
        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        
        # UI controls
        self.action = None
        self.gui = None
        self.wp_tool = None
        self.pilot_tool = None
        
        # Memory layers
        self.layer_group = None
        self.lyr_waypoints = None
        self.lyr_pilot = None
        self.lyr_route = None
        self.lyr_fg = None
        self.lyr_cv = None
        self.lyr_grb = None
        self.lyr_aga = None
        self.lyr_vlos = None

    def load_config_params(self):
        """
        Loads parameters from config.json. If the file doesn't exist,
        creates it with standard default parameters.
        Preserves active session styling overrides in memory.
        """
        defaults = ParameterDialog().params.copy()
        defaults["stepSize"] = 50.0
        defaults["language"] = "de"
        defaults["linewidth_route"] = 1.0
        defaults["linewidth_fg"] = 1.0
        defaults["linewidth_cv"] = 1.0
        defaults["linewidth_grb"] = 1.0
        defaults["linewidth_adjacentarea"] = 1.0
        defaults["linewidth_vlos"] = 0.8
        defaults["color_route"] = "#50505a"
        defaults["color_fg"] = "#397c59"
        defaults["color_cv"] = "#f7bb3d"
        defaults["color_grb"] = "#eb5757"
        defaults["color_adjacentarea"] = "#2980b9"
        defaults["color_vlos"] = "#2d9cdb"
        defaults["opacity_fg"] = 15
        defaults["opacity_cv"] = 15
        defaults["opacity_grb"] = 15
        defaults["opacity_adjacentarea"] = 0
        defaults["opacity_vlos"] = 0
        
        # Capture session styling modifications if self.params already exists
        session_styles = {}
        if hasattr(self, 'params') and self.params:
            style_keys = [
                "linewidth_route", "linewidth_fg", "linewidth_cv", "linewidth_grb", "linewidth_adjacentarea", "linewidth_vlos",
                "color_route", "color_fg", "color_cv", "color_grb", "color_adjacentarea", "color_vlos",
                "opacity_fg", "opacity_cv", "opacity_grb", "opacity_adjacentarea", "opacity_vlos"
            ]
            for key in style_keys:
                if key in self.params:
                    session_styles[key] = self.params[key]
                    
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Fehler beim Laden von config.json: {e}",
                    "QUCORE", Qgis.Warning
                )
                
        # Restore active session style overrides
        defaults.update(session_styles)
        
        # Migration: map old typo keys to new corrected keys
        typo_map = {
            "linewidth_adjecentarea": "linewidth_adjacentarea",
            "color_adjecentarea": "color_adjacentarea",
            "opacity_adjecentarea": "opacity_adjacentarea"
        }
        for old_key, new_key in typo_map.items():
            if old_key in defaults and new_key not in defaults:
                defaults[new_key] = defaults.pop(old_key)
            elif old_key in defaults:
                defaults.pop(old_key)
        
        # Check QSettings for license activation to override commercial_unlocked
        from PyQt5.QtCore import QSettings
        settings = QSettings()
        saved_key = str(settings.value("QUCORE/license_key", ""))
        
        is_comm = defaults.get("commercial_unlocked", False)
        if isinstance(is_comm, str):
            is_comm = (is_comm.lower() == "true" or verify_license_key(is_comm))
            
        if verify_license_key(saved_key) or is_comm:
            is_comm = True
            
        defaults["commercial_unlocked"] = is_comm
        
        return defaults

    def save_config_params(self):
        """
        Disallowed writing to config.json from GUI as per user preference.
        Custom defaults can only be changed manually in config.json.
        """
        pass

    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return self.tr_strings.get(key, {}).get(lang, default)

    def initGui(self):
        """
        Adds action to QGIS toolbar and menus.
        """
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        icon = QIcon(icon_path)
        
        self.action = QAction(
            icon, 
            "QUCORE – UAS-Korridorplanung (FG/CV/GRB)", 
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        
        # Add to Toolbar and Menu
        self.iface.addVectorToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu("QUCORE", self.action)
        
        # Add Help Action
        self.help_action = QAction(
            self.iface.mainWindow().style().standardIcon(QStyle.SP_MessageBoxQuestion),
            "Anleitung / Hilfe...",
            self.iface.mainWindow()
        )
        self.help_action.triggered.connect(self.open_help)
        self.iface.addPluginToVectorMenu("QUCORE", self.help_action)
        
        # Initialize custom Map Tools
        self.wp_tool = WaypointMapTool(self.canvas, self)
        
        self.pilot_tool = QgsMapToolEmitPoint(self.canvas)
        self.pilot_tool.canvasClicked.connect(self.on_pilot_clicked)

        # Auto-cleanup on project clear
        from qgis.core import QgsProject
        QgsProject.instance().cleared.connect(self.on_project_cleared)

    def unload(self):
        """
        Removes action from QGIS toolbar and menus, disconnects signals,
        and cleans up active map tools to prevent memory leaks.
        """
        # 0. Close the dialog and disconnect its finished signal to avoid triggering on_gui_finished during teardown
        if hasattr(self, 'gui') and self.gui:
            try:
                self.gui.finished.disconnect(self.on_gui_finished)
            except Exception:
                pass
            try:
                self.gui.close()
            except Exception:
                pass
            try:
                self.gui.deleteLater()
            except Exception:
                pass

        # Remove layers and group silently on unload
        try:
            self.remove_layers_and_group()
        except Exception:
            pass

        # 1. Disconnect UI action triggers
        if self.action:
            try:
                self.action.triggered.disconnect(self.run)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Entwickler-Warnung beim Trennen der Hauptaktion: {e}", "QUCORE", Qgis.Info)
            self.iface.removePluginVectorMenu("QUCORE", self.action)
            self.iface.removeVectorToolBarIcon(self.action)
            
        if hasattr(self, 'help_action') and self.help_action:
            try:
                self.help_action.triggered.disconnect(self.open_help)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Entwickler-Warnung beim Trennen der Hilfeaktion: {e}", "QUCORE", Qgis.Info)
            self.iface.removePluginVectorMenu("QUCORE", self.help_action)

        # 2. Safely disconnect global application exit listener
        if hasattr(self, 'gui') and self.gui:
            try:
                from qgis.core import QgsApplication
                QgsApplication.instance().aboutToQuit.disconnect(self.gui.reject)
            except Exception:
                pass

        # 3. Disconnect and clean up map tools
        if hasattr(self, 'pilot_tool') and self.pilot_tool:
            try:
                self.pilot_tool.canvasClicked.disconnect(self.on_pilot_clicked)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Entwickler-Warnung beim Trennen des Piloten-Werkzeugs: {e}", "QUCORE", Qgis.Info)

        # 4. Deactivate tools if active on the canvas
        if hasattr(self, 'wp_tool') and hasattr(self, 'pilot_tool'):
            if self.canvas.mapTool() in [self.wp_tool, self.pilot_tool]:
                self.canvas.unsetMapTool(self.canvas.mapTool())
            
        # 5. Clean up active midpoint markers and break references
        if hasattr(self, 'wp_tool') and self.wp_tool:
            try:
                self.wp_tool.cleanup()
            except Exception:
                pass

        # Disconnect project cleared signal
        try:
            from qgis.core import QgsProject
            QgsProject.instance().cleared.disconnect(self.on_project_cleared)
        except Exception:
            pass

        # 6. Nullify references to trigger Python Garbage Collection
        self.wp_tool = None
        self.pilot_tool = None
        self.gui = None
        self.layer_group = None
        self.lyr_waypoints = None
        self.lyr_pilot = None
        self.lyr_route = None
        self.lyr_fg = None
        self.lyr_cv = None
        self.lyr_grb = None
        self.lyr_aga = None
        self.lyr_vlos = None

    def on_project_cleared(self):
        """
        Triggered when QgsProject is cleared. Removes all state and layer references
        so that subsequent plugin actions start in a completely empty and clean state.
        """
        self.waypoints = []
        self.pilot_pos = None
        self.geometry_type = "Corridor"
        self.undo_stack = []
        self.redo_stack = []
        
        self.layer_group = None
        self.lyr_waypoints = None
        self.lyr_pilot = None
        self.lyr_route = None
        self.lyr_fg = None
        self.lyr_cv = None
        self.lyr_grb = None
        self.lyr_aga = None
        self.lyr_vlos = None

    def remove_layers_and_group(self):
        """
        Removes the QUCORE-Korridorplanung group and all its memory layers from the map canvas and registry.
        """
        try:
            from qgis.core import QgsProject, QgsLayerTreeNode
            root = QgsProject.instance().layerTreeRoot()
            group = root.findGroup("QUCORE-Korridorplanung")
            if group:
                # Remove all child layers in the group from the map layer registry
                for child in list(group.children()):
                    if child.nodeType() == QgsLayerTreeNode.NodeLayer:
                        layer = child.layer()
                        if layer:
                            QgsProject.instance().removeMapLayer(layer.id())
                # Remove the group node itself
                parent = group.parent()
                if parent:
                    parent.removeChildNode(group)
        except Exception:
            pass

    def run(self):
        """
        Runs the plugin main control panel GUI.
        """
        if not self.gui:
            self.gui = QDialog(self.iface.mainWindow())
            self.gui.setWindowTitle(self.tr("dialog_title", "QUCORE – UAS-Korridorplanung (FG/CV/GRB)"))
            self.gui.resize(330, 580)
            self.gui.setWindowFlags(Qt.Tool)
            
            
            # Close dialog when QGIS is about to quit to prevent blocking modal exit dialogs
            from qgis.core import QgsApplication
            QgsApplication.instance().aboutToQuit.connect(self.gui.reject)
            
            self.gui.finished.connect(self.on_gui_finished)
            
            layout = QVBoxLayout(self.gui)
            
            # Create a Menu Bar at the top of the dialog
            from PyQt5.QtWidgets import QMenuBar
            self.menu_bar = QMenuBar(self.gui)
            layout.setMenuBar(self.menu_bar)
            
            # File Menu
            self.file_menu = self.menu_bar.addMenu("Datei")
            
            self.import_active_action = self.file_menu.addAction("Aktivierten QGIS-Layer einlesen...")
            self.import_active_action.triggered.connect(self.import_active_layer)
            
            self.import_action = self.file_menu.addAction("Importieren...")
            self.import_action.triggered.connect(self.import_file)
            
            self.export_action = self.file_menu.addAction("Exportieren...")
            self.export_action.triggered.connect(self.export_file)
            
            self.sora_export_action = self.file_menu.addAction("SORA Dokumentations-Export (.docx)...")
            self.sora_export_action.triggered.connect(self.export_sora_report)
            
            self.save_persistent_action = self.file_menu.addAction("Planung als persistenten Layer (GeoPackage) speichern...")
            self.save_persistent_action.triggered.connect(self.save_as_persistent_layer)
            
            self.file_menu.addSeparator()
            
            self.reset_action = self.file_menu.addAction("Planung zurücksetzen")
            self.reset_action.triggered.connect(self.reset_planning)
            
            # Settings Menu
            self.settings_menu = self.menu_bar.addMenu("Einstellungen")
            
            self.calc_params_action = self.settings_menu.addAction("Berechnungsparameter...")
            self.calc_params_action.triggered.connect(self.open_parameter_dialog)
            
            self.adv_settings_action = self.settings_menu.addAction("Erweiterte Einstellungen...")
            self.adv_settings_action.triggered.connect(self.open_advanced_settings_dialog)
            
            self.settings_menu.addSeparator()
            
            # Language Submenu
            self.lang_menu = self.settings_menu.addMenu("Sprache / Language")
            self.lang_de_action = self.lang_menu.addAction("🇩🇪 Deutsch (DE)")
            self.lang_de_action.setCheckable(True)
            self.lang_de_action.triggered.connect(lambda: self.change_language("de"))
            
            self.lang_en_action = self.lang_menu.addAction("🇬🇧 English (EN)")
            self.lang_en_action.setCheckable(True)
            self.lang_en_action.triggered.connect(lambda: self.change_language("en"))
            
            # Check the active language
            active_lang = self.params.get("language", "de")
            self.lang_de_action.setChecked(active_lang == "de")
            self.lang_en_action.setChecked(active_lang == "en")
            
            # Tools Menu
            self.tools_menu = self.menu_bar.addMenu("Werkzeuge")
            self.vlos_calc_action = self.tools_menu.addAction("VLOS-Rechner (ALOS/DLOS)...")
            self.vlos_calc_action.triggered.connect(self.open_vlos_calculator)
            
            self.pop_density_action = self.tools_menu.addAction("Bevölkerungsdichte im AA-Bereich berechnen...")
            self.pop_density_action.triggered.connect(self.open_population_density_dialog)
            
            self.grb_density_action = self.tools_menu.addAction("Bodenrisiko-Analyse (GRB-Bevölkerungsdichte)...")
            self.grb_density_action.triggered.connect(self.open_grb_density_dialog)
            
            # Help Menu
            self.help_menu = self.menu_bar.addMenu("Hilfe")
            
            self.help_action_menu = self.help_menu.addAction("Anleitung / Hilfe...")
            self.help_action_menu.triggered.connect(self.open_help)
            
            self.about_action = self.help_menu.addAction("Über QUCORE...")
            self.about_action.triggered.connect(self.open_about_dialog)
            
            # Header
            self.header_label = QLabel("<b>Drohnen-Sicherheitskorridore</b><br>Kartenbasierte interaktive Planung")
            self.header_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.header_label)
            
            # Geometry type dropdown
            lay_geom = QHBoxLayout()
            self.lbl_geom = QLabel("Geometrietyp:")
            self.cmb_geom_type = QComboBox()
            self.cmb_geom_type.currentIndexChanged.connect(self.on_geometry_type_changed)
            lay_geom.addWidget(self.lbl_geom)
            lay_geom.addWidget(self.cmb_geom_type)
            layout.addLayout(lay_geom)
            
            # Circle radius spinner (only visible/enabled in Circle mode)
            self.lay_circle_rad = QHBoxLayout()
            self.lbl_circle_rad = QLabel("Kreis-Radius (m):")
            self.spn_circle_radius = QDoubleSpinBox()
            self.spn_circle_radius.setRange(5.0, 50000.0)
            self.spn_circle_radius.setValue(50.0)
            self.spn_circle_radius.setDecimals(1)
            self.spn_circle_radius.setSingleStep(5.0)
            self.spn_circle_radius.valueChanged.connect(self.on_circle_radius_changed)
            self.lay_circle_rad.addWidget(self.lbl_circle_rad)
            self.lay_circle_rad.addWidget(self.spn_circle_radius)
            layout.addLayout(self.lay_circle_rad)
            
            # Initially hidden
            self.lbl_circle_rad.setVisible(False)
            self.spn_circle_radius.setVisible(False)
            
            # Map interaction group
            self.grp_map = QGroupBox("Karten-Interaktion")
            lay_map = QVBoxLayout(self.grp_map)
            
            # Row for Draw Waypoints, Undo, and Redo
            lay_wp_row = QHBoxLayout()
            
            self.btn_draw_wp = QPushButton("Wegpunkte zeichnen/modifizieren")
            self.btn_draw_wp.setCheckable(True)
            self.btn_draw_wp.clicked.connect(self.toggle_waypoint_drawing)
            lay_wp_row.addWidget(self.btn_draw_wp)
            
            self.btn_undo = QPushButton()
            self.btn_undo.setFixedSize(30, 30)
            self.btn_undo.setIcon(self.gui.style().standardIcon(QStyle.SP_ArrowBack))
            self.btn_undo.clicked.connect(self.undo)
            lay_wp_row.addWidget(self.btn_undo)
            
            self.btn_redo = QPushButton()
            self.btn_redo.setFixedSize(30, 30)
            self.btn_redo.setIcon(self.gui.style().standardIcon(QStyle.SP_ArrowForward))
            self.btn_redo.clicked.connect(self.redo)
            lay_wp_row.addWidget(self.btn_redo)
            
            lay_map.addLayout(lay_wp_row)
            
            self.btn_set_pilot = QPushButton("Pilotenposition setzen")
            self.btn_set_pilot.setCheckable(True)
            self.btn_set_pilot.clicked.connect(self.toggle_pilot_setting)
            lay_map.addWidget(self.btn_set_pilot)
            
            self.btn_load_active_layer = QPushButton("Aktivierten QGIS-Layer einlesen")
            self.btn_load_active_layer.clicked.connect(self.import_active_layer)
            lay_map.addWidget(self.btn_load_active_layer)
            
            layout.addWidget(self.grp_map)
            
            # Parameter Group Box
            self.grp_params = QGroupBox("Parameter")
            lay_params = QVBoxLayout(self.grp_params)
            
            self.btn_params = QPushButton("Berechnungsparameter anpassen...")
            self.btn_params.clicked.connect(self.open_parameter_dialog)
            lay_params.addWidget(self.btn_params)
            
            self.btn_alt = QPushButton("Höhe, FG-Breite, Geschwindigkeit pro Wegpunkt bearbeiten...")
            self.btn_alt.clicked.connect(self.open_altitude_table)
            lay_params.addWidget(self.btn_alt)
            
            layout.addWidget(self.grp_params)
            
            # Results Group Box
            self.grp_results = QGroupBox("Berechnungsergebnis")
            self.grp_results.setMinimumHeight(220) # Enforce a clean height so that the visualization box fits snugly without empty spaces
            lay_results = QVBoxLayout(self.grp_results)
            lay_results.setContentsMargins(6, 12, 6, 6)
            lay_results.setSpacing(2)
            
            self.lbl_results = QLabel()
            self.lbl_results.setWordWrap(True)
            self.lbl_results.setStyleSheet("font-size: 11px; color: #333; padding: 2px;")
            self.lbl_results.setTextFormat(Qt.RichText)
            lay_results.addWidget(self.lbl_results)
            
            # Sora dynamic visualization widget
            self.sora_viz = SoraVolumeWidget(self.gui, tr_fn=self.tr)
            lay_results.addWidget(self.sora_viz)
            
            layout.addWidget(self.grp_results)
            
            # Action buttons laid out horizontally to save valuable screen height
            lay_actions = QHBoxLayout()
            lay_actions.setSpacing(6)
            
            self.btn_reset_panel = QPushButton("Planung zurücksetzen")
            self.btn_reset_panel.setStyleSheet("QPushButton { color: red; font-weight: bold; }")
            self.btn_reset_panel.clicked.connect(self.reset_planning)
            lay_actions.addWidget(self.btn_reset_panel)
            
            self.btn_close_panel = QPushButton("Planung abschließen")
            self.btn_close_panel.setStyleSheet("QPushButton { color: green; font-weight: bold; }")
            self.btn_close_panel.clicked.connect(self.gui.accept)
            lay_actions.addWidget(self.btn_close_panel)
            
            layout.addLayout(lay_actions)
            
            # Status Label
            self.lbl_status = QLabel()
            self.lbl_status.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.lbl_status)
            
            # Trial Warning Label
            self.lbl_trial_warning = QLabel()
            self.lbl_trial_warning.setAlignment(Qt.AlignCenter)
            self.lbl_trial_warning.setWordWrap(True)
            layout.addWidget(self.lbl_trial_warning)
            
        # Check trial status and display warning if necessary
        from PyQt5.QtCore import QSettings, QDateTime
        settings = QSettings()
        install_date_str = settings.value("QUCORE/install_date", "")
        if not install_date_str:
            install_date_str = QDateTime.currentDateTime().toString(Qt.ISODate)
            settings.setValue("QUCORE/install_date", install_date_str)
            
        install_date = QDateTime.fromString(install_date_str, Qt.ISODate)
        days_since_install = install_date.daysTo(QDateTime.currentDateTime())
        
        is_commercial_unlocked = self.params.get("commercial_unlocked", False)
        if isinstance(is_commercial_unlocked, str):
            is_commercial_unlocked = (is_commercial_unlocked.lower() == "true" or verify_license_key(is_commercial_unlocked))
            
        saved_key = str(settings.value("QUCORE/license_key", ""))
        if verify_license_key(saved_key):
            is_commercial_unlocked = True
            
        if hasattr(self, 'lbl_trial_warning'):
            if days_since_install > 30 and not is_commercial_unlocked:
                self.lbl_trial_warning.setText(
                    "<div style='color: #eb5757; font-size: 10px; font-weight: bold; margin-top: 4px; text-align: center;'>"
                    "⚠️ Testphase für kommerzielle Nutzung abgelaufen (Kommerzielle Nutzung erfordert eine Lizenz. Die private Nutzung ist weiterhin gestattet. Support: tim.strohbach@gmx.de)"
                    "</div>"
                )
                self.lbl_trial_warning.setVisible(True)
            else:
                self.lbl_trial_warning.setVisible(False)
            
        self.apply_translations()
        self.update_undo_redo_buttons()
        
        # Sync combobox to self.geometry_type
        if hasattr(self, 'cmb_geom_type'):
            types = ["Corridor", "Circle", "Polygon"]
            if self.geometry_type in types:
                self.cmb_geom_type.blockSignals(True)
                self.cmb_geom_type.setCurrentIndex(types.index(self.geometry_type))
                self.cmb_geom_type.blockSignals(False)
                
        # Position self.gui at the center of the QGIS main window
        try:
            qgis_win = self.iface.mainWindow()
            qgis_geom = qgis_win.geometry()
            dialog_width = self.gui.width() if self.gui.width() > 100 else 310
            dialog_height = self.gui.height() if self.gui.height() > 100 else 410
            x_pos = qgis_geom.x() + (qgis_geom.width() - dialog_width) // 2
            y_pos = qgis_geom.y() + (qgis_geom.height() - dialog_height) // 2
            if x_pos < qgis_geom.x():
                x_pos = qgis_geom.x()
            if y_pos < qgis_geom.y():
                y_pos = qgis_geom.y()
            self.gui.move(x_pos, y_pos)
        except Exception:
            pass

        # Smart re-bind layers first
        self.initialize_layers()

        # 1. Restore state from project entries if available (preferred for rich state restoration)
        try:
            state_json, ok = QgsProject.instance().readEntry("QUCORE", "state")
            if ok and state_json and not self.waypoints:
                self.deserialize_state(state_json)
        except Exception:
            pass

        # Fallback: Restore waypoints and pilot from layers if python state is still empty (e.g. on reload without project entry)
        if self.is_layer_valid(self.lyr_waypoints) and not self.waypoints:
            try:
                features = list(self.lyr_waypoints.getFeatures())
                if features:
                    def get_index_safe(feat):
                        try:
                            val = feat.attribute("index")
                            from qgis.core import NULL
                            if val is not None and val != NULL:
                                return int(val)
                        except Exception:
                            pass
                        return 999999
                    
                    features.sort(key=get_index_safe)
                    
                    def get_attr_safe(feat, field_name, default_val):
                        try:
                            val = feat.attribute(field_name)
                            from qgis.core import NULL
                            if val is not None and val != NULL:
                                return float(val)
                        except Exception:
                            pass
                        return default_val
                    
                    loaded_wps = []
                    for f in features:
                        geom = f.geometry()
                        if geom and not geom.isEmpty():
                            pt = geom.asPoint()
                            alt_val = get_attr_safe(f, "altitude", float(self.params.get("maxFlightHeight", 100.0)))
                            spd_val = get_attr_safe(f, "speed", float(self.params.get("maxVelocity", 30.0)))
                            fg_val = get_attr_safe(f, "fg_width", float(self.params.get("corridorWidth", 50.0)))
                            loaded_wps.append((pt.x(), pt.y(), alt_val, spd_val, fg_val))
                    if loaded_wps:
                        self.waypoints = loaded_wps
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Fehler beim Laden der Wegpunkte aus dem existierenden Layer beim Start: {e}",
                    "QUCORE", Qgis.Warning
                )

        if self.is_layer_valid(self.lyr_pilot) and self.pilot_pos is None:
            try:
                features = list(self.lyr_pilot.getFeatures())
                if features:
                    geom = features[0].geometry()
                    if geom and not geom.isEmpty():
                        self.pilot_pos = geom.asPoint()
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    f"Fehler beim Laden der Pilotenposition aus dem existierenden Layer beim Start: {e}",
                    "QUCORE", Qgis.Warning
                )

        self.gui.show()
        self.rebuild_and_calculate()

    def change_language(self, lang):
        self.params["language"] = lang
        self.save_config_params()
        
        # Update check marks
        self.lang_de_action.setChecked(lang == "de")
        self.lang_en_action.setChecked(lang == "en")
        
        self.apply_translations()

    def apply_translations(self):
        # Update Window Title of main GUI
        if self.gui:
            self.gui.setWindowTitle(self.tr("dialog_title", "QUCORE – UAS-Korridorplanung (FG/CV/GRB)"))
            
        # Update Menu Titles
        if hasattr(self, 'menu_bar'):
            self.file_menu.setTitle(self.tr("menu_file", "Datei"))
            self.import_action.setText(self.tr("menu_import", "Importieren..."))
            if hasattr(self, 'import_active_action'):
                self.import_active_action.setText(self.tr("menu_import_active", "Importieren aus aktivem QGIS-Layer..."))
            self.export_action.setText(self.tr("menu_export", "Exportieren..."))
            if hasattr(self, 'sora_export_action'):
                self.sora_export_action.setText(self.tr("menu_sora_export", "SORA Dokumentations-Export (.docx)..."))
            if hasattr(self, 'save_persistent_action'):
                self.save_persistent_action.setText(self.tr("menu_save_persistent", "Planung als persistenten Layer (GeoPackage) speichern..."))
            self.reset_action.setText(self.tr("menu_reset", "Planung zurücksetzen"))
            
            self.settings_menu.setTitle(self.tr("menu_settings", "Einstellungen"))
            self.calc_params_action.setText(self.tr("menu_calc_params", "Berechnungsparameter..."))
            self.adv_settings_action.setText(self.tr("menu_adv_settings", "Erweiterte Einstellungen..."))
            self.lang_menu.setTitle(self.tr("menu_lang", "Sprache / Language"))
            self.lang_de_action.setText(self.tr("menu_lang_de", "🇩🇪 Deutsch (DE)"))
            self.lang_en_action.setText(self.tr("menu_lang_en", "🇬🇧 English (EN)"))
            
            self.tools_menu.setTitle(self.tr("menu_tools", "Werkzeuge"))
            self.vlos_calc_action.setText(self.tr("menu_vlos_calc", "VLOS-Rechner (ALOS/DLOS)..."))
            if hasattr(self, 'pop_density_action'):
                self.pop_density_action.setText(self.tr("menu_pop_density", "Bevölkerungsdichte im AA-Bereich berechnen..."))
            if hasattr(self, 'grb_density_action'):
                self.grb_density_action.setText(self.tr("menu_grb_density", "Bodenrisiko-Analyse (GRB-Bevölkerungsdichte)..."))
            
            self.help_menu.setTitle(self.tr("menu_help", "Hilfe"))
            self.help_action_menu.setText(self.tr("menu_instructions", "Anleitung / Hilfe..."))
            if hasattr(self, 'about_action'):
                self.about_action.setText(self.tr("menu_about", "Über QUCORE..."))

        # Update Widget Texts in Planning Panel
        if hasattr(self, 'header_label'):
            self.header_label.setText(self.tr("header_title", "<b>Drohnen-Sicherheitskorridore</b><br>Kartenbasierte interaktive Planung"))
            self.lbl_geom.setText(self.tr("geom_type", "Geometrietyp:"))
            self.lbl_circle_rad.setText(self.tr("circle_rad", "Kreis-Radius (m):"))
            
            # Update ComboBox items without triggering signals
            self.cmb_geom_type.blockSignals(True)
            curr_idx = self.cmb_geom_type.currentIndex()
            self.cmb_geom_type.clear()
            self.cmb_geom_type.addItems([
                self.tr("geom_corridor", "Korridor"),
                self.tr("geom_circle", "Kreis"),
                self.tr("geom_polygon", "Polygon")
            ])
            if curr_idx != -1:
                self.cmb_geom_type.setCurrentIndex(curr_idx)
            self.cmb_geom_type.blockSignals(False)
            
            self.grp_map.setTitle(self.tr("map_interaction_grp", "Karten-Interaktion"))
            self.btn_draw_wp.setText(self.tr("btn_draw_wp", "Wegpunkte zeichnen/modifizieren"))
            self.btn_set_pilot.setText(self.tr("btn_set_pilot", "Pilotenposition setzen"))
            if hasattr(self, 'btn_load_active_layer'):
                self.btn_load_active_layer.setText(self.tr("btn_load_active_layer", "Aktivierten QGIS-Layer einlesen"))
            self.btn_undo.setToolTip(self.tr("btn_undo_tooltip", "Rückgängig (Undo)"))
            self.btn_redo.setToolTip(self.tr("btn_redo_tooltip", "Wiederholen (Redo)"))
            
            self.grp_params.setTitle(self.tr("params_grp", "Parameter"))
            self.btn_params.setText(self.tr("btn_params", "Berechnungsparameter anpassen..."))
            self.btn_alt.setText(self.tr("btn_alt", "Höhe, FG-Breite, Geschwindigkeit pro Wegpunkt bearbeiten..."))
            
            if hasattr(self, 'grp_results'):
                self.grp_results.setTitle(self.tr("results_grp", "Berechnungsergebnis"))
            
            self.btn_reset_panel.setText(self.tr("btn_reset", "Planung zurücksetzen"))
            self.btn_close_panel.setText(self.tr("btn_close", "Planung abschließen"))
            
            # Update Status text
            if self.waypoints:
                self.lbl_status.setText(self.tr("status_calculated", "Wegpunkte: {wp} | Puffer: Berechnet").format(wp=len(self.waypoints)))
            else:
                self.lbl_status.setText(self.tr("status_ready", "Wegpunkte: {wp} | Puffer: Bereit").format(wp=0))

    def open_help(self):
        """
        Opens the local HTML help guide in the user's default web browser.
        """
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        
        help_path = os.path.join(self.plugin_dir, "instructions.html")
        if os.path.exists(help_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(help_path))
        else:
            QMessageBox.warning(
                self.gui if self.gui else self.iface.mainWindow(),
                "Hilfe nicht gefunden",
                "Die Hilfedatei 'instructions.html' konnte im Plugin-Ordner nicht gefunden werden."
            )

    def open_about_dialog(self):
        """
        Parses metadata.txt at runtime and displays the 'Über QUCORE...' dialog.
        """
        import configparser
        metadata_path = os.path.join(self.plugin_dir, "metadata.txt")
        metadata = {}
        if os.path.exists(metadata_path):
            try:
                parser = configparser.ConfigParser(interpolation=None)
                parser.read(metadata_path, encoding='utf-8')
                if parser.has_section('general'):
                    metadata = dict(parser.items('general'))
            except Exception:
                metadata = {}
                
        # Robust fallback line-by-line parsing if configparser was not populated
        if not metadata and os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line:
                            k, v = line.strip().split('=', 1)
                            metadata[k.strip()] = v.strip()
            except Exception:
                pass
                
        dlg = AboutDialog(self.gui if self.gui else self.iface.mainWindow(), metadata, self)
        dlg.exec_()

    def on_geometry_type_changed(self, index):
        types = ["Corridor", "Circle", "Polygon"]
        self.geometry_type = types[index]
        self.rebuild_and_calculate()

    def on_circle_radius_changed(self, val):
        if self.geometry_type == "Circle" and self.waypoints:
            cd = float(self.params.get("maxCharacteristicDimension", 3.6))
            min_radius = 3.0 * cd
            if val < min_radius:
                val = min_radius
            self.push_undo()
            w = self.waypoints[0]
            alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
            spd = w[3] if len(w) > 3 else float(self.params.get("maxVelocity", 30.0))
            self.waypoints[0] = (w[0], w[1], alt, spd, val)
            self.rebuild_and_calculate()

    # ----------------------------------------------------
    # LAYER MANAGEMENT & STYLING
    # ----------------------------------------------------
    def initialize_layers(self, force_restyle=False):
        """
        Creates memory layers in a custom project group at the very top of the layer tree.
        """
        self._force_restyle = force_restyle
        root = QgsProject.instance().layerTreeRoot()
        self.layer_group = root.findGroup("QUCORE-Korridorplanung")
        if self.layer_group is None:
            self.layer_group = root.insertGroup(0, "QUCORE-Korridorplanung")
            self.layer_group.setItemVisibilityChecked(True)
        else:
            # Ensure it is at the very top (index 0) of the layer tree
            if root.children() and root.children()[0] != self.layer_group:
                try:
                    parent = self.layer_group.parent()
                    if parent:
                        cloned_group = self.layer_group.clone()
                        root.insertChildNode(0, cloned_group)
                        parent.removeChildNode(self.layer_group)
                        self.layer_group = cloned_group
                except Exception as e:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        f"Fehler beim Verschieben der Layer-Gruppe an die Spitze des Baums: {e}",
                        "QUCORE", Qgis.Warning
                    )

        # Smart Re-Binding of existing project layers to avoid duplicate creation upon plugin reload
        if self.layer_group:
            from qgis.core import QgsLayerTreeNode
            for child in self.layer_group.children():
                if child.nodeType() == QgsLayerTreeNode.NodeLayer:
                    layer = child.layer()
                    if layer:
                        name = layer.name()
                        if name == "Wegpunkte" and not self.is_layer_valid(self.lyr_waypoints):
                            self.lyr_waypoints = layer
                        elif name == "Flugweg (Mittelachse)" and not self.is_layer_valid(self.lyr_route):
                            self.lyr_route = layer
                        elif name == "Flight Geography (FG)" and not self.is_layer_valid(self.lyr_fg):
                            self.lyr_fg = layer
                        elif name == "Contingency Volume (CV)" and not self.is_layer_valid(self.lyr_cv):
                            self.lyr_cv = layer
                        elif name == "Ground Risk Buffer (GRB)" and not self.is_layer_valid(self.lyr_grb):
                            self.lyr_grb = layer
                        elif name == "Adjacent Area (AA)" and not self.is_layer_valid(self.lyr_aga):
                            self.lyr_aga = layer
                        elif name == "Pilotenposition" and not self.is_layer_valid(self.lyr_pilot):
                            self.lyr_pilot = layer
                        elif name == "VLOS-Reichweite (Pilotenposition)" and not self.is_layer_valid(self.lyr_vlos):
                            self.lyr_vlos = layer

        # (Restore logic has been moved to run() to prevent side-effects during clear/reset planning)

        # Get linewidths from self.params
        lw_route = float(self.params.get("linewidth_route", 1.0))
        lw_fg = float(self.params.get("linewidth_fg", 1.0))
        lw_cv = float(self.params.get("linewidth_cv", 1.0))
        lw_grb = float(self.params.get("linewidth_grb", 1.0))
        lw_aga = float(self.params.get("linewidth_adjacentarea", 1.0))

        # (Nested hex conversion helper functions have been refactored to module-level)

        color_route = self.params.get("color_route", "#50505a")
        color_fg = self.params.get("color_fg", "#397c59")
        color_cv = self.params.get("color_cv", "#f7bb3d")
        color_grb = self.params.get("color_grb", "#eb5757")
        color_adj = self.params.get("color_adjacentarea", "#2980b9")

        opacity_fg = self.params.get("opacity_fg", 15)
        opacity_cv = self.params.get("opacity_cv", 15)
        opacity_grb = self.params.get("opacity_grb", 15)
        opacity_adj = self.params.get("opacity_adjacentarea", 0)

        # 1. Ground Risk Buffer (GRB)
        self.lyr_grb = self.setup_layer(self.lyr_grb, "Polygon?crs=EPSG:4326", "Ground Risk Buffer (GRB)", self.style_polygon_layer, hex_to_rgba(color_grb, opacity_grb), hex_to_border_rgba(color_grb), lw_grb)
            
        # 2. Contingency Volume (CV)
        self.lyr_cv = self.setup_layer(self.lyr_cv, "Polygon?crs=EPSG:4326", "Contingency Volume (CV)", self.style_polygon_layer, hex_to_rgba(color_cv, opacity_cv), hex_to_border_rgba(color_cv), lw_cv)
            
        # 3. Flight Geography (FG)
        self.lyr_fg = self.setup_layer(self.lyr_fg, "Polygon?crs=EPSG:4326", "Flight Geography (FG)", self.style_polygon_layer, hex_to_rgba(color_fg, opacity_fg), hex_to_border_rgba(color_fg), lw_fg)
            
        # 4. Route Centerline
        self.lyr_route = self.setup_layer(self.lyr_route, "LineString?crs=EPSG:4326", "Flugweg (Mittelachse)", self.style_line_layer, hex_to_border_rgba(color_route), lw_route, Qt.DashLine)

        # 5. Adjacent Area (AA)
        self.lyr_aga = self.setup_layer(self.lyr_aga, "Polygon?crs=EPSG:4326", "Adjacent Area (AA)", self.style_aga_layer, color_adj, opacity_adj, lw_aga)
            
        # 6. Pilot Position
        self.lyr_pilot = self.setup_layer(self.lyr_pilot, "Point?crs=EPSG:4326", "Pilotenposition", self.style_point_layer, "242,153,74,255", "255,255,255,255", 3.5)
            
        # 7. Waypoints
        # Special initialization for waypoints to add fields
        exists = self.is_layer_valid(self.lyr_waypoints)
        if not exists:
            self.lyr_waypoints = QgsVectorLayer("Point?crs=EPSG:4326", "Wegpunkte", "memory")
            # Fields
            self.lyr_waypoints.dataProvider().addAttributes([
                QgsField("index", QVariant.Int),
                QgsField("altitude", QVariant.Double),
                QgsField("speed", QVariant.Double),
                QgsField("fg_width", QVariant.Double)
            ])
            self.lyr_waypoints.updateFields()
            self.style_point_layer(self.lyr_waypoints, "45,156,219,255", "255,255,255,255", 3.0)
            QgsProject.instance().addMapLayer(self.lyr_waypoints, False)
            
        node = self.layer_group.findLayer(self.lyr_waypoints.id())
        if node is None:
            node = self.layer_group.addLayer(self.lyr_waypoints)
        if node:
            node.setItemVisibilityChecked(True)

        # 8. VLOS Range Circle (display only)
        self.lyr_vlos = self.setup_layer(self.lyr_vlos, "Polygon?crs=EPSG:4326", "VLOS-Reichweite (Pilotenposition)", self.style_vlos_layer)
 
        # Enforce exact layer order inside the group (Top to Bottom): Waypoints, Route, FG, CV, GRB, VLOS, AA, Pilot
        expected_order = [
            self.lyr_waypoints,
            self.lyr_route,
            self.lyr_fg,
            self.lyr_cv,
            self.lyr_grb,
            self.lyr_vlos,
            self.lyr_aga,
            self.lyr_pilot
        ]
        expected_order = [lyr for lyr in expected_order if self.is_layer_valid(lyr)]
        for target_idx, lyr in enumerate(expected_order):
            node = self.layer_group.findLayer(lyr.id())
            if node:
                parent = node.parent()
                if parent:
                    try:
                        current_idx = parent.children().index(node)
                        if current_idx != target_idx:
                            cloned_node = node.clone()
                            parent.insertChildNode(target_idx, cloned_node)
                            parent.removeChildNode(node)
                    except Exception as e:
                        from qgis.core import QgsMessageLog, Qgis
                        QgsMessageLog.logMessage(
                            f"Fehler beim Sortieren des Layers '{lyr.name()}': {e}",
                            "QUCORE", Qgis.Warning
                        )

    def is_layer_valid(self, layer):
        """
        Safely checks if a layer exists and its underlying C++ object has not been deleted.
        """
        if layer is None:
            return False
        try:
            # If the C++ layer was deleted, calling id() raises RuntimeError
            layer_id = layer.id()
            return QgsProject.instance().mapLayer(layer_id) is not None
        except RuntimeError:
            return False

    def setup_layer(self, layer_var, layer_type, layer_name, style_fn, *style_args):
        """
        Ensures a layer is registered in the project and added/visible in the custom group.
        """
        exists = self.is_layer_valid(layer_var)
        if not exists:
            layer_var = QgsVectorLayer(layer_type, layer_name, "memory")
            QgsProject.instance().addMapLayer(layer_var, False)
            style_fn(layer_var, *style_args)
        elif getattr(self, '_force_restyle', False):
            style_fn(layer_var, *style_args)
        
        node = self.layer_group.findLayer(layer_var.id())
        if node is None:
            node = self.layer_group.addLayer(layer_var)
        if node:
            node.setItemVisibilityChecked(True)
        return layer_var

    def style_aga_layer(self, layer, color_hex, opacity_pct, border_width):
        props = {
            'color': hex_to_rgba(color_hex, opacity_pct),
            'outline_color': hex_to_border_rgba(color_hex, "41,128,185,255"),
            'outline_width': str(border_width),
            'outline_style': 'dash',
            'style': 'solid' if float(opacity_pct) > 0 else 'no'
        }
        symbol_layer = QgsSimpleFillSymbolLayer.create(props)
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.changeSymbolLayer(0, symbol_layer)
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def style_polygon_layer(self, layer, fill_rgba, border_rgba, border_width):
        props = {
            'color': fill_rgba,
            'outline_color': border_rgba,
            'outline_width': str(border_width),
            'style': 'solid'
        }
        symbol_layer = QgsSimpleFillSymbolLayer.create(props)
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.changeSymbolLayer(0, symbol_layer)
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def style_line_layer(self, layer, rgba, width, pen_style):
        props = {
            'color': rgba,
            'width': str(width),
            'style': 'solid'
        }
        symbol_layer = QgsSimpleLineSymbolLayer.create(props)
        symbol_layer.setPenStyle(pen_style)
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.changeSymbolLayer(0, symbol_layer)
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def style_point_layer(self, layer, fill_rgba, border_rgba, size):
        props = {
            'color': fill_rgba,
            'outline_color': border_rgba,
            'size': str(size),
            'outline_width': '1.0'
        }
        symbol_layer = QgsSimpleMarkerSymbolLayer.create(props)
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.changeSymbolLayer(0, symbol_layer)
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def style_vlos_layer(self, layer):
        """
        Styles the VLOS range circle: thin blue dash-dot outline, no fill.
        """
        color_hex = self.params.get("color_vlos", "#2d9cdb")
        opacity_pct = self.params.get("opacity_vlos", 0)
        border_width = self.params.get("linewidth_vlos", 0.8)

        props = {
            'color': hex_to_rgba(color_hex, opacity_pct),
            'outline_color': hex_to_border_rgba(color_hex, "45,156,219,255"),
            'outline_width': str(border_width),
            'outline_style': 'dash_dot',
            'style': 'solid' if float(opacity_pct) > 0 else 'no'
        }
        symbol_layer = QgsSimpleFillSymbolLayer.create(props)
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.changeSymbolLayer(0, symbol_layer)
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def on_gui_finished(self, result):
        if self.canvas.mapTool() in [self.wp_tool, self.pilot_tool]:
            self.canvas.unsetMapTool(self.canvas.mapTool())
        if hasattr(self, 'btn_draw_wp'):
            self.btn_draw_wp.setChecked(False)
        if hasattr(self, 'btn_set_pilot'):
            self.btn_set_pilot.setChecked(False)

    def toggle_waypoint_drawing(self, checked):
        if checked:
            self.btn_set_pilot.setChecked(False)
            self.canvas.setMapTool(self.wp_tool)
        else:
            if self.canvas.mapTool() == self.wp_tool:
                self.canvas.unsetMapTool(self.wp_tool)

    def toggle_pilot_setting(self, checked):
        if checked:
            self.btn_draw_wp.setChecked(False)
            self.canvas.setMapTool(self.pilot_tool)
        else:
            if self.canvas.mapTool() == self.pilot_tool:
                self.canvas.unsetMapTool(self.pilot_tool)

    def push_undo(self):
        """
        Pushes a copy of the current waypoints list onto the undo stack and clears the redo stack.
        """
        self.undo_stack.append(list(self.waypoints))
        self.redo_stack.clear()
        self.update_undo_redo_buttons()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(list(self.waypoints))
            self.waypoints = self.undo_stack.pop()
            self.rebuild_and_calculate()
            self.update_pilot_layer()
            self.update_undo_redo_buttons()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(list(self.waypoints))
            self.waypoints = self.redo_stack.pop()
            self.rebuild_and_calculate()
            self.update_pilot_layer()
            self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        if hasattr(self, 'btn_undo'):
            self.btn_undo.setEnabled(len(self.undo_stack) > 0)
        if hasattr(self, 'btn_redo'):
            self.btn_redo.setEnabled(len(self.redo_stack) > 0)

    def serialize_state(self):
        """
        Serializes the complete current planning state (waypoints, pilot, geometry_type, params) to JSON.
        """
        import json
        state = {
            "waypoints": self.waypoints,
            "pilot_pos": [self.pilot_pos.x(), self.pilot_pos.y()] if self.pilot_pos else None,
            "geometry_type": self.geometry_type,
            "params": self.params
        }
        return json.dumps(state, ensure_ascii=False)

    def deserialize_state(self, state_json):
        """
        Deserializes state JSON and restores the complete planning environment.
        """
        import json
        from qgis.core import QgsPointXY
        
        state = json.loads(state_json)
        self.waypoints = [tuple(wp) for wp in state.get("waypoints", [])]
        
        pilot_coords = state.get("pilot_pos")
        if pilot_coords:
            self.pilot_pos = QgsPointXY(pilot_coords[0], pilot_coords[1])
        else:
            self.pilot_pos = None
            
        self.geometry_type = state.get("geometry_type", "Corridor")
        self.params.update(state.get("params", {}))
        
        # Clear undo/redo stacks when re-activating a saved state
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_undo_redo_buttons()
        
        # Sync UI combobox if visible
        if hasattr(self, 'cmb_geom_type'):
            types = ["Corridor", "Circle", "Polygon"]
            if self.geometry_type in types:
                self.cmb_geom_type.blockSignals(True)
                self.cmb_geom_type.setCurrentIndex(types.index(self.geometry_type))
                self.cmb_geom_type.blockSignals(False)
                
        self.rebuild_and_calculate()
        self.update_pilot_layer()

    def transform_to_wgs84(self, point_canvas):
        """
        Transforms a point from the active QGIS Canvas CRS to EPSG:4326 WGS 84.
        """
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            wgs_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(canvas_crs, wgs_crs, QgsProject.instance())
            return transform.transform(point_canvas)
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(f"CRS-Transformationsfehler (zu WGS84): {e}", "QUCORE", Qgis.Warning)
            return point_canvas

    def transform_from_wgs84(self, point_wgs):
        """
        Transforms a point from EPSG:4326 WGS 84 to the active QGIS Canvas CRS.
        """
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            wgs_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(wgs_crs, canvas_crs, QgsProject.instance())
            return transform.transform(point_wgs)
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(f"CRS-Transformationsfehler (aus WGS84): {e}", "QUCORE", Qgis.Warning)
            return point_wgs

    def on_waypoint_clicked(self, point, button):
        """
        Handles clicks when waypoint drawing is active.
        """
        if button == Qt.LeftButton:
            pt_wgs = self.transform_to_wgs84(point)
            
            # Set default altitude to params default altitude
            def_alt = float(self.params.get("maxFlightHeight", 100.0))
            self.waypoints.append((pt_wgs.x(), pt_wgs.y(), def_alt))
            
            # Recalculate
            self.rebuild_and_calculate()
        elif button == Qt.RightButton:
            # Done drawing, turn off map tool
            self.btn_draw_wp.setChecked(False)
            self.canvas.unsetMapTool(self.wp_tool)

    def on_pilot_clicked(self, point, button):
        """
        Handles clicks when setting pilot position is active.
        """
        if button == Qt.LeftButton:
            pt_wgs = self.transform_to_wgs84(point)
            self.pilot_pos = pt_wgs
            
            # Deactivate tool
            self.btn_set_pilot.setChecked(False)
            self.canvas.unsetMapTool(self.pilot_tool)
            
            # Update layer
            self.update_pilot_layer()

    # ----------------------------------------------------
    # BERECHNUNG & LAYER REBUILDS
    # ----------------------------------------------------
    def rebuild_and_calculate(self, force_restyle=False):
        """
        Rebuilds waypoints, route, and buffer layers and re-runs the safety calculations.
        """
        self.initialize_layers(force_restyle=force_restyle)
        
        # Lock geometry type dropdown as soon as waypoints are added
        if hasattr(self, 'cmb_geom_type'):
            self.cmb_geom_type.setEnabled(len(self.waypoints) == 0)
            
        # Hide/show circle radius controls and disable parameter dialog if not Corridor
        show_circle = (self.geometry_type == "Circle")
        cd = float(self.params.get("maxCharacteristicDimension", 3.6))
        min_radius = 3.0 * cd
        
        if hasattr(self, 'spn_circle_radius'):
            self.spn_circle_radius.setMinimum(min_radius)
            if show_circle and self.waypoints:
                w = self.waypoints[0]
                rad = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
                if rad < min_radius:
                    rad = min_radius
                    alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
                    spd = w[3] if len(w) > 3 else float(self.params.get("maxVelocity", 30.0))
                    self.waypoints[0] = (w[0], w[1], alt, spd, rad)
                # Sync spinbox value without triggering recursive events
                self.spn_circle_radius.blockSignals(True)
                self.spn_circle_radius.setValue(rad)
                self.spn_circle_radius.blockSignals(False)

        if hasattr(self, 'lbl_circle_rad'):
            self.lbl_circle_rad.setVisible(show_circle)
        if hasattr(self, 'spn_circle_radius'):
            self.spn_circle_radius.setVisible(show_circle)
        if hasattr(self, 'btn_alt'):
            self.btn_alt.setEnabled(self.geometry_type == "Corridor")
        
        # 1. Update waypoints point layer
        self.lyr_waypoints.dataProvider().truncate()
        wp_features = []
        for idx, w in enumerate(self.waypoints):
            lon, lat = w[0], w[1]
            alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
            spd = w[3] if len(w) > 3 else float(self.params.get("maxVelocity", 30.0))
            fg = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
            
            f = QgsFeature(self.lyr_waypoints.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            f.setAttributes([idx, alt, spd, fg])
            wp_features.append(f)
        self.lyr_waypoints.dataProvider().addFeatures(wp_features)
        self.lyr_waypoints.updateExtents()
        self.lyr_waypoints.triggerRepaint()
        
        # 2. Update route centerline layer
        self.lyr_route.dataProvider().truncate()
        if self.geometry_type == "Corridor" and len(self.waypoints) >= 2:
            pts = [QgsPointXY(w[0], w[1]) for w in self.waypoints]
            f = QgsFeature(self.lyr_route.fields())
            f.setGeometry(QgsGeometry.fromPolylineXY(pts))
            self.lyr_route.dataProvider().addFeatures([f])
        elif self.geometry_type == "Polygon" and len(self.waypoints) >= 3:
            pts = [QgsPointXY(w[0], w[1]) for w in self.waypoints]
            pts.append(pts[0]) # close the loop
            f = QgsFeature(self.lyr_route.fields())
            f.setGeometry(QgsGeometry.fromPolylineXY(pts))
            self.lyr_route.dataProvider().addFeatures([f])
        self.lyr_route.updateExtents()
        self.lyr_route.triggerRepaint()
        
        # 3. Calculate and update buffer polygon layers
        self.lyr_fg.dataProvider().truncate()
        self.lyr_cv.dataProvider().truncate()
        self.lyr_grb.dataProvider().truncate()
        if self.lyr_aga:
            self.lyr_aga.dataProvider().truncate()
        
        if self.waypoints:
            calc_params = self.params.copy()
            if getattr(self, 'is_dragging', False):
                # Dynamically set a larger stepSize for extreme performance optimization during real-time dragging.
                # A stepSize of 1000m reduces convex hull/union computations to the absolute minimum, keeping dragging perfectly fluid.
                calc_params["stepSize"] = 1000.0
                
            fg_geom, cv_geom, grb_geom, aga_geom = BufferCalculator.generate_buffers(self.waypoints, calc_params, self.geometry_type)
            
            if not fg_geom.isEmpty():
                f_fg = QgsFeature(self.lyr_fg.fields())
                f_fg.setGeometry(fg_geom)
                self.lyr_fg.dataProvider().addFeatures([f_fg])
                
            if not cv_geom.isEmpty():
                f_cv = QgsFeature(self.lyr_cv.fields())
                f_cv.setGeometry(cv_geom)
                self.lyr_cv.dataProvider().addFeatures([f_cv])
                
            if not grb_geom.isEmpty():
                f_grb = QgsFeature(self.lyr_grb.fields())
                f_grb.setGeometry(grb_geom)
                self.lyr_grb.dataProvider().addFeatures([f_grb])
                
            if self.lyr_aga and not aga_geom.isEmpty():
                f_aga = QgsFeature(self.lyr_aga.fields())
                f_aga.setGeometry(aga_geom)
                self.lyr_aga.dataProvider().addFeatures([f_aga])
                
        self.lyr_fg.updateExtents()
        self.lyr_fg.triggerRepaint()
        
        self.lyr_cv.updateExtents()
        self.lyr_cv.triggerRepaint()
        
        self.lyr_grb.updateExtents()
        self.lyr_grb.triggerRepaint()
        
        if self.lyr_aga:
            self.lyr_aga.updateExtents()
            self.lyr_aga.triggerRepaint()
        
        # Update Status bar
        if self.waypoints:
            self.lbl_status.setText(self.tr("status_calculated", "Wegpunkte: {wp} | Puffer: Berechnet").format(wp=len(self.waypoints)))
        else:
            self.lbl_status.setText(self.tr("status_ready", "Wegpunkte: {wp} | Puffer: Bereit").format(wp=0))
        
        # Update Results Panel
        self.update_results_panel()
        
        # Avoid blocking synchronous canvas refreshes during interactive waypoint dragging
        is_dragging = False
        if hasattr(self, 'wp_tool') and self.wp_tool is not None:
            is_dragging = (self.wp_tool.dragging_idx != -1)
            # Update midpoint markers if waypoint tool is active and we are not dragging
            if not is_dragging and self.canvas.mapTool() == self.wp_tool:
                self.wp_tool.update_midpoint_markers()
        if not is_dragging:
            self.canvas.refresh()

        # Save state to QgsProject entry if not dragging
        if not is_dragging:
            try:
                state_json = self.serialize_state()
                QgsProject.instance().writeEntry("QUCORE", "state", state_json)
            except Exception:
                pass


    def update_pilot_layer(self):
        """
        Updates the pilot position layer feature and the VLOS range circle.
        """
        self.initialize_layers()
        self.lyr_pilot.dataProvider().truncate()
        if self.is_layer_valid(self.lyr_vlos):
            self.lyr_vlos.dataProvider().truncate()
        
        if self.pilot_pos:
            f = QgsFeature(self.lyr_pilot.fields())
            f.setGeometry(QgsGeometry.fromPointXY(self.pilot_pos))
            self.lyr_pilot.dataProvider().addFeatures([f])
            
            # Draw VLOS range circle around pilot position
            # Uses the exact same UTM buffer pattern as BufferCalculator.generate_buffers (Circle mode)
            if self.is_layer_valid(self.lyr_vlos):
                try:
                    uas_type = self.params.get("uas_type", "FixedWing")
                    cd = float(self.params.get("maxCharacteristicDimension", 3.6))
                    is_mc = (uas_type in ["Multikopter", "Rotorcraft"])
                    
                    # ALOS calculation (same formula as VlosCalculatorDialog)
                    if is_mc:
                        alos = 327.0 * cd + 20.0
                    else:
                        alos = 490.0 * cd + 30.0
                    
                    # DLOS = 0.3 * GV (assume max 5000m ground visibility)
                    dlos = 0.3 * 5000.0
                    vlos_range = min(alos, dlos)
                    
                    # Same pattern as BufferCalculator.generate_buffers Circle mode
                    lon = self.pilot_pos.x()
                    lat = self.pilot_pos.y()
                    from .buffer_calculator import get_utm_epsg, BUFFER_SEGMENTS
                    utm_epsg = get_utm_epsg(lon, lat)
                    
                    src_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                    dest_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                    
                    project = QgsProject.instance()
                    transform = QgsCoordinateTransform(src_crs, dest_crs, project)
                    inverse_transform = QgsCoordinateTransform(dest_crs, src_crs, project)
                    
                    pt_wgs = QgsPointXY(lon, lat)
                    center_utm = transform.transform(pt_wgs)
                    
                    circle_geom = QgsGeometry.fromPointXY(center_utm).buffer(vlos_range, BUFFER_SEGMENTS)
                    circle_geom.transform(inverse_transform)
                    
                    f_vlos = QgsFeature(self.lyr_vlos.fields())
                    f_vlos.setGeometry(circle_geom)
                    self.lyr_vlos.dataProvider().addFeatures([f_vlos])
                except Exception as e:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(f"VLOS circle error: {e}", "DroneCorridorPlanner", Qgis.Warning)
        
        self.lyr_pilot.updateExtents()
        self.lyr_pilot.triggerRepaint()
        if self.is_layer_valid(self.lyr_vlos):
            self.lyr_vlos.updateExtents()
            self.lyr_vlos.triggerRepaint()
        self.canvas.refresh()

        try:
            state_json = self.serialize_state()
            QgsProject.instance().writeEntry("QUCORE", "state", state_json)
        except Exception:
            pass


    def update_results_panel(self):
        """
        Updates the results summary panel with calculated buffer widths.
        Shows min–max range when waypoint parameters vary.
        """
        if not hasattr(self, 'lbl_results'):
            return
            
        if not self.waypoints:
            self.lbl_results.setText(
                f"<i style='color:#999;'>{self.tr('results_no_data', 'Noch keine Wegpunkte gesetzt.')}</i>"
            )
            if hasattr(self, 'sora_viz'):
                self.sora_viz.update_values([], [], [], [], [])
            return
        
        try:
            from .buffer_calculator import BufferCalculator
            
            r_fg_list = []
            r_cv_list = []
            r_grb_list = []
            s_cv_list = []
            s_grb_list = []
            h_fg_list = []
            h_cv_list = []
            
            for w in self.waypoints:
                h = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
                spd = w[3] if len(w) > 3 else float(self.params.get("maxVelocity", 30.0))
                fg = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
                
                params_wp = self.params.copy()
                params_wp["maxVelocity"] = spd
                params_wp["corridorWidth"] = fg
                
                r_fg, r_cv, r_grb, h_cv = BufferCalculator.calculate_buffer_widths(h, params_wp)
                
                r_fg_list.append(r_fg)
                r_cv_list.append(r_cv)
                r_grb_list.append(r_grb)
                s_cv_list.append(r_cv - r_fg)
                s_grb_list.append(r_grb - r_cv)
                h_fg_list.append(h)
                h_cv_list.append(h_cv)
            
            def fmt_range(values, unit="m"):
                mn, mx = min(values), max(values)
                if abs(mn - mx) < 0.05:
                    return f"{mn:.1f} {unit}"
                return f"{mn:.1f}–{mx:.1f} {unit}"
            
            lbl_rfg = "R<sub>FG</sub>"
            lbl_rcv = "R<sub>CV</sub>"
            lbl_rgrb = "R<sub>GRB</sub>"
            
            html = (
                f"<table style='border-collapse:collapse; width:100%; font-size:11px;'>"
                f"<tr>"
                f"<td style='padding: 2px 2px;'><b>{lbl_rfg}:</b> {fmt_range(r_fg_list)}</td>"
                f"<td style='padding: 2px 2px; text-align:center;'><b>{lbl_rcv}:</b> {fmt_range(r_cv_list)}</td>"
                f"<td style='padding: 2px 2px; text-align:right;'><b>{lbl_rgrb}:</b> {fmt_range(r_grb_list)}</td>"
                f"</tr>"
                f"</table>"
            )
            
            self.lbl_results.setText(html)
            if hasattr(self, 'sora_viz'):
                self.sora_viz.update_values(r_fg_list, s_cv_list, s_grb_list, h_fg_list, h_cv_list)
        except Exception:
            self.lbl_results.setText(
                f"<i style='color:#c00;'>{self.tr('results_error', 'Berechnungsfehler')}</i>"
            )
            if hasattr(self, 'sora_viz'):
                self.sora_viz.update_values([], [], [], [], [])

    # ----------------------------------------------------
    # DIALOG ACTIONS
    # ----------------------------------------------------
    def open_parameter_dialog(self):
        params_backup = dict(self.params)
        dialog = ParameterDialog(self.gui, self.params, self.waypoints)
        
        # Connect live preview callback
        dialog.on_change_callback = self.on_parameter_dialog_changed
        
        if dialog.exec_() == QDialog.Accepted:
            self.push_undo() # Push state before finalizing accepted changes
            self.on_parameter_dialog_changed(dialog.get_parameters())
        else:
            # Restore original parameters
            self.params.clear()
            self.params.update(params_backup)
            
            # The dialog's reject() has already restored self.waypoints, 
            # so we just need to trigger a final recalculation to redraw the original state!
            self.rebuild_and_calculate()

    def on_parameter_dialog_changed(self, new_params):
        old_v0 = self.params.get("maxVelocity", 30.0)
        self.params.update(new_params)
        
        new_v0 = self.params.get("maxVelocity", 30.0)
        new_cd = self.params.get("maxCharacteristicDimension", 3.6)
        min_fg = 3.0 * new_cd
        
        for idx in range(len(self.waypoints)):
            w = self.waypoints[idx]
            alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
            spd = w[3] if len(w) > 3 else float(self.params.get("maxVelocity", 30.0))
            fg = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
            
            if abs(new_v0 - old_v0) > 1e-5:
                spd = new_v0
            elif spd > new_v0:
                spd = new_v0
                
            if fg < min_fg:
                fg = min_fg
                
            self.waypoints[idx] = (w[0], w[1], alt, spd, fg)
            
        self.rebuild_and_calculate()
        self.update_pilot_layer()

    def open_advanced_settings_dialog(self):
        dialog = AdvancedSettingsDialog(self.gui, self.config_path, self.params.get("stepSize", 50.0), current_params=self.params)
        if dialog.exec_() == QDialog.Accepted:
            self.push_undo()
            self.params["stepSize"] = dialog.get_step_size()
            self.params.update(dialog.get_style_params())
            self.rebuild_and_calculate(force_restyle=True)

    def open_vlos_calculator(self):
        uas_type = self.params.get("uas_type", "FixedWing")
        cd = float(self.params.get("maxCharacteristicDimension", 3.6))
        
        # Save a single undo state when opening the dialog
        self.push_undo()
        
        def on_vlos_changed(new_cd, new_uas_type):
            self.params["maxCharacteristicDimension"] = new_cd
            self.params["uas_type"] = new_uas_type
            
            # Enforce Flight Geography width min limit (3 * CD) on all waypoints
            min_fg = 3.0 * new_cd
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
                spd = w[3] if len(w) > 3 else float(self.params.get("maxVelocity", 30.0))
                fg = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
                if fg < min_fg:
                    fg = min_fg
                self.waypoints[idx] = (w[0], w[1], alt, spd, fg)
                
            self.rebuild_and_calculate()
            self.update_pilot_layer()

        dialog = VlosCalculatorDialog(self.gui, uas_type, cd, current_params=self.params)
        dialog.on_change_callback = on_vlos_changed
        dialog.exec_()

    def open_population_density_dialog(self):
        if not self.is_layer_valid(self.lyr_aga):
            QMessageBox.warning(
                self.gui,
                self.tr("error_empty_aa_title", "Keine Adjacent Area"),
                self.tr("error_empty_aa_text", "Es existiert kein gültiger 'Adjacent Area (AA)'-Layer. Bitte erstellen Sie zuerst eine Flugplanung.")
            )
            return
            
        # Check if the layer contains at least one non-empty polygon feature
        has_features = False
        for feature in self.lyr_aga.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                has_features = True
                break
                
        if not has_features:
            QMessageBox.warning(
                self.gui,
                self.tr("error_empty_aa_title", "Keine Adjacent Area"),
                self.tr("error_empty_aa_text", "Der 'Adjacent Area (AA)'-Layer enthält keine gültige Geometrie. Bitte erstellen Sie zuerst eine Flugplanung.")
            )
            return
            
        from .population_density_dialog import PopulationDensityDialog
        dialog = PopulationDensityDialog(self.gui, self.lyr_aga, current_params=self.params)
        dialog.exec_()

    def open_grb_density_dialog(self):
        if not self.is_layer_valid(self.lyr_grb):
            QMessageBox.warning(
                self.gui,
                self.tr("error_empty_grb_title", "Kein Ground Risk Buffer"),
                self.tr("error_empty_grb_text", "Es existiert kein gültiger 'Ground Risk Buffer (GRB)'-Layer. Bitte erstellen Sie zuerst eine Flugplanung.")
            )
            return
            
        # Check if the layer contains at least one non-empty polygon feature
        has_features = False
        for feature in self.lyr_grb.getFeatures():
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                has_features = True
                break
                
        if not has_features:
            QMessageBox.warning(
                self.gui,
                self.tr("error_empty_grb_title", "Kein Ground Risk Buffer"),
                self.tr("error_empty_grb_text", "Der 'Ground Risk Buffer (GRB)'-Layer enthält keine gültige Geometrie. Bitte erstellen Sie zuerst eine Flugplanung.")
            )
            return
            
        from .grb_density_dialog import GrbDensityDialog
        dialog = GrbDensityDialog(self.gui, self.lyr_grb, current_params=self.params)
        dialog.exec_()

    def open_altitude_table(self):
        if not self.waypoints:
            QMessageBox.information(
                self.gui, 
                self.tr("msg_no_wp_title", "Keine Wegpunkte"), 
                self.tr("msg_no_wp_text", "Zeichnen Sie bitte zuerst Wegpunkte auf der Karte ein.")
            )
            return
            
        original_waypoints = list(self.waypoints)
        
        def on_waypoint_edited():
            updated_params = dialog.get_waypoint_params()
            for idx in range(len(self.waypoints)):
                lon, lat, new_alt, new_spd, new_fg = updated_params[idx]
                self.waypoints[idx] = (lon, lat, new_alt, new_spd, new_fg)
            self.rebuild_and_calculate()
            
        dialog = AltitudeTableDialog(self.gui, self.waypoints, self.params, on_change_callback=on_waypoint_edited)
        if dialog.exec_() == QDialog.Accepted:
            # Commit changes and add to undo stack
            self.undo_stack.append(list(original_waypoints))
            self.redo_stack.clear()
            self.update_undo_redo_buttons()
            # Already updated on the map, but a final calculation ensures everything is clean
            self.rebuild_and_calculate()
        else:
            # Revert to original waypoints on cancel
            self.waypoints = original_waypoints
            self.rebuild_and_calculate()

    def reset_planning(self):
        reply = QMessageBox.question(
            self.gui, 
            self.tr("msg_reset_title", "Planung zurücksetzen"), 
            self.tr("msg_reset_text", "Möchten Sie die gesamte Route, den Piloten und alle berechneten Korridore löschen?"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.push_undo() # Save state before reset
            # Clear state
            self.waypoints = []
            self.pilot_pos = None
            
            # Remove QgsProject state entry so it doesn't get restored on reload/reopen
            try:
                QgsProject.instance().removeEntry("QUCORE", "state")
            except Exception:
                pass
            
            # Clear layers
            self.rebuild_and_calculate()
            self.update_pilot_layer()

    def import_active_layer(self):
        from qgis.core import QgsWkbTypes, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer, NULL
        from PyQt5.QtWidgets import QMessageBox
        
        layer = self.iface.activeLayer()
        if not layer or not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(
                self.gui,
                self.tr("msg_invalid_layer_title", "Ungültiger Layer-Typ"),
                self.tr("msg_invalid_layer_text", "Bitte wählen Sie zuerst einen Vektor-Layer vom Typ Linie (Line) oder Punkt (Point / Multi-Point) in QGIS aus.")
            )
            return

        # Check if the layer contains our persistent state attribute (reactivation)
        fields = layer.fields()
        state_idx = fields.indexOf("qucore_state")
        if state_idx != -1:
            features = list(layer.getFeatures())
            if features:
                state_json = features[0].attribute(state_idx)
                if state_json and state_json != NULL and str(state_json) != 'NULL' and str(state_json) != '':
                    try:
                        self.push_undo() # Save state before restoring
                        self.deserialize_state(str(state_json))
                        QMessageBox.information(
                            self.gui,
                            self.tr("msg_import_success_title", "Planung reaktiviert"),
                            "Interaktive Drohnen-Korridorplanung erfolgreich aus Layer '{name}' reaktiviert!".format(name=layer.name())
                        )
                        return
                    except Exception as e:
                        QMessageBox.warning(
                            self.gui,
                            self.tr("msg_import_error_title", "Reaktivierungsfehler"),
                            "Fehler beim Reaktivieren der Planung aus Layer:\n{error}".format(error=str(e))
                        )

        geom_type = layer.geometryType()
        if self.geometry_type == "Polygon":
            # In Polygon mode, we only allow Polygon layers (no Lines or Points!)
            allowed_geoms = [QgsWkbTypes.PolygonGeometry]
            if geom_type not in allowed_geoms:
                QMessageBox.warning(
                    self.gui,
                    self.tr("msg_invalid_layer_title", "Ungültiger Layer-Typ"),
                    self.tr("msg_invalid_polygon_layer_text", "Im Polygon-Modus können nur Vektor-Layer vom Typ Polygon eingelesen werden.")
                )
                return
        else:
            # In Corridor/Circle mode, we only allow Line and Point layers (no Polygons!)
            allowed_geoms = [QgsWkbTypes.LineGeometry, QgsWkbTypes.PointGeometry]
            if geom_type not in allowed_geoms:
                if geom_type == QgsWkbTypes.PolygonGeometry:
                    # Specific helpful error explaining they must switch to Polygon mode first
                    QMessageBox.warning(
                        self.gui,
                        self.tr("msg_invalid_layer_title", "Ungültiger Layer-Typ"),
                        self.tr("msg_polygon_mode_required_text", "Ein Polygon-Layer kann nur im Planungsmodus 'Polygon' eingelesen werden. Bitte wechseln Sie zuerst den Geometrietyp auf 'Polygon'.")
                    )
                else:
                    QMessageBox.warning(
                        self.gui,
                        self.tr("msg_invalid_layer_title", "Ungültiger Layer-Typ"),
                        self.tr("msg_invalid_layer_text", "Bitte wählen Sie zuerst einen Vektor-Layer vom Typ Linie (Line) oder Punkt (Point / Multi-Point) in QGIS aus.")
                    )
                return

        self.push_undo() # Save state before importing

        try:
            # Setup coordinate transform to WGS 84 (EPSG:4326)
            src_crs = layer.crs()
            dest_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(src_crs, dest_crs, QgsProject.instance())

            default_alt = float(self.params.get("maxFlightHeight", 100.0))
            default_spd = float(self.params.get("maxVelocity", 30.0))
            default_fg = float(self.params.get("corridorWidth", 50.0))

            raw_waypoints = []

            # Check if columns for altitude, speed, or width exist
            fields = layer.fields()
            
            def find_field(names):
                for name in names:
                    idx = fields.indexOf(name)
                    if idx != -1:
                        return idx
                return -1

            alt_idx = find_field(["altitude", "height", "hoehe", "h"])
            spd_idx = find_field(["speed", "velocity", "geschwindigkeit", "v", "v0"])
            fg_idx = find_field(["fg_width", "width", "breite", "w_fg", "w"])

            # Iterate through features
            for feature in layer.getFeatures():
                geom = feature.geometry()
                if geom.isNull():
                    continue

                # Read attributes if fields exist
                alt = default_alt
                if alt_idx != -1:
                    val = feature.attribute(alt_idx)
                    # NULL is a QVariant NULL representation which is not None in some python mappings, check both
                    from qgis.core import NULL
                    if val is not None and val != NULL and str(val) != 'NULL' and str(val) != '':
                        try:
                            alt = float(val)
                        except ValueError:
                            pass

                spd = default_spd
                if spd_idx != -1:
                    val = feature.attribute(spd_idx)
                    from qgis.core import NULL
                    if val is not None and val != NULL and str(val) != 'NULL' and str(val) != '':
                        try:
                            spd = float(val)
                        except ValueError:
                            pass

                fg = default_fg
                if fg_idx != -1:
                    val = feature.attribute(fg_idx)
                    from qgis.core import NULL
                    if val is not None and val != NULL and str(val) != 'NULL' and str(val) != '':
                        try:
                            fg = float(val)
                        except ValueError:
                            pass

                # Extract vertices from geometry
                for vertex in geom.vertices():
                    from qgis.core import QgsPointXY
                    pt_xy = QgsPointXY(vertex.x(), vertex.y())
                    pt_wgs = transform.transform(pt_xy)
                    raw_waypoints.append((pt_wgs.x(), pt_wgs.y(), alt, spd, fg))

            # Filter out consecutive duplicate points (within 1e-7 degrees, ~1cm)
            filtered_waypoints = []
            for wp in raw_waypoints:
                if not filtered_waypoints:
                    filtered_waypoints.append(wp)
                else:
                    last = filtered_waypoints[-1]
                    dx = wp[0] - last[0]
                    dy = wp[1] - last[1]
                    dist = math.sqrt(dx*dx + dy*dy)
                    if dist > 1e-7:
                        filtered_waypoints.append(wp)

            if not filtered_waypoints:
                raise ValueError("Keine gültigen Geometrie-Stützpunkte im ausgewählten Layer gefunden.")

            # If Polygon mode, and first and last points are identical, discard the last one to let renderer close it dynamically
            if self.geometry_type == "Polygon" and len(filtered_waypoints) >= 3:
                first = filtered_waypoints[0]
                last = filtered_waypoints[-1]
                dx = first[0] - last[0]
                dy = first[1] - last[1]
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < 1e-7:
                    filtered_waypoints.pop()

            self.waypoints = filtered_waypoints
            self.redo_stack.clear()
            self.update_undo_redo_buttons()

            # Set geometry type
            if self.geometry_type == "Polygon":
                # Keep it as Polygon mode!
                pass
            elif geom_type == QgsWkbTypes.LineGeometry:
                self.geometry_type = "Corridor"
            elif geom_type == QgsWkbTypes.PointGeometry:
                self.geometry_type = "Corridor"

            # Sync GUI geometry type selection combobox if visible
            if hasattr(self, 'cmb_geom_type'):
                types = ["Corridor", "Circle", "Polygon"]
                if self.geometry_type in types:
                    self.cmb_geom_type.blockSignals(True)
                    self.cmb_geom_type.setCurrentIndex(types.index(self.geometry_type))
                    self.cmb_geom_type.blockSignals(False)

            self.rebuild_and_calculate()
            self.update_pilot_layer()

            QMessageBox.information(
                self.gui,
                self.tr("msg_import_success_title", "Import erfolgreich"),
                self.tr("msg_import_active_success", "Import abgeschlossen!\n{count} Wegpunkte aus Layer '{name}' geladen.")
                    .format(count=len(self.waypoints), name=layer.name())
            )

        except Exception as e:
            # Revert state on failure
            self.undo() if self.undo_stack else None
            QMessageBox.critical(
                self.gui,
                self.tr("msg_import_error_title", "Import Fehler"),
                self.tr("msg_import_error_text", "Fehler beim Importieren der Datei:\n{error}").format(error=str(e))
            )

    def write_to_gpkg(self, file_path):
        """
        Saves all current planning layers into a single GeoPackage file,
        adding a hidden 'qucore_state' field to the Wegpunkte layer.
        Returns a tuple: (success_boolean, error_msg_string)
        """
        from qgis.core import QgsVectorFileWriter, QgsProject, QgsField, QgsFeature, QgsGeometry, QgsVectorLayer
        from PyQt5.QtCore import QVariant
        import os

        if not self.waypoints:
            return False, "Es gibt keine Wegpunkte zum Exportieren."

        if not file_path.lower().endswith('.gpkg'):
            file_path += '.gpkg'

        # 1. Prepare serialize state string
        state_json = self.serialize_state()

        # 2. Add the field "qucore_state" temporarily to waypoints memory layer
        dp = self.lyr_waypoints.dataProvider()
        fields = self.lyr_waypoints.fields()
        state_idx = fields.indexOf("qucore_state")
        
        if state_idx == -1:
            dp.addAttributes([QgsField("qucore_state", QVariant.String, len=100000)])
            self.lyr_waypoints.updateFields()
            fields = self.lyr_waypoints.fields()
            state_idx = fields.indexOf("qucore_state")

        # Set the state JSON attribute on the first feature of Wegpunkte
        self.lyr_waypoints.startEditing()
        for f in self.lyr_waypoints.getFeatures():
            f.setAttribute(state_idx, state_json)
            self.lyr_waypoints.updateFeature(f)
        self.lyr_waypoints.commitChanges()

        # Export all available layers to the GPKG!
        layers_to_export = [
            (self.lyr_waypoints, "Wegpunkte"),
            (self.lyr_route, "Flugweg_Mittelachse"),
            (self.lyr_fg, "Flight_Geography_FG"),
            (self.lyr_cv, "Contingency_Volume_CV"),
            (self.lyr_grb, "Ground_Risk_Buffer_GRB")
        ]
        if self.is_layer_valid(self.lyr_aga):
            layers_to_export.append((self.lyr_aga, "Adjacent_Area_AA"))
        if self.is_layer_valid(self.lyr_pilot) and self.pilot_pos:
            layers_to_export.append((self.lyr_pilot, "Pilotenposition"))
        if self.is_layer_valid(self.lyr_vlos) and self.pilot_pos:
            layers_to_export.append((self.lyr_vlos, "VLOS_Reichweite"))

        # Setup vector file writer options
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        
        transform_context = QgsProject.instance().transformContext()

        error_occurred = False
        error_msg = ""
        first_layer = True

        for lyr, layer_name in layers_to_export:
            if not self.is_layer_valid(lyr):
                continue
            
            options.layerName = layer_name
            if not first_layer:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            err, err_str, path, new_lyr_name = QgsVectorFileWriter.writeAsVectorFormatV3(
                lyr,
                file_path,
                transform_context,
                options
            )
            
            if err == QgsVectorFileWriter.NoError:
                first_layer = False
            else:
                error_occurred = True
                error_msg = err_str
                break

        # Remove the temporary qucore_state attribute from waypoints layer
        state_idx = self.lyr_waypoints.fields().indexOf("qucore_state")
        if state_idx != -1:
            self.lyr_waypoints.startEditing()
            dp.deleteAttributes([state_idx])
            self.lyr_waypoints.commitChanges()
            self.lyr_waypoints.updateFields()

        if error_occurred:
            return False, error_msg

        return True, None

    def save_as_persistent_layer(self):
        """
        Saves all current planning layers into a single GeoPackage file,
        adding a hidden 'qucore_state' field to the Wegpunkte layer,
        and adds them permanently to the QGIS project.
        """
        from qgis.core import QgsProject, QgsVectorLayer
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        if not self.waypoints:
            QMessageBox.warning(
                self.gui,
                self.tr("msg_export_error_title", "Export Fehler"),
                self.tr("msg_export_no_wp_text", "Es gibt keine Wegpunkte zum Exportieren.")
            )
            return

        from PyQt5.QtCore import QDate
        from qgis.core import QgsSettings
        settings = QgsSettings()
        last_dir = settings.value("/QUCORE/last_export_dir", "")

        date_str = QDate.currentDate().toString("yyyyMMdd")
        default_filename = f"QUCORE-Route_{date_str}.gpkg"
        default_path = os.path.join(last_dir, default_filename) if last_dir else default_filename

        file_path, _ = QFileDialog.getSaveFileName(
            self.gui,
            self.tr("dialog_save_persistent_title", "Planung als persistenten Layer (GeoPackage) speichern"),
            default_path,
            "GeoPackage (*.gpkg)"
        )
        if not file_path:
            return

        # Save the directory path for next time
        settings.setValue("/QUCORE/last_export_dir", os.path.dirname(file_path))

        # Ask user for the layer group name
        from PyQt5.QtWidgets import QLineEdit
        default_group_name = "QUCORE-Persistente_Layer"
        group_name, ok = QInputDialog.getText(
            self.gui,
            self.tr("group_name_dialog_title", "Layer-Gruppe benennen"),
            self.tr("group_name_dialog_label", "Geben Sie einen Namen für die Layer-Gruppe im QGIS-Projekt ein:"),
            QLineEdit.Normal,
            default_group_name
        )
        if not ok:
            return
        
        group_name = group_name.strip()
        if not group_name:
            group_name = default_group_name

        if not file_path.lower().endswith('.gpkg'):
            file_path += '.gpkg'

        success, error_msg = self.write_to_gpkg(file_path)

        if not success:
            QMessageBox.critical(
                self.gui,
                self.tr("msg_save_error_title", "Speicherfehler"),
                self.tr("msg_save_error_text", "Fehler beim Speichern in GeoPackage:\n{error}").format(error=error_msg)
            )
            return

        # Load the persistent GPKG layers to the project
        exported_layers = []
        layers_to_add = [
            ("Wegpunkte", self.lyr_waypoints),
            ("Flugweg_Mittelachse", self.lyr_route),
            ("Flight_Geography_FG", self.lyr_fg),
            ("Contingency_Volume_CV", self.lyr_cv),
            ("Ground_Risk_Buffer_GRB", self.lyr_grb)
        ]
        if self.is_layer_valid(self.lyr_aga):
            layers_to_add.append(("Adjacent_Area_AA", self.lyr_aga))
        if self.is_layer_valid(self.lyr_pilot) and self.pilot_pos:
            layers_to_add.append(("Pilotenposition", self.lyr_pilot))
        if self.is_layer_valid(self.lyr_vlos) and self.pilot_pos:
            layers_to_add.append(("VLOS_Reichweite", self.lyr_vlos))

        for layer_name, orig_lyr in layers_to_add:
            uri = f"{file_path}|layerName={layer_name}"
            gpkg_layer = QgsVectorLayer(uri, orig_lyr.name() + " (Persistent)", "ogr")
            if gpkg_layer.isValid():
                exported_layers.append((gpkg_layer, orig_lyr))

        project = QgsProject.instance()
        root = project.layerTreeRoot()
        persistent_group = root.findGroup(group_name)
        if persistent_group is None:
            persistent_group = root.insertGroup(0, group_name)
            persistent_group.setItemVisibilityChecked(True)

        for gpkg_lyr, orig_lyr in exported_layers:
            project.addMapLayer(gpkg_lyr, False)
            persistent_group.addLayer(gpkg_lyr)
            gpkg_lyr.setRenderer(orig_lyr.renderer().clone())
            gpkg_lyr.triggerRepaint()

        QMessageBox.information(
            self.gui,
            self.tr("msg_save_success_title", "Speichern erfolgreich"),
            self.tr("msg_save_success_text", "Die Korridorplanung wurde erfolgreich als dauerhafter GeoPackage-Layer gespeichert!\n\nDatei: {file_path}\n\nDie Layer wurden zur Gruppe '{group_name}' hinzugefügt.")
                .format(file_path=file_path, group_name=group_name)
        )

    def capture_map_views(self):
        """
        Captures three map screenshots:
        1. Overview (zoomed to safety corridors with a 15% margin)
        2. Start takeoff area (500x500m zoom around waypoint 0)
        3. Landing area (500x500m zoom around last waypoint)
        Restores the user's original map extent afterward.
        """
        import uuid
        import tempfile
        from PyQt5.QtCore import QSize
        from qgis.core import (
            QgsRectangle, 
            QgsCoordinateTransform, 
            QgsCoordinateReferenceSystem, 
            QgsProject,
            QgsMapSettings,
            QgsMapRendererSequentialJob
        )
        
        canvas = self.iface.mapCanvas()
        
        overview_path = os.path.join(tempfile.gettempdir(), f"map_overview_{uuid.uuid4().hex[:8]}.png")
        start_path = None
        end_path = None
        
        def render_extent_to_image(extent, filepath, width=1000, height=700):
            # Create offline map settings using active canvas layers and configurations
            settings = QgsMapSettings(canvas.mapSettings())
            settings.setExtent(extent)
            settings.setOutputSize(QSize(width, height))
            
            # Execute sequential render job synchronously
            job = QgsMapRendererSequentialJob(settings)
            job.start()
            job.waitForFinished()
            
            # Save final rendered image
            image = job.renderedImage()
            image.save(filepath, "PNG")
            
        try:
            # 1. Overview Map Extent: zoom to ground risk buffer (GRB) or Flight Geography (FG)
            overview_extent = canvas.extent()
            extent_layer = self.lyr_grb if self.is_layer_valid(self.lyr_grb) else self.lyr_fg
            if self.is_layer_valid(extent_layer) and not extent_layer.extent().isEmpty():
                extent = extent_layer.extent()
                canvas_crs = canvas.mapSettings().destinationCrs()
                wgs_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                transform = QgsCoordinateTransform(wgs_crs, canvas_crs, QgsProject.instance())
                overview_extent = transform.transformBoundingBox(extent)
                # Grow by 15% margin
                overview_extent.grow(overview_extent.width() * 0.15)
                
            render_extent_to_image(overview_extent, overview_path, width=1000, height=700)
            
            # Detailed views: only if Corridor/Polygon and we have >= 2 waypoints
            if self.geometry_type != "Circle" and len(self.waypoints) >= 2:
                # Helper to get 500x500m bounding box in canvas CRS
                def get_500m_extent(wp):
                    lon, lat = wp[0], wp[1]
                    import math
                    cos_lat = math.cos(math.radians(lat))
                    delta_lat = 250.0 / 111111.0
                    delta_lon = 250.0 / (111111.0 * cos_lat) if cos_lat > 0.01 else delta_lat
                    
                    rect_wgs = QgsRectangle(lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat)
                    canvas_crs = canvas.mapSettings().destinationCrs()
                    wgs_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                    transform = QgsCoordinateTransform(wgs_crs, canvas_crs, QgsProject.instance())
                    return transform.transformBoundingBox(rect_wgs)
                
                # 2. Start Map (waypoint 0)
                start_extent = get_500m_extent(self.waypoints[0])
                start_path = os.path.join(tempfile.gettempdir(), f"map_start_{uuid.uuid4().hex[:8]}.png")
                render_extent_to_image(start_extent, start_path, width=800, height=560)
                
                # 3. End Map (last waypoint)
                end_extent = get_500m_extent(self.waypoints[-1])
                end_path = os.path.join(tempfile.gettempdir(), f"map_end_{uuid.uuid4().hex[:8]}.png")
                render_extent_to_image(end_extent, end_path, width=800, height=560)
                
        except Exception:
            try:
                # Fallback to current canvas view
                render_extent_to_image(canvas.extent(), overview_path, width=1000, height=700)
            except Exception:
                pass
                
        return overview_path, start_path, end_path

    # ----------------------------------------------------
    # FILE IMPORTS / EXPORTS
    # ----------------------------------------------------
    def import_file(self):
        from qgis.core import QgsSettings
        settings = QgsSettings()
        last_dir = settings.value("/QUCORE/last_import_dir", "")

        file_path, _ = QFileDialog.getOpenFileName(
            self.gui, 
            self.tr("dialog_import_title", "Datei importieren"), 
            last_dir, 
            "Planungsdateien (*.dipul *.kml *.flightplan *.geojson *.gpkg);;dipul Planungsdatei (*.dipul);;KML Geometriedatei (*.kml);;SkyDemon Flugplan (*.flightplan);;GeoJSON (*.geojson);;GeoPackage (*.gpkg)"
        )
        if not file_path:
            return

        settings.setValue("/QUCORE/last_import_dir", os.path.dirname(file_path))
            
        self.push_undo() # Save state before import
        try:
            imported_geom_type = "Corridor"
            if file_path.lower().endswith('.dipul'):
                waypoints, pilot_pos, width, max_height, params, geom_type = ImporterExporter.import_dipul(file_path)
                self.waypoints = waypoints
                self.pilot_pos = pilot_pos
                self.params.update(params)
                imported_geom_type = geom_type
            elif file_path.lower().endswith('.flightplan'):
                waypoints, pilot_pos, width, max_height, params, geom_type = ImporterExporter.import_flightplan(file_path)
                self.waypoints = waypoints
                self.pilot_pos = pilot_pos
                self.params.update(params)
                imported_geom_type = geom_type
            elif file_path.lower().endswith('.geojson'):
                waypoints, pilot_pos, width, max_height, params, geom_type = ImporterExporter.import_geojson(file_path)
                self.waypoints = waypoints
                self.pilot_pos = pilot_pos
                self.params.update(params)
                imported_geom_type = geom_type
            elif file_path.lower().endswith('.gpkg'):
                uri = f"{file_path}|layerName=Wegpunkte"
                gpkg_layer = QgsVectorLayer(uri, "temp_wegpunkte", "ogr")
                if gpkg_layer.isValid():
                    fields = gpkg_layer.fields()
                    state_idx = fields.indexOf("qucore_state")
                    if state_idx != -1:
                        features = list(gpkg_layer.getFeatures())
                        if features:
                            state_json = features[0].attribute(state_idx)
                            if state_json and str(state_json) != 'NULL' and str(state_json) != '':
                                self.deserialize_state(str(state_json))
                                imported_geom_type = self.geometry_type
                            else:
                                raise ValueError("Die GPKG-Datei enthält keine gespeicherte Planung (qucore_state fehlt oder leer).")
                        else:
                            raise ValueError("Die GPKG-Datei enthält keine Features im Wegpunkte-Layer.")
                    else:
                        raise ValueError("Der Wegpunkte-Layer in der GPKG-Datei enthält kein qucore_state-Feld.")
                else:
                    raise ValueError("Der Wegpunkte-Layer konnte nicht aus der GeoPackage-Datei geladen werden.")
            else:
                # KML
                waypoints, pilot_pos, geom_type = ImporterExporter.import_kml(file_path)
                self.waypoints = waypoints
                self.pilot_pos = pilot_pos
                imported_geom_type = geom_type
                
            self.geometry_type = imported_geom_type
            if hasattr(self, 'cmb_geom_type'):
                types = ["Corridor", "Circle", "Polygon"]
                if self.geometry_type in types:
                    self.cmb_geom_type.blockSignals(True)
                    self.cmb_geom_type.setCurrentIndex(types.index(self.geometry_type))
                    self.cmb_geom_type.blockSignals(False)
                
            self.rebuild_and_calculate()
            self.update_pilot_layer()
            
            QMessageBox.information(
                self.gui, 
                self.tr("msg_import_success_title", "Import erfolgreich"), 
                self.tr("msg_import_success_text", "Import abgeschlossen!\n{count} Wegpunkte geladen.").format(count=len(self.waypoints))
            )
        except Exception as e:
            QMessageBox.critical(
                self.gui, 
                self.tr("msg_import_error_title", "Import Fehler"), 
                self.tr("msg_import_error_text", "Fehler beim Importieren der Datei:\n{error}").format(error=str(e))
            )

    def export_file(self):
        if not self.waypoints:
            QMessageBox.warning(
                self.gui, 
                self.tr("msg_export_error_title", "Export Fehler"), 
                self.tr("msg_export_no_wp_text", "Es gibt keine Wegpunkte zum Exportieren.")
            )
            return
            
        from PyQt5.QtCore import QDate
        from qgis.core import QgsSettings
        settings = QgsSettings()
        last_dir = settings.value("/QUCORE/last_export_dir", "")

        date_str = QDate.currentDate().toString("yyyyMMdd")
        default_filename = f"QUCORE-Route_{date_str}"
        default_path = os.path.join(last_dir, default_filename) if last_dir else default_filename

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.gui, 
            self.tr("dialog_export_file_title", "Datei exportieren"), 
            default_path, 
            "dipul Planungsdatei (*.dipul);;KML Geometriedatei (*.kml);;SkyDemon Flugplan (*.flightplan);;GeoJSON (*.geojson);;GeoPackage (*.gpkg);;SORA Dokumentations-Export (*.docx)"
        )
        if not file_path:
            return

        settings.setValue("/QUCORE/last_export_dir", os.path.dirname(file_path))
            
        # Ensure correct extension
        is_kml = file_path.lower().endswith('.kml') or "kml" in selected_filter.lower()
        is_flightplan = file_path.lower().endswith('.flightplan') or "flightplan" in selected_filter.lower()
        is_geojson = file_path.lower().endswith('.geojson') or "geojson" in selected_filter.lower()
        is_gpkg = file_path.lower().endswith('.gpkg') or "gpkg" in selected_filter.lower()
        is_docx = file_path.lower().endswith('.docx') or "docx" in selected_filter.lower()
        
        if is_kml and not file_path.lower().endswith('.kml'):
            file_path += '.kml'
        elif is_flightplan and not file_path.lower().endswith('.flightplan'):
            file_path += '.flightplan'
        elif is_geojson and not file_path.lower().endswith('.geojson'):
            file_path += '.geojson'
        elif is_gpkg and not file_path.lower().endswith('.gpkg'):
            file_path += '.gpkg'
        elif is_docx and not file_path.lower().endswith('.docx'):
            file_path += '.docx'
        elif not is_kml and not is_flightplan and not is_docx and not is_geojson and not is_gpkg and not file_path.lower().endswith('.dipul'):
            file_path += '.dipul'
            
        if is_gpkg:
            try:
                success, error_msg = self.write_to_gpkg(file_path)
                if success:
                    QMessageBox.information(
                        self.gui, 
                        self.tr("msg_export_success_title", "Export erfolgreich"), 
                        self.tr("msg_export_success_text", "Die Datei wurde erfolgreich exportiert unter:\n{path}").format(path=file_path)
                    )
                else:
                    raise Exception(error_msg)
            except Exception as e:
                QMessageBox.critical(
                    self.gui, 
                    self.tr("msg_export_error_title", "Export Fehler"), 
                    self.tr("msg_export_error_text", "Fehler beim Exportieren der Datei:\n{error}").format(error=str(e))
                )
            return

        if is_kml:
            try:
                ImporterExporter.export_kml(file_path, self.waypoints, self.pilot_pos, self.params, self.geometry_type)
                QMessageBox.information(
                    self.gui, 
                    self.tr("msg_export_success_title", "Export erfolgreich"), 
                    self.tr("msg_export_success_text", "Die Datei wurde erfolgreich exportiert unter:\n{path}").format(path=file_path)
                )
            except Exception as e:
                QMessageBox.critical(
                    self.gui, 
                    self.tr("msg_export_error_title", "Export Fehler"), 
                    self.tr("msg_export_error_text", "Fehler beim Exportieren der Datei:\n{error}").format(error=str(e))
                )
            return
            
        if is_geojson:
            try:
                ImporterExporter.export_geojson(file_path, self.waypoints, self.pilot_pos, self.params, self.geometry_type)
                QMessageBox.information(
                    self.gui, 
                    self.tr("msg_export_success_title", "Export erfolgreich"), 
                    self.tr("msg_export_success_text", "Die Datei wurde erfolgreich exportiert unter:\n{path}").format(path=file_path)
                )
            except Exception as e:
                QMessageBox.critical(
                    self.gui, 
                    self.tr("msg_export_error_title", "Export Fehler"), 
                    self.tr("msg_export_error_text", "Fehler beim Exportieren der Datei:\n{error}").format(error=str(e))
                )
            return
            
        if is_docx:
            try:
                # Capture three map screenshots dynamically
                overview_path, start_path, end_path = self.capture_map_views()
                
                # Grab live Sora visual widget screenshot
                temp_sora_path = None
                if hasattr(self, 'sora_viz') and self.sora_viz is not None:
                    try:
                        sora_pixmap = self.sora_viz.grab()
                        temp_sora_path = os.path.join(tempfile.gettempdir(), f"sora_viz_{uuid.uuid4().hex[:8]}.png")
                        sora_pixmap.save(temp_sora_path, "PNG")
                    except Exception:
                        pass
                
                ImporterExporter.export_sora_docx(
                    file_path, 
                    self.waypoints, 
                    self.pilot_pos, 
                    self.params, 
                    overview_path, 
                    self.geometry_type,
                    start_image_path=start_path,
                    end_image_path=end_path,
                    sora_viz_image_path=temp_sora_path
                )
                
                # Clean up temporary PNGs
                for p in [overview_path, start_path, end_path, temp_sora_path]:
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                        
                QMessageBox.information(
                    self.gui, 
                    self.tr("msg_export_success_title", "Export erfolgreich"), 
                    self.tr("msg_export_success_text", "Die Datei wurde erfolgreich exportiert unter:\n{path}").format(path=file_path)
                )
            except Exception as e:
                QMessageBox.critical(
                    self.gui, 
                    self.tr("msg_export_error_title", "Export Fehler"), 
                    self.tr("msg_export_error_text", "Fehler beim Exportieren der Datei:\n{error}").format(error=str(e))
                )
            return
            
        # Display unified PyQt5 ExportSettingsDialog
        default_h = float(self.params.get("maxFlightHeight", 100.0))
        default_spd = float(self.params.get("maxVelocity", 30.0))
        default_fg = float(self.params.get("corridorWidth", 50.0))
        
        # If there are waypoints, we can also pre-populate using the first waypoint's altitude, speed, and FG width
        if self.waypoints:
            w0 = self.waypoints[0]
            if len(w0) > 2:
                default_h = w0[2]
            if len(w0) > 3:
                default_spd = w0[3]
            if len(w0) > 4:
                default_fg = w0[4]
                
        dialog = ExportSettingsDialog(self.gui, default_h, default_spd, default_fg, params=self.params)
        if dialog.exec_() != QDialog.Accepted:
            return
            
        const_height, const_speed, const_fg_width = dialog.get_values()
            
        try:
            params_export = self.params.copy()
            params_export["corridorWidth"] = const_fg_width
            
            if file_path.lower().endswith('.flightplan'):
                ImporterExporter.export_flightplan(file_path, self.waypoints, const_height)
            else:
                ImporterExporter.export_dipul(file_path, self.waypoints, self.pilot_pos, const_height, const_speed, params_export, self.geometry_type)
                
            QMessageBox.information(
                self.gui, 
                self.tr("msg_export_success_title", "Export erfolgreich"), 
                self.tr("msg_export_success_text", "Die Datei wurde erfolgreich exportiert unter:\n{path}").format(path=file_path)
            )
        except Exception as e:
            QMessageBox.critical(
                self.gui, 
                self.tr("msg_export_error_title", "Export Fehler"), 
                self.tr("msg_export_error_text", "Fehler beim Exportieren der Datei:\n{error}").format(error=str(e))
            )

    def export_sora_report(self):
        if not self.waypoints:
            QMessageBox.warning(
                self.gui, 
                self.tr("msg_export_error_title", "Export Fehler"), 
                self.tr("msg_export_no_wp_text", "Es gibt keine Wegpunkte zum Exportieren.")
            )
            return
            
        from PyQt5.QtCore import QDate
        from qgis.core import QgsSettings
        settings = QgsSettings()
        last_dir = settings.value("/QUCORE/last_export_dir", "")

        date_str = QDate.currentDate().toString("yyyyMMdd")
        default_filename = f"QUCORE-Route_{date_str}.docx"
        default_path = os.path.join(last_dir, default_filename) if last_dir else default_filename

        file_path, _ = QFileDialog.getSaveFileName(
            self.gui, 
            self.tr("menu_sora_export", "SORA Dokumentations-Export (.docx)..."), 
            default_path, 
            "SORA Dokumentations-Export (*.docx)"
        )
        if not file_path:
            return

        settings.setValue("/QUCORE/last_export_dir", os.path.dirname(file_path))
            
        if not file_path.lower().endswith('.docx'):
            file_path += '.docx'
            
        try:
            # Capture three map screenshots dynamically
            overview_path, start_path, end_path = self.capture_map_views()
            
            # Grab live Sora visual widget screenshot
            temp_sora_path = None
            if hasattr(self, 'sora_viz') and self.sora_viz is not None:
                try:
                    sora_pixmap = self.sora_viz.grab()
                    temp_sora_path = os.path.join(tempfile.gettempdir(), f"sora_viz_{uuid.uuid4().hex[:8]}.png")
                    sora_pixmap.save(temp_sora_path, "PNG")
                except Exception:
                    pass
            
            # Run SORA DOCX Export
            ImporterExporter.export_sora_docx(
                file_path, 
                self.waypoints, 
                self.pilot_pos, 
                self.params, 
                overview_path, 
                self.geometry_type,
                start_image_path=start_path,
                end_image_path=end_path,
                sora_viz_image_path=temp_sora_path
            )
            
            # Clean up temporary PNGs
            for p in [overview_path, start_path, end_path, temp_sora_path]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                    
            QMessageBox.information(
                self.gui, 
                self.tr("msg_export_success_title", "Export erfolgreich"), 
                self.tr("msg_export_success_text", "Die Datei wurde erfolgreich exportiert unter:\n{path}").format(path=file_path)
            )
        except Exception as e:
            QMessageBox.critical(
                self.gui, 
                self.tr("msg_export_error_title", "Export Fehler"), 
                self.tr("msg_export_error_text", "Fehler beim Exportieren der Datei:\n{error}").format(error=str(e))
            )
