"""Audit log page."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QMessageBox, QTabWidget
)

from ciscoman_core import database as db

logger = logging.getLogger(__name__)


class AuditPage(QWidget):
    """Audit log viewer."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h1>📜 Audit Log</h1>"))
        
        # Toolbar
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_logs)
        toolbar.addWidget(refresh_btn)
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        toolbar.addWidget(clear_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Time", "Device", "IP", "Action", "Status", "Command"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)
        
        # Detail view
        detail_group = QLabel("<b>Entry Details (select a row above):</b>")
        layout.addWidget(detail_group)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(200)
        layout.addWidget(self.detail_text)
        
        self.load_logs()
    
    def load_logs(self):
        """Load audit logs."""
        try:
            logs = db.get_audit_log(limit=500)
            self.logs_data = logs
            self.table.setRowCount(len(logs))
            
            for row, log in enumerate(logs):
                from datetime import datetime
                ts = datetime.fromtimestamp(log["ts"]).strftime("%Y-%m-%d %H:%M:%S") if log["ts"] else "-"
                
                self.table.setItem(row, 0, QTableWidgetItem(ts))
                self.table.setItem(row, 1, QTableWidgetItem(log["device_name"] or "-"))
                self.table.setItem(row, 2, QTableWidgetItem(log["ip"] or "-"))
                self.table.setItem(row, 3, QTableWidgetItem(log["action"]))
                self.table.setItem(row, 4, QTableWidgetItem(log["status"]))
                
                cmd_preview = (log["command"] or "")[:50]
                self.table.setItem(row, 5, QTableWidgetItem(cmd_preview))
            
            self.table.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"Failed to load audit logs: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load audit logs:\n{e}")
    
    def on_selection_changed(self):
        """Show details of selected log entry."""
        selected = self.table.selectedItems()
        if not selected:
            self.detail_text.clear()
            return
        
        row = selected[0].row()
        log = self.logs_data[row]
        
        detail = f"<b>Action:</b> {log['action']}<br>"
        detail += f"<b>Device:</b> {log['device_name']} ({log['ip']})<br>"
        detail += f"<b>Status:</b> {log['status']}<br><br>"
        detail += f"<b>Command:</b><br><pre>{log['command'] or '(none)'}</pre><br>"
        
        if log['output']:
            detail += f"<b>Output:</b><br><pre>{log['output'][:1000]}</pre><br>"
        
        if log['error']:
            detail += f"<b>Error:</b><br><pre>{log['error']}</pre>"
        
        self.detail_text.setHtml(detail)
    
    def clear_log(self):
        """Clear the audit log."""
        reply = QMessageBox.question(
            self,
            "Clear Audit Log",
            "This will permanently delete all audit log entries. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                db.clear_audit_log()
                self.load_logs()
                QMessageBox.information(self, "Success", "Audit log cleared.")
            except Exception as e:
                logger.error(f"Failed to clear audit log: {e}")
                QMessageBox.critical(self, "Error", f"Failed to clear audit log:\n{e}")
