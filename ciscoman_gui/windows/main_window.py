"""Main application window."""

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction

from ciscoman_core import database as db
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


class MainWindow(QMainWindow):
    """Main application window with navigation and pages."""
    
    def __init__(self):
        super().__init__()
        self.session_key = None
        self.init_db()
        self.init_ui()
        self.show_login()
    
    def init_db(self):
        """Initialize database."""
        try:
            db.init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            QMessageBox.critical(self, "Database Error", f"Failed to initialize database:\n{e}")
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("CiscoMan - Network Management")
        self.setMinimumSize(1200, 800)
        
        # Central widget with stack for different pages
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Create pages
        self.scanner_page = ScannerPage(self)
        self.inventory_page = InventoryPage(self)
        self.control_center_page = ControlCenterPage(self)
        self.quick_wizard_page = QuickWizardPage(self)
        self.tunnel_wizard_page = TunnelWizardPage(self)
        self.coach_page = CoachPage(self)
        self.backups_page = BackupsPage(self)
        self.audit_page = AuditPage(self)
        self.settings_page = SettingsPage(self)
        
        # Add pages to stack
        self.stack.addWidget(self.scanner_page)         # 0
        self.stack.addWidget(self.inventory_page)       # 1
        self.stack.addWidget(self.control_center_page)  # 2
        self.stack.addWidget(self.quick_wizard_page)    # 3
        self.stack.addWidget(self.tunnel_wizard_page)   # 4
        self.stack.addWidget(self.coach_page)           # 5
        self.stack.addWidget(self.backups_page)         # 6
        self.stack.addWidget(self.audit_page)           # 7
        self.stack.addWidget(self.settings_page)        # 8
        
        # Create menu bar
        self.create_menu_bar()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Session timeout timer
        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.check_session)
        self.session_timer.start(60000)  # Check every minute
    
    
    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        logout_action = QAction("&Logout", self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        scanner_action = QAction("&Scanner", self)
        scanner_action.triggered.connect(lambda: self.stack.setCurrentIndex(0))
        view_menu.addAction(scanner_action)
        
        inventory_action = QAction("&Inventory", self)
        inventory_action.triggered.connect(lambda: self.stack.setCurrentIndex(1))
        view_menu.addAction(inventory_action)
        
        view_menu.addSeparator()
        
        control_action = QAction("&Control Center", self)
        control_action.triggered.connect(lambda: self.stack.setCurrentIndex(2))
        view_menu.addAction(control_action)
        
        wizard_action = QAction("Quick &Wizard", self)
        wizard_action.triggered.connect(lambda: self.stack.setCurrentIndex(3))
        view_menu.addAction(wizard_action)
        
        tunnel_action = QAction("&Tunnel Wizard", self)
        tunnel_action.triggered.connect(lambda: self.stack.setCurrentIndex(4))
        view_menu.addAction(tunnel_action)
        
        view_menu.addSeparator()
        
        coach_action = QAction("C&oach", self)
        coach_action.triggered.connect(lambda: self.stack.setCurrentIndex(5))
        view_menu.addAction(coach_action)
        
        backups_action = QAction("&Backups", self)
        backups_action.triggered.connect(lambda: self.stack.setCurrentIndex(6))
        view_menu.addAction(backups_action)
        
        audit_action = QAction("&Audit Log", self)
        audit_action.triggered.connect(lambda: self.stack.setCurrentIndex(7))
        view_menu.addAction(audit_action)
        
        settings_action = QAction("Se&ttings", self)
        settings_action.triggered.connect(lambda: self.stack.setCurrentIndex(8))
        view_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def show_login(self):
        """Show login dialog."""
        dialog = LoginDialog(self)
        if dialog.exec():
            self.session_key = dialog.get_key()
            self.status_bar.showMessage(f"Logged in | Database: {db.config.DB_PATH}")
            logger.info("User logged in successfully")
        else:
            # No login, exit
            self.close()
    
    def logout(self):
        """Logout and show login dialog."""
        self.session_key = None
        self.status_bar.showMessage("Logged out")
        logger.info("User logged out")
        self.show_login()
    
    def check_session(self):
        """Check session validity (timeout)."""
        # TODO: Implement session timeout logic
        pass
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About CiscoMan",
            "<h2>CiscoMan v2.0.0</h2>"
            "<p>Native Windows desktop application for managing Cisco network devices.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Network Scanner</li>"
            "<li>Device Inventory</li>"
            "<li>Control Center (CLI automation)</li>"
            "<li>Quick & Tunnel Wizards</li>"
            "<li>Config Backups & Diff</li>"
            "<li>Audit Logging</li>"
            "<li>Offline Demo Mode</li>"
            "</ul>"
            "<p>Built with Python, PySide6, and Netmiko.</p>"
        )
    
    def get_key(self) -> bytes:
        """Get the current session encryption key."""
        return self.session_key
