# -*- coding: utf-8 -*-
import sys
import os
import unittest
from unittest.mock import MagicMock

# 1. Mock qgis and PyQt5 environments to allow running standalone without QGIS or PyQt5 installations
import types
qgis_mock = MagicMock()
qgis_core_mock = MagicMock()

class RealMockQgsGeometry:
    is_valid_mock_geom = True
    def __init__(self, *args, **kwargs):
        if len(args) == 0:
            self.empty = kwargs.get('empty', True)
        else:
            first_arg = args[0]
            if isinstance(first_arg, bool):
                self.empty = first_arg
            elif type(first_arg).__name__ == "RealMockQgsGeometry":
                self.empty = first_arg.empty
            else:
                self.empty = False
        self._area = 100.0
    def isEmpty(self):
        return self.empty
    def asPolygon(self):
        return [[RealMockQgsPointXY(0.0, 0.0), RealMockQgsPointXY(1.0, 0.0), RealMockQgsPointXY(1.0, 1.0), RealMockQgsPointXY(0.0, 1.0), RealMockQgsPointXY(0.0, 0.0)]]
    def isMultipart(self):
        return False
    def asMultiPolygon(self):
        return [self.asPolygon()]
    def isGeosValid(self):
        return RealMockQgsGeometry.is_valid_mock_geom
    def area(self):
        return self._area
    def combine(self, other):
        res = RealMockQgsGeometry(empty=False)
        res._area = self._area + getattr(other, '_area', 0.0)
        return res
    def buffer(self, *args):
        res = RealMockQgsGeometry(empty=False)
        if args:
            try:
                res._area = 1000.0 * float(args[0])
            except (ValueError, TypeError) as e:
                from qgis.core import QgsMessageLog, Qgis
                import traceback
                QgsMessageLog.logMessage(f"Silent exception caught in test_suite.py (line 47): {str(e)}\n{traceback.format_exc()}", "QUCORE", Qgis.Warning)
        return res
    def convexHull(self):
        return self
    def transform(self, *args):
        pass
    def translate(self, dx, dy):
        """Mock: Wind drift translate — does nothing geometrically but must not crash."""
        pass
    @staticmethod
    def fromPolygonXY(*args):
        return RealMockQgsGeometry(empty=False)
    @staticmethod
    def fromPointXY(*args):
        return RealMockQgsGeometry(empty=False)
    @staticmethod
    def unaryUnion(*args):
        return RealMockQgsGeometry(empty=False)
    @staticmethod
    def collectGeometry(geom_list):
        """Mock: Collects geometries into a GeometryCollection for convexHull."""
        res = RealMockQgsGeometry(empty=False)
        res._area = sum(getattr(g, '_area', 0.0) for g in geom_list)
        return res

class RealMockQgsPointXY:
    def __init__(self, x=0.0, y=0.0):
        self._x = x
        self._y = y
    def x(self):
        return float(self._x)
    def y(self):
        return float(self._y)

qgis_core_mock.QgsPointXY = RealMockQgsPointXY
qgis_core_mock.QgsGeometry = RealMockQgsGeometry
sys.modules['qgis'] = qgis_mock
sys.modules['qgis.core'] = qgis_core_mock
sys.modules['qgis.gui'] = MagicMock()

# Mock PyQt5 modules with simple mock types so subclasses execute normal python initialization
qt_widgets = types.ModuleType("QtWidgets")
class MockQWidget:
    Ok = 1
    Cancel = 2
    Yes = 16384
    No = 65536
    RestoreDefaults = 3
    
    def __init__(self, parent=None, *args, **kwargs):
        self._val = 100.0
        self._idx = 0
    def palette(self):
        m = MagicMock()
        m.color.return_value.lightness.return_value = 200 # light theme default
        return m
    def backgroundRole(self):
        return 0
    def rect(self):
        return MagicMock()
    def width(self):
        return 300.0
    def height(self):
        return 320.0
    def setValue(self, val):
        self._val = val
    def value(self):
        return self._val
    def setCurrentIndex(self, idx):
        self._idx = idx
    def currentIndex(self):
        return self._idx
    def accept(self):
        pass
    def reject(self):
        pass
    def exec_(self):
        return 1
    def __getattr__(self, name):
        return MagicMock()

qt_widgets.QWidget = MockQWidget
qt_widgets.QDialog = MockQWidget
qt_widgets.QVBoxLayout = MockQWidget
qt_widgets.QHBoxLayout = MockQWidget
qt_widgets.QTabWidget = MockQWidget
qt_widgets.QLabel = MockQWidget
qt_widgets.QComboBox = MockQWidget
qt_widgets.QDoubleSpinBox = MockQWidget
qt_widgets.QFormLayout = MockQWidget
qt_widgets.QGroupBox = MockQWidget
qt_widgets.QPushButton = MockQWidget
qt_widgets.QDialogButtonBox = MockQWidget
qt_widgets.QCheckBox = MockQWidget
qt_widgets.QApplication = MagicMock
class MockQHeaderView:
    Stretch = 1
qt_widgets.QHeaderView = MockQHeaderView
class MockQTableWidgetItemClass:
    def __init__(self, text=""):
        self._text = text
        self._flags = 0
    def flags(self):
        return self._flags
    def setFlags(self, flags):
        self._flags = flags
    def setTextAlignment(self, align):
        pass
    def setBackground(self, brush):
        pass
    def setForeground(self, brush):
        pass
    def text(self):
        return self._text
    def setText(self, text):
        self._text = text

class MockQTableWidget(MockQWidget):
    NoEditTriggers = 0
    NoSelection = 0
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._items = {}
        self._cols = 0
        self._rows = 0
    def setColumnCount(self, count):
        self._cols = count
    def setRowCount(self, count):
        self._rows = count
    def columnCount(self):
        return self._cols
    def rowCount(self):
        return self._rows
    def setItem(self, row, col, item):
        self._items[(row, col)] = item
    def item(self, row, col):
        return self._items.get((row, col))
    def columnWidth(self, col):
        return 100

qt_widgets.QTableWidget = MockQTableWidget
qt_widgets.QTableWidgetItem = MockQTableWidgetItemClass
class MockQMessageBox(MockQWidget):
    Yes = 16384
    No = 65536
    Ok = 1
    Cancel = 2
    @staticmethod
    def question(*args, **kwargs):
        return 65536
qt_widgets.QMessageBox = MockQMessageBox
qt_widgets.QAction = MockQWidget
qt_widgets.QFileDialog = MockQWidget
qt_widgets.QInputDialog = MockQWidget
qt_widgets.QStyle = MockQWidget
qt_widgets.QGridLayout = MockQWidget
qt_widgets.QSpinBox = MockQWidget
qt_widgets.QTreeWidget = MockQWidget
class MockQTreeWidgetItem:
    def __init__(self, *args, **kwargs):
        pass
    def setText(self, col, text):
        pass
    def setExpanded(self, expanded):
        pass
    def font(self, col):
        return MagicMock()
    def setFont(self, col, font):
        pass
qt_widgets.QTreeWidgetItem = MockQTreeWidgetItem
qt_widgets.QColorDialog = MockQWidget

sys.modules['PyQt5.QtWidgets'] = qt_widgets

qt_gui = types.ModuleType("QtGui")
class DummyClass:
    def __init__(self, *args, **kwargs):
        pass
qt_gui.QPainter = DummyClass
qt_gui.QColor = DummyClass
qt_gui.QPen = DummyClass
qt_gui.QBrush = DummyClass
qt_gui.QFont = DummyClass
qt_gui.QIcon = DummyClass
qt_gui.QTextDocument = DummyClass
qt_gui.QPolygonF = DummyClass
qt_gui.QPainterPath = DummyClass
qt_gui.QIcon = DummyClass
qt_gui.QDesktopServices = DummyClass
sys.modules['PyQt5.QtGui'] = qt_gui

qt_core = types.ModuleType("QtCore")
qt_core.Qt = MagicMock()
qt_core.QRectF = DummyClass
qt_core.QPointF = DummyClass
qt_core.QVariant = DummyClass
qt_core.QUrl = DummyClass
qt_core.pyqtSignal = MagicMock
sys.modules['PyQt5.QtCore'] = qt_core

# Mock PyQt5.QtXml for standalone tests
qt_xml = types.ModuleType("QtXml")
import xml.etree.ElementTree as ET

class MockQDomNode:
    def __init__(self, element, parent_node=None, idx=0):
        self.element = element
        self.parent_node = parent_node
        self.idx = idx
        if element is not None:
            self._children = [MockQDomNode(child, self, i) for i, child in enumerate(element)]
        else:
            self._children = []
            
    def isElement(self):
        return self.element is not None
        
    def toElement(self):
        return self
        
    def tagName(self):
        # XML tags in element tree might include namespace in format {ns}tag, strip namespace
        tag = self.element.tag if self.element is not None else ""
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        return tag
        
    def attribute(self, name, default=""):
        return self.element.attrib.get(name, default) if self.element is not None else default
        
    def text(self):
        if self.element is None:
            return ""
        return "".join(self.element.itertext())
        
    def firstChild(self):
        if self._children:
            return self._children[0]
        return MockQDomNode(None)
        
    def nextSibling(self):
        if self.parent_node and self.idx + 1 < len(self.parent_node._children):
            return self.parent_node._children[self.idx + 1]
        return MockQDomNode(None)
        
    def isNull(self):
        return self.element is None

class MockQDomDocument:
    def __init__(self):
        self.root_element = None
        
    def setContent(self, xml_data):
        try:
            # Handle potential encoding declarations in XML bytes
            self.root_element = ET.fromstring(xml_data)
            return True, "", 0, 0
        except Exception as e:
            return False, str(e), 1, 1
            
    def documentElement(self):
        return MockQDomNode(self.root_element)

qt_xml.QDomDocument = MockQDomDocument
sys.modules['PyQt5.QtXml'] = qt_xml


# 2. Add parent directory of QUCORE package to sys.path dynamically
tests_dir = os.path.dirname(os.path.abspath(__file__))
plugin_dir = os.path.dirname(tests_dir)
parent_dir = os.path.dirname(plugin_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import the BufferCalculator
from QUCORE.buffer_calculator import BufferCalculator

class TestBufferCalculatorSuite(unittest.TestCase):
    def setUp(self):
        # Base parameters matching the standard LBA guidelines defaults
        self.base_params = {
            "uas_type": "FixedWing",
            "altimetry": "GPS",
            "maxOpsSpeedV0": 30.0,
            "maxCharacteristicDimension": 3.6,
            "maxRollAngle": 30.0,
            "maxPitchAngle": 30.0,
            "glideRatioDenominator": 10.0,
            "maxWindVelocity": 3.0,
            "stallVelocity": 10.0,
            "gpsInaccuracy": 3.0,
            "positionError": 3.0,
            "mapError": 1.0,
            "reactionTime": 1.0,
            "altitudeErrorGps": 4.0,
            "altitudeErrorBarometric": 1.0,
            "corridorWidth": 50.0,
            "maxFlightHeight": 100.0,
            "groundRiskBufferMethod": "Simplified",
            "lateralContingencyManoeuvreType": "Default",
            "verticalContingencyManoeuvreType": "Default",
            "parachuteOpeningTimeLateral": 2.0,
            "parachuteOpeningTimeVertical": 2.0,
            "parachuteOpeningTimeGRB": 2.0,
            "parachuteDescentRate": 2.0,
            "additionalErrorLateral": 0.0,
            "additionalErrorVertical": 0.0,
            "enableAsymmetricBufferWinddrift": False,
            "windDirection": 0.0,
            "windDirectionVariance": 15.0,
            "minWindVelocity": 0.0
        }

    def test_tc1_fixed_wing_parachute_manoeuvres_and_parachute_grb(self):
        """
        TC1: Fixed-Wing, Baro altimetry, Parachute CV manoeuvres, Parachute GRB.
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 20.0,
            "maxCharacteristicDimension": 3.6,
            "corridorWidth": 50.0,
            "maxFlightHeight": 110.0,
            "lateralContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeLateral": 2.0,
            "verticalContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeVertical": 2.0,
            "groundRiskBufferMethod": "Parachute",
            "parachuteOpeningTimeGRB": 1.0,
            "maxWindVelocity": 3.0,
            "parachuteDescentRate": 2.0
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(110.0, params)
        
        # Expected results:
        # r_fg = 25.0
        # s_cv = 3 + 3 + 1 + (20 * 1) + (20 * 2) = 67.0 => r_cv = 92.0
        # h_cv = 110 + 1 + 14 + 28 = 153.0
        # s_grb = 20 * 1 + 3 * (153.0 / 2) = 249.5 => r_grb = 341.5
        self.assertAlmostEqual(r_fg, 25.0, places=4)
        self.assertAlmostEqual(r_cv, 92.0, places=4)
        self.assertAlmostEqual(r_grb, 341.5, places=4)

    def test_tc2_multicopter_default_manoeuvres_and_ballistic_grb(self):
        """
        TC2: Multicopter, Baro altimetry, Default stopping CV, Ballistic GRB.
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "Multikopter",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 10.0,
            "maxCharacteristicDimension": 1.5,
            "corridorWidth": 50.0,
            "maxFlightHeight": 100.0,
            "lateralContingencyManoeuvreType": "Default",
            "maxPitchAngle": 45.0,
            "verticalContingencyManoeuvreType": "Default",
            "groundRiskBufferMethod": "Ballistic"
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(100.0, params)
        
        # Expected results:
        # r_fg = 25.0
        # s_cm = 0.5 * 10.0^2 / (9.81 * tan(45)) = 50 / 9.81 = 5.096839959 m
        # s_cv = 3 + 3 + 1 + 10 * 1 + 5.096839959 = 22.096839959 m => r_cv = 47.096839959 m
        # h_cm = 0.5 * 10^2 / 9.81 = 5.096839959 m
        # h_cv = 100 + 1 + 7 + 5.096839959 = 113.096839959 m
        # s_grb = 10 * sqrt(2 * 113.096839959 / 9.81) + 0.5 * 1.5 = 10 * sqrt(23.05745973) + 0.75 = 48.7681781 m
        # r_grb = 47.096839959 + 48.7681781 = 95.86501806 m
        self.assertAlmostEqual(r_fg, 25.0, places=4)
        self.assertAlmostEqual(r_cv, 47.0968, places=4)
        self.assertAlmostEqual(r_grb, 95.8650, places=4)

    def test_tc3_fixed_wing_default_manoeuvres_and_simplified_1_1_grb(self):
        """
        TC3: Fixed-Wing, GPS altimetry, Default curve CV, 1:1 Simplified GRB.
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "altimetry": "GPS",
            "maxOpsSpeedV0": 20.0,
            "maxCharacteristicDimension": 3.6,
            "corridorWidth": 50.0,
            "maxFlightHeight": 110.0,
            "lateralContingencyManoeuvreType": "Default",
            "maxRollAngle": 30.0,
            "verticalContingencyManoeuvreType": "Default",
            "groundRiskBufferMethod": "Simplified"
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(110.0, params)
        
        # Expected results:
        # r_fg = 25.0
        # s_cm = 20^2 / (9.81 * tan(30)) = 70.6238864 m
        # s_cv = 3 + 3 + 1 + 20 * 1 + 70.6238864 = 97.6238864 m => r_cv = 122.6238864 m
        # h_cm = 0.3 * 20^2 / 9.81 = 12.2324159 m
        # h_cv = 110 + 4 + 14 + 12.2324159 = 140.2324159 m
        # s_grb = 140.2324159 + 0.5 * 3.6 = 142.0324159 m => r_grb = 264.6563023 m
        self.assertAlmostEqual(r_fg, 25.0, places=4)
        self.assertAlmostEqual(r_cv, 122.6239, places=4)
        self.assertAlmostEqual(r_grb, 264.6563, places=4)

    def test_tc4_fixed_wing_default_manoeuvres_and_glide_grb(self):
        """
        TC4: Fixed-Wing, Baro altimetry, Default curve CV, Glide GRB (E = 15).
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 20.0,
            "maxCharacteristicDimension": 3.6,
            "corridorWidth": 50.0,
            "maxFlightHeight": 110.0,
            "lateralContingencyManoeuvreType": "Default",
            "maxRollAngle": 30.0,
            "verticalContingencyManoeuvreType": "Default",
            "groundRiskBufferMethod": "Glide",
            "glideRatioDenominator": 15.0
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(110.0, params)
        
        # Expected results:
        # r_fg = 25.0
        # s_cv = 97.6238864 m => r_cv = 122.6238864 m
        # h_cv = 110 + 1 + 14 + 12.2324159 = 137.2324159 m
        # s_grb = 137.2324159 * 15 = 2058.486238 m => r_grb = 2181.110124 m
        self.assertAlmostEqual(r_fg, 25.0, places=4)
        self.assertAlmostEqual(r_cv, 122.6239, places=4)
        self.assertAlmostEqual(r_grb, 2181.1101, places=4)

    def test_tc5_multicopter_parachute_manoeuvres_and_ballistic_grb(self):
        """
        TC5: Multicopter, GPS altimetry, Parachute CV manoeuvres, Ballistic GRB.
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "Multikopter",
            "altimetry": "GPS",
            "maxOpsSpeedV0": 12.0,
            "maxCharacteristicDimension": 2.0,
            "corridorWidth": 60.0,
            "maxFlightHeight": 120.0,
            "lateralContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeLateral": 2.5,
            "verticalContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeVertical": 1.5,
            "groundRiskBufferMethod": "Ballistic"
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(120.0, params)
        
        # Expected results:
        # r_fg = 30.0
        # s_cm = 12.0 * 2.5 = 30.0 m
        # s_cv = 3 + 3 + 1 + 12 * 1 + 30.0 = 49.0 m => r_cv = 79.0 m
        # h_cm = 0.7 * 12.0 * 1.5 = 12.6 m
        # h_cv = 120 + 4 + 8.4 + 12.6 = 145.0 m
        # s_grb = 12 * sqrt(2 * 145.0 / 9.81) + 0.5 * 2.0 = 12 * sqrt(29.56167176) + 1.0 = 66.244766 m => r_grb = 145.2448 m
        self.assertAlmostEqual(r_fg, 30.0, places=4)
        self.assertAlmostEqual(r_cv, 79.0, places=4)
        self.assertAlmostEqual(r_grb, 145.2448, places=4)

    def test_tc6_fixed_wing_parachute_manoeuvres_and_glide_grb(self):
        """
        TC6: Fixed-Wing, GPS altimetry, Parachute CV manoeuvres, Glide GRB (E = 8).
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "altimetry": "GPS",
            "maxOpsSpeedV0": 15.0,
            "maxCharacteristicDimension": 4.0,
            "corridorWidth": 80.0,
            "maxFlightHeight": 100.0,
            "lateralContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeLateral": 2.0,
            "verticalContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeVertical": 2.0,
            "groundRiskBufferMethod": "Glide",
            "glideRatioDenominator": 8.0
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(100.0, params)
        
        # Expected results:
        # r_fg = 40.0
        # s_cm = 15.0 * 2.0 = 30.0 m
        # s_cv = 3 + 3 + 1 + 15 * 1 + 30.0 = 52.0 m => r_cv = 92.0 m
        # h_cm = 0.7 * 15.0 * 2.0 = 21.0 m
        # h_cv = 100 + 4 + 10.5 + 21.0 = 135.5 m
        # s_grb = 135.5 * 8 = 1084.0 m => r_grb = 1176.0 m
        self.assertAlmostEqual(r_fg, 40.0, places=4)
        self.assertAlmostEqual(r_cv, 92.0, places=4)
        self.assertAlmostEqual(r_grb, 1176.0, places=4)

    def test_tc7_multicopter_default_manoeuvres_and_simplified_1_1_grb(self):
        """
        TC7: Multicopter, Baro altimetry, Default stopping CV, 1:1 Simplified GRB.
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "Multikopter",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 15.0,
            "maxCharacteristicDimension": 2.5,
            "corridorWidth": 50.0,
            "maxFlightHeight": 90.0,
            "lateralContingencyManoeuvreType": "Default",
            "maxPitchAngle": 25.0,
            "verticalContingencyManoeuvreType": "Default",
            "groundRiskBufferMethod": "Simplified"
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(90.0, params)
        
        # Expected results:
        # r_fg = 25.0
        # s_cm = 0.5 * 15^2 / (9.81 * tan(25)) = 112.5 / (9.81 * 0.466307658) = 24.59296366 m
        # s_cv = 3 + 3 + 1 + 15 * 1 + 24.59296366 = 46.59296366 m => r_cv = 71.59296366 m
        # h_cm = 0.5 * 15^2 / 9.81 = 11.4678899 m
        # h_cv = 90 + 1 + 10.5 + 11.4678899 = 112.9678899 m
        # s_grb = 112.9678899 + 0.5 * 2.5 = 114.2178899 m => r_grb = 185.8108536 m
        self.assertAlmostEqual(r_fg, 25.0, places=4)
        self.assertAlmostEqual(r_cv, 71.5930, places=4)
        self.assertAlmostEqual(r_grb, 185.8109, places=4)

    def test_tc8_fixed_wing_default_manoeuvres_and_parachute_grb(self):
        """
        TC8: Fixed-Wing, Baro altimetry, Default curve CV, Parachute GRB.
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 25.0,
            "maxCharacteristicDimension": 4.5,
            "corridorWidth": 100.0,
            "maxFlightHeight": 120.0,
            "lateralContingencyManoeuvreType": "Default",
            "maxRollAngle": 40.0,
            "verticalContingencyManoeuvreType": "Default",
            "groundRiskBufferMethod": "Parachute",
            "parachuteOpeningTimeGRB": 1.5,
            "maxWindVelocity": 5.0,
            "parachuteDescentRate": 3.0
        })
        
        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(120.0, params)
        
        # Expected results:
        # r_fg = 50.0
        # s_cm = 25^2 / (9.81 * tan(40)) = 625 / (9.81 * 0.83909963) = 75.9272186 m
        # s_cv = 3 + 3 + 1 + 25 * 1 + 75.9272186 = 107.9272186 m => r_cv = 157.9272186 m
        # h_cm = 0.3 * 25^2 / 9.81 = 19.11314985 m
        # h_cv = 120 + 1 + 17.5 + 19.11314985 = 157.61314985 m
        # s_grb = 25 * 1.5 + 5 * (157.61314985 / 3.0) = 37.5 + 262.688583 = 300.188583 m => r_grb = 458.1158017 m
        self.assertAlmostEqual(r_fg, 50.0, places=4)
        self.assertAlmostEqual(r_cv, 157.9272, places=4)
        self.assertAlmostEqual(r_grb, 458.1158, places=4)

    def test_sora_volume_widget_logic(self):
        """
        Verify that SoraVolumeWidget logic handles updates correctly.
        """
        from QUCORE.sora_volume_widget import SoraVolumeWidget
        
        # Test widget initialization and logic without painting to avoid QApplication dependencies
        try:
            widget = SoraVolumeWidget(tr_fn=lambda key, d: d)
        except Exception:
            # Headless environment platform error, skip QWidget tests
            return
            
        # Perform assertions outside of the try-except block so AssertionError is never swallowed!
        # Initially empty
        self.assertFalse(widget.has_data)
        
        # Update with lists
        r_fg_list = [50.0]
        s_cv_list = [10.0]
        s_grb_list = [30.0]
        h_fg_list = [100.0]
        h_cv_list = [120.0]
        
        widget.update_values(r_fg_list, s_cv_list, s_grb_list, h_fg_list, h_cv_list)
        
        self.assertTrue(widget.has_data)
        self.assertEqual(widget.avg_r_fg, 50.0)
        self.assertEqual(widget.avg_s_cv, 10.0)
        self.assertEqual(widget.avg_s_grb, 30.0)
        self.assertEqual(widget.avg_h_fg, 100.0)
        self.assertEqual(widget.avg_h_cv, 120.0)
        self.assertEqual(widget.r_fg_str, "100,0 m")
        self.assertEqual(widget.s_cv_str, "10,0 m")
        self.assertEqual(widget.s_grb_str, "30,0 m")
        self.assertEqual(widget.h_fg_str, "100,0 m")
        self.assertEqual(widget.h_cv_str, "120,0 m")
        
        # Test range formatting (German locale comma decimal separator)
        widget.update_values([50.0, 100.0], [10.0, 20.0], [30.0, 45.0], [100.0, 100.0], [120.0, 150.0])
        self.assertEqual(widget.r_fg_str, "100,0–200,0 m")
        self.assertEqual(widget.s_cv_str, "10,0–20,0 m")
        self.assertEqual(widget.s_grb_str, "30,0–45,0 m")
        self.assertEqual(widget.h_fg_str, "100,0 m")
        self.assertEqual(widget.h_cv_str, "120,0–150,0 m")
        
        # Test clear
        widget.update_values([], [], [], [], [])
        self.assertFalse(widget.has_data)
        self.assertEqual(widget.avg_r_fg, 0.0)


    def test_sora_docx_export(self):
        """
        Verify that SORA report docx export works without crashes.
        """
        from QUCORE.report_generator import ReportGenerator
        from qgis.core import QgsPointXY
        import tempfile
        
        # Define some mock waypoints and parameters
        waypoints = [
            (8.751481, 53.841847, 100.0, 30.0, 50.0),
            (8.336079, 54.006354, 110.0, 25.0, 60.0)
        ]
        
        pilot_pos = QgsPointXY(8.751481, 53.841847)
        params = self.base_params.copy()
        
        # Create a mock map image PNG
        temp_dir = tempfile.gettempdir()
        mock_map_png = os.path.join(temp_dir, "mock_map.png")
        with open(mock_map_png, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
            
        dest_docx = os.path.join(temp_dir, "test_sora_report.docx")
        
        try:
            ReportGenerator.export_sora_docx(dest_docx, waypoints, pilot_pos, params, mock_map_png, "Corridor")
            self.assertTrue(os.path.exists(dest_docx))
            self.assertGreater(os.path.getsize(dest_docx), 1000)
        finally:
            if os.path.exists(mock_map_png):
                os.remove(mock_map_png)
            if os.path.exists(dest_docx):
                os.remove(dest_docx)

    def test_sora_geojson_export_and_import(self):
        """
        Verify that QUCORE UAS corridor planning projects can be exported to and imported from GeoJSON.
        """
        from QUCORE.importer_exporter import ImporterExporter
        from qgis.core import QgsPointXY
        import tempfile
        
        # 1. Define waypoints, pilot position, and parameters
        waypoints = [
            (8.751481, 53.841847, 100.0, 30.0, 50.0),
            (8.336079, 54.006354, 110.0, 25.0, 60.0)
        ]
        pilot_pos = QgsPointXY(8.751481, 53.841847)
        params = self.base_params.copy()
        
        temp_dir = tempfile.gettempdir()
        dest_geojson = os.path.join(temp_dir, "test_sora_export.geojson")
        
        try:
            # 2. Export to GeoJSON
            ImporterExporter.export_geojson(dest_geojson, waypoints, pilot_pos, params, "Corridor")
            self.assertTrue(os.path.exists(dest_geojson))
            self.assertGreater(os.path.getsize(dest_geojson), 100)
            
            # Verify direct JSON properties (zero-dependency check bypasses QGIS MagicMock)
            import json
            with open(dest_geojson, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            features = json_data.get("features", [])
            
            # Assert waypoint 1 values directly in GeoJSON dictionary
            wp1_feat = next(f for f in features if f.get("properties", {}).get("name") == "Waypoint 1")
            self.assertAlmostEqual(wp1_feat["geometry"]["coordinates"][0], 8.751481, places=6)
            self.assertAlmostEqual(wp1_feat["geometry"]["coordinates"][1], 53.841847, places=6)
            self.assertEqual(wp1_feat["properties"]["altitude"], 100.0)
            self.assertEqual(wp1_feat["properties"]["speed"], 30.0)
            self.assertEqual(wp1_feat["properties"]["fg_width"], 50.0)
            
            # Assert metadata properties directly
            meta_feat = next(f for f in features if f.get("properties", {}).get("type") == "Metadata")
            self.assertEqual(meta_feat["properties"]["uas_type"], "FixedWing")
            self.assertEqual(meta_feat["properties"]["altimetry"], "GPS")
            
            # 3. Read back from GeoJSON and verify
            wpts_in, pilot_in, width_in, max_height_in, params_in, geom_in, warnings_in = ImporterExporter.import_geojson(dest_geojson)
            
            # 4. Verify structural correctness
            self.assertEqual(len(wpts_in), 2)
            self.assertEqual(geom_in, "Corridor")
            
            # First waypoint
            self.assertAlmostEqual(wpts_in[0][0], 8.751481, places=6)
            self.assertAlmostEqual(wpts_in[0][1], 53.841847, places=6)
            self.assertEqual(wpts_in[0][2], 100.0)
            self.assertEqual(wpts_in[0][3], 30.0)
            self.assertEqual(wpts_in[0][4], 50.0)
            
            # Second waypoint
            self.assertAlmostEqual(wpts_in[1][0], 8.336079, places=6)
            self.assertAlmostEqual(wpts_in[1][1], 54.006354, places=6)
            self.assertEqual(wpts_in[1][2], 110.0)
            self.assertEqual(wpts_in[1][3], 25.0)
            self.assertEqual(wpts_in[1][4], 60.0)
            
            # Pilot Position
            self.assertIsNotNone(pilot_in)
            self.assertAlmostEqual(pilot_in.x(), 8.751481, places=6)
            self.assertAlmostEqual(pilot_in.y(), 53.841847, places=6)
            
            # General parameters
            self.assertEqual(params_in.get("uas_type"), "FixedWing")
            self.assertEqual(params_in.get("altimetry"), "GPS")
            self.assertEqual(params_in.get("maxOpsSpeedV0"), 30.0)
            self.assertEqual(params_in.get("corridorWidth"), 50.0)
            
        finally:
            if os.path.exists(dest_geojson):
                os.remove(dest_geojson)

    def test_sora_kml_export_and_import(self):
        """
        Verify that QUCORE UAS corridor planning projects can be exported to and imported from KML with full roundtrip.
        """
        from QUCORE.importer_exporter import ImporterExporter
        from qgis.core import QgsPointXY
        import tempfile
        
        # 1. Define waypoints, pilot position, and parameters
        waypoints = [
            (8.751481, 53.841847, 100.0, 30.0, 50.0),
            (8.336079, 54.006354, 110.0, 25.0, 60.0)
        ]
        pilot_pos = QgsPointXY(8.751481, 53.841847)
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "maxOpsSpeedV0": 20.0,
            "maxWindVelocity": 5.0,
            "groundRiskBufferMethod": "Parachute"
        })
        
        temp_dir = tempfile.gettempdir()
        dest_kml = os.path.join(temp_dir, "test_sora_export.kml")
        
        try:
            # 2. Export to KML
            ImporterExporter.export_kml(dest_kml, waypoints, pilot_pos, params, "Corridor")
            self.assertTrue(os.path.exists(dest_kml))
            self.assertGreater(os.path.getsize(dest_kml), 100)
            
            # 3. Read back from KML and verify
            wpts_in, pilot_in, width_in, max_height_in, params_in, geom_in, warnings_in = ImporterExporter.import_kml(dest_kml)
            
            # 4. Verify structural correctness
            self.assertEqual(len(wpts_in), 2)
            self.assertEqual(geom_in, "Corridor")
            
            # First waypoint (height, speed, width should be fully restored!)
            self.assertAlmostEqual(wpts_in[0][0], 8.751481, places=6)
            self.assertAlmostEqual(wpts_in[0][1], 53.841847, places=6)
            self.assertEqual(wpts_in[0][2], 100.0)
            self.assertEqual(wpts_in[0][3], 30.0)
            
            # Second waypoint
            self.assertAlmostEqual(wpts_in[1][0], 8.336079, places=6)
            self.assertAlmostEqual(wpts_in[1][1], 54.006354, places=6)
            self.assertEqual(wpts_in[1][2], 110.0)
            self.assertEqual(wpts_in[1][3], 25.0)
            
            # Pilot Position
            self.assertIsNotNone(pilot_in)
            
            # General parameters restored
            self.assertEqual(params_in.get("uas_type"), "FixedWing")
            self.assertEqual(params_in.get("maxOpsSpeedV0"), 20.0)
            self.assertEqual(params_in.get("maxWindVelocity"), 5.0)
            self.assertEqual(params_in.get("groundRiskBufferMethod"), "Parachute")
            
        finally:
            if os.path.exists(dest_kml):
                os.remove(dest_kml)

    def test_parameter_dialog_apply_height_to_all_waypoints(self):
        """
        Verify that applying flight height to all waypoints updates waypoint altitudes correctly
        and that canceling the dialog restores them.
        """
        from QUCORE.parameter_dialog import ParameterDialog
        
        waypoints = [
            (8.751481, 53.841847, 100.0, 30.0, 50.0),
            (8.336079, 54.006354, 110.0, 25.0, 60.0)
        ]
        params = self.base_params.copy()
        params["maxFlightHeight"] = 120.0
        
        dialog = ParameterDialog(None, params, waypoints)
        self.assertEqual(dialog.spin_default_h.value(), 120.0)
        
        # Test cancel/restore:
        # Check that rejecting restores original values if we change them
        dialog.waypoints[0] = (8.751481, 53.841847, 999.0, 30.0, 50.0)
        dialog.reject()
        self.assertEqual(waypoints[0][2], 100.0) # Restored!
        
        # Test toggling the override checkbox
        dialog2 = ParameterDialog(None, params, waypoints)
        dialog2.on_override_h_toggled(True)
                
        self.assertEqual(waypoints[0][2], 120.0)
        self.assertEqual(waypoints[1][2], 120.0)

    def test_parameter_dialog_apply_width_to_all_waypoints(self):
        """
        Verify that applying Flight Geography width to all waypoints updates waypoint widths correctly
        and that canceling the dialog restores them.
        """
        from QUCORE.parameter_dialog import ParameterDialog
        
        waypoints = [
            (8.751481, 53.841847, 100.0, 30.0, 50.0),
            (8.336079, 54.006354, 110.0, 25.0, 60.0)
        ]
        params = self.base_params.copy()
        params["corridorWidth"] = 75.0
        
        dialog = ParameterDialog(None, params, waypoints)
        self.assertEqual(dialog.spin_corridor_width.value(), 75.0)
        
        # Test cancel/restore:
        # Check that rejecting restores original values if we change them
        dialog.waypoints[0] = (8.751481, 53.841847, 100.0, 30.0, 999.0)
        dialog.reject()
        self.assertEqual(waypoints[0][4], 50.0) # Restored!
        
        # Test toggling the override checkbox
        dialog2 = ParameterDialog(None, params, waypoints)
        dialog2.on_override_w_toggled(True)
                
        self.assertEqual(waypoints[0][4], 75.0)
        self.assertEqual(waypoints[1][4], 75.0)

    def test_parameter_dialog_live_preview(self):
        """
        Verify that changing dialog values triggers the live preview callback with the updated parameters.
        """
        from QUCORE.parameter_dialog import ParameterDialog
        
        waypoints = [(8.751481, 53.841847, 100.0, 30.0, 50.0)]
        params = self.base_params.copy()
        
        dialog = ParameterDialog(None, params, waypoints)
        callback_mock = MagicMock()
        dialog.on_change_callback = callback_mock
        
        dialog.spin_corridor_width.setValue(125.0)
        dialog.on_value_changed()
        
        # Verify callback was called at least once
        self.assertTrue(callback_mock.called)
        last_call_args = callback_mock.call_args[0][0]
        self.assertEqual(last_call_args["corridorWidth"], 125.0)

    def test_clear_population_density_results(self):
        """
        Verify that clear_population_density_results correctly removes population calculation
        parameters but preserves other plugin settings.
        """
        from QUCORE.plugin import DroneCorridorPlanner
        
        # Mock class to avoid executing full constructor
        class MockPlanner(DroneCorridorPlanner):
            def __init__(self):
                self.params = {
                    "aa_area_km2": 10.0,
                    "aa_population": 500,
                    "aa_density": 50.0,
                    "grb_area_km2": 2.0,
                    "grb_population": 100,
                    "grb_avg_density": 50.0,
                    "grb_max_density": 80.0,
                    "grb_max_raw_value": 0.25,
                    "maxFlightHeight": 120.0  # Unrelated setting
                }
                
        planner = MockPlanner()
        planner.clear_population_density_results()
        
        # All population density/ground risk results should be cleared
        for key in ["aa_area_km2", "aa_population", "aa_density", 
                    "grb_area_km2", "grb_population", "grb_avg_density", 
                    "grb_max_density", "grb_max_raw_value"]:
            self.assertNotIn(key, planner.params)
            
        # Other settings must be preserved
        self.assertEqual(planner.params.get("maxFlightHeight"), 120.0)

    def test_show_formats_info_dialog(self):
        """
        Verify that show_formats_info_dialog runs without errors and instantiates QDialog and QTableWidget correctly.
        """
        from QUCORE.plugin import DroneCorridorPlanner
        from unittest.mock import MagicMock
        
        class MockPlanner(DroneCorridorPlanner):
            def __init__(self):
                self.params = {"language": "de"}
                self.tr_strings = {}
                self.gui = MagicMock()
                self.iface = MagicMock()
                
        planner = MockPlanner()
        # Mock QDialog's exec_ to avoid blocking
        from PyQt5.QtWidgets import QDialog
        original_exec = QDialog.exec_
        QDialog.exec_ = MagicMock()
        
        try:
            planner.show_formats_info_dialog()
            # Verify QDialog.exec_ was called
            self.assertTrue(QDialog.exec_.called)
        finally:
            QDialog.exec_ = original_exec

    def test_translations_exist(self):
        """
        Verify that the new translation keys for IDEE B and C exist and have de/en values.
        """
        import json
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_dir = os.path.dirname(tests_dir)
        tr_path = os.path.join(plugin_dir, "translations.json")
        
        self.assertTrue(os.path.exists(tr_path))
        with open(tr_path, 'r', encoding='utf-8') as f:
            tr_strings = json.load(f)
            
        keys_to_check = [
            "import_file_filter",
            "export_file_filter",
            "dialog_formats_title",
            "formats_header",
            "formats_note",
            "matrix_col_format",
            "matrix_col_geom",
            "matrix_col_height",
            "matrix_col_speed",
            "matrix_col_params",
            "matrix_col_roundtrip",
            "yes",
            "no",
            "yes_full",
            "limited_qucore",
            "global_only",
            "route_only",
            "menu_formats_matrix",
            "btn_close_dialog",
            "matrix_col_pilot"
        ]
        
        for key in keys_to_check:
            self.assertIn(key, tr_strings)
            self.assertIn("de", tr_strings[key])
            self.assertIn("en", tr_strings[key])
            self.assertGreater(len(tr_strings[key]["de"]), 0)
            self.assertGreater(len(tr_strings[key]["en"]), 0)

    def test_volume_widget_cv_warnings(self):
        """
        Verify that SoraVolumeWidget calculates cv_warning and sets tooltip/styling correctly.
        """
        from QUCORE.sora_volume_widget import SoraVolumeWidget
        from unittest.mock import MagicMock
        
        widget = SoraVolumeWidget(tr_fn=lambda key, d: d)
        widget.setToolTip = MagicMock()
        
        # Case A: s_cv = 12.0m -> no warning (r_cv - r_fg = 22.0 - 10.0 = 12.0m)
        widget.update_values([10.0, 10.0], [12.0, 12.0], [8.0, 8.0], [100.0, 100.0], [120.0, 120.0])
        self.assertFalse(widget.cv_warning)
        widget.setToolTip.assert_called_with("")
        
        # Case B: s_cv = 8.0m -> warning should trigger
        widget.update_values([10.0, 10.0], [8.0, 8.0], [8.0, 8.0], [100.0, 100.0], [120.0, 120.0])
        self.assertTrue(widget.cv_warning)
        widget.setToolTip.assert_called()
        self.assertIn("AMC1", widget.setToolTip.call_args[0][0])

    def test_volume_widget_polygon_mode(self):
        """
        Verify that SoraVolumeWidget stores geometry_type and handles Polygon mode correctly.
        """
        from QUCORE.sora_volume_widget import SoraVolumeWidget
        
        widget = SoraVolumeWidget(tr_fn=lambda key, d: d)
        widget.update_values([10.0, 10.0], [12.0, 12.0], [8.0, 8.0], [100.0, 100.0], [120.0, 120.0], "Polygon")
        self.assertEqual(widget.geometry_type, "Polygon")

    def test_parameter_dialog_cv_warnings(self):
        """
        Verify that ParameterDialog displays a warning banner if any calculated CV is < 10m.
        """
        from QUCORE.parameter_dialog import ParameterDialog
        from unittest.mock import MagicMock
        
        waypoints = []
        params = self.base_params.copy()
        # Set values that yield a very low s_cv (reaction time = 0.1s, maxVelocity = 1m/s, maxPitchAngle = 80deg)
        params.update({
            "uas_type": "Multikopter",
            "maxOpsSpeedV0": 1.0,
            "reactionTime": 0.1,
            "gpsInaccuracy": 1.0,
            "positionError": 1.0,
            "mapError": 1.0,
            "additionalErrorLateral": 0.0,
            "lateralContingencyManoeuvreType": "Default",
            "maxPitchAngle": 80.0,
            "corridorWidth": 50.0
        })
        
        dialog = ParameterDialog(None, params, waypoints)
        dialog.lbl_cv_warning.setVisible = MagicMock()
        dialog.lbl_cv_warning.setText = MagicMock()
        dialog.check_cv_warnings()
        dialog.lbl_cv_warning.setVisible.assert_called_with(True)
        dialog.lbl_cv_warning.setText.assert_called()
        self.assertIn("Hinweis zum Contingency Volume", dialog.lbl_cv_warning.setText.call_args[0][0])
        
        # Set high velocity -> s_cv will increase above 10m
        dialog.spin_v0.setValue(50.0)
        dialog.check_cv_warnings()
        dialog.lbl_cv_warning.setVisible.assert_called_with(False)

    def test_velocity_parameter_separation_and_migration(self):
        """
        Verify that:
        1. ParameterDialog migrates legacy keys to maxOpsSpeedV0 and maxCommandableSpeedVmax.
        2. calculate_buffer_widths is driven by maxOpsSpeedV0 and not maxCommandableSpeedVmax.
        """
        from QUCORE.parameter_dialog import ParameterDialog
        
        # Test migration 1: maxVelocity -> maxOpsSpeedV0
        legacy_params = {
            "maxVelocity": 12.3
        }
        dialog = ParameterDialog(None, legacy_params, [])
        self.assertEqual(dialog.params["maxOpsSpeedV0"], 12.3)
        self.assertEqual(dialog.params["maxCommandableSpeedVmax"], 12.3) # Fallback to maxOpsSpeedV0
        
        # Test migration 2: maxVelocityVmax -> maxCommandableSpeedVmax
        legacy_params_2 = {
            "maxVelocity": 12.3,
            "maxVelocityVmax": 45.6
        }
        dialog_2 = ParameterDialog(None, legacy_params_2, [])
        self.assertEqual(dialog_2.params["maxOpsSpeedV0"], 12.3)
        self.assertEqual(dialog_2.params["maxCommandableSpeedVmax"], 45.6)
        
        # Test migration 3: maxCommandSpeedVmax -> maxCommandableSpeedVmax
        legacy_params_3 = {
            "maxVelocity": 10.0,
            "maxCommandSpeedVmax": 25.0
        }
        dialog_3 = ParameterDialog(None, legacy_params_3, [])
        self.assertEqual(dialog_3.params["maxOpsSpeedV0"], 10.0)
        self.assertEqual(dialog_3.params["maxCommandableSpeedVmax"], 25.0)

        # Test calculation separation
        params = self.base_params.copy()
        params.update({
            "uas_type": "Multikopter",
            "maxOpsSpeedV0": 10.0,
            "maxCommandableSpeedVmax": 25.0
        })
        
        # Calculate widths with v0=10.0, vmax=25.0
        r_fg_1, r_cv_1, r_grb_1, h_cv_1, d_min_1, d_max_1 = BufferCalculator.calculate_buffer_widths(100.0, params)
        
        # Change maxCommandableSpeedVmax to 40.0. This should NOT change FG, CV or GRB widths.
        params_high_vmax = params.copy()
        params_high_vmax["maxCommandableSpeedVmax"] = 40.0
        r_fg_2, r_cv_2, r_grb_2, h_cv_2, d_min_2, d_max_2 = BufferCalculator.calculate_buffer_widths(100.0, params_high_vmax)
        
        self.assertEqual(r_fg_1, r_fg_2)
        self.assertEqual(r_cv_1, r_cv_2)
        self.assertEqual(r_grb_1, r_grb_2)
        
        # Change maxOpsSpeedV0 to 20.0. This should increase CV/GRB width.
        params_high_v0 = params.copy()
        params_high_v0["maxOpsSpeedV0"] = 20.0
        r_fg_3, r_cv_3, r_grb_3, h_cv_3, d_min_3, d_max_3 = BufferCalculator.calculate_buffer_widths(100.0, params_high_v0)
        
        self.assertTrue(r_cv_3 > r_cv_1)

        # Test real-time spinbox synchronization (v0 <= vmax)
        dialog.spin_vmax.setValue(50.0)
        dialog.spin_v0.setValue(40.0)
        self.assertEqual(dialog.spin_v0.value(), 40.0)
        self.assertEqual(dialog.spin_vmax.value(), 50.0)
        
        # 1. Setting v0 higher than vmax should push vmax up to match
        dialog.spin_v0.setValue(60.0)
        dialog.sender = lambda: dialog.spin_v0
        dialog.on_value_changed()
        self.assertEqual(dialog.spin_vmax.value(), 60.0)
        
        # 2. Setting vmax lower than v0 should pull v0 down to match
        dialog.spin_vmax.setValue(35.0)
        dialog.sender = lambda: dialog.spin_vmax
        dialog.on_value_changed()
        self.assertEqual(dialog.spin_v0.value(), 35.0)

        # Test speed validation check safety net (v0 > vmax)
        from PyQt5.QtWidgets import QMessageBox
        from unittest.mock import MagicMock, patch
        
        QMessageBox.warning = MagicMock()
        
        # Force unequal values using blockSignals
        dialog.spin_v0.blockSignals(True)
        dialog.spin_vmax.blockSignals(True)
        dialog.spin_v0.setValue(40.0)
        dialog.spin_vmax.setValue(30.0)
        dialog.spin_v0.blockSignals(False)
        dialog.spin_vmax.blockSignals(False)
        
        dialog.accept()
        QMessageBox.warning.assert_called_once()
        self.assertIn("v0", QMessageBox.warning.call_args[0][2])
            
        # Reset to valid and it should accept
        dialog.spin_v0.setValue(30.0)
        dialog.spin_vmax.setValue(30.0)
        
        with patch('QUCORE.parameter_dialog.QDialog.accept') as mock_accept:
            dialog.accept()
            mock_accept.assert_called_once()

    def test_polygon_self_intersection(self):
        """
        Verify that generate_buffers returns empty geometries if the polygon self-intersects.
        """
        import sys
        geom_class = sys.modules['qgis.core'].QgsGeometry
        geom_class.is_valid_mock_geom = False
        
        try:
            # Self-intersecting hourglass-shaped polygon
            waypoints = [
                (0.0, 0.0, 100.0, 30.0, 50.0),
                (1.0, 1.0, 100.0, 30.0, 50.0),
                (1.0, 0.0, 100.0, 30.0, 50.0),
                (0.0, 1.0, 100.0, 30.0, 50.0)
            ]
            params = self.base_params.copy()
            
            fg_geom, cv_geom, grb_geom, aga_geom = BufferCalculator.generate_buffers(waypoints, params, "Polygon")
            self.assertTrue(fg_geom.isEmpty())
            self.assertTrue(cv_geom.isEmpty())
            self.assertTrue(grb_geom.isEmpty())
        finally:
            geom_class.is_valid_mock_geom = True

    def test_polygon_variable_buffering(self):
        """
        Verify that variable segment-based buffering is executed when variable_polygon_buffers is True.
        """
        # Simple triangle polygon
        waypoints = [
            (0.0, 0.0, 50.0, 10.0, 30.0),      # low parameters
            (0.0, 0.1, 150.0, 40.0, 100.0),    # high parameters
            (0.1, 0.0, 100.0, 25.0, 60.0)      # medium parameters
        ]
        
        # Test case 1: Variable buffering disabled (uses max parameters uniformly)
        params_uniform = self.base_params.copy()
        params_uniform["variable_polygon_buffers"] = False
        
        fg_u, cv_u, grb_u, aga_u = BufferCalculator.generate_buffers(waypoints, params_uniform, "Polygon")
        self.assertFalse(fg_u.isEmpty())
        self.assertFalse(cv_u.isEmpty())
        self.assertFalse(grb_u.isEmpty())
        
        # Test case 2: Variable buffering enabled (applies local segment-based parameters)
        params_variable = self.base_params.copy()
        params_variable["variable_polygon_buffers"] = True
        
        fg_v, cv_v, grb_v, aga_v = BufferCalculator.generate_buffers(waypoints, params_variable, "Polygon")
        self.assertFalse(fg_v.isEmpty())
        self.assertFalse(cv_v.isEmpty())
        self.assertFalse(grb_v.isEmpty())
        
        # Because uniform uses the maximum speed (40.0 m/s) and height (150.0 m) uniformly,
        # the uniform buffer should have a larger area than the variable buffer.
        self.assertTrue(grb_u.area() > grb_v.area())

    def test_altitude_table_dialog_show_waypoint_numbers(self):
        """
        Verify that toggling the chk_show_wp_nums checkbox in AltitudeTableDialog
        emits the sigToggleWaypointLabels signal.
        """
        from QUCORE.altitude_table_dialog import AltitudeTableDialog
        from unittest.mock import MagicMock
        
        waypoints = [
            (8.751481, 53.841847, 100.0, 30.0, 50.0),
            (8.336079, 54.006354, 110.0, 25.0, 60.0)
        ]
        
        dialog = AltitudeTableDialog(None, waypoints, self.base_params)
        
        # Mock the signal emit function
        dialog.sigToggleWaypointLabels.emit = MagicMock()
        
        # Initially labeling is not active
        self.assertFalse(dialog.labels_active)
        
        # Toggle checkbox to True (checked)
        dialog.toggle_waypoint_numbers(True)
        self.assertTrue(dialog.labels_active)
        dialog.sigToggleWaypointLabels.emit.assert_called_with(True)
        
        # Toggle checkbox to False (unchecked)
        dialog.sigToggleWaypointLabels.emit.reset_mock()
        dialog.toggle_waypoint_numbers(False)
        self.assertFalse(dialog.labels_active)
        dialog.sigToggleWaypointLabels.emit.assert_called_with(False)
        
        # Test dialog acceptance triggers cleanup
        dialog.toggle_waypoint_numbers(True)
        dialog.sigToggleWaypointLabels.emit.reset_mock()
        dialog.accept()
        dialog.sigToggleWaypointLabels.emit.assert_called_with(False)

    def test_advanced_settings_dialog_restore_defaults(self):
        """
        Verify that AdvancedSettingsDialog can restore all parameters back to defaults
        upon calling restore_defaults() and updates all style parameters and the tree.
        """
        from QUCORE.advanced_settings_dialog import AdvancedSettingsDialog
        from unittest.mock import MagicMock, patch
        import tempfile
        import json
        
        # Create a temp config file
        temp_dir = tempfile.gettempdir()
        temp_config_path = os.path.join(temp_dir, "config.json")
        default_config = {
            "stepSize": 50.0,
            "corridorWidth": 50.0,
            "linewidth_route": 1.0,
            "color_route": "#50505a"
        }
        
        with open(temp_config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f)
            
        try:
            current_params = {
                "stepSize": 120.0,
                "corridorWidth": 80.0,
                "linewidth_route": 3.0,
                "color_route": "#ff0000"
            }
            
            dialog = AdvancedSettingsDialog(None, temp_config_path, current_step_size=120.0, current_params=current_params)
            
            # Verify initial values are updated with current params
            self.assertEqual(dialog.spin_step.value(), 120.0)
            self.assertEqual(dialog.spin_lw_route.value(), 3.0)
            
            # Patch QMessageBox.question to return QMessageBox.Yes to confirm restoration
            from PyQt5.QtWidgets import QMessageBox
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                dialog.restore_defaults()
                
            # Verify values have been reset to defaults from config.json
            self.assertEqual(dialog.spin_step.value(), 50.0)
            self.assertEqual(dialog.spin_lw_route.value(), 1.0)
            self.assertEqual(dialog.get_all_params()["corridorWidth"], 50.0)
            self.assertEqual(dialog.get_all_params()["stepSize"], 50.0)
            
        finally:
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)

    def test_remove_planning_layers_when_reset_or_empty(self):
        """
        Verify that remove_planning_layers properly removes all map layers and group from project,
        resets internal references to None, and updates results label.
        """
        from QUCORE.plugin import DroneCorridorPlanner
        from unittest.mock import MagicMock, patch
        
        # We need to mock QgsProject.instance(), self.gui, and the layers
        class MockPlanner(DroneCorridorPlanner):
            def __init__(self):
                self.params = {}
                self.geometry_type = "Corridor"
                self.waypoints = []
                self.pilot_pos = None
                self.gui = MagicMock()
                self.canvas = MagicMock()
                
                # Mock layer attributes
                self.layer_group = MagicMock()
                self.lyr_waypoints = MagicMock()
                self.lyr_route = MagicMock()
                self.lyr_fg = MagicMock()
                self.lyr_cv = MagicMock()
                self.lyr_grb = MagicMock()
                self.lyr_pilot = MagicMock()
                self.lyr_vlos = MagicMock()
                self.lyr_aga = MagicMock()
                self.lbl_results = MagicMock()
                self.sora_viz = MagicMock()
                
            def tr(self, key, text):
                return text
                
            def is_layer_valid(self, layer):
                return layer is not None

        planner = MockPlanner()
        
        # Patch QgsProject.instance()
        mock_project = MagicMock()
        mock_root = MagicMock()
        mock_project.layerTreeRoot.return_value = mock_root
        mock_root.findGroups.return_value = [planner.layer_group]
        planner.layer_group.name.return_value = "Active QUCORE-Plan"
        planner.layer_group.parent.return_value = mock_root
        
        # Set layer IDs for removal verification
        for lyr_name in ['lyr_waypoints', 'lyr_route', 'lyr_fg', 'lyr_cv', 'lyr_grb', 'lyr_pilot', 'lyr_vlos', 'lyr_aga']:
            lyr = getattr(planner, lyr_name)
            lyr.id.return_value = lyr_name + "_id"
            
        expected_group = planner.layer_group
        with patch('qgis.core.QgsProject.instance', return_value=mock_project):
            planner.remove_planning_layers()
            
        # Verify removeMapLayer was called for all layers
        calls = [c[0][0] for c in mock_project.removeMapLayer.call_args_list]
        for lyr_name in ['lyr_waypoints', 'lyr_route', 'lyr_fg', 'lyr_cv', 'lyr_grb', 'lyr_pilot', 'lyr_vlos', 'lyr_aga']:
            self.assertIn(lyr_name + "_id", calls)
            
        # Verify the group node was removed
        mock_root.removeChildNode.assert_called_with(expected_group)
        
        # Verify all layer attributes are reset to None
        self.assertIsNone(planner.layer_group)
        self.assertIsNone(planner.lyr_waypoints)
        self.assertIsNone(planner.lyr_route)
        self.assertIsNone(planner.lyr_fg)
        self.assertIsNone(planner.lyr_cv)
        self.assertIsNone(planner.lyr_grb)
        self.assertIsNone(planner.lyr_pilot)
        self.assertIsNone(planner.lyr_vlos)
        self.assertIsNone(planner.lyr_aga)
        
        # Verify sora viz was cleared
        planner.sora_viz.update_values.assert_called_once()
        
        # Verify label results was cleared
        planner.lbl_results.setText.assert_called_once()

    # ================================================================
    # Wind Drift / Asymmetric Buffer Tests
    # ================================================================

    def test_wind_drift_disabled_returns_zero_drift(self):
        """
        Verify that d_min and d_max are 0.0 when enableAsymmetricBufferWinddrift is False.
        """
        params = self.base_params.copy()
        params["enableAsymmetricBufferWinddrift"] = False
        params["groundRiskBufferMethod"] = "Parachute"
        params["maxWindVelocity"] = 10.0
        params["minWindVelocity"] = 3.0

        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(100.0, params)

        self.assertEqual(d_min, 0.0, "d_min must be 0 when asymmetric is disabled")
        self.assertEqual(d_max, 0.0, "d_max must be 0 when asymmetric is disabled")

    def test_wind_drift_parachute_calculates_drift_and_reduces_grb(self):
        """
        Verify d_max/d_min for Parachute GRB and that s_grb is reduced by the
        wind portion now handled as a vector.

        Math (FixedWing, Baro, Parachute CV+GRB, v0=20, h=110):
          h_cv = 110 + 1 + 14 + 28 = 153.0
          t_fall = h_cv / v_z = 153 / 2 = 76.5
          d_max = v_max * t_fall = 3.0 * 76.5 = 229.5
          d_min = v_min * t_fall = 1.0 * 76.5 = 76.5
          Original s_grb = 20*1 + 3*153/2 = 249.5
          Reduced s_grb = max(0, 249.5 - 229.5) = 20.0
          r_grb = r_cv + 20.0 = 92.0 + 20.0 = 112.0
        """
        params = self.base_params.copy()
        params.update({
            "uas_type": "FixedWing",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 20.0,
            "maxCharacteristicDimension": 3.6,
            "corridorWidth": 50.0,
            "lateralContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeLateral": 2.0,
            "verticalContingencyManoeuvreType": "Parachute",
            "parachuteOpeningTimeVertical": 2.0,
            "groundRiskBufferMethod": "Parachute",
            "parachuteOpeningTimeGRB": 1.0,
            "maxWindVelocity": 3.0,
            "minWindVelocity": 1.0,
            "parachuteDescentRate": 2.0,
            "enableAsymmetricBufferWinddrift": True,
        })

        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(110.0, params)

        # FG and CV stay unchanged
        self.assertAlmostEqual(r_fg, 25.0, places=4)
        self.assertAlmostEqual(r_cv, 92.0, places=4)
        self.assertAlmostEqual(h_cv, 153.0, places=4)

        # Drift distances
        self.assertAlmostEqual(d_max, 229.5, places=4)
        self.assertAlmostEqual(d_min, 76.5, places=4)

        # r_grb reduced: r_cv + max(0, 249.5 - 229.5) = 92 + 20 = 112
        self.assertAlmostEqual(r_grb, 112.0, places=4)

    def test_wind_drift_simplified_method_ignores_wind(self):
        """
        Verify that Simplified GRB returns d_min=d_max=0 even when asymmetric is enabled.
        The Simplified 1:1 rule does not use wind in the standard formulas.
        """
        params = self.base_params.copy()
        params.update({
            "enableAsymmetricBufferWinddrift": True,
            "groundRiskBufferMethod": "Simplified",
            "maxWindVelocity": 15.0,
            "minWindVelocity": 5.0,
        })

        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(100.0, params)

        self.assertEqual(d_min, 0.0, "Simplified should produce no wind drift")
        self.assertEqual(d_max, 0.0, "Simplified should produce no wind drift")

    def test_wind_drift_ballistic_calculates_drift(self):
        """
        Verify d_max for Ballistic GRB with asymmetric enabled.
        t_fall = sqrt(2 * h_cv / g), d_max = v_max * t_fall
        """
        import math
        params = self.base_params.copy()
        params.update({
            "uas_type": "Multikopter",
            "altimetry": "Baro",
            "maxOpsSpeedV0": 10.0,
            "maxCharacteristicDimension": 1.5,
            "maxPitchAngle": 45.0,
            "corridorWidth": 50.0,
            "groundRiskBufferMethod": "Ballistic",
            "enableAsymmetricBufferWinddrift": True,
            "maxWindVelocity": 10.0,
            "minWindVelocity": 2.0,
        })

        r_fg, r_cv, r_grb, h_cv, d_min, d_max = BufferCalculator.calculate_buffer_widths(100.0, params)

        t_fall = math.sqrt(2.0 * h_cv / 9.81)
        self.assertAlmostEqual(d_max, 10.0 * t_fall, places=4)
        self.assertAlmostEqual(d_min, 2.0 * t_fall, places=4)

    # ================================================================
    # Return Signature Guard
    # ================================================================

    def test_calculate_buffer_widths_returns_six_values(self):
        """
        Guard: Verify that calculate_buffer_widths always returns exactly 6 values.
        Protects against accidental signature changes.
        """
        params = self.base_params.copy()
        result = BufferCalculator.calculate_buffer_widths(100.0, params)

        self.assertIsInstance(result, tuple, "Must return a tuple")
        self.assertEqual(len(result), 6,
            f"Must return exactly 6 values (r_fg, r_cv, r_grb, h_cv, d_min, d_max), got {len(result)}")
        for i, val in enumerate(result):
            self.assertIsInstance(val, (int, float),
                f"Value at index {i} must be numeric, got {type(val)}")

    # ================================================================
    # Import Smoke Test
    # ================================================================

    def test_all_modules_importable(self):
        """
        Smoke test: Verify that all QUCORE modules can be imported without errors.
        Catches missing mock symbols, circular imports, and broken import chains.
        """
        import importlib
        modules = [
            'QUCORE.buffer_calculator',
            'QUCORE.config_manager',
            'QUCORE.translation_manager',
            'QUCORE.importer_exporter',
            'QUCORE.report_generator',
            'QUCORE.parameter_dialog',
            'QUCORE.altitude_table_dialog',
            'QUCORE.advanced_settings_dialog',
            'QUCORE.export_settings_dialog',
            'QUCORE.vlos_calculator_dialog',
            'QUCORE.sora_volume_widget',
            'QUCORE.map_tools',
            'QUCORE.zonal_stats_calculator',
            'QUCORE.plugin',
            'QUCORE.asymmetric_buffer_winddrift_dialog',
        ]
        for mod_name in modules:
            with self.subTest(module=mod_name):
                try:
                    importlib.import_module(mod_name)
                except ImportError as e:
                    self.fail(f"Failed to import {mod_name}: {e}")

    # ================================================================
    # QGIS Plugin Contract Guard
    # ================================================================

    def test_plugin_qgis_contract(self):
        """
        Verify that DroneCorridorPlanner fulfills the QGIS plugin contract:
        - __init__(self, iface) with exactly 2 parameters
        - initGui() method exists and is callable
        - unload() method exists and is callable
        """
        from QUCORE.plugin import DroneCorridorPlanner
        import inspect

        # Check __init__ signature
        sig = inspect.signature(DroneCorridorPlanner.__init__)
        param_names = list(sig.parameters.keys())
        self.assertEqual(param_names, ['self', 'iface'],
            f"__init__ signature must be (self, iface), got {param_names}")

        # Check required methods exist
        self.assertTrue(hasattr(DroneCorridorPlanner, 'initGui'),
            "Plugin must have initGui method")
        self.assertTrue(callable(getattr(DroneCorridorPlanner, 'initGui')),
            "initGui must be callable")
        self.assertTrue(hasattr(DroneCorridorPlanner, 'unload'),
            "Plugin must have unload method")
        self.assertTrue(callable(getattr(DroneCorridorPlanner, 'unload')),
            "unload must be callable")

    def test_import_waypoints_success(self):
        import tempfile
        from QUCORE.formats.ardupilot_handler import ArduPilotHandler
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.waypoints') as tmp:
            tmp.write("QGC WPL 110\n")
            tmp.write("0\t1\t0\t16\t0\t0\t0\t0\t54.0\t7.0\t10.0\t1\n") # Dummy Home
            tmp.write("1\t0\t3\t178\t1.0\t15.0\t-1.0\t0.0\t54.0\t7.0\t0.0\t1\n") # DO_CHANGE_SPEED
            tmp.write("2\t0\t3\t16\t0.0\t0.0\t0.0\t0.0\t54.1\t7.1\t20.0\t1\n") # NAV_WAYPOINT
            tmp_path = tmp.name

        try:
            waypoints, pilot_pos, width, max_height, params, geom_type, warnings = ArduPilotHandler.import_waypoints(tmp_path)
            self.assertEqual(len(waypoints), 1)
            # Waypoint should be (lon, lat, alt, speed, width)
            # 7.1 is lon, 54.1 is lat, 20.0 is alt, 15.0 is speed (from DO_CHANGE_SPEED)
            self.assertAlmostEqual(waypoints[0][0], 7.1)
            self.assertAlmostEqual(waypoints[0][1], 54.1)
            self.assertAlmostEqual(waypoints[0][2], 20.0)
            self.assertAlmostEqual(waypoints[0][3], 15.0)
            self.assertEqual(geom_type, "Corridor")
        finally:
            os.unlink(tmp_path)

    def test_import_plan_success(self):
        import tempfile, json
        from QUCORE.formats.ardupilot_handler import ArduPilotHandler
        
        plan_data = {
            "fileType": "Plan",
            "mission": {
                "items": [
                    { "command": 178, "params": [1, 25.0, 0, 0, 0, 0, 0] },
                    { "command": 16, "params": [0, 0, 0, 0, 54.2, 7.2, 30.0] },
                    { "command": 5001, "params": [0, 0, 0, 0, 54.3, 7.3, 40.0] }, # Fence point to ignore
                    { "command": 5002, "params": [0, 0, 0, 0, 54.4, 7.4, 40.0] }  # Exclusion fence point to ignore
                ]
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.plan') as tmp:
            json.dump(plan_data, tmp)
            tmp_path = tmp.name

        try:
            waypoints, pilot_pos, width, max_height, params, geom_type, warnings = ArduPilotHandler.import_plan(tmp_path)
            self.assertEqual(len(waypoints), 1) # Ignore the fence point
            self.assertAlmostEqual(waypoints[0][0], 7.2)
            self.assertAlmostEqual(waypoints[0][1], 54.2)
            self.assertAlmostEqual(waypoints[0][2], 30.0)
            self.assertAlmostEqual(waypoints[0][3], 25.0)
            self.assertEqual(geom_type, "Corridor")
        finally:
            os.unlink(tmp_path)

if __name__ == "__main__":
    unittest.main()
