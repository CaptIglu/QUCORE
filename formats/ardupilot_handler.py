# -*- coding: utf-8 -*-
import json
import uuid
import math
from qgis.core import QgsPointXY, QgsMessageLog, Qgis, QgsGeometry
from ..config_manager import ConfigManager
from ..buffer_calculator import BufferCalculator
from .utils import unpack_waypoint, tr

class ArduPilotHandler:
    @staticmethod
    def export_plan(file_path, waypoints, pilot_pos, params, geometry_type="Corridor", geofence_type="FG", resolution=8, mp_compat=True):
        
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

