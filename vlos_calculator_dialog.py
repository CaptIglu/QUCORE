# -*- coding: utf-8 -*-
import os
import json
from qgis.gui import QgsMapCanvas
from .config_manager import ConfigManager
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QDialogButtonBox,
    QGroupBox
)

class VlosCalculatorDialog(QDialog):
    def __init__(self, parent=None, uas_type="FixedWing", cd=3.6, current_params=None):
        super(VlosCalculatorDialog, self).__init__(parent)
        self.resize(450, 340)
        self.setModal(True)
        self.uas_type = uas_type
        self.cd = cd
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
                
        self.setWindowTitle(self.tr("dialog_vlos_title", "VLOS-Rechner (ALOS/DLOS)"))
        self.init_ui()
        self.recalculate()

    def tr(self, key, default=""):
        lang = ConfigManager.get_param(self.params, "language")
        return self.tr_strings.get(key, {}).get(lang, default)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Info Header
        info_label = QLabel(
            self.tr("vlos_desc", 
                    "Berechnung der maximalen Sichtweite (VLOS) gemäß den EASA/LBA-Richtlinien "
                    "basierend auf der Größe der Drohne (ALOS) und der Bodensicht (DLOS).")
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #444; margin-bottom: 5px; font-style: italic;")
        layout.addWidget(info_label)
        
        # Input Group
        input_group = QGroupBox(self.tr("group_inputs", "Eigenschaften des UAS & Piloten"))
        form_layout = QFormLayout(input_group)
        form_layout.setSpacing(10)
        
        self.cmb_uas_type = QComboBox()
        self.cmb_uas_type.addItems([
            self.tr("uas_fw", "Flächenflieger (Fixed Wing)"), 
            self.tr("uas_mc_rot", "Multikopter / Drehflügler")
        ])
        if self.uas_type == "Multikopter":
            self.cmb_uas_type.setCurrentIndex(1)
        else:
            self.cmb_uas_type.setCurrentIndex(0)
        self.cmb_uas_type.currentIndexChanged.connect(self.recalculate)
        form_layout.addRow(self.tr("uas_type", "UAS Typ:"), self.cmb_uas_type)
        
        self.spin_cd = QDoubleSpinBox()
        self.spin_cd.setRange(0.01, 100.0)
        self.spin_cd.setValue(self.cd)
        self.spin_cd.setSuffix(" m")
        self.spin_cd.setDecimals(2)
        self.spin_cd.setSingleStep(0.1)
        self.spin_cd.valueChanged.connect(self.recalculate)
        form_layout.addRow(self.tr("label_cd", "Charakteristische Dimension (CD):"), self.spin_cd)
        
        self.spin_gv = QDoubleSpinBox()
        self.spin_gv.setRange(0.0, 5000.0)
        self.spin_gv.setValue(5000.0)
        self.spin_gv.setSuffix(" m")
        self.spin_gv.setDecimals(0)
        self.spin_gv.setSingleStep(100.0)
        self.spin_gv.valueChanged.connect(self.recalculate)
        form_layout.addRow(self.tr("label_gv", "Aktuelle Bodensicht (GV, max. 5000m):"), self.spin_gv)
        
        layout.addWidget(input_group)
        
        # Output Group
        output_group = QGroupBox(self.tr("group_results", "Berechnete Sichtweiten-Grenzwerte"))
        out_layout = QFormLayout(output_group)
        out_layout.setSpacing(8)
        
        self.lbl_alos = QLabel("0.0 m")
        self.lbl_alos.setStyleSheet("font-weight: bold; color: #2D9CDB;")
        out_layout.addRow(self.tr("label_alos", "Attitude Line of Sight (ALOSmax):"), self.lbl_alos)
        
        self.lbl_dlos = QLabel("0.0 m")
        self.lbl_dlos.setStyleSheet("font-weight: bold; color: #2D9CDB;")
        out_layout.addRow(self.tr("label_dlos", "Detection Line of Sight (DLOSmax):"), self.lbl_dlos)
        
        self.lbl_vlos = QLabel("0.0 m")
        self.lbl_vlos.setStyleSheet("font-weight: bold; font-size: 14px; color: #219653;")
        out_layout.addRow(f"<b>{self.tr('label_vlos_max', 'Maximale VLOS-Distanz (VLOSmax):')}</b>", self.lbl_vlos)
        
        layout.addWidget(output_group)
        
        # Bottom Close Button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def recalculate(self):
        is_multicopter = (self.cmb_uas_type.currentIndex() == 1)
        cd = self.spin_cd.value()
        gv = self.spin_gv.value()
        
        # 1. Calculate ALOS
        if is_multicopter:
            # ALOS = 327 * CD + 20
            alos = 327.0 * cd + 20.0
        else:
            # ALOS = 490 * CD + 30
            alos = 490.0 * cd + 30.0
            
        # 2. Calculate DLOS
        dlos = 0.3 * min(gv, 5000.0)
        
        # 3. VLOS is the minimum
        vlos = min(alos, dlos)
        
        # Update labels
        self.lbl_alos.setText(f"{alos:.1f} m")
        self.lbl_dlos.setText(f"{dlos:.1f} m")
        self.lbl_vlos.setText(f"{vlos:.1f} m")
        
        # Fire callback to sync with parent planner in QGIS
        new_uas_type = "Multikopter" if is_multicopter else "FixedWing"
        if hasattr(self, 'on_change_callback') and self.on_change_callback:
            self.on_change_callback(cd, new_uas_type)
