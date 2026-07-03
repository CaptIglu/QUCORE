# -*- coding: utf-8 -*-
import os
import json
import math
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from .config_manager import ConfigManager
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
    QLabel,
    QApplication,
    QHeaderView,
    QCheckBox
)
from .translation_manager import TranslationManager

from PyQt5.QtCore import pyqtSignal

class AltitudeTableDialog(QDialog):
    sigToggleWaypointLabels = pyqtSignal(bool)
    sigWaypointFocused = pyqtSignal(int)
    sigClearFocus = pyqtSignal()

    def __init__(self, parent=None, waypoints=None, params=None, on_change_callback=None, geometry_type="Corridor"):
        super(AltitudeTableDialog, self).__init__(parent)
        self.resize(1150, 450) # increased width to fit all 10 columns beautifully
        self.setModal(False)
        
        # self.waypoints is a list of tuples: (lon, lat, height, speed, fg_width)
        self.waypoints = waypoints if waypoints is not None else []
        self.params = params if params is not None else {}
        self.on_change_callback = on_change_callback
        self.geometry_type = geometry_type
        self.labels_active = False
        
        # Load translations
        # self.tr_strings logic removed in favor of TranslationManager
        

        self.setWindowTitle(self.tr("dialog_altitude_title", "Wegpunkt-Parameter bearbeiten"))
        self.init_ui()

    def tr(self, key, default=""):
        lang = ConfigManager.get_param(self.params, "language")
        return TranslationManager.tr(key, lang, default)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Info Label
        label = QLabel(self.tr("dialog_altitude_desc", "Geben Sie die Werte für jeden Wegpunkt individuell ein. Die Pufferzonen passen sich an diese lokalen Parameter dynamisch an."))
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Checkbox & warning label layout for Polygon mode
        if self.geometry_type == "Polygon":
            
            # Checkbox
            self.chk_variable_polygon = QCheckBox(self.tr("chk_variable_polygon_buffers", "Variable Pufferung der Grenzsegmente erlauben (Expertenmodus)"))
            self.chk_variable_polygon.setChecked(self.params.get("variable_polygon_buffers", False))
            self.chk_variable_polygon.toggled.connect(self.on_variable_polygon_toggled)
            layout.addWidget(self.chk_variable_polygon)
            
            # Warning label
            self.lbl_polygon_uniform_warning = QLabel(
                self.tr("lbl_polygon_uniform_warning", "Hinweis: Da die variable Pufferung deaktiviert ist, werden für alle Segmente einheitlich die Maximalwerte aller Wegpunkte (Flughöhe, Geschwindigkeit, Breite) für die Berechnung verwendet.")
            )
            self.lbl_polygon_uniform_warning.setWordWrap(True)
            self.lbl_polygon_uniform_warning.setStyleSheet(
                "background-color: #fffbeb; "
                "color: #b45309; "
                "border: 1px solid #fcd34d; "
                "border-radius: 4px; "
                "padding: 8px; "
                "font-weight: bold;"
            )
            self.lbl_polygon_uniform_warning.setVisible(not self.chk_variable_polygon.isChecked())
            layout.addWidget(self.lbl_polygon_uniform_warning)
        
        # Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            self.tr("col_wp", "Wegpunkt"), 
            self.tr("col_pos", "Position (Lat, Lon)"),
            self.tr("col_alt", "h_FG (Flughöhe) (m)"), 
            self.tr("col_spd", "v0 (Geschwindigkeit) (m/s)"), 
            self.tr("col_fg", "S_FG (Breite) (m)"), 
            self.tr("col_cv", "S_CV (Breite) (m)"), 
            self.tr("col_grb", "S_GRB (Breite) (m)"),
            self.tr("col_hcv", "h_CV (m)"),
            self.tr("col_dist", "Distanz"),
            self.tr("col_dur", "Dauer (mm:ss)")
        ])
        self.table.setRowCount(len(self.waypoints))
        if self.geometry_type == "Polygon":
            self.table.setColumnHidden(4, True)
        
        # Populate table
        for idx, w in enumerate(self.waypoints):
            lon, lat = w[0], w[1]
            alt = w[2] if len(w) > 2 else 100.0
            spd = w[3] if len(w) > 3 else 30.0
            fg = w[4] if len(w) > 4 else 50.0
            
            # 0. Waypoint label item (read-only)
            item_wp = QTableWidgetItem(f"{self.tr('col_wp', 'Wegpunkt')} {idx + 1}")
            item_wp.setFlags(item_wp.flags() & ~Qt.ItemIsEditable)
            item_wp.setForeground(QBrush(QColor(130, 130, 130)))
            self.table.setItem(idx, 0, item_wp)
            
            # 1. Position item (editable, Lat/Lon 5 decimals)
            lat_lon_str = f"{lat:.5f}, {lon:.5f}"
            item_pos = QTableWidgetItem(lat_lon_str)
            item_pos.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 1, item_pos)
            
            # 2. Altitude item (editable)
            item_alt = QTableWidgetItem(f"{alt:.1f}")
            item_alt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 2, item_alt)
            
            # 3. Speed item (editable)
            item_spd = QTableWidgetItem(f"{spd:.1f}")
            item_spd.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 3, item_spd)
            
            # 4. FG Width item (editable)
            item_fg = QTableWidgetItem(f"{fg:.1f}")
            item_fg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 4, item_fg)
            
        # Initialize total label early so recalculate_distances_and_durations can update it
        self.lbl_total = QLabel("")
        self.lbl_total.setStyleSheet("font-weight: bold;")
        if self.geometry_type in ["Circle", "Polygon"]:
            self.lbl_total.setVisible(False)

        # Run recalculation for each row initially to populate CV/GRB columns
        self.table.blockSignals(True)
        for r in range(len(self.waypoints)):
            self.recalculate_buffers(r)
        self.recalculate_distances_and_durations()
        self.table.blockSignals(False)
        
        # Resize columns to fit headers and contents beautifully
        self.table.resizeColumnsToContents()
        
        self.table.setAlternatingRowColors(True)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
            
        self.table.horizontalHeader().setStretchLastSection(False)
        
        # Ensure Column 7 (h_CV) has a matching width to Column 5 (CV Radius) and Column 6 (GRB Radius)
        target_width = max(self.table.columnWidth(5), self.table.columnWidth(6), 110)
        self.table.setColumnWidth(7, target_width)
        
        # Stretch the coordinate column (col 1) to absorb any remaining space beautifully
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        self.update_table_editable_states()
        
        layout.addWidget(self.table)
        
        # Checkbox for showing waypoint numbers on map and total label
        lay_options = QHBoxLayout()
        self.chk_show_wp_nums = QCheckBox(self.tr("chk_show_wp_nums", "Zeige Wegpunkt-Nummern an"))
        self.chk_show_wp_nums.setChecked(self.labels_active)
        self.chk_show_wp_nums.toggled.connect(self.toggle_waypoint_numbers)
        lay_options.addWidget(self.chk_show_wp_nums)
        
        lay_options.addStretch()
        
        lay_options.addWidget(self.lbl_total)
        
        layout.addLayout(lay_options)
        
        # Bottom Layout with Copy Button and OK/Cancel Button Box
        lay_buttons = QHBoxLayout()
        btn_copy = QPushButton(self.tr("btn_copy_excel", "Tabelle kopieren (für Excel)"))
        btn_copy.clicked.connect(self.copy_selection_to_clipboard)
        btn_copy.setToolTip(self.tr("btn_copy_excel_tooltip", "Kopiert die gesamte Tabelle inkl. Spaltenköpfe in die Zwischenablage für MS Excel."))
        lay_buttons.addWidget(btn_copy)
        
        btn_delete_wp = QPushButton(self.tr("btn_delete_wp", "Wegpunkt löschen"))
        btn_delete_wp.setStyleSheet("QPushButton { color: red; }")
        btn_delete_wp.clicked.connect(self.delete_selected_waypoint)
        btn_delete_wp.setToolTip(self.tr("btn_delete_wp_tooltip", "Löscht den ausgewählten Wegpunkt (auch per Entf-Taste)."))
        lay_buttons.addWidget(btn_delete_wp)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        lay_buttons.addWidget(button_box)
        
        layout.addLayout(lay_buttons)

    def update_table_editable_states(self):
        is_polygon = (self.geometry_type == "Polygon")
        is_variable = self.params.get("variable_polygon_buffers", False)
        
        # Determine if h_FG (col 2) and v0 (col 3) should be editable
        should_edit = not is_polygon or is_variable
        
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            # Column 2 (Altitude)
            item_alt = self.table.item(r, 2)
            if item_alt:
                if should_edit:
                    item_alt.setFlags(item_alt.flags() | Qt.ItemIsEditable)
                    item_alt.setForeground(QBrush(QColor(0, 0, 0)))
                else:
                    item_alt.setFlags(item_alt.flags() & ~Qt.ItemIsEditable)
                    item_alt.setForeground(QBrush(QColor(130, 130, 130)))
                
            # Column 3 (Speed)
            item_spd = self.table.item(r, 3)
            if item_spd:
                if should_edit:
                    item_spd.setFlags(item_spd.flags() | Qt.ItemIsEditable)
                    item_spd.setForeground(QBrush(QColor(0, 0, 0)))
                else:
                    item_spd.setFlags(item_spd.flags() & ~Qt.ItemIsEditable)
                    item_spd.setForeground(QBrush(QColor(130, 130, 130)))
        self.table.blockSignals(False)

    def on_variable_polygon_toggled(self, checked):
        self.params["variable_polygon_buffers"] = checked
        if hasattr(self, 'lbl_polygon_uniform_warning'):
            self.lbl_polygon_uniform_warning.setVisible(not checked)
            
        if checked:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                self.tr("variable_polygon_buffers_warning_title", "Sicherheitsrelevanter Hinweis"),
                self.tr(
                    "variable_polygon_buffers_warning_text",
                    "Die segmentweise Pufferung im Polygon-Modus ist nur flugsicherheitstechnisch zulässig, "
                    "wenn sichergestellt ist, dass die Drohne im inneren Flugbereich physisch/flugtaktisch nicht "
                    "die höheren Geschwindigkeiten oder Höhen aus anderen Segmenten aufbauen und in Richtung der "
                    "schmaleren Puffer driften kann (z. B. bei engen Einflugschläuchen).\n\n"
                    "Für freie Flächen wird dringend empfohlen, den einheitlichen Puffer basierend auf den Maximalwerten zu nutzen."
                )
            )
            
        self.update_table_editable_states()
            
        if self.on_change_callback is not None:
            self.on_change_callback()

    def delete_selected_waypoint(self):
        """
        Deletes the currently selected waypoint row from the table and internal list.
        """
        selected_rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        if not selected_rows:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, 
                self.tr("msg_delete_wp_title", "Wegpunkt löschen"),
                self.tr("msg_delete_wp_no_sel", "Bitte wählen Sie zuerst eine Zeile in der Tabelle aus."))
            return
        
        self.table.blockSignals(True)
        for row_idx in selected_rows:
            if 0 <= row_idx < len(self.waypoints):
                self.waypoints.pop(row_idx)
                self.table.removeRow(row_idx)
        
        # Re-number remaining rows
        for r in range(self.table.rowCount()):
            item_wp = self.table.item(r, 0)
            if item_wp:
                item_wp.setText(f"{self.tr('col_wp', 'Wegpunkt')} {r + 1}")
        
        self.recalculate_distances_and_durations()
        self.table.blockSignals(False)
        
        # Fire real-time map update
        if self.on_change_callback is not None:
            self.on_change_callback()

    def _haversine(self, lon1, lat1, lon2, lat2):
        R = 6371000.0  # Radius of Earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2.0) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2.0) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def recalculate_distances_and_durations(self):
        prev_lon, prev_lat = None, None
        total_dist = 0.0
        total_duration_s = 0.0
        
        for r in range(self.table.rowCount()):
            # Get Position
            item_pos = self.table.item(r, 1)
            lon, lat = 0.0, 0.0
            if item_pos:
                try:
                    parts = [x.strip() for x in item_pos.text().split(",")]
                    if len(parts) == 2:
                        lat = float(parts[0])
                        lon = float(parts[1])
                except ValueError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in altitude_table_dialog.py (line 324): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
                    
            # Calculate distance
            dist = 0.0
            if prev_lon is not None and prev_lat is not None:
                dist = self._haversine(prev_lon, prev_lat, lon, lat)
            
            total_dist += dist
            prev_lon, prev_lat = lon, lat
            
            # Format distance
            if dist >= 10000:
                dist_str = f"{dist/1000.0:.1f} km"
            else:
                dist_str = f"{dist:.0f}"
                
            # Update Distance Column (col 8)
            item_dist = self.table.item(r, 8)
            if not item_dist:
                item_dist = QTableWidgetItem()
                item_dist.setFlags(item_dist.flags() & ~Qt.ItemIsEditable)
                item_dist.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item_dist.setForeground(QBrush(QColor(130, 130, 130)))
                self.table.setItem(r, 8, item_dist)
            item_dist.setText(dist_str)
            
            # Get Speed
            item_spd = self.table.item(r, 3)
            spd = 30.0
            if item_spd:
                try:
                    spd = float(item_spd.text().replace(',', '.'))
                except ValueError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in altitude_table_dialog.py (line 357): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
            
            if spd < 0.1:
                spd = 0.1
                
            # Calculate Duration
            duration_s = dist / spd
            total_duration_s += duration_s
            minutes = int(duration_s // 60)
            seconds = int(duration_s % 60)
            dur_str = f"{minutes:02d}:{seconds:02d}"
            
            # Update Duration Column (col 9)
            item_dur = self.table.item(r, 9)
            if not item_dur:
                item_dur = QTableWidgetItem()
                item_dur.setFlags(item_dur.flags() & ~Qt.ItemIsEditable)
                item_dur.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item_dur.setForeground(QBrush(QColor(130, 130, 130)))
                self.table.setItem(r, 9, item_dur)
            item_dur.setText(dur_str)

        # Update Total Label
        if total_dist >= 10000:
            total_dist_str = f"{total_dist/1000.0:.1f} km"
        else:
            total_dist_str = f"{total_dist:.0f} m"
            
        t_hours = int(total_duration_s // 3600)
        t_minutes = int((total_duration_s % 3600) // 60)
        t_seconds = int(total_duration_s % 60)
        if t_hours > 0:
            total_dur_str = f"{t_hours:02d}:{t_minutes:02d}:{t_seconds:02d}"
        else:
            total_dur_str = f"{t_minutes:02d}:{t_seconds:02d}"
            
        total_text = self.tr("lbl_total_dist_dur", "Gesamtdistanz: {dist}   |   Gesamtdauer: {dur}").format(dist=total_dist_str, dur=total_dur_str)
        if hasattr(self, 'lbl_total'):
            self.lbl_total.setText(total_text)

    def recalculate_buffers(self, row):
        # Read values from table row
        # Altitude (col 2)
        item_alt = self.table.item(row, 2)
        try:
            h = float(item_alt.text().replace(',', '.')) if item_alt else 100.0
        except ValueError:
            h = 100.0
            
        # Speed (col 3)
        item_spd = self.table.item(row, 3)
        try:
            spd = float(item_spd.text().replace(',', '.')) if item_spd else 30.0
        except ValueError:
            spd = 30.0
            
        # FG width (col 4)
        item_fg = self.table.item(row, 4)
        try:
            fg = float(item_fg.text().replace(',', '.')) if item_fg else 50.0
        except ValueError:
            fg = 50.0
            
        # Local copy of params
        params_wp = self.params.copy()
        params_wp["maxOpsSpeedV0"] = spd
        params_wp["maxVelocity"] = spd
        params_wp["corridorWidth"] = fg
        
        # Calculate CV & GRB
        from .buffer_calculator import BufferCalculator
        r_fg, r_cv, r_grb, h_cv = BufferCalculator.calculate_buffer_widths(h, params_wp)
        
        s_cv = r_cv - r_fg
        s_grb = r_grb - r_cv
        
        # Update CV and GRB columns
        item_cv = self.table.item(row, 5)
        if not item_cv:
            item_cv = QTableWidgetItem()
            item_cv.setFlags(item_cv.flags() & ~Qt.ItemIsEditable)
            item_cv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_cv.setForeground(QBrush(QColor(130, 130, 130)))
            self.table.setItem(row, 5, item_cv)
        item_cv.setText(f"{s_cv:.1f}")
        
        item_grb = self.table.item(row, 6)
        if not item_grb:
            item_grb = QTableWidgetItem()
            item_grb.setFlags(item_grb.flags() & ~Qt.ItemIsEditable)
            item_grb.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_grb.setForeground(QBrush(QColor(130, 130, 130)))
            self.table.setItem(row, 6, item_grb)
        item_grb.setText(f"{s_grb:.1f}")
        
        # Update h_CV column with grey background (read-only)
        item_hcv = self.table.item(row, 7)
        if not item_hcv:
            item_hcv = QTableWidgetItem()
            item_hcv.setFlags(item_hcv.flags() & ~Qt.ItemIsEditable)
            item_hcv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_hcv.setForeground(QBrush(QColor(130, 130, 130)))
            self.table.setItem(row, 7, item_hcv)
        item_hcv.setText(f"{h_cv:.1f}")

    def on_cell_changed(self, row, col):
        if col in [1, 2, 3, 4]: # Position, Flughöhe, Geschwindigkeit, or FG Breite
            self.table.blockSignals(True)
            
            # Validation for Position (col 1)
            if col == 1:
                item_pos = self.table.item(row, col)
                if item_pos:
                    text = item_pos.text().strip()
                    try:
                        # Try parsing as lat, lon
                        parts = [x.strip() for x in text.split(",")]
                        if len(parts) == 2:
                            lat = float(parts[0])
                            lon = float(parts[1])
                            # Check valid range
                            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                                # Safe format: update cell display to exactly Lat, Lon (5 decimals)
                                item_pos.setText(f"{lat:.5f}, {lon:.5f}")
                            else:
                                raise ValueError("Ungültiger Koordinatenbereich.")
                        else:
                            raise ValueError("Ungültiges Koordinatenformat.")
                    except ValueError:
                        # Revert to original waypoints coordinates
                        w = self.waypoints[row]
                        lon_orig, lat_orig = w[0], w[1]
                        item_pos.setText(f"{lat_orig:.5f}, {lon_orig:.5f}")
            
            # Validation for Speed (col 3)
            elif col == 3:
                item_spd = self.table.item(row, col)
                max_vel = float(ConfigManager.get_param(self.params, "maxCommandableSpeedVmax"))
                uas_type = ConfigManager.get_param(self.params, "uas_type")
                stall_vel = float(ConfigManager.get_param(self.params, "stallVelocity"))
                
                if item_spd:
                    try:
                        spd_val = float(item_spd.text().replace(',', '.'))
                        if spd_val > max_vel:
                            from PyQt5.QtWidgets import QMessageBox
                            title = self.tr("msg_speed_limit_title", "Geschwindigkeit überschritten")
                            text = self.tr("msg_speed_limit_text", 
                                           "Die eingegebene Geschwindigkeit ({spd_val:.1f} m/s) darf die maximale "
                                           "kommandierbare Geschwindigkeit des UAS ({max_vel:.1f} m/s) nicht überschreiten.\n"
                                           "Der Wert wurde automatisch auf {max_vel:.1f} m/s zurückgesetzt.").format(spd_val=spd_val, max_vel=max_vel)
                            QMessageBox.warning(self, title, text)
                            item_spd.setText(f"{max_vel:.1f}")
                        elif uas_type == "FixedWing" and spd_val < stall_vel:
                            from PyQt5.QtWidgets import QMessageBox
                            title = self.tr("msg_stall_limit_title", "Unterschreitung der Stall-Speed")
                            text = self.tr("msg_stall_limit_text", 
                                           "Die eingegebene Geschwindigkeit ({spd_val:.1f} m/s) darf die eingestellte "
                                           "Stall-Speed des Flächenflugzeugs ({stall_vel:.1f} m/s) nicht unterschreiten.\n"
                                           "Der Wert wurde automatisch auf {stall_vel:.1f} m/s gesetzt.").format(spd_val=spd_val, stall_vel=stall_vel)
                            QMessageBox.warning(self, title, text)
                            item_spd.setText(f"{stall_vel:.1f}")
                        elif spd_val < 0.1:
                            item_spd.setText("0.1")
                    except ValueError:
                        if uas_type == "FixedWing":
                            item_spd.setText(f"{stall_vel:.1f}")
                        else:
                            item_spd.setText("0.1")
            
            # Validation for FG Width (col 4)
            elif col == 4:
                item_fg = self.table.item(row, col)
                cd = float(ConfigManager.get_param(self.params, "maxCharacteristicDimension"))
                min_fg = 3.0 * cd
                if item_fg:
                    try:
                        fg_val = float(item_fg.text().replace(',', '.'))
                        if fg_val < min_fg:
                            from PyQt5.QtWidgets import QMessageBox
                            title = self.tr("msg_fg_limit_title", "Flight Geography Breite zu gering")
                            text = self.tr("msg_fg_limit_text", 
                                           "Die Flight Geography Breite ({fg_val:.1f} m) muss mindestens 3-mal so groß wie die "
                                           "Charakteristische Dimension des UAS (CD = {cd:.1f} m, 3x CD = {min_fg:.1f} m) sein.\n"
                                           "Der Wert wurde automatisch auf {min_fg:.1f} m gesetzt.").format(fg_val=fg_val, cd=cd, min_fg=min_fg)
                            QMessageBox.warning(self, title, text)
                            item_fg.setText(f"{min_fg:.1f}")
                    except ValueError:
                        item_fg.setText(f"{min_fg:.1f}")
            
            self.recalculate_buffers(row)
            self.recalculate_distances_and_durations()
            self.table.blockSignals(False)
            
            # Fire real-time map updates!
            if hasattr(self, 'on_change_callback') and self.on_change_callback is not None:
                self.on_change_callback()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
            self.copy_selection_to_clipboard()
            event.accept()
        elif event.key() == Qt.Key_Delete:
            self.delete_selected_waypoint()
            event.accept()
        else:
            super(AltitudeTableDialog, self).keyPressEvent(event)

    def copy_selection_to_clipboard(self):
        selection = self.table.selectedRanges()
        if not selection:
            # If nothing is selected, copy the ENTIRE table with headers
            rows = self.table.rowCount()
            cols = self.table.columnCount()
            headers = [self.table.horizontalHeaderItem(c).text() for c in range(cols)]
            lines = ["\t".join(headers)]
            for r in range(rows):
                row_data = []
                for c in range(cols):
                    item = self.table.item(r, c)
                    row_data.append(item.text() if item else "")
                lines.append("\t".join(row_data))
            clipboard_text = "\n".join(lines)
        else:
            # Copy only selected ranges as tab-separated values
            selected_range = selection[0]
            lines = []
            for r in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                row_data = []
                for c in range(selected_range.leftColumn(), selected_range.rightColumn() + 1):
                    item = self.table.item(r, c)
                    row_data.append(item.text() if item else "")
                lines.append("\t".join(row_data))
            clipboard_text = "\n".join(lines)
            
        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)

    def get_waypoint_params(self):
        """
        Reads values from the table and returns a list of tuples (lon, lat, altitude, speed, fg_width).
        """
        updated_params = []
        for idx in range(len(self.waypoints)):
            w = self.waypoints[idx]
            lon_prev = w[0]
            lat_prev = w[1]
            alt_prev = w[2] if len(w) > 2 else 100.0
            spd_prev = w[3] if len(w) > 3 else 30.0
            fg_prev = w[4] if len(w) > 4 else 50.0
            
            # Read Coordinates (col 1)
            lon_val = lon_prev
            lat_val = lat_prev
            item_pos = self.table.item(idx, 1)
            if item_pos is not None:
                try:
                    text = item_pos.text().strip()
                    parts = [x.strip() for x in text.split(",")]
                    if len(parts) == 2:
                        lat_val = float(parts[0])
                        lon_val = float(parts[1])
                except ValueError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in altitude_table_dialog.py (line 622): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
            
            # Read Altitude (col 2)
            alt_val = alt_prev
            item_alt = self.table.item(idx, 2)
            if item_alt is not None:
                try:
                    alt_val = float(item_alt.text().replace(',', '.'))
                    if alt_val < 0.0:
                        alt_val = 0.0
                except ValueError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in altitude_table_dialog.py (line 633): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
            
            # Read Speed (col 3)
            spd_val = spd_prev
            item_spd = self.table.item(idx, 3)
            if item_spd is not None:
                try:
                    spd_val = float(item_spd.text().replace(',', '.'))
                    if spd_val < 0.1:
                        spd_val = 0.1
                except ValueError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in altitude_table_dialog.py (line 644): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
                    
            # Read FG Width (col 4)
            fg_val = fg_prev
            item_fg = self.table.item(idx, 4)
            if item_fg is not None:
                try:
                    fg_val = float(item_fg.text().replace(',', '.'))
                    if fg_val < 1.0:
                        fg_val = 1.0
                except ValueError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in altitude_table_dialog.py (line 655): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
                    
            updated_params.append((lon_val, lat_val, alt_val, spd_val, fg_val))
        return updated_params

    def toggle_waypoint_numbers(self, checked):
        self.labels_active = checked
        self.sigToggleWaypointLabels.emit(checked)

    def cleanup_labels(self):
        if getattr(self, "labels_active", False):
            self.sigToggleWaypointLabels.emit(False)
            self.labels_active = False

    def on_selection_changed(self):
        selection = self.table.selectedRanges()
        if not selection:
            self.sigClearFocus.emit()
        else:
            row = selection[0].topRow()
            self.sigWaypointFocused.emit(row)

    def accept(self):
        self.cleanup_labels()
        super(AltitudeTableDialog, self).accept()

    def reject(self):
        self.cleanup_labels()
        super(AltitudeTableDialog, self).reject()

    def closeEvent(self, event):
        self.cleanup_labels()
        super(AltitudeTableDialog, self).closeEvent(event)
