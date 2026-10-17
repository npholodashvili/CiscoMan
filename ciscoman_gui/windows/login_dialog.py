"""Login dialog for master password authentication."""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt

from ciscoman_core import database as db

logger = logging.getLogger(__name__)


class LoginDialog(QDialog):
    """Master password login dialog."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.key = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("CiscoMan - Login")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Check if this is first-time setup
        if not db.is_initialized():
            self.setup_mode()
        else:
            self.login_mode()
    
    def setup_mode(self):
        """First-time setup UI."""
        layout = self.layout()
        
        title = QLabel("<h2>First-Time Setup</h2>")
        layout.addWidget(title)
        
        info = QLabel(
            "Create a <b>master password</b>. It encrypts all stored device credentials.\n"
            "The encryption key is derived from this password and is never saved to disk.\n\n"
            "<b>If you lose it, stored credentials are unrecoverable.</b>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addWidget(QLabel("Master password (8+ characters):"))
        self.password1 = QLineEdit()
        self.password1.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password1)
        
        layout.addWidget(QLabel("Confirm master password:"))
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password2)
        
        create_btn = QPushButton("Create Master Password")
        create_btn.clicked.connect(self.handle_setup)
        layout.addWidget(create_btn)
    
    def login_mode(self):
        """Login UI."""
        layout = self.layout()
        
        title = QLabel("<h2>CiscoMan Login</h2>")
        layout.addWidget(title)
        
        layout.addWidget(QLabel("Master password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.handle_login)
        layout.addWidget(self.password_input)
        
        login_btn = QPushButton("Unlock")
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)
    
    def handle_setup(self):
        """Handle first-time setup."""
        p1 = self.password1.text()
        p2 = self.password2.text()
        
        if len(p1) < 8:
            QMessageBox.warning(self, "Invalid Password", "Password must be at least 8 characters.")
            return
        
        if p1 != p2:
            QMessageBox.warning(self, "Password Mismatch", "Passwords do not match.")
            return
        
        try:
            self.key = db.set_master_password(p1)
            logger.info("Master password created successfully")
            self.accept()
        except Exception as e:
            logger.error(f"Failed to set master password: {e}")
            QMessageBox.critical(self, "Error", f"Failed to set master password:\n{e}")
    
    def handle_login(self):
        """Handle login attempt."""
        password = self.password_input.text()
        
        try:
            key = db.verify_master_password(password)
            if key is None:
                QMessageBox.warning(self, "Login Failed", "Incorrect master password.")
                self.password_input.clear()
                return
            
            self.key = key
            logger.info("Login successful")
            self.accept()
        except Exception as e:
            logger.error(f"Login error: {e}")
            QMessageBox.critical(self, "Error", f"Login failed:\n{e}")
    
    def get_key(self) -> bytes:
        """Get the derived encryption key."""
        return self.key
