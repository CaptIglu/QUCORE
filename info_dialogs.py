# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDialogButtonBox, 
                             QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QGroupBox, QLineEdit, QMessageBox)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt, QSettings, QDateTime
from .dialog_utils import QucoreBaseDialog

class AboutDialog(QucoreBaseDialog):
    def __init__(self, parent, metadata, plugin):
        super(AboutDialog, self).__init__(parent, dialog_key="AboutDialog")
        self.metadata = metadata
        self.plugin = plugin
        self.plugin_dir = plugin.plugin_dir
        self.tr = plugin.tr
        
        self.setWindowTitle(self.tr("dialog_about_title", "Über QUCORE"))
        self.setModal(True)
        self.init_ui()
        
    def init_ui(self):
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
            lbl_icon.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(lbl_icon)
        
        # Title and Version Info
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        
        name = self.metadata.get('name', 'QUCORE (Variable UAS Corridor Planning)')
        version = self.metadata.get('version', '1.0.2')
        
        lbl_name = QLabel(f'<span style="font-size: 16px; font-weight: bold; color: #2c3e50;">{name}</span>')
        lbl_version = QLabel(f'<span style="font-size: 12px; color: #7f8c8d; font-weight: 500;">Version {version}</span>')
        
        title_layout.addWidget(lbl_name)
        title_layout.addWidget(lbl_version)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Subtitle / Short description
        subtitle_text = self.tr("about_subtitle", "QUCORE – QGIS UAS Corridor Outlining & Routing Engine (GPLv2+ Open Source)")
        lbl_subtitle = QLabel(f'<div style="font-size: 12px; color: #34495e; font-weight: 500; margin-top: 2px; margin-bottom: 4px;">{subtitle_text}</div>')
        lbl_subtitle.setWordWrap(True)
        lbl_subtitle.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl_subtitle)

        
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
        lbl_table.setTextFormat(Qt.TextFormat.RichText)
        lbl_table.setOpenExternalLinks(True)
        layout.addWidget(lbl_table)
        
        # License Group Box (Dynamic Status & Activation Button)
        self.grp_license = QGroupBox(self.tr("license_status_title", "Lizenzierung & Commercial Supporter"))
        lay_lic = QHBoxLayout(self.grp_license)
        lay_lic.setContentsMargins(10, 10, 10, 10)
        lay_lic.setSpacing(10)
        
        self.lbl_license_status = QLabel()
        self.lbl_license_status.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_license_status.setWordWrap(True)
        lay_lic.addWidget(self.lbl_license_status, 1)
        
        self.btn_license = QPushButton()
        self.btn_license.setFixedWidth(180)
        self.btn_license.clicked.connect(self.on_license_button_clicked)
        lay_lic.addWidget(self.btn_license, 0, Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(self.grp_license)
        
        # Initialize/update the license UI details
        self.update_license_ui()
        
        # Aviation Safety & Disclaimer Box
        tr_disclaimer_title = self.tr('aviation_disclaimer_title', 'Flugsicherheit & Haftungsausschluss')
        tr_disclaimer_text = self.tr('aviation_disclaimer_text', 'Achtung: QUCORE dient als Unterstützungswerkzeug für die Flugplanung. Die SORA-Berechnungen entbinden den Fernpiloten nicht von der eigenverantwortlichen Prüfung und Einhaltung aller gesetzlichen Vorgaben (EASA/LBA). Nutzung auf eigene Gefahr. Keine Gewährleistung für die Richtigkeit der berechneten Geodaten.')
        
        disclaimer_html = f"""
        <div style="padding: 10px 12px; background-color: #fdf2f2; border-left: 4px solid #e74c3c; border-radius: 4px; color: #555555; font-size: 11px; line-height: 1.4;">
            <strong style="color: #c0392b;">{tr_disclaimer_title}:</strong> {tr_disclaimer_text}
        </div>
        """
        lbl_disclaimer = QLabel(disclaimer_html)
        lbl_disclaimer.setWordWrap(True)
        lbl_disclaimer.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl_disclaimer)

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
        lbl_note.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl_note)
        
        # Button Box
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

    def update_license_ui(self):
        from .plugin import verify_license_key
        settings = QSettings()
        
        # Check license activation
        is_commercial_unlocked = self.plugin.params.get("commercial_unlocked", False)
        saved_key = str(settings.value("QUCORE/license_key", ""))
        if verify_license_key(saved_key):
            is_commercial_unlocked = True
            
        # Get trial details
        install_date_str = settings.value("QUCORE/install_date", "")
        if not install_date_str:
            install_date_str = QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
            settings.setValue("QUCORE/install_date", install_date_str)
            
        install_date = QDateTime.fromString(install_date_str, Qt.DateFormat.ISODate)
        days_since_install = install_date.daysTo(QDateTime.currentDateTime())
        remaining_days = 30 - days_since_install
        
        if is_commercial_unlocked:
            bg_color = "#e8f8f5"
            border_color = "#2ecc71"
            title_text = self.tr("license_activated", "Aktiviert (Registrierter Commercial Supporter)")
            
            # Extract email if possible
            display_email = "In Konfigurationsdatei freigeschaltet"
            if '|' in saved_key:
                display_email = saved_key.split('|', 1)[0]
            elif ':' in saved_key: # legacy fallback display
                display_email = saved_key.split(':', 1)[0]
                
            sub_text = f"Registrierte E-Mail: {display_email}"
            btn_text = self.tr("btn_change_license_key", "Lizenzschlüssel ändern...")
            status_style = "color: #27ae60; font-weight: bold; font-size: 11px;"
        elif remaining_days < 0:
            bg_color = "#fef9e7"
            border_color = "#f39c12"
            title_text = self.tr("license_expired", "Empfehlung: Commercial Supporter License")
            sub_text = self.tr("license_expired_desc", "QUCORE ist Open Source (GPLv2+). Für die gewerbliche Nutzung gibt es die Möglichkeit einer Commercial Supporter License (Major-Version-Lizenz). Kontakt: tim.strohbach  [at] gmx.de")
            btn_text = self.tr("btn_enter_license_key", "Lizenzschlüssel eingeben...")
            status_style = "color: #d35400; font-weight: bold; font-size: 11px;"
        else:
            bg_color = "#e8f8f5"
            border_color = "#3498db"
            title_text = self.tr("license_not_activated", "Freie Open-Source Software (GPLv2+)")
            days_str = self.tr("license_days", "{days} Tage").format(days=max(0, remaining_days))
            sub_text = f"Kostenfrei für private & akademische Nutzung. Testphase für kommerzielle Nutzung (noch <b>{days_str}</b>)."
            btn_text = self.tr("btn_enter_license_key", "Lizenzschlüssel eingeben...")
            status_style = "color: #2980b9; font-weight: bold; font-size: 11px;"
            
        license_html = f"""
        <div style="padding: 8px; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 4px;">
            <div style="{status_style}">🔑 {title_text}</div>
            <div style="font-size: 10.5px; margin-top: 3px; color: #555555; line-height: 1.3;">{sub_text}</div>
        </div>
        """
        self.lbl_license_status.setText(license_html)
        self.btn_license.setText(btn_text)

    def on_license_button_clicked(self):
        from .plugin import verify_license_key
        
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("license_prompt_title", "Commercial Supporter Schlüssel eingeben"))
        layout = QVBoxLayout(dlg)
        
        lbl_email = QLabel(self.tr("license_prompt_email", "E-Mail (Registrierter Nutzer):"))
        le_email = QLineEdit()
        layout.addWidget(lbl_email)
        layout.addWidget(le_email)
        
        lbl_key = QLabel(self.tr("license_prompt_key", "Lizenzschlüssel (z.B. ABCD-1234-...):"))
        le_key = QLineEdit()
        layout.addWidget(lbl_key)
        layout.addWidget(le_key)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            email = le_email.text().strip()
            key = le_key.text().strip()
            
            if not email or not key:
                QMessageBox.warning(self, "Fehler", self.tr("license_empty_error", "Bitte E-Mail und Schlüssel eingeben."))
                return
                
            saved_val = f"{email}|{key}"
            
            if verify_license_key(saved_val):
                # Save key in settings
                settings = QSettings()
                settings.setValue("QUCORE/license_key", saved_val)
                
                # Update plugin params
                self.plugin.params["commercial_unlocked"] = True
                
                # Show success message
                QMessageBox.information(
                    self,
                    self.tr("license_success_title", "Aktivierung erfolgreich"),
                    self.tr("license_success_text", "Commercial Supporter License erfolgreich aktiviert! Vielen Dank für die Unterstützung von QUCORE.")
                )
                
                # Refresh our dialog UI
                self.update_license_ui()
                
                # Refresh the main plugin panel if it exists!
                if hasattr(self.plugin, 'update_trial_warning'):
                    self.plugin.update_trial_warning()
            else:
                # Show error message
                QMessageBox.warning(
                    self,
                    self.tr("license_invalid_title", "Ungültiger Lizenzschlüssel"),
                    self.tr("license_invalid_text", "Ungültiger Lizenzschlüssel oder falsche E-Mail-Adresse. Wenden Sie sich bei Fragen an tim.strohbach  [at] gmx.de.")
                )



class FormatsInfoDialog(QucoreBaseDialog):
    def __init__(self, parent, plugin):
        super(FormatsInfoDialog, self).__init__(parent, dialog_key="FormatsInfoDialog")
        self.plugin = plugin
        self.tr = plugin.tr
        
        self.setObjectName("FormatsInfoDialog")
        self.setWindowTitle(self.tr("dialog_formats_title", "QUCORE – Dateiformate im Vergleich"))
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(self.tr("formats_header", "<b>Dateiformate und deren Unterstützung bei Import / Export</b>"))
        header.setObjectName("FormatsHeaderLabel")
        layout.addWidget(header)
        
        # Table setup
        table = QTableWidget(6, 7)
        table.setObjectName("FormatsTableWidget")
        table.setHorizontalHeaderLabels([
            self.tr("matrix_col_format", "Format"),
            self.tr("matrix_col_geom", "Geometrie"),
            self.tr("matrix_col_height", "Wegpunkt-Höhen"),
            self.tr("matrix_col_speed", "Wegpunkt-Geschw."),
            self.tr("matrix_col_pilot", "Pilotenposition"),
            self.tr("matrix_col_params", "Berechnungsparameter"),
            self.tr("matrix_col_roundtrip", "Round-Trip fähig?")
        ])
        
        # Style table
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setAlternatingRowColors(True)
        
        # Data Rows
        rows_data = [
            ("GeoPackage (.gpkg)", self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes_full", "Ja (Vollständig)")),
            ("GeoJSON (.geojson)", self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes_full", "Ja (Vollständig)")),
            ("KML (.kml)", self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes_full", "Ja (Vollständig)")),
            ("dipul (.dipul)", self.tr("yes", "Ja"), self.tr("global_only", "Nur global"), self.tr("global_only", "Nur global"), self.tr("yes", "Ja"), self.tr("global_only", "Nur global"), self.tr("limited_qucore", "Eingeschränkt (Vollständig bei QUCORE-Dateien)")),
            ("SkyDemon (.flightplan)", self.tr("yes", "Ja"), self.tr("global_only", "Nur global"), self.tr("no", "Nein"), self.tr("no", "Nein"), self.tr("no", "Nein"), self.tr("route_only", "Nur Route / Wegpunkte")),
            ("QGC / Ardupilot (.plan / .waypoints)", self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("yes", "Ja"), self.tr("no", "Nein"), self.tr("no", "Nein"), self.tr("route_only", "Nur Route / Wegpunkte"))
        ]
        
        for r_idx, row in enumerate(rows_data):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(val)
                if c_idx > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r_idx, c_idx, item)
                
        layout.addWidget(table)
        
        # Note
        note = QLabel(self.tr("formats_note", "<i>* Hinweis: GeoPackage, GeoJSON und aus QUCORE exportierte KML-Dateien speichern den 100% exakten Zustand Ihrer Planung (einschließlich aller SORA-Parameter) für die spätere Weiterbearbeitung.</i>"))
        note.setObjectName("FormatsNoteLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        # OK Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton(self.tr("btn_close_dialog", "Schließen"))
        btn_ok.setObjectName("FormatsCloseButton")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
