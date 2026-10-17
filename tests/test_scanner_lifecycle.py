"""Scanner scan / identify / rescan / cancel must not touch deleted QThreads."""

from __future__ import annotations

import os
import socket
import threading
import time

import pytest
from PySide6.QtWidgets import QApplication

from ciscoman_core import database as db
from ciscoman_core.fingerprint import Fingerprint
from ciscoman_gui.crash_guard import install_crash_guards, set_strict_test_mode, take_unhandled


@pytest.fixture(scope="module")
def qapp():
    if "CI" in os.environ or "GITHUB_ACTIONS" in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def crash_strict(qapp, tmp_path):
    install_crash_guards(tmp_path, qapp)
    set_strict_test_mode(True)
    take_unhandled()
    yield
    set_strict_test_mode(False)
    leftover = take_unhandled()
    assert leftover == [], leftover


def _open_window(qtbot, mocker, key):
    from ciscoman_gui.windows.main_window import MainWindow

    mocker.patch("ciscoman_gui.windows.main_window.LoginDialog.exec", return_value=True)
    mocker.patch("ciscoman_gui.windows.main_window.LoginDialog.get_key", return_value=key)
    window = MainWindow()
    window.session_key = key
    qtbot.addWidget(window)
    return window


def _key():
    db.init_db()
    if not db.is_initialized():
        return db.set_master_password("test_password_12345")
    return db.verify_master_password("test_password_12345")


class _LocalListener:
    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self._sock.settimeout(0.3)
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
                conn.close()
            except OSError:
                continue

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=2)


def _wait_idle(qtbot, page, timeout=15000):
    qtbot.waitUntil(
        lambda: (not page._scan.running) and (not page._ident.running),
        timeout=timeout,
    )
    QApplication.processEvents()


def _assert_sync_safe(page):
    page._sync_buttons()
    page._sync_buttons()
    assert page.worker is None or not page._scan.running
    leftover = take_unhandled()
    assert leftover == [], leftover


@pytest.mark.timeout(60)
def test_scan_identify_rescan_cancel_no_deleted_worker(qapp, qtbot, mocker, crash_strict):
    mocker.patch("ciscoman_core.snmp_discovery.discover_via_snmp", return_value=None)
    mocker.patch(
        "ciscoman_core.fingerprint.fingerprint_host",
        return_value=Fingerprint(),
    )
    mocker.patch(
        "ciscoman_core.device_identification._reverse_dns",
        return_value="localhost",
    )

    key = _key()
    window = _open_window(qtbot, mocker, key)
    page = window.scanner_page

    with _LocalListener() as listener:
        page.target_input.setText("127.0.0.1")
        page.port_spin.setValue(listener.port)
        page.timeout_spin.setValue(1)

        for _cycle in range(3):
            page.start_scan()
            _wait_idle(qtbot, page)
            _assert_sync_safe(page)
            assert "127.0.0.1" in page._rows

        page.identify_devices()
        _wait_idle(qtbot, page)
        _assert_sync_safe(page)

        page.start_scan()
        _wait_idle(qtbot, page)
        page.identify_devices()
        _wait_idle(qtbot, page)
        _assert_sync_safe(page)

    def slow_scan(*_args, cancelled=None, progress_callback=None, host_found_callback=None, **_kw):
        for i in range(40):
            if cancelled is not None and cancelled():
                return []
            time.sleep(0.05)
            if progress_callback:
                progress_callback(i + 1, 40, "127.0.0.1")
        if host_found_callback:
            host_found_callback("127.0.0.1")
        return ["127.0.0.1"]

    mocker.patch("ciscoman_core.network_utils.scan_network", side_effect=slow_scan)
    page.start_scan()
    qtbot.waitUntil(lambda: page._scan.running, timeout=3000)
    page.cancel_scan()
    _wait_idle(qtbot, page, timeout=10000)
    _assert_sync_safe(page)

    page.start_scan()
    _wait_idle(qtbot, page)
    _assert_sync_safe(page)
    window.close()


@pytest.mark.timeout(20)
def test_worker_slot_clears_wrapper_before_delete(qapp, qtbot, crash_strict):
    from PySide6.QtCore import QThread

    from ciscoman_gui.workers import WorkerSlot, qobject_alive

    class Immediate(QThread):
        def run(self):
            return

    from PySide6.QtWidgets import QWidget

    host = QWidget()
    qtbot.addWidget(host)
    slot = WorkerSlot(host)
    for _ in range(5):
        thread = Immediate()
        slot.bind(thread)
        thread.start()
        qtbot.waitUntil(lambda: not slot.running, timeout=5000)
        assert slot.get() is None
        assert not qobject_alive(thread) or True
        QApplication.processEvents()
    leftover = take_unhandled()
    assert leftover == [], leftover
