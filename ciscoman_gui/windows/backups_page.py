"""Config backups page."""

import logging
import difflib
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QComboBox, QMessageBox, QFileDialog, QTabWidget
)

from ciscoman_core import database as db
from ciscoman_gui.workers import WorkerSlot

logger = logging.getLogger(__name__)


class BackupsPage(QWidget):
    """Config backups management."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._exec = WorkerSlot(self)
        self.init_ui()

    @property
    def worker(self):
        return self._exec.get()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h1>💾 Config Backups & Diff</h1>"))
        
        # Toolbar
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_snapshots)
        toolbar.addWidget(refresh_btn)
        
        pull_btn = QPushButton("Pull Fresh Backup")
        pull_btn.clicked.connect(self.pull_backup)
        toolbar.addWidget(pull_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Snapshots table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Device", "IP", "Time", "Label"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        # View/Diff section
        tabs = QTabWidget()
        
        # View tab
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)
        view_layout.addWidget(QLabel("Select a snapshot above to view:"))
        view_btn = QPushButton("View Selected")
        view_btn.clicked.connect(self.view_snapshot)
        view_layout.addWidget(view_btn)
        
        self.view_text = QTextEdit()
        self.view_text.setReadOnly(True)
        self.view_text.setStyleSheet("font-family: 'Courier New', monospace;")
        view_layout.addWidget(self.view_text)
        
        export_btn = QPushButton("Export to File")
        export_btn.clicked.connect(self.export_snapshot)
        view_layout.addWidget(export_btn)
        
        tabs.addTab(view_widget, "View")
        
        # Diff tab
        diff_widget = QWidget()
        diff_layout = QVBoxLayout(diff_widget)
        
        diff_select_layout = QHBoxLayout()
        diff_select_layout.addWidget(QLabel("Snapshot A (older):"))
        self.diff_a_combo = QComboBox()
        diff_select_layout.addWidget(self.diff_a_combo)
        diff_select_layout.addWidget(QLabel("Snapshot B (newer):"))
        self.diff_b_combo = QComboBox()
        diff_select_layout.addWidget(self.diff_b_combo)
        diff_layout.addLayout(diff_select_layout)
        
        diff_btn = QPushButton("Show Diff A → B")
        diff_btn.clicked.connect(self.show_diff)
        diff_layout.addWidget(diff_btn)
        
        self.diff_text = QTextEdit()
        self.diff_text.setReadOnly(True)
        self.diff_text.setStyleSheet("font-family: 'Courier New', monospace;")
        diff_layout.addWidget(self.diff_text)
        
        tabs.addTab(diff_widget, "Diff")
        
        layout.addWidget(tabs)
        
        self.load_snapshots()
    
    def load_snapshots(self):
        """Load snapshots list."""
        try:
            snapshots = db.list_snapshots()
            self.table.setRowCount(len(snapshots))
            
            self.diff_a_combo.clear()
            self.diff_b_combo.clear()
            
            for row, snap in enumerate(snapshots):
                self.table.setItem(row, 0, QTableWidgetItem(str(snap["id"])))
                self.table.setItem(row, 1, QTableWidgetItem(snap["device_name"]))
                self.table.setItem(row, 2, QTableWidgetItem(snap["ip"]))
                
                from datetime import datetime
                ts = datetime.fromtimestamp(snap["ts"]).strftime("%Y-%m-%d %H:%M:%S") if snap["ts"] else "-"
                self.table.setItem(row, 3, QTableWidgetItem(ts))
                self.table.setItem(row, 4, QTableWidgetItem(snap["label"]))
                
                combo_label = f"#{snap['id']} {snap['device_name']} @ {ts}"
                self.diff_a_combo.addItem(combo_label, snap["id"])
                self.diff_b_combo.addItem(combo_label, snap["id"])
            
            self.table.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load snapshots:\n{e}")
    
    def pull_backup(self):
        """Pull fresh backup from devices."""
        QMessageBox.information(self, "Pull Backup", "Select devices in Inventory, then use Control Center → Diagnostics → Show Running Config")
    
    def view_snapshot(self):
        """View selected snapshot."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a snapshot to view.")
            return
        
        snap_id = int(self.table.item(selected[0].row(), 0).text())
        
        try:
            key = self.main_window.get_key()
            content = db.get_snapshot_content(key, snap_id)
            if content:
                self.view_text.setPlainText(content)
            else:
                QMessageBox.warning(self, "Not Found", "Snapshot content not found.")
        except Exception as e:
            logger.error(f"Failed to view snapshot: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view snapshot:\n{e}")
    
    def export_snapshot(self):
        """Export snapshot to file."""
        content = self.view_text.toPlainText()
        if not content:
            QMessageBox.warning(self, "No Content", "View a snapshot first.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(self, "Export Snapshot", "", "Text Files (*.txt);;All Files (*)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                QMessageBox.information(self, "Success", f"Exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")
    
    def show_diff(self):
        """Show diff between two snapshots."""
        snap_a_id = self.diff_a_combo.currentData()
        snap_b_id = self.diff_b_combo.currentData()
        
        if snap_a_id is None or snap_b_id is None:
            QMessageBox.warning(self, "No Selection", "Select two snapshots to compare.")
            return
        
        try:
            key = self.main_window.get_key()
            content_a = db.get_snapshot_content(key, snap_a_id) or ""
            content_b = db.get_snapshot_content(key, snap_b_id) or ""
            
            diff = list(difflib.unified_diff(
                content_a.splitlines(),
                content_b.splitlines(),
                "A", "B", lineterm=""
            ))
            
            if diff:
                self.diff_text.setPlainText("\n".join(diff))
            else:
                self.diff_text.setPlainText("No differences between the two snapshots.")
        except Exception as e:
            logger.error(f"Failed to generate diff: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate diff:\n{e}")
