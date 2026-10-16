"""Quick Wizard page."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup, QPushButton,
    QGroupBox, QScrollArea, QCheckBox, QSpinBox, QLineEdit, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt

from ciscoman_core import actions, database as db, wizard
from ciscoman_gui.workers import DeviceWorker, retain_worker
from ciscoman_core import network_utils as net

logger = logging.getLogger(__name__)


class QuickWizardPage(QWidget):
    """Quick Wizard - simplified workflow."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.selected_devices = []
        self.current_intent = None
        self.worker = None
        self.device_checkboxes = {}
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h1>⚡ Quick Wizard</h1>"))
        layout.addWidget(QLabel("Simplest path: devices → intent → run"))
        
        # Step 1: Devices
        dev_group = QGroupBox("1. Choose Devices")
        dev_layout = QVBoxLayout(dev_group)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_devices)
        dev_layout.addWidget(refresh_btn)
        
        self.device_area = QScrollArea()
        self.device_area.setWidgetResizable(True)
        self.device_area.setMinimumHeight(150)
        dev_layout.addWidget(self.device_area)
        
        layout.addWidget(dev_group)
        
        # Step 2: Intent
        intent_group = QGroupBox("2. What to Do")
        intent_layout = QVBoxLayout(intent_group)
        
        self.intent_btn_group = QButtonGroup(self)
        for intent in wizard.INTENTS:
            rb = QRadioButton(intent.label)
            rb.intent_obj = intent
            rb.toggled.connect(lambda checked, i=intent: self.on_intent_selected(i) if checked else None)
            self.intent_btn_group.addButton(rb)
            intent_layout.addWidget(rb)
        
        layout.addWidget(intent_group)
        
        # Step 3: Extra params
        self.param_group = QGroupBox("3. Additional Settings")
        self.param_layout = QVBoxLayout(self.param_group)
        self.param_group.setVisible(False)
        layout.addWidget(self.param_group)
        
        # Step 4: Execute
        exec_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute")
        self.execute_btn.clicked.connect(self.execute)
        self.execute_btn.setEnabled(False)
        exec_layout.addWidget(self.execute_btn)
        exec_layout.addStretch()
        layout.addLayout(exec_layout)
        
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results)
        
        layout.addStretch()
        self.load_devices()
    
    def load_devices(self):
        """Load devices."""
        devices = db.list_devices()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.device_checkboxes = {}
        for device in devices:
            cb = QCheckBox(f"{device['name']} ({device['ip']})")
            cb.device_id = device['id']
            cb.toggled.connect(self.update_selection)
            self.device_checkboxes[device['id']] = cb
            layout.addWidget(cb)
        
        layout.addStretch()
        self.device_area.setWidget(widget)
    
    def update_selection(self):
        """Update selection state."""
        self.selected_devices = [d_id for d_id, cb in self.device_checkboxes.items() if cb.isChecked()]
        self.execute_btn.setEnabled(self.current_intent is not None and len(self.selected_devices) > 0)
    
    def on_intent_selected(self, intent: wizard.WizardIntent):
        """Handle intent selection."""
        self.current_intent = intent
        
        # Clear param widgets
        while self.param_layout.count():
            child = self.param_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add extra param widgets
        self.extra_param_widgets = {}
        if "vlan" in intent.extra_params:
            self.param_layout.addWidget(QLabel("Access VLAN ID:"))
            vlan_spin = QSpinBox()
            vlan_spin.setRange(1, 4094)
            vlan_spin.setValue(1)
            self.param_layout.addWidget(vlan_spin)
            self.extra_param_widgets["vlan"] = vlan_spin
        
        if "description" in intent.extra_params:
            self.param_layout.addWidget(QLabel("Description:"))
            desc_line = QLineEdit()
            desc_line.setPlaceholderText("e.g. Printer - Floor 2")
            self.param_layout.addWidget(desc_line)
            self.extra_param_widgets["description"] = desc_line
        
        self.param_group.setVisible(len(self.extra_param_widgets) > 0)
        self.update_selection()
    
    def execute(self):
        """Execute wizard action."""
        if not self.current_intent or not self.selected_devices:
            return
        
        # Get param values
        values = {}
        for key, widget in self.extra_param_widgets.items():
            if isinstance(widget, QSpinBox):
                values[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text()
        
        # Build action (simplified - using placeholder interface)
        try:
            action, cli_lines = wizard.build_cli(self.current_intent.id, "GigabitEthernet1/0/1", values)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build command: {e}")
            return
        
        # Get devices
        key = self.main_window.get_key()
        targets = [db.get_device_with_credentials(key, d_id) for d_id in self.selected_devices]
        targets = [t for t in targets if t]
        
        if action.kind == "show":
            task = lambda d: net.run_show_commands(d, cli_lines, use_textfsm=action.use_textfsm)
        else:
            task = lambda d: net.send_config(d, cli_lines, save=False)
        
        self.results.clear()
        self.results.append(f"Executing {self.current_intent.label} on {len(targets)} device(s)...\n")
        
        self.worker = retain_worker(self, DeviceWorker(targets, task))
        self.worker.result.connect(
            lambda result: self.results.append(
                f"{'✅' if result.success else '❌'} {result.name} ({result.ip})"
            )
        )
        self.worker.finished.connect(lambda: self.results.append("\nComplete."))
        self.worker.start()
