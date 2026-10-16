"""Device inventory management page."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt

from ciscoman_core import database as db

logger = logging.getLogger(__name__)


class InventoryPage(QWidget):
    """Device inventory interface."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("<h1>🗂️ Device Inventory</h1>")
        layout.addWidget(title)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_devices)
        toolbar.addWidget(refresh_btn)
        
        add_btn = QPushButton("Add Device")
        add_btn.clicked.connect(self.add_device)
        toolbar.addWidget(add_btn)
        
        demo_btn = QPushButton("🧪 Add Demo Devices")
        demo_btn.clicked.connect(self.add_demo_devices)
        toolbar.addWidget(demo_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Device table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "IP", "Type", "Location", "Group", "Username"
        ])
        layout.addWidget(self.table)
        
        # Load initial data
        self.load_devices()
    
    def load_devices(self):
        """Load devices from database."""
        try:
            devices = db.list_devices()
            self.table.setRowCount(len(devices))
            
            for row, device in enumerate(devices):
                self.table.setItem(row, 0, QTableWidgetItem(str(device["id"])))
                self.table.setItem(row, 1, QTableWidgetItem(device["name"]))
                self.table.setItem(row, 2, QTableWidgetItem(device["ip"]))
                self.table.setItem(row, 3, QTableWidgetItem(device["device_type"]))
                self.table.setItem(row, 4, QTableWidgetItem(device["location"]))
                self.table.setItem(row, 5, QTableWidgetItem(device["group_name"]))
                self.table.setItem(row, 6, QTableWidgetItem(device["username"]))
            
            self.table.resizeColumnsToContents()
            logger.info(f"Loaded {len(devices)} devices")
            
        except Exception as e:
            logger.error(f"Failed to load devices: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load devices:\n{e}")
    
    def add_device(self):
        """Add a new device (show dialog)."""
        QMessageBox.information(
            self,
            "Add Device",
            "Device add dialog implementation in progress.\n\n"
            "Use the Streamlit web app (app.py) for now, or add devices via SQL."
        )
    
    def add_demo_devices(self):
        """Add demo devices."""
        try:
            key = self.main_window.get_key()
            if not key:
                QMessageBox.warning(self, "Not Logged In", "Please log in first.")
                return
            
            added = db.seed_demo_devices(key)
            self.load_devices()
            QMessageBox.information(self, "Success", f"Added {added} demo devices.")
            logger.info(f"Added {added} demo devices")
            
        except Exception as e:
            logger.error(f"Failed to add demo devices: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add demo devices:\n{e}")
