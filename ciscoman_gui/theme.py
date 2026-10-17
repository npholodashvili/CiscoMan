"""Windows 11 Fluent-style theme, typography, and optional Mica backdrop."""

from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtGui import QColor, QFont, QPalette, QPainter, QPen
from PySide6.QtWidgets import QApplication, QStyleFactory, QWidget

logger = logging.getLogger(__name__)

# Fluent dark tokens (Windows 11)
BG = "#202020"
BG_ALT = "#2B2B2B"
SURFACE = "#2D2D2D"
CARD = "#323232"
STROKE = "#3F3F3F"
ACCENT = "#60CDFF"
ACCENT_HOVER = "#4CC2FF"
TEXT = "#FFFFFF"
TEXT_SEC = "#C8C8C8"
TEXT_TER = "#9A9A9A"
DANGER = "#FF99A4"
OK = "#6CCB5F"

FLUENT_QSS = f"""
* {{
    font-family: "Segoe UI Variable", "Segoe UI", "Segoe UI Variable Text", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog, QWidget {{
    background-color: {BG};
    color: {TEXT};
}}
QStackedWidget {{
    background-color: {BG};
}}
/* Sidebar */
#NavSidebar {{
    background-color: {BG_ALT};
    border-right: 1px solid {STROKE};
}}
#NavBrand {{
    font-size: 16px;
    font-weight: 600;
    color: {TEXT};
    padding: 8px 4px 16px 4px;
}}
QPushButton#NavButton {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    text-align: left;
    padding: 9px 12px;
    color: {TEXT_SEC};
}}
QPushButton#NavButton:hover {{
    background-color: rgba(255,255,255,0.06);
    color: {TEXT};
}}
QPushButton#NavButton:checked {{
    background-color: rgba(96,205,255,0.16);
    color: {TEXT};
    font-weight: 600;
}}
/* Cards / groups */
QGroupBox {{
    background-color: {CARD};
    border: 1px solid {STROKE};
    border-radius: 0px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {TEXT_SEC};
}}
QLabel {{
    background: transparent;
    color: {TEXT};
}}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    border: 1px solid {STROKE};
    border-radius: 0px;
    padding: 6px 10px;
    selection-background-color: {ACCENT};
    selection-color: #001018;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {STROKE};
    border-radius: 0px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: #3A3A3A;
    border-color: #555555;
}}
QPushButton:pressed {{
    background-color: #262626;
}}
QPushButton:disabled {{
    color: {TEXT_TER};
    background-color: #2A2A2A;
}}
QPushButton#AccentButton {{
    background-color: {ACCENT};
    color: #001018;
    border: none;
    font-weight: 600;
}}
QPushButton#AccentButton:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#AccentButton:disabled {{
    background-color: #3A4A52;
    color: #7A8A90;
}}
QTableWidget {{
    background-color: {CARD};
    alternate-background-color: {SURFACE};
    border: 1px solid {STROKE};
    border-radius: 0px;
    gridline-color: {STROKE};
    selection-background-color: rgba(96,205,255,0.22);
    selection-color: {TEXT};
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QHeaderView::section {{
    background-color: {BG_ALT};
    color: {TEXT_SEC};
    border: none;
    border-bottom: 1px solid {STROKE};
    padding: 8px;
    font-weight: 600;
}}
QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {STROKE};
    border-radius: 0px;
    text-align: center;
    height: 16px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 0px;
}}
QTabWidget::pane {{
    border: 1px solid {STROKE};
    border-radius: 0px;
    background: {CARD};
}}
QTabBar::tab {{
    background: {SURFACE};
    border: 1px solid {STROKE};
    border-bottom: none;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    padding: 7px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {CARD};
    color: {TEXT};
}}
QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #5A5A5A;
    border-radius: 0px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QCheckBox, QRadioButton {{
    spacing: 8px;
}}
QMenu {{
    background-color: {CARD};
    border: 1px solid {STROKE};
    border-radius: 0px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 24px 7px 16px;
    border-radius: 0px;
}}
QMenu::item:selected {{
    background-color: rgba(96,205,255,0.18);
}}
QStatusBar {{
    background-color: {BG_ALT};
    color: {TEXT_SEC};
    border-top: 1px solid {STROKE};
}}
QMenuBar {{
    background-color: {BG};
    color: {TEXT};
}}
QMenuBar::item:selected {{
    background-color: {SURFACE};
    border-radius: 0px;
}}
QToolTip {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {STROKE};
    padding: 4px 8px;
}}
"""


class NavSidebar(QWidget):
    """Sidebar with a balanced QPainter (Fusion + QSS radius leaks save frames)."""

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.save()
            painter.fillRect(self.rect(), QColor(BG_ALT))
            painter.setPen(QPen(QColor(STROKE)))
            x = self.width() - 1
            painter.drawLine(x, 0, x, self.height())
            painter.restore()
        finally:
            if painter.isActive():
                painter.end()


def _pick_base_style() -> str:
    keys = {k.lower(): k for k in QStyleFactory.keys()}
    if sys.platform == "win32" and "windows11" in keys:
        return keys["windows11"]
    if sys.platform == "win32" and "windowsvista" in keys:
        return keys["windowsvista"]
    return keys.get("fusion", "Fusion")


def apply_fluent_theme(app: QApplication) -> None:
    """Apply dark Fluent palette + QSS to the whole application."""
    font = QFont()
    font.setFamilies(["Segoe UI Variable", "Segoe UI", "Segoe UI Variable Text", "sans-serif"])
    font.setPixelSize(13)
    app.setFont(font)
    app.setStyle(_pick_base_style())

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor(CARD))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(SURFACE))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#001018"))
    pal.setColor(QPalette.ToolTipBase, QColor(CARD))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    pal.setColor(QPalette.PlaceholderText, QColor(TEXT_TER))
    app.setPalette(pal)
    app.setStyleSheet(FLUENT_QSS)


def apply_mica(window) -> bool:
    """Enable Windows 11 Mica / dark title bar when DWM supports it."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = int(window.winId())
        dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        # DWMWA_SYSTEMBACKDROP_TYPE = 38, DWMSBT_MAINWINDOW (Mica) = 2
        mica = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(mica), ctypes.sizeof(mica))
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
        corners = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corners), ctypes.sizeof(corners))
        return True
    except Exception as exc:
        logger.debug("Mica not applied: %s", exc)
        return False
