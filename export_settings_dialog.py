# -*- coding: utf-8 -*-
import os
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QDoubleSpinBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout
)

class ExportSettingsDialog(QDialog):
    def __init__(self, parent=None, default_height=100.0, default_speed=30.0, default_fg_width=50.0, params=None):
        super(ExportSettingsDialog, self).__init__(parent)
        self.resize(350, 220)
        self.setModal(True)
        self.params = params if params is not None else {}
        
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
                
        self.setWindowTitle(self.tr("dialog_export_title", "Parameter für den Export festlegen"))
        
        main_layout = QVBoxLayout(self)
        
        # Info Header
        info_label = QLabel(
            self.tr("dialog_export_desc", 
                    "Beim Exportieren einer dipul- oder flightplan-Datei müssen die veränderlichen Wegpunkt-Parameter "
                    "(Höhe, Geschwindigkeit und Flight Geography Breite) in konstante Werte überführt werden, um den "
                    "offiziellen Formatspezifikationen zu entsprechen. Bitte legen Sie diese konstanten Werte hier fest:")
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { margin-bottom: 10px; font-size: 11px; }")
        main_layout.addWidget(info_label)
        
        # Form Layout
        form_layout = QFormLayout()
        
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(0.0, 2000.0)
        self.spin_height.setDecimals(1)
        self.spin_height.setSingleStep(5.0)
        self.spin_height.setValue(default_height)
        self.spin_height.setSuffix(" m")
        self.spin_height.setStyleSheet("QDoubleSpinBox { padding: 4px; font-weight: bold; }")
        form_layout.addRow(self.tr("label_export_height", "Konstante Flughöhe (m):"), self.spin_height)
        
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.1, 200.0)
        self.spin_speed.setDecimals(1)
        self.spin_speed.setSingleStep(1.0)
        self.spin_speed.setValue(default_speed)
        self.spin_speed.setSuffix(" m/s")
        self.spin_speed.setStyleSheet("QDoubleSpinBox { padding: 4px; font-weight: bold; }")
        form_layout.addRow(self.tr("label_export_speed", "Konstante Geschwindigkeit (m/s):"), self.spin_speed)
        
        self.spin_fg_width = QDoubleSpinBox()
        self.spin_fg_width.setRange(1.0, 5000.0)
        self.spin_fg_width.setDecimals(1)
        self.spin_fg_width.setSingleStep(5.0)
        self.spin_fg_width.setValue(default_fg_width)
        self.spin_fg_width.setSuffix(" m")
        self.spin_fg_width.setStyleSheet("QDoubleSpinBox { padding: 4px; font-weight: bold; }")
        form_layout.addRow(self.tr("label_export_fg_width", "Konstante FG-Breite (m):"), self.spin_fg_width)
        
        main_layout.addLayout(form_layout)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.setStyleSheet("QDialogButtonBox { margin-top: 10px; }")
        main_layout.addWidget(self.button_box)
        
    def tr(self, key, default=""):
        lang = self.params.get("language", "de")
        return self.tr_strings.get(key, {}).get(lang, default)
        
    def get_values(self):
        return self.spin_height.value(), self.spin_speed.value(), self.spin_fg_width.value()
