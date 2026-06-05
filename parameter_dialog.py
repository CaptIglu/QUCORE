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

class ParameterDialog(QDialog):
    def __init__(self, parent=None, current_params=None, waypoints=None):
        super(ParameterDialog, self).__init__(parent)
        self.resize(680, 480)
        self.setModal(True)
        
        self.waypoints = waypoints
        self.waypoints_backup = list(waypoints) if waypoints is not None else []
        self.on_change_callback = None

        # Load config.json defaults to show actual configured defaults in brackets
        self.config_defaults = {}
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(plugin_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config_defaults = json.load(f)
            except Exception:
                pass

        # Load config_limits.json for dynamic min/max/step/decimals of spinboxes
        self.config_limits = {}
        limits_path = os.path.join(plugin_dir, "config_limits.json")
        if os.path.exists(limits_path):
            try:
                with open(limits_path, 'r', encoding='utf-8') as f:
                    self.config_limits = json.load(f)
            except Exception:
                pass

        # ----------------------------------------------------
        # DEFAULT PARAMETERS FROM HELGOLAND DIPUL
        # ----------------------------------------------------
        self.params = {
            "uas_type": "FixedWing",
            "altimetry": "GPS",
            "maxOpsSpeedV0": 30.0,
            "maxCommandableSpeedVmax": 30.0,
            "maxCharacteristicDimension": 3.6,
            "maxRollAngle": 30.0,
            "maxPitchAngle": 30.0,
            "glideRatioDenominator": 10.0,
            "maxWindVelocity": 3.0,
            "stallVelocity": 10.0,
            "gpsInaccuracy": 3.0,
            "positionError": 3.0,
            "mapError": 1.0,
            "reactionTime": 1.0,
            "altitudeErrorGps": 4.0,
            "altitudeErrorBarometric": 1.0,
            "corridorWidth": 50.0,
            "maxFlightHeight": 100.0,
            "groundRiskBufferMethod": "Simplified",
            "lateralContingencyManoeuvreType": "Default",
            "verticalContingencyManoeuvreType": "Default",
            "parachuteOpeningTimeLateral": 2.0,
            "parachuteOpeningTimeVertical": 2.0,
            "parachuteOpeningTimeGRB": 2.0,
            "parachuteDescentRate": 2.0,
            "additionalErrorLateral": 0.0,
            "additionalErrorVertical": 0.0
        }

        # Apply config defaults to baseline params
        if self.config_defaults:
            self.params.update(self.config_defaults)

        # Override with current parameters if provided
        if current_params:
            migrated_params = current_params.copy()
            if "maxVelocity" in migrated_params:
                if "maxOpsSpeedV0" not in migrated_params:
                    migrated_params["maxOpsSpeedV0"] = migrated_params["maxVelocity"]
                if "maxVelocityVmax" not in migrated_params and "maxCommandSpeedVmax" not in migrated_params and "maxCommandableSpeedVmax" not in migrated_params:
                    migrated_params["maxCommandableSpeedVmax"] = migrated_params["maxVelocity"]

            if ("maxVelocityVmax" in migrated_params or "maxCommandSpeedVmax" in migrated_params) and "maxCommandableSpeedVmax" not in migrated_params:
                migrated_params["maxCommandableSpeedVmax"] = migrated_params.get("maxVelocityVmax", migrated_params.get("maxCommandSpeedVmax"))

            if "maxOpsSpeedV0" in migrated_params and "maxCommandableSpeedVmax" not in migrated_params:
                migrated_params["maxCommandableSpeedVmax"] = migrated_params["maxOpsSpeedV0"]

            self.params.update(migrated_params)

        if "maxCommandableSpeedVmax" not in self.params:
            self.params["maxCommandableSpeedVmax"] = self.params.get("maxOpsSpeedV0", 30.0)

        # Load translations
        self.tr_strings = {}
        tr_path = os.path.join(plugin_dir, "translations.json")
        if os.path.exists(tr_path):
            try:
                with open(tr_path, 'r', encoding='utf-8') as f:
                    self.tr_strings = json.load(f)
            except Exception:
                pass

        self.setWindowTitle(self.tr("dialog_calc_params_title", "UAS Korridor Berechnungsparameter"))
        self.init_ui()

    def configure_spinbox(self, spinbox, param_key, default_min, default_max, default_step=1.0, default_decimals=2):
        limits = self.config_limits.get(param_key, {})
        s_min = limits.get("min", default_min)
        s_max = limits.get("max", default_max)
        s_step = limits.get("step", default_step)
        s_dec = limits.get("decimals", default_decimals)
        
        if hasattr(spinbox, "setDecimals"):
            spinbox.setDecimals(s_dec)
        spinbox.setRange(s_min, s_max)
        spinbox.setSingleStep(s_step)

    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return self.tr_strings.get(key, {}).get(lang, default)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Get defaults from config_defaults with robust fallbacks
        v0_def = self.config_defaults.get("maxOpsSpeedV0", self.config_defaults.get("maxVelocity", 30.0))
        vmax_def = self.config_defaults.get("maxCommandableSpeedVmax", self.config_defaults.get("maxVelocityVmax", v0_def))
        cd_def = self.config_defaults.get("maxCharacteristicDimension", 3.6)
        stall_def = self.config_defaults.get("stallVelocity", 10.0)
        gps_def = self.config_defaults.get("gpsInaccuracy", 3.0)
        pos_def = self.config_defaults.get("positionError", 3.0)
        map_def = self.config_defaults.get("mapError", 1.0)
        rz_def = self.config_defaults.get("reactionTime", 1.0)
        alt_gps_def = self.config_defaults.get("altitudeErrorGps", 4.0)
        alt_baro_def = self.config_defaults.get("altitudeErrorBarometric", 1.0)
        add_lat_def = self.config_defaults.get("additionalErrorLateral", 0.0)
        add_vert_def = self.config_defaults.get("additionalErrorVertical", 0.0)
        roll_def = self.config_defaults.get("maxRollAngle", 30.0)
        pitch_def = self.config_defaults.get("maxPitchAngle", 30.0)
        para_lat_def = self.config_defaults.get("parachuteOpeningTimeLateral", 2.0)
        para_vert_def = self.config_defaults.get("parachuteOpeningTimeVertical", 2.0)
        glide_def = self.config_defaults.get("glideRatioDenominator", 10.0)
        para_grb_def = self.config_defaults.get("parachuteOpeningTimeGRB", 2.0)
        wind_def = self.config_defaults.get("maxWindVelocity", 3.0)
        descent_def = self.config_defaults.get("parachuteDescentRate", 2.0)
        w_fg_def = self.config_defaults.get("corridorWidth", 50.0)
        h_fg_def = self.config_defaults.get("maxFlightHeight", 100.0)

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
        uas_layout.setMargin(15)
        uas_layout.setSpacing(10)
        
        self.combo_uas_type = QComboBox()
        self.combo_uas_type.addItems([self.tr("uas_fw", "Flächenflieger (Fixed Wing)"), self.tr("uas_mc", "Multikopter")])
        if self.params["uas_type"] == "Multikopter":
            self.combo_uas_type.setCurrentIndex(1)
        else:
            self.combo_uas_type.setCurrentIndex(0)
        uas_layout.addRow(self.tr("uas_type", "UAS Typ:"), self.combo_uas_type)
        
        self.spin_v0 = QDoubleSpinBox()
        self.configure_spinbox(self.spin_v0, "maxOpsSpeedV0", 0.1, 200.0, 1.0, 1)
        self.spin_v0.setValue(self.params.get("maxOpsSpeedV0", 30.0))
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
        self.configure_spinbox(self.spin_vmax, "maxCommandableSpeedVmax", 0.1, 200.0, 1.0, 1)
        self.spin_vmax.setValue(self.params.get("maxCommandableSpeedVmax", 30.0))
        self.spin_vmax.setSuffix(" m/s")
        uas_layout.addRow(f"{self.tr('label_v_max', 'Max. kommandierbare Geschwindigkeit (v_max)')} ({default_label}: {vmax_def:.1f} m/s):", self.spin_vmax)
        
        self.spin_cd = QDoubleSpinBox()
        self.configure_spinbox(self.spin_cd, "maxCharacteristicDimension", 0.01, 100.0, 0.1, 2)
        self.spin_cd.setValue(self.params["maxCharacteristicDimension"])
        self.spin_cd.setSuffix(" m")
        uas_layout.addRow(f"{self.tr('label_cd', 'Charakteristische Dimension (CD)')} ({default_label}: {cd_def:.1f} m):", self.spin_cd)

        self.spin_stall = QDoubleSpinBox()
        self.configure_spinbox(self.spin_stall, "stallVelocity", 0.0, 100.0, 1.0, 1)
        self.spin_stall.setValue(self.params["stallVelocity"])
        self.spin_stall.setSuffix(" m/s")
        uas_layout.addRow(f"{self.tr('label_stall', 'Überziehgeschwindigkeit (stallVelocity)')} ({default_label}: {stall_def:.1f} m/s):", self.spin_stall)

        # ----------------------------------------------------
        # TAB 2: ASSUMPTIONS & ERRORS
        # ----------------------------------------------------
        ass_layout = QFormLayout(self.tab_assumptions)
        ass_layout.setMargin(15)
        
        self.combo_altimetry = QComboBox()
        self.combo_altimetry.addItems([self.tr("alt_gps", "GPS-basiert"), self.tr("alt_baro", "barometrisch")])
        if self.params["altimetry"] == "Baro" or self.params["altimetry"] == "barometrisch":
            self.combo_altimetry.setCurrentIndex(1)
        else:
            self.combo_altimetry.setCurrentIndex(0)
        ass_layout.addRow(self.tr("altimetry", "Höhenmessung:"), self.combo_altimetry)
        
        self.spin_gps_inacc = QDoubleSpinBox()
        self.configure_spinbox(self.spin_gps_inacc, "gpsInaccuracy", 0.0, 50.0, 0.5, 1)
        self.spin_gps_inacc.setValue(self.params["gpsInaccuracy"])
        self.spin_gps_inacc.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_gps_inacc', 'GPS Ungenauigkeit (SGPS)')} ({default_label}: {gps_def:.1f} m):", self.spin_gps_inacc)
        
        self.spin_pos_err = QDoubleSpinBox()
        self.configure_spinbox(self.spin_pos_err, "positionError", 0.0, 50.0, 0.5, 1)
        self.spin_pos_err.setValue(self.params["positionError"])
        self.spin_pos_err.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_pos_err', 'Positionshaltefehler (SPos)')} ({default_label}: {pos_def:.1f} m):", self.spin_pos_err)
        
        self.spin_map_err = QDoubleSpinBox()
        self.configure_spinbox(self.spin_map_err, "mapError", 0.0, 50.0, 0.5, 1)
        self.spin_map_err.setValue(self.params["mapError"])
        self.spin_map_err.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_map_err', 'Kartenfehler (SK)')} ({default_label}: {map_def:.1f} m):", self.spin_map_err)
        
        self.spin_t_rz = QDoubleSpinBox()
        self.configure_spinbox(self.spin_t_rz, "reactionTime", 0.1, 10.0, 0.1, 1)
        self.spin_t_rz.setValue(self.params["reactionTime"])
        self.spin_t_rz.setSuffix(" s")
        ass_layout.addRow(f"{self.tr('label_t_rz', 'Fernpilot Reaktionszeit (tRZ)')} ({default_label}: {rz_def:.1f} s):", self.spin_t_rz)
        
        self.spin_alt_gps = QDoubleSpinBox()
        self.configure_spinbox(self.spin_alt_gps, "altitudeErrorGps", 0.0, 50.0, 0.5, 1)
        self.spin_alt_gps.setValue(self.params["altitudeErrorGps"])
        self.spin_alt_gps.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_alt_gps', 'GPS Höhenfehler')} ({default_label}: {alt_gps_def:.1f} m):", self.spin_alt_gps)
        
        self.spin_alt_baro = QDoubleSpinBox()
        self.configure_spinbox(self.spin_alt_baro, "altitudeErrorBarometric", 0.0, 50.0, 0.5, 1)
        self.spin_alt_baro.setValue(self.params["altitudeErrorBarometric"])
        self.spin_alt_baro.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_alt_baro', 'Baro Höhenfehler')} ({default_label}: {alt_baro_def:.1f} m):", self.spin_alt_baro)
        
        self.spin_add_horiz = QDoubleSpinBox()
        self.configure_spinbox(self.spin_add_horiz, "additionalErrorLateral", 0.0, 500.0, 1.0, 1)
        self.spin_add_horiz.setValue(self.params.get("additionalErrorLateral", 0.0))
        self.spin_add_horiz.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_add_horiz', 'Zusatzentfernung (horizontal)')} ({default_label}: {add_lat_def:.1f} m):", self.spin_add_horiz)
        
        self.spin_add_vert = QDoubleSpinBox()
        self.configure_spinbox(self.spin_add_vert, "additionalErrorVertical", 0.0, 500.0, 1.0, 1)
        self.spin_add_vert.setValue(self.params.get("additionalErrorVertical", 0.0))
        self.spin_add_vert.setSuffix(" m")
        ass_layout.addRow(f"{self.tr('label_add_vert', 'Zusatzentfernung (vertikal)')} ({default_label}: {add_vert_def:.1f} m):", self.spin_add_vert)

        # ----------------------------------------------------
        # TAB 3: CONTINGENCY MANOEUVRES
        # ----------------------------------------------------
        man_layout = QVBoxLayout(self.tab_manoeuvre)
        man_layout.setMargin(15)
        
        # Lateral group
        group_lat = QGroupBox(self.tr("group_lat", "Laterales Contingency Manöver"))
        lat_form = QFormLayout(group_lat)
        
        self.combo_lat_man = QComboBox()
        self.combo_lat_man.addItems([self.tr("man_default_lat", "Standard (Kurve / Anhalten)"), self.tr("man_parachute", "Auslösen des Fallschirms")])
        if self.params["lateralContingencyManoeuvreType"] in ["Parachute", "Auslösen des Fallschirms"]:
            self.combo_lat_man.setCurrentIndex(1)
        else:
            self.combo_lat_man.setCurrentIndex(0)
        lat_form.addRow(self.tr("manoeuvre_type", "Manövertyp:"), self.combo_lat_man)
        
        self.spin_roll_angle = QDoubleSpinBox()
        self.configure_spinbox(self.spin_roll_angle, "maxRollAngle", 5.0, 80.0, 1.0, 1)
        self.spin_roll_angle.setValue(self.params["maxRollAngle"])
        self.spin_roll_angle.setSuffix(" °")
        lat_form.addRow(f"{self.tr('label_roll', 'Rollwinkel (FixedWing, Φ)')} ({default_label}: {roll_def:.1f} °):", self.spin_roll_angle)
 
        self.spin_pitch_angle = QDoubleSpinBox()
        self.configure_spinbox(self.spin_pitch_angle, "maxPitchAngle", 5.0, 80.0, 1.0, 1)
        self.spin_pitch_angle.setValue(self.params["maxPitchAngle"])
        self.spin_pitch_angle.setSuffix(" °")
        lat_form.addRow(f"{self.tr('label_pitch', 'Nickwinkel (Multikopter, Θ)')} ({default_label}: {pitch_def:.1f} °):", self.spin_pitch_angle)
        
        self.spin_para_lat = QDoubleSpinBox()
        self.configure_spinbox(self.spin_para_lat, "parachuteOpeningTimeLateral", 0.1, 20.0, 0.1, 1)
        self.spin_para_lat.setValue(self.params["parachuteOpeningTimeLateral"])
        self.spin_para_lat.setSuffix(" s")
        lat_form.addRow(f"{self.tr('label_para_lat', 'Fallschirm Öffnungszeit (lat)')} ({default_label}: {para_lat_def:.1f} s):", self.spin_para_lat)
        
        man_layout.addWidget(group_lat)
        
        # Vertical group
        group_vert = QGroupBox(self.tr("group_vert", "Vertikales Contingency Manöver"))
        vert_form = QFormLayout(group_vert)
        
        self.combo_vert_man = QComboBox()
        self.combo_vert_man.addItems([self.tr("man_default_vert", "Standard (Energiewandlung / Climb)"), self.tr("man_parachute", "Auslösen des Fallschirms")])
        if self.params["verticalContingencyManoeuvreType"] in ["Parachute", "Auslösen des Fallschirms"]:
            self.combo_vert_man.setCurrentIndex(1)
        else:
            self.combo_vert_man.setCurrentIndex(0)
        vert_form.addRow(self.tr("manoeuvre_type", "Manövertyp:"), self.combo_vert_man)
        
        self.spin_para_vert = QDoubleSpinBox()
        self.configure_spinbox(self.spin_para_vert, "parachuteOpeningTimeVertical", 0.1, 20.0, 0.1, 1)
        self.spin_para_vert.setValue(self.params["parachuteOpeningTimeVertical"])
        self.spin_para_vert.setSuffix(" s")
        vert_form.addRow(f"{self.tr('label_para_vert', 'Fallschirm Öffnungszeit (vert)')} ({default_label}: {para_vert_def:.1f} s):", self.spin_para_vert)
        
        man_layout.addWidget(group_vert)

        # ----------------------------------------------------
        # TAB 4: GROUND RISK BUFFER (GRB)
        # ----------------------------------------------------
        grb_layout = QFormLayout(self.tab_grb)
        grb_layout.setMargin(15)
        
        self.combo_grb_method = QComboBox()
        self.combo_grb_method.addItems([
            self.tr("grb_simplified", "Vereinfachter Ansatz (1:1 Regel)"), 
            self.tr("grb_ballistic", "Ballistischer Ansatz"), 
            self.tr("grb_glide", "Antrieb aus mit Gleitflug"), 
            self.tr("grb_parachute", "Terminierung mit Auslösen des Fallschirms")
        ])
        
        m_map = {
            "Simplified": 0, "Vereinfachter Ansatz (1:1 Regel)": 0,
            "Ballistic": 1, "Ballistischer Ansatz": 1,
            "Glide": 2, "Antrieb wird ausgeschaltet mit Gleitflug": 2,
            "Parachute": 3, "Terminierung mit Auslösen des Fallschirms": 3
        }
        self.combo_grb_method.setCurrentIndex(m_map.get(self.params["groundRiskBufferMethod"], 0))
        grb_layout.addRow(self.tr("label_grb_method", "Terminierungsmethode (GRB):"), self.combo_grb_method)
        
        self.spin_glide = QDoubleSpinBox()
        self.configure_spinbox(self.spin_glide, "glideRatioDenominator", 1.0, 100.0, 0.5, 1)
        self.spin_glide.setValue(self.params["glideRatioDenominator"])
        self.spin_glide.setSuffix(" : 1")
        grb_layout.addRow(f"{self.tr('label_glide', 'Gleitzahl (E)')} ({default_label}: {glide_def:.1f} : 1):", self.spin_glide)
        
        self.spin_para_grb = QDoubleSpinBox()
        self.configure_spinbox(self.spin_para_grb, "parachuteOpeningTimeGRB", 0.1, 20.0, 0.1, 1)
        self.spin_para_grb.setValue(self.params["parachuteOpeningTimeGRB"])
        self.spin_para_grb.setSuffix(" s")
        grb_layout.addRow(f"{self.tr('label_para_grb', 'Fallschirm Öffnungszeit (GRB)')} ({default_label}: {para_grb_def:.1f} s):", self.spin_para_grb)
        
        self.spin_wind = QDoubleSpinBox()
        self.configure_spinbox(self.spin_wind, "maxWindVelocity", 0.0, 50.0, 0.5, 1)
        self.spin_wind.setValue(self.params["maxWindVelocity"])
        self.spin_wind.setSuffix(" m/s")
        grb_layout.addRow(f"{self.tr('label_wind', 'Max. zulässige Windgeschwindigkeit')} ({default_label}: {wind_def:.1f} m/s):", self.spin_wind)
        
        self.spin_descent = QDoubleSpinBox()
        self.configure_spinbox(self.spin_descent, "parachuteDescentRate", 0.1, 50.0, 0.5, 1)
        self.spin_descent.setValue(self.params["parachuteDescentRate"])
        self.spin_descent.setSuffix(" m/s")
        grb_layout.addRow(f"{self.tr('label_descent', 'Fallschirm Sinkgeschwindigkeit (vZ)')} ({default_label}: {descent_def:.1f} m/s):", self.spin_descent)

        # ----------------------------------------------------
        # TAB 5: GENERAL CORRIDOR SETTINGS
        # ----------------------------------------------------
        gen_layout = QFormLayout(self.tab_general)
        gen_layout.setMargin(15)
        
        self.spin_corridor_width = QDoubleSpinBox()
        self.configure_spinbox(self.spin_corridor_width, "corridorWidth", 1.0, 5000.0, 5.0, 1)
        self.spin_corridor_width.setValue(self.params["corridorWidth"])
        self.spin_corridor_width.setSuffix(" m")
        gen_layout.addRow(f"{self.tr('label_corridor_width', 'Standard Flight Geography Breite (W_FG)')} ({default_label}: {w_fg_def:.1f} m):", self.spin_corridor_width)
        
        self.chk_override_w = QCheckBox(self.tr("chk_override_w", "Individuelle Wegpunktbreiten überschreiben"))
        self.chk_override_w.setStyleSheet("color: #d97706; font-weight: bold;")
        self.chk_override_w.setChecked(False)
        self.has_custom_w = self.has_individual_widths()
        self.chk_override_w.setVisible(self.has_custom_w)
        self.chk_override_w.toggled.connect(self.on_override_w_toggled)
        gen_layout.addRow("", self.chk_override_w)
        
        if self.has_custom_w:
            self.spin_corridor_width.setEnabled(False)
        
        self.spin_default_h = QDoubleSpinBox()
        self.configure_spinbox(self.spin_default_h, "maxFlightHeight", 0.0, 2000.0, 5.0, 1)
        self.spin_default_h.setValue(self.params["maxFlightHeight"])
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
            # Recreate baseline default parameter dictionary
            baseline_defaults = {
                "uas_type": "FixedWing",
                "altimetry": "GPS",
                "maxOpsSpeedV0": 30.0,
                "maxCommandableSpeedVmax": 30.0,
                "maxCharacteristicDimension": 3.6,
                "maxRollAngle": 30.0,
                "maxPitchAngle": 30.0,
                "glideRatioDenominator": 10.0,
                "maxWindVelocity": 3.0,
                "stallVelocity": 10.0,
                "gpsInaccuracy": 3.0,
                "positionError": 3.0,
                "mapError": 1.0,
                "reactionTime": 1.0,
                "altitudeErrorGps": 4.0,
                "altitudeErrorBarometric": 1.0,
                "corridorWidth": 50.0,
                "maxFlightHeight": 100.0,
                "groundRiskBufferMethod": "Simplified",
                "lateralContingencyManoeuvreType": "Default",
                "verticalContingencyManoeuvreType": "Default",
                "parachuteOpeningTimeLateral": 2.0,
                "parachuteOpeningTimeVertical": 2.0,
                "parachuteOpeningTimeGRB": 2.0,
                "parachuteDescentRate": 2.0,
                "additionalErrorLateral": 0.0,
                "additionalErrorVertical": 0.0
            }
            
            # Apply config defaults to baseline params
            defaults = baseline_defaults.copy()
            if self.config_defaults:
                defaults.update(self.config_defaults)
                
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
                # Apply defaults
                uas_type = defaults.get("uas_type", "FixedWing")
                self.combo_uas_type.setCurrentIndex(1 if uas_type == "Multikopter" else 0)
                
                altimetry = defaults.get("altimetry", "GPS")
                self.combo_altimetry.setCurrentIndex(1 if altimetry in ["Baro", "barometrisch"] else 0)
                
                lat_man = defaults.get("lateralContingencyManoeuvreType", "Default")
                self.combo_lat_man.setCurrentIndex(1 if lat_man in ["Parachute", "Auslösen des Fallschirms"] else 0)
                
                vert_man = defaults.get("verticalContingencyManoeuvreType", "Default")
                self.combo_vert_man.setCurrentIndex(1 if vert_man in ["Parachute", "Auslösen des Fallschirms"] else 0)
                
                grb_method = defaults.get("groundRiskBufferMethod", "Simplified")
                m_map = {
                    "Simplified": 0, "Vereinfachter Ansatz (1:1 Regel)": 0,
                    "Ballistic": 1, "Ballistischer Ansatz": 1,
                    "Glide": 2, "Antrieb wird ausgeschaltet mit Gleitflug": 2,
                    "Parachute": 3, "Terminierung mit Auslösen des Fallschirms": 3
                }
                self.combo_grb_method.setCurrentIndex(m_map.get(grb_method, 0))
                
                self.spin_v0.setValue(defaults.get("maxOpsSpeedV0", 30.0))
                self.spin_vmax.setValue(defaults.get("maxCommandableSpeedVmax", 30.0))
                self.spin_cd.setValue(defaults.get("maxCharacteristicDimension", 3.6))
                self.spin_stall.setValue(defaults.get("stallVelocity", 10.0))
                
                self.spin_gps_inacc.setValue(defaults.get("gpsInaccuracy", 3.0))
                self.spin_pos_err.setValue(defaults.get("positionError", 3.0))
                self.spin_map_err.setValue(defaults.get("mapError", 1.0))
                self.spin_t_rz.setValue(defaults.get("reactionTime", 1.0))
                self.spin_alt_gps.setValue(defaults.get("altitudeErrorGps", 4.0))
                self.spin_alt_baro.setValue(defaults.get("altitudeErrorBarometric", 1.0))
                self.spin_add_horiz.setValue(defaults.get("additionalErrorLateral", 0.0))
                self.spin_add_vert.setValue(defaults.get("additionalErrorVertical", 0.0))
                
                self.spin_roll_angle.setValue(defaults.get("maxRollAngle", 30.0))
                self.spin_pitch_angle.setValue(defaults.get("maxPitchAngle", 30.0))
                self.spin_para_lat.setValue(defaults.get("parachuteOpeningTimeLateral", 2.0))
                self.spin_para_vert.setValue(defaults.get("parachuteOpeningTimeVertical", 2.0))
                
                self.spin_glide.setValue(defaults.get("glideRatioDenominator", 10.0))
                self.spin_para_grb.setValue(defaults.get("parachuteOpeningTimeGRB", 2.0))
                self.spin_wind.setValue(defaults.get("maxWindVelocity", 3.0))
                self.spin_descent.setValue(defaults.get("parachuteDescentRate", 2.0))
                
                self.spin_corridor_width.setValue(defaults.get("corridorWidth", 50.0))
                self.spin_default_h.setValue(defaults.get("maxFlightHeight", 100.0))
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
        
        # Disable/enable "Antrieb aus mit Gleitflug" (index 2) in combo_grb_method
        model = self.combo_grb_method.model()
        item = model.item(2)
        if item:
            item.setEnabled(is_fixed)
            
        if not is_fixed and self.combo_grb_method.currentIndex() == 2:
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
            "override_speeds": self.chk_override_v.isChecked() if (hasattr(self, 'chk_override_v') and self.has_custom_v) else True
        }

    def on_override_h_toggled(self, checked):
        self.spin_default_h.setEnabled(checked)
        if checked:
            new_h = self.spin_default_h.value()
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                lon, lat = w[0], w[1]
                spd = w[3] if len(w) > 3 else float(self.params.get("maxOpsSpeedV0", self.params.get("maxVelocity", 30.0)))
                fg = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
                self.waypoints[idx] = (lon, lat, new_h, spd, fg)
            self.on_value_changed()

    def on_override_w_toggled(self, checked):
        self.spin_corridor_width.setEnabled(checked)
        if checked:
            new_w = self.spin_corridor_width.value()
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                lon, lat = w[0], w[1]
                alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
                spd = w[3] if len(w) > 3 else float(self.params.get("maxOpsSpeedV0", self.params.get("maxVelocity", 30.0)))
                self.waypoints[idx] = (lon, lat, alt, spd, new_w)
            self.on_value_changed()

    def on_override_v_toggled(self, checked):
        self.spin_v0.setEnabled(checked)
        if checked:
            new_v = self.spin_v0.value()
            for idx in range(len(self.waypoints)):
                w = self.waypoints[idx]
                lon, lat = w[0], w[1]
                alt = w[2] if len(w) > 2 else float(self.params.get("maxFlightHeight", 100.0))
                fg = w[4] if len(w) > 4 else float(self.params.get("corridorWidth", 50.0))
                self.waypoints[idx] = (lon, lat, alt, new_v, fg)
            self.on_value_changed()

    def has_individual_heights(self):
        if not self.waypoints:
            return False
        standard = self.params.get("maxFlightHeight", 100.0)
        return any(len(w) > 2 and abs(w[2] - standard) > 1e-3 for w in self.waypoints)

    def has_individual_widths(self):
        if not self.waypoints:
            return False
        standard = self.params.get("corridorWidth", 50.0)
        return any(len(w) > 4 and abs(w[4] - standard) > 1e-3 for w in self.waypoints)

    def has_individual_speeds(self):
        if not self.waypoints:
            return False
        standard = self.params.get("maxOpsSpeedV0", self.params.get("maxVelocity", 30.0))
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
            h = params.get("maxFlightHeight", 100.0)
            r_fg, r_cv, r_grb, h_cv = BufferCalculator.calculate_buffer_widths(h, params)
            s_cv_list.append(r_cv - r_fg)
        else:
            for w in self.waypoints:
                h = w[2] if len(w) > 2 else params.get("maxFlightHeight", 100.0)
                spd = w[3] if len(w) > 3 else params.get("maxOpsSpeedV0", params.get("maxVelocity", 30.0))
                fg = w[4] if len(w) > 4 else params.get("corridorWidth", 50.0)
                
                params_wp = params.copy()
                params_wp["maxOpsSpeedV0"] = spd
                params_wp["maxVelocity"] = spd
                params_wp["corridorWidth"] = fg
                
                r_fg, r_cv, r_grb, h_cv = BufferCalculator.calculate_buffer_widths(h, params_wp)
                s_cv_list.append(r_cv - r_fg)
                
        return s_cv_list

    def check_cv_warnings(self):
        s_cv_list = self.get_s_cv_values()
        has_warning = any(x < 9.99 for x in s_cv_list) if s_cv_list else False
        
        if has_warning:
            text = self.tr(
                "msg_cv_warning_banner",
                "⚠️ <b>Hinweis zum Contingency Volume (CV):</b><br>"
                "In mindestens einem Abschnitt beträgt die berechnete Pufferbreite (s_cv) weniger als 10,0 m. "
                "Nach EASA SORA (AMC1 zu Artikel 11) wird eine Mindestbreite von 10 Metern empfohlen. "
                "Bitte begründen Sie den geringeren Puffer betrieblich in Ihrem ConOps."
            )
            self.lbl_cv_warning.setText(text)
            self.lbl_cv_warning.setVisible(True)
        else:
            self.lbl_cv_warning.setVisible(False)
