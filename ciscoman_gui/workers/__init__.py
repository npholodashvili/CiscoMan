"""Worker threads for background operations."""

from ciscoman_gui.workers.device_worker import DeviceWorker, ScanWorker
from ciscoman_gui.workers.identification_worker import IdentificationWorker


def retain_worker(owner, worker):
    """Keep a QThread alive until it finishes, then deleteLater.

    Dropping the last Python reference while the native thread is still
    running is a common source of 0xc0000409 aborts on Windows.
    """
    bag = getattr(owner, "_alive_workers", None)
    if bag is None:
        bag = []
        owner._alive_workers = bag
    bag.append(worker)

    def _cleanup():
        try:
            bag.remove(worker)
        except ValueError:
            pass
        worker.deleteLater()

    worker.finished.connect(_cleanup)
    return worker
