# -*- coding: utf-8 -*-
from ..config_manager import ConfigManager
from ..translation_manager import TranslationManager

def tr(key, default=""):
    try:
        lang = ConfigManager.get_default("language")
    except KeyError:
        lang = "de"
    return TranslationManager.tr(key, lang, default)

DEFAULT_ALTITUDE = 100.0
DEFAULT_SPEED = 30.0
DEFAULT_WIDTH = 50.0
FEET_TO_METERS = 3.28084

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

def find_local_elements(parent, local_name):
    results = []
    def recurse(node):
        if node.isElement():
            elem = node.toElement()
            tag = elem.tagName()
            if ":" in tag:
                tag = tag.split(":", 1)[1]
            if tag == local_name:
                results.append(elem)
        child = node.firstChild()
        while not child.isNull():
            recurse(child)
            child = child.nextSibling()
    recurse(parent)
    return results

def find_first_local_element(parent, local_name):
    def recurse(node):
        if node.isElement():
            elem = node.toElement()
            tag = elem.tagName()
            if ":" in tag:
                tag = tag.split(":", 1)[1]
            if tag == local_name:
                return elem
        child = node.firstChild()
        while not child.isNull():
            res = recurse(child)
            if res is not None:
                return res
            child = child.nextSibling()
        return None
    return recurse(parent)
