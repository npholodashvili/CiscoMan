"""Tunnel Wizard page for DMVPN - complete implementation."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup, 
    QPushButton, QGroupBox, QScrollArea, QCheckBox, QLineEdit, QSpinBox,
    QTextEdit, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt

from ciscoman_core import actions, database as db, tunnel_wizard
from ciscoman_core import network_utils as net
from ciscoman_gui.workers import DeviceWorker, WorkerSlot

logger = logging.getLogger(__name__)


class TunnelWizardPage(QWidget):
    """DMVPN Tunnel Wizard with full GRE/IPsec configuration."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.selected_devices = []
        self.current_role = None
        self.param_widgets = {}
        self._exec = WorkerSlot(self)
        self.device_checkboxes = {}
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<h1>🛤️ Tunnel Wizard (DMVPN)</h1>"))
        layout.addWidget(QLabel(
            "Step-by-step hub or spoke setup — shared crypto, GRE multipoint, NHRP on hub.\n"
            "Deploy the hub first, then spokes with matching PSK and NHRP network-id."
        ))
        
        # Step 1: Target devices
        targets_group = QGroupBox("1. Choose Target Devices")
        targets_layout = QVBoxLayout(targets_group)
        
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self.load_devices)
        targets_layout.addWidget(refresh_btn)
        
        self.device_area = QScrollArea()
        self.device_area.setWidgetResizable(True)
        self.device_area.setMinimumHeight(150)
        targets_layout.addWidget(self.device_area)
        
        self.device_count_label = QLabel("0 device(s) selected")
        targets_layout.addWidget(self.device_count_label)
        
        layout.addWidget(targets_group)
        
        # Step 2: Hub or Spoke
        role_group = QGroupBox("2. Hub or Spoke")
        role_layout = QVBoxLayout(role_group)
        
        self.role_btn_group = QButtonGroup(self)
        for role in tunnel_wizard.ROLES:
            rb = QRadioButton(role.label)
            rb.role_obj = role
            rb.toggled.connect(lambda checked, r=role: self.on_role_selected(r) if checked else None)
            self.role_btn_group.addButton(rb)
            role_layout.addWidget(rb)
        
        self.role_explanation = QLabel("")
        self.role_explanation.setWordWrap(True)
        role_layout.addWidget(self.role_explanation)
        
        layout.addWidget(role_group)
        
        # Step 3: Configuration parameters
        params_group = QGroupBox("3. Configuration & Preview")
        params_layout = QVBoxLayout(params_group)
        
        self.param_scroll = QScrollArea()
        self.param_scroll.setWidgetResizable(True)
        self.param_scroll.setMinimumHeight(200)
        params_layout.addWidget(self.param_scroll)
        
        # CLI Preview
        preview_layout = QHBoxLayout()
        self.show_preview_cb = QCheckBox("Show CLI Preview")
        self.show_preview_cb.setChecked(True)
        self.show_preview_cb.toggled.connect(self.update_preview)
        preview_layout.addWidget(self.show_preview_cb)
        preview_layout.addStretch()
        params_layout.addLayout(preview_layout)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setStyleSheet("font-family: 'Courier New', monospace;")
        params_layout.addWidget(self.preview_text)
        
        layout.addWidget(params_group)
        
        # Step 4: Execute
        exec_group = QGroupBox("4. Deploy Configuration")
        exec_layout = QVBoxLayout(exec_group)
        
        button_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Deploy to Selected Devices")
        self.execute_btn.clicked.connect(self.execute_tunnel)
        self.execute_btn.setEnabled(False)
        button_layout.addWidget(self.execute_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_execution)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        button_layout.addWidget(self.progress_bar, 1)
        
        exec_layout.addLayout(button_layout)
        
        # Results
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(150)
        exec_layout.addWidget(self.results_text)
        
        layout.addWidget(exec_group)
        
        # Load devices
        self.load_devices()
    
    def load_devices(self):
        """Load and display devices."""
        try:
            devices = db.list_devices()
            
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            if not devices:
                layout.addWidget(QLabel("No devices. Add them in Inventory."))
            else:
                self.device_checkboxes = {}
                for device in devices:
                    tag = " 🧪" if device.get("is_demo") else ""
                    cb = QCheckBox(f"{device['name']} ({device['ip']}){tag}")
                    cb.device_id = device['id']
                    cb.toggled.connect(self.update_device_selection)
                    self.device_checkboxes[device['id']] = cb
                    layout.addWidget(cb)
            
            layout.addStretch()
            self.device_area.setWidget(widget)
            self.update_device_selection()
            
        except Exception as e:
            logger.error(f"Failed to load devices: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load devices:\n{e}")
    
    def update_device_selection(self):
        """Update selected device list."""
        self.selected_devices = []
        if hasattr(self, 'device_checkboxes'):
            for device_id, cb in self.device_checkboxes.items():
                if cb.isChecked():
                    self.selected_devices.append(device_id)
        
        self.device_count_label.setText(f"{len(self.selected_devices)} device(s) selected")
        self.update_execute_button()
    
    def on_role_selected(self, role: tunnel_wizard.TunnelRole):
        """Handle role selection."""
        self.current_role = role
        self.role_explanation.setText(f"<i>{role.explanation}</i>")
        
        # Get the action for this role
        action = tunnel_wizard.action_for_role(role.id)
        
        # Build parameter widgets
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.param_widgets = {}
        
        if action.params:
            for param in action.params:
                param_layout = QHBoxLayout()
                param_layout.addWidget(QLabel(f"{param.label}:"))
                
                if param.kind == "int":
                    w = QSpinBox()
                    w.setValue(int(param.default or 0))
                    w.setMaximum(999999)
                    w.valueChanged.connect(self.update_preview)
                elif param.kind == "bool":
                    w = QCheckBox()
                    w.setChecked(bool(param.default))
                    w.toggled.connect(self.update_preview)
                elif param.kind == "select":
                    from PySide6.QtWidgets import QComboBox
                    w = QComboBox()
                    w.addItems(param.options)
                    w.currentTextChanged.connect(self.update_preview)
                elif param.kind == "textarea":
                    w = QTextEdit()
                    w.setPlainText(str(param.default))
                    w.setMaximumHeight(80)
                    w.textChanged.connect(self.update_preview)
                else:
                    w = QLineEdit(str(param.default))
                    w.setPlaceholderText(param.placeholder or "")
                    w.textChanged.connect(self.update_preview)
                
                param_layout.addWidget(w)
                
                if param.help:
                    help_label = QLabel(f"<i>({param.help})</i>")
                    help_label.setWordWrap(True)
                    param_layout.addWidget(help_label)
                
                param_layout.addStretch()
                layout.addLayout(param_layout)
                
                self.param_widgets[param.key] = w
        
        layout.addStretch()
        self.param_scroll.setWidget(widget)
        self.update_preview()
        self.update_execute_button()
    
    def get_param_values(self) -> dict:
        """Get current parameter values."""
        values = {}
        if not self.current_role:
            return values
        
        action = tunnel_wizard.action_for_role(self.current_role.id)
        if not action.params:
            return values
        
        for param in action.params:
            widget = self.param_widgets.get(param.key)
            if not widget:
                continue
            
            if param.kind == "int":
                values[param.key] = widget.value()
            elif param.kind == "bool":
                values[param.key] = widget.isChecked()
            elif param.kind == "select":
                values[param.key] = widget.currentText()
            elif param.kind == "textarea":
                values[param.key] = widget.toPlainText()
            else:
                values[param.key] = widget.text()
        
        return values
    
    def update_preview(self):
        """Update CLI preview."""
        if not self.show_preview_cb.isChecked():
            self.preview_text.hide()
            return
        
        self.preview_text.show()
        
        if not self.current_role:
            self.preview_text.setPlainText("Select hub or spoke above")
            return
        
        try:
            values = self.get_param_values()
            action, cli_lines = tunnel_wizard.build_cli(self.current_role.id, values)
            
            preview = "configure terminal\n" + "\n".join(cli_lines) + "\nend"
            self.preview_text.setPlainText(preview)
        except Exception as e:
            self.preview_text.setPlainText(f"Error generating preview: {e}")
    
    def update_execute_button(self):
        """Enable/disable execute button."""
        can_execute = (
            self.current_role is not None and
            len(self.selected_devices) > 0
        )
        self.execute_btn.setEnabled(can_execute and not self._exec.running)

    @property
    def worker(self):
        return self._exec.get()
    
    def execute_tunnel(self):
        """Execute tunnel configuration."""
        if not self.current_role or not self.selected_devices:
            return
        
        # Confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Tunnel Deployment",
            f"This will configure {self.current_role.label} on {len(self.selected_devices)} device(s).\n\n"
            f"Ensure hub is deployed before spokes.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        # Get devices with credentials
        key = self.main_window.get_key()
        targets = []
        for dev_id in self.selected_devices:
            dev = db.get_device_with_credentials(key, dev_id)
            if dev:
                targets.append(dev)
        
        if not targets:
            QMessageBox.warning(self, "No Devices", "No valid devices selected.")
            return
        
        # Build CLI
        try:
            values = self.get_param_values()
            action, cli_lines = tunnel_wizard.build_cli(self.current_role.id, values)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build configuration:\n{e}")
            return
        
        # Create task
        task = lambda d: net.send_config(d, cli_lines, save=False)
        
        # Start worker
        self.results_text.clear()
        self.results_text.append(f"<b>Deploying {self.current_role.label} to {len(targets)} device(s)...</b><br>")
        self.progress_bar.setMaximum(len(targets))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.execute_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        self._pending_cli = "\n".join(cli_lines)
        self._pending_action_id = action.id
        worker = DeviceWorker(targets, task)
        self._exec.bind(worker)
        worker.progress.connect(lambda d, t: self.progress_bar.setValue(d))
        worker.result.connect(self._on_worker_result)
        worker.finished.connect(self.on_execution_finished)
        worker.error.connect(self.on_execution_error)
        worker.start()

    def _on_worker_result(self, result):
        if result.success:
            self.results_text.append(f"✅ <b>{result.name}</b> ({result.ip}): Success<br>")
        else:
            self.results_text.append(f"❌ <b>{result.name}</b> ({result.ip}): {result.error}<br>")
        try:
            db.log_action(
                result.device_id, result.name, result.ip,
                getattr(self, "_pending_action_id", ""),
                getattr(self, "_pending_cli", ""),
                "success" if result.success else "failed",
                result.output, result.error,
            )
            if result.success and result.device_id:
                db.mark_seen(result.device_id)
        except Exception:
            logger.exception("audit log failed")
    
    def cancel_execution(self):
        """Cancel execution."""
        if self._exec.running:
            self._exec.cancel()
            self.results_text.append("<br><b>Cancelling...</b><br>")
    
    def on_execution_finished(self):
        """Handle execution completion."""
        self.results_text.append("<br><b>Deployment complete.</b>")
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
    
    def on_execution_error(self, error_msg: str):
        """Handle execution error."""
        self.results_text.append(f"<br><b>Error: {error_msg}</b>")
        QMessageBox.critical(self, "Execution Error", error_msg)
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
