"""Worker threads for device operations."""

import logging
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal, QThread

from ciscoman_core import network_utils as net

logger = logging.getLogger(__name__)


class DeviceWorkerSignals(QObject):
    """Signals for device worker."""
    progress = Signal(int, int)  # (done, total)
    result = Signal(object)  # ExecResult
    finished = Signal()
    error = Signal(str)


class DeviceWorker(QThread):
    """Worker thread for device operations with progress and cancel support."""
    
    def __init__(self, devices: list, task: Callable, progress_callback: Optional[Callable] = None):
        super().__init__()
        self.devices = devices
        self.task = task
        self.progress_callback = progress_callback
        self.signals = DeviceWorkerSignals()
        self._is_cancelled = False
    
    def run(self):
        """Execute the task on all devices."""
        try:
            def wrapped_callback(done: int, total: int, result: net.ExecResult):
                if self._is_cancelled:
                    return
                self.signals.progress.emit(done, total)
                self.signals.result.emit(result)
                if self.progress_callback:
                    self.progress_callback(done, total, result)
            
            results = net.mass_execute(
                self.devices,
                self.task,
                progress_callback=wrapped_callback
            )
            
            if not self._is_cancelled:
                self.signals.finished.emit()
        except Exception as e:
            logger.exception("Device worker error")
            self.signals.error.emit(str(e))
    
    def cancel(self):
        """Cancel the operation."""
        self._is_cancelled = True
        logger.info("Device worker cancelled")


class ScanWorkerSignals(QObject):
    """Signals for scan worker."""
    progress = Signal(int, int, str)  # (done, total, current_ip)
    host_found = Signal(str)  # streamed as each live host is found
    finished = Signal(list)  # List of alive IPs
    error = Signal(str)


class ScanWorker(QThread):
    """Worker thread for network scanning."""
    
    def __init__(self, target: str, port: int, timeout: float):
        super().__init__()
        self.target = target
        self.port = port
        self.timeout = timeout
        self.signals = ScanWorkerSignals()
        self._is_cancelled = False
    
    def run(self):
        """Execute the scan."""
        try:
            seen: set[str] = set()

            def progress_cb(done: int, total: int, ip: str):
                if self._is_cancelled:
                    return
                self.signals.progress.emit(done, total, ip)

            def found_cb(ip: str):
                if self._is_cancelled or ip in seen:
                    return
                seen.add(ip)
                self.signals.host_found.emit(ip)

            alive = net.scan_network(
                self.target,
                port=self.port,
                timeout=self.timeout,
                progress_callback=progress_cb,
                host_found_callback=found_cb,
            )
            
            if not self._is_cancelled:
                self.signals.finished.emit(alive)
        except Exception as e:
            logger.exception("Scan worker error")
            self.signals.error.emit(str(e))
    
    def cancel(self):
        """Cancel the scan."""
        self._is_cancelled = True
        logger.info("Scan worker cancelled")
