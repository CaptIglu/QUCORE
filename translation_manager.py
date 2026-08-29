# -*- coding: utf-8 -*-
import os
import json
from qgis.core import QgsMessageLog, Qgis

class TranslationManager:
    """
    Centralized Translation Manager for QUCORE.
    Loads translations.json exactly once into memory.
    """
    _instance = None
    _translations = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranslationManager, cls).__new__(cls)
            cls._instance._load_translations()
        return cls._instance

    def _load_translations(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        tr_path = os.path.join(plugin_dir, "translations.json")

        if os.path.exists(tr_path):
            try:
                with open(tr_path, 'r', encoding='utf-8') as f:
                    self._translations = json.load(f)
            except Exception as e:
                import traceback
                QgsMessageLog.logMessage(f"Fehler beim Laden von translations.json: {e}\n{traceback.format_exc()}", "QUCORE_Translation", Qgis.MessageLevel.Warning)
        else:
            QgsMessageLog.logMessage("Warnung: translations.json nicht gefunden!", "QUCORE_Translation", Qgis.MessageLevel.Warning)

    @classmethod
    def get_instance(cls):
        return cls()

    @classmethod
    def tr(cls, key, lang="de", default=""):
        inst = cls.get_instance()
        return inst._translations.get(key, {}).get(lang, default)
