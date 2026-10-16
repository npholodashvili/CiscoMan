"""Worker for batch device identification — one ARP read, bounded thread pool."""

import logging

from PySide6.QtCore import QThread, Signal

from ciscoman_core import database as db
from ciscoman_core import device_identification

logger = logging.getLogger(__name__)


class IdentificationWorker(QThread):
    """Identify many hosts without per-IP subprocesses or console windows."""

    progress = Signal(int, int, object)
    finished = Signal()
    error = Signal(str)

    def __init__(self, ip_list: list[str]):
        super().__init__()
        self.ip_list = list(ip_list)
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            online_oui = db.get_setting("online_oui_lookup", "0") == "1"
            snmp_community = db.get_setting("snmp_community", "public")

            def on_progress(done, total, ident):
                if not self.cancelled:
                    self.progress.emit(done, total, ident)

            device_identification.identify_hosts(
                self.ip_list,
                try_snmp=True,
                snmp_community=snmp_community,
                online_oui=online_oui,
                max_workers=8,
                progress_callback=on_progress,
                cancelled=lambda: self.cancelled,
            )
            self.finished.emit()
        except Exception as e:
            logger.exception("Identification worker error")
            self.error.emit(str(e))
