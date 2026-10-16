"""CiscoMan Windows native desktop application entry point."""

import sys
import logging
import socket
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtGui import QIcon, QAction

from ciscoman_gui.theme import apply_fluent_theme

# Configure logging
from ciscoman_core import config

log_file = config.LOG_DIR / "ciscoman.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def check_single_instance():
    """Check if another instance is running using shared memory."""
    shared_mem = QSharedMemory("CiscoMan_SingleInstance")
    if shared_mem.attach():
        return False, None  # Already running
    
    if not shared_mem.create(1):
        return False, None
    
    return True, shared_mem


def main():
    """Main entry point for CiscoMan Windows application."""
    try:
        # Enable High DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        app = QApplication(sys.argv)
        app.setApplicationName("CiscoMan")
        app.setOrganizationName("CiscoMan Project")
        app.setApplicationVersion("2.0.0")
        apply_fluent_theme(app)

        icon_path = Path(__file__).resolve().parent / "icon.ico"
        app_icon = QIcon(str(icon_path)) if icon_path.is_file() else QIcon()
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
        
        # Single instance lock
        is_first, shared_mem = check_single_instance()
        if not is_first:
            QMessageBox.warning(
                None,
                "Already Running",
                "CiscoMan is already running. Check the system tray."
            )
            return 1
        
        logger.info("Starting CiscoMan v2.0.0")
        logger.info(f"Data directory: {config.get_data_dir()}")
        logger.info(f"Database: {config.DB_PATH}")
        
        # Import and show main window
        from ciscoman_gui.windows.main_window import MainWindow
        
        window = MainWindow()
        
        # System tray icon
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray_icon = QSystemTrayIcon(app)
            if not app_icon.isNull():
                tray_icon.setIcon(app_icon)
            
            tray_menu = QMenu()
            show_action = QAction("Show", tray_menu)
            show_action.triggered.connect(window.show)
            tray_menu.addAction(show_action)
            
            quit_action = QAction("Quit", tray_menu)
            quit_action.triggered.connect(app.quit)
            tray_menu.addAction(quit_action)
            
            tray_icon.setContextMenu(tray_menu)
            tray_icon.activated.connect(lambda reason: window.show() if reason == QSystemTrayIcon.DoubleClick else None)
            tray_icon.show()
            tray_icon.setToolTip("CiscoMan")
            
            logger.info("System tray icon enabled")
        
        window.show()
        
        exit_code = app.exec()
        
        # Cleanup shared memory
        if shared_mem:
            shared_mem.detach()
        
        return exit_code
        
    except Exception as e:
        logger.exception("Fatal error during startup")
        QMessageBox.critical(
            None,
            "CiscoMan Fatal Error",
            f"Failed to start CiscoMan:\n\n{e}\n\nCheck {log_file} for details."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
