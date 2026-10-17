"""Worker threads for background operations.

QThread objects are owned by a WorkerSlot on the GUI thread. Running state is a
plain enum updated by started/finished — pages must never call isRunning() on a
finished wrapper (that is the ScanWorker-already-deleted crash).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Slot

from ciscoman_gui.workers.device_worker import DeviceWorker, ScanWorker
from ciscoman_gui.workers.identification_worker import IdentificationWorker

__all__ = [
    "DeviceWorker",
    "ScanWorker",
    "IdentificationWorker",
    "WorkerSlot",
    "qobject_alive",
    "retain_worker",
]


def qobject_alive(obj) -> bool:
    """True if the Shiboken wrapper still has a C++ QObject."""
    if obj is None:
        return False
    try:
        from shiboken6 import isValid

        return bool(isValid(obj))
    except Exception:
        try:
            obj.objectName()
            return True
        except RuntimeError:
            return False


class WorkerSlot(QObject):
    """One QThread at a time. `running` is a bool; the wrapper is cleared first."""

    IDLE = "idle"
    RUNNING = "running"

    def __init__(self, owner: QObject):
        super().__init__(owner)
        self._owner = owner
        self._worker: QThread | None = None
        self.state = self.IDLE

    @property
    def running(self) -> bool:
        return self.state == self.RUNNING

    def get(self) -> QThread | None:
        worker = self._worker
        if worker is None:
            return None
        if not qobject_alive(worker):
            self._worker = None
            self.state = self.IDLE
            return None
        return worker

    def bind(self, worker: QThread) -> QThread:
        """Take ownership of ``worker``. Replaces any previous thread."""
        self.release()
        worker.setParent(self._owner)
        self._worker = worker
        self.state = self.RUNNING
        worker.started.connect(self._on_started, Qt.QueuedConnection)
        worker.finished.connect(self._on_finished, Qt.QueuedConnection)
        return worker

    @Slot()
    def _on_started(self) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._worker:
            return
        self.state = self.RUNNING

    @Slot()
    def _on_finished(self) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._worker:
            if qobject_alive(sender):
                sender.deleteLater()
            return
        self.state = self.IDLE
        worker = self._worker
        self._worker = None
        if worker is not None and qobject_alive(worker):
            worker.deleteLater()

    def cancel(self) -> None:
        worker = self.get()
        if worker is None:
            return
        if hasattr(worker, "cancel"):
            try:
                worker.cancel()
            except RuntimeError:
                return

    def release(self) -> None:
        """Cancel + wait + deleteLater any current worker, then forget it."""
        worker = self._worker
        self._worker = None
        self.state = self.IDLE
        if worker is None or not qobject_alive(worker):
            return
        if hasattr(worker, "cancel"):
            try:
                worker.cancel()
            except RuntimeError:
                return
        try:
            if worker.isRunning():
                worker.wait(2000)
        except RuntimeError:
            return
        if qobject_alive(worker):
            worker.deleteLater()


def retain_worker(owner, worker):
    """Back-compat: parent the thread to ``owner`` and return it.

    Prefer WorkerSlot.bind() so the Python wrapper is cleared before deleteLater.
    """
    slot = getattr(owner, "_compat_slot", None)
    if slot is None:
        slot = WorkerSlot(owner)
        owner._compat_slot = slot
    slot.bind(worker)
    return worker
