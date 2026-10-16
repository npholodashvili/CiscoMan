"""Worker threads for device operations. UI is updated only via queued signals."""

import logging
from typing import Callable
from PySide6.QtCore import Signal, QThread

from ciscoman_core import network_utils as net

logger = logging.getLogger(__name__)


class DeviceWorker(QThread):
    """Run a task on many devices. Never touch widgets from run()."""

    progress = Signal(int, int)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, devices: list, task: Callable, progress_callback=None):
        super().__init__()
        self.devices = devices
        self.task = task
        # progress_callback is ignored — callers must connect to `result`/`progress`.
        self._is_cancelled = False
        # Back-compat alias so older pages that used worker.signals.finished still
        # have something to connect; prefer QThread.finished + result.
        self.signals = self

    def run(self):
        try:
            def wrapped_callback(done: int, total: int, result: net.ExecResult):
                if self._is_cancelled:
                    return
                self.progress.emit(done, total)
                self.result.emit(result)

            net.mass_execute(
                self.devices,
                self.task,
                progress_callback=wrapped_callback,
            )
        except Exception as e:
            logger.exception("Device worker error")
            self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
        logger.info("Device worker cancelled")


class ScanWorker(QThread):
    """Network scan worker. Emits host_found as each live host appears."""

    progress = Signal(int, int, str)
    host_found = Signal(str)
    scan_finished = Signal(list)
    error = Signal(str)

    def __init__(self, target: str, port: int, timeout: float):
        super().__init__()
        self.target = target
        self.port = port
        self.timeout = timeout
        self._is_cancelled = False
        self.signals = self

    def run(self):
        try:
            seen: set[str] = set()

            def progress_cb(done: int, total: int, ip: str):
                if not self._is_cancelled:
                    self.progress.emit(done, total, ip)

            def found_cb(ip: str):
                if self._is_cancelled or ip in seen:
                    return
                seen.add(ip)
                self.host_found.emit(ip)

            alive = net.scan_network(
                self.target,
                self.port,
                self.timeout,
                progress_callback=progress_cb,
                host_found_callback=found_cb,
            )
            if not self._is_cancelled:
                self.scan_finished.emit(alive)
        except Exception as e:
            logger.exception("Scan worker error")
            self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
        logger.info("Scan worker cancelled")
