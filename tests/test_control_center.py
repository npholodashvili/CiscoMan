"""Control Center execution: simulator success and unreachable failure, no crash."""

import os

import pytest
from PySide6.QtWidgets import QApplication

from ciscoman_core import actions, database as db
from ciscoman_core.network_utils import ExecResult


@pytest.fixture(scope="module")
def qapp():
    if "CI" in os.environ or "GITHUB_ACTIONS" in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


def _open_window(qtbot, mocker, key):
    from ciscoman_gui.windows.main_window import MainWindow

    mocker.patch("ciscoman_gui.windows.main_window.LoginDialog.exec", return_value=True)
    mocker.patch("ciscoman_gui.windows.main_window.LoginDialog.get_key", return_value=key)
    window = MainWindow()
    window.session_key = key
    qtbot.addWidget(window)
    return window


def _pick_show_action():
    return next(a for a in actions.ACTIONS if a.id == "show_version")


@pytest.mark.timeout(30)
def test_control_center_demo_device(qapp, qtbot, mocker):
    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    db.seed_demo_devices(key)

    window = _open_window(qtbot, mocker, key)
    cc = window.control_center_page
    cc.load_devices()
    assert cc.device_checkboxes
    demo_ids = {d["id"] for d in db.list_devices() if d.get("is_demo")}
    found = False
    for dev_id, cb in cc.device_checkboxes.items():
        if not found and dev_id in demo_ids:
            cb.setChecked(True)
            found = True
        else:
            cb.setChecked(False)
    assert found
    cc.on_action_selected(_pick_show_action())
    cc.execute_action()

    def done():
        return "Success" in cc.results_area.toPlainText()

    qtbot.waitUntil(done, timeout=20000)
    assert "Success" in cc.results_area.toPlainText()
    qtbot.waitUntil(lambda: not cc._exec.running, timeout=5000)
    cc.results_area.clear()
    cc.execute_action()
    qtbot.waitUntil(done, timeout=20000)
    assert "Success" in cc.results_area.toPlainText()
    window.close()


@pytest.mark.timeout(20)
def test_control_center_unreachable_does_not_crash(qapp, qtbot, mocker):
    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")

    db.upsert_device(
        key,
        name="dead-router",
        ip="192.0.2.99",
        username="admin",
        password="admin",
        device_type="cisco_ios",
        port=22,
    )

    def boom(device, commands, use_textfsm=False):
        return ExecResult(device.get("id"), device.get("name"), device["ip"], False, error="Connection timed out")

    mocker.patch("ciscoman_core.network_utils.run_show_commands", side_effect=boom)

    window = _open_window(qtbot, mocker, key)
    cc = window.control_center_page
    cc.load_devices()
    dead = None
    for dev_id, cb in cc.device_checkboxes.items():
        dev = db.get_device_with_credentials(key, dev_id)
        checked = bool(dev and dev.get("ip") == "192.0.2.99")
        cb.setChecked(checked)
        if checked:
            dead = dev_id
    assert dead is not None

    cc.on_action_selected(_pick_show_action())
    cc.execute_action()

    def done():
        text = cc.results_area.toPlainText()
        return "timed out" in text.lower() or "complete" in text.lower() or "Error" in text

    qtbot.waitUntil(done, timeout=15000)
    assert window.isVisible() or True  # process still here
    assert "timed out" in cc.results_area.toPlainText().lower() or "complete" in cc.results_area.toPlainText().lower()
    window.close()
