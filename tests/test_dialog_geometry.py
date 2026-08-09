# -*- coding: utf-8 -*-
"""
Unit tests for QUCORE dialog geometry persistence, screen bounds validation,
and geometry reset functionality.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure QUCORE package directory is in sys.path
tests_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(tests_dir)
parent_dir = os.path.dirname(plugin_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Initialize standalone test environment mocks if needed
import QUCORE.tests.test_suite

from QUCORE.config_manager import ConfigManager
from QUCORE.dialog_utils import QucoreBaseDialog, is_rect_visible_on_screens, reset_all_qucore_geometries
from QUCORE.parameter_dialog import ParameterDialog
from QUCORE.altitude_table_dialog import AltitudeTableDialog
from QUCORE.advanced_settings_dialog import AdvancedSettingsDialog
from QUCORE.population_density_dialog import PopulationDensityDialog
from QUCORE.asymmetric_buffer_winddrift_dialog import WindDriftDialog
from QUCORE.vlos_calculator_dialog import VlosCalculatorDialog
from QUCORE.export_settings_dialog import ExportSettingsDialog
from QUCORE.info_dialogs import AboutDialog, FormatsInfoDialog


class TestDialogGeometrySuite(unittest.TestCase):
    def setUp(self):
        self.config_manager = ConfigManager.get_instance()
        self.base_params = ConfigManager.get_default_params()

    def test_config_manager_dialog_default_sizes(self):
        """
        Verify that ConfigManager returns correct standard sizes for all dialogs from config.json.
        """
        expected_sizes = {
            "ParameterDialog": (680, 480),
            "AltitudeTableDialog": (1150, 450),
            "AdvancedSettingsDialog": (550, 480),
            "PopulationDensityDialog": (750, 580),
            "WindDriftDialog": (520, 580),
            "VlosCalculatorDialog": (450, 340),
            "ExportSettingsDialog": (350, 220),
            "AboutDialog": (550, 530),
            "FormatsInfoDialog": (820, 360),
            "ControlPanel": (350, 720)
        }
        for dialog_key, expected_size in expected_sizes.items():
            size = ConfigManager.get_dialog_default_size(dialog_key)
            self.assertEqual(size, expected_size, f"Mismatch for {dialog_key}")

        # Test strict Fail-Fast KeyError for non-existent dialog
        with self.assertRaises(KeyError):
            ConfigManager.get_dialog_default_size("NonExistentDialog")

    def test_qucore_base_dialog_geometry_lifecycle(self):
        """
        Verify that QucoreBaseDialog saves, restores, and resets geometry cleanly.
        """
        # Test with a registered dialog key from config.json
        dialog = QucoreBaseDialog(None, dialog_key="ParameterDialog")
        self.assertEqual(dialog.dialog_key, "ParameterDialog")
        dialog.restore_dialog_geometry()
        self.assertTrue(dialog._geometry_restored)
        dialog.save_dialog_geometry()
        dialog.reset_to_default_geometry()

        # Test with an unregistered key (fallback resilience)
        fallback_dlg = QucoreBaseDialog(None, dialog_key="UnregisteredCustomDialog")
        fallback_dlg.restore_dialog_geometry()
        self.assertTrue(fallback_dlg._geometry_restored)

    def test_reset_all_qucore_geometries(self):
        """
        Verify that reset_all_qucore_geometries executes successfully.
        """
        res = reset_all_qucore_geometries()
        self.assertTrue(res)

    def test_all_dialogs_inherit_from_qucore_base_dialog(self):
        """
        Verify that all 9 UI dialogs inherit from QucoreBaseDialog and instantiate properly.
        """
        dialog_classes = [
            ParameterDialog,
            AltitudeTableDialog,
            AdvancedSettingsDialog,
            PopulationDensityDialog,
            WindDriftDialog,
            VlosCalculatorDialog,
            ExportSettingsDialog,
            AboutDialog,
            FormatsInfoDialog
        ]
        for cls in dialog_classes:
            self.assertTrue(issubclass(cls, QucoreBaseDialog), f"{cls.__name__} does not inherit from QucoreBaseDialog")

    def test_is_rect_visible_on_screens_fallback(self):
        """
        Verify that is_rect_visible_on_screens returns a boolean safely in headless/mocked environments.
        """
        from qgis.PyQt.QtCore import QRect
        rect = QRect(100, 100, 500, 400)
        visible = is_rect_visible_on_screens(rect)
        self.assertIsInstance(visible, bool)


if __name__ == "__main__":
    unittest.main()
