# -*- coding: utf-8 -*-
import json
import uuid
import math
from qgis.core import QgsPointXY, QgsMessageLog, Qgis, QgsGeometry
from ..config_manager import ConfigManager
from ..buffer_calculator import BufferCalculator
from .utils import unpack_waypoint, tr

class GeoJsonHandler:
    @staticmethod
    def import_geojson(file_path):
        """
        Imports waypoints, pilot position, and parameters from a GeoJSON file.
        Returns a tuple: (waypoints, pilot_pos, width, max_height, params, geom_type)
        """
        def_alt = float(ConfigManager.get_default('maxFlightHeight'))
        def_spd = float(ConfigManager.get_default('maxOpsSpeedV0'))
        def_w = float(ConfigManager.get_default('corridorWidth'))
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
                                waypoints.append((float(c[0]), float(c[1]), def_alt, def_spd, def_w))
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
                                    waypoints.append((float(c[0]), float(c[1]), def_alt, def_spd, def_w))
                            break
                    elif g_type == "Point":
                        coords = geom.get("coordinates")
                        if coords and len(coords) >= 2:
                            geom_type = "Circle"
                            waypoints.append((float(coords[0]), float(coords[1]), def_alt, def_spd, def_w))
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
        width = def_w
        max_height = def_alt
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

