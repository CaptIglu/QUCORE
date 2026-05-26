# -*- coding: utf-8 -*-

def classFactory(iface):
    """
    QGIS plugin entry point called by the QGIS plugin manager.
    Loads the main plugin orchestrator class.
    """
    from .plugin import DroneCorridorPlanner
    return DroneCorridorPlanner(iface)
