"""Tunnel Wizard page for DMVPN."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QMessageBox
)

logger = logging.getLogger(__name__)


class TunnelWizardPage(QWidget):
    """DMVPN Tunnel Wizard - simplified for now."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h1>🛤️ Tunnel Wizard</h1>"))
        layout.addWidget(QLabel(
            "DMVPN hub/spoke wizard.\n\n"
            "Full implementation uses the same pattern as Control Center.\n"
            "For now, use Control Center → Routing & Tunnels → tunnel actions."
        ))
        layout.addStretch()
