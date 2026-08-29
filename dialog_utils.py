# -*- coding: utf-8 -*-
"""
QUCORE Dialog Utilities
Provides a unified base dialog class (QucoreBaseDialog) with automatic geometry
persistence (size and position), multi-monitor off-screen validation, and reset utilities.
"""

from qgis.PyQt.QtWidgets import QDialog, QApplication
from qgis.PyQt.QtCore import QByteArray, QRect, QPoint
from qgis.core import QgsSettings, QgsMessageLog, Qgis

from .config_manager import ConfigManager


def is_rect_visible_on_screens(rect):
    """
    Checks if a given QRect is at least partially visible on any connected screen.
    Guards against 'lost windows' when an external monitor has been disconnected.
    """
    try:
        from qgis.PyQt.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        if not screens:
            return True

        for screen in screens:
            screen_geo = screen.availableGeometry() if hasattr(screen, 'availableGeometry') else screen.geometry()
            # If the screen intersects with at least a 50x50 area of the window
            intersection = screen_geo.intersected(rect)
            if intersection.width() >= 50 and intersection.height() >= 50:
                return True
        return False
    except Exception as e:
        # Fallback to True if screen introspection is unsupported (e.g. headless test environment)
        return True


def reset_all_qucore_geometries():
    """
    Clears all saved dialog geometries and window positions from QgsSettings.
    """
    try:
        settings = QgsSettings()
        settings.remove("QUCORE/geometry")
        if hasattr(settings, 'sync'):
            settings.sync()
        return True
    except Exception as e:
        QgsMessageLog.logMessage(f"Fehler beim Zurücksetzen der Fenstergeometrien: {e}", "QUCORE", Qgis.Warning)
        return False


class QucoreBaseDialog(QDialog):
    """
    Base dialog class for all QUCORE dialogs.
    Automatically manages size, position persistence, and screen bounds checking.
    """
    def __init__(self, parent=None, dialog_key=None, *args, **kwargs):
        super(QucoreBaseDialog, self).__init__(parent, *args, **kwargs)
        self.dialog_key = dialog_key or self.__class__.__name__
        self._geometry_restored = False

    def restore_dialog_geometry(self):
        """
        Restores window geometry from QgsSettings.
        If no saved geometry exists or if the window is outside screen bounds,
        applies default dimensions from ConfigManager and centers the window.
        """
        try:
            w_def, h_def = ConfigManager.get_dialog_default_size(self.dialog_key)
            settings = QgsSettings()
            saved_geom = settings.value(f"QUCORE/geometry/{self.dialog_key}", None)
            
            restored = False
            if saved_geom is not None:
                if isinstance(saved_geom, (bytes, bytearray)):
                    saved_geom = QByteArray(saved_geom)
                if isinstance(saved_geom, QByteArray) and not saved_geom.isEmpty():
                    restored = self.restoreGeometry(saved_geom)
            
            # If restored, verify that the window is actually on a visible screen
            if restored:
                curr_geo = self.geometry()
                if not is_rect_visible_on_screens(curr_geo):
                    # Off-screen window detected! Fallback to default size & center
                    self.resize(w_def, h_def)
                    self.center_on_parent()
            else:
                self.resize(w_def, h_def)
                self.center_on_parent()

        except Exception as e:
            QgsMessageLog.logMessage(f"Fehler beim Wiederherstellen der Geometrie für {self.dialog_key}: {e}", "QUCORE", Qgis.Warning)
            w, h = 500, 400
            hint = self.sizeHint() if hasattr(self, 'sizeHint') else None
            if hint and hasattr(hint, 'isValid') and callable(hint.isValid) and hint.isValid() is True:
                try:
                    if isinstance(hint.width(), (int, float)) and hint.width() > 0:
                        w = int(hint.width())
                    if isinstance(hint.height(), (int, float)) and hint.height() > 0:
                        h = int(hint.height())
                except Exception as e:
                    QgsMessageLog.logMessage(f"Hinweis bei sizeHint-Ermittlung für {self.dialog_key}: {e}", "QUCORE", Qgis.Info)
            self.resize(w, h)
            self.center_on_parent()
            
        self._geometry_restored = True

    def center_on_parent(self):
        """
        Centers the dialog relative to its parent window or the primary screen.
        """
        try:
            parent = self.parent()
            if parent and hasattr(parent, 'geometry') and hasattr(parent, 'isVisible') and parent.isVisible():
                parent_geo = parent.geometry()
                x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
                y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
                self.move(max(0, x), max(0, y))
            else:
                from qgis.PyQt.QtGui import QGuiApplication
                primary = QGuiApplication.primaryScreen()
                if primary:
                    avail = primary.availableGeometry() if hasattr(primary, 'availableGeometry') else primary.geometry()
                    x = avail.x() + (avail.width() - self.width()) // 2
                    y = avail.y() + (avail.height() - self.height()) // 2
                    self.move(max(0, x), max(0, y))
        except Exception as e:
            QgsMessageLog.logMessage(f"Fehler beim Zentrieren des Dialogs {self.dialog_key}: {e}", "QUCORE", Qgis.Warning)

    def save_dialog_geometry(self):
        """
        Persists the current window geometry into QgsSettings.
        """
        if not self.dialog_key:
            return
        try:
            settings = QgsSettings()
            geom = self.saveGeometry()
            settings.setValue(f"QUCORE/geometry/{self.dialog_key}", geom)
        except Exception as e:
            QgsMessageLog.logMessage(f"Fehler beim Speichern der Geometrie für {self.dialog_key}: {e}", "QUCORE", Qgis.Warning)

    def showEvent(self, event):
        if not self._geometry_restored:
            self.restore_dialog_geometry()
        super(QucoreBaseDialog, self).showEvent(event)

    def closeEvent(self, event):
        self.save_dialog_geometry()
        super(QucoreBaseDialog, self).closeEvent(event)

    def hideEvent(self, event):
        self.save_dialog_geometry()
        super(QucoreBaseDialog, self).hideEvent(event)

    def reset_to_default_geometry(self):
        """
        Resets this specific dialog to default dimensions and centers it.
        """
        try:
            settings = QgsSettings()
            settings.remove(f"QUCORE/geometry/{self.dialog_key}")
            w_def, h_def = ConfigManager.get_dialog_default_size(self.dialog_key)
            self.resize(w_def, h_def)
            self.center_on_parent()
        except Exception as e:
            QgsMessageLog.logMessage(f"Fehler beim Zurücksetzen der Geometrie für {self.dialog_key}: {e}", "QUCORE", Qgis.Warning)
