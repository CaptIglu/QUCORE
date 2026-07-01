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
    _schema = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_configs()
        return cls._instance

    def _load_configs(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(plugin_dir, "config.json")
        limits_path = os.path.join(plugin_dir, "config_limits.json")
        schema_path = os.path.join(plugin_dir, "config.schema.json")

        # Load schema
        if os.path.exists(schema_path):
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    self._schema = json.load(f)
            except Exception as e:
                QgsMessageLog.logMessage(f"Fehler beim Laden von config.schema.json: {e}", "QUCORE_Config", Qgis.Warning)

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
    def get_default_params(cls):
        """
        Returns a copy of all default parameters.
        """
        inst = cls.get_instance()
        return inst._defaults.copy()

    @classmethod
    def get_limits(cls):
        """
        Returns a copy of all configuration limits.
        """
        inst = cls.get_instance()
        return inst._limits.copy()

    @classmethod
    def get_limit(cls, key):
        """
        Gibt die Limits für einen Parameter aus config_limits.json zurück.
        Wirft einen strikten Fehler, wenn der Parameter komplett fehlt.
        """
        inst = cls.get_instance()
        if key in inst._limits:
            return inst._limits[key]
            
        raise KeyError(f"Limits für '{key}' fehlen in config_limits.json. Dies ist nicht erlaubt.")

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

    @classmethod
    def sanitize_imported_state(cls, state):
        """
        Sanitizes a deserialized planning state dict before it is applied.
        Returns a tuple: (sanitized_state, list_of_warnings)
        """
        inst = cls.get_instance()
        warnings = []
        sanitized_state = {}
        
        # 1. Geometry Type
        geom_type = state.get("geometry_type", "Corridor")
        allowed_geom_types = ["Corridor", "Circle", "Polygon"]
        if geom_type not in allowed_geom_types:
            warnings.append(f"Ungültiger geometry_type '{geom_type}', setze auf 'Corridor'.")
            geom_type = "Corridor"
        sanitized_state["geometry_type"] = geom_type
        
        # 2. Pilot Pos
        pilot_pos = state.get("pilot_pos")
        if pilot_pos is not None:
            if isinstance(pilot_pos, list) and len(pilot_pos) >= 2 and all(isinstance(x, (int, float)) for x in pilot_pos[:2]):
                sanitized_state["pilot_pos"] = [float(pilot_pos[0]), float(pilot_pos[1])]
            else:
                warnings.append("Ungültiges Format für pilot_pos, verwerfe Pilot-Position.")
                sanitized_state["pilot_pos"] = None
        else:
            sanitized_state["pilot_pos"] = None
            
        # 3. Waypoints
        waypoints = state.get("waypoints", [])
        sanitized_waypoints = []
        if isinstance(waypoints, list):
            for i, wp in enumerate(waypoints):
                if isinstance(wp, (list, tuple)) and len(wp) >= 3:
                    if all(isinstance(x, (int, float)) for x in wp):
                        sanitized_waypoints.append(list(wp))
                    else:
                        warnings.append(f"Wegpunkt {i} enthält nicht-numerische Werte, übersprungen.")
                else:
                    warnings.append(f"Ungültiges Format für Wegpunkt {i}, übersprungen.")
        else:
            warnings.append("waypoints ist keine Liste, verwerfe alle Wegpunkte.")
        sanitized_state["waypoints"] = sanitized_waypoints
        
        # 4. Params
        params = state.get("params", {})
        sanitized_params = {}
        
        if not isinstance(params, dict):
            warnings.append("params ist kein Dictionary, setze leere Parameter.")
            params = {}
            
        schema_props = inst._schema.get("properties", {})
        
        # Pre-mapping for legacy keys
        if "maxVelocity" in params and "maxOpsSpeedV0" not in params:
            params["maxOpsSpeedV0"] = params["maxVelocity"]
        
        for k, v in params.items():
            if k not in schema_props:
                # Log but silently drop
                warnings.append(f"Unbekannter Parameter '{k}' wurde verworfen.")
                continue
                
            prop_def = schema_props[k]
            expected_type = prop_def.get("type")
            
            # Type checking
            valid = True
            if expected_type == "number" or expected_type == "integer":
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    warnings.append(f"Parameter '{k}' sollte numerisch sein, ist aber '{type(v).__name__}'. Verworfen.")
                    valid = False
                else:
                    # Clamp using limits
                    if k in inst._limits:
                        limits = inst._limits[k]
                        min_val = limits.get("min")
                        max_val = limits.get("max")
                        
                        if min_val is not None and v < min_val:
                            warnings.append(f"Parameter '{k}' ({v}) ist unter dem Minimum ({min_val}). Gekappt.")
                            v = float(min_val)
                        if max_val is not None and v > max_val:
                            warnings.append(f"Parameter '{k}' ({v}) ist über dem Maximum ({max_val}). Gekappt.")
                            v = float(max_val)
            elif expected_type == "boolean":
                if not isinstance(v, bool):
                    warnings.append(f"Parameter '{k}' sollte boolesch sein, ist aber '{type(v).__name__}'. Verworfen.")
                    valid = False
            elif expected_type == "string":
                if not isinstance(v, str):
                    warnings.append(f"Parameter '{k}' sollte ein String sein, ist aber '{type(v).__name__}'. Verworfen.")
                    valid = False
                else:
                    enum_vals = prop_def.get("enum")
                    if enum_vals and v not in enum_vals:
                        warnings.append(f"Parameter '{k}' hat einen ungültigen Wert '{v}'. Verworfen.")
                        valid = False
                        
            if valid:
                sanitized_params[k] = v
                
        sanitized_state["params"] = sanitized_params
        
        for w in warnings:
            QgsMessageLog.logMessage(f"Sanitization Warning: {w}", "QUCORE_Import", Qgis.Warning)
            
        return sanitized_state, warnings

