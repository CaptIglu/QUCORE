# -*- coding: utf-8 -*-
import os
import json
from qgis.core import QgsMessageLog, Qgis

class ConfigManager:
    """
    Centralized Configuration Manager for QUCORE.
    Acts as the single source of truth for all parameters, eliminating hardcoded defaults.
    Loads config.json and config_limits.json exactly once into memory.
    """
    _instance = None
    _defaults = {}
    _limits = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_configs()
        return cls._instance

    def _load_configs(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(plugin_dir, "config.json")
        limits_path = os.path.join(plugin_dir, "config_limits.json")

        # Load limits first so we can use them to clamp defaults if necessary
        if os.path.exists(limits_path):
            try:
                with open(limits_path, 'r', encoding='utf-8') as f:
                    self._limits = json.load(f)
            except Exception as e:
                QgsMessageLog.logMessage(f"Fehler beim Laden von config_limits.json: {e}", "QUCORE_Config", Qgis.Warning)

        # Load main config
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._defaults = json.load(f)
            except Exception as e:
                QgsMessageLog.logMessage(f"Fehler beim Laden von config.json: {e}", "QUCORE_Config", Qgis.Warning)
        else:
            QgsMessageLog.logMessage("Kritischer Fehler: config.json nicht gefunden!", "QUCORE_Config", Qgis.Critical)
            raise FileNotFoundError("config.json fehlt. Die Konfiguration kann nicht geladen werden.")

    @classmethod
    def get_instance(cls):
        return cls()

    @classmethod
    def get_default(cls, key):
        """
        Retrieves the strict default value for a parameter straight from config.json.
        Raises an error if the key is completely missing to enforce Fail-Fast.
        """
        inst = cls.get_instance()
        if key in inst._defaults:
            return inst._defaults[key]
        
        # Legacy mapping fallback for strictly equivalent keys if the new key is missing in config
        legacy_map = {
            "maxOpsSpeedV0": "maxVelocity",
            "maxCommandableSpeedVmax": "maxVelocity"
        }
        if key in legacy_map and legacy_map[key] in inst._defaults:
            return inst._defaults[legacy_map[key]]

        raise KeyError(f"Parameter '{key}' fehlt in config.json. Dies ist nicht erlaubt.")

    @classmethod
    def get_param(cls, params_dict, key):
        """
        Retrieves a parameter from the provided params_dict. 
        If missing, falls back to get_default(key).
        Automatically clamps the value if limits are defined in config_limits.json.
        """
        inst = cls.get_instance()
        
        # 1. Retrieve the raw value
        if key in params_dict:
            val = params_dict[key]
        else:
            # Handle legacy keys in params_dict before falling back to default
            if key == "maxOpsSpeedV0" and "maxVelocity" in params_dict:
                val = params_dict["maxVelocity"]
            elif key == "maxCommandableSpeedVmax":
                val = params_dict.get("maxVelocityVmax", params_dict.get("maxCommandSpeedVmax", params_dict.get("maxOpsSpeedV0", params_dict.get("maxVelocity"))))
                if val is None:
                    val = cls.get_default(key)
            else:
                val = cls.get_default(key)

        # 2. Clamp the value if it's numeric and has limits
        if key in inst._limits and isinstance(val, (int, float)):
            limits = inst._limits[key]
            min_val = limits.get("min")
            max_val = limits.get("max")
            
            if min_val is not None:
                val = max(float(min_val), float(val))
            if max_val is not None:
                val = min(float(max_val), float(val))
                
        return val
