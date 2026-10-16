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
        """Add a new device."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QComboBox, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Device")
        layout = QFormLayout(dialog)
        
        from PySide6.QtWidgets import QLineEdit, QSpinBox
        name_input = QLineEdit()
        ip_input = QLineEdit()
        type_combo = QComboBox()
        type_combo.addItems(config.SUPPORTED_DEVICE_TYPES)
        port_spin = QSpinBox()
        port_spin.setRange(1, 65535)
        port_spin.setValue(22)
        location_input = QLineEdit()
        group_input = QLineEdit()
        user_input = QLineEdit()
        pw_input = QLineEdit()
        pw_input.setEchoMode(QLineEdit.Password)
        secret_input = QLineEdit()
        secret_input.setEchoMode(QLineEdit.Password)
        
        layout.addRow("Device name:", name_input)
        layout.addRow("IP address:", ip_input)
        layout.addRow("Device type:", type_combo)
        layout.addRow("SSH port:", port_spin)
        layout.addRow("Location:", location_input)
        layout.addRow("Group:", group_input)
        layout.addRow("SSH username:", user_input)
        layout.addRow("SSH password:", pw_input)
        layout.addRow("Enable secret:", secret_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec():
            try:
                key = self.main_window.get_key()
                db.add_device(
                    key,
                    name=name_input.text() or ip_input.text(),
                    ip=ip_input.text(),
                    username=user_input.text(),
                    password=pw_input.text(),
                    secret=secret_input.text(),
                    device_type=type_combo.currentText(),
                    port=port_spin.value(),
                    location=location_input.text(),
                    group_name=group_input.text()
                )
                self.load_devices()
                QMessageBox.information(self, "Success", "Device added.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add device:\n{e}")
    
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
