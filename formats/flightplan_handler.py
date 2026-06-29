# -*- coding: utf-8 -*-
import json
import uuid
import math
from qgis.core import QgsPointXY, QgsMessageLog, Qgis, QgsGeometry
from ..config_manager import ConfigManager
from ..buffer_calculator import BufferCalculator
from .utils import unpack_waypoint, tr, find_local_elements, find_first_local_element

class FlightplanHandler:
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
        
        # Use extracted functions from utils.py

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

