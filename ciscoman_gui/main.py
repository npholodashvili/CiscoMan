"""CiscoMan Windows native desktop application entry point."""

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

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
        
        logger.info("Starting CiscoMan v2.0.0")
        logger.info(f"Data directory: {config.get_data_dir()}")
        logger.info(f"Database: {config.DB_PATH}")
        
        # Import and show main window
        from ciscoman_gui.windows.main_window import MainWindow
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.exception("Fatal error during startup")
        QMessageBox.critical(
            None,
            "CiscoMan Fatal Error",
            f"Failed to start CiscoMan:\n\n{e}\n\nCheck {log_file} for details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
