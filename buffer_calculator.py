# -*- coding: utf-8 -*-
import math
from .config_manager import ConfigManager
from qgis.core import (
    QgsPointXY,
    QgsGeometry,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject
)

# Number of segments per quadrant to represent circles (higher = smoother, lower = faster).
# A value of 8 segments per quadrant (32 vertices per circle) provides an excellent balance
# of smooth visual display and highly performant spatial computations.
BUFFER_SEGMENTS = 8

def get_utm_epsg(lon, lat):
    """
    Finds the appropriate UTM zone EPSG code for a WGS 84 coordinate.
    Safely falls back to Universal Polar Stereographic (UPS) outside UTM bounds.
    """
    if lat > 84.0:
        return 32661  # WGS 84 / UPS North
    elif lat < -80.0:
        return 32761  # WGS 84 / UPS South

    zone = int((lon + 180) / 6) + 1
    if lat >= 0:
        return 32600 + zone
    else:
        return 32700 + zone

class BufferCalculator:
    @staticmethod
    def calculate_buffer_widths(h, params):
        """
        Calculates FG, CV, and GRB widths (distances from route centerline) for a given flight height h.
        Returns a tuple of (R_FG, R_CV, R_GRB, H_CV, D_MIN, D_MAX) in meters.
        """
        g = 9.81

        # ----------------------------------------------------
        # 1. READ PARAMETERS & DEFAULTS
        # ----------------------------------------------------
        uas_type = ConfigManager.get_param(params, "uas_type")
        altimetry = ConfigManager.get_param(params, "altimetry")
        
        # Enforce positive bounds to avoid singularities or negative scaling
        v0 = ConfigManager.get_param(params, "maxOpsSpeedV0")
        CD = ConfigManager.get_param(params, "maxCharacteristicDimension")
        
        gps_inaccuracy = ConfigManager.get_param(params, "gpsInaccuracy")
        pos_error = ConfigManager.get_param(params, "positionError")
        map_error = ConfigManager.get_param(params, "mapError")
        t_rz = ConfigManager.get_param(params, "reactionTime")
        
        alt_err_gps = ConfigManager.get_param(params, "altitudeErrorGps")
        alt_err_baro = ConfigManager.get_param(params, "altitudeErrorBarometric")
        
        # Altimetry vertical error
        h_delta = alt_err_gps if altimetry == "GPS" else alt_err_baro
        
        # ----------------------------------------------------
        # 2. CONTINGENCY VOLUME (CV) LATERAL
        # ----------------------------------------------------
        # Reaction path
        s_rz = v0 * t_rz
        
        # Contingency Manoeuvre distance (SCM)
        lat_manoeuvre = ConfigManager.get_param(params, "lateralContingencyManoeuvreType")
        s_cm = 0.0
        
        if lat_manoeuvre == "Default":
            # For Multikopter: Stop manoeuvre
            if uas_type == "Multikopter":
                angle = ConfigManager.get_param(params, "maxPitchAngle")
                rad = math.radians(angle)
                s_cm = (0.5 * v0 * v0) / (g * math.tan(rad)) if rad > 0 else 0
            else:
                # For Fixed Wing: Turnaround curve
                angle = ConfigManager.get_param(params, "maxRollAngle")
                rad = math.radians(angle)
                s_cm = (v0 * v0) / (g * math.tan(rad)) if rad > 0 else 0
        elif lat_manoeuvre == "Parachute":
            t_parachute = ConfigManager.get_param(params, "parachuteOpeningTimeLateral")
            s_cm = v0 * t_parachute
            
        # Lateral CV extension
        add_horiz = ConfigManager.get_param(params, "additionalErrorLateral")
        s_cv = gps_inaccuracy + pos_error + map_error + s_rz + s_cm + add_horiz
        
        # ----------------------------------------------------
        # 3. CONTINGENCY VOLUME (CV) VERTICAL
        # ----------------------------------------------------
        # Reaction height
        h_rz = 0.7 * v0 * t_rz
        
        # Vertical Manoeuvre height (HCM)
        vert_manoeuvre = ConfigManager.get_param(params, "verticalContingencyManoeuvreType")
        h_cm = 0.0
        
        if vert_manoeuvre == "Default":
            if uas_type == "Multikopter":
                # Convert kinetic to potential energy
                h_cm = (0.5 * v0 * v0) / g
            else:
                # Fixed Wing: 45 degree climb via circular path to horizontal flight
                h_cm = 0.3 * (v0 * v0) / g
        elif vert_manoeuvre == "Parachute":
            t_para_vert = ConfigManager.get_param(params, "parachuteOpeningTimeVertical")
            h_cm = 0.7 * v0 * t_para_vert
            
        # Absolute height of CV ceiling
        add_vert = ConfigManager.get_param(params, "additionalErrorVertical")
        h_cv = h + h_delta + h_rz + h_cm + add_vert
        
        # ----------------------------------------------------
        # 4. GROUND RISK BUFFER (GRB) LATERAL
        # ----------------------------------------------------
        grb_method = ConfigManager.get_param(params, "groundRiskBufferMethod")
        s_grb = 0.0
        
        if grb_method == "Simplified":
            s_grb = h_cv + 0.5 * CD
            
        elif grb_method == "Ballistic":
            s_grb = v0 * math.sqrt(2 * h_cv / g) + 0.5 * CD
            
        elif grb_method == "Glide":
            glide_ratio = ConfigManager.get_param(params, "glideRatioDenominator")
            s_grb = h_cv * glide_ratio
            
        elif grb_method == "Parachute":
            t_para_grb = ConfigManager.get_param(params, "parachuteOpeningTimeGRB")
            v_wind = ConfigManager.get_param(params, "maxWindVelocity")
            v_z = ConfigManager.get_param(params, "parachuteDescentRate")
            s_grb = v0 * t_para_grb + v_wind * (h_cv / v_z) if v_z > 0 else 0
            
        # Calculate d_grb for asymmetric wind drift
        d_min = 0.0
        d_max = 0.0
        if ConfigManager.get_param(params, "enableAsymmetricBufferWinddrift"):
            v_max = ConfigManager.get_param(params, "maxWindVelocity")
            v_min = ConfigManager.get_param(params, "minWindVelocity")
            if grb_method == "Parachute":
                v_z = ConfigManager.get_param(params, "parachuteDescentRate")
                t_fall = (h_cv / v_z) if v_z > 0 else 0.0
                d_max = v_max * t_fall
                d_min = v_min * t_fall
                # Reduce symmetric buffer by the wind portion that is now handled as a vector
                s_grb -= d_max
                s_grb = max(0.0, s_grb)
            elif grb_method == "Ballistic":
                t_fall = math.sqrt(2 * h_cv / g)
                d_max = v_max * t_fall
                d_min = v_min * t_fall
            elif grb_method == "Glide":
                glide_ratio = ConfigManager.get_param(params, "glideRatioDenominator")
                t_fall = (h_cv * glide_ratio) / v0 if v0 > 0 else 0.0
                d_max = v_max * t_fall
                d_min = v_min * t_fall
            
        # ----------------------------------------------------
        # 5. RADIUS FROM CENTERLINE
        # ----------------------------------------------------
        if params.get("geometry_type") == "Circle":
            circle_radius = ConfigManager.get_param(params, "circlemodeRadius")
            if circle_radius < 3.0 * CD:
                circle_radius = 3.0 * CD
            r_fg = circle_radius
        else:
            corridor_width = ConfigManager.get_param(params, "corridorWidth")
            if corridor_width < 3.0 * CD:
                corridor_width = 3.0 * CD
            r_fg = corridor_width / 2.0
        r_cv = r_fg + s_cv
        r_grb = r_cv + s_grb
        return r_fg, r_cv, r_grb, h_cv, d_min, d_max

    @staticmethod
    def _apply_wind_drift_envelope(base_geom, d_min, d_max, drift_angle_rad, variance_deg):
        if d_max == 0.0:
            return base_geom
            
        vectors = []
        vectors.append((d_min * math.sin(drift_angle_rad), d_min * math.cos(drift_angle_rad)))
        
        var_rad = math.radians(variance_deg)
        a_left = drift_angle_rad - var_rad
        a_right = drift_angle_rad + var_rad
        vectors.append((d_max * math.sin(a_left), d_max * math.cos(a_left)))
        vectors.append((d_max * math.sin(a_right), d_max * math.cos(a_right)))
        
        if variance_deg > 15.0:
            steps = int(variance_deg / 15.0)
            step_rad = var_rad / steps
            for i in range(1, steps):
                a1 = drift_angle_rad - var_rad + i * step_rad
                vectors.append((d_max * math.sin(a1), d_max * math.cos(a1)))
                a2 = drift_angle_rad + var_rad - i * step_rad
                vectors.append((d_max * math.sin(a2), d_max * math.cos(a2)))
                
        geoms_to_hull = []
        for dx, dy in vectors:
            geom_copy = QgsGeometry(base_geom)
            geom_copy.translate(dx, dy)
            geoms_to_hull.append(geom_copy)
                
        # Collect all geometries and calculate the convex hull at once
        # This bypasses expensive boolean union operations and calculates the hull over all vertices directly.
        collection = QgsGeometry.collectGeometry(geoms_to_hull)
        return collection.convexHull()

    @staticmethod
    def calculate_adjacent_area_width(params):
        """
        Calculates the Adjacent Area width S_AGA based on max commandable speed (vmax).
        Clamped between 5000m and 35000m.
        """
        vmax = ConfigManager.get_param(params, "maxCommandableSpeedVmax")
        s_aga = 180.0 * vmax
        if s_aga < 5000.0:
            return 5000.0
        elif s_aga > 35000.0:
            return 35000.0
        return s_aga


    @classmethod
    def generate_buffers(cls, waypoints, params, geometry_type="Corridor"):
        """
        Generates FG, CV, and GRB buffer geometries for a list of waypoints.
        Each waypoint is a tuple/dict: (lon, lat, height, speed, fg_width) or {'lon': lon, 'lat': lat, 'height': height, 'speed': speed, 'fg_width': fg_width}.
        
        Returns a tuple of QgsGeometry: (fg_geom, cv_geom, grb_geom, aga_geom) in WGS 84.
        """
        if not waypoints:
            return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()

        # Parse waypoints to robust format, clamp coordinates, and filter out coincident duplicates
        parsed_wpts = []
        def_h = ConfigManager.get_param(params, "maxFlightHeight")
        def_spd = ConfigManager.get_param(params, "maxOpsSpeedV0")
        def_fg = ConfigManager.get_param(params, "corridorWidth")
        
        for w in waypoints:
            try:
                if isinstance(w, dict):
                    if 'lon' not in w or 'lat' not in w:
                        raise ValueError("Fehlende Koordinate (lon/lat) im Wegpunkt.")
                    lon = float(w['lon'])
                    lat = float(w['lat'])
                    h = float(w.get('height', def_h))
                    spd = float(w.get('speed', def_spd))
                    fg = float(w.get('fg_width', def_fg))
                else:
                    lon = float(w[0])
                    lat = float(w[1])
                    h = float(w[2]) if len(w) > 2 else def_h
                    spd = float(w[3]) if len(w) > 3 else def_spd
                    fg = float(w[4]) if len(w) > 4 else def_fg
                
                # WGS84 boundary clamping
                lon = max(-180.0, min(180.0, lon))
                lat = max(-90.0, min(90.0, lat))
                h = max(0.0, h)
                spd = max(0.1, spd)
                fg = max(0.1, fg)
                
                # Skip coincident consecutive waypoints (< 1e-7 deg difference, approx. 1.1 cm)
                if parsed_wpts:
                    prev_lon, prev_lat = parsed_wpts[-1][0], parsed_wpts[-1][1]
                    if abs(lon - prev_lon) < 1e-7 and abs(lat - prev_lat) < 1e-7:
                        continue
                parsed_wpts.append((lon, lat, h, spd, fg))
            except (ValueError, TypeError, IndexError) as e:
                # Ignore malformed points
                from qgis.core import QgsMessageLog, Qgis
                import traceback
                QgsMessageLog.logMessage(f"Silent exception caught in buffer_calculator.py (line 204): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.MessageLevel.Warning)

        if not parsed_wpts:
            return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
                
        # ----------------------------------------------------
        # BRANCH ON GEOMETRY TYPE
        # ----------------------------------------------------
        enable_asym = ConfigManager.get_param(params, "enableAsymmetricBufferWinddrift")
        wind_dir = ConfigManager.get_param(params, "windDirection")
        variance_deg = ConfigManager.get_param(params, "windDirectionVariance")
        drift_angle_rad = math.radians(wind_dir + 180.0)

        if geometry_type == "Circle":
            # Circle uses the first waypoint as center, and fg as radius
            lon, lat, h, spd, radius = parsed_wpts[0]
            
            # Local parameters copy with the waypoint speed and FG width (radius)
            params_wp = params.copy()
            params_wp["geometry_type"] = "Circle"
            params_wp["maxOpsSpeedV0"] = spd
            params_wp["maxVelocity"] = spd
            params_wp["circlemodeRadius"] = radius
            
            r_fg, r_cv, r_grb, _h_cv, d_min, d_max = cls.calculate_buffer_widths(h, params_wp)
            
            # Calculate Adjacent Area width: S_AGA = max(5000, min(35000, 180 * vmax))
            s_aga = cls.calculate_adjacent_area_width(params)
                
            try:
                # Use local UTM zone for this single point (100% native EPSG, no custom Proj distortion)
                utm_epsg = get_utm_epsg(lon, lat)
                src_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                dest_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                project = QgsProject.instance()
                transform = QgsCoordinateTransform(src_crs, dest_crs, project)
                inverse_transform = QgsCoordinateTransform(dest_crs, src_crs, project)
                
                center_utm = transform.transform(QgsPointXY(lon, lat))
                
                fg_geom = QgsGeometry.fromPointXY(center_utm).buffer(r_fg, BUFFER_SEGMENTS)
                cv_geom = QgsGeometry.fromPointXY(center_utm).buffer(r_cv, BUFFER_SEGMENTS)
                grb_geom = QgsGeometry.fromPointXY(center_utm).buffer(r_grb, BUFFER_SEGMENTS)
                if enable_asym and d_max > 0:
                    grb_geom = cls._apply_wind_drift_envelope(grb_geom, d_min, d_max, drift_angle_rad, variance_deg)
                # We no longer combine with fg_geom, envelope handles it.
                aga_geom = cv_geom.buffer(s_aga, BUFFER_SEGMENTS)
                
                # Project back to WGS 84
                fg_geom.transform(inverse_transform)
                cv_geom.transform(inverse_transform)
                grb_geom.transform(inverse_transform)
                aga_geom.transform(inverse_transform)
                
                # Enforce validity of final output geometries
                if fg_geom and not fg_geom.isGeosValid():
                    fg_geom = fg_geom.makeValid()
                if cv_geom and not cv_geom.isGeosValid():
                    cv_geom = cv_geom.makeValid()
                if grb_geom and not grb_geom.isGeosValid():
                    grb_geom = grb_geom.makeValid()
                if aga_geom and not aga_geom.isGeosValid():
                    aga_geom = aga_geom.makeValid()
                
                return fg_geom, cv_geom, grb_geom, aga_geom
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Fehler bei Kreis-Geometrieberechnung: {e}", "QUCORE", Qgis.MessageLevel.Critical)
                return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
            
        elif geometry_type == "Polygon":
            # Vertices polygon
            if len(parsed_wpts) < 3:
                return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
                
            try:
                # Use native UTM zone of the polygon's midpoint to eliminate any scale distortion
                lons = [w[0] for w in parsed_wpts]
                lats = [w[1] for w in parsed_wpts]
                mid_lon = sum(lons) / len(lons)
                mid_lat = sum(lats) / len(lats)
                
                utm_epsg = get_utm_epsg(mid_lon, mid_lat)
                src_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                dest_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                project = QgsProject.instance()
                transform = QgsCoordinateTransform(src_crs, dest_crs, project)
                inverse_transform = QgsCoordinateTransform(dest_crs, src_crs, project)
                
                # Project vertices to UTM
                utm_pts = []
                for lon, lat, _, _, _ in parsed_wpts:
                    pt_wgs = QgsPointXY(lon, lat)
                    pt_utm = transform.transform(pt_wgs)
                    utm_pts.append(pt_utm)
                    
                # Create outer ring (closed)
                ring = list(utm_pts)
                ring.append(utm_pts[0])
                fg_polygon_utm = QgsGeometry.fromPolygonXY([ring])
                # Check and enforce validity of input polygon first to handle self-crossing paths
                if fg_polygon_utm and not fg_polygon_utm.isGeosValid():
                    # Return empty geometries to flag invalid self-intersecting state
                    return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
                
                fg_polygon_wgs = QgsGeometry(fg_polygon_utm)
                fg_polygon_wgs.transform(inverse_transform)
                
                # Calculate Adjacent Area width: S_AGA = max(5000, min(35000, 180 * vmax))
                s_aga = cls.calculate_adjacent_area_width(params)
                
                # Check if expert mode variable buffering is enabled
                if params.get("variable_polygon_buffers", False):
                    # Segment-specific variable buffering (Expert Mode)
                    radii = []
                    for i, (lon, lat, h, spd, fg) in enumerate(parsed_wpts):
                        params_wp = params.copy()
                        params_wp["geometry_type"] = "Polygon"
                        params_wp["maxOpsSpeedV0"] = spd
                        params_wp["maxVelocity"] = spd
                        params_wp["corridorWidth"] = fg
                        
                        r_fg, r_cv, r_grb, _h_cv, d_min, d_max = cls.calculate_buffer_widths(h, params_wp)
                        radii.append((r_fg, r_cv, r_grb, _h_cv, d_min, d_max))
                        
                    fg_capsules = []
                    cv_capsules = []
                    grb_capsules = []
                    
                    n = len(parsed_wpts)
                    for i in range(n):
                        next_idx = (i + 1) % n
                        lon_a, lat_a, h_a, spd_a, fg_a = parsed_wpts[i]
                        lon_b, lat_b, h_b, spd_b, fg_b = parsed_wpts[next_idx]
                        
                        r_fg_a, r_cv_a, r_grb_a, _, d_min_a, d_max_a = radii[i]
                        r_fg_b, r_cv_b, r_grb_b, _, d_min_b, d_max_b = radii[next_idx]
                        
                        seg_utm_epsg = get_utm_epsg(lon_a, lat_a)
                        seg_dest_crs = QgsCoordinateReferenceSystem(f"EPSG:{seg_utm_epsg}")
                        
                        seg_transform = QgsCoordinateTransform(src_crs, seg_dest_crs, project)
                        seg_inverse_transform = QgsCoordinateTransform(seg_dest_crs, src_crs, project)
                        
                        pt_a_utm = seg_transform.transform(QgsPointXY(lon_a, lat_a))
                        pt_b_utm = seg_transform.transform(QgsPointXY(lon_b, lat_b))
                        
                        c_fg_a = QgsGeometry.fromPointXY(pt_a_utm).buffer(r_fg_a, BUFFER_SEGMENTS)
                        c_fg_b = QgsGeometry.fromPointXY(pt_b_utm).buffer(r_fg_b, BUFFER_SEGMENTS)
                        fg_capsule = c_fg_a.combine(c_fg_b).convexHull()
                        fg_capsule.transform(seg_inverse_transform)
                        fg_capsules.append(fg_capsule)
                        
                        c_cv_a = QgsGeometry.fromPointXY(pt_a_utm).buffer(r_cv_a, BUFFER_SEGMENTS)
                        c_cv_b = QgsGeometry.fromPointXY(pt_b_utm).buffer(r_cv_b, BUFFER_SEGMENTS)
                        cv_capsule = c_cv_a.combine(c_cv_b).convexHull()
                        cv_capsule.transform(seg_inverse_transform)
                        cv_capsules.append(cv_capsule)
                        
                        c_grb_a = QgsGeometry.fromPointXY(pt_a_utm).buffer(r_grb_a, BUFFER_SEGMENTS)
                        c_grb_b = QgsGeometry.fromPointXY(pt_b_utm).buffer(r_grb_b, BUFFER_SEGMENTS)
                        if enable_asym:
                            c_grb_a = cls._apply_wind_drift_envelope(c_grb_a, d_min_a, d_max_a, drift_angle_rad, variance_deg)
                            c_grb_b = cls._apply_wind_drift_envelope(c_grb_b, d_min_b, d_max_b, drift_angle_rad, variance_deg)
                        grb_capsule = c_grb_a.combine(c_grb_b).convexHull()
                        grb_capsule.transform(seg_inverse_transform)
                        grb_capsules.append(grb_capsule)
                        
                    fg_geom = fg_polygon_wgs.combine(QgsGeometry.unaryUnion(fg_capsules))
                    cv_geom = fg_polygon_wgs.combine(QgsGeometry.unaryUnion(cv_capsules))
                    grb_geom = fg_polygon_wgs.combine(QgsGeometry.unaryUnion(grb_capsules))
                else:
                    # Uniform constant buffering (Default Mode) - Use maximum values for safety
                    max_h = max(w[2] for w in parsed_wpts)
                    max_spd = max(w[3] for w in parsed_wpts)
                    max_fg = max(w[4] for w in parsed_wpts)
                    
                    params_wp = params.copy()
                    params_wp["geometry_type"] = "Polygon"
                    params_wp["maxOpsSpeedV0"] = max_spd
                    params_wp["maxVelocity"] = max_spd
                    params_wp["corridorWidth"] = max_fg
                    
                    r_fg_tmp, r_cv_tmp, r_grb_tmp, _h_cv, d_min_tmp, d_max_tmp = cls.calculate_buffer_widths(max_h, params_wp)
                    s_cv = r_cv_tmp - r_fg_tmp
                    s_grb = r_grb_tmp - r_cv_tmp
                    
                    cv_geom_utm = fg_polygon_utm.buffer(s_cv, BUFFER_SEGMENTS)
                    grb_geom_utm = cv_geom_utm.buffer(s_grb, BUFFER_SEGMENTS)
                    if enable_asym and d_max_tmp > 0:
                        grb_geom_utm = cls._apply_wind_drift_envelope(grb_geom_utm, d_min_tmp, d_max_tmp, drift_angle_rad, variance_deg)
                    
                    cv_geom = cv_geom_utm
                    cv_geom.transform(inverse_transform)
                    
                    grb_geom = grb_geom_utm
                    grb_geom.transform(inverse_transform)
                    
                    fg_geom = fg_polygon_wgs
                
                # Generate Adjacent Area buffer around CV
                cv_clone = QgsGeometry(cv_geom)
                cv_clone.transform(transform)
                aga_geom = cv_clone.buffer(s_aga, BUFFER_SEGMENTS)
                aga_geom.transform(inverse_transform)
                
                # Enforce validity of final projected outputs
                if fg_geom and not fg_geom.isGeosValid():
                    fg_geom = fg_geom.makeValid()
                if cv_geom and not cv_geom.isGeosValid():
                    cv_geom = cv_geom.makeValid()
                if grb_geom and not grb_geom.isGeosValid():
                    grb_geom = grb_geom.makeValid()
                if aga_geom and not aga_geom.isGeosValid():
                    aga_geom = aga_geom.makeValid()
                
                return fg_geom, cv_geom, grb_geom, aga_geom
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Fehler bei Polygon-Geometrieberechnung: {e}", "QUCORE", Qgis.MessageLevel.Critical)
                return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
            
        else: # Corridor (Default)
            # stores (r_fg, r_cv, r_grb) for each waypoint
            radii = []
            for i, (lon, lat, h, spd, fg) in enumerate(parsed_wpts):
                params_wp = params.copy()
                params_wp["geometry_type"] = "Corridor"
                params_wp["maxOpsSpeedV0"] = spd
                params_wp["maxVelocity"] = spd
                params_wp["corridorWidth"] = fg
                
                r_fg, r_cv, r_grb, _h_cv, d_min, d_max = cls.calculate_buffer_widths(h, params_wp)
                radii.append((r_fg, r_cv, r_grb, _h_cv, d_min, d_max))
                
            fg_capsules = []
            cv_capsules = []
            grb_capsules = []
            
            project = QgsProject.instance()
            src_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            # If only 1 waypoint, generate simple circles in its local UTM zone
            if len(parsed_wpts) == 1:
                lon, lat, h, spd, radius = parsed_wpts[0]
                r_fg, r_cv, r_grb, _h_cv, d_min, d_max = radii[0]
                
                s_aga = cls.calculate_adjacent_area_width(params)
                    
                try:
                    utm_epsg = get_utm_epsg(lon, lat)
                    dest_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                    transform = QgsCoordinateTransform(src_crs, dest_crs, project)
                    inverse_transform = QgsCoordinateTransform(dest_crs, src_crs, project)
                    
                    pt_utm = transform.transform(QgsPointXY(lon, lat))
                    
                    fg_geom = QgsGeometry.fromPointXY(pt_utm).buffer(r_fg, BUFFER_SEGMENTS)
                    cv_geom = QgsGeometry.fromPointXY(pt_utm).buffer(r_cv, BUFFER_SEGMENTS)
                    grb_geom = QgsGeometry.fromPointXY(pt_utm).buffer(r_grb, BUFFER_SEGMENTS)
                    if enable_asym and d_max > 0:
                        grb_geom = cls._apply_wind_drift_envelope(grb_geom, d_min, d_max, drift_angle_rad, variance_deg)
                    # We no longer combine with fg_geom, envelope handles it.
                    aga_geom = cv_geom.buffer(s_aga, BUFFER_SEGMENTS)
                    
                    # Project back to WGS 84
                    fg_geom.transform(inverse_transform)
                    cv_geom.transform(inverse_transform)
                    grb_geom.transform(inverse_transform)
                    aga_geom.transform(inverse_transform)
                    
                    # Enforce validity of outputs
                    if fg_geom and not fg_geom.isGeosValid():
                        fg_geom = fg_geom.makeValid()
                    if cv_geom and not cv_geom.isGeosValid():
                        cv_geom = cv_geom.makeValid()
                    if grb_geom and not grb_geom.isGeosValid():
                        grb_geom = grb_geom.makeValid()
                    if aga_geom and not aga_geom.isGeosValid():
                        aga_geom = aga_geom.makeValid()
                    
                    return fg_geom, cv_geom, grb_geom, aga_geom
                except Exception as e:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(f"Fehler bei Einzelwegpunkt-Corridor-Geometrieberechnung: {e}", "QUCORE", Qgis.MessageLevel.Critical)
                    return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
    
            # For multiple waypoints, build tapered capsules for each segment.
            # To ensure the flightway remains perfectly and symmetrically centered inside the buffers
            # even over extreme trans-continental distances (e.g. Hamburg to London),
            # each segment is buffered in its OWN local UTM zone and immediately transformed back to WGS 84.
            # This completely bypasses the slow sub-segment loop, improving performance by 1000x on long routes.
            for i in range(len(parsed_wpts) - 1):
                try:
                    lon_a, lat_a, h_a, spd_a, fg_a = parsed_wpts[i]
                    lon_b, lat_b, h_b, spd_b, fg_b = parsed_wpts[i+1]
                    
                    r_fg_a, r_cv_a, r_grb_a, _, d_min_a, d_max_a = radii[i]
                    r_fg_b, r_cv_b, r_grb_b, _, d_min_b, d_max_b = radii[i+1]
                    
                    utm_epsg = get_utm_epsg(lon_a, lat_a)
                    dest_crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")
                    
                    transform = QgsCoordinateTransform(src_crs, dest_crs, project)
                    inverse_transform = QgsCoordinateTransform(dest_crs, src_crs, project)
                    
                    pt_a_utm = transform.transform(QgsPointXY(lon_a, lat_a))
                    pt_b_utm = transform.transform(QgsPointXY(lon_b, lat_b))
                    
                    c_fg_a = QgsGeometry.fromPointXY(pt_a_utm).buffer(r_fg_a, BUFFER_SEGMENTS)
                    c_fg_b = QgsGeometry.fromPointXY(pt_b_utm).buffer(r_fg_b, BUFFER_SEGMENTS)
                    fg_capsule = c_fg_a.combine(c_fg_b).convexHull()
                    fg_capsule.transform(inverse_transform) # Transform back to WGS 84 immediately
                    fg_capsules.append(fg_capsule)
                    
                    c_cv_a = QgsGeometry.fromPointXY(pt_a_utm).buffer(r_cv_a, BUFFER_SEGMENTS)
                    c_cv_b = QgsGeometry.fromPointXY(pt_b_utm).buffer(r_cv_b, BUFFER_SEGMENTS)
                    cv_capsule = c_cv_a.combine(c_cv_b).convexHull()
                    cv_capsule.transform(inverse_transform) # Transform back to WGS 84 immediately
                    cv_capsules.append(cv_capsule)
                    
                    c_grb_a = QgsGeometry.fromPointXY(pt_a_utm).buffer(r_grb_a, BUFFER_SEGMENTS)
                    c_grb_b = QgsGeometry.fromPointXY(pt_b_utm).buffer(r_grb_b, BUFFER_SEGMENTS)
                    if enable_asym:
                        c_grb_a = cls._apply_wind_drift_envelope(c_grb_a, d_min_a, d_max_a, drift_angle_rad, variance_deg)
                        c_grb_b = cls._apply_wind_drift_envelope(c_grb_b, d_min_b, d_max_b, drift_angle_rad, variance_deg)
                    grb_capsule = c_grb_a.combine(c_grb_b).convexHull()
                    grb_capsule.transform(inverse_transform) # Transform back to WGS 84 immediately
                    grb_capsules.append(grb_capsule)
                except Exception as e:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(f"Fehler bei Kapsel-Berechnung für Segment {i}: {e}", "QUCORE", Qgis.MessageLevel.Warning)
                    
            if not fg_capsules:
                return QgsGeometry(), QgsGeometry(), QgsGeometry(), QgsGeometry()
                
            # Determine Adjacent Area width S_AGA based on max commandable speed
            s_aga = cls.calculate_adjacent_area_width(params)
 
            # Merge all segment capsules in WGS 84
            fg_merged = QgsGeometry.unaryUnion(fg_capsules)
            cv_merged = QgsGeometry.unaryUnion(cv_capsules)
            grb_merged = QgsGeometry.unaryUnion(grb_capsules)
            
            # Ensure GRB does NOT artificially cover FG anymore, the envelope handles it
            # (Legacy fallback removed here)
            
            # Generate Adjacent Area buffer around the merged WGS 84 CV.
            # We project cv_merged to the UTM zone of the route's midpoint, buffer it there, and project back.
            aga_merged = QgsGeometry()
            try:
                lons = [w[0] for w in parsed_wpts]
                lats = [w[1] for w in parsed_wpts]
                mid_lon = sum(lons) / len(lons)
                mid_lat = sum(lats) / len(lats)
                
                utm_epsg_mid = get_utm_epsg(mid_lon, mid_lat)
                dest_crs_mid = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg_mid}")
                
                transform_mid = QgsCoordinateTransform(src_crs, dest_crs_mid, project)
                inverse_transform_mid = QgsCoordinateTransform(dest_crs_mid, src_crs, project)
                
                # Clone cv_merged for adjacent area buffering in local UTM
                cv_clone = QgsGeometry(cv_merged)
                cv_clone.transform(transform_mid)
                aga_merged = cv_clone.buffer(s_aga, BUFFER_SEGMENTS)
                aga_merged.transform(inverse_transform_mid)
            except Exception as e:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage(f"Fehler bei Adjacent-Area-Berechnung: {e}", "QUCORE", Qgis.MessageLevel.Warning)
            
            # Enforce validity of final output geometries
            if fg_merged and not fg_merged.isGeosValid():
                fg_merged = fg_merged.makeValid()
            if cv_merged and not cv_merged.isGeosValid():
                cv_merged = cv_merged.makeValid()
            if grb_merged and not grb_merged.isGeosValid():
                grb_merged = grb_merged.makeValid()
            if aga_merged and not aga_merged.isGeosValid():
                aga_merged = aga_merged.makeValid()
            
            return fg_merged, cv_merged, grb_merged, aga_merged
