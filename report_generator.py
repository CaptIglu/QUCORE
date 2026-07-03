# -*- coding: utf-8 -*-
import os
import zipfile
import shutil
import tempfile
import uuid
import re
from datetime import datetime
from qgis.core import QgsPointXY, QgsMessageLog, Qgis

from .config_manager import ConfigManager
from .translation_manager import TranslationManager
from .buffer_calculator import BufferCalculator

def tr(key, default=""):
    try:
        lang = ConfigManager.get_default("language")
    except KeyError:
        lang = "de"
    return TranslationManager.tr(key, lang, default)


class ReportGenerator:
    @staticmethod
    def make_docx_table(headers, rows):
        """
        Generates an OpenXML Word table string.
        """
        xml = []
        xml.append('<w:tbl>')
        xml.append('  <w:tblPr>')
        xml.append('    <w:tblStyle w:val="TableGrid"/>')
        xml.append('    <w:tblW w:w="0" w:type="auto"/>')
        xml.append('    <w:tblBorders>')
        xml.append('      <w:top w:val="single" w:sz="6" w:space="0" w:color="CCCCCC"/>')
        xml.append('      <w:left w:val="none"/>')
        xml.append('      <w:bottom w:val="single" w:sz="6" w:space="0" w:color="CCCCCC"/>')
        xml.append('      <w:right w:val="none"/>')
        xml.append('      <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E0E0E0"/>')
        xml.append('      <w:insideV w:val="none"/>')
        xml.append('    </w:tblBorders>')
        xml.append('    <w:tblCellMar>')
        xml.append('      <w:top w:w="120" w:type="dxa"/>')
        xml.append('      <w:bottom w:w="120" w:type="dxa"/>')
        xml.append('      <w:left w:w="150" w:type="dxa"/>')
        xml.append('      <w:right w:w="150" w:type="dxa"/>')
        xml.append('    </w:tblCellMar>')
        xml.append('  </w:tblPr>')
        
        # Headers row
        xml.append('  <w:tr>')
        for h in headers:
            xml.append('    <w:tc>')
            xml.append('      <w:tcPr>')
            xml.append('        <w:shd w:fill="F2F2F2"/>')
            xml.append('      </w:tcPr>')
            xml.append('      <w:p>')
            xml.append('        <w:pPr>')
            xml.append('          <w:rPr><w:b/></w:rPr>')
            xml.append('        </w:pPr>')
            xml.append(f'        <w:r><w:rPr><w:b/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">{h}</w:t></w:r>')
            xml.append('      </w:p>')
            xml.append('    </w:tc>')
        xml.append('  </w:tr>')
        
        # Data rows
        for r in rows:
            xml.append('  <w:tr>')
            for cell in r:
                xml.append('    <w:tc>')
                xml.append('      <w:p>')
                xml.append('        <w:pPr>')
                xml.append('          <w:rPr><w:sz w:val="18"/></w:rPr>')
                xml.append('        </w:pPr>')
                xml.append(f'        <w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">{cell}</w:t></w:r>')
                xml.append('      </w:p>')
                xml.append('    </w:tc>')
            xml.append('  </w:tr>')
            
        xml.append('</w:tbl>')
        return "\n".join(xml)

    @staticmethod
    def get_document_xml_template(lang="de"):
        """Reads the report XML structure from the template file."""
        import os
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        template_xml_name = f"report_template_{lang}.xml"
        template_xml_path = os.path.join(plugin_dir, template_xml_name)
        
        if os.path.exists(template_xml_path):
            with open(template_xml_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise FileNotFoundError(f"Die Berichtsvorlage '{template_xml_name}' fehlt im Plugin-Ordner.")

    @staticmethod
    def export_sora_docx(file_path, waypoints, pilot_pos, params, map_image_path, geometry_type="Corridor", start_image_path=None, end_image_path=None, sora_viz_image_path=None):
        """
        Exports SORA-relevant documentation as a native Word .docx file.
        Uses report_template.docx as a base and modifies its zip contents.
        """
        import os
        import zipfile
        import shutil
        import tempfile
        import uuid
        from datetime import datetime
        
        lang = ConfigManager.get_param(params, "language")
        if lang not in ["de", "en"]:
            lang = "de"
        is_en = (lang == "en")
        
        def get_png_size(filepath):
            try:
                with open(filepath, 'rb') as f:
                    data = f.read(24)
                    if len(data) >= 24 and data[:8] == b'\x89PNG\r\n\x1a\n':
                        import struct
                        w, h = struct.unpack('>II', data[16:24])
                        return w, h
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Failed to parse PNG dimensions for {filepath}: {e}", "QUCORE", Qgis.Info)
            return None
            
        # 1. Path to template file in the plugin directory
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        template_name = f"report_template_{lang}.docx"
        template_path = os.path.join(plugin_dir, template_name)
        
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template DOCX file not found in plugin directory: {template_path}")
                    
        # Check for template's native headers and footers relationships to preserve them,
        # and also dynamically parse existing relationship IDs to prevent collisions
        header_rids = []
        footer_rids = []
        existing_rids = []
        overview_rid = "rId6" # Default fallback for the overview map
        overview_target = "media/image2.png" # Default fallback
        
        try:
            with zipfile.ZipFile(template_path, 'r') as z:
                if "word/_rels/document.xml.rels" in z.namelist():
                    rels_xml = z.read("word/_rels/document.xml.rels").decode('utf-8')
                    import re
                    # Robust attribute-order-agnostic parsing of Relationship tags
                    for rel in re.findall(r'<Relationship\s+[^>]+>', rels_xml):
                        rid_m = re.search(r'Id="([^"]+)"', rel)
                        type_m = re.search(r'Type="([^"]+)"', rel)
                        target_m = re.search(r'Target="([^"]+)"', rel)
                        if rid_m and type_m and target_m:
                            rid = rid_m.group(1)
                            rtype = type_m.group(1)
                            target = target_m.group(1)
                            
                            if "header" in target.lower():
                                header_rids.append(rid)
                            elif "footer" in target.lower():
                                footer_rids.append(rid)
                            elif "relationships/image" in rtype:
                                overview_rid = rid
                                overview_target = target
                                
                            if rid.startswith("rId"):
                                try:
                                    existing_rids.append(int(rid[3:]))
                                except ValueError as e:
                                    from qgis.core import QgsMessageLog, Qgis
                                    import traceback
                                    QgsMessageLog.logMessage(f"Silent exception caught in importer_exporter.py (line 973): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
        except Exception as e:
            QgsMessageLog.logMessage(f"Failed to parse docx rels: {e}", "QUCORE", Qgis.Warning)
            
        overview_zip_path = f"word/{overview_target}"
            
        # Dynamically assign new, non-colliding relationship IDs for our embedded assets
        max_rid_val = max(existing_rids) if existing_rids else 100
        start_rid = f"rId{max_rid_val + 1}"
        end_rid = f"rId{max_rid_val + 2}"
        sora_rid = f"rId{max_rid_val + 3}"
        
        header_footer_xml = []
        for rid in header_rids:
            header_footer_xml.append(f'<w:headerReference w:type="default" r:id="{rid}"/>')
        for rid in footer_rids:
            header_footer_xml.append(f'<w:footerReference w:type="default" r:id="{rid}"/>')
        header_footer_xml_str = "".join(header_footer_xml)
            
        # 2. Extract and format variables
        name = os.path.splitext(os.path.basename(file_path))[0]
        date_str = datetime.now().strftime("%Y-%m-%d") if is_en else datetime.now().strftime("%d.%m.%Y")
        
        # Calculate coordinate center
        center_lat = 0.0
        center_lon = 0.0
        if waypoints:
            center_lat = sum(wp[1] for wp in waypoints) / len(waypoints)
            center_lon = sum(wp[0] for wp in waypoints) / len(waypoints)
        center_str = f"N{center_lat:.6f} E{center_lon:.6f}"
        
        # Pilot Position
        if pilot_pos:
            try:
                pilot_str = f"N{pilot_pos.y():.6f} E{pilot_pos.x():.6f}"
            except Exception as e:
                QgsMessageLog.logMessage(f"Failed to format pilot_pos using coordinates: {e}", "QUCORE", Qgis.Info)
                pilot_str = str(pilot_pos)
        else:
            pilot_str = "No pilot position defined" if is_en else "Keine Pilotenposition definiert"
            

        # UAS Properties
        uas_type = ConfigManager.get_param(params, "uas_type")
        is_copter = uas_type == "Multikopter" or "kopter" in str(uas_type).lower()
        if is_en:
            uas_type_str = "Multicopter" if is_copter else "Fixed Wing"
            altimetry = ConfigManager.get_param(params, "altimetry")
            altimetry_str = "GPS-based" if altimetry == "GPS" else "Barometric"
        else:
            uas_type_str = "Multikopter" if is_copter else "Flächenflieger (Fixed Wing)"
            altimetry = ConfigManager.get_param(params, "altimetry")
            altimetry_str = "GPS-basiert" if altimetry == "GPS" else "Barometrisch"
        
        v0 = ConfigManager.get_param(params, "maxOpsSpeedV0")
        vmax = ConfigManager.get_param(params, "maxCommandableSpeedVmax")
        v_wind = ConfigManager.get_param(params, "maxWindVelocity")
        cd = ConfigManager.get_param(params, "maxCharacteristicDimension")
        
        uas_spec_fields = []
        is_fixed_wing = not is_copter
        if is_fixed_wing:
            glide = ConfigManager.get_param(params, "glideRatioDenominator")
            roll = ConfigManager.get_param(params, "maxRollAngle")
            v_stall = ConfigManager.get_param(params, "stallVelocity")
            if is_en:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Glide Ratio: {glide:.1f}</w:t></w:r></w:p>')
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Maximum Roll Angle: {roll:.1f}°</w:t></w:r></w:p>')
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Stall Velocity (v_stall): {v_stall:.1f} m/s</w:t></w:r></w:p>')
            else:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Gleitzahl: {glide:.1f}</w:t></w:r></w:p>')
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Maximaler Rollwinkel: {roll:.1f}°</w:t></w:r></w:p>')
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Geschwindigkeit bei Strömungsabriss (v_stall): {v_stall:.1f} m/s</w:t></w:r></w:p>')
        else:
            pitch = ConfigManager.get_param(params, "maxPitchAngle")
            if is_en:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Maximum Pitch Angle: {pitch:.1f}°</w:t></w:r></w:p>')
            else:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Maximaler Nickwinkel: {pitch:.1f}°</w:t></w:r></w:p>')
            
        grb_method = ConfigManager.get_param(params, "groundRiskBufferMethod")
        if grb_method == "Parachute" or "parachute" in str(grb_method).lower():
            t_para_grb = ConfigManager.get_param(params, "parachuteOpeningTimeGRB")
            v_z = ConfigManager.get_param(params, "parachuteDescentRate")
            if is_en:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Parachute Opening Time (GRB): {t_para_grb:.1f} s</w:t></w:r></w:p>')
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Parachute Descent Rate (vZ): {v_z:.1f} m/s</w:t></w:r></w:p>')
            else:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Fallschirm Öffnungszeit (GRB): {t_para_grb:.1f} s</w:t></w:r></w:p>')
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Fallschirm Sinkgeschwindigkeit (vZ): {v_z:.1f} m/s</w:t></w:r></w:p>')
            
        lat_man_type = ConfigManager.get_param(params, "lateralContingencyManoeuvreType")
        if lat_man_type == "Parachute" or "parachute" in str(lat_man_type).lower():
            t_para_lat = ConfigManager.get_param(params, "parachuteOpeningTimeLateral")
            if is_en:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Parachute Opening Time (horizontal): {t_para_lat:.1f} s</w:t></w:r></w:p>')
            else:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Fallschirm Öffnungszeit (horizontal): {t_para_lat:.1f} s</w:t></w:r></w:p>')
            
        vert_man_type = ConfigManager.get_param(params, "verticalContingencyManoeuvreType")
        if vert_man_type == "Parachute" or "parachute" in str(vert_man_type).lower():
            t_para_vert = ConfigManager.get_param(params, "parachuteOpeningTimeVertical")
            if is_en:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Parachute Opening Time (vertical): {t_para_vert:.1f} s</w:t></w:r></w:p>')
            else:
                uas_spec_fields.append(f'<w:p><w:pPr><w:pStyle w:val="Listenabsatz"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t xml:space="preserve">Fallschirm Öffnungszeit (vertikal): {t_para_vert:.1f} s</w:t></w:r></w:p>')
            
        uas_spec_fields_str = "\n".join(uas_spec_fields)
        
        # Buffer methods
        if is_en:
            if grb_method == "Simplified":
                method_str = "Simplified Approach (1:1 Rule)"
            elif grb_method == "Ballistic":
                method_str = "Ballistic Approach"
            elif grb_method == "Glide":
                method_str = "Power-off with Glide Flight"
            elif grb_method == "Parachute":
                method_str = "Termination with Parachute Deployment"
            else:
                method_str = str(grb_method)
                
            lat_man = "Turn / Hover" if ConfigManager.get_param(params, "lateralContingencyManoeuvreType") == "Default" else "Parachute Deployment"
            vert_man = "Descent / Climb" if ConfigManager.get_param(params, "verticalContingencyManoeuvreType") == "Default" else "Parachute Deployment"
        else:
            if grb_method == "Simplified":
                method_str = "Vereinfachter Ansatz (1:1 Regel)"
            elif grb_method == "Ballistic":
                method_str = "Ballistischer Ansatz"
            elif grb_method == "Glide":
                method_str = "Antrieb aus mit Gleitflug"
            elif grb_method == "Parachute":
                method_str = "Terminierung mit Auslösen des Fallschirms"
            else:
                method_str = str(grb_method)
                
            lat_man = "Kurve / Anhalten" if ConfigManager.get_param(params, "lateralContingencyManoeuvreType") == "Default" else "Auslösen des Fallschirms"
            vert_man = "Sinkflug / Climb" if ConfigManager.get_param(params, "verticalContingencyManoeuvreType") == "Default" else "Auslösen des Fallschirms"
        
        # Assumptions
        gps_inacc = ConfigManager.get_param(params, "gpsInaccuracy")
        pos_err = ConfigManager.get_param(params, "positionError")
        map_err = ConfigManager.get_param(params, "mapError")
        reaction = ConfigManager.get_param(params, "reactionTime")
        alt_baro = ConfigManager.get_param(params, "altitudeErrorBarometric")
        alt_gps = ConfigManager.get_param(params, "altitudeErrorGps")
        add_horiz = ConfigManager.get_param(params, "additionalErrorLateral")
        add_vert = ConfigManager.get_param(params, "additionalErrorVertical")
        
        # 3. Build dynamic table & Calculate min/max ranges
        is_poly = (geometry_type == "Polygon")
        enable_asym = ConfigManager.get_param(params, "enableAsymmetricBufferWinddrift")
        
        grb_header = "S_GRB (Luv/Lee) (m)" if enable_asym else "S_GRB (m)"
        
        if is_poly:
            headers = [
                "WP",
                "Position (Lat, Lon)",
                "h_FG (m)",
                "v0 (m/s)",
                "S_CV (m)",
                grb_header,
                "h_CV (m)"
            ]
        else:
            headers = [
                "WP",
                "Position (Lat, Lon)",
                "h_FG (m)",
                "v0 (m/s)",
                "S_FG (m)",
                "S_CV (m)",
                grb_header,
                "h_CV (m)"
            ]
        
        rows = []
        fg_widths = []
        cv_widths = []
        grb_widths = []
        grb_luv_widths = []
        grb_lee_widths = []
        h_cvs = []
        
        has_narrow_cv = False
        for i, wp in enumerate(waypoints):
            idx_str = f"WP {i+1}"
            lat_lon_str = f"{wp[1]:.5f}, {wp[0]:.5f}"
            h = wp[2] if len(wp) > 2 else float(ConfigManager.get_param(params, "maxFlightHeight"))
            spd = wp[3] if len(wp) > 3 else float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
            fg_w = wp[4] if len(wp) > 4 else float(ConfigManager.get_param(params, "corridorWidth"))
            
            # Recalculate
            params_wp = params.copy()
            params_wp["geometry_type"] = geometry_type
            params_wp["maxFlightHeight"] = h
            params_wp["maxOpsSpeedV0"] = spd
            params_wp["maxVelocity"] = spd
            if geometry_type == "Circle":
                params_wp["corridorWidth"] = 2.0 * fg_w
            else:
                params_wp["corridorWidth"] = fg_w
            
            r_fg, r_cv, r_grb, h_cv, d_grb = BufferCalculator.calculate_buffer_widths(h, params_wp)
            s_cv = r_cv - r_fg
            s_grb = r_grb - r_cv
            if s_cv < 9.99:
                has_narrow_cv = True
                
            if enable_asym and d_grb > 0:
                luv = max(s_grb - d_grb, -s_cv)
                lee = s_grb + d_grb
                grb_str = f"{luv:.1f} / {lee:.1f}"
                grb_luv_widths.append(luv)
                grb_lee_widths.append(lee)
            else:
                grb_str = f"{s_grb:.1f}"
            
            fg_widths.append(fg_w)
            cv_widths.append(s_cv)
            grb_widths.append(s_grb)
            h_cvs.append(h_cv)
            
            if is_poly:
                rows.append([
                    idx_str,
                    lat_lon_str,
                    f"{h:.1f}",
                    f"{spd:.1f}",
                    f"{s_cv:.1f}",
                    grb_str,
                    f"{h_cv:.1f}"
                ])
            else:
                rows.append([
                    idx_str,
                    lat_lon_str,
                    f"{h:.1f}",
                    f"{spd:.1f}",
                    f"{fg_w:.1f}",
                    f"{s_cv:.1f}",
                    grb_str,
                    f"{h_cv:.1f}"
                ])
            
        table_xml = ReportGenerator.make_docx_table(headers, rows)
        
        # Format overall results ranges
        def get_range_str(val_list, unit="m"):
            if not val_list:
                return f"0.0 {unit}" if is_en else f"0,0 {unit}"
            min_v = min(val_list)
            max_v = max(val_list)
            if abs(min_v - max_v) < 0.05:
                val_str = f"{min_v:.1f} {unit}"
                return val_str if is_en else val_str.replace('.', ',')
            else:
                if is_en:
                    return f"{min_v:.1f} {unit} to {max_v:.1f} {unit}"
                else:
                    return f"{min_v:.1f} {unit} bis {max_v:.1f} {unit}".replace('.', ',')
                
        fg_range = get_range_str(fg_widths)
        cv_range = get_range_str(cv_widths)
        if enable_asym and grb_luv_widths:
            luv_range = get_range_str(grb_luv_widths)
            lee_range = get_range_str(grb_lee_widths)
            grb_range = f"{luv_range} (Luv) / {lee_range} (Lee)"
        else:
            grb_range = get_range_str(grb_widths)
        h_cv_range = get_range_str(h_cvs)
        
        # 4. Generate dynamic document.xml using placeholder replacements
        xml_content = ReportGenerator.get_document_xml_template(lang)
        
        # Replace the hardcoded overview map blip relationship ID with the one discovered from the template
        xml_content = xml_content.replace('<a:blip r:embed="rId6"', f'<a:blip r:embed="{overview_rid}"')
        

            
        # Format custom parameter block values
        h_fg_val = ConfigManager.get_param(params, "maxFlightHeight")
        if is_en:
            h_fg_str = f"{float(h_fg_val):.1f} m"
            
            if ConfigManager.get_param(params, "lateralContingencyManoeuvreType") == "Default":
                lat_man_text = "180° Turn" if is_fixed_wing else "Hover"
            else:
                lat_man_text = "Parachute Deployment"
                
            if ConfigManager.get_param(params, "verticalContingencyManoeuvreType") == "Default":
                vert_man_text = "Transition to Descent"
            else:
                vert_man_text = "Parachute Deployment"
                
            if grb_method == "Simplified":
                grb_man_text = "1:1 Rule"
            elif grb_method == "Ballistic":
                grb_man_text = "Ballistic Case"
            elif grb_method == "Glide":
                grb_man_text = "Glide Flight"
            elif grb_method == "Parachute":
                grb_man_text = "Parachute Deployment"
            else:
                grb_man_text = str(grb_method)
        else:
            h_fg_str = f"{float(h_fg_val):.1f}".replace('.', ',') + " m"
            
            if ConfigManager.get_param(params, "lateralContingencyManoeuvreType") == "Default":
                lat_man_text = "180° Kurve" if is_fixed_wing else "Anhalten"
            else:
                lat_man_text = "Auslösen des Fallschirms"
                
            if ConfigManager.get_param(params, "verticalContingencyManoeuvreType") == "Default":
                vert_man_text = "Übergang in den Sinkflug"
            else:
                vert_man_text = "Auslösen des Fallschirms"
                
            if grb_method == "Simplified":
                grb_man_text = "1:1 Regel"
            elif grb_method == "Ballistic":
                grb_man_text = "ballistischer Fall"
            elif grb_method == "Glide":
                grb_man_text = "Gleitflug"
            elif grb_method == "Parachute":
                grb_man_text = "Auslösen des Fallschirms"
            else:
                grb_man_text = str(grb_method)
            
        # Get aspect ratios and replace main map placeholders
        main_cx, main_cy = 5715000, 4000000
        if map_image_path and os.path.exists(map_image_path):
            size = get_png_size(map_image_path)
            if size:
                w, h = size
                if h > 0:
                    main_cy = int(main_cx * (h / w))
        xml_content = xml_content.replace("__MAIN_MAP_CX__", str(main_cx))
        xml_content = xml_content.replace("__MAIN_MAP_CY__", str(main_cy))
        
        xml_content = xml_content.replace("__H_FG__", h_fg_str)
        xml_content = xml_content.replace("__LAT_MAN_TEXT__", lat_man_text)
        xml_content = xml_content.replace("__VERT_MAN_TEXT__", vert_man_text)
        xml_content = xml_content.replace("__GRB_MAN_TEXT__", grb_man_text)
        
        v0_str = f"{v0:.1f}"
        vmax_str = f"{vmax:.1f}"
        if not is_en:
            v0_str = v0_str.replace('.', ',')
            vmax_str = vmax_str.replace('.', ',')
            
        escaped_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
        xml_content = xml_content.replace("__NAME__", escaped_name)
        xml_content = xml_content.replace("__DATE__", date_str)
        xml_content = xml_content.replace("__CENTER_COORDS__", center_str)
        xml_content = xml_content.replace("__PILOT_COORDS__", pilot_str)
        xml_content = xml_content.replace("__UAS_TYPE__", uas_type_str)
        xml_content = xml_content.replace("__ALTIMETRY__", altimetry_str)
        xml_content = xml_content.replace("__V0__", v0_str)
        xml_content = xml_content.replace("__VMAX__", vmax_str)
        xml_content = xml_content.replace("__V_WIND__", f"{v_wind:.1f}")
        xml_content = xml_content.replace("__CD__", f"{cd:.2f}")
        xml_content = xml_content.replace("__SPEC_FIELDS__", uas_spec_fields_str)
        xml_content = xml_content.replace("__LAT_MAN__", lat_man)
        xml_content = xml_content.replace("__VERT_MAN__", vert_man)
        xml_content = xml_content.replace("__METHOD__", method_str)
        xml_content = xml_content.replace("__GPS_INACC__", f"{gps_inacc:.1f}")
        xml_content = xml_content.replace("__POS_ERR__", f"{pos_err:.1f}")
        xml_content = xml_content.replace("__MAP_ERR__", f"{map_err:.1f}")
        xml_content = xml_content.replace("__REACTION__", f"{reaction:.1f}")
        xml_content = xml_content.replace("__ALT_BARO__", f"{alt_baro:.1f}")
        xml_content = xml_content.replace("__ALT_GPS__", f"{alt_gps:.1f}")
        xml_content = xml_content.replace("__ADD_HORIZ__", f"{add_horiz:.1f}")
        xml_content = xml_content.replace("__ADD_VERT__", f"{add_vert:.1f}")

        
        xml_content = xml_content.replace("__FG_RANGE__", fg_range)
        xml_content = xml_content.replace("__CV_RANGE__", cv_range)
        xml_content = xml_content.replace("__GRB_RANGE__", grb_range)
        xml_content = xml_content.replace("__H_CV_RANGE__", h_cv_range)
        
        # If any segment has a narrow Contingency Volume (s_cv < 10m), append a warning note below the table
        warning_xml = ""
        if has_narrow_cv:
            if is_en:
                warning_text = (
                    "Note: In at least one segment, the calculated Contingency Volume (CV) width (s_cv) is less than 10.0 meters. "
                    "According to EASA SORA (AMC1 to Article 11), a minimum width of 10 meters is recommended for the Contingency Volume. "
                    "A smaller buffer should be operationally justified in the ConOps (e.g., due to high system precision or rapid pilot reaction times)."
                )
            else:
                warning_text = (
                    "Hinweis: In mindestens einem Abschnitt unterschreitet die berechnete Breite des Contingency Volumes (s_cv) 10,0 Meter. "
                    "Nach EASA SORA (AMC1 zu Artikel 11) wird eine Mindestbreite von 10 Metern für das Contingency Volume empfohlen. "
                    "Eine Abweichung sollte im ConOps betrieblich begründet werden (z. B. durch hohe Navigationsgenauigkeit des UAS oder schnelle Reaktionszeiten)."
                )
                
            warning_xml = (
                f'<w:p>'
                f'<w:pPr>'
                f'<w:spacing w:before="120" w:after="120"/>'
                f'</w:pPr>'
                f'<w:r>'
                f'<w:rPr>'
                f'<w:i/>'
                f'<w:color w:val="D97706"/>' # Warning orange color
                f'</w:rPr>'
                f'<w:t xml:space="preserve">{warning_text}</w:t>'
                f'</w:r>'
                f'</w:p>'
            )
            
        xml_content = xml_content.replace("__TABLE_XML__", table_xml + warning_xml)
        
        # Build and replace __POPULATION_ANALYSIS_XML__
        pop_xml = []
        
        raster_name = params.get("pop_raster_name")
        raster_crs = params.get("pop_raster_crs")
        raster_res = params.get("pop_raster_res")
        
        # Escape XML characters to prevent corrupting the DOCX structure
        if raster_name:
            raster_name = raster_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
        if raster_crs:
            raster_crs = raster_crs.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
        if raster_res:
            raster_res = raster_res.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
        
        if is_en:
            pop_xml.append('  <w:p>')
            pop_xml.append('    <w:pPr>')
            pop_xml.append('      <w:pStyle w:val="berschrift3"/>')
            pop_xml.append('      <w:spacing w:before="400" w:after="100"/>')
            pop_xml.append('    </w:pPr>')
            pop_xml.append('    <w:r><w:t xml:space="preserve">Population Density and Ground Risk Assessment</w:t></w:r>')
            pop_xml.append('  </w:p>')
            
            if raster_name:
                intro_text = (
                    f"The analysis of the population density in the safety zones (Adjacent Area and Ground Risk Buffer) "
                    f"was performed based on the loaded GHS-POP raster data layer '{raster_name}' (CRS: {raster_crs}, "
                    f"Resolution: {raster_res}). This serves to evaluate operating risks and verify GRC according to SORA guidelines:"
                )
            else:
                intro_text = (
                    "The analysis of the population density in the safety zones (Adjacent Area and Ground Risk Buffer) "
                    "was performed based on the loaded GHS-POP raster data. This serves to evaluate operating risks "
                    "and verify GRC according to SORA guidelines:"
                )
                
            pop_xml.append('  <w:p>')
            pop_xml.append(f'    <w:r><w:t xml:space="preserve">{intro_text}</w:t></w:r>')
            pop_xml.append('  </w:p>')
        else:
            pop_xml.append('  <w:p>')
            pop_xml.append('    <w:pPr>')
            pop_xml.append('      <w:pStyle w:val="berschrift3"/>')
            pop_xml.append('      <w:spacing w:before="400" w:after="100"/>')
            pop_xml.append('    </w:pPr>')
            pop_xml.append('    <w:r><w:t xml:space="preserve">Bevölkerungsdichte- und Bodenrisikobewertung</w:t></w:r>')
            pop_xml.append('  </w:p>')
            
            if raster_name:
                intro_text = (
                    f"Die Analyse der Bevölkerungsdichte in den Sicherheitszonen (Adjacent Area und Ground Risk Buffer) "
                    f"wurde auf Basis des geladenen GHS-POP Raster-Layers '{raster_name}' (CRS: {raster_crs}, "
                    f"Auflösung: {raster_res}) durchgeführt. Dies dient zur Bewertung der Betriebsrisiken und zur GRC-Verifizierung gemäss den SORA-Richtlinien:"
                )
            else:
                intro_text = (
                    "Die Analyse der Bevölkerungsdichte in den Sicherheitszonen (Adjacent Area und Ground Risk Buffer) "
                    "wurde auf Basis der geladenen GHS-POP Rasterdaten durchgeführt. Dies dient zur Bewertung der "
                    "Betriebsrisiken und zur GRC-Verifizierung gemäss den SORA-Richtlinien:"
                )
                
            pop_xml.append('  <w:p>')
            pop_xml.append(f'    <w:r><w:t xml:space="preserve">{intro_text}</w:t></w:r>')
            pop_xml.append('  </w:p>')
        
        zones = [
            ("aa", "Adjacent Area (AA)"),
            ("grb", "Ground Risk Buffer (GRB)"),
            ("cv", "Contingency Volume (CV)"),
            ("fg", "Flight Geography (FG)")
        ]
        
        has_any_pop = False
        rows = []
        
        for zone_prefix, zone_name in zones:
            area = params.get(f"{zone_prefix}_area_km2")
            if area is not None:
                has_any_pop = True
                pop = params.get(f"{zone_prefix}_population", 0)
                avg_dens = params.get(f"{zone_prefix}_avg_density", 0)
                max_dens = params.get(f"{zone_prefix}_max_density")
                
                # Format values
                area_str = f"{float(area):.3f}"
                pop_str = f"{int(round(float(pop))):,}"
                avg_str = f"{float(avg_dens):.2f}"
                if max_dens is not None:
                    max_str = f"{float(max_dens):.2f}"
                else:
                    max_str = "N/A"
                    
                if not is_en:
                    area_str = area_str.replace('.', ',')
                    pop_str = pop_str.replace(',', '.')
                    avg_str = avg_str.replace('.', ',')
                    if max_str != "N/A":
                        max_str = max_str.replace('.', ',')
                        
                rows.append([zone_name, area_str, pop_str, avg_str, max_str])

        if has_any_pop:
            if is_en:
                pop_xml.append('  <w:p>')
                pop_xml.append('    <w:pPr><w:jc w:val="left"/></w:pPr>')
                pop_xml.append('    <w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Population Density per Zone:</w:t></w:r>')
                pop_xml.append('  </w:p>')
                headers = ["Zone", "Area (km²)", "Total Population", "Avg. Density\n(People/km²)", "Max. Density\n(People/km²)"]
            else:
                pop_xml.append('  <w:p>')
                pop_xml.append('    <w:pPr><w:jc w:val="left"/></w:pPr>')
                pop_xml.append('    <w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Bevölkerungsdichte pro Zone:</w:t></w:r>')
                pop_xml.append('  </w:p>')
                headers = ["Zone", "Fläche (km²)", "Gesamtbevölkerung", "Ø Dichte\n(Einw./km²)", "Max. Dichte\n(Einw./km²)"]
                
            pop_xml.append(ReportGenerator.make_docx_table(headers, rows))
            pop_xml.append('  <w:p><w:spacing w:before="200"/></w:p>')
        else:
            pop_xml.append('  <w:p>')
            if is_en:
                pop_xml.append('    <w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">No population density analysis was calculated before export. If you need this section, please run the calculation in the plugin at least once before exporting.</w:t></w:r>')
            else:
                pop_xml.append('    <w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">Für diese Planung wurde vor dem Export keine Bevölkerungsdichte-Analyse berechnet. Wenn Sie diesen Abschnitt brauchen, dann führen Sie die Berechnung im Plugin vor dem Export mindestens einmal durch.</w:t></w:r>')
            pop_xml.append('  </w:p>')
            
        pop_analysis_xml_str = "\n".join(pop_xml)
        xml_content = xml_content.replace("__POPULATION_ANALYSIS_XML__", pop_analysis_xml_str)
        
        xml_content = xml_content.replace("__HEADER_FOOTER_XML__", header_footer_xml_str)
        
        # Build Detail Maps XML
        if start_image_path and end_image_path and len(waypoints) >= 2:
            if is_en:
                detail_xml = """  <w:p>
    <w:pPr><w:pStyle w:val="berschrift3"/><w:spacing w:before="300" w:after="100"/></w:pPr>
    <w:r><w:t xml:space="preserve">Detail Views of Takeoff and Landing Area (approx. 500x500m)</w:t></w:r>
  </w:p>
  <w:p>
    <w:r><w:t xml:space="preserve">For detailed safety assessment, the high-resolution views of the takeoff and landing areas (each approx. 500 x 500 m) are shown below:</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">View of Takeoff Area (Takeoff / WP 1):</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="__START_MAP_CX__" cy="__START_MAP_CY__"/>
          <wp:effectExtent t="0" r="0" b="0" l="0"/>
          <wp:docPr id="2" name="Start_Map" descr="QGIS Map Start Area"/>
          <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
          </wp:cNvGraphicFramePr>
          <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:nvPicPr>
                  <pic:cNvPr id="0" name="" descr=""/>
                  <pic:cNvPicPr>
                    <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                  </pic:cNvPicPr>
                </pic:nvPicPr>
                <pic:blipFill>
                  <a:blip r:embed="__START_RID__" cstate="none"/>
                  <a:srcRect/>
                  <a:stretch><a:fillRect/></a:stretch>
                </pic:blipFill>
                <pic:spPr bwMode="auto">
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="__START_MAP_CX__" cy="__START_MAP_CY__"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                </pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/><w:spacing w:before="200"/></w:pPr>
    <w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">View of Landing Area (Landing / WP __LAST_WP_NUM__):</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="__END_MAP_CX__" cy="__END_MAP_CY__"/>
          <wp:effectExtent t="0" r="0" b="0" l="0"/>
          <wp:docPr id="3" name="End_Map" descr="QGIS Map Landing Area"/>
          <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
          </wp:cNvGraphicFramePr>
          <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:nvPicPr>
                  <pic:cNvPr id="0" name="" descr=""/>
                  <pic:cNvPicPr>
                    <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                  </pic:cNvPicPr>
                </pic:nvPicPr>
                <pic:blipFill>
                  <a:blip r:embed="__END_RID__" cstate="none"/>
                  <a:srcRect/>
                  <a:stretch><a:fillRect/></a:stretch>
                </pic:blipFill>
                <pic:spPr bwMode="auto">
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="__END_MAP_CX__" cy="__END_MAP_CY__"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                </pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
  </w:p>"""
            else:
                detail_xml = """  <w:p>
    <w:pPr><w:pStyle w:val="berschrift3"/><w:spacing w:before="300" w:after="100"/></w:pPr>
    <w:r><w:t xml:space="preserve">Detailausschnitte Start- und Landebereich (ca. 500x500m)</w:t></w:r>
  </w:p>
  <w:p>
    <w:r><w:t xml:space="preserve">Zur detaillierten Sicherheitsbewertung sind nachfolgend die hochauflösenden Ausschnitte des Start- und Landebereichs (jeweils ca. 500 x 500 m) dargestellt:</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Ausschnitt Startbereich (Takeoff / WP 1):</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="__START_MAP_CX__" cy="__START_MAP_CY__"/>
          <wp:effectExtent t="0" r="0" b="0" l="0"/>
          <wp:docPr id="2" name="Start_Map" descr="QGIS Map Start Area"/>
          <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
          </wp:cNvGraphicFramePr>
          <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:nvPicPr>
                  <pic:cNvPr id="0" name="" descr=""/>
                  <pic:cNvPicPr>
                    <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                  </pic:cNvPicPr>
                </pic:nvPicPr>
                <pic:blipFill>
                  <a:blip r:embed="__START_RID__" cstate="none"/>
                  <a:srcRect/>
                  <a:stretch><a:fillRect/></a:stretch>
                </pic:blipFill>
                <pic:spPr bwMode="auto">
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="__START_MAP_CX__" cy="__START_MAP_CY__"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                </pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/><w:spacing w:before="200"/></w:pPr>
    <w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Ausschnitt Landebereich (Landing / WP __LAST_WP_NUM__):</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="__END_MAP_CX__" cy="__END_MAP_CY__"/>
          <wp:effectExtent t="0" r="0" b="0" l="0"/>
          <wp:docPr id="3" name="End_Map" descr="QGIS Map Landing Area"/>
          <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
          </wp:cNvGraphicFramePr>
          <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:nvPicPr>
                  <pic:cNvPr id="0" name="" descr=""/>
                  <pic:cNvPicPr>
                    <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                  </pic:cNvPicPr>
                </pic:nvPicPr>
                <pic:blipFill>
                  <a:blip r:embed="__END_RID__" cstate="none"/>
                  <a:srcRect/>
                  <a:stretch><a:fillRect/></a:stretch>
                </pic:blipFill>
                <pic:spPr bwMode="auto">
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="__END_MAP_CX__" cy="__END_MAP_CY__"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                </pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
  </w:p>"""
            start_cx, start_cy = 4500000, 3150000
            if start_image_path and os.path.exists(start_image_path):
                size = get_png_size(start_image_path)
                if size:
                    w, h = size
                    if h > 0:
                        start_cy = int(start_cx * (h / w))
            end_cx, end_cy = 4500000, 3150000
            if end_image_path and os.path.exists(end_image_path):
                size = get_png_size(end_image_path)
                if size:
                    w, h = size
                    if h > 0:
                        end_cy = int(end_cx * (h / w))
            detail_xml = detail_xml.replace("__START_MAP_CX__", str(start_cx))
            detail_xml = detail_xml.replace("__START_MAP_CY__", str(start_cy))
            detail_xml = detail_xml.replace("__END_MAP_CX__", str(end_cx))
            detail_xml = detail_xml.replace("__END_MAP_CY__", str(end_cy))
            detail_xml = detail_xml.replace("__LAST_WP_NUM__", str(len(waypoints)))
            detail_xml = detail_xml.replace("__START_RID__", start_rid)
            detail_xml = detail_xml.replace("__END_RID__", end_rid)
            xml_content = xml_content.replace("__DETAIL_MAPS_XML__", detail_xml)
        else:
            xml_content = xml_content.replace("__DETAIL_MAPS_XML__", "")
            
        # Build Sora visual widget XML
        if sora_viz_image_path and os.path.exists(sora_viz_image_path):
            if is_en:
                sora_xml = """  <w:p>
    <w:pPr><w:pStyle w:val="berschrift3"/><w:spacing w:before="300" w:after="100"/></w:pPr>
    <w:r><w:t xml:space="preserve">Graphical Profile of Safety Volumes</w:t></w:r>
  </w:p>
  <w:p>
    <w:r><w:t xml:space="preserve">The following graphic schematically illustrates the geometric nesting and height relations of the calculated safety volumes (Flight Geography, Contingency Volume, and Ground Risk Buffer) in plan view and vertical profile:</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="__SORA_VIZ_CX__" cy="__SORA_VIZ_CY__"/>
          <wp:effectExtent t="0" r="0" b="0" l="0"/>
          <wp:docPr id="4" name="Sora_Viz" descr="SORA Volume Profile Visualization"/>
          <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
          </wp:cNvGraphicFramePr>
          <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:nvPicPr>
                  <pic:cNvPr id="0" name="" descr=""/>
                  <pic:cNvPicPr>
                    <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                  </pic:cNvPicPr>
                </pic:nvPicPr>
                <pic:blipFill>
                  <a:blip r:embed="__SORA_RID__" cstate="none"/>
                  <a:srcRect/>
                  <a:stretch><a:fillRect/></a:stretch>
                </pic:blipFill>
                <pic:spPr bwMode="auto">
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="__SORA_VIZ_CX__" cy="__SORA_VIZ_CY__"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                </pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
  </w:p>"""
            else:
                sora_xml = """  <w:p>
    <w:pPr><w:pStyle w:val="berschrift3"/><w:spacing w:before="300" w:after="100"/></w:pPr>
    <w:r><w:t xml:space="preserve">Grafisches Profil der Sicherheitsvolumina</w:t></w:r>
  </w:p>
  <w:p>
    <w:r><w:t xml:space="preserve">Die folgende Grafik veranschaulicht schematisch die geometrische Schachtelung und die Höhenrelationen der berechneten Sicherheitsvolumina (Flight Geography, Contingency Volume und Ground Risk Buffer) in der Draufsicht sowie im Vertikalprofil:</w:t></w:r>
  </w:p>
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r>
      <w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="__SORA_VIZ_CX__" cy="__SORA_VIZ_CY__"/>
          <wp:effectExtent t="0" r="0" b="0" l="0"/>
          <wp:docPr id="4" name="Sora_Viz" descr="SORA Volume Profile Visualization"/>
          <wp:cNvGraphicFramePr>
            <a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>
          </wp:cNvGraphicFramePr>
          <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:nvPicPr>
                  <pic:cNvPr id="0" name="" descr=""/>
                  <pic:cNvPicPr>
                    <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                  </pic:cNvPicPr>
                </pic:nvPicPr>
                <pic:blipFill>
                  <a:blip r:embed="__SORA_RID__" cstate="none"/>
                  <a:srcRect/>
                  <a:stretch><a:fillRect/></a:stretch>
                </pic:blipFill>
                <pic:spPr bwMode="auto">
                  <a:xfrm>
                    <a:off x="0" y="0"/>
                    <a:ext cx="__SORA_VIZ_CX__" cy="__SORA_VIZ_CY__"/>
                  </a:xfrm>
                  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                </pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing>
    </w:r>
  </w:p>"""
            sora_cx, sora_cy = 5715000, 3800000
            size = get_png_size(sora_viz_image_path)
            if size:
                w, h = size
                if h > 0:
                    sora_cy = int(sora_cx * (h / w))
            sora_xml = sora_xml.replace("__SORA_VIZ_CX__", str(sora_cx))
            sora_xml = sora_xml.replace("__SORA_VIZ_CY__", str(sora_cy))
            sora_xml = sora_xml.replace("__SORA_RID__", sora_rid)
            xml_content = xml_content.replace("__SORA_VIZ_XML__", sora_xml)
        else:
            xml_content = xml_content.replace("__SORA_VIZ_XML__", "")
        
        # 5. Modify Zip archive
        temp_zip_path = os.path.join(tempfile.gettempdir(), f"temp_{uuid.uuid4().hex}.docx")
        
        with zipfile.ZipFile(template_path, 'r') as z_in:
            with zipfile.ZipFile(temp_zip_path, 'w') as z_out:
                for item in z_in.infolist():
                    if item.filename == "word/document.xml":
                        z_out.writestr(item.filename, xml_content.encode('utf-8'))
                    elif item.filename == "word/_rels/document.xml.rels":
                        rels_content = z_in.read(item.filename).decode('utf-8')
                        new_rels = []
                        if start_image_path and end_image_path:
                            new_rels.append(f'<Relationship Id="{start_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image_start.png"/>')
                            new_rels.append(f'<Relationship Id="{end_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image_end.png"/>')
                        if sora_viz_image_path:
                            new_rels.append(f'<Relationship Id="{sora_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/sora_viz.png"/>')
                        
                        if new_rels:
                            rels_content = rels_content.replace('</Relationships>', "".join(new_rels) + '</Relationships>')
                        z_out.writestr(item.filename, rels_content.encode('utf-8'))
                    elif item.filename == overview_zip_path and map_image_path and os.path.exists(map_image_path):
                        with open(map_image_path, "rb") as f:
                            z_out.writestr(item.filename, f.read())
                    else:
                        z_out.writestr(item.filename, z_in.read(item.filename))
                        
                # Append the new physical image files to the ZIP package
                if start_image_path and os.path.exists(start_image_path):
                    with open(start_image_path, "rb") as f:
                        z_out.writestr("word/media/image_start.png", f.read())
                if end_image_path and os.path.exists(end_image_path):
                    with open(end_image_path, "rb") as f:
                        z_out.writestr("word/media/image_end.png", f.read())
                if sora_viz_image_path and os.path.exists(sora_viz_image_path):
                    with open(sora_viz_image_path, "rb") as f:
                        z_out.writestr("word/media/sora_viz.png", f.read())
                        
        try:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(
                        tr("log_remove_docx_failed", "Fehler beim Entfernen der existierenden DOCX-Datei: {error}").format(error=str(e)),
                        "QUCORE", Qgis.Critical
                    )
                    raise IOError(tr("error_docx_overwrite_failed", "Zieldatei konnte nicht überschrieben werden (Möglicherweise geöffnet?): {error}").format(error=str(e)))
            
            # Copy file content securely (handles cross-device/drive boundaries)
            shutil.copy(temp_zip_path, file_path)
            
            try:
                os.remove(temp_zip_path)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(
                    tr("log_remove_temp_zip_failed", "Fehler beim Löschen der temporären ZIP-Datei: {error}").format(error=str(e)),
                    "QUCORE", Qgis.Warning
                )
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                tr("log_save_docx_failed", "Fehler beim Speichern der finalen DOCX-Datei auf dem Ziellaufwerk: {error}").format(error=str(e)),
                "QUCORE", Qgis.Critical
            )
            raise IOError(tr("error_docx_save_failed", "Fehler beim Speichern der finalen DOCX-Datei auf dem Ziellaufwerk: {error}").format(error=str(e)))
