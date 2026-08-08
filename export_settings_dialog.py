# -*- coding: utf-8 -*-
import os
import json
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QCheckBox,
    QMessageBox
)
from .translation_manager import TranslationManager
from .config_manager import ConfigManager

class ExportSettingsDialog(QDialog):
    def __init__(self, parent=None, default_height=None, default_speed=None, default_fg_width=None, params=None, is_qgc_plan=False, is_waypoints_export=False):
        super(ExportSettingsDialog, self).__init__(parent)
        self.resize(350, 220)
        self.setModal(True)
        self.params = params if params is not None else {}
        self.is_qgc_plan = is_qgc_plan
        self.is_waypoints_export = is_waypoints_export

        if default_height is None:
            default_height = float(ConfigManager.get_param(self.params, "maxFlightHeight"))
        if default_speed is None:
            default_speed = float(ConfigManager.get_param(self.params, "maxOpsSpeedV0"))
        if default_fg_width is None:
            default_fg_width = float(ConfigManager.get_param(self.params, "corridorWidth"))
        
        # Load translations
        # self.tr_strings logic removed in favor of TranslationManager
        

        self.setWindowTitle(self.tr("dialog_export_title", "Parameter für den Export festlegen"))
        
        main_layout = QVBoxLayout(self)
        
        # Info Header
        info_label = QLabel(
            self.tr("dialog_export_desc", 
                    "Beim Exportieren einer dipul- oder flightplan-Datei müssen die veränderlichen Wegpunkt-Parameter "
                    "(Höhe, Geschwindigkeit und Flight Geography Breite) in konstante Werte überführt werden, um den "
                    "offiziellen Formatspezifikationen zu entsprechen. Bitte legen Sie diese konstanten Werte hier fest:")
        )
        if self.is_qgc_plan or self.is_waypoints_export:
            info_label.setText(
                self.tr("dialog_export_qgc_desc", 
                        "Bitte konfigurieren Sie die Export-Einstellungen.\n\n"
                        "WICHTIGER HINWEIS ZUR GESCHWINDIGKEIT:\n"
                        "Aus Sicherheitsgründen wird für jedes Flugsegment zwischen zwei Wegpunkten immer die niedrigere "
                        "Geschwindigkeit der beiden angrenzenden Wegpunkte angewendet (min(V_A, V_B)). Dies stellt sicher, "
                        "dass die Drohne den berechneten Ground Risk Buffer zu keinem Zeitpunkt verlässt.")
            )
            
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { margin-bottom: 10px; font-size: 11px; }")
        main_layout.addWidget(info_label)
        
        # Form Layout
        form_layout = QFormLayout()
        
        if not self.is_qgc_plan and not self.is_waypoints_export:
            h_lim = ConfigManager.get_limit("maxFlightHeight")
            self.spin_height = QDoubleSpinBox()
            self.spin_height.setRange(h_lim.get("min", 0.0), h_lim.get("max", 2000.0))
            self.spin_height.setDecimals(1)
            self.spin_height.setSingleStep(5.0)
            self.spin_height.setValue(default_height)
            self.spin_height.setSuffix(" m")
            self.spin_height.setStyleSheet("QDoubleSpinBox { padding: 4px; font-weight: bold; }")
            form_layout.addRow(self.tr("label_export_height", "Konstante Flughöhe (m):"), self.spin_height)
            
            spd_lim = ConfigManager.get_limit("maxOpsSpeedV0")
            self.spin_speed = QDoubleSpinBox()
            self.spin_speed.setRange(spd_lim.get("min", 0.1), spd_lim.get("max", 200.0))
            self.spin_speed.setDecimals(1)
            self.spin_speed.setSingleStep(1.0)
            self.spin_speed.setValue(default_speed)
            self.spin_speed.setSuffix(" m/s")
            self.spin_speed.setStyleSheet("QDoubleSpinBox { padding: 4px; font-weight: bold; }")
            form_layout.addRow(self.tr("label_export_speed", "Konstante Geschwindigkeit (m/s):"), self.spin_speed)
            
            fg_lim = ConfigManager.get_limit("corridorWidth")
            self.spin_fg_width = QDoubleSpinBox()
            self.spin_fg_width.setRange(fg_lim.get("min", 1.0), fg_lim.get("max", 5000.0))
            self.spin_fg_width.setDecimals(1)
            self.spin_fg_width.setSingleStep(5.0)
            self.spin_fg_width.setValue(default_fg_width)
            self.spin_fg_width.setSuffix(" m")
            self.spin_fg_width.setStyleSheet("QDoubleSpinBox { padding: 4px; font-weight: bold; }")
            form_layout.addRow(self.tr("label_export_fg_width", "Konstante FG-Breite (m):"), self.spin_fg_width)
        else:
            if self.is_waypoints_export:
                self.check_flightplan = QCheckBox(self.tr("checkbox_export_flightplan", "Flugweg exportieren"))
                self.check_flightplan.setChecked(True)
                form_layout.addRow("", self.check_flightplan)
                
                self.check_geofence = QCheckBox(self.tr("checkbox_export_geofence", "GeoFence exportieren"))
                self.check_geofence.setChecked(True)
                self.check_geofence.stateChanged.connect(self.on_geofence_check_changed)
                form_layout.addRow("", self.check_geofence)

            self.combo_geofence = QComboBox()
            self.combo_geofence.addItem(self.tr("export_geofence_fg", "Flight Geography"), "FG")
            self.combo_geofence.addItem(self.tr("export_geofence_cv", "Contingency Volume"), "CV")
            if self.is_waypoints_export:
                self.combo_geofence.addItem(self.tr("export_geofence_grb", "Ground Risk Buffer"), "GRB")

            self.combo_geofence.setStyleSheet("QComboBox { padding: 4px; font-weight: bold; }")
            form_layout.addRow(self.tr("label_export_geofence", "GeoFence für Export:"), self.combo_geofence)
            
            self.spin_resolution = QSpinBox()
            self.spin_resolution.setRange(3, 8)
            self.spin_resolution.setValue(8)
            self.spin_resolution.setStyleSheet("QSpinBox { padding: 4px; font-weight: bold; }")
            form_layout.addRow(self.tr("label_export_resolution", "Kreis-Auflösung (Stützpunkte pro 90° Bogen):"), self.spin_resolution)
            
            self.check_mp_compat = QCheckBox(self.tr("checkbox_mp_compat", "Integer-Werte (verbesserte Kompatibilität)"))
            self.check_mp_compat.setChecked(True)
            self.check_mp_compat.stateChanged.connect(self.on_mp_compat_changed)
            form_layout.addRow("", self.check_mp_compat)
            
            warn_vcv_label = QLabel(self.tr("warn_vertical_cv_text", "WICHTIG ZUM VERTIKALEN CV:\nDas vertikale Contingency Volume (das 'Dach' des Korridors) ist in dieser Datei NICHT enthalten! Da MAVLink derzeit keine sichere Methode bietet, Geofence-Höhen pro Wegpunkt dynamisch zu setzen, müssen Sie ein sicheres Höhenlimit (z.B. FENCE_ALT_MAX) manuell in QGC/MissionPlanner festlegen."))
            warn_vcv_label.setWordWrap(True)
            warn_vcv_label.setStyleSheet("QLabel { margin-top: 10px; color: #b71c1c; font-size: 11px; }")
            form_layout.addRow(warn_vcv_label)
            
        main_layout.addLayout(form_layout)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.setStyleSheet("QDialogButtonBox { margin-top: 10px; }")
        main_layout.addWidget(self.button_box)
        
    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return TranslationManager.tr(key, lang, default)
        
    def get_values(self):
        if not self.is_qgc_plan and not self.is_waypoints_export:
            return self.spin_height.value(), self.spin_speed.value(), self.spin_fg_width.value()
        elif self.is_qgc_plan:
            return self.combo_geofence.currentData(), self.spin_resolution.value(), self.check_mp_compat.isChecked()
        else:
            # is_waypoints_export
            return (self.check_flightplan.isChecked(), 
                    self.check_geofence.isChecked(), 
                    self.combo_geofence.currentData(), 
                    self.spin_resolution.value(), 
                    self.check_mp_compat.isChecked())

    def on_geofence_check_changed(self, state):
        enabled = (state == Qt.CheckState.Checked)
        self.combo_geofence.setEnabled(enabled)
        self.spin_resolution.setEnabled(enabled)

    def on_mp_compat_changed(self, state):
        if state != Qt.CheckState.Checked:
            QMessageBox.warning(
                self,
                self.tr("warn_mp_compat_title", "Kompatibilitäts-Warnung"),
                self.tr("warn_mp_compat_text", "QGroundControl unterstützt Fließkommazahlen. Andere Bodenstationen benötigen jedoch möglicherweise Integer-Werte für Geschwindigkeit und Höhe.")
            )

