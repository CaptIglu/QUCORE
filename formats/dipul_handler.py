# -*- coding: utf-8 -*-
import json
import uuid
import math
from qgis.core import QgsPointXY, QgsMessageLog, Qgis, QgsGeometry
from ..config_manager import ConfigManager
from ..translation_manager import TranslationManager
from ..buffer_calculator import BufferCalculator
from .utils import unpack_waypoint

def tr(key, default=""):
    try:
        lang = ConfigManager.get_default("language")
    except KeyError:
        lang = "de"
    return TranslationManager.tr(key, lang, default)

class DipulHandler:
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

