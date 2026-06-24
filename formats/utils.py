# -*- coding: utf-8 -*-
from ..config_manager import ConfigManager

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
