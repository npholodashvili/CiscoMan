"""Control Center page - full implementation."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QRadioButton, QButtonGroup, QScrollArea, QFrame, QCheckBox, QTextEdit,
    QMessageBox, QProgressBar, QGroupBox, QSpinBox, QLineEdit, QComboBox, QTextBrowser
)
from PySide6.QtCore import Qt

from ciscoman_core import actions, database as db
from ciscoman_core import network_utils as net
from ciscoman_gui.workers import DeviceWorker, WorkerSlot

logger = logging.getLogger(__name__)


class ControlCenterPage(QWidget):
    """Full Control Center with actions catalog."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.selected_devices = []
        self.current_action = None
        self.param_widgets = {}
        self._exec = WorkerSlot(self)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        
        # Title
        layout.addWidget(QLabel("<h1>🎛️ Control Center</h1>"))
        
        # Step 1: Device selection
        device_group = QGroupBox("1. Choose Targets")
        device_layout = QVBoxLayout(device_group)
        
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self.load_devices)
        device_layout.addWidget(refresh_btn)
        
        self.device_area = QScrollArea()
        self.device_area.setWidgetResizable(True)
        self.device_area.setMinimumHeight(150)
        device_layout.addWidget(self.device_area)
        
        self.device_count_label = QLabel("0 devices selected")
        device_layout.addWidget(self.device_count_label)
        
        layout.addWidget(device_group)
        
        # Step 2: Action selection
        action_group = QGroupBox("2. Choose Action")
        action_layout = QVBoxLayout(action_group)
        
        self.action_tabs = QTabWidget()
        for category in actions.CATEGORIES:
            tab = self.create_action_tab(category)
            self.action_tabs.addTab(tab, category)
        
        action_layout.addWidget(self.action_tabs)
        layout.addWidget(action_group)
        
        # Step 3: Parameters and execution
        exec_group = QGroupBox("3. Configure & Execute")
        exec_layout = QVBoxLayout(exec_group)
        
        self.explanation_label = QLabel("")
        self.explanation_label.setWordWrap(True)
        exec_layout.addWidget(self.explanation_label)
        
        self.param_area = QScrollArea()
        self.param_area.setWidgetResizable(True)
        self.param_area.setMinimumHeight(100)
        exec_layout.addWidget(self.param_area)
        
        # CLI Preview
        preview_layout = QHBoxLayout()
        self.show_preview_cb = QCheckBox("Show CLI Preview")
        self.show_preview_cb.setChecked(True)
        self.show_preview_cb.toggled.connect(self.update_preview)
        preview_layout.addWidget(self.show_preview_cb)
        preview_layout.addStretch()
        exec_layout.addLayout(preview_layout)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setStyleSheet("font-family: 'Courier New', monospace;")
        exec_layout.addWidget(self.preview_text)
        
        # Execute button and progress
        button_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute")
        self.execute_btn.clicked.connect(self.execute_action)
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
        
        # Results area
        self.results_area = QTextBrowser()
        self.results_area.setMinimumHeight(200)
        exec_layout.addWidget(self.results_area)
        
        layout.addWidget(exec_group)
        
        # Load devices
        self.load_devices()
    
    def create_action_tab(self, category: str) -> QWidget:
        """Create a tab for an action category."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        cat_actions = [a for a in actions.ACTIONS if a.category == category]
        
        if not cat_actions:
            scroll_layout.addWidget(QLabel(f"No actions in {category}"))
        else:
            btn_group = QButtonGroup(scroll_widget)
            btn_group.setExclusive(True)
            
            for action in cat_actions:
                rb = QRadioButton(action.name)
                rb.action_obj = action
                rb.toggled.connect(lambda checked, a=action: self.on_action_selected(a) if checked else None)
                btn_group.addButton(rb)
                scroll_layout.addWidget(rb)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        return widget
    
    def load_devices(self):
        """Load and display devices for selection."""
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
    
    def on_action_selected(self, action: actions.Action):
        """Handle action selection."""
        self.current_action = action
        self.explanation_label.setText(f"<b>What this does:</b> {action.explanation}")
        
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
                elif param.kind == "bool":
                    w = QCheckBox()
                    w.setChecked(bool(param.default))
                elif param.kind == "select":
                    w = QComboBox()
                    w.addItems(param.options)
                elif param.kind == "textarea":
                    w = QTextEdit()
                    w.setPlainText(str(param.default))
                    w.setMaximumHeight(100)
                else:
                    w = QLineEdit(str(param.default))
                    w.setPlaceholderText(param.placeholder or "")
                
                if param.help:
                    label_with_help = QLabel(f"{param.label} <i>({param.help})</i>:")
                    param_layout.insertWidget(0, label_with_help)
                    param_layout.removeWidget(param_layout.itemAt(1).widget())
                
                param_layout.addWidget(w)
                param_layout.addStretch()
                layout.addLayout(param_layout)
                
                self.param_widgets[param.key] = w
        
        layout.addStretch()
        self.param_area.setWidget(widget)
        self.update_preview()
        self.update_execute_button()
    
    def get_param_values(self) -> dict:
        """Get current parameter values."""
        values = {}
        if not self.current_action or not self.current_action.params:
            return values
        
        for param in self.current_action.params:
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
        
        if not self.current_action:
            self.preview_text.setPlainText("Select an action above")
            return
        
        try:
            values = self.get_param_values()
            if self.current_action.id == "save_config":
                lines = []
            elif self.current_action.id in ("custom_show", "custom_config"):
                cmd_text = values.get("commands", "")
                lines = [ln.strip() for ln in cmd_text.splitlines() if ln.strip()]
            else:
                lines = self.current_action.render(values)
            
            if self.current_action.kind == "config" and lines:
                preview = "configure terminal\n" + "\n".join(lines) + "\nend"
            elif self.current_action.id == "save_config":
                preview = "write memory"
            else:
                preview = "\n".join(lines) if lines else "(no commands)"
            
            self.preview_text.setPlainText(preview)
        except Exception as e:
            self.preview_text.setPlainText(f"Error generating preview: {e}")
    
    def _worker_busy(self) -> bool:
        return self._exec.running

    @property
    def worker(self):
        return self._exec.get()

    def update_execute_button(self):
        """Enable/disable execute button."""
        can_execute = (
            self.current_action is not None and
            len(self.selected_devices) > 0
        )
        self.execute_btn.setEnabled(can_execute and not self._worker_busy())
    
    def execute_action(self):
        """Execute the selected action on selected devices."""
        if not self.current_action or not self.selected_devices:
            return
        if self._worker_busy():
            return
        
        # Confirmation for config changes
        if self.current_action.kind == "config":
            reply = QMessageBox.question(
                self,
                "Confirm Execution",
                f"This will send configuration commands to {len(self.selected_devices)} device(s).\n\nContinue?",
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
        
        # Build task
        values = self.get_param_values()
        
        if self.current_action.id == "save_config":
            cli_lines = []
            task = lambda d: net.send_config(d, [], save=True)
        elif self.current_action.kind == "show":
            if self.current_action.id in ("custom_show",):
                cli_lines = [ln.strip() for ln in values.get("commands", "").splitlines() if ln.strip()]
            else:
                cli_lines = self.current_action.render(values)
            task = lambda d: net.run_show_commands(d, cli_lines, use_textfsm=self.current_action.use_textfsm)
        else:  # config
            if self.current_action.id in ("custom_config",):
                cli_lines = [ln.strip() for ln in values.get("commands", "").splitlines() if ln.strip()]
            else:
                cli_lines = self.current_action.render(values)
            task = lambda d: net.send_config(d, cli_lines, save=False)
        
        # Start worker
        self.results_area.clear()
        self.results_area.append(f"<b>Starting execution on {len(targets)} device(s)...</b><br>")
        self.progress_bar.setMaximum(len(targets))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.execute_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        self._pending_cli = "\n".join(cli_lines) if cli_lines else "write memory"
        self._pending_action_id = self.current_action.id

        worker = DeviceWorker(targets, task)
        self._exec.bind(worker)
        worker.progress.connect(self._on_worker_progress)
        worker.result.connect(self._on_worker_result)
        worker.finished.connect(self.on_execution_finished)
        worker.error.connect(self.on_execution_error)
        worker.start()

    def _on_worker_progress(self, done: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)

    def _on_worker_result(self, result):
        if result.success:
            self.results_area.append(f"✅ <b>{result.name}</b> ({result.ip}): Success<br>")
        else:
            self.results_area.append(f"❌ <b>{result.name}</b> ({result.ip}): {result.error}<br>")
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
            logger.exception("Failed to write audit row")
    
    def cancel_execution(self):
        """Cancel running execution."""
        if self._exec.running:
            self._exec.cancel()
            self.results_area.append("<br><b>Cancelling...</b><br>")
    
    def on_execution_finished(self):
        """Handle execution completion."""
        self.results_area.append("<br><b>Execution complete.</b>")
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
    
    def on_execution_error(self, error_msg: str):
        """Handle execution error."""
        self.results_area.append(f"<br><b>Error: {error_msg}</b>")
        QMessageBox.critical(self, "Execution Error", error_msg)
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
