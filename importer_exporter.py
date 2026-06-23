# -*- coding: utf-8 -*-
import os
import json
import uuid
from qgis.core import QgsPointXY, QgsGeometry, QgsMessageLog, Qgis
from .buffer_calculator import BufferCalculator
from .config_manager import ConfigManager
from .translation_manager import TranslationManager

def tr(key, default=""):
    try:
        lang = ConfigManager.get_default("language")
    except KeyError:
        lang = "de"
    return TranslationManager.tr(key, lang, default)


def unpack_waypoint(w, params=None):
    """
    Standardizes unpacking of a waypoint list/tuple.
    Returns: (lon, lat, alt) as floats.
    """
    lon, lat = float(w[0]), float(w[1])
    
    if len(w) > 2:
        alt = float(w[2])
    elif params:
        alt = float(ConfigManager.get_param(params, "maxFlightHeight"))
    else:
        alt = 0.0
        
    return lon, lat, alt


class ImporterExporter:
    @staticmethod
    def import_dipul(file_path):
        """
        Imports waypoints, pilot position, parameters from a .dipul JSON file.
        Returns a tuple: (waypoints, pilot_pos, width, max_height, params, geom_type)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            # Try to repair truncated JSON if it cuts off in qucore_state
            idx = content.find('"qucore_state"')
            if idx != -1:
                comma_idx = content.rfind(',', 0, idx)
                slice_idx = comma_idx if comma_idx != -1 else idx
                repaired_content = content[:slice_idx] + "}}}"
                try:
                    data = json.loads(repaired_content)
                except Exception:
                    raise e
            else:
                raise e
            
        payload = data.get("payload", {})
        settings = payload.get("settings", {})
        
        # Check if complete QUCORE state exists in settings (100% reactivation)
        qucore_state = settings.get("qucore_state", None)
        warnings = []
        if qucore_state:
            qucore_state, warnings = ConfigManager.sanitize_imported_state(qucore_state)
            pilot_coords = qucore_state.get("pilot_pos")
            pilot_pos = None
            if pilot_coords and len(pilot_coords) >= 2:
                pilot_pos = QgsPointXY(pilot_coords[0], pilot_coords[1])
                
            waypoints = [tuple(wp) for wp in qucore_state.get("waypoints", [])]
            params = qucore_state.get("params", {})
            # Legacy migrations (already handled in sanitize, but we can leave it to be safe)
            if "maxVelocity" in params and "maxOpsSpeedV0" not in params:
                params["maxOpsSpeedV0"] = params["maxVelocity"]
            if "maxCommandableSpeedVmax" not in params:
                params["maxCommandableSpeedVmax"] = params.get("maxVelocityVmax", params.get("maxCommandSpeedVmax", params.get("maxOpsSpeedV0", 30.0)))
            geom_type = qucore_state.get("geometry_type", "Corridor")
            width = float(ConfigManager.get_param(params, "corridorWidth"))
            max_height = float(ConfigManager.get_param(params, "maxFlightHeight"))
            return waypoints, pilot_pos, width, max_height, params, geom_type, warnings

        geometry = payload.get("geometry", {})
        lateral = geometry.get("lateral", {})
        geom_type = lateral.get("type", "Corridor")
        
        # 1. Pilot Position
        pilot_coords = settings.get("pilotPosition", None)
        pilot_pos = None
        if pilot_coords and len(pilot_coords) >= 2:
            pilot_pos = QgsPointXY(pilot_coords[0], pilot_coords[1])
            
        # 2. Corridor Width
        width = float(lateral.get("width", 50.0))
        if geom_type == "Circle":
            width = float(lateral.get("radius", 50.0))
            
        # 3. Parameters
        params = {}
        
        # Assumptions
        assumptions = payload.get("assumptions", {}).get("values", {})
        for k, v in assumptions.items():
            params[k] = v
            
        # UAS Properties
        uas = payload.get("uasProperties", {}).get("values", {})
        for k, v in uas.items():
            if k == "type":
                if v in ["Rotorcraft", "RotorcraftWithParachute"]:
                    params["uas_type"] = "Multikopter"
                elif v in ["FixedWing", "FixedWingWithParachute"]:
                    params["uas_type"] = "FixedWing"
                else:
                    params["uas_type"] = v
            elif k == "altimetry":
                if v == "Barometric":
                    params["altimetry"] = "Baro"
                else:
                    params["altimetry"] = v
            elif k == "parachute" and isinstance(v, dict):
                p_time = v.get("openingTime", 2.0)
                p_rate = v.get("descentRate", 6.0)
                params["parachuteOpeningTimeGRB"] = p_time
                params["parachuteOpeningTimeLateral"] = p_time
                params["parachuteOpeningTimeVertical"] = p_time
                params["parachuteDescentRate"] = p_rate
            elif k == "maxVelocity":
                params["maxOpsSpeedV0"] = v
                params["maxVelocity"] = v # legacy fallback
            else:
                params[k] = v
        
        # Populate maxCommandableSpeedVmax if missing
        if "maxCommandableSpeedVmax" not in params:
            params["maxCommandableSpeedVmax"] = params.get("maxOpsSpeedV0", 30.0)
                
        # Settings
        params["groundRiskBufferMethod"] = settings.get("groundRiskBufferMethod", "Simplified")
        params["lateralContingencyManoeuvreType"] = settings.get("lateralContingencyManoeuvreType", "Default")
        params["verticalContingencyManoeuvreType"] = settings.get("verticalContingencyManoeuvreType", "Default")
        params["corridorWidth"] = width
        max_height = float(geometry.get("maxFlightHeight", 100.0))
        params["maxFlightHeight"] = max_height
        
        # 4. Waypoints with loaded maxFlightHeight and maxVelocity
        max_velocity = float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
        waypoints = []
        
        if geom_type == "Circle":
            center = lateral.get("center", [0.0, 0.0])
            radius = float(lateral.get("radius", 50.0))
            waypoints = [(center[0], center[1], max_height, max_velocity, radius)]
        elif geom_type == "Polygon":
            coords_list = lateral.get("coordinates", [[]])
            if coords_list and len(coords_list) > 0:
                coords = coords_list[0]
                if len(coords) >= 3 and coords[0] == coords[-1]:
                    coords = coords[:-1]
                for c in coords:
                    waypoints.append((c[0], c[1], max_height, max_velocity, width))
        else: # Corridor
            coords = lateral.get("coordinates", [])
            for c in coords:
                waypoints.append((c[0], c[1], max_height, max_velocity, width))
                
        # Sanitize the manually built state
        dummy_state = {
            "waypoints": waypoints,
            "pilot_pos": [pilot_pos.x(), pilot_pos.y()] if pilot_pos else None,
            "geometry_type": geom_type,
            "params": params
        }
        sanitized_state, warnings = ConfigManager.sanitize_imported_state(dummy_state)
        
        # Unpack sanitized state
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
    def export_dipul(file_path, waypoints, pilot_pos, const_height, const_speed, params, geometry_type="Corridor"):
        """
        Exports waypoints, pilot position, and parameters to a .dipul JSON file.
        Uses const_height and const_speed as the constant flight parameters for export.
        Ensures strict compliance with official DIPUL schemas and types.
        """
        width = float(params.get("corridorWidth", 500.0))
        
        pilot_coords = None
        if pilot_pos:
            pilot_coords = [pilot_pos.x(), pilot_pos.y()]
            
        lateral_block = {
            "id": str(uuid.uuid4()),
            "type": geometry_type
        }
        
        if geometry_type == "Circle":
            w0 = waypoints[0]
            lon0, lat0, _ = unpack_waypoint(w0, params)
            lateral_block["center"] = [lon0, lat0]
            # Use specific circle radius if present, otherwise fall back to width
            lateral_block["radius"] = float(w0[4]) if len(w0) > 4 else width
        elif geometry_type == "Polygon":
            coords = [[lon, lat] for lon, lat, _ in (unpack_waypoint(w, params) for w in waypoints)]
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            lateral_block["coordinates"] = [coords]
        else: # Corridor
            coords = [[lon, lat] for lon, lat, _ in (unpack_waypoint(w, params) for w in waypoints)]
            lateral_block["coordinates"] = coords
            lateral_block["width"] = width
            
        # Determine if a parachute is used
        grb_method = ConfigManager.get_param(params, "groundRiskBufferMethod")
        has_parachute = (
            grb_method == "Parachute" or 
            ConfigManager.get_param(params, "lateralContingencyManoeuvreType") == "Parachute" or 
            ConfigManager.get_param(params, "verticalContingencyManoeuvreType") == "Parachute"
        )

        # Normalize UAS type matching the official DIPUL schema
        uas_type_raw = ConfigManager.get_param(params, "uas_type")
        if uas_type_raw in ["Multikopter", "Rotorcraft"]:
            uas_type = "RotorcraftWithParachute" if has_parachute else "Rotorcraft"
        else:
            uas_type = "FixedWingWithParachute" if has_parachute else "FixedWing"
        
        # Normalize Altimetry (Baro -> Barometric, otherwise GPS)
        altimetry_raw = ConfigManager.get_param(params, "altimetry")
        altimetry = "Barometric" if altimetry_raw in ["Baro", "Barometric"] else "GPS"
        
        # Dynamically build uasProperties values matching the strict DIPUL schema
        uas_values = {
            "type": uas_type,
            "altimetry": altimetry,
            "maxVelocity": const_speed,
            "maxWindVelocity": float(params.get("maxWindVelocity", 3.0)),
            "maxCharacteristicDimension": float(params.get("maxCharacteristicDimension", 3.6))
        }
        
        if "FixedWing" in uas_type:
            uas_values["maxRollAngle"] = float(ConfigManager.get_param(params, "maxRollAngle"))
            uas_values["glideRatioDenominator"] = float(ConfigManager.get_param(params, "glideRatioDenominator"))
            uas_values["stallVelocity"] = float(ConfigManager.get_param(params, "stallVelocity"))
        else: # Rotorcraft / RotorcraftWithParachute
            uas_values["maxPitchAngle"] = float(params.get("maxPitchAngle", 30.0))

        # If a parachute is used, add its specs to uasProperties.values
        if has_parachute:
            if grb_method == "Parachute":
                t_para = float(params.get("parachuteOpeningTimeGRB", 2.0))
            elif ConfigManager.get_param(params, "lateralContingencyManoeuvreType") == "Parachute":
                t_para = float(params.get("parachuteOpeningTimeLateral", 2.0))
            else:
                t_para = float(params.get("parachuteOpeningTimeVertical", 2.0))
                
            uas_values["parachute"] = {
                "openingTime": t_para,
                "descentRate": float(params.get("parachuteDescentRate", 6.0))
            }

        # Dynamically build settings block to match presence/absence of pilotPosition
        settings_block = {
            "bufferDirection": "Outward",
            "groundRiskBufferMethod": grb_method,
            "lateralContingencyManoeuvreType": ConfigManager.get_param(params, "lateralContingencyManoeuvreType"),
            "verticalContingencyManoeuvreType": ConfigManager.get_param(params, "verticalContingencyManoeuvreType")
        }
        if pilot_coords:
            settings_block["pilotPosition"] = pilot_coords
            settings_block["name"] = "QGIS_Corridor_Export"
            settings_block["generalComment"] = "Generated by QUCORE (QGIS UAS Corridor Outlining & Routing Engine)"
            
        # Embed full QUCORE state inside settings block for 100% accurate reactivation
        state = {
            "waypoints": waypoints,
            "pilot_pos": pilot_coords,
            "geometry_type": geometry_type,
            "params": params
        }
        settings_block["qucore_state"] = state
            
        # Structure the payload matching the official DIPUL standard
        data = {
            "dipulFileVersion": "1.1",
            "payload": {
                "assumptions": {
                    "values": {
                        "gpsInaccuracy": float(ConfigManager.get_param(params, "gpsInaccuracy")),
                        "positionError": float(ConfigManager.get_param(params, "positionError")),
                        "mapError": float(ConfigManager.get_param(params, "mapError")),
                        "reactionTime": float(ConfigManager.get_param(params, "reactionTime")),
                        "altitudeErrorGps": float(ConfigManager.get_param(params, "altitudeErrorGps")),
                        "altitudeErrorBarometric": float(ConfigManager.get_param(params, "altitudeErrorBarometric")),
                        "additionalErrorLateral": float(ConfigManager.get_param(params, "additionalErrorLateral")),
                        "additionalErrorVertical": float(ConfigManager.get_param(params, "additionalErrorVertical"))
                    },
                    "rationales": {
                        "gpsInaccuracy": "", "positionError": "", "mapError": "", "reactionTime": "",
                        "altitudeErrorGps": "", "altitudeErrorBarometric": "", "additionalErrorLateral": "", "additionalErrorVertical": ""
                    }
                },
                "uasProperties": {
                    "values": uas_values,
                    "rationales": {
                        "maxVelocity": "", "maxWindVelocity": "", "maxCharacteristicDimension": "",
                        "maxRollAngle": "", "glideRatioDenominator": "", "stallVelocity": "",
                        "parachute": {"openingTime": "", "descentRate": ""}, "maxPitchAngle": ""
                    }
                },
                "geometry": {
                    "lateral": lateral_block,
                    "maxFlightHeight": const_height
                },
                "override": {
                    "values": {},
                    "rationales": {"lateralContingencyManoeuvre": "", "verticalContingencyManoeuvre": ""}
                },
                "settings": settings_block
            }
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def import_kml(file_path):
        """
        Parses waypoints and pilot position from a KML file.
        Returns a tuple: (waypoints, pilot_pos, width, max_height, params, geometry_type)
        Supports 100% reactivation if qucore_state is stored in ExtendedData.
        """
        from PyQt5.QtXml import QDomDocument
        
        doc = QDomDocument()
        with open(file_path, 'rb') as f:
            xml_data = f.read()
        ok, error_msg, error_line, error_col = doc.setContent(xml_data)
        if not ok:
            raise ValueError(tr("error_kml_parse_failed", "XML-Parsing der KML-Datei fehlgeschlagen: {error} in Zeile {line}, Spalte {col}").format(error=error_msg, line=error_line, col=error_col))
            
        root = doc.documentElement()
        
        def find_local_elements(parent, local_name):
            results = []
            def recurse(node):
                if node.isElement():
                    elem = node.toElement()
                    tag = elem.tagName()
                    if ":" in tag:
                        tag = tag.split(":", 1)[1]
                    if tag == local_name:
                        results.append(elem)
                child = node.firstChild()
                while not child.isNull():
                    recurse(child)
                    child = child.nextSibling()
            recurse(parent)
            return results
            
        def find_first_local_element(parent, local_name):
            def recurse(node):
                if node.isElement():
                    elem = node.toElement()
                    tag = elem.tagName()
                    if ":" in tag:
                        tag = tag.split(":", 1)[1]
                    if tag == local_name:
                        return elem
                child = node.firstChild()
                while not child.isNull():
                    res = recurse(child)
                    if res is not None:
                        return res
                    child = child.nextSibling()
                return None
            return recurse(parent)

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
                            h = float(parts[2]) if len(parts) >= 3 else 100.0
                            spd = 30.0
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
                        h = float(parts[2]) if len(parts) >= 3 else 100.0
                        spd = 30.0
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
                                h = float(parts[2]) if len(parts) >= 3 else 100.0
                                spd = 30.0
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
        width = 50.0
        max_height = 100.0
        if waypoints:
            max_height = max(wp[2] for wp in waypoints)
            
        params = {
            "maxFlightHeight": max_height,
            "maxOpsSpeedV0": 30.0,
            "maxCommandableSpeedVmax": 30.0,
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
            aga_op = float(params.get("opacity_adjacentarea", 0))
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

    @staticmethod
    def import_flightplan(file_path):
        """
        Imports waypoints from a SkyDemon flightplan file.
        Converts DMS coordinates to decimal and altitude (feet) to meters.
        Returns a tuple: (waypoints, pilot_pos, width, max_height, params, geom_type)
        """
        def dms_to_decimal(dms_str):
            direction = dms_str[0]
            rest = dms_str[1:]
            
            if direction in ['N', 'S']:
                deg = int(rest[0:2])
                minutes = int(rest[2:4])
                sec = float(rest[4:])
            else:
                deg = int(rest[0:3])
                minutes = int(rest[3:5])
                sec = float(rest[5:])
                
            val = deg + minutes / 60.0 + sec / 3600.0
            if direction in ['S', 'W']:
                val = -val
            return val

        def parse_dms_pair(pair_str):
            parts = pair_str.strip().split()
            lat = None
            lon = None
            for p in parts:
                if p.startswith('N') or p.startswith('S'):
                    lat = dms_to_decimal(p)
                elif p.startswith('E') or p.startswith('W'):
                    lon = dms_to_decimal(p)
            return lon, lat

        from PyQt5.QtXml import QDomDocument
        
        doc = QDomDocument()
        with open(file_path, 'rb') as f:
            xml_data = f.read()
        ok, error_msg, error_line, error_col = doc.setContent(xml_data)
        if not ok:
            raise ValueError(f"XML-Parsing des Flugplans fehlgeschlagen: {error_msg} in Zeile {error_line}, Spalte {error_col}")
            
        root = doc.documentElement()
        
        def find_local_elements(parent, local_name):
            results = []
            def recurse(node):
                if node.isElement():
                    elem = node.toElement()
                    tag = elem.tagName()
                    if ":" in tag:
                        tag = tag.split(":", 1)[1]
                    if tag == local_name:
                        results.append(elem)
                child = node.firstChild()
                while not child.isNull():
                    recurse(child)
                    child = child.nextSibling()
            recurse(parent)
            return results
            
        def find_first_local_element(parent, local_name):
            def recurse(node):
                if node.isElement():
                    elem = node.toElement()
                    tag = elem.tagName()
                    if ":" in tag:
                        tag = tag.split(":", 1)[1]
                    if tag == local_name:
                        return elem
                child = node.firstChild()
                while not child.isNull():
                    res = recurse(child)
                    if res is not None:
                        return res
                    child = child.nextSibling()
                return None
            return recurse(parent)

        pr = find_first_local_element(root, "PrimaryRoute")
        if pr is None:
            raise ValueError(tr("error_invalid_skydemon_format", "Ungültiges SkyDemon-Flugplanformat: <PrimaryRoute> nicht gefunden."))
            
        level_feet = float(pr.attribute("Level", "3000"))
        max_height = level_feet / 3.28084
        
        waypoints = []
        
        start_str = pr.attribute("Start", "")
        if start_str:
            lon, lat = parse_dms_pair(start_str)
            if lon is not None and lat is not None:
                waypoints.append((lon, lat, max_height, 30.0, 50.0))
                
        rhumb_lines = find_local_elements(pr, "RhumbLineRoute")
        for r in rhumb_lines:
            to_str = r.attribute("To", "")
            if to_str:
                lon, lat = parse_dms_pair(to_str)
                if lon is not None and lat is not None:
                    waypoints.append((lon, lat, max_height, 30.0, 50.0))
                    
        params = {
            "maxFlightHeight": max_height,
            "maxOpsSpeedV0": 30.0,
            "maxCommandableSpeedVmax": 30.0,
            "corridorWidth": 50.0
        }
        
        return waypoints, None, 50.0, max_height, params, "Corridor", []

    @staticmethod
    def export_flightplan(file_path, waypoints, const_height):
        """
        Exports waypoints to a SkyDemon flightplan file.
        Height is converted from meters to feet (level).
        """
        if not waypoints:
            raise ValueError("Keine Wegpunkte vorhanden.")
            
        def decimal_to_dms(deg, is_lat):
            direction = ""
            if is_lat:
                direction = "N" if deg >= 0 else "S"
            else:
                direction = "E" if deg >= 0 else "W"
                
            abs_deg = abs(deg)
            d = int(abs_deg)
            m_float = (abs_deg - d) * 60.0
            m = int(m_float)
            s = (m_float - m) * 60.0
            
            if is_lat:
                return f"{direction}{d:02d}{m:02d}{s:05.2f}"
            else:
                return f"{direction}{d:03d}{m:02d}{s:05.2f}"

        level_feet = int(round(const_height * 3.28084))
        
        w0 = waypoints[0]
        lon0, lat0, _ = unpack_waypoint(w0)
        start_dms = f"{decimal_to_dms(lat0, True)} {decimal_to_dms(lon0, False)}"
        
        xml_content = f'<?xml version="1.0" encoding="utf-8"?>\n'
        xml_content += '<DivelementsFlightPlanner>\n'
        xml_content += f'  <PrimaryRoute CourseType="GreatCircle" Start="{start_dms}" StartType="Unknown" Level="{level_feet}" Rules="Vfr" PlannedFuel="1.000000">\n'
        
        for w in waypoints[1:]:
            lon, lat, _ = unpack_waypoint(w)
            to_dms = f"{decimal_to_dms(lat, True)} {decimal_to_dms(lon, False)}"
            xml_content += f'    <RhumbLineRoute To="{to_dms}" ToType="Unknown" Level="MSL" LevelChange="B" />\n'
            
        xml_content += '    <ReferencedAirfields />\n'
        xml_content += '  </PrimaryRoute>\n'
        xml_content += '</DivelementsFlightPlanner>\n'
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)

    @staticmethod
    def import_geojson(file_path):
        """
        Imports waypoints, pilot position, and parameters from a GeoJSON file.
        Returns a tuple: (waypoints, pilot_pos, width, max_height, params, geom_type)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        waypoints = []
        pilot_pos = None
        params = {}
        geom_type = "Corridor"
        
        # Search for features inside the FeatureCollection
        features = data.get("features", [])
        
        # 1. Search for pilot position
        for feat in features:
            props = feat.get("properties", {})
            f_type = props.get("type", "")
            geom = feat.get("geometry", {})
            if f_type == "Pilot" and geom and geom.get("type") == "Point":
                coords = geom.get("coordinates")
                if coords and len(coords) >= 2:
                    pilot_pos = QgsPointXY(float(coords[0]), float(coords[1]))
                    
        # 2. Extract waypoints
        # Check if there are explicit "Waypoint" features
        wp_features = [f for f in features if f.get("properties", {}).get("type") == "Waypoint"]
        if wp_features:
            # Sort by index if present
            wp_features.sort(key=lambda f: f.get("properties", {}).get("index", 0))
            for feat in wp_features:
                geom = feat.get("geometry", {})
                if geom and geom.get("type") == "Point":
                    coords = geom.get("coordinates")
                    if coords and len(coords) >= 2:
                        props = feat.get("properties", {})
                        h = float(props.get("altitude", props.get("height", ConfigManager.get_default("maxFlightHeight"))))
                        spd = float(props.get("speed", props.get("velocity", ConfigManager.get_default("maxOpsSpeedV0"))))
                        w = float(props.get("fg_width", props.get("width", ConfigManager.get_default("corridorWidth"))))
                        waypoints.append((float(coords[0]), float(coords[1]), h, spd, w))
        
        # If no explicit waypoints were found, fall back to "Centerline" or "Flight Geography" or any LineString/Polygon
        if not waypoints:
            for feat in features:
                props = feat.get("properties", {})
                f_type = props.get("type", "")
                geom = feat.get("geometry", {})
                g_type = geom.get("type", "")
                
                if f_type == "Centerline" or g_type in ["LineString", "Polygon"]:
                    if g_type == "LineString":
                        coords = geom.get("coordinates", [])
                        geom_type = "Corridor"
                        for c in coords:
                            if len(c) >= 2:
                                # default height, speed, width
                                waypoints.append((float(c[0]), float(c[1]), 100.0, 30.0, 50.0))
                        break
                    elif g_type == "Polygon":
                        coords_list = geom.get("coordinates", [[]])
                        if coords_list and len(coords_list[0]) > 0:
                            coords = coords_list[0]
                            # closed polygon, remove last if identical
                            if len(coords) >= 3 and coords[0] == coords[-1]:
                                coords = coords[:-1]
                            geom_type = "Polygon"
                            for c in coords:
                                if len(c) >= 2:
                                    waypoints.append((float(c[0]), float(c[1]), 100.0, 30.0, 50.0))
                            break
                    elif g_type == "Point":
                        coords = geom.get("coordinates")
                        if coords and len(coords) >= 2:
                            geom_type = "Circle"
                            waypoints.append((float(coords[0]), float(coords[1]), 100.0, 30.0, 50.0))
                            break
                            
        # 3. Read general parameters if available from a metadata feature
        for feat in features:
            props = feat.get("properties", {})
            f_type = props.get("type", "")
            if f_type == "Metadata":
                for k, v in props.items():
                    if k not in ["type", "name", "geometry_type"]:
                        params[k] = v
                geom_type = props.get("geometry_type", geom_type)
                break
                
        # If waypoints are loaded, extract width and max_height
        width = 50.0
        max_height = 100.0
        if waypoints:
            width = waypoints[0][4]
            max_height = max(wp[2] for wp in waypoints)
            
        params["corridorWidth"] = width
        params["maxFlightHeight"] = max_height
        
        if not waypoints:
            raise ValueError(tr("error_no_waypoints_geojson", "Keine gültigen Wegpunkte oder Centerline-Geometrien im GeoJSON-Dokument gefunden."))
            
        # Sanitize manually extracted properties
        dummy_state = {
            "waypoints": waypoints,
            "pilot_pos": [pilot_pos.x(), pilot_pos.y()] if pilot_pos else None,
            "geometry_type": geom_type,
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
    def export_geojson(file_path, waypoints, pilot_pos, params, geometry_type="Corridor"):
        """
        Exports safety corridors, routing data, pilot position, and parameter metadata to a GeoJSON file.
        """
        features = []
        
        # 1. Metadata Feature (to persist all plugin parameters)
        meta_props = {
            "type": "Metadata",
            "name": "Planner Metadata",
            "geometry_type": geometry_type,
        }
        for k, v in params.items():
            # Only serialize standard json-friendly types
            if isinstance(v, (int, float, str, bool, list, dict)) or v is None:
                meta_props[k] = v
        
        features.append({
            "type": "Feature",
            "geometry": None,
            "properties": meta_props
        })
        
        # 2. Pilot Position
        if pilot_pos:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(pilot_pos.x()), float(pilot_pos.y())]
                },
                "properties": {
                    "type": "Pilot",
                    "name": "Pilot Position"
                }
            })
            
        # 3. Waypoint Features
        for i, wp in enumerate(waypoints):
            h = wp[2] if len(wp) > 2 else float(ConfigManager.get_param(params, "maxFlightHeight"))
            spd = wp[3] if len(wp) > 3 else float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
            fg_w = wp[4] if len(wp) > 4 else float(ConfigManager.get_param(params, "corridorWidth"))
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(wp[0]), float(wp[1])]
                },
                "properties": {
                    "type": "Waypoint",
                    "name": f"Waypoint {i+1}",
                    "index": i,
                    "altitude": h,
                    "speed": spd,
                    "fg_width": fg_w
                }
            })
            
        # 4. Route Centerline
        centerline_geom = None
        if geometry_type == "Circle" and waypoints:
            lon0, lat0, _ = unpack_waypoint(waypoints[0], params)
            centerline_geom = {
                "type": "Point",
                "coordinates": [lon0, lat0]
            }
        elif geometry_type == "Polygon" and waypoints:
            coords = [[lon, lat] for lon, lat, _ in (unpack_waypoint(w, params) for w in waypoints)]
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            centerline_geom = {
                "type": "Polygon",
                "coordinates": [coords]
            }
        elif waypoints:
            coords = [[lon, lat] for lon, lat, _ in (unpack_waypoint(w, params) for w in waypoints)]
            centerline_geom = {
                "type": "LineString",
                "coordinates": coords
            }
            
        if centerline_geom:
            features.append({
                "type": "Feature",
                "geometry": centerline_geom,
                "properties": {
                    "type": "Centerline",
                    "name": "Route Centerline"
                }
            })
            
        # 5. Safety Buffers (Flight Geography, Contingency Volume, Ground Risk Buffer, Adjacent Area)
        try:
            fg_geom, cv_geom, grb_geom, aga_geom = BufferCalculator.generate_buffers(waypoints, params, geometry_type)
        except Exception as e:
            QgsMessageLog.logMessage(f"Failed to generate buffers for GeoJSON: {e}", "QUCORE", Qgis.Critical)
            raise ValueError(f"Sicherheitskorridore konnten nicht generiert werden: {e}")
            
        def get_geojson_coordinates(geom):
            if not geom:
                return []
            try:
                if geom.isEmpty():
                    return []
                poly = geom.asPolygon()
                if not poly:
                    try:
                        poly = geom.constGet().geometryN(0).asPolygon() if hasattr(geom.constGet(), 'geometryN') else []
                    except Exception as e:
                        QgsMessageLog.logMessage(f"GeoJSON geometry parsing fallback: {e}", "QUCORE", Qgis.Info)
                if not poly or len(poly) == 0:
                    return []
                
                coords = []
                for pt in poly[0]:
                    coords.append([float(pt.x()), float(pt.y())])
                return coords
            except Exception as e:
                QgsMessageLog.logMessage(f"Failed to extract GeoJSON coordinates from geometry: {e}", "QUCORE", Qgis.Warning)
                return []
                
        fg_coords = get_geojson_coordinates(fg_geom)
        if fg_coords:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [fg_coords]
                },
                "properties": {
                    "type": "FG",
                    "name": "Flight Geography"
                }
            })
            
        cv_coords = get_geojson_coordinates(cv_geom)
        if cv_coords:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [cv_coords]
                },
                "properties": {
                    "type": "CV",
                    "name": "Contingency Volume"
                }
            })
            
        grb_coords = get_geojson_coordinates(grb_geom)
        if grb_coords:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [grb_coords]
                },
                "properties": {
                    "type": "GRB",
                    "name": "Ground Risk Buffer"
                }
            })
            
        aga_coords = get_geojson_coordinates(aga_geom)
        if aga_coords:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [aga_coords]
                },
                "properties": {
                    "type": "AGA",
                    "name": "Adjacent Area"
                }
            })
            
        geojson_data = {
            "type": "FeatureCollection",
            "name": "QGIS_Corridor_GeoJSON_Export",
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            },
            "features": features
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, indent=2)

    @staticmethod
    def export_plan(file_path, waypoints, pilot_pos, params, geometry_type="Corridor", geofence_type="FG", resolution=8, mp_compat=True):
        from .buffer_calculator import BufferCalculator
        from .config_manager import ConfigManager
        
        # Temporarily set resolution
        orig_res = getattr(BufferCalculator, 'BUFFER_SEGMENTS', 8)
        try:
            import sys
            if 'QUCORE.buffer_calculator' in sys.modules:
                sys.modules['QUCORE.buffer_calculator'].BUFFER_SEGMENTS = resolution
            BufferCalculator.BUFFER_SEGMENTS = resolution
            fg_geom, cv_geom, grb_geom, aga_geom = BufferCalculator.generate_buffers(waypoints, params, geometry_type)
        finally:
            if 'QUCORE.buffer_calculator' in sys.modules:
                sys.modules['QUCORE.buffer_calculator'].BUFFER_SEGMENTS = orig_res
            BufferCalculator.BUFFER_SEGMENTS = orig_res

        gf_geom = fg_geom if geofence_type == "FG" else cv_geom
        polygon_coords = []
        if gf_geom and not gf_geom.isEmpty():
            if gf_geom.isMultipart():
                gf_geom = gf_geom.asGeometryCollection()[0]
            poly = gf_geom.asPolygon()
            if poly and len(poly) > 0:
                # QGC expects [Lat, Lon]
                polygon_coords = [[pt.y(), pt.x()] for pt in poly[0]]

        items = []
        do_jump_id = 1
        
        if geometry_type == "Corridor" and waypoints:
            home_lat, home_lon, home_alt = waypoints[0][1], waypoints[0][0], waypoints[0][2]
            current_speed = -1
            
            for i, wp in enumerate(waypoints):
                lon, lat, alt = wp[0], wp[1], wp[2]
                v_current_wp = float(wp[3]) if len(wp) > 3 else float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
                
                # Determine segment speed
                if i < len(waypoints) - 1:
                    next_wp = waypoints[i+1]
                    v_next_wp = float(next_wp[3]) if len(next_wp) > 3 else float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
                    v_segment = min(v_current_wp, v_next_wp)
                else:
                    v_segment = v_current_wp
                    
                if mp_compat:
                    v_segment = int(round(v_segment))
                    alt = int(round(alt))
                    
                if abs(v_segment - current_speed) > 0.01:
                    items.append({
                        "autoContinue": True,
                        "command": 178, # DO_CHANGE_SPEED
                        "doJumpId": do_jump_id,
                        "frame": 2,
                        "params": [1, v_segment, -1, 0, 0, 0, 0],
                        "type": "SimpleItem"
                    })
                    do_jump_id += 1
                    current_speed = v_segment
                    
                items.append({
                    "autoContinue": True,
                    "command": 16, # NAV_WAYPOINT
                    "doJumpId": do_jump_id,
                    "frame": 3,
                    "params": [0, 0, 0, 0, lat, lon, alt],
                    "type": "SimpleItem"
                })
                do_jump_id += 1
        else:
            if waypoints:
                # For polygon/circle, calculate center for home pos
                avg_lat = sum(unpack_waypoint(w, params)[1] for w in waypoints) / len(waypoints)
                avg_lon = sum(unpack_waypoint(w, params)[0] for w in waypoints) / len(waypoints)
                _, _, avg_alt = unpack_waypoint(waypoints[0], params)
                home_lat, home_lon, home_alt = avg_lat, avg_lon, avg_alt
            elif pilot_pos:
                home_lat, home_lon, home_alt = pilot_pos.y(), pilot_pos.x(), float(ConfigManager.get_param(params, "maxFlightHeight"))
            else:
                home_lat, home_lon, home_alt = 0.0, 0.0, 0.0

        if mp_compat:
            home_alt = int(round(home_alt))
            
        cruise_spd = float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
        hover_spd = 5.0
        if mp_compat:
            cruise_spd = int(round(cruise_spd))
            hover_spd = int(round(hover_spd))
            
        fw_type = 3 if mp_compat else 12

        plan_data = {
            "fileType": "Plan",
            "version": 1,
            "geoFence": {
                "circles": [],
                "polygons": [
                    {
                        "inclusion": True,
                        "polygon": polygon_coords,
                        "version": 1
                    }
                ] if polygon_coords else [],
                "version": 2
            },
            "groundStation": "QGroundControl",
            "mission": {
                "cruiseSpeed": cruise_spd,
                "firmwareType": fw_type,
                "hoverSpeed": hover_spd,
                "items": items,
                "plannedHomePosition": [home_lat, home_lon, home_alt],
                "vehicleType": 2,
                "version": 2
            },
            "rallyPoints": {
                "points": [],
                "version": 2
            }
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=4)

    @staticmethod
    def export_waypoints(file_path, waypoints, pilot_pos, params, geometry_type="Corridor", export_mission=True, export_fence=True, geofence_type="FG", resolution=8, mp_compat=True):
        import os
        from .buffer_calculator import BufferCalculator
        from .config_manager import ConfigManager
        
        base_path = file_path
        if base_path.lower().endswith('.waypoints'):
            base_path = base_path[:-10]
            
        created_files = []
        
        if export_mission and waypoints:
            mission_path = f"{base_path}_Mission.waypoints"
            
            with open(mission_path, 'w', encoding='utf-8') as f:
                f.write("QGC WPL 110\n")
                
                # Write home pos
                home_lat, home_lon, home_alt = waypoints[0][1], waypoints[0][0], waypoints[0][2]
                if mp_compat:
                    home_alt = int(round(home_alt))
                f.write(f"0\t1\t0\t16\t0\t0\t0\t0\t{home_lat:.8f}\t{home_lon:.8f}\t{home_alt:.6f}\t1\n")
                
                seq = 1
                current_speed = -1
                
                for i, wp in enumerate(waypoints):
                    lon, lat, alt = wp[0], wp[1], wp[2]
                    v_current_wp = float(wp[3]) if len(wp) > 3 else float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
                    
                    if i < len(waypoints) - 1:
                        next_wp = waypoints[i+1]
                        v_next_wp = float(next_wp[3]) if len(next_wp) > 3 else float(ConfigManager.get_param(params, "maxOpsSpeedV0"))
                        v_segment = min(v_current_wp, v_next_wp)
                    else:
                        v_segment = v_current_wp
                        
                    if mp_compat:
                        v_segment = int(round(v_segment))
                        alt = int(round(alt))
                        
                    if abs(v_segment - current_speed) > 0.01:
                        # DO_CHANGE_SPEED
                        # param1=1 (Ground Speed), param2=Speed
                        # Use previous wp lat/lon if available, else current
                        prev_wp = waypoints[i-1] if i > 0 else wp
                        p_lon, p_lat = prev_wp[0], prev_wp[1]
                        f.write(f"{seq}\t0\t3\t178\t1.00000000\t{v_segment:.8f}\t-1.00000000\t0.00000000\t{p_lat:.8f}\t{p_lon:.8f}\t0.000000\t1\n")
                        seq += 1
                        current_speed = v_segment
                        
                    # WAYPOINT
                    f.write(f"{seq}\t0\t3\t16\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t{lat:.8f}\t{lon:.8f}\t{alt:.6f}\t1\n")
                    seq += 1
                    
            created_files.append(mission_path)
            
        if export_fence:
            fence_path = f"{base_path}_Fence-{geofence_type}.waypoints"
            
            orig_res = getattr(BufferCalculator, 'BUFFER_SEGMENTS', 8)
            try:
                import sys
                if 'QUCORE.buffer_calculator' in sys.modules:
                    sys.modules['QUCORE.buffer_calculator'].BUFFER_SEGMENTS = resolution
                BufferCalculator.BUFFER_SEGMENTS = resolution
                fg_geom, cv_geom, grb_geom, aga_geom = BufferCalculator.generate_buffers(waypoints, params, geometry_type)
            finally:
                if 'QUCORE.buffer_calculator' in sys.modules:
                    sys.modules['QUCORE.buffer_calculator'].BUFFER_SEGMENTS = orig_res
                BufferCalculator.BUFFER_SEGMENTS = orig_res

            if geofence_type == "FG":
                gf_geom = fg_geom
            elif geofence_type == "CV":
                gf_geom = cv_geom
            else:
                gf_geom = grb_geom
                
            polygon_coords = []
            if gf_geom and not gf_geom.isEmpty():
                if gf_geom.isMultipart():
                    gf_geom = gf_geom.asGeometryCollection()[0]
                poly = gf_geom.asPolygon()
                if poly and len(poly) > 0:
                    polygon_coords = [(pt.x(), pt.y()) for pt in poly[0]]
                    
            # Remove duplicated last point if closed
            if len(polygon_coords) > 1 and polygon_coords[-1] == polygon_coords[0]:
                polygon_coords = polygon_coords[:-1]
                    
            if polygon_coords:
                with open(fence_path, 'w', encoding='utf-8') as f:
                    f.write("QGC WPL 110\n")
                    
                    # Dummy home pos for fence (required by Ardupilot format usually)
                    home_lat, home_lon, home_alt = waypoints[0][1] if waypoints else 0.0, waypoints[0][0] if waypoints else 0.0, waypoints[0][2] if waypoints else 0.0
                    if mp_compat:
                        home_alt = int(round(home_alt))
                    f.write(f"0\t1\t0\t16\t0\t0\t0\t0\t{home_lat:.8f}\t{home_lon:.8f}\t{home_alt:.6f}\t1\n")
                    
                    for i, pt in enumerate(polygon_coords):
                        lon, lat = pt[0], pt[1]
                        # 5001 = FENCE_POINT. param1 = total points count. z = vertex index
                        f.write(f"{i+1}\t0\t3\t5001\t{len(polygon_coords):.8f}\t0.00000000\t0.00000000\t0.00000000\t{lat:.8f}\t{lon:.8f}\t{float(i):.6f}\t1\n")
                        
                created_files.append(fence_path)

        return created_files

