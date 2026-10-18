"""Device inventory management page."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QAbstractItemView,
    QDialog, QFormLayout, QComboBox, QDialogButtonBox, QLineEdit, QSpinBox,
    QCheckBox, QInputDialog,
)
from PySide6.QtCore import Qt

from ciscoman_core import database as db, config

logger = logging.getLogger(__name__)


def make_os_combo(current: str | None = None) -> QComboBox:
    """Dropdown of device OS types with friendly labels; data = stored type."""
    combo = QComboBox()
    types = list(config.SUPPORTED_DEVICE_TYPES)
    if current and current not in types:
        types.append(current)  # keep an unusual stored value selectable
    for t in types:
        combo.addItem(config.device_type_label(t), t)
    if current:
        combo.setCurrentIndex(max(0, combo.findData(current)))
    return combo


class DeviceDialog(QDialog):
    """Add / edit a device. In edit mode, blank password fields keep the old ones."""

    def __init__(self, parent=None, device: dict | None = None):
        super().__init__(parent)
        self.editing = device is not None
        d = device or {}
        self.setWindowTitle("Edit Device" if self.editing else "Add Device")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)

        self.name_input = QLineEdit(d.get("name") or "")
        self.ip_input = QLineEdit(d.get("ip") or "")
        self.type_combo = make_os_combo(d.get("device_type") or "cisco_ios")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(d.get("port") or config.DEFAULT_SSH_PORT))
        self.location_input = QLineEdit(d.get("location") or "")
        self.group_input = QLineEdit(d.get("group_name") or "")
        self.user_input = QLineEdit(d.get("username") or "")
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.secret_input = QLineEdit()
        self.secret_input.setEchoMode(QLineEdit.Password)
        self.clear_secret = QCheckBox("Remove saved enable secret")
        if self.editing:
            self.pw_input.setPlaceholderText("Leave blank to keep current password")
            self.secret_input.setPlaceholderText("Leave blank to keep current secret")

        layout.addRow("Device name:", self.name_input)
        layout.addRow("IP address:", self.ip_input)
        layout.addRow("Device OS:", self.type_combo)
        layout.addRow("SSH port:", self.port_spin)
        layout.addRow("Location:", self.location_input)
        layout.addRow("Group:", self.group_input)
        layout.addRow("SSH username:", self.user_input)
        layout.addRow("SSH password:", self.pw_input)
        layout.addRow("Enable secret:", self.secret_input)
        if self.editing:
            layout.addRow("", self.clear_secret)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate(self):
        if not self.ip_input.text().strip():
            QMessageBox.warning(self, "Missing IP", "Please enter the device IP address.")
            return
        if not self.editing and not self.pw_input.text():
            ok = QMessageBox.question(
                self, "No password", "Save this device without an SSH password?"
            ) == QMessageBox.Yes
            if not ok:
                return
        self.accept()

    def values(self) -> dict:
        ip = self.ip_input.text().strip()
        v = {
            "name": self.name_input.text().strip() or ip,
            "ip": ip,
            "device_type": self.type_combo.currentData(),
            "port": self.port_spin.value(),
            "location": self.location_input.text().strip(),
            "group_name": self.group_input.text().strip(),
            "username": self.user_input.text().strip(),
        }
        if self.editing:
            # Only change credentials the user actually typed.
            if self.pw_input.text():
                v["password"] = self.pw_input.text()
            if self.clear_secret.isChecked():
                v["secret"] = ""
            elif self.secret_input.text():
                v["secret"] = self.secret_input.text()
        else:
            v["password"] = self.pw_input.text()
            v["secret"] = self.secret_input.text()
        return v


class InventoryPage(QWidget):
    """Device inventory interface."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._devices: dict[int, dict] = {}
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        title = QLabel("<h1>🗂️ Device Inventory</h1>")
        layout.addWidget(title)

        toolbar = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_devices)
        toolbar.addWidget(refresh_btn)

        add_btn = QPushButton("Add Device")
        add_btn.clicked.connect(self.add_device)
        toolbar.addWidget(add_btn)

        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setToolTip("Edit the selected device (or double-click a row)")
        self.edit_btn.clicked.connect(self.edit_device)
        toolbar.addWidget(self.edit_btn)

        self.os_btn = QPushButton("Set OS…")
        self.os_btn.setToolTip("Change the OS / platform of all selected devices")
        self.os_btn.clicked.connect(self.set_os_for_selected)
        toolbar.addWidget(self.os_btn)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setToolTip("Delete the selected device(s)")
        self.delete_btn.clicked.connect(self.delete_devices)
        toolbar.addWidget(self.delete_btn)

        demo_btn = QPushButton("🧪 Add Demo Devices")
        demo_btn.clicked.connect(self.add_demo_devices)
        toolbar.addWidget(demo_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        hint = QLabel(
            "Tip: double-click a device to edit it. Select several rows (Ctrl/Shift) "
            "to change their OS or delete them together. Pick the right OS so "
            "CiscoMan sends commands that device understands."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "IP", "OS", "Vendor", "MAC",
            "Location", "Group", "Username", "Source",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_device())
        self.table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.table)

        self.load_devices()

    # --- helpers --------------------------------------------------------------

    def selected_ids(self) -> list[int]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        ids = []
        for r in rows:
            item = self.table.item(r, 0)
            if item is not None:
                ids.append(int(item.text()))
        return ids

    def _update_buttons(self):
        n = len(self.selected_ids())
        self.edit_btn.setEnabled(n == 1)
        self.os_btn.setEnabled(n >= 1)
        self.delete_btn.setEnabled(n >= 1)

    def _key_or_warn(self):
        key = self.main_window.get_key()
        if not key:
            QMessageBox.warning(self, "Not Logged In", "Please log in first.")
        return key

    # --- actions --------------------------------------------------------------

    def load_devices(self):
        """Load devices from database."""
        try:
            devices = db.list_devices()
            self._devices = {d["id"]: d for d in devices}
            self.table.setRowCount(len(devices))

            for row, device in enumerate(devices):
                dtype = device.get("device_type") or ""
                type_item = QTableWidgetItem(config.device_type_label(dtype))
                type_item.setToolTip(dtype)
                self.table.setItem(row, 0, QTableWidgetItem(str(device["id"])))
                self.table.setItem(row, 1, QTableWidgetItem(device["name"]))
                self.table.setItem(row, 2, QTableWidgetItem(device["ip"]))
                self.table.setItem(row, 3, type_item)
                self.table.setItem(row, 4, QTableWidgetItem(device.get("vendor") or ""))
                self.table.setItem(row, 5, QTableWidgetItem(device.get("mac") or ""))
                self.table.setItem(row, 6, QTableWidgetItem(device["location"]))
                self.table.setItem(row, 7, QTableWidgetItem(device["group_name"]))
                self.table.setItem(row, 8, QTableWidgetItem(device["username"]))
                self.table.setItem(row, 9, QTableWidgetItem(device.get("ident_source") or ""))

            self.table.resizeColumnsToContents()
            self._update_buttons()
            logger.info(f"Loaded {len(devices)} devices")

        except Exception as e:
            logger.error(f"Failed to load devices: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load devices:\n{e}")

    def add_device(self):
        """Add a new device."""
        dialog = DeviceDialog(self)
        if dialog.exec():
            try:
                key = self._key_or_warn()
                if not key:
                    return
                db.add_device(key, **dialog.values())
                self.load_devices()
                QMessageBox.information(self, "Success", "Device added.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add device:\n{e}")

    def edit_device(self):
        """Edit the selected device, including credentials and OS."""
        ids = self.selected_ids()
        if len(ids) != 1:
            QMessageBox.information(self, "Edit Device", "Select one device to edit.")
            return
        device = self._devices.get(ids[0])
        if not device:
            return
        dialog = DeviceDialog(self, device)
        if dialog.exec():
            try:
                values = dialog.values()
                key = self.main_window.get_key()
                if not key and ("password" in values or values.get("secret")):
                    QMessageBox.warning(
                        self, "Not Logged In", "Please log in first to change credentials."
                    )
                    return
                db.update_device(key, device["id"], **values)
                self.load_devices()
                logger.info("Updated device %s (%s)", device["id"], values["ip"])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update device:\n{e}")

    def set_os_for_selected(self):
        """Change device_type for every selected device."""
        ids = self.selected_ids()
        if not ids:
            return
        labels = [config.device_type_label(t) for t in config.SUPPORTED_DEVICE_TYPES]
        current = self._devices.get(ids[0], {}).get("device_type")
        start = (list(config.SUPPORTED_DEVICE_TYPES).index(current)
                 if current in config.SUPPORTED_DEVICE_TYPES else 0)
        label, ok = QInputDialog.getItem(
            self, "Set Device OS", f"OS for {len(ids)} selected device(s):",
            labels, start, False,
        )
        if not ok:
            return
        dtype = config.SUPPORTED_DEVICE_TYPES[labels.index(label)]
        try:
            for did in ids:
                db.update_device(None, did, device_type=dtype)
            self.load_devices()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set OS:\n{e}")

    def delete_devices(self):
        """Delete the selected device(s) after confirmation."""
        ids = self.selected_ids()
        if not ids:
            return
        names = [
            f"{self._devices[i]['name']} ({self._devices[i]['ip']})"
            for i in ids if i in self._devices
        ]
        shown = "\n".join(names[:10]) + (f"\n…and {len(names) - 10} more" if len(names) > 10 else "")
        reply = QMessageBox.question(
            self, "Delete Devices",
            f"Delete {len(ids)} device(s) from the inventory?\n\n{shown}\n\n"
            "This removes their saved credentials too.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            for did in ids:
                db.delete_device(did)
            self.load_devices()
            logger.info("Deleted devices %s", ids)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete:\n{e}")

    def add_demo_devices(self):
        """Add demo devices."""
        try:
            key = self._key_or_warn()
            if not key:
                return

            added = db.seed_demo_devices(key)
            self.load_devices()
            QMessageBox.information(self, "Success", f"Added {added} demo devices.")
            logger.info(f"Added {added} demo devices")

        except Exception as e:
            logger.error(f"Failed to add demo devices: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add demo devices:\n{e}")
