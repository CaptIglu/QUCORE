# -*- coding: utf-8 -*-
import os
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QDialogButtonBox,
    QCheckBox
)
from .config_manager import ConfigManager
from .translation_manager import TranslationManager

class ParameterDialog(QDialog):
    def __init__(self, parent=None, current_params=None, waypoints=None):
        super(ParameterDialog, self).__init__(parent)
        self.resize(680, 480)
        self.setModal(True)
        
        self.waypoints = waypoints
        self.waypoints_backup = list(waypoints) if waypoints is not None else []
        self.on_change_callback = None

        # Load config.json defaults to show actual configured defaults in brackets
        self.config_defaults = ConfigManager.get_instance()._defaults.copy()

        # Load config_limits.json for dynamic min/max/step/decimals of spinboxes
        self.config_limits = ConfigManager.get_instance()._limits.copy()

        # ----------------------------------------------------
        # DEFAULT PARAMETERS FROM HELGOLAND DIPUL
        # ----------------------------------------------------
        self.params = ConfigManager.get_instance()._defaults.copy()

        # Apply config defaults to baseline params
        if self.config_defaults:
            self.params.update(self.config_defaults)

        # Override with current parameters if provided
        if current_params:
            cp = current_params.copy()
            if "maxVelocity" in cp and "maxOpsSpeedV0" not in cp:
                cp["maxOpsSpeedV0"] = cp["maxVelocity"]
            if "maxVelocityVmax" in cp and "maxCommandableSpeedVmax" not in cp:
                cp["maxCommandableSpeedVmax"] = cp["maxVelocityVmax"]
            if "maxCommandSpeedVmax" in cp and "maxCommandableSpeedVmax" not in cp:
                cp["maxCommandableSpeedVmax"] = cp["maxCommandSpeedVmax"]
                
            # Fallback to V0 if Vmax is missing
            if "maxOpsSpeedV0" in cp and "maxCommandableSpeedVmax" not in cp:
                cp["maxCommandableSpeedVmax"] = cp["maxOpsSpeedV0"]
                
            self.params.update(cp)

        self.params["maxOpsSpeedV0"] = ConfigManager.get_param(self.params, "maxOpsSpeedV0")
        self.params["maxCommandableSpeedVmax"] = ConfigManager.get_param(self.params, "maxCommandableSpeedVmax")

        # Load translations
        # self.tr_strings logic removed in favor of TranslationManager
        

        self.setWindowTitle(self.tr("dialog_calc_params_title", "UAS Korridor Berechnungsparameter"))
        self.init_ui()

    def configure_spinbox(self, spinbox, param_key):
        limits = ConfigManager.get_limit(param_key)
        s_min = limits["min"]
        s_max = limits["max"]
        s_step = limits["step"]
        s_dec = limits["decimals"]
        
        if hasattr(spinbox, "setDecimals"):
            spinbox.setDecimals(s_dec)
        spinbox.setRange(s_min, s_max)
        spinbox.setSingleStep(s_step)

    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return TranslationManager.tr(key, lang, default)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Get defaults from config_defaults with robust fallbacks
        v0_def = ConfigManager.get_default("maxOpsSpeedV0")
        vmax_def = ConfigManager.get_default("maxCommandableSpeedVmax")
        cd_def = ConfigManager.get_default("maxCharacteristicDimension")
        stall_def = ConfigManager.get_default("stallVelocity")
        gps_def = ConfigManager.get_default("gpsInaccuracy")
        pos_def = ConfigManager.get_default("positionError")
        map_def = ConfigManager.get_default("mapError")
        rz_def = ConfigManager.get_default("reactionTime")
        alt_gps_def = ConfigManager.get_default("altitudeErrorGps")
        alt_baro_def = ConfigManager.get_default("altitudeErrorBarometric")
        add_lat_def = ConfigManager.get_default("additionalErrorLateral")
        add_vert_def = ConfigManager.get_default("additionalErrorVertical")
        roll_def = ConfigManager.get_default("maxRollAngle")
        pitch_def = ConfigManager.get_default("maxPitchAngle")
        para_lat_def = ConfigManager.get_default("parachuteOpeningTimeLateral")
        para_vert_def = ConfigManager.get_default("parachuteOpeningTimeVertical")
        glide_def = ConfigManager.get_default("glideRatioDenominator")
        para_grb_def = ConfigManager.get_default("parachuteOpeningTimeGRB")
        wind_def = ConfigManager.get_default("maxWindVelocity")
        descent_def = ConfigManager.get_default("parachuteDescentRate")
        w_fg_def = ConfigManager.get_default("corridorWidth")
        h_fg_def = ConfigManager.get_default("maxFlightHeight")

        # Translate helper for "Standard" or "Default" literal inside brackets
        default_label = self.tr("tree_value", "Standardwert")

        # Create Tab Widget
        self.tabs = QTabWidget()
        
        # Add Tabs
        self.tab_uas = QWidget()
        self.tab_assumptions = QWidget()
        self.tab_manoeuvre = QWidget()
        self.tab_grb = QWidget()
        self.tab_general = QWidget()
        
        self.tabs.addTab(self.tab_general, self.tr("tab_general", "Korridoreinstellungen"))
        self.tabs.addTab(self.tab_uas, self.tr("tab_uas", "UAS Eigenschaften"))
        self.tabs.addTab(self.tab_assumptions, self.tr("tab_assumptions", "Annahmen"))
        self.tabs.addTab(self.tab_manoeuvre, self.tr("tab_manoeuvre", "Sicherheitsmanöver"))
        self.tabs.addTab(self.tab_grb, self.tr("tab_grb", "Ground Risk Buffer"))
        
        main_layout.addWidget(self.tabs)

        # ----------------------------------------------------
        # TAB 1: UAS PROPERTIES
        # ----------------------------------------------------
        uas_layout = QFormLayout(self.tab_uas)
        uas_layout.setContentsMargins(15, 15, 15, 15)
        uas_layout.setSpacing(10)
        
        self.combo_uas_type = QComboBox()
        self.combo_uas_type.addItems([self.tr("uas_fw", "Flächenflieger (Fixed Wing)"), self.tr("uas_mc", "Multikopter")])
        if ConfigManager.get_param(self.params, "uas_type") == "Multikopter":
            self.combo_uas_type.setCurrentIndex(1)
        else:
            self.combo_uas_type.setCurrentIndex(0)
        uas_layout.addRow(self.tr("uas_type", "UAS Typ:"), self.combo_uas_type)
        
        self.spin_v0 = QDoubleSpinBox()
        self.configure_spinbox(self.spin_v0, "maxOpsSpeedV0")
        self.spin_v0.setValue(ConfigManager.get_param(self.params, "maxOpsSpeedV0"))
        self.spin_v0.setSuffix(" m/s")
        uas_layout.addRow(f"{self.tr('label_v0', 'Max. Betriebsgeschwindigkeit (v0)')} ({default_label}: {v0_def:.1f} m/s):", self.spin_v0)
        
        self.chk_override_v = QCheckBox(self.tr("chk_override_v", "Individuelle Wegpunktgeschwindigkeiten überschreiben"))
        self.chk_override_v.setStyleSheet("color: #d97706; font-weight: bold;")
        self.chk_override_v.setChecked(False)
        self.has_custom_v = self.has_individual_speeds()
        self.chk_override_v.setVisible(self.has_custom_v)
        self.chk_override_v.toggled.connect(self.on_override_v_toggled)
        uas_layout.addRow("", self.chk_override_v)
        
        if self.has_custom_v:
            self.spin_v0.setEnabled(False)

        self.spin_vmax = QDoubleSpinBox()
        self.configure_spinbox(self.spin_vmax, "maxCommandableSpeedVmax")
        self.spin_vmax.setValue(ConfigManager.get_param(self.params, "maxCommandableSpeedVmax"))
        self.spin_vmax.setSuffix(" m/s")
        uas_layout.addRow(f"{self.tr('label_v_max', 'Max. kommandierbare Geschwindigkeit (v_max)')} ({default_label}: {vmax_def:.1f} m/s):", self.spin_vmax)
        
        self.spin_cd = QDoubleSpinBox()
        self.configure_spinbox(self.spin_cd, "maxCharacteristicDimension")
        self.spin_cd.setValue(ConfigManager.get_param(self.params, "maxCharacteristicDimension"))
        self.spin_cd.setSuffix(" m")
        uas_layout.addRow(f"{self.tr('label_cd', 'Charakteristische Dimension (CD)')} ({default_label}: {cd_def:.1f} m):", self.spin_cd)

        self.spin_stall = QDoubleSpinBox()
        self.configure_spinbox(self.spin_stall, "stallVelocity")
        self.spin_stall.setValue(ConfigManager.get_param(self.params, "stallVelocity"))
        self.spin_stall.setSuffix(" m/s")
        uas_layout.addRow(f"{self.tr('label_stall', 'Überziehgeschwindigkeit (stallVelocity)')} ({default_label}: {stall_def:.1f} m/s):", self.spin_stall)

        # ----------------------------------------------------
        # TAB 2: ASSUMPTIONS & ERRORS
        # ----------------------------------------------------
        ass_layout = QFormLayout(self.tab_assumptions)
        ass_layout.setContentsMargins(15, 15, 15, 15)
        
        self.combo_altimetry = QComboBox()
        self.combo_altimetry.addItems([self.tr("alt_gps", "GPS-basiert"), self.tr("alt_baro", "barometrisch")])
        alt_type = ConfigManager.get_param(self.params, "altimetry")
        if alt_type == "Baro" or alt_type == "barometrisch":
            self.combo_altimetry.setCurrentIndex(1)
        else:
            self.combo_altimetry.setCurrentIndex(0)
        ass_layout.addRow(self.tr("altimetry", "Höhenmessung:"), self.combo_altimetry)
        
        self.spin_gps_inacc = QDoubleSpinBox()
        self.configure_spinbox(self.spin_gps_inacc, "gpsInaccuracy")
        self.spin_gps_inacc.setValue(ConfigManager.get_param(self.params, "gpsInaccuracy"))
        self.spin_gps_inacc.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_gps_inacc', 'GPS Ungenauigkeit (SGPS)')} ({default_label}: {gps_def:.1f} m):", self.spin_gps_inacc)
        
        self.spin_pos_err = QDoubleSpinBox()
        self.configure_spinbox(self.spin_pos_err, "positionError")
        self.spin_pos_err.setValue(ConfigManager.get_param(self.params, "positionError"))
        self.spin_pos_err.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_pos_err', 'Positionshaltefehler (SPos)')} ({default_label}: {pos_def:.1f} m):", self.spin_pos_err)
        
        self.spin_map_err = QDoubleSpinBox()
        self.configure_spinbox(self.spin_map_err, "mapError")
        self.spin_map_err.setValue(ConfigManager.get_param(self.params, "mapError"))
        self.spin_map_err.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_map_err', 'Kartenfehler (SK)')} ({default_label}: {map_def:.1f} m):", self.spin_map_err)
        
        self.spin_t_rz = QDoubleSpinBox()
        self.configure_spinbox(self.spin_t_rz, "reactionTime")
        self.spin_t_rz.setValue(ConfigManager.get_param(self.params, "reactionTime"))
        self.spin_t_rz.setSuffix(" s")
        ass_layout.addRow(f"{self.tr('label_t_rz', 'Fernpilot Reaktionszeit (tRZ)')} ({default_label}: {rz_def:.1f} s):", self.spin_t_rz)
        
        self.spin_alt_gps = QDoubleSpinBox()
        self.configure_spinbox(self.spin_alt_gps, "altitudeErrorGps")
        self.spin_alt_gps.setValue(ConfigManager.get_param(self.params, "altitudeErrorGps"))
        self.spin_alt_gps.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_alt_gps', 'GPS Höhenfehler')} ({default_label}: {alt_gps_def:.1f} m):", self.spin_alt_gps)
        
        self.spin_alt_baro = QDoubleSpinBox()
        self.configure_spinbox(self.spin_alt_baro, "altitudeErrorBarometric")
        self.spin_alt_baro.setValue(ConfigManager.get_param(self.params, "altitudeErrorBarometric"))
        self.spin_alt_baro.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_alt_baro', 'Baro Höhenfehler')} ({default_label}: {alt_baro_def:.1f} m):", self.spin_alt_baro)
        
        self.spin_add_horiz = QDoubleSpinBox()
        self.configure_spinbox(self.spin_add_horiz, "additionalErrorLateral")
        self.spin_add_horiz.setValue(ConfigManager.get_param(self.params, "additionalErrorLateral"))
        self.spin_add_horiz.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_add_horiz', 'Zusatzentfernung (horizontal)')} ({default_label}: {add_lat_def:.1f} m):", self.spin_add_horiz)
        
        self.spin_add_vert = QDoubleSpinBox()
        self.configure_spinbox(self.spin_add_vert, "additionalErrorVertical")
        self.spin_add_vert.setValue(ConfigManager.get_param(self.params, "additionalErrorVertical"))
        self.spin_add_vert.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_add_vert', 'Zusatzentfernung (vertikal)')} ({default_label}: {add_vert_def:.1f} m):", self.spin_add_vert)

        # ----------------------------------------------------
        # TAB 3: CONTINGENCY MANOEUVRES
        # ----------------------------------------------------
        man_layout = QVBoxLayout(self.tab_manoeuvre)
        man_layout.setContentsMargins(15, 15, 15, 15)
        
        # Lateral group
        group_lat = QGroupBox(self.tr("group_lat", "Laterales Contingency Manöver"))
        lat_form = QFormLayout(group_lat)
        
        self.combo_lat_man = QComboBox()
        self.combo_lat_man.addItems([self.tr("man_default_lat", "Standard (Kurve / Anhalten)"), self.tr("man_parachute", "Auslösen des Fallschirms")])
        if ConfigManager.get_param(self.params, "lateralContingencyManoeuvreType") == "Parachute":
            self.combo_lat_man.setCurrentIndex(1)
        else:
            self.combo_lat_man.setCurrentIndex(0)
        lat_form.addRow(self.tr("manoeuvre_type", "Manövertyp:"), self.combo_lat_man)
        
        self.spin_roll_angle = QDoubleSpinBox()
        self.configure_spinbox(self.spin_roll_angle, "maxRollAngle")
        self.spin_roll_angle.setValue(ConfigManager.get_param(self.params, "maxRollAngle"))
        self.spin_roll_angle.setSuffix(" °")
        lat_form.addRow(f"{self.tr('label_roll', 'Rollwinkel (FixedWing, Φ)')} ({default_label}: {roll_def:.1f} °):", self.spin_roll_angle)
 
        self.spin_pitch_angle = QDoubleSpinBox()
        self.configure_spinbox(self.spin_pitch_angle, "maxPitchAngle")
        self.spin_pitch_angle.setValue(ConfigManager.get_param(self.params, "maxPitchAngle"))
        self.spin_pitch_angle.setSuffix(" °")
        lat_form.addRow(f"{self.tr('label_pitch', 'Nickwinkel (Multikopter, Θ)')} ({default_label}: {pitch_def:.1f} °):", self.spin_pitch_angle)
        
        self.spin_para_lat = QDoubleSpinBox()
        self.configure_spinbox(self.spin_para_lat, "parachuteOpeningTimeLateral")
        self.spin_para_lat.setValue(ConfigManager.get_param(self.params, "parachuteOpeningTimeLateral"))
        self.spin_para_lat.setSuffix(" s")
        lat_form.addRow(f"{self.tr('label_para_lat', 'Fallschirm Öffnungszeit (lat)')} ({default_label}: {para_lat_def:.1f} s):", self.spin_para_lat)
        
        man_layout.addWidget(group_lat)
        
        # Vertical group
        group_vert = QGroupBox(self.tr("group_vert", "Vertikales Contingency Manöver"))
        vert_form = QFormLayout(group_vert)
        
        self.combo_vert_man = QComboBox()
        self.combo_vert_man.addItems([self.tr("man_default_vert", "Standard (Energiewandlung / Climb)"), self.tr("man_parachute", "Auslösen des Fallschirms")])
        if ConfigManager.get_param(self.params, "verticalContingencyManoeuvreType") == "Parachute":
            self.combo_vert_man.setCurrentIndex(1)
        else:
            self.combo_vert_man.setCurrentIndex(0)
        vert_form.addRow(self.tr("manoeuvre_type", "Manövertyp:"), self.combo_vert_man)
        
        self.spin_para_vert = QDoubleSpinBox()
        self.configure_spinbox(self.spin_para_vert, "parachuteOpeningTimeVertical")
        self.spin_para_vert.setValue(ConfigManager.get_param(self.params, "parachuteOpeningTimeVertical"))
        self.spin_para_vert.setSuffix(" s")
        vert_form.addRow(f"{self.tr('label_para_vert', 'Fallschirm Öffnungszeit (vert)')} ({default_label}: {para_vert_def:.1f} s):", self.spin_para_vert)
        
        man_layout.addWidget(group_vert)

        # ----------------------------------------------------
        # TAB 4: GROUND RISK BUFFER (GRB)
        # ----------------------------------------------------
        grb_layout = QFormLayout(self.tab_grb)
        grb_layout.setContentsMargins(15, 15, 15, 15)
        
        self.combo_grb_method = QComboBox()
        self.combo_grb_method.addItems([
            self.tr("grb_simplified", "Vereinfachter Ansatz (1:1 Regel)"), 
            self.tr("grb_ballistic", "Ballistischer Ansatz"), 
            self.tr("grb_glide", "Antrieb aus mit Gleitflug"), 
            self.tr("grb_parachute", "Terminierung mit Auslösen des Fallschirms")
        ])
        
        grb_map = {
            "Simplified": 0,
            "Ballistic": 1,
            "Glide": 2,
            "Parachute": 3
        }
        self.combo_grb_method.setCurrentIndex(grb_map.get(ConfigManager.get_param(self.params, "groundRiskBufferMethod"), 0))
        grb_layout.addRow(self.tr("label_grb_method", "Terminierungsmethode (GRB):"), self.combo_grb_method)
        
        self.spin_glide = QDoubleSpinBox()
        self.configure_spinbox(self.spin_glide, "glideRatioDenominator")
        self.spin_glide.setValue(ConfigManager.get_param(self.params, "glideRatioDenominator"))
        self.spin_glide.setSuffix(" : 1")
        grb_layout.addRow(f"{self.tr('label_glide', 'Gleitzahl (E)')} ({default_label}: {glide_def:.1f} : 1):", self.spin_glide)
        
        self.spin_para_grb = QDoubleSpinBox()
        self.configure_spinbox(self.spin_para_grb, "parachuteOpeningTimeGRB")
        self.spin_para_grb.setValue(ConfigManager.get_param(self.params, "parachuteOpeningTimeGRB"))
        self.spin_para_grb.setSuffix(" s")
        grb_layout.addRow(f"{self.tr('label_para_grb', 'Fallschirm Öffnungszeit (GRB)')} ({default_label}: {para_grb_def:.1f} s):", self.spin_para_grb)
        
        self.spin_wind = QDoubleSpinBox()
        self.configure_spinbox(self.spin_wind, "maxWindVelocity")
        self.spin_wind.setValue(ConfigManager.get_param(self.params, "maxWindVelocity"))
        self.spin_wind.setSuffix(" m/s")
        grb_layout.addRow(f"{self.tr('label_wind', 'Max. zulässige Windgeschwindigkeit')} ({default_label}: {wind_def:.1f} m/s):", self.spin_wind)
        
        self.spin_descent = QDoubleSpinBox()
        self.configure_spinbox(self.spin_descent, "parachuteDescentRate")
        self.spin_descent.setValue(ConfigManager.get_param(self.params, "parachuteDescentRate"))
        self.spin_descent.setSuffix(" m/s")
        grb_layout.addRow(f"{self.tr('label_descent', 'Fallschirm Sinkgeschwindigkeit (vZ)')} ({default_label}: {descent_def:.1f} m/s):", self.spin_descent)

        # ----------------------------------------------------
        # TAB 5: GENERAL CORRIDOR SETTINGS
        # ----------------------------------------------------
        gen_layout = QFormLayout(self.tab_general)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        
        self.spin_corridor_width = QDoubleSpinBox()
        self.configure_spinbox(self.spin_corridor_width, "corridorWidth")
        self.spin_corridor_width.setValue(ConfigManager.get_param(self.params, "corridorWidth"))
        self.spin_corridor_width.setSuffix(" m")
        gen_layout.addRow(f"{self.tr('label_corridor_width', 'Standard Flight Geography Breite (W_FG)')} ({default_label}: {w_fg_def:.1f} m):", self.spin_corridor_width)
        
        self.chk_override_w = QCheckBox(self.tr("chk_override_w", "Individuelle Wegpunktbreiten überschreiben"))
        self.chk_override_w.setStyleSheet("color: #d97706; font-weight: bold;")
        self.chk_override_w.setChecked(False)
        self.has_custom_w = self.has_individual_widths()
        self.chk_override_w.toggled.connect(self.on_override_w_toggled)
        gen_layout.addRow("", self.chk_override_w)
        
        if self.params.get("geometry_type") == "Circle":
            self.spin_corridor_width.setEnabled(False)
            self.chk_override_w.setVisible(False)
        else:
            self.chk_override_w.setVisible(self.has_custom_w)
            if self.has_custom_w:
                self.spin_corridor_width.setEnabled(False)
        
        self.spin_default_h = QDoubleSpinBox()
        self.configure_spinbox(self.spin_default_h, "maxFlightHeight")
        self.spin_default_h.setValue(ConfigManager.get_param(self.params, "maxFlightHeight"))
        self.spin_default_h.setSuffix(" m")
        gen_layout.addRow(f"{self.tr('label_default_height', 'Standard Flughöhe (h)')} ({default_label}: {h_fg_def:.1f} m):", self.spin_default_h)
        
        self.chk_override_h = QCheckBox(self.tr("chk_override_h", "Individuelle Wegpunkthöhen überschreiben"))
        self.chk_override_h.setStyleSheet("color: #d97706; font-weight: bold;")
        self.chk_override_h.setChecked(False)
        self.has_custom_h = self.has_individual_heights()
        self.chk_override_h.setVisible(self.has_custom_h)
        self.chk_override_h.toggled.connect(self.on_override_h_toggled)
        gen_layout.addRow("", self.chk_override_h)


        
        if self.has_custom_h:
            self.spin_default_h.setEnabled(False)

        # Warning banner for Contingency Volume < 10m
        self.lbl_cv_warning = QLabel()
        self.lbl_cv_warning.setWordWrap(True)
        self.lbl_cv_warning.setStyleSheet(
            "background-color: #fffbeb; "
            "color: #b45309; "
            "border: 1px solid #fcd34d; "
            "border-radius: 4px; "
            "padding: 8px; "
            "font-size: 11px;"
        )
        self.lbl_cv_warning.setVisible(False)
        main_layout.addWidget(self.lbl_cv_warning)

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        btn_restore = button_box.button(QDialogButtonBox.RestoreDefaults)
        if btn_restore:
            btn_restore.clicked.connect(self.restore_defaults)
            btn_restore.setText(self.tr("msg_restore_defaults_title", "Standardwerte wiederherstellen"))
            
        main_layout.addWidget(button_box)
        
        # Connect combos to enable/disable widgets accordingly
        self.combo_uas_type.currentIndexChanged.connect(self.on_uas_changed)
        self.combo_grb_method.currentIndexChanged.connect(self.on_grb_changed)
        self.combo_lat_man.currentIndexChanged.connect(self.on_lat_man_changed)
        self.combo_vert_man.currentIndexChanged.connect(self.on_vert_man_changed)
        
        # Trigger initial UI updates
        self.on_uas_changed()
        self.on_grb_changed()
        self.on_vert_man_changed()

        # Connect change signals of all widgets for live preview
        for widget in [
            self.combo_uas_type, self.combo_altimetry, self.combo_lat_man, 
            self.combo_vert_man, self.combo_grb_method
        ]:
            widget.currentIndexChanged.connect(self.on_value_changed)
            
        for widget in [
            self.spin_v0, self.spin_vmax, self.spin_cd, self.spin_stall, self.spin_gps_inacc, 
            self.spin_pos_err, self.spin_map_err, self.spin_t_rz, self.spin_alt_gps, 
            self.spin_alt_baro, self.spin_add_horiz, self.spin_add_vert, 
            self.spin_roll_angle, self.spin_pitch_angle, self.spin_para_lat, 
            self.spin_para_vert, self.spin_glide, self.spin_para_grb, 
            self.spin_wind, self.spin_descent, self.spin_corridor_width, 
            self.spin_default_h
        ]:
            widget.valueChanged.connect(self.on_value_changed)

        # Initial check for Contingency Volume warnings
        self.check_cv_warnings()

    def accept(self):
        # Enforce that max operational speed (v0) is not greater than max commandable speed (v_max)
        v0 = self.spin_v0.value()
        vmax = self.spin_vmax.value()
        if v0 > vmax:
            from PyQt5.QtWidgets import QMessageBox
            title = self.tr("msg_speed_ops_vs_cmd_title", "Ungültige Geschwindigkeitseinstellung")
            text = self.tr("msg_speed_ops_vs_cmd_text", "Die maximale Betriebsgeschwindigkeit (v0 = {v0:.1f} m/s) darf nicht größer sein als die maximale kommandierbare Geschwindigkeit (v_max = {vmax:.1f} m/s).\nBitte korrigieren Sie die Werte.").format(v0=v0, vmax=vmax)
            QMessageBox.warning(self, title, text)
            return

        cd = self.spin_cd.value()
        width = self.spin_corridor_width.value()
        min_width = 3.0 * cd
        if width < min_width:
            from PyQt5.QtWidgets import QMessageBox
            title = self.tr("msg_cd_warning_title", "Einstellung korrigiert")
            text = self.tr("msg_cd_warning_text", "Die Flight Geography Breite ({width:.1f} m) muss mindestens 3-mal so groß wie die Charakteristische Dimension des UAS (CD = {cd:.1f} m, 3x CD = {min_width:.1f} m) sein.\nDie Breite wurde automatisch auf {min_width:.1f} m angepasst.").format(width=width, cd=cd, min_width=min_width)
            QMessageBox.warning(self, title, text)
            self.spin_corridor_width.setValue(min_width)
            return
        super(ParameterDialog, self).accept()

    def restore_defaults(self):
        from PyQt5.QtWidgets import QMessageBox
        title = self.tr("msg_restore_defaults_title", "Standardwerte wiederherstellen")
        text = self.tr("msg_restore_defaults_text", "Möchten Sie wirklich alle Parameter auf die Standardwerte aus der config.json zurücksetzen?")
        reply = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:

                
            # Block signals temporarily to prevent redundant calculations during reset
            self.combo_uas_type.blockSignals(True)
            self.combo_altimetry.blockSignals(True)
            self.combo_lat_man.blockSignals(True)
            self.combo_vert_man.blockSignals(True)
            self.combo_grb_method.blockSignals(True)
            
            self.spin_v0.blockSignals(True)
            self.spin_vmax.blockSignals(True)
            self.spin_cd.blockSignals(True)
            self.spin_stall.blockSignals(True)
            
            self.spin_gps_inacc.blockSignals(True)
            self.spin_pos_err.blockSignals(True)
            self.spin_map_err.blockSignals(True)
            self.spin_t_rz.blockSignals(True)
            self.spin_alt_gps.blockSignals(True)
            self.spin_alt_baro.blockSignals(True)
            self.spin_add_horiz.blockSignals(True)
            self.spin_add_vert.blockSignals(True)
            
            self.spin_roll_angle.blockSignals(True)
            self.spin_pitch_angle.blockSignals(True)
            self.spin_para_lat.blockSignals(True)
            self.spin_para_vert.blockSignals(True)
            
            self.spin_glide.blockSignals(True)
            self.spin_para_grb.blockSignals(True)
            self.spin_wind.blockSignals(True)
            self.spin_descent.blockSignals(True)
            
            self.spin_corridor_width.blockSignals(True)
            self.spin_default_h.blockSignals(True)

            
            try:
                # Apply defaults directly from ConfigManager
                uas_type = ConfigManager.get_default("uas_type")
                self.combo_uas_type.setCurrentIndex(1 if uas_type == "Multikopter" else 0)
                
                altimetry = ConfigManager.get_default("altimetry")
                self.combo_altimetry.setCurrentIndex(1 if altimetry in ["Baro", "barometrisch"] else 0)
                
                lat_man = ConfigManager.get_default("lateralContingencyManoeuvreType")
                self.combo_lat_man.setCurrentIndex(1 if lat_man == "Parachute" else 0)
                
                vert_man = ConfigManager.get_default("verticalContingencyManoeuvreType")
                self.combo_vert_man.setCurrentIndex(1 if vert_man == "Parachute" else 0)
                
                grb_method = ConfigManager.get_default("groundRiskBufferMethod")
                grb_map = {
                    "Simplified": 0,
                    "Ballistic": 1,
                    "Glide": 2,
                    "Parachute": 3
                }
                self.combo_grb_method.setCurrentIndex(grb_map.get(grb_method, 0))
                
                self.spin_v0.setValue(ConfigManager.get_default("maxOpsSpeedV0"))
                self.spin_vmax.setValue(ConfigManager.get_default("maxCommandableSpeedVmax"))
                self.spin_cd.setValue(ConfigManager.get_default("maxCharacteristicDimension"))
                self.spin_stall.setValue(ConfigManager.get_default("stallVelocity"))
                
                self.spin_gps_inacc.setValue(ConfigManager.get_default("gpsInaccuracy"))
                self.spin_pos_err.setValue(ConfigManager.get_default("positionError"))
                self.spin_map_err.setValue(ConfigManager.get_default("mapError"))
                self.spin_t_rz.setValue(ConfigManager.get_default("reactionTime"))
                self.spin_alt_gps.setValue(ConfigManager.get_default("altitudeErrorGps"))
                self.spin_alt_baro.setValue(ConfigManager.get_default("altitudeErrorBarometric"))
                self.spin_add_horiz.setValue(ConfigManager.get_default("additionalErrorLateral"))
                self.spin_add_vert.setValue(ConfigManager.get_default("additionalErrorVertical"))
                
                self.spin_roll_angle.setValue(ConfigManager.get_default("maxRollAngle"))
                self.spin_pitch_angle.setValue(ConfigManager.get_default("maxPitchAngle"))
                self.spin_para_lat.setValue(ConfigManager.get_default("parachuteOpeningTimeLateral"))
                self.spin_para_vert.setValue(ConfigManager.get_default("parachuteOpeningTimeVertical"))
                
                self.spin_glide.setValue(ConfigManager.get_default("glideRatioDenominator"))
                self.spin_para_grb.setValue(ConfigManager.get_default("parachuteOpeningTimeGRB"))
                self.spin_wind.setValue(ConfigManager.get_default("maxWindVelocity"))
                self.spin_descent.setValue(ConfigManager.get_default("parachuteDescentRate"))
                
                self.spin_corridor_width.setValue(ConfigManager.get_default("corridorWidth"))
                self.spin_default_h.setValue(ConfigManager.get_default("maxFlightHeight"))

            finally:
                # Unblock signals
                self.combo_uas_type.blockSignals(False)
                self.combo_altimetry.blockSignals(False)
                self.combo_lat_man.blockSignals(False)
                self.combo_vert_man.blockSignals(False)
                self.combo_grb_method.blockSignals(False)
                
                self.spin_v0.blockSignals(False)
                self.spin_vmax.blockSignals(False)
                self.spin_cd.blockSignals(False)
                self.spin_stall.blockSignals(False)
                
                self.spin_gps_inacc.blockSignals(False)
                self.spin_pos_err.blockSignals(False)
                self.spin_map_err.blockSignals(False)
                self.spin_t_rz.blockSignals(False)
                self.spin_alt_gps.blockSignals(False)
                self.spin_alt_baro.blockSignals(False)
                self.spin_add_horiz.blockSignals(False)
                self.spin_add_vert.blockSignals(False)
                
                self.spin_roll_angle.blockSignals(False)
                self.spin_pitch_angle.blockSignals(False)
                self.spin_para_lat.blockSignals(False)
                self.spin_para_vert.blockSignals(False)
                
                self.spin_glide.blockSignals(False)
                self.spin_para_grb.blockSignals(False)
                self.spin_wind.blockSignals(False)
                self.spin_descent.blockSignals(False)
                
                self.spin_corridor_width.blockSignals(False)
                self.spin_default_h.blockSignals(False)

                
            # Trigger updates
            self.on_uas_changed()
            self.on_grb_changed()
            self.on_vert_man_changed()
            self.on_value_changed()

    def on_uas_changed(self):
        self.on_lat_man_changed()
        is_fixed = (self.combo_uas_type.currentIndex() == 0)
        self.spin_stall.setEnabled(is_fixed)
        
        model = self.combo_grb_method.model()
        # Disable/enable "Antrieb aus mit Gleitflug" (index 2) in combo_grb_method
        item_glide = model.item(2)
        if item_glide:
            item_glide.setEnabled(is_fixed)
            
        # Disable/enable "Ballistischer Ansatz" (index 1) in combo_grb_method
        item_ballistic = model.item(1)
        if item_ballistic:
            item_ballistic.setEnabled(not is_fixed)
            
        current_idx = self.combo_grb_method.currentIndex()
        if not is_fixed and current_idx == 2:
            self.combo_grb_method.setCurrentIndex(0) # Fallback to 1:1 Regel
        elif is_fixed and current_idx == 1:
            self.combo_grb_method.setCurrentIndex(0) # Fallback to 1:1 Regel

    def on_lat_man_changed(self):
        is_parachute = (self.combo_lat_man.currentIndex() == 1)
        self.spin_para_lat.setEnabled(is_parachute)
        # Roll angle and Pitch angle are only enabled when NOT Parachute manoeuvre is selected
        is_fixed = (self.combo_uas_type.currentIndex() == 0)
        self.spin_roll_angle.setEnabled(not is_parachute and is_fixed)
        self.spin_pitch_angle.setEnabled(not is_parachute and not is_fixed)

    def on_vert_man_changed(self):
        is_parachute = (self.combo_vert_man.currentIndex() == 1)
        self.spin_para_vert.setEnabled(is_parachute)

    def on_grb_changed(self):
        # Enable/disable parameters based on GRB method
        idx = self.combo_grb_method.currentIndex()
        self.spin_glide.setEnabled(idx == 2) # Glide method
        
        is_parachute = (idx == 3)
        self.spin_para_grb.setEnabled(is_parachute)
        self.spin_wind.setEnabled(is_parachute)
        self.spin_descent.setEnabled(is_parachute)

    def get_parameters(self):
        """
        Retrieves all parameters from GUI and returns a dictionary.
        """
        uas_type = "FixedWing" if self.combo_uas_type.currentIndex() == 0 else "Multikopter"
        altimetry = "GPS" if self.combo_altimetry.currentIndex() == 0 else "Baro"
        
        grb_methods = ["Simplified", "Ballistic", "Glide", "Parachute"]
        grb_method = grb_methods[self.combo_grb_method.currentIndex()]
        
        lat_man = "Default" if self.combo_lat_man.currentIndex() == 0 else "Parachute"
        vert_man = "Default" if self.combo_vert_man.currentIndex() == 0 else "Parachute"

        return {
            "uas_type": uas_type,
            "altimetry": altimetry,
            "maxOpsSpeedV0": self.spin_v0.value(),
            "maxCommandableSpeedVmax": self.spin_vmax.value(),
            "maxVelocity": self.spin_v0.value(), # legacy fallback
            "maxCharacteristicDimension": self.spin_cd.value(),
            "maxRollAngle": self.spin_roll_angle.value(),
            "maxPitchAngle": self.spin_pitch_angle.value(),
            "glideRatioDenominator": self.spin_glide.value(),
            "maxWindVelocity": self.spin_wind.value(),
            "stallVelocity": self.spin_stall.value(),
            "gpsInaccuracy": self.spin_gps_inacc.value(),
            "positionError": self.spin_pos_err.value(),
            "mapError": self.spin_map_err.value(),
            "reactionTime": self.spin_t_rz.value(),
            "altitudeErrorGps": self.spin_alt_gps.value(),
            "altitudeErrorBarometric": self.spin_alt_baro.value(),
            "corridorWidth": self.spin_corridor_width.value(),
            "maxFlightHeight": self.spin_default_h.value(),
            "groundRiskBufferMethod": grb_method,
            "lateralContingencyManoeuvreType": lat_man,
            "verticalContingencyManoeuvreType": vert_man,
            "parachuteOpeningTimeLateral": self.spin_para_lat.value(),
            "parachuteOpeningTimeVertical": self.spin_para_vert.value(),
            "parachuteOpeningTimeGRB": self.spin_para_grb.value(),
            "parachuteDescentRate": self.spin_descent.value(),
            "additionalErrorLateral": self.spin_add_horiz.value(),
            "additionalErrorVertical": self.spin_add_vert.value(),
            "override_heights": self.chk_override_h.isChecked() if (hasattr(self, 'chk_override_h') and self.has_custom_h) else True,
            "override_widths": self.chk_override_w.isChecked() if (hasattr(self, 'chk_override_w') and self.has_custom_w) else True,
            "override_speeds": self.chk_override_v.isChecked() if (hasattr(self, 'chk_override_v') and self.has_custom_v) else True,
            "variable_polygon_buffers": self.params.get("variable_polygon_buffers", False)
        }

    def on_override_h_toggled(self, checked):
        self.spin_default_h.setEnabled(checked)
        if checked:
            new_h = self.spin_default_h.value()
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                lon, lat = w[0], w[1]
                spd = w[3] if len(w) > 3 else float(ConfigManager.get_param(self.params, "maxOpsSpeedV0"))
                fg = w[4] if len(w) > 4 else float(ConfigManager.get_param(self.params, "corridorWidth"))
                self.waypoints[idx] = (lon, lat, new_h, spd, fg)
            self.on_value_changed()

    def on_override_w_toggled(self, checked):
        self.spin_corridor_width.setEnabled(checked)
        if checked:
            new_w = self.spin_corridor_width.value()
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                lon, lat = w[0], w[1]
                alt = w[2] if len(w) > 2 else float(ConfigManager.get_param(self.params, "maxFlightHeight"))
                spd = w[3] if len(w) > 3 else float(ConfigManager.get_param(self.params, "maxOpsSpeedV0"))
                self.waypoints[idx] = (lon, lat, alt, spd, new_w)
            self.on_value_changed()

    def on_override_v_toggled(self, checked):
        self.spin_v0.setEnabled(checked)
        if checked:
            new_v = self.spin_v0.value()
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                lon, lat = w[0], w[1]
                alt = w[2] if len(w) > 2 else float(ConfigManager.get_param(self.params, "maxFlightHeight"))
                fg = w[4] if len(w) > 4 else float(ConfigManager.get_param(self.params, "corridorWidth"))
                self.waypoints[idx] = (lon, lat, alt, new_v, fg)
            self.on_value_changed()



    def has_individual_heights(self):
        if not self.waypoints:
            return False
        standard = ConfigManager.get_param(self.params, "maxFlightHeight")
        return any(len(w) > 2 and abs(w[2] - standard) > 1e-3 for w in self.waypoints)

    def has_individual_widths(self):
        if not self.waypoints:
            return False
        standard = ConfigManager.get_param(self.params, "corridorWidth")
        return any(len(w) > 4 and abs(w[4] - standard) > 1e-3 for w in self.waypoints)

    def has_individual_speeds(self):
        if not self.waypoints:
            return False
        standard = ConfigManager.get_param(self.params, "maxOpsSpeedV0")
        return any(len(w) > 3 and abs(w[3] - standard) > 1e-3 for w in self.waypoints)

    def reject(self):
        # Restore the waypoints backup in case of cancellation
        if hasattr(self, 'waypoints') and self.waypoints is not None and hasattr(self, 'waypoints_backup'):
            self.waypoints.clear()
            self.waypoints.extend(self.waypoints_backup)
        super(ParameterDialog, self).reject()

    def on_value_changed(self):
        # Enforce v0 <= vmax dynamic adjustment
        v0 = self.spin_v0.value()
        vmax = self.spin_vmax.value()
        sender = self.sender()
        if sender == self.spin_vmax:
            # If vmax decreased below v0, push v0 down
            if vmax < v0:
                self.spin_v0.blockSignals(True)
                self.spin_v0.setValue(vmax)
                self.spin_v0.blockSignals(False)
        else:
            # For spin_v0 or other changes, if v0 exceeds vmax, push vmax up
            if v0 > vmax:
                self.spin_vmax.blockSignals(True)
                self.spin_vmax.setValue(v0)
                self.spin_vmax.blockSignals(False)

        self.check_cv_warnings()
        if hasattr(self, 'on_change_callback') and self.on_change_callback:
            self.on_change_callback(self.get_parameters())

    def get_s_cv_values(self):
        try:
            from .buffer_calculator import BufferCalculator
        except ImportError:
            return []
            
        params = self.get_parameters()
        s_cv_list = []
        
        # If there are no waypoints, check the default settings
        if not self.waypoints:
            h = ConfigManager.get_param(params, "maxFlightHeight")
            r_fg, r_cv, r_grb, h_cv = BufferCalculator.calculate_buffer_widths(h, params)
            s_cv_list.append(r_cv - r_fg)
        else:
            for w in self.waypoints:
                h = w[2] if len(w) > 2 else ConfigManager.get_param(params, "maxFlightHeight")
                spd = w[3] if len(w) > 3 else ConfigManager.get_param(params, "maxOpsSpeedV0")
                fg = w[4] if len(w) > 4 else ConfigManager.get_param(params, "corridorWidth")
                
                params_wp = params.copy()
                params_wp["maxOpsSpeedV0"] = spd
                params_wp["maxVelocity"] = spd
                params_wp["corridorWidth"] = fg
                
                r_fg, r_cv, r_grb, h_cv, d_grb = BufferCalculator.calculate_buffer_widths(h, params_wp)
                s_cv_list.append(r_cv - r_fg)
                
        return s_cv_list

    def check_cv_warnings(self):
        s_cv_list = self.get_s_cv_values()
        warnings = []
        
        # 1. Contingency Volume width warning
        has_warning = any(x < 9.99 for x in s_cv_list) if s_cv_list else False
        if has_warning:
            warnings.append(self.tr(
                "msg_cv_warning_banner",
                "⚠️ <b>Hinweis zum Contingency Volume (CV):</b><br>"
                "In mindestens einem Abschnitt beträgt die berechnete Pufferbreite (s_cv) weniger als 10,0 m. "
                "Nach EASA SORA (AMC1 zu Artikel 11) wird eine Mindestbreite von 10 Metern empfohlen. "
                "Bitte begründen Sie den geringeren Puffer betrieblich in Ihrem ConOps."
            ))
            
        # 2. Check active parachute opening times
        lat_is_para = (self.combo_lat_man.currentIndex() == 1)
        vert_is_para = (self.combo_vert_man.currentIndex() == 1)
        grb_is_para = (self.combo_grb_method.currentIndex() == 3)
        
        para_times = []
        if lat_is_para:
            para_times.append(self.spin_para_lat.value())
        if vert_is_para:
            para_times.append(self.spin_para_vert.value())
        if grb_is_para:
            para_times.append(self.spin_para_grb.value())
            
        if len(para_times) > 1 and len(set(para_times)) > 1:
            warnings.append(self.tr(
                "msg_different_para_times_warning",
                "⚠️ <b>Compliance-Hinweis (Fallschirm-Öffnungszeiten):</b><br>"
                "Sie haben unterschiedliche Fallschirm-Öffnungszeiten in Ihren aktiven Manövern konfiguriert. "
                "Dies weicht von der Logik des offiziellen LBA-Berechnungstools ab. Dieser Betriebszustand "
                "ist unter Umständen nicht konform und erfordert eine zusätzliche Begründung in Ihrem Betriebshandbuch (OM)."
            ))
            
        # 3. Check contradictory safety manoeuvre concepts
        if (lat_is_para or vert_is_para) and not grb_is_para:
            warnings.append(self.tr(
                "msg_different_manoeuvres_warning",
                "⚠️ <b>Compliance-Hinweis (Manöverkonzepte):</b><br>"
                "Sie haben das Fallschirm-Manöver für das Contingency Volume gewählt, nutzen aber ein anderes Verfahren "
                "(ballistisch/Gleitflug) für die Flugbeendigung (GRB). Dies ist physikalisch widersprüchlich "
                "(da der Fallschirm bereits entfaltet ist) und wird vom offiziellen LBA-Excel-Tool gesperrt. "
                "Dieser Betriebszustand ist unter Umständen nicht konform und erfordert eine zusätzliche Begründung "
                "in Ihrem Betriebshandbuch (OM)."
            ))
            
        if warnings:
            combined_text = "<br><hr style='border: 0; border-top: 1px solid #fcd34d;'><br>".join(warnings)
            self.lbl_cv_warning.setText(combined_text)
            self.lbl_cv_warning.setVisible(True)
        else:
            self.lbl_cv_warning.setVisible(False)
