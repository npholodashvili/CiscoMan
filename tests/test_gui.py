"""GUI smoke tests using pytest-qt."""

import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists for tests
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests."""
    # Set offscreen platform for CI
    if "CI" in os.environ or "GITHUB_ACTIONS" in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.mark.timeout(30)
def test_main_window_opens(qapp, qtbot, mocker):
    """Test that main window opens without crashing."""
    from ciscoman_gui.windows.main_window import MainWindow
    from ciscoman_core import database as db
    
    # Initialize DB
    db.init_db()
    
    # Set a test master password if needed
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    
    # Mock the login dialog to return success
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.exec', return_value=True)
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.get_key', return_value=key)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Should have pages loaded
    assert window.stack.count() == 9
    
    window.close()


@pytest.mark.timeout(30)
def test_login_dialog(qapp, qtbot):
    """Test login dialog can be created."""
    from ciscoman_gui.windows.login_dialog import LoginDialog
    from ciscoman_core import database as db
    
    db.init_db()
    
    dialog = LoginDialog()
    qtbot.addWidget(dialog)
    
    # Dialog should have password input
    assert hasattr(dialog, 'password_input') or hasattr(dialog, 'password1')
    
    dialog.close()


@pytest.mark.timeout(30)
def test_all_pages_instantiate(qapp, qtbot, mocker):
    """Test that all page widgets can be instantiated."""
    from ciscoman_gui.windows.main_window import MainWindow
    from ciscoman_core import database as db
    
    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    
    # Mock the login dialog
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.exec', return_value=True)
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.get_key', return_value=key)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Switch to each page
    for i in range(window.stack.count()):
        window.stack.setCurrentIndex(i)
        qapp.processEvents()
    
    window.close()


@pytest.mark.timeout(30)
def test_demo_device_workflow(qapp, qtbot, mocker):
    """Test adding demo devices and viewing them in inventory."""
    from ciscoman_gui.windows.main_window import MainWindow
    from ciscoman_core import database as db
    
    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    
    # Add demo devices
    added = db.seed_demo_devices(key)
    assert added > 0
    
    # Mock the login dialog
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.exec', return_value=True)
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.get_key', return_value=key)
    
    # Load main window
    window = MainWindow()
    window.session_key = key
    qtbot.addWidget(window)
    
    # Switch to inventory page
    window.stack.setCurrentIndex(1)
    qapp.processEvents()
    
    # Inventory page should show devices
    inventory_page = window.inventory_page
    inventory_page.load_devices()
    assert inventory_page.table.rowCount() > 0
    
    window.close()


@pytest.mark.timeout(30)
def test_control_center_loads_actions(qapp, qtbot, mocker):
    """Test that Control Center loads action catalog."""
    from ciscoman_gui.windows.control_center_page import ControlCenterPage
    from ciscoman_gui.windows.main_window import MainWindow
    from ciscoman_core import database as db
    
    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    
    # Mock the login dialog
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.exec', return_value=True)
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.get_key', return_value=key)
    
    window = MainWindow()
    window.session_key = key
    qtbot.addWidget(window)
    
    # Control Center page
    cc_page = window.control_center_page
    
    # Should have action tabs
    assert cc_page.action_tabs.count() > 0
    
    window.close()


@pytest.mark.timeout(30)
def test_scanner_page_ui(qapp, qtbot, mocker):
    """Test scanner page UI elements."""
    from ciscoman_gui.windows.scanner_page import ScannerPage
    from ciscoman_gui.windows.main_window import MainWindow
    from ciscoman_core import database as db
    
    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    
    # Mock the login dialog
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.exec', return_value=True)
    mocker.patch('ciscoman_gui.windows.main_window.LoginDialog.get_key', return_value=key)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    scanner = window.scanner_page
    
    # Should have input fields
    assert scanner.target_input is not None
    assert scanner.port_spin is not None
    assert scanner.scan_btn is not None
    assert scanner.table.columnCount() == 8
    assert scanner.table.isSortingEnabled()
    
    window.close()
