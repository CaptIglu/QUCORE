# -*- coding: utf-8 -*-
import os
import json
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QColor
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QFormLayout,
    QPushButton,
    QDialogButtonBox,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QColorDialog
)
from .translation_manager import TranslationManager
from .config_manager import ConfigManager

class AdvancedSettingsDialog(QDialog):
    def __init__(self, parent=None, config_path=None, current_step_size=50.0, current_params=None):
        super(AdvancedSettingsDialog, self).__init__(parent)
        self.setWindowTitle("Erweiterte Einstellungen & Standardwerte")
        self.resize(550, 480)
        self.setModal(True)
        self.config_path = config_path
        self.step_size = current_step_size
        
        # Load all default parameters and limits directly from ConfigManager
        self.config_params = ConfigManager.get_instance().get_default_params()
        self.config_limits = ConfigManager.get_instance().get_limits()

        # Apply current in-memory parameters to reflect the active session
        if current_params:
            self.config_params.update(current_params)
            
        # Load translations
        # self.tr_strings logic removed in favor of TranslationManager
        

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
        lang = self.config_params.get("language", "de")
        return TranslationManager.tr(key, lang, default)

    def init_ui(self):
        self.setWindowTitle(self.tr("dialog_adv_settings_title", "Erweiterte Einstellungen & Standardwerte"))
        layout = QVBoxLayout(self)
        
        # Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Allgemeine Einstellungen (UI-Editable)
        self.tab_general = QWidget()
        lay_gen = QVBoxLayout(self.tab_general)
        
        form_gen = QFormLayout()
        form_gen.setContentsMargins(15, 15, 15, 15)
        form_gen.setSpacing(15)
        
        self.spin_step = QDoubleSpinBox()
        self.configure_spinbox(self.spin_step, "stepSize", 1.0, 1000.0, 5.0, 1)
        self.spin_step.setValue(self.step_size)
        self.spin_step.setSuffix(" m")
        
        desc_label = QLabel(self.tr("step_desc", "Die Schrittweite legt fest, in welchen Abständen entlang der Route Zwischenwerte interpoliert und berechnet werden. Ein kleinerer Wert erhöht die Genauigkeit und Krümmungssicherheit des Ground Risk Buffers (ballistischer Ansatz), erzeugt jedoch mehr Geometrie-Stützpunkte."))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #555; font-style: italic; margin-bottom: 10px;")
        
        form_gen.addRow(desc_label)
        form_gen.addRow(self.tr("step_size", "Interpolations-Schrittweite (für GRB):"), self.spin_step)
        
        lay_gen.addLayout(form_gen)
        lay_gen.addStretch()
        
        # Tab 2: Darstellungseinstellungen (UI-Editable)
        self.tab_style = QWidget()
        lay_style = QVBoxLayout(self.tab_style)
        
        form_style = QFormLayout()
        form_style.setContentsMargins(15, 15, 15, 15)
        form_style.setSpacing(10)
        
        style_desc = QLabel(self.tr("style_desc", "<b>Hinweis:</b> Änderungen an der Darstellung (Linienstärke, Farbe, Deckkraft) in diesem Dialog gelten nur für die aktuelle Sitzung. Dauerhafte Einstellungen können Sie durch direktes Bearbeiten der <code>config.json</code>-Datei vornehmen."))
        style_desc.setWordWrap(True)
        style_desc.setStyleSheet("margin-bottom: 10px; color: #333;")
        form_style.addRow(style_desc)

        # Add column header label row
        header_layout = QHBoxLayout()
        header_width = QLabel(self.tr("header_lw", "<b>Stärke</b>"))
        header_width.setAlignment(Qt.AlignCenter)
        header_width.setFixedWidth(80)
        header_color = QLabel(self.tr("header_col", "<b>Farbe</b>"))
        header_color.setAlignment(Qt.AlignCenter)
        header_color.setFixedWidth(70)
        header_opac = QLabel(self.tr("header_op", "<b>Deckkraft</b>"))
        header_opac.setAlignment(Qt.AlignCenter)
        header_opac.setFixedWidth(80)
        
        header_layout.addWidget(header_width)
        header_layout.addSpacing(15)
        header_layout.addWidget(header_color)
        header_layout.addSpacing(15)
        header_layout.addWidget(header_opac)
        form_style.addRow("", header_layout)
        
        # 1. Route
        self.spin_lw_route = QDoubleSpinBox()
        self.configure_spinbox(self.spin_lw_route, "linewidth_route", 0.1, 10.0, 0.1, 2)
        self.spin_lw_route.setSuffix(" mm")
        self.spin_lw_route.setValue(self.config_params.get("linewidth_route", 1.0))
        self.btn_col_route = QPushButton()
        self.update_color_button(self.btn_col_route, self.config_params.get("color_route", "#50505a"))
        self.create_layer_row(form_style, self.tr("lyr_route", "Flugweg (Mittelachse):"), self.spin_lw_route, self.btn_col_route, None)
        
        # 2. FG
        self.spin_lw_fg = QDoubleSpinBox()
        self.configure_spinbox(self.spin_lw_fg, "linewidth_fg", 0.1, 10.0, 0.1, 2)
        self.spin_lw_fg.setSuffix(" mm")
        self.spin_lw_fg.setValue(self.config_params.get("linewidth_fg", 1.0))
        self.btn_col_fg = QPushButton()
        self.update_color_button(self.btn_col_fg, self.config_params.get("color_fg", "#397c59"))
        self.spin_op_fg = QSpinBox()
        self.configure_spinbox(self.spin_op_fg, "opacity_fg", 0, 100, 1)
        self.spin_op_fg.setSuffix(" %")
        self.spin_op_fg.setValue(self.config_params.get("opacity_fg", 15))
        self.create_layer_row(form_style, self.tr("lyr_fg", "Flight Geography (FG):"), self.spin_lw_fg, self.btn_col_fg, self.spin_op_fg)
        
        # 3. CV
        self.spin_lw_cv = QDoubleSpinBox()
        self.configure_spinbox(self.spin_lw_cv, "linewidth_cv", 0.1, 10.0, 0.1, 2)
        self.spin_lw_cv.setSuffix(" mm")
        self.spin_lw_cv.setValue(self.config_params.get("linewidth_cv", 1.0))
        self.btn_col_cv = QPushButton()
        self.update_color_button(self.btn_col_cv, self.config_params.get("color_cv", "#f7bb3d"))
        self.spin_op_cv = QSpinBox()
        self.configure_spinbox(self.spin_op_cv, "opacity_cv", 0, 100, 1)
        self.spin_op_cv.setSuffix(" %")
        self.spin_op_cv.setValue(self.config_params.get("opacity_cv", 15))
        self.create_layer_row(form_style, self.tr("lyr_cv", "Contingency Volume (CV):"), self.spin_lw_cv, self.btn_col_cv, self.spin_op_cv)
        
        # 4. GRB
        self.spin_lw_grb = QDoubleSpinBox()
        self.configure_spinbox(self.spin_lw_grb, "linewidth_grb", 0.1, 10.0, 0.1, 2)
        self.spin_lw_grb.setSuffix(" mm")
        self.spin_lw_grb.setValue(self.config_params.get("linewidth_grb", 1.0))
        self.btn_col_grb = QPushButton()
        self.update_color_button(self.btn_col_grb, self.config_params.get("color_grb", "#eb5757"))
        self.spin_op_grb = QSpinBox()
        self.configure_spinbox(self.spin_op_grb, "opacity_grb", 0, 100, 1)
        self.spin_op_grb.setSuffix(" %")
        self.spin_op_grb.setValue(self.config_params.get("opacity_grb", 15))
        self.create_layer_row(form_style, self.tr("lyr_grb", "Ground Risk Buffer (GRB):"), self.spin_lw_grb, self.btn_col_grb, self.spin_op_grb)
        
        # 5. AA
        self.spin_lw_aga = QDoubleSpinBox()
        self.configure_spinbox(self.spin_lw_aga, "linewidth_adjacentarea", 0.1, 10.0, 0.1, 2)
        self.spin_lw_aga.setSuffix(" mm")
        self.spin_lw_aga.setValue(self.config_params.get("linewidth_adjacentarea", 1.0))
        self.btn_col_aga = QPushButton()
        self.update_color_button(self.btn_col_aga, self.config_params.get("color_adjacentarea", "#2980b9"))
        self.spin_op_aga = QSpinBox()
        self.configure_spinbox(self.spin_op_aga, "opacity_adjacentarea", 0, 100, 1)
        self.spin_op_aga.setSuffix(" %")
        self.spin_op_aga.setValue(self.config_params.get("opacity_adjacentarea", 0))
        self.create_layer_row(form_style, self.tr("lyr_aa", "Adjacent Area (AA):"), self.spin_lw_aga, self.btn_col_aga, self.spin_op_aga)
        
        # 6. VLOS
        self.spin_lw_vlos = QDoubleSpinBox()
        self.configure_spinbox(self.spin_lw_vlos, "linewidth_vlos", 0.1, 10.0, 0.1, 2)
        self.spin_lw_vlos.setSuffix(" mm")
        self.spin_lw_vlos.setValue(self.config_params.get("linewidth_vlos", 0.8))
        self.btn_col_vlos = QPushButton()
        self.update_color_button(self.btn_col_vlos, self.config_params.get("color_vlos", "#2d9cdb"))
        self.spin_op_vlos = QSpinBox()
        self.configure_spinbox(self.spin_op_vlos, "opacity_vlos", 0, 100, 1)
        self.spin_op_vlos.setSuffix(" %")
        self.spin_op_vlos.setValue(self.config_params.get("opacity_vlos", 0))
        self.create_layer_row(form_style, self.tr("lyr_vlos", "VLOS-Reichweite (Pilotenposition):"), self.spin_lw_vlos, self.btn_col_vlos, self.spin_op_vlos)
        
        # Verbindungen für die Farbauswahl-Buttons
        self.btn_col_route.clicked.connect(lambda: self.pick_color(self.btn_col_route))
        self.btn_col_fg.clicked.connect(lambda: self.pick_color(self.btn_col_fg))
        self.btn_col_cv.clicked.connect(lambda: self.pick_color(self.btn_col_cv))
        self.btn_col_grb.clicked.connect(lambda: self.pick_color(self.btn_col_grb))
        self.btn_col_aga.clicked.connect(lambda: self.pick_color(self.btn_col_aga))
        self.btn_col_vlos.clicked.connect(lambda: self.pick_color(self.btn_col_vlos))
        
        lay_style.addLayout(form_style)
        lay_style.addStretch()
        
        # Tab 3: Standard-Berechnungswerte (Read-Only)
        self.tab_defaults = QWidget()
        lay_def = QVBoxLayout(self.tab_defaults)
        
        info_def = QLabel(self.tr("defaults_info", "<b>Hinweis:</b> Die folgenden Parameter stellen die Standardwerte gemäß dem LBA-Leitfaden dar. Diese Liste ist schreibgeschützt. Um diese Werte dauerhaft anzupassen, bearbeiten Sie bitte die <code>config.json</code>-Datei über den Button unten."))
        info_def.setWordWrap(True)
        info_def.setStyleSheet("margin-bottom: 10px; color: #333;")
        lay_def.addWidget(info_def)
        
        # Tree Widget for Grouped Display
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([self.tr("tree_param", "Parameter"), self.tr("tree_value", "Standardwert")])
        self.tree.setColumnWidth(0, 320)
        lay_def.addWidget(self.tree)
        
        self.populate_defaults_tree()
        
        # Layout for actions
        lay_actions = QHBoxLayout()
        
        # Restore Defaults Button
        self.btn_restore = QPushButton(self.tr("msg_restore_defaults_title", "Standardwerte wiederherstellen"))
        self.btn_restore.clicked.connect(self.restore_defaults)
        lay_actions.addWidget(self.btn_restore)
        
        # Open Config File Button
        btn_open_config = QPushButton(self.tr("btn_open_config", "Konfigurationsdatei (config.json) öffnen..."))
        btn_open_config.clicked.connect(self.open_config_file)
        lay_actions.addWidget(btn_open_config)
        
        lay_def.addLayout(lay_actions)
        
        # Add tabs in the specified order:
        # 1. Darstellung
        # 2. Standardwerte
        # 3. Interpolationsschrittweite (formerly Allgemeine Einstellungen)
        self.tabs.addTab(self.tab_style, self.tr("tab_style", "Darstellung"))
        self.tabs.addTab(self.tab_defaults, self.tr("tab_defaults", "Standardwerte (LBA-Leitfaden)"))
        self.tabs.addTab(self.tab_general, self.tr("tab_interpolation", "Interpolationsschrittweite"))
        
        # Bottom Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_defaults_tree(self):
        # Definitions of translation keys for groups and parameters
        grp_tr_keys = {
            "UAS Eigenschaften": "tree_grp_uas",
            "Sensorik & Unsicherheiten": "tree_grp_sensors",
            "Sicherheitsmanöver & Puffer": "tree_grp_manoeuvres",
            "Globale Korridoreinstellungen": "tree_grp_global"
        }
        
        label_tr_keys = {
            "uas_type": "uas_type",
            "maxVelocity": "label_v0",
            "maxCharacteristicDimension": "label_cd",
            "stallVelocity": "label_stall",
            "maxRollAngle": "label_roll",
            "maxPitchAngle": "label_pitch",
            "glideRatioDenominator": "label_glide",
            "altimetry": "altimetry",
            "gpsInaccuracy": "label_gps_inacc",
            "positionError": "label_pos_err",
            "mapError": "label_map_err",
            "reactionTime": "label_t_rz",
            "altitudeErrorGps": "label_alt_gps",
            "altitudeErrorBarometric": "label_alt_baro",
            "corridorWidth": "label_corridor_width",
            "maxFlightHeight": "label_default_height",
            "parachuteOpeningTimeLateral": "label_para_lat",
            "parachuteOpeningTimeVertical": "label_para_vert",
            "parachuteOpeningTimeGRB": "label_para_grb",
            "parachuteDescentRate": "label_descent",
            "maxWindVelocity": "label_wind",
            "additionalErrorLateral": "label_add_horiz",
            "additionalErrorVertical": "label_add_vert",
            "groundRiskBufferMethod": "label_grb_method",
            "lateralContingencyManoeuvreType": "manoeuvre_type",
            "verticalContingencyManoeuvreType": "manoeuvre_type"
        }

        groups = [
            ("UAS Eigenschaften", [
                ("uas_type", "UAS Typ", ""),
                ("maxVelocity", "Max. Betriebsgeschwindigkeit (v0)", " m/s"),
                ("maxCharacteristicDimension", "Charakteristische Dimension (CD)", " m"),
                ("stallVelocity", "Überziehgeschwindigkeit (stallVelocity)", " m/s"),
                ("maxRollAngle", "Max. Rollwinkel (Φ)", " °"),
                ("maxPitchAngle", "Max. Nickwinkel (Θ)", " °"),
                ("glideRatioDenominator", "Gleitzahl (E)", " : 1")
            ]),
            ("Sensorik & Unsicherheiten", [
                ("altimetry", "Höhenmessung", ""),
                ("gpsInaccuracy", "GPS Ungenauigkeit (SGPS)", " m"),
                ("positionError", "Positionshaltefehler (SPos)", " m"),
                ("mapError", "Kartenfehler (SK)", " m"),
                ("altitudeErrorGps", "GPS Höhenmessfehler", " m"),
                ("altitudeErrorBarometric", "Barometrischer Höhenmessfehler", " m")
            ]),
            ("Sicherheitsmanöver & Puffer", [
                ("reactionTime", "Fernpilot Reaktionszeit (tRZ)", " s"),
                ("groundRiskBufferMethod", "Ground Risk Buffer Methode", ""),
                ("lateralContingencyManoeuvreType", "Laterales Contingency-Manöver", ""),
                ("verticalContingencyManoeuvreType", "Vertikales Contingency-Manöver", ""),
                ("parachuteOpeningTimeLateral", "Fallschirm Öffnungszeit (lateral)", " s"),
                ("parachuteOpeningTimeVertical", "Fallschirm Öffnungszeit (vertikal)", " s"),
                ("parachuteOpeningTimeGRB", "Fallschirm Öffnungszeit (GRB)", " s"),
                ("parachuteDescentRate", "Fallschirm Sinkgeschwindigkeit (vZ)", " m/s"),
                ("maxWindVelocity", "Max. Windgeschwindigkeit", " m/s"),
                ("additionalErrorLateral", "Zusatzentfernung (lateral)", " m"),
                ("additionalErrorVertical", "Zusatzentfernung (vertikal)", " m")
            ]),
            ("Globale Korridoreinstellungen", [
                ("corridorWidth", "Standard Flight Geography Breite (W_FG)", " m"),
                ("maxFlightHeight", "Standard Flughöhe (h)", " m")
            ])
        ]
        
        # Add to Tree
        for group_name, params_list in groups:
            group_item = QTreeWidgetItem(self.tree)
            tr_group_name = self.tr(grp_tr_keys.get(group_name, ""), group_name)
            group_item.setText(0, tr_group_name)
            group_item.setExpanded(True)
            # Make group bold
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            
            for key, label, suffix in params_list:
                val = self.config_params.get(key, "N/A")
                
                # Format some specific text values nicely
                if key == "uas_type":
                    val = self.tr("uas_fw", "Flächenflieger (Fixed Wing)") if val == "FixedWing" else self.tr("uas_mc", "Multikopter")
                elif key == "altimetry":
                    val = self.tr("alt_gps", "GPS-basiert") if val == "GPS" else self.tr("alt_baro", "barometrisch").capitalize()
                elif key == "groundRiskBufferMethod":
                    m_map = {
                        "Simplified": self.tr("grb_simplified", "Vereinfachter Ansatz (1:1 Regel)"),
                        "Ballistic": self.tr("grb_ballistic", "Ballistischer Ansatz"),
                        "Glide": self.tr("grb_glide", "Antrieb aus mit Gleitflug"),
                        "Parachute": self.tr("grb_parachute", "Terminierung mit Auslösen des Fallschirms")
                    }
                    val = m_map.get(val, val)
                elif key in ["lateralContingencyManoeuvreType", "verticalContingencyManoeuvreType"]:
                    default_desc = self.tr("man_default_lat", "Standard (Kurve / Anhalten)") if key == "lateralContingencyManoeuvreType" else self.tr("man_default_vert", "Standard (Energiewandlung / Climb)")
                    val = self.tr("man_parachute", "Auslösen des Fallschirms") if val == "Parachute" else default_desc
                
                param_item = QTreeWidgetItem(group_item)
                tr_label = self.tr(label_tr_keys.get(key, ""), label).rstrip(":")
                param_item.setText(0, tr_label)
                param_item.setText(1, f"{val}{suffix}")
                
        self.tree.expandAll()

    def open_config_file(self):
        if self.config_path and os.path.exists(self.config_path):
            file_url = QUrl.fromLocalFile(self.config_path)
            QDesktopServices.openUrl(file_url)
        else:
            QMessageBox.warning(
                self,
                self.tr("msg_file_not_found_title", "Datei nicht gefunden"),
                self.tr("msg_config_not_found_text", "Die Konfigurationsdatei config.json konnte nicht im Plugin-Ordner gefunden werden.")
            )

    def restore_defaults(self):
        title = self.tr("msg_restore_defaults_title", "Standardwerte wiederherstellen")
        text = self.tr("msg_restore_defaults_text", "Möchten Sie wirklich alle Parameter auf die Standardwerte aus der config.json zurücksetzen?")
        reply = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            fresh_config = {}
            if self.config_path and os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        fresh_config = json.load(f)
                except Exception as e:
                    from qgis.core import QgsMessageLog, Qgis
                    import traceback
                    QgsMessageLog.logMessage(f"Silent exception caught in advanced_settings_dialog.py (line 415): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
            
            if not fresh_config:
                return
                
            self.config_params = fresh_config
            
            # Update step size spinbox
            self.spin_step.setValue(self.config_params.get("stepSize", 50.0))
            
            # Update representation parameters in UI
            self.spin_lw_route.setValue(self.config_params.get("linewidth_route", 1.0))
            self.update_color_button(self.btn_col_route, self.config_params.get("color_route", "#50505a"))
            
            self.spin_lw_fg.setValue(self.config_params.get("linewidth_fg", 1.0))
            self.update_color_button(self.btn_col_fg, self.config_params.get("color_fg", "#397c59"))
            self.spin_op_fg.setValue(self.config_params.get("opacity_fg", 15))
            
            self.spin_lw_cv.setValue(self.config_params.get("linewidth_cv", 1.0))
            self.update_color_button(self.btn_col_cv, self.config_params.get("color_cv", "#f7bb3d"))
            self.spin_op_cv.setValue(self.config_params.get("opacity_cv", 15))
            
            self.spin_lw_grb.setValue(self.config_params.get("linewidth_grb", 1.0))
            self.update_color_button(self.btn_col_grb, self.config_params.get("color_grb", "#eb5757"))
            self.spin_op_grb.setValue(self.config_params.get("opacity_grb", 15))
            
            self.spin_lw_aga.setValue(self.config_params.get("linewidth_adjacentarea", 1.0))
            self.update_color_button(self.btn_col_aga, self.config_params.get("color_adjacentarea", "#2980b9"))
            self.spin_op_aga.setValue(self.config_params.get("opacity_adjacentarea", 0))
            
            self.spin_lw_vlos.setValue(self.config_params.get("linewidth_vlos", 0.8))
            self.update_color_button(self.btn_col_vlos, self.config_params.get("color_vlos", "#2d9cdb"))
            self.spin_op_vlos.setValue(self.config_params.get("opacity_vlos", 0))
            
            # Refresh the Tree widget
            self.tree.clear()
            self.populate_defaults_tree()

    def get_step_size(self):
        return self.spin_step.value()

    def update_color_button(self, btn, color_hex):
        btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999; min-width: 60px; max-width: 60px; min-height: 20px;")
        btn.setProperty("color_hex", color_hex)

    def pick_color(self, btn):
        curr_color = QColor(btn.property("color_hex"))
        color = QColorDialog.getColor(curr_color, self, self.tr("dialog_color_picker_title", "Farbe wählen"))
        if color.isValid():
            hex_name = color.name()
            self.update_color_button(btn, hex_name)

    def create_layer_row(self, form, label_text, spin_w, btn_c, spin_o=None):
        h_lay = QHBoxLayout()
        
        # Style spin width
        spin_w.setFixedWidth(80)
        h_lay.addWidget(spin_w)
        h_lay.addSpacing(15)
        
        # Style color button (Editable, session-only)
        btn_c.setFixedWidth(70)
        btn_c.setEnabled(True)
        h_lay.addWidget(btn_c)
        h_lay.addSpacing(15)
        
        # Style opacity spin (Editable, session-only)
        if spin_o:
            spin_o.setFixedWidth(80)
            spin_o.setEnabled(True)
            h_lay.addWidget(spin_o)
        else:
            dummy = QLabel("N/A")
            dummy.setAlignment(Qt.AlignCenter)
            dummy.setFixedWidth(80)
            dummy.setStyleSheet("color: #888; font-style: italic;")
            h_lay.addWidget(dummy)
            
        form.addRow(label_text, h_lay)

    def get_linewidths(self):
        return self.get_style_params()

    def get_style_params(self):
        return {
            "linewidth_route": self.spin_lw_route.value(),
            "linewidth_fg": self.spin_lw_fg.value(),
            "linewidth_cv": self.spin_lw_cv.value(),
            "linewidth_grb": self.spin_lw_grb.value(),
            "linewidth_adjacentarea": self.spin_lw_aga.value(),
            "linewidth_vlos": self.spin_lw_vlos.value(),
            
            "color_route": self.btn_col_route.property("color_hex"),
            "color_fg": self.btn_col_fg.property("color_hex"),
            "color_cv": self.btn_col_cv.property("color_hex"),
            "color_grb": self.btn_col_grb.property("color_hex"),
            "color_adjacentarea": self.btn_col_aga.property("color_hex"),
            "color_vlos": self.btn_col_vlos.property("color_hex"),
            
            "opacity_fg": self.spin_op_fg.value(),
            "opacity_cv": self.spin_op_cv.value(),
            "opacity_grb": self.spin_op_grb.value(),
            "opacity_adjacentarea": self.spin_op_aga.value(),
            "opacity_vlos": self.spin_op_vlos.value()
        }

    def get_all_params(self):
        params = dict(self.config_params)
        params["stepSize"] = self.get_step_size()
        params.update(self.get_style_params())
        return params
