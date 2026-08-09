# -*- coding: utf-8 -*-
import math
from qgis.PyQt.QtCore import Qt, pyqtSignal, QRectF, QPointF
from qgis.PyQt.QtGui import QPainter, QColor, QPen, QFont, QPolygonF, QBrush
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QDoubleSpinBox, QLabel, QPushButton, QWidget
)
from .config_manager import ConfigManager
from .dialog_utils import QucoreBaseDialog

class WindCompassWidget(QWidget):
    def __init__(self, parent=None):
        super(WindCompassWidget, self).__init__(parent)
        self.setMinimumSize(150, 150)
        self.direction = 0.0
        self.variance = 15.0
        self.min_speed = 0.0
        self.speed = 0.0

    def set_values(self, direction, variance, min_speed, speed):
        self.direction = direction
        self.variance = variance
        self.min_speed = min_speed
        self.speed = speed
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        side = min(rect.width(), rect.height())
        center = QPointF(rect.width() / 2.0, rect.height() / 2.0)
        radius = (side / 2.0) - 10.0
        
        # Draw background circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#a0a0a0"))
        painter.drawEllipse(center, radius, radius)
        
        # Draw inner circle for text
        painter.setBrush(QColor("#b0b0b0"))
        inner_radius = radius * 0.55
        painter.drawEllipse(center, inner_radius, inner_radius)
        
        # Draw ticks and labels
        painter.translate(center)
        
        # Draw Ticks
        for i in range(360):
            if i % 10 == 0:
                length = 6.0 if i % 90 == 0 else 4.0
                pen = QPen(QColor(255, 255, 255, 200))
                pen.setWidth(2 if i % 90 == 0 else 1)
                painter.setPen(pen)
                
                # We want to draw from radius - length to radius
                p1 = QPointF(0, -radius + length)
                p2 = QPointF(0, -radius)
                painter.drawLine(p1, p2)
            
            painter.rotate(1)
            
        # Draw Labels
        font = painter.font()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 220))
        
        labels = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]
        label_radius = radius - 18.0
        for text, angle in labels:
            rad = math.radians(angle - 90)
            x = label_radius * math.cos(rad)
            y = label_radius * math.sin(rad)
            text_rect = QRectF(x - 10, y - 10, 20, 20)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
            
        # Draw Arrow indicating where the wind blows FROM (Meteorological convention)
        arrow_angle = self.direction
        painter.save()
        painter.rotate(arrow_angle)
        
        # Draw the arrow body pointing inward (towards the center)
        pen = QPen(QColor(255, 255, 255))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255))
        
        # From outer edge to center
        edge_y = -(radius - 15.0)
        center_y = -(inner_radius + 5.0)
        
        # Line
        painter.drawLine(QPointF(0, edge_y), QPointF(0, center_y))
        
        # Arrowhead (pointing inwards towards center)
        poly = QPolygonF([
            QPointF(0.0, center_y + 5.0),
            QPointF(-6.0, center_y - 8.0),
            QPointF(6.0, center_y - 8.0)
        ])
        painter.drawPolygon(poly)
        
        # Tail circle
        painter.drawEllipse(QPointF(0.0, edge_y), 4.0, 4.0)
        
        # Draw variance arc (Teilstrich)
        if self.variance > 0:
            arc_radius = -edge_y
            arc_rect = QRectF(-arc_radius, -arc_radius, arc_radius * 2, arc_radius * 2)
            
            pen = QPen(QColor(80, 80, 80)) # dunkelgrau
            pen.setWidth(5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            start_angle = int((90 - self.variance) * 16)
            span_angle = int((2 * self.variance) * 16)
            
            painter.drawArc(arc_rect, start_angle, span_angle)
        
        painter.restore()
        
        # Draw speed in center
        font.setPixelSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        
        text_rect_speed = QRectF(-inner_radius, -15.0, inner_radius*2.0, 30.0)
        painter.drawText(text_rect_speed, Qt.AlignmentFlag.AlignCenter, str(int(self.speed)))
        
        font.setPixelSize(14)
        font.setBold(False)
        painter.setFont(font)
        text_rect_unit = QRectF(-inner_radius, 15.0, inner_radius*2.0, 20.0)
        painter.drawText(text_rect_unit, Qt.AlignmentFlag.AlignCenter, "m/s")


class WindDriftDialog(QucoreBaseDialog):
    def __init__(self, parent, params, tr_fn, recalculate_callback):
        super(WindDriftDialog, self).__init__(parent, dialog_key="WindDriftDialog")
        self.params = params
        self.tr = tr_fn
        self.recalculate_callback = recalculate_callback
        
        self.setWindowTitle(self.tr("wind_drift_title", "Wind-Drift & Asymmetrische Puffer"))
        self.init_ui()
        self.update_compass()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Enable Checkbox
        self.chk_enable = QCheckBox(self.tr("wind_drift_enable", "Asymmetrische Wind-Drift Puffer Berechnung aktivieren"))
        is_enabled = ConfigManager.get_param(self.params, "enableAsymmetricBufferWinddrift")
        self.chk_enable.setChecked(bool(is_enabled))
        self.chk_enable.toggled.connect(self.on_enable_toggled)
        layout.addWidget(self.chk_enable)
        
        # Info Box
        lbl_info = QLabel(self.tr("wind_drift_info", "<b>Hinweis:</b> Wenn aktiviert, werden die Ground Risk Buffer (GRB) asymmetrisch anhand des Windes verschoben (Luv verkleinert, Lee vergrößert). Das Contingency Volume (CV) bleibt als Reaktionspuffer symmetrisch."))
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #2c3e50; font-size: 11px; margin-bottom: 5px;")
        layout.addWidget(lbl_info)
        
        lbl_warning1 = QLabel(self.tr("wind_drift_warning", "<b>⚠️ Abweichung von LBA/EASA-Formelvorlagen:</b> Diese dynamische vektorielle Verschiebung ist eine detailliertere Auslegung und weicht von den vereinfachten statischen 1:1 Beispielen in den Standarddokumenten ab."))
        lbl_warning1.setWordWrap(True)
        lbl_warning1.setStyleSheet("color: #d35400; font-size: 11px; background-color: #fef9e7; padding: 5px; border: 1px solid #f39c12; border-radius: 4px;")
        layout.addWidget(lbl_warning1)
        
        # Warning if Simplified mode is active
        self.lbl_warning_simplified = QLabel(self.tr("msg_wind_drift_simplified_warning", "⚠️ Hinweis: Die 1:1 Regel (Simplified) ist aktuell als GRB-Methode ausgewählt. Der Wind-Drift hat bei dieser Methode laut Vorgaben keine Auswirkung auf den Puffer. Bitte wechsle hier oder im Parameter-Dialog auf 'Fallschirm', 'Ballistisch' oder 'Gleitflug', um asymmetrische Puffer zu berechnen."))
        self.lbl_warning_simplified.setWordWrap(True)
        self.lbl_warning_simplified.setStyleSheet("color: #d97706; font-weight: bold; margin-top: 10px; margin-bottom: 10px;")
        
        current_method = ConfigManager.get_param(self.params, "groundRiskBufferMethod")
        self.lbl_warning_simplified.setVisible(current_method == "Simplified")
        layout.addWidget(self.lbl_warning_simplified)
        
        self.grp_settings = QGroupBox(self.tr("grp_wind_settings", "Wind Parameter"))
        lay_settings = QVBoxLayout(self.grp_settings)
        
        # Compass
        self.compass = WindCompassWidget()
        lay_settings.addWidget(self.compass, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Controls
        lay_controls = QHBoxLayout()
        
        # Direction
        lay_dir = QVBoxLayout()
        lbl_dir = QLabel(self.tr("wind_drift_direction", "Windrichtung (Herkunft, 0-360°):"))
        self.spn_dir = QDoubleSpinBox()
        limits_dir = ConfigManager.get_limit("windDirection")
        self.spn_dir.setRange(limits_dir["min"], limits_dir["max"])
        self.spn_dir.setDecimals(limits_dir["decimals"])
        self.spn_dir.setSingleStep(limits_dir["step"])
        self.spn_dir.setWrapping(True)
        self.spn_dir.setValue(float(ConfigManager.get_param(self.params, "windDirection")))
        self.spn_dir.valueChanged.connect(self.on_value_changed)
        lay_dir.addWidget(lbl_dir)
        lay_dir.addWidget(self.spn_dir)
        
        lbl_var = QLabel(self.tr("wind_drift_variance", "Varianz (±°):"))
        self.spn_var = QDoubleSpinBox()
        limits_var = ConfigManager.get_limit("windDirectionVariance")
        self.spn_var.setRange(limits_var["min"], limits_var["max"])
        self.spn_var.setDecimals(limits_var["decimals"])
        self.spn_var.setSingleStep(limits_var["step"])
        self.spn_var.setValue(float(ConfigManager.get_param(self.params, "windDirectionVariance")))
        self.spn_var.valueChanged.connect(self.on_value_changed)
        lay_dir.addWidget(lbl_var)
        lay_dir.addWidget(self.spn_var)
        
        lay_controls.addLayout(lay_dir)
        
        # Max Speed
        lay_speed = QVBoxLayout()
        lbl_speed = QLabel(self.tr("wind_drift_speed", "Max Wind (m/s):"))
        self.spn_speed = QDoubleSpinBox()
        limits_spd = ConfigManager.get_limit("maxWindVelocity")
        self.spn_speed.setRange(limits_spd["min"], limits_spd["max"])
        self.spn_speed.setDecimals(limits_spd["decimals"])
        self.spn_speed.setSingleStep(limits_spd["step"])
        self.spn_speed.setValue(float(ConfigManager.get_param(self.params, "maxWindVelocity")))
        self.spn_speed.valueChanged.connect(self.on_value_changed)
        lay_speed.addWidget(lbl_speed)
        lay_speed.addWidget(self.spn_speed)
        
        # Min Speed
        lbl_min_speed = QLabel(self.tr("wind_drift_min_speed", "Min Wind (m/s):"))
        self.spn_min_speed = QDoubleSpinBox()
        limits_min_spd = ConfigManager.get_limit("minWindVelocity")
        self.spn_min_speed.setRange(limits_min_spd["min"], limits_min_spd["max"])
        self.spn_min_speed.setDecimals(limits_min_spd["decimals"])
        self.spn_min_speed.setSingleStep(limits_min_spd["step"])
        self.spn_min_speed.setValue(float(ConfigManager.get_param(self.params, "minWindVelocity")))
        self.spn_min_speed.valueChanged.connect(self.on_value_changed)
        lay_speed.addWidget(lbl_min_speed)
        lay_speed.addWidget(self.spn_min_speed)
        
        lay_controls.addLayout(lay_speed)
        
        lay_settings.addLayout(lay_controls)
        
        # GRB Method selection
        lay_grb = QHBoxLayout()
        lbl_grb = QLabel(self.tr("wind_drift_grb_method", "GRB Methode (Terminierung):"))
        from qgis.PyQt.QtWidgets import QComboBox
        self.cmb_grb = QComboBox()
        self.cmb_grb.addItems(["Simplified", "Parachute", "Ballistic", "Glide"])
        idx = self.cmb_grb.findText(current_method)
        if idx >= 0:
            self.cmb_grb.setCurrentIndex(idx)
        self.cmb_grb.currentTextChanged.connect(self.on_grb_method_changed)
        lay_grb.addWidget(lbl_grb)
        lay_grb.addWidget(self.cmb_grb)
        lay_settings.addLayout(lay_grb)
        layout.addWidget(self.grp_settings)
        
        self.grp_settings.setEnabled(self.chk_enable.isChecked())
        
        layout.addStretch()
        
        btn_close = QPushButton(self.tr("btn_close", "Schließen"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def on_enable_toggled(self, checked):
        self.grp_settings.setEnabled(checked)
        self.params["enableAsymmetricBufferWinddrift"] = checked
        if self.recalculate_callback:
            self.recalculate_callback()
            
    def on_grb_method_changed(self, text):
        self.params["groundRiskBufferMethod"] = text
        self.lbl_warning_simplified.setVisible(text == "Simplified")
        if self.recalculate_callback:
            self.recalculate_callback()
            
    def on_value_changed(self):
        self.params["windDirection"] = self.spn_dir.value()
        self.params["windDirectionVariance"] = self.spn_var.value()
        self.params["maxWindVelocity"] = self.spn_speed.value()
        self.params["minWindVelocity"] = self.spn_min_speed.value()
        
        # Enforce min <= max visually (or just logical in background)
        if self.spn_min_speed.value() > self.spn_speed.value():
            self.spn_min_speed.blockSignals(True)
            self.spn_min_speed.setValue(self.spn_speed.value())
            self.spn_min_speed.blockSignals(False)
            self.params["minWindVelocity"] = self.spn_min_speed.value()
            
        self.update_compass()
        if self.recalculate_callback:
            self.recalculate_callback()

    def update_compass(self):
        self.compass.set_values(
            self.spn_dir.value(), 
            self.spn_var.value(),
            self.spn_min_speed.value(), 
            self.spn_speed.value()
        )

    def set_wind_speed(self, speed):
        """Called externally if maxWindVelocity changes in the main param dialog"""
        self.spn_speed.blockSignals(True)
        self.spn_speed.setValue(speed)
        self.spn_speed.blockSignals(False)
        self.update_compass()

    def set_grb_method(self, method):
        """Called externally if groundRiskBufferMethod changes in the main param dialog"""
        self.cmb_grb.blockSignals(True)
        idx = self.cmb_grb.findText(method)
        if idx >= 0:
            self.cmb_grb.setCurrentIndex(idx)
        self.cmb_grb.blockSignals(False)
        self.lbl_warning_simplified.setVisible(method == "Simplified")
