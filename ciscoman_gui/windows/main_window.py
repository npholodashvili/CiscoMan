"""Main application window with Fluent sidebar navigation."""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QStatusBar, QButtonGroup,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QIcon

from ciscoman_core import database as db
from ciscoman_gui.theme import NavSidebar, apply_mica
from ciscoman_gui.widgets.scroll_page import ScrollPage
from ciscoman_gui.windows.login_dialog import LoginDialog
from ciscoman_gui.windows.scanner_page import ScannerPage
from ciscoman_gui.windows.inventory_page import InventoryPage
from ciscoman_gui.windows.control_center_page import ControlCenterPage
from ciscoman_gui.windows.quick_wizard_page import QuickWizardPage
from ciscoman_gui.windows.tunnel_wizard_page import TunnelWizardPage
from ciscoman_gui.windows.coach_page import CoachPage
from ciscoman_gui.windows.backups_page import BackupsPage
from ciscoman_gui.windows.audit_page import AuditPage
from ciscoman_gui.windows.settings_page import SettingsPage

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    (0, "Scanner", "Scan the network"),
    (1, "Inventory", "Managed devices"),
    (2, "Control Center", "Push CLI actions"),
    (3, "Quick Wizard", "Guided tasks"),
    (4, "Tunnel Wizard", "GRE / IPsec / DMVPN"),
    (5, "Coach", "Command cheat sheet"),
    (6, "Backups", "Config snapshots"),
    (7, "Audit", "Action history"),
    (8, "Settings", "Password, OUI, SNMP"),
]


def app_icon() -> QIcon:
    here = Path(__file__).resolve().parent.parent
    for candidate in (
        here / "icon.ico",
        here / "resources" / "icon.ico",
        Path.cwd() / "ciscoman_gui" / "icon.ico",
    ):
        if candidate.is_file():
            return QIcon(str(candidate))
    return QIcon()


class MainWindow(QMainWindow):
    """Main application window with navigation and pages."""

    def __init__(self):
        super().__init__()
        self.session_key = None
        self.init_db()
        self.init_ui()
        apply_mica(self)
        self.show_login()

    def init_db(self):
        try:
            db.init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error("Database initialization failed: %s", e)
            QMessageBox.critical(self, "Database Error", f"Failed to initialize database:\n{e}")

    def init_ui(self):
        self.setWindowTitle("CiscoMan")
        # Small minimum so the window fits laptops and scaled displays;
        # pages scroll when they need more room.
        self.setMinimumSize(900, 560)
        self.resize(1280, 800)
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = NavSidebar()
        sidebar.setObjectName("NavSidebar")
        sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 18, 12, 12)
        side_layout.setSpacing(4)

        brand = QLabel("CiscoMan")
        brand.setObjectName("NavBrand")
        side_layout.addWidget(brand)
        caption = QLabel("Network operations")
        caption.setStyleSheet("color: #9A9A9A; font-size: 12px; padding: 0 4px 12px 4px;")
        side_layout.addWidget(caption)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        for index, label, tip in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=index: self.stack.setCurrentIndex(i))
            self.nav_group.addButton(btn, index)
            self._nav_buttons.append(btn)
            side_layout.addWidget(btn)
        self._nav_buttons[0].setChecked(True)
        side_layout.addStretch()
        root_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.scanner_page = ScannerPage(self)
        self.inventory_page = InventoryPage(self)
        self.control_center_page = ControlCenterPage(self)
        self.quick_wizard_page = QuickWizardPage(self)
        self.tunnel_wizard_page = TunnelWizardPage(self)
        self.coach_page = CoachPage(self)
        self.backups_page = BackupsPage(self)
        self.audit_page = AuditPage(self)
        self.settings_page = SettingsPage(self)

        # Every page sits in a scroll container: if the window is smaller than
        # the page needs, it scrolls instead of squeezing controls. Settings
        # already manages its own scroll area.
        for page in (
            self.scanner_page,
            self.inventory_page,
            self.control_center_page,
            self.quick_wizard_page,
            self.tunnel_wizard_page,
            self.coach_page,
            self.backups_page,
            self.audit_page,
        ):
            self.stack.addWidget(ScrollPage(page))
        self.stack.addWidget(self.settings_page)
        self.stack.currentChanged.connect(self._on_page_changed)

        self.create_menu_bar()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.check_session)
        self.session_timer.start(60000)

    def _on_page_changed(self, index: int):
        if 0 <= index < len(self._nav_buttons):
            self._nav_buttons[index].setChecked(True)
        if index == 1:
            self.inventory_page.load_devices()

    def create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        logout_action = QAction("&Logout", self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu("&View")
        for index, label, _tip in NAV_ITEMS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, i=index: self.stack.setCurrentIndex(i))
            view_menu.addAction(action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_login(self):
        dialog = LoginDialog(self)
        if dialog.exec():
            self.session_key = dialog.get_key()
            self.status_bar.showMessage(f"Unlocked  ·  {db.config.DB_PATH}")
            logger.info("User logged in successfully")
        else:
            self.close()

    def logout(self):
        self.session_key = None
        self.status_bar.showMessage("Locked")
        logger.info("User logged out")
        self.show_login()

    def check_session(self):
        pass

    def show_about(self):
        QMessageBox.about(
            self,
            "About CiscoMan",
            "<h2>CiscoMan 2.0</h2>"
            "<p>Native Windows app for Cisco and H3C network operations.</p>"
            "<p>Scanner, inventory, Control Center, Tunnel Wizard, backups, and audit.</p>",
        )

    def get_key(self) -> bytes:
        return self.session_key
