"""Network scanner page - complete implementation."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QSpinBox, QTextEdit, QMessageBox, QProgressBar, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt

from ciscoman_core import database as db, config
from ciscoman_gui.workers.device_worker import ScanWorker
from ciscoman_gui.workers.identification_worker import IdentificationWorker

logger = logging.getLogger(__name__)


class ScannerPage(QWidget):
    """Network scanner interface with auto-add."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.worker = None
        self.identify_worker = None
        self.scan_results = []
        self.identification_results = {}
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<h1>🔎 Network Scanner</h1>"))
        layout.addWidget(QLabel("Privilege-free TCP scan of the SSH port."))
        
        # Scan parameters
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("IP range:"))
        self.target_input = QLineEdit("192.168.1.0/24")
        self.target_input.setPlaceholderText("CIDR, single IP, or 192.168.1.1-50")
        params_layout.addWidget(self.target_input, 2)
        
        params_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        params_layout.addWidget(self.port_spin)
        
        params_layout.addWidget(QLabel("Timeout (s):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 10)
        self.timeout_spin.setValue(1)
        params_layout.addWidget(self.timeout_spin)
        
        layout.addLayout(params_layout)
        
        # Auto-add options (opt-in)
        auto_group = QGroupBox("Auto-Add with Default Credentials (Opt-In)")
        auto_layout = QVBoxLayout(auto_group)
        
        self.enable_auto_cb = QCheckBox("Enable auto-add (requires explicit opt-in)")
        auto_layout.addWidget(self.enable_auto_cb)
        
        auto_layout.addWidget(QLabel("⚠️ Only use on trusted networks you control."))
        
        cred_layout = QHBoxLayout()
        cred_layout.addWidget(QLabel("Username:"))
        self.default_user = QLineEdit()
        cred_layout.addWidget(self.default_user)
        cred_layout.addWidget(QLabel("Password:"))
        self.default_pw = QLineEdit()
        self.default_pw.setEchoMode(QLineEdit.Password)
        cred_layout.addWidget(self.default_pw)
        auto_layout.addLayout(cred_layout)
        
        auto_group.setVisible(False)
        auto_group.setCheckable(False)
        layout.addWidget(auto_group)
        
        # Scan button and progress
        scan_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Start Scan")
        self.scan_btn.clicked.connect(self.start_scan)
        scan_layout.addWidget(self.scan_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_scan)
        self.cancel_btn.setEnabled(False)
        scan_layout.addWidget(self.cancel_btn)
        
        self.identify_btn = QPushButton("Identify Scanned Devices (MAC/SNMP)")
        self.identify_btn.clicked.connect(self.identify_devices)
        self.identify_btn.setEnabled(False)
        scan_layout.addWidget(self.identify_btn)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        scan_layout.addWidget(self.progress, 1)
        
        layout.addLayout(scan_layout)
        
        # Results
        layout.addWidget(QLabel("Results:"))
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)
    
    def start_scan(self):
        """Start network scan."""
        target = self.target_input.text()
        port = self.port_spin.value()
        timeout = self.timeout_spin.value()
        
        self.results_text.clear()
        self.results_text.append(f"<b>Starting scan: {target} port {port}</b><br>")
        
        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        
        self.worker = ScanWorker(target, port, timeout)
        self.worker.signals.progress.connect(self.on_scan_progress)
        self.worker.signals.finished.connect(self.on_scan_finished)
        self.worker.signals.error.connect(self.on_scan_error)
        self.worker.start()
    
    def cancel_scan(self):
        """Cancel scan or identification."""
        if self.worker:
            self.worker.cancel()
            self.results_text.append("<br><b>Cancelling scan...</b><br>")
        if self.identify_worker:
            self.identify_worker.cancel()
            self.results_text.append("<br><b>Cancelling identification...</b><br>")
    
    def on_scan_progress(self, done: int, total: int, ip: str):
        """Update scan progress."""
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        # Don't spam the results with every IP
    
    def on_scan_finished(self, alive: list):
        """Handle scan completion."""
        self.scan_results = alive
        self.results_text.append(f"<br><b>Scan complete: {len(alive)} host(s) with port {self.port_spin.value()} open</b><br>")
        
        for ip in alive:
            self.results_text.append(f"• {ip}")
        
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.identify_btn.setEnabled(len(alive) > 0)
        self.worker = None
        
        if alive:
            self.results_text.append(f"<br><i>Click 'Identify Scanned Devices' to discover device types via MAC/SNMP.</i>")
    
    def on_scan_error(self, error_msg: str):
        """Handle scan error."""
        self.results_text.append(f"<br><b>Error: {error_msg}</b>")
        QMessageBox.critical(self, "Scan Error", error_msg)
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.worker = None
    
    def identify_devices(self):
        """Identify scanned devices using MAC/SNMP."""
        if not self.scan_results:
            return
        
        self.results_text.append(f"<br><b>Identifying {len(self.scan_results)} device(s)...</b><br>")
        self.results_text.append("<i>Using ARP table, OUI lookup, and SNMP discovery</i><br>")
        
        self.identify_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.scan_results))
        self.progress.setValue(0)
        
        self.identification_results = {}
        self.identify_worker = IdentificationWorker(self.scan_results)
        self.identify_worker.progress.connect(self.on_identification_progress)
        self.identify_worker.finished.connect(self.on_identification_finished)
        self.identify_worker.error.connect(self.on_identification_error)
        self.identify_worker.start()
    
    def on_identification_progress(self, done: int, total: int, ident):
        """Handle identification progress."""
        self.progress.setValue(done)
        
        if ident:
            ip = ident.ip
            self.identification_results[ip] = ident
            
            # Show result
            vendor = ident.vendor or "Unknown"
            model = f" {ident.model}" if ident.model else ""
            hostname = f" ({ident.hostname})" if ident.hostname else ""
            sources = ", ".join(ident.sources)
            confidence = f"{ident.confidence:.0%}"
            device_type = f" → {ident.device_type}" if ident.device_type else ""
            
            self.results_text.append(
                f"✓ <b>{ip}</b>{hostname}: {vendor}{model} "
                f"[{sources}, {confidence}]{device_type}"
            )
    
    def on_identification_finished(self):
        """Handle identification completion."""
        identified_count = len(self.identification_results)
        total = len(self.scan_results)
        
        self.results_text.append(
            f"<br><b>Identification complete: {identified_count}/{total} device(s) identified</b><br>"
        )
        
        if self.identification_results:
            self.results_text.append(
                "<i>Review results in Inventory, or use Control Center with identified device types.</i>"
            )
        
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.identify_btn.setEnabled(True)
        self.identify_worker = None
    
    def on_identification_error(self, error_msg: str):
        """Handle identification error."""
        self.results_text.append(f"<br><b>Identification error: {error_msg}</b>")
        QMessageBox.warning(self, "Identification Error", error_msg)
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.identify_btn.setEnabled(True)
        self.identify_worker = None
