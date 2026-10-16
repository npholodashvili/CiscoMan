"""Worker for device identification."""

import logging
from PySide6.QtCore import QThread, Signal
from dataclasses import asdict

from ciscoman_core import device_identification, database as db

logger = logging.getLogger(__name__)


class IdentificationWorker(QThread):
    """Worker thread for device identification."""
    
    progress = Signal(int, int, object)  # current, total, result
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, ip_list: list[str]):
        super().__init__()
        self.ip_list = ip_list
        self.cancelled = False
    
    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
    
    def run(self):
        """Run identification for all IPs."""
        try:
            # Get settings
            online_oui = db.get_setting("online_oui_lookup", "0") == "1"
            snmp_community = db.get_setting("snmp_community", "public")
            
            total = len(self.ip_list)
            
            for i, ip in enumerate(self.ip_list):
                if self.cancelled:
                    break
                
                try:
                    # Identify device
                    ident = device_identification.identify_device(
                        ip,
                        try_snmp=True,
                        snmp_community=snmp_community,
                        online_oui=online_oui,
                        ping_first=True
                    )
                    
                    # Emit result (even if None)
                    self.progress.emit(i + 1, total, ident)
                    
                except Exception as e:
                    logger.error(f"Identification failed for {ip}: {e}")
                    self.progress.emit(i + 1, total, None)
            
            self.finished.emit()
            
        except Exception as e:
            logger.error(f"Identification worker error: {e}")
            self.error.emit(str(e))
