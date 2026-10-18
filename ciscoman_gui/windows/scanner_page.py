"""Network scanner — interactive results table with identify / SSH / inventory."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QMessageBox, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QAbstractItemView, QInputDialog,
    QComboBox,
)

from ciscoman_core import config, database as db
from ciscoman_core.device_identification import DeviceIdentity
from ciscoman_core.win_native import icmp_echo
from ciscoman_gui.workers import ScanWorker, IdentificationWorker, WorkerSlot

logger = logging.getLogger(__name__)

COLS = [
    "IP", "Hostname", "MAC", "Vendor", "Model / OS",
    "Open ports", "Status", "Source / confidence",
]


@dataclass
class HostRow:
    ip: str
    hostname: str = ""
    mac: str = ""
    vendor: str = ""
    model_os: str = ""
    ports: str = ""
    status: str = "Open"
    source: str = ""
    confidence: float = 0.0
    note: str = ""
    device_type: str = ""
    identity: Optional[DeviceIdentity] = field(default=None, repr=False)


class ScannerPage(QWidget):
    """Network scanner with a live, actionable results table."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._scan = WorkerSlot(self)
        self._ident = WorkerSlot(self)
        self.scan_results: list[str] = []
        self.identification_results: dict = {}
        self._rows: dict[str, HostRow] = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Scanner")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)
        sub = QLabel(
            "Privilege-free TCP scan. Routed subnets have no local ARP — "
            "Identify uses SNMP, SSH/HTTP banners, and optional switch ARP."
        )
        sub.setStyleSheet("color: #C8C8C8;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        params = QHBoxLayout()
        params.addWidget(QLabel("Range"))
        self.target_input = QLineEdit("192.168.1.0/24")
        self.target_input.setPlaceholderText("CIDR, single IP, or 192.168.1.1-50")
        params.addWidget(self.target_input, 2)
        params.addWidget(QLabel("Port"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        params.addWidget(self.port_spin)
        params.addWidget(QLabel("Timeout (s)"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 10)
        self.timeout_spin.setValue(1)
        params.addWidget(self.timeout_spin)
        layout.addLayout(params)

        # Keep auto-add widgets so older tests / callers don't break (hidden).
        self.enable_auto_cb = None
        self.default_user = QLineEdit()
        self.default_pw = QLineEdit()
        self.default_pw.setEchoMode(QLineEdit.Password)
        self.default_user.hide()
        self.default_pw.hide()

        btns = QHBoxLayout()
        self.scan_btn = QPushButton("Start scan")
        self.scan_btn.setObjectName("AccentButton")
        self.scan_btn.clicked.connect(self.start_scan)
        btns.addWidget(self.scan_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_scan)
        self.cancel_btn.setEnabled(False)
        btns.addWidget(self.cancel_btn)
        self.identify_btn = QPushButton("Identify")
        self.identify_btn.clicked.connect(self.identify_devices)
        self.identify_btn.setEnabled(False)
        btns.addWidget(self.identify_btn)
        self.add_btn = QPushButton("Add to inventory")
        self.add_btn.clicked.connect(self.add_selected_to_inventory)
        self.add_btn.setEnabled(False)
        btns.addWidget(self.add_btn)
        self.ssh_btn = QPushButton("Open SSH")
        self.ssh_btn.clicked.connect(self.open_ssh_selected)
        btns.addWidget(self.ssh_btn)
        self.web_btn = QPushButton("Open in browser")
        self.web_btn.clicked.connect(self.open_browser_selected)
        btns.addWidget(self.web_btn)
        self.ping_btn = QPushButton("Ping")
        self.ping_btn.clicked.connect(self.ping_selected)
        btns.addWidget(self.ping_btn)
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self.copy_selected)
        btns.addWidget(self.copy_btn)
        btns.addStretch()
        layout.addLayout(btns)

        arp_row = QHBoxLayout()
        arp_row.addWidget(QLabel("Query ARP from"))
        self.switch_combo = QComboBox()
        self.switch_combo.setMinimumWidth(260)
        arp_row.addWidget(self.switch_combo, 1)
        refresh_sw = QPushButton("Refresh devices")
        refresh_sw.clicked.connect(self.refresh_switch_combo)
        arp_row.addWidget(refresh_sw)
        layout.addLayout(arp_row)
        self.refresh_switch_combo()

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter by IP, hostname, vendor, MAC…")
        self.filter_input.textChanged.connect(self.apply_filter)
        filter_row.addWidget(self.filter_input, 1)
        self.summary_label = QLabel("No results yet")
        self.summary_label.setStyleSheet("color: #9A9A9A;")
        filter_row.addWidget(self.summary_label)
        layout.addLayout(filter_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        hint = QLabel(
            "Hosts on another subnet have no MAC via ARP (you would see the gateway). "
            "Identify falls back to SNMP (community in Settings) and reverse DNS."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9A9A9A; font-size: 12px;")
        layout.addWidget(hint)

        self.results_text = None  # old API removed; keep attr so nothing crashes

    # --- scan ----------------------------------------------------------------

    def start_scan(self):
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, "Range required", "Enter a CIDR, IP, or range.")
            return
        port = self.port_spin.value()
        timeout = self.timeout_spin.value()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self._rows.clear()
        self.scan_results = []
        self.identification_results = {}
        self.summary_label.setText("Scanning…")

        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.identify_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(100)
        self.progress.setValue(0)

        worker = ScanWorker(target, port, timeout)
        self._scan.bind(worker)
        worker.progress.connect(self.on_scan_progress)
        worker.host_found.connect(self.on_host_found)
        worker.scan_finished.connect(self.on_scan_finished)
        worker.error.connect(self.on_scan_error)
        worker.finished.connect(self._sync_buttons)
        worker.start()
        self._sync_buttons()

    def cancel_scan(self):
        self._scan.cancel()
        self._ident.cancel()

    def on_scan_progress(self, done: int, total: int, ip: str):
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)

    def on_host_found(self, ip: str):
        if ip in self._rows:
            return
        port = str(self.port_spin.value())
        row = HostRow(ip=ip, ports=port, status="Port open")
        self._rows[ip] = row
        self.scan_results.append(ip)
        self._append_table_row(row)
        self.summary_label.setText(f"{len(self._rows)} host(s) so far")
        self._sync_buttons()

    def on_scan_finished(self, alive: list):
        for ip in alive:
            if ip not in self._rows:
                self.on_host_found(ip)
        self.scan_results = list(alive)
        self.progress.setVisible(False)
        self.table.setSortingEnabled(True)
        self.summary_label.setText(f"{len(self._rows)} host(s) with port {self.port_spin.value()} open")
        self._sync_buttons()

    def on_scan_error(self, error_msg: str):
        QMessageBox.critical(self, "Scan error", error_msg)
        self.progress.setVisible(False)
        self._sync_buttons()

    def refresh_switch_combo(self):
        self.switch_combo.clear()
        self.switch_combo.addItem("Local ARP only (this PC)", None)
        try:
            for dev in db.list_devices():
                label = f"{dev['name']} ({dev['ip']}) — {dev.get('device_type') or ''}"
                self.switch_combo.addItem(label, dev["id"])
        except Exception:
            logger.debug("Could not list devices for ARP combo", exc_info=True)

    # --- identify -------------------------------------------------------------

    def identify_devices(self):
        ips = self._selected_ips() or list(self._rows.keys())
        if not ips:
            return
        self.identify_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(ips))
        self.progress.setValue(0)
        self.summary_label.setText(
            f"Identifying {len(ips)} host(s) via SNMP / SSH / HTTP"
            + (" and switch ARP…" if self.switch_combo.currentData() else "…")
        )

        switch_dev = None
        dev_id = self.switch_combo.currentData()
        if dev_id:
            key = self.main_window.get_key()
            if key:
                switch_dev = db.get_device_with_credentials(key, int(dev_id))

        worker = IdentificationWorker(ips, switch_device=switch_dev)
        self._ident.bind(worker)
        worker.progress.connect(self.on_identification_progress)
        worker.switch_arp_note.connect(self.summary_label.setText)
        worker.finished.connect(self.on_identification_finished)
        worker.error.connect(self.on_identification_error)
        worker.start()
        self._sync_buttons()

    def on_identification_progress(self, done: int, total: int, ident):
        self.progress.setValue(done)
        if not ident:
            return
        self.identification_results[ident.ip] = ident
        row = self._rows.get(ident.ip)
        if not row:
            row = HostRow(ip=ident.ip)
            self._rows[ident.ip] = row
            self._append_table_row(row)
        row.identity = ident
        row.hostname = ident.hostname or row.hostname
        row.mac = ident.mac or row.mac
        row.vendor = ident.vendor or row.vendor
        model = " ".join(p for p in (ident.model, ident.os_version) if p)
        if model:
            row.model_os = model
        row.device_type = ident.device_type or ""
        row.confidence = ident.confidence
        row.note = ident.note
        if ident.identified:
            row.status = "Identified"
        elif not ident.on_link:
            row.status = "Remote subnet"
        else:
            row.status = "No identity"
        row.source = f"{ident.source_label} · {ident.confidence:.0%}"
        if ident.note:
            row.source = f"{ident.source_label} — {ident.note}" if not ident.identified else (
                f"{ident.source_label} · {ident.confidence:.0%}"
            )
        self._refresh_row(ident.ip)

    def on_identification_finished(self):
        identified = sum(1 for r in self._rows.values() if r.identity and r.identity.identified)
        remote = sum(1 for r in self._rows.values() if r.identity and not r.identity.on_link)
        self.summary_label.setText(
            f"{identified}/{len(self._rows)} identified"
            + (f" · {remote} remote (no ARP MAC)" if remote else "")
        )
        self.progress.setVisible(False)
        self._sync_buttons()

    def on_identification_error(self, error_msg: str):
        QMessageBox.warning(self, "Identification error", error_msg)
        self.progress.setVisible(False)
        self._sync_buttons()

    # --- table helpers --------------------------------------------------------

    def _append_table_row(self, row: HostRow):
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        r = self.table.rowCount()
        self.table.insertRow(r)
        self._write_row(r, row)
        self.table.setSortingEnabled(sorting)

    def _write_row(self, r: int, row: HostRow):
        values = [
            row.ip, row.hostname, row.mac, row.vendor, row.model_os,
            row.ports, row.status, row.source,
        ]
        for c, val in enumerate(values):
            item = QTableWidgetItem(val)
            if c == 0:
                item.setData(Qt.UserRole, row.ip)
            self.table.setItem(r, c, item)

    def _row_index_for_ip(self, ip: str) -> int:
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.text() == ip:
                return r
        return -1

    def _refresh_row(self, ip: str):
        row = self._rows.get(ip)
        if not row:
            return
        r = self._row_index_for_ip(ip)
        if r < 0:
            return
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self._write_row(r, row)
        self.table.setSortingEnabled(sorting)

    def apply_filter(self, text: str):
        needle = text.strip().lower()
        for r in range(self.table.rowCount()):
            if not needle:
                self.table.setRowHidden(r, False)
                continue
            blob = " ".join(
                (self.table.item(r, c).text() if self.table.item(r, c) else "")
                for c in range(self.table.columnCount())
            ).lower()
            self.table.setRowHidden(r, needle not in blob)

    def _selected_ips(self) -> list[str]:
        ips = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item:
                ips.append(item.text())
        return ips

    def _sync_buttons(self):
        has_rows = self.table.rowCount() > 0
        scan_busy = self._scan.running
        ident_busy = self._ident.running
        self.identify_btn.setEnabled(has_rows and not scan_busy and not ident_busy)
        self.add_btn.setEnabled(bool(self._selected_ips()))
        self.scan_btn.setEnabled(not scan_busy and not ident_busy)
        self.cancel_btn.setEnabled(scan_busy or ident_busy)

    @property
    def worker(self):
        """Back-compat: current scan thread, or None after it finished."""
        return self._scan.get()

    @property
    def identify_worker(self):
        return self._ident.get()

    # --- context menu / actions ----------------------------------------------

    def show_context_menu(self, pos):
        ips = self._selected_ips()
        if not ips:
            return
        menu = QMenu(self)
        menu.addAction("Add to inventory", self.add_selected_to_inventory)
        menu.addAction("Identify", self.identify_devices)
        menu.addAction("Test SSH", self.test_ssh_selected)
        menu.addAction("Open SSH", self.open_ssh_selected)
        menu.addAction("Open in browser (HTTP)", lambda: self.open_browser_selected("http"))
        menu.addAction("Open in browser (HTTPS)", lambda: self.open_browser_selected("https"))
        menu.addAction("Ping", self.ping_selected)
        menu.addAction("Copy IP", self.copy_selected)
        menu.addAction("Copy row", self.copy_rows)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def add_selected_to_inventory(self):
        ips = self._selected_ips()
        if not ips:
            QMessageBox.information(self, "Select hosts", "Select one or more rows first.")
            return
        key = self.main_window.get_key()
        if not key:
            QMessageBox.warning(self, "Not logged in", "Unlock the vault first.")
            return
        user, ok = QInputDialog.getText(self, "SSH username", "Username for selected hosts:")
        if not ok or not user.strip():
            return
        password, ok = QInputDialog.getText(
            self, "SSH password", "Password (stored encrypted):", QLineEdit.Password
        )
        if not ok:
            return
        added = 0
        for ip in ips:
            row = self._rows.get(ip)
            name = (row.hostname if row and row.hostname else ip)
            dtype = row.device_type if row and row.device_type else ""
            if not dtype and row and row.vendor:
                from ciscoman_core.device_identification import _suggest_device_type
                dtype = _suggest_device_type(row.vendor, row.model_os, row.model_os) or ""
            dtype = dtype or "cisco_ios"
            try:
                db.upsert_device(
                    key,
                    name=name,
                    ip=ip,
                    username=user.strip(),
                    password=password,
                    device_type=dtype,
                    port=self.port_spin.value(),
                    location="",
                    group_name="",
                    mac=row.mac if row else "",
                    vendor=row.vendor if row else "",
                    model=row.model_os if row else "",
                    ident_source=row.source if row else "",
                )
                added += 1
            except Exception as exc:
                logger.error("Add %s failed: %s", ip, exc)
        if hasattr(self.main_window, "inventory_page"):
            self.main_window.inventory_page.load_devices()
        QMessageBox.information(self, "Inventory", f"Added/updated {added} device(s).")

    def test_ssh_selected(self):
        ips = self._selected_ips()
        if not ips:
            return
        from ciscoman_core import network_utils as net
        ok, fail = 0, 0
        for ip in ips:
            if net._tcp_probe(ip, self.port_spin.value(), 1.5):
                ok += 1
            else:
                fail += 1
        QMessageBox.information(self, "SSH port test", f"{ok} open, {fail} closed/filtered.")

    def open_ssh_selected(self):
        ips = self._selected_ips()
        if not ips:
            return
        ip = ips[0]
        user, ok = QInputDialog.getText(self, "SSH user", f"Username for {ip}:", text="admin")
        if not ok:
            return
        target = f"{user.strip()}@{ip}" if user.strip() else ip
        try:
            if os.name == "nt":
                wt = shutil.which("wt")
                putty = shutil.which("putty")
                if wt:
                    subprocess.Popen([wt, "ssh", target])
                    return
                if putty:
                    subprocess.Popen([putty, "-ssh", target])
                    return
                subprocess.Popen(["cmd", "/c", "start", "ssh", target], shell=False)
            else:
                subprocess.Popen(["ssh", target])
        except Exception as exc:
            QMessageBox.warning(self, "Open SSH", str(exc))

    def open_browser_selected(self, scheme: str = "https"):
        ips = self._selected_ips()
        if not ips:
            return
        webbrowser.open(f"{scheme}://{ips[0]}")

    def ping_selected(self):
        ips = self._selected_ips()
        if not ips:
            return
        reachable = [ip for ip in ips if icmp_echo(ip, 1000)]
        QMessageBox.information(
            self,
            "Ping",
            f"{len(reachable)}/{len(ips)} replied.\n"
            + (", ".join(reachable) if reachable else "No replies."),
        )

    def copy_selected(self):
        ips = self._selected_ips()
        if ips:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(ips))

    def copy_rows(self):
        ips = self._selected_ips()
        lines = []
        for ip in ips:
            row = self._rows.get(ip)
            if row:
                lines.append(
                    f"{row.ip}\t{row.hostname}\t{row.mac}\t{row.vendor}\t{row.model_os}\t{row.ports}\t{row.status}\t{row.source}"
                )
        if lines:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(lines))
