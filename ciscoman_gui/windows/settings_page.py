"""Settings page with password change, Credential Manager, data folder."""

import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QGroupBox, QMessageBox, QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt

from ciscoman_core import database as db, config
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Settings management."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h1>⚙️ Settings</h1>"))
        
        # Master Password
        pw_group = QGroupBox("Change Master Password")
        pw_layout = QVBoxLayout(pw_group)
        
        pw_layout.addWidget(QLabel("Current password:"))
        self.current_pw = QLineEdit()
        self.current_pw.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.current_pw)
        
        pw_layout.addWidget(QLabel("New password (8+ characters):"))
        self.new_pw1 = QLineEdit()
        self.new_pw1.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.new_pw1)
        
        pw_layout.addWidget(QLabel("Confirm new password:"))
        self.new_pw2 = QLineEdit()
        self.new_pw2.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.new_pw2)
        
        change_pw_btn = QPushButton("Change Password")
        change_pw_btn.clicked.connect(self.change_password)
        pw_layout.addWidget(change_pw_btn)
        
        layout.addWidget(pw_group)
        
        # Credential Manager
        if KEYRING_AVAILABLE:
            cred_group = QGroupBox("Windows Credential Manager")
            cred_layout = QVBoxLayout(cred_group)
            
            cred_layout.addWidget(QLabel(
                "Store master password in Windows Credential Manager for auto-login.\n"
                "⚠️ Only use on a PC you control."
            ))
            
            self.use_keyring_cb = QCheckBox("Remember master password")
            self.use_keyring_cb.toggled.connect(self.toggle_keyring)
            cred_layout.addWidget(self.use_keyring_cb)
            
            # Check current state
            try:
                stored = keyring.get_password("CiscoMan", "master")
                self.use_keyring_cb.setChecked(stored is not None)
            except:
                pass
            
            layout.addWidget(cred_group)
        
        # Data Folder
        data_group = QGroupBox("Data Location")
        data_layout = QVBoxLayout(data_group)
        
        data_dir = config.get_data_dir()
        data_layout.addWidget(QLabel(f"<b>Data directory:</b> {data_dir}"))
        data_layout.addWidget(QLabel(f"<b>Database:</b> {config.DB_PATH}"))
        data_layout.addWidget(QLabel(f"<b>Logs:</b> {config.LOG_DIR}"))
        
        open_folder_btn = QPushButton("Open Data Folder")
        open_folder_btn.clicked.connect(lambda: self.open_folder(data_dir))
        data_layout.addWidget(open_folder_btn)
        
        layout.addWidget(data_group)
        
        # Discovery Settings
        discovery_group = QGroupBox("Device Discovery")
        discovery_layout = QVBoxLayout(discovery_group)
        
        discovery_layout.addWidget(QLabel(
            "MAC/OUI uses a bundled offline IEEE database. Online lookup (macvendors.com) "
            "is off by default, rate-limited, and cached."
        ))
        restore_oui_btn = QPushButton("Restore bundled OUI database")
        restore_oui_btn.clicked.connect(self.restore_oui_db)
        discovery_layout.addWidget(restore_oui_btn)
        
        self.online_oui_cb = QCheckBox("Enable online OUI vendor lookup (opt-in)")
        self.online_oui_cb.toggled.connect(self.toggle_online_oui)
        discovery_layout.addWidget(self.online_oui_cb)
        
        # Check current state
        online_enabled = db.get_setting("online_oui_lookup", "0") == "1"
        self.online_oui_cb.setChecked(online_enabled)
        
        discovery_layout.addWidget(QLabel("SNMP community string for device discovery:"))
        self.snmp_community_input = QLineEdit()
        self.snmp_community_input.setText(db.get_setting("snmp_community", "public"))
        self.snmp_community_input.setPlaceholderText("public")
        discovery_layout.addWidget(self.snmp_community_input)
        
        save_snmp_btn = QPushButton("Save SNMP Settings")
        save_snmp_btn.clicked.connect(self.save_snmp_settings)
        discovery_layout.addWidget(save_snmp_btn)
        
        layout.addWidget(discovery_group)
        
        # Import/Export
        import_group = QGroupBox("Import / Export Inventory")
        import_layout = QVBoxLayout(import_group)
        
        export_btn = QPushButton("Export Inventory (CSV, no secrets)")
        export_btn.clicked.connect(self.export_inventory)
        import_layout.addWidget(export_btn)
        
        import_btn = QPushButton("Import Inventory (CSV)")
        import_btn.clicked.connect(self.import_inventory)
        import_layout.addWidget(import_btn)
        
        layout.addWidget(import_group)
        
        layout.addStretch()
    
    def change_password(self):
        """Change master password."""
        current = self.current_pw.text()
        new1 = self.new_pw1.text()
        new2 = self.new_pw2.text()
        
        if not current or not new1:
            QMessageBox.warning(self, "Invalid Input", "Fill in all fields.")
            return
        
        if len(new1) < 8:
            QMessageBox.warning(self, "Invalid Password", "New password must be at least 8 characters.")
            return
        
        if new1 != new2:
            QMessageBox.warning(self, "Mismatch", "New passwords do not match.")
            return
        
        try:
            if db.verify_master_password(current) is None:
                QMessageBox.warning(self, "Wrong Password", "Current password is incorrect.")
                return
            
            key = self.main_window.get_key()
            new_key = db.change_master_password(key, new1)
            self.main_window.session_key = new_key
            
            # Update keyring if enabled
            if KEYRING_AVAILABLE and self.use_keyring_cb.isChecked():
                keyring.set_password("CiscoMan", "master", new1)
            
            self.current_pw.clear()
            self.new_pw1.clear()
            self.new_pw2.clear()
            
            QMessageBox.information(self, "Success", "Master password changed. All secrets re-encrypted.")
            logger.info("Master password changed")
            
        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            QMessageBox.critical(self, "Error", f"Failed to change password:\n{e}")
    
    def restore_oui_db(self):
        """Copy the packaged OUI database into the user data folder."""
        try:
            from ciscoman_core import mac_discovery
            path = mac_discovery.ensure_oui_db()
            if path is None:
                QMessageBox.warning(self, "OUI database", "Bundled OUI database was not found.")
                return
            dest = config.get_data_dir() / "oui.db"
            dest.write_bytes(path.read_bytes())
            QMessageBox.information(self, "OUI database", f"Restored to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self, "OUI database", str(e))

    def toggle_online_oui(self, checked: bool):
        """Toggle online OUI lookup."""
        try:
            db.set_setting("online_oui_lookup", "1" if checked else "0")
            logger.info(f"Online OUI lookup {'enabled' if checked else 'disabled'}")
        except Exception as e:
            logger.error(f"Failed to save online OUI setting: {e}")
    
    def save_snmp_settings(self):
        """Save SNMP community string."""
        try:
            community = self.snmp_community_input.text().strip() or "public"
            db.set_setting("snmp_community", community)
            QMessageBox.information(self, "Saved", "SNMP settings saved.")
            logger.info("SNMP settings saved")
        except Exception as e:
            logger.error(f"Failed to save SNMP settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save SNMP settings:\n{e}")
    
    def toggle_keyring(self, checked: bool):
        """Toggle Credential Manager storage."""
        if not KEYRING_AVAILABLE:
            return
        
        try:
            if checked:
                # Store current password
                reply = QMessageBox.question(
                    self,
                    "Store Password",
                    "Store your master password in Windows Credential Manager?\n\n"
                    "This enables auto-login but stores your password.\n"
                    "Only use on a PC you control.",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    self.use_keyring_cb.setChecked(False)
                    return
                
                # Need to ask for password
                from PySide6.QtWidgets import QInputDialog
                password, ok = QInputDialog.getText(
                    self, "Master Password", "Enter your master password:",
                    QLineEdit.Password
                )
                if ok and password:
                    if db.verify_master_password(password):
                        keyring.set_password("CiscoMan", "master", password)
                        QMessageBox.information(self, "Success", "Password stored in Credential Manager.")
                    else:
                        QMessageBox.warning(self, "Wrong Password", "Incorrect password.")
                        self.use_keyring_cb.setChecked(False)
                else:
                    self.use_keyring_cb.setChecked(False)
            else:
                # Remove stored password
                try:
                    keyring.delete_password("CiscoMan", "master")
                    QMessageBox.information(self, "Success", "Password removed from Credential Manager.")
                except:
                    pass
        except Exception as e:
            logger.error(f"Keyring error: {e}")
            QMessageBox.critical(self, "Error", f"Credential Manager error:\n{e}")
    
    def open_folder(self, path: Path):
        """Open folder in file explorer."""
        import subprocess
        import sys
        
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")
    
    def export_inventory(self):
        """Export inventory to CSV."""
        try:
            csv_text = db.export_devices_csv()
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Inventory", "ciscoman_inventory.csv",
                "CSV Files (*.csv);;All Files (*)"
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(csv_text)
                QMessageBox.information(self, "Success", f"Exported to {filename}")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")
    
    def import_inventory(self):
        """Import inventory from CSV."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Inventory", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                csv_text = f.read()
            
            key = self.main_window.get_key()
            count, errors = db.import_devices_csv(key, csv_text)
            
            msg = f"Imported/updated {count} device(s)."
            if errors:
                msg += "\n\nErrors:\n" + "\n".join(errors[:10])
            
            QMessageBox.information(self, "Import Complete", msg)
            logger.info(f"Imported {count} devices with {len(errors)} errors")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            QMessageBox.critical(self, "Error", f"Import failed:\n{e}")
