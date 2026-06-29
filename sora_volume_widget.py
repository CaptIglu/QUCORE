# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QTextDocument
from PyQt5.QtCore import Qt, QRectF

class SoraVolumeWidget(QWidget):
    def __init__(self, parent=None, tr_fn=None):
        super(SoraVolumeWidget, self).__init__(parent)
        self.tr_fn = tr_fn
        
        # State values
        self.avg_r_fg = 0.0
        self.avg_s_cv = 0.0
        self.avg_s_grb = 0.0
        self.avg_h_fg = 0.0
        self.avg_h_cv = 0.0
        
        # Formatted string values (e.g., "50,0 m" or "50,0–100,0 m")
        self.r_fg_str = ""
        self.s_cv_str = ""
        self.s_grb_str = ""
        self.h_fg_str = ""
        self.h_cv_str = ""
        self.s_aga_str = ""
        
        self.has_data = False
        
        # Layout metrics - height further compressed from 250 to 210 to fully eliminate empty space
        self.setMinimumHeight(210)
        
    def tr(self, key, default=""):
        if self.tr_fn:
            return self.tr_fn(key, default)
        return default

    def update_values(self, r_fg_list, s_cv_list, s_grb_list, h_fg_list, h_cv_list, geometry_type="Corridor", s_aga_list=None):
        """
        Updates the values to be drawn. 
        Takes raw lists representing the parameters per waypoint.
        """
        self.geometry_type = geometry_type
        if not r_fg_list or len(r_fg_list) == 0:
            self.avg_r_fg = 0.0
            self.avg_s_cv = 0.0
            self.avg_s_grb = 0.0
            self.avg_h_fg = 0.0
            self.avg_h_cv = 0.0
            self.s_aga_str = ""
            
            self.r_fg_str = ""
            self.s_cv_str = ""
            self.s_grb_str = ""
            self.h_fg_str = ""
            self.h_cv_str = ""
            self.s_aga_str = ""
            
            self.has_data = False
            self.update()
            return
            
        # Calculate averages for drawing proportions
        self.avg_r_fg = sum(r_fg_list) / len(r_fg_list)
        self.avg_s_cv = sum(s_cv_list) / len(s_cv_list)
        self.avg_s_grb = sum(s_grb_list) / len(s_grb_list)
        self.avg_h_fg = sum(h_fg_list) / len(h_fg_list)
        self.avg_h_cv = sum(h_cv_list) / len(h_cv_list)
        
        # Get active decimal separator
        sep = self.tr("decimal_separator", ",")
        
        # Formatter helper
        def fmt_range(values, unit="m"):
            mn, mx = min(values), max(values)
            if abs(mn - mx) < 0.05:
                val_str = f"{mn:.1f}"
            else:
                val_str = f"{mn:.1f}–{mx:.1f}"
                
            # Replace dot with local separator (e.g., "," in German)
            val_str = val_str.replace(".", sep)
            return f"{val_str} {unit}"
            
        self.r_fg_str = fmt_range([2.0 * x for x in r_fg_list])
        self.s_cv_str = fmt_range(s_cv_list)
        self.s_grb_str = fmt_range(s_grb_list)
        self.h_fg_str = fmt_range(h_fg_list)
        self.h_cv_str = fmt_range(h_cv_list)
        self.s_aga_str = f"{int(round(s_aga_list[0]))} m" if s_aga_list and len(s_aga_list) > 0 else ""
        
        self.cv_warning = any(x < 9.99 for x in s_cv_list) if s_cv_list else False
        if self.cv_warning:
            tooltip_txt = self.tr("cv_warning_tooltip", 
                "Empfohlener Mindestwert nach EASA SORA (AMC1 zu Artikel 11) beträgt 10,0 m.\n"
                "Ein geringerer Puffer ist im ConOps betrieblich zu begründen (z. B. durch hohe Navigationsgenauigkeit)."
            )
            self.setToolTip(tooltip_txt)
        else:
            self.setToolTip("")

        self.has_data = True
        self.update()

    def draw_horizontal_arrow(self, painter, x1, x2, y, arrow_size=4):
        painter.drawLine(int(x1), int(y), int(x2), int(y))
        # Left arrowhead
        painter.drawLine(int(x1), int(y), int(x1 + arrow_size), int(y - arrow_size))
        painter.drawLine(int(x1), int(y), int(x1 + arrow_size), int(y + arrow_size))
        # Right arrowhead
        painter.drawLine(int(x2), int(y), int(x2 - arrow_size), int(y - arrow_size))
        painter.drawLine(int(x2), int(y), int(x2 - arrow_size), int(y + arrow_size))

    def draw_vertical_arrow(self, painter, x, y1, y2, arrow_size=4):
        painter.drawLine(int(x), int(y1), int(x), int(y2))
        # Top arrowhead
        painter.drawLine(int(x), int(y1), int(x - arrow_size), int(y1 + arrow_size))
        painter.drawLine(int(x), int(y1), int(x + arrow_size), int(y1 + arrow_size))
        # Bottom arrowhead
        painter.drawLine(int(x), int(y2), int(x - arrow_size), int(y2 - arrow_size))
        painter.drawLine(int(x), int(y2), int(x + arrow_size), int(y2 - arrow_size))

    def draw_html_text(self, painter, rect, html):
        doc = QTextDocument()
        doc.setDefaultFont(painter.font())
        doc.setHtml(html)
        painter.save()
        painter.translate(rect.topLeft())
        doc.drawContents(painter, QRectF(0, 0, rect.width(), rect.height()))
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Dynamic theme styling based on current QGIS/OS theme
        bg_color = self.palette().color(self.backgroundRole())
        is_dark = bg_color.lightness() < 128
        
        # Always use high-contrast dark text inside the pastel boxes
        text_color = QColor(44, 44, 44)
        
        # Header text above vertical section uses theme-dependent colors
        header_text_color = QColor(220, 220, 220) if is_dark else QColor(50, 50, 50)
        
        W = float(self.width())
        H = float(self.height())
        
        # Fallback if no waypoints
        if not self.has_data:
            painter.setPen(QPen(header_text_color))
            painter.setFont(QFont("Arial", 9, QFont.StyleItalic))
            waiting_txt = self.tr("viz_waiting", "Warten auf Puffer-Berechnung...")
            painter.drawText(self.rect(), Qt.AlignCenter, waiting_txt)
            painter.end()
            return
            
        # Hard limits optimized for H = 210
        H_half = 125.0
        
        # Colors strictly mirroring the DIPUL volume planner:
        # Sage green for Flight Geography, warm soft yellow for Contingency Volume, raspberry/pink for Ground Risk Buffer
        color_fg = QColor(146, 180, 140)  # #92B48C (Flight Geography)
        color_cv = QColor(247, 219, 138)  # #F7DB8A (Contingency Volume)
        color_grb = QColor(209, 94, 124)  # #D15E7C (Ground Risk Buffer)
        color_aa = QColor("#2980b9")      # Adjacent Area
        
        # Outlines and arrow pens matching reference
        box_pen = QPen(QColor(80, 80, 80), 1)
        arrow_pen = QPen(QColor(44, 44, 44), 1)
        
        # =====================================================================
        # TOP BLOCK: HORIZONTAL BUFFER LAYERS (DIPUL SCHEMATIC - COMPACT)
        # =====================================================================
        pad_aa_x = 10.0
        pad_aa_y_top = 11.0
        
        # 0. Adjacent Area (AA) ( blue dashed ) - Outermost bounding box
        aa_rect = QRectF(10, 5, W - 20, 102.0)
        aa_pen = QPen(color_aa, 2, Qt.DashLine)
        painter.setPen(aa_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(aa_rect)
        
        # Label for AA (moved down to arrow)
        
        # 1. Ground Risk Buffer ( raspberry pink ) - Outer bounding box (height 80.0)
        grb_rect = QRectF(10 + pad_aa_x, 5 + pad_aa_y_top, W - 20 - 2 * pad_aa_x, 80.0)
        painter.setPen(box_pen)
        painter.setBrush(QBrush(color_grb))
        painter.drawRect(grb_rect)
        
        # Label for GRB
        html_grb = f"<div style='color: rgb({text_color.red()},{text_color.green()},{text_color.blue()}); font-family: Arial; font-size: 11px; font-weight: bold;'>S<sub>GRB</sub> = {self.s_grb_str}</div>"
        self.draw_html_text(painter, QRectF(18 + pad_aa_x, 8 + pad_aa_y_top, W - 36, 16), html_grb)
        
        # 2. Contingency Volume ( soft warm yellow ) - Sits nested inside GRB (height 51.0)
        pad_x = 22.0
        pad_y_top = 23.0
        pad_y_bottom = 6.0
        
        cv_rect = QRectF(10 + pad_aa_x + pad_x, 5 + pad_aa_y_top + pad_y_top, W - 20 - 2 * pad_aa_x - 2 * pad_x, 51.0)
        painter.setPen(box_pen)
        painter.setBrush(QBrush(color_cv))
        painter.drawRect(cv_rect)
        
        # Label for CV
        is_cv_warning = getattr(self, "cv_warning", False)
        cv_col = "#d97706" if is_cv_warning else f"rgb({text_color.red()},{text_color.green()},{text_color.blue()})"
        cv_warn_txt = "⚠️ " if is_cv_warning else ""
        html_cv = f"<div style='color: {cv_col}; font-family: Arial; font-size: 11px; font-weight: bold;'>{cv_warn_txt}S<sub>CV</sub> = {self.s_cv_str}</div>"
        self.draw_html_text(painter, QRectF(10 + pad_aa_x + pad_x + 24, 5 + pad_aa_y_top + pad_y_top + 1, W - 20 - 2 * pad_aa_x - 2 * pad_x - 32, 16), html_cv)
                         
        # 3. Flight Geography ( sage green ) - Sits nested inside CV (height 28.0)
        pad_x2 = 20.0
        pad_y2_top = 20.0
        pad_y2_bottom = 5.0
        
        fg_rect = QRectF(10 + pad_aa_x + pad_x + pad_x2, 5 + pad_aa_y_top + pad_y_top + pad_y2_top, W - 20 - 2 * (pad_aa_x + pad_x + pad_x2), 28.0)
        painter.setPen(box_pen)
        painter.setBrush(QBrush(color_fg))
        painter.drawRect(fg_rect)
        
        geom_type = getattr(self, "geometry_type", "Corridor")
        if geom_type != "Polygon":
            html_fg = f"<div style='color: rgb({text_color.red()},{text_color.green()},{text_color.blue()}); font-family: Arial; font-size: 11px; font-weight: bold;'>S<sub>FG</sub> = {self.r_fg_str}</div>"
            self.draw_html_text(painter, QRectF(10 + pad_aa_x + pad_x + pad_x2 + 8, 5 + pad_aa_y_top + pad_y_top + pad_y2_top + 2, W - 20 - 2 * (pad_aa_x + pad_x + pad_x2) - 16, 16), html_fg)
                         
        # Draw horizontal dimension arrows for top section
        painter.setPen(arrow_pen)
        # S_AGA arrow (Right side: from CV right edge to AA right edge)
        x_cv_right = W - 10 - pad_aa_x - pad_x
        x_aa_right = W - 10
        y_aga_arrow = 5 + pad_aa_y_top + pad_y_top  # Aligned with top right corner of CV box
        self.draw_horizontal_arrow(painter, x_cv_right, x_aa_right, y_aga_arrow)
        
        # Label for AA (positioned near the arrow on the right side)
        html_aa = f"<div style='color: rgb({text_color.red()},{text_color.green()},{text_color.blue()}); font-family: Arial; font-size: 11px; font-weight: bold; text-align: center;'>S<sub>AGA</sub> = {self.s_aga_str}</div>"
        arrow_center_x = (x_cv_right + x_aa_right) / 2.0
        y_label_aa = 8 + pad_aa_y_top  # same height as S_GRB label
        self.draw_html_text(painter, QRectF(arrow_center_x - 50, y_label_aa, 100, 16), html_aa)
        
        # S_GRB arrow (Left padding: from GRB left edge to CV left edge)
        self.draw_horizontal_arrow(painter, 10 + pad_aa_x, 10 + pad_aa_x + pad_x, 5 + pad_aa_y_top + 25.5)
        # S_CV arrow (Middle padding: from CV left edge to FG left edge)
        self.draw_horizontal_arrow(painter, 10 + pad_aa_x + pad_x, 10 + pad_aa_x + pad_x + pad_x2, 5 + pad_aa_y_top + pad_y_top + 14.0)
        # S_FG arrow (spanning full width of FG box near bottom)
        if geom_type != "Polygon":
            self.draw_horizontal_arrow(painter, 10 + pad_aa_x + pad_x + pad_x2, W - 10 - pad_aa_x - pad_x - pad_x2, 5 + pad_aa_y_top + pad_y_top + pad_y2_top + 20.0)
        
        # =====================================================================
        # DIVIDER TEXT: VERTIKAL (NICHT MASSSTÄBLICH)
        # =====================================================================
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.setPen(QPen(header_text_color))
        vert_title = self.tr("viz_vertical_title", "Vertikal (nicht maßstäblich)")
        painter.drawText(QRectF(10, H_half - 12, W - 20, 16), Qt.AlignCenter, vert_title)
        
        # =====================================================================
        # BOTTOM BLOCK: VERTICAL BUFFER LAYERS (DIPUL SCHEMATIC - SPACE OPTIMIZED)
        # =====================================================================
        # Proportional vertical height scaling
        h_max_val = max(self.avg_h_cv, 1.0)
        fg_ratio = self.avg_h_fg / h_max_val
        
        # We set the Flight Geography box visual height to be dynamic between 25px and 40px
        fg_h_px = fg_ratio * 40.0
        if fg_h_px < 25.0:
            fg_h_px = 25.0
        if fg_h_px > 40.0:
            fg_h_px = 40.0
            
        # CV height box is scaled to be exactly the FG height plus 20px (enough to fit CV text perfectly)
        cv_h_box = fg_h_px + 20.0
        
        # Sits from cv_y_start downwards, fitting compactly inside the bottom half
        cv_y_start = 131.0
        cv_rect_v = QRectF(10, cv_y_start, W - 20, cv_h_box)
        
        painter.setPen(box_pen)
        painter.setBrush(QBrush(color_cv))
        painter.drawRect(cv_rect_v)
        
        # Label for CV (Vertical)
        html_hcv = f"<div style='color: rgb({text_color.red()},{text_color.green()},{text_color.blue()}); font-family: Arial; font-size: 11px; font-weight: bold;'>H<sub>CV</sub> = {self.h_cv_str}</div>"
        self.draw_html_text(painter, QRectF(18, cv_y_start + 3, W - 36, 16), html_hcv)
        
        # 2. Flight Geography ( sage green ) - Sits nested and bottom-aligned inside CV
        # Starts exactly 20px below the top of CV
        fg_rect_v = QRectF(10 + pad_x, cv_y_start + 20.0, W - 20 - 2 * pad_x, fg_h_px)
        painter.setPen(box_pen)
        painter.setBrush(QBrush(color_fg))
        painter.drawRect(fg_rect_v)
        
        # Label for FG (Vertical)
        html_hfg = f"<div style='color: rgb({text_color.red()},{text_color.green()},{text_color.blue()}); font-family: Arial; font-size: 11px; font-weight: bold;'>H<sub>FG</sub> = {self.h_fg_str}</div>"
        self.draw_html_text(painter, QRectF(10 + pad_x + 8, cv_y_start + 20.0 + 4, W - 20 - 2 * pad_x - 16, 16), html_hfg)
                         
        # Draw vertical dimension arrows for bottom section
        painter.setPen(arrow_pen)
        # H_FG vertical arrow (inside green box on the right side)
        self.draw_vertical_arrow(painter, W - 10 - pad_x - 15.0, cv_y_start + 20.0, cv_y_start + 20.0 + fg_h_px)
        # H_CV vertical arrow (outside green box on the far right padding of yellow box)
        self.draw_vertical_arrow(painter, W - 21.0, cv_y_start, cv_y_start + cv_h_box)
        
        painter.end()
