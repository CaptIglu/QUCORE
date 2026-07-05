# -*- coding: utf-8 -*-
from qgis.core import QgsPointXY
from .config_manager import ConfigManager
from .translation_manager import TranslationManager

from .formats.dipul_handler import DipulHandler
from .formats.kml_handler import KmlHandler
from .formats.flightplan_handler import FlightplanHandler
from .formats.geojson_handler import GeoJsonHandler
from .formats.ardupilot_handler import ArduPilotHandler

def tr(key, default=""):
    try:
        lang = ConfigManager.get_default("language")
    except KeyError:
        lang = "de"
    return TranslationManager.tr(key, lang, default)

class ImporterExporter:
    @staticmethod
    def import_dipul(file_path):
        return DipulHandler.import_dipul(file_path)

    @staticmethod
    def export_dipul(file_path, waypoints, pilot_pos, const_height, const_speed, params, geometry_type="Corridor"):
        return DipulHandler.export_dipul(file_path, waypoints, pilot_pos, const_height, const_speed, params, geometry_type)

    @staticmethod
    def import_kml(file_path):
        return KmlHandler.import_kml(file_path)

    @staticmethod
    def export_kml(file_path, waypoints, pilot_pos, params, geometry_type="Corridor"):
        return KmlHandler.export_kml(file_path, waypoints, pilot_pos, params, geometry_type)

    @staticmethod
    def import_flightplan(file_path):
        return FlightplanHandler.import_flightplan(file_path)

    @staticmethod
    def export_flightplan(file_path, waypoints, const_height):
        return FlightplanHandler.export_flightplan(file_path, waypoints, const_height)

    @staticmethod
    def import_geojson(file_path):
        return GeoJsonHandler.import_geojson(file_path)

    @staticmethod
    def export_geojson(file_path, waypoints, pilot_pos, params, geometry_type="Corridor"):
        return GeoJsonHandler.export_geojson(file_path, waypoints, pilot_pos, params, geometry_type)

    @staticmethod
    def import_waypoints(file_path):
        return ArduPilotHandler.import_waypoints(file_path)

    @staticmethod
    def import_plan(file_path):
        return ArduPilotHandler.import_plan(file_path)

    @staticmethod
    def export_plan(file_path, waypoints, pilot_pos, params, geometry_type="Corridor", geofence_type="FG", resolution=8, mp_compat=True):
        return ArduPilotHandler.export_plan(file_path, waypoints, pilot_pos, params, geometry_type, geofence_type, resolution, mp_compat)

    @staticmethod
    def export_waypoints(file_path, waypoints, pilot_pos, params, geometry_type="Corridor", export_mission=True, export_fence=True, geofence_type="FG", resolution=8, mp_compat=True):
        return ArduPilotHandler.export_waypoints(file_path, waypoints, pilot_pos, params, geometry_type, export_mission, export_fence, geofence_type, resolution, mp_compat)
