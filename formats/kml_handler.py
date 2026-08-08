# -*- coding: utf-8 -*-
import json
import uuid
import math
from qgis.core import QgsPointXY, QgsMessageLog, Qgis, QgsGeometry
from ..config_manager import ConfigManager
from ..buffer_calculator import BufferCalculator
from .utils import unpack_waypoint, tr, find_local_elements, find_first_local_element

class KmlHandler:
    @staticmethod
    def import_kml(file_path):
        """
        Parses waypoints and pilot position from a KML file.
        Returns a tuple: (waypoints, pilot_pos, width, max_height, params, geometry_type)
        Supports 100% reactivation if qucore_state is stored in ExtendedData.
        """
        def_alt = float(ConfigManager.get_default('maxFlightHeight'))
        def_spd = float(ConfigManager.get_default('maxOpsSpeedV0'))
        def_w = float(ConfigManager.get_default('corridorWidth'))
        from qgis.PyQt.QtXml import QDomDocument
        
        doc = QDomDocument()
        with open(file_path, 'rb') as f:
            xml_data = f.read()
        ok, error_msg, error_line, error_col = doc.setContent(xml_data)
        if not ok:
            raise ValueError(tr("error_kml_parse_failed", "XML-Parsing der KML-Datei fehlgeschlagen: {error} in Zeile {line}, Spalte {col}").format(error=error_msg, line=error_line, col=error_col))
            
        root = doc.documentElement()
        
        # 1. Try to restore complete QUCORE state from ExtendedData
        data_elems = find_local_elements(root, "Data")
        for de in data_elems:
            if de.attribute("name") == "qucore_state":
                val_elem = find_first_local_element(de, "value")
                if val_elem is not None and val_elem.text():
                    state_json = val_elem.text()
                    try:
                        import json
                        state = json.loads(state_json)
                        state, warnings = ConfigManager.sanitize_imported_state(state)
                        waypoints = [tuple(wp) for wp in state.get("waypoints", [])]
                        pilot_coords = state.get("pilot_pos")
                        pilot_pos = None
                        if pilot_coords and len(pilot_coords) >= 2:
                            pilot_pos = QgsPointXY(pilot_coords[0], pilot_coords[1])
                        params = state.get("params", {})
                        geom_type = state.get("geometry_type", "Corridor")
                        width = float(ConfigManager.get_param(params, "corridorWidth"))
                        max_height = float(ConfigManager.get_param(params, "maxFlightHeight"))
                        return waypoints, pilot_pos, width, max_height, params, geom_type, warnings
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Failed to restore state from KML qucore_state: {e}", "QUCORE", Qgis.Warning)

        # 2. Fallback: Parse only geometry and pilot from KML
        waypoints = []
        pilot_pos = None
        geometry_type = "Corridor"
        
        found_centerline = False
        
        placemarks = find_local_elements(root, "Placemark")
        
        # Search for LineString or Point (Circle Center) or Polygon (vertices)
        for pm in placemarks:
            ls = find_first_local_element(pm, "LineString")
            if ls is not None:
                coord_elem = find_first_local_element(ls, "coordinates")
                if coord_elem is not None and coord_elem.text():
                    coord_text = coord_elem.text().strip()
                    pts = []
                    for pt_str in coord_text.split():
                        parts = pt_str.split(',')
                        if len(parts) >= 2:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            h = float(parts[2]) if len(parts) >= 3 else def_alt
                            spd = def_spd
                            pts.append((lon, lat, h, spd))
                    
                    if len(pts) >= 3 and pts[0][0] == pts[-1][0] and pts[0][1] == pts[-1][1]:
                        geometry_type = "Polygon"
                        waypoints = pts[:-1]
                    else:
                        geometry_type = "Corridor"
                        waypoints = pts
                    found_centerline = True
                    break
                    
            pt = find_first_local_element(pm, "Point")
            name_elem = find_first_local_element(pm, "name")
            name = name_elem.text() if name_elem is not None else ""
            if pt is not None and name != "Pilotenposition":
                coord_elem = find_first_local_element(pt, "coordinates")
                if coord_elem is not None and coord_elem.text():
                    parts = coord_elem.text().strip().split(',')
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        h = float(parts[2]) if len(parts) >= 3 else def_alt
                        spd = def_spd
                        waypoints = [(lon, lat, h, spd)]
                        geometry_type = "Circle"
                        found_centerline = True
                        break
                        
        if not found_centerline:
            for pm in placemarks:
                poly = find_first_local_element(pm, "Polygon")
                if poly is not None:
                    coord_elem = find_first_local_element(poly, "coordinates")
                    if coord_elem is not None and coord_elem.text():
                        coord_text = coord_elem.text().strip()
                        pts = []
                        for pt_str in coord_text.split():
                            parts = pt_str.split(',')
                            if len(parts) >= 2:
                                lon = float(parts[0])
                                lat = float(parts[1])
                                h = float(parts[2]) if len(parts) >= 3 else def_alt
                                spd = def_spd
                                pts.append((lon, lat, h, spd))
                        if pts:
                            geometry_type = "Polygon"
                            if len(pts) >= 3 and pts[0][0] == pts[-1][0] and pts[0][1] == pts[-1][1]:
                                waypoints = pts[:-1]
                            else:
                                waypoints = pts
                            break
                            
        for pm in placemarks:
            name_elem = find_first_local_element(pm, "name")
            name = name_elem.text() if name_elem is not None else ""
            
            pt = find_first_local_element(pm, "Point")
            if pt is not None:
                if name == "Pilotenposition" or not pilot_pos:
                    coord_elem = find_first_local_element(pt, "coordinates")
                    if coord_elem is not None and coord_elem.text():
                        parts = coord_elem.text().strip().split(',')
                        if len(parts) >= 2:
                            pilot_pos = QgsPointXY(float(parts[0]), float(parts[1]))
                            if name == "Pilotenposition":
                                break
                                
        if not waypoints:
            raise ValueError(tr("error_no_waypoints_kml", "Keine gültigen Wegpunkte oder Centerline-Geometrien im KML-Dokument gefunden."))
            
        # Fallback values for standard KML files
        width = def_w
        max_height = def_alt
        if waypoints:
            max_height = max(wp[2] for wp in waypoints)
            
        params = {
            "maxFlightHeight": max_height,
            "maxOpsSpeedV0": def_spd,
            "maxCommandableSpeedVmax": def_spd,
            "corridorWidth": width
        }
        
        # Sanitize manually extracted properties
        dummy_state = {
            "waypoints": waypoints,
            "pilot_pos": [pilot_pos.x(), pilot_pos.y()] if pilot_pos else None,
            "geometry_type": geometry_type,
            "params": params
        }
        sanitized_state, warnings = ConfigManager.sanitize_imported_state(dummy_state)
        
        geom_type = sanitized_state.get("geometry_type", "Corridor")
        waypoints = [tuple(wp) for wp in sanitized_state.get("waypoints", [])]
        pilot_coords = sanitized_state.get("pilot_pos")
        if pilot_coords and len(pilot_coords) >= 2:
            pilot_pos = QgsPointXY(pilot_coords[0], pilot_coords[1])
        else:
            pilot_pos = None
        params = sanitized_state.get("params", {})
        width = float(ConfigManager.get_param(params, "corridorWidth"))
        max_height = float(ConfigManager.get_param(params, "maxFlightHeight"))
        
        return waypoints, pilot_pos, width, max_height, params, geom_type, warnings

    @staticmethod
    def export_kml(file_path, waypoints, pilot_pos, params, geometry_type="Corridor"):
        """
        Exports safety corridors and routing data to an official KML file.
        Uses individual waypoint parameters (height, speed, FG width) to export the corridor exactly as defined.
        """
        import json
        import uuid
        
        # Serialize full planning state
        state = {
            "waypoints": waypoints,
            "pilot_pos": [pilot_pos.x(), pilot_pos.y()] if pilot_pos else None,
            "geometry_type": geometry_type,
            "params": params
        }
        state_json = json.dumps(state, ensure_ascii=False)
        state_xml_escaped = state_json.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", "&apos;")
        
        extended_data_xml = f"""      <ExtendedData>
        <Data name="qucore_state">
          <value>{state_xml_escaped}</value>
        </Data>
      </ExtendedData>"""

        fg_geom, cv_geom, grb_geom, aga_geom = BufferCalculator.generate_buffers(waypoints, params, geometry_type)
        
        def get_kml_coordinates_string(geom):
            if geom.isEmpty():
                return ""
            poly = geom.asPolygon()
            if not poly:
                try:
                    poly = geom.constGet().geometryN(0).asPolygon() if hasattr(geom.constGet(), 'geometryN') else []
                except Exception as e:
                    QgsMessageLog.logMessage(f"KML geometry parsing fallback: {e}", "QUCORE", Qgis.Info)
            if not poly:
                return ""
            
            coord_strs = []
            for pt in poly[0]:
                coord_strs.append(f"{pt.x():.14f},{pt.y():.14f}")
            return " ".join(coord_strs)

        fg_coords = get_kml_coordinates_string(fg_geom)
        cv_coords = get_kml_coordinates_string(cv_geom)
        grb_coords = get_kml_coordinates_string(grb_geom)
        aga_coords = get_kml_coordinates_string(aga_geom)
        
        # Route centerline KML representation with heights and altitudeMode
        centerline_xml = ""
        if geometry_type == "Circle":
            lon0, lat0, alt0 = unpack_waypoint(waypoints[0], params)
            centerline_xml = f"""      <Placemark id="{str(uuid.uuid4())}">
        <name>Center</name>
{extended_data_xml}
        <Point>
          <altitudeMode>relativeToGround</altitudeMode>
          <coordinates>{lon0:.14f},{lat0:.14f},{alt0:.2f}</coordinates>
        </Point>
      </Placemark>"""
        else:
            route_coord_strs = []
            for w in waypoints:
                lon, lat, alt = unpack_waypoint(w, params)
                route_coord_strs.append(f"{lon:.14f},{lat:.14f},{alt:.2f}")
            if geometry_type == "Polygon" and waypoints:
                lon0, lat0, alt0 = unpack_waypoint(waypoints[0], params)
                route_coord_strs.append(f"{lon0:.14f},{lat0:.14f},{alt0:.2f}")
            route_coords = " ".join(route_coord_strs)
            
            centerline_xml = f"""      <Placemark id="{str(uuid.uuid4())}">
        <name>Flugweg</name>
{extended_data_xml}
        <LineString>
          <altitudeMode>relativeToGround</altitudeMode>
          <coordinates>{route_coords}</coordinates>
        </LineString>
      </Placemark>"""
        
        pilot_xml = ""
        if pilot_pos:
            pilot_xml = f"""      <Placemark id="{str(uuid.uuid4())}">
        <name>Pilotenposition</name>
{extended_data_xml}
        <Point>
          <coordinates>{pilot_pos.x():.14f},{pilot_pos.y():.14f}</coordinates>
        </Point>
      </Placemark>"""

        aga_xml = ""
        if aga_coords:
            aga_op = float(ConfigManager.get_param(params, "opacity_adjacentarea"))
            aga_alpha = int(round(aga_op * 255 / 100))
            aga_alpha_hex = f"{aga_alpha:02x}"
            aga_xml = f"""      <Placemark id="adjacentAreaPolygonRing">
        <name>Adjacent Area</name>
{extended_data_xml}
        <Style>
          <LineStyle><color>ffb98029</color><width>2</width></LineStyle>
          <PolyStyle><color>{aga_alpha_hex}b98029</color></PolyStyle>
        </Style>
        <Polygon>
          <tessellate>1</tessellate>
          <altitudeMode>clampToGround</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>{aga_coords}</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>"""

        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/kml/2.2 https://developers.google.com/kml/schema/kml22gx.xsd">
  <Document>
    <Folder>
      <name>QGIS_Corridor_Export</name>
      <Placemark id="flightGeographyPolygon">
        <name>Flight Geography</name>
{extended_data_xml}
        <Style>
          <LineStyle><color>ff397c59</color><width>2</width></LineStyle>
          <PolyStyle><color>80397c59</color></PolyStyle>
        </Style>
        <Polygon>
          <tessellate>1</tessellate>
          <altitudeMode>clampToGround</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>{fg_coords}</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
      <Placemark id="contingencyPolygonRing">
        <name>Contingency Volume</name>
{extended_data_xml}
        <Style>
          <LineStyle><color>ff3dbbf7</color><width>2</width></LineStyle>
          <PolyStyle><color>803dbbf7</color></PolyStyle>
        </Style>
        <Polygon>
          <tessellate>1</tessellate>
          <altitudeMode>clampToGround</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>{cv_coords}</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
      <Placemark id="groundRiskBufferPolygonRing">
        <name>Ground Risk Buffer</name>
{extended_data_xml}
        <Style>
          <LineStyle><color>ff5757eb</color><width>2</width></LineStyle>
          <PolyStyle><color>805757eb</color></PolyStyle>
        </Style>
        <Polygon>
          <tessellate>1</tessellate>
          <altitudeMode>clampToGround</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>{grb_coords}</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
{pilot_xml}
{centerline_xml}
{aga_xml}
    </Folder>
  </Document>
</kml>
"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(kml_content)

