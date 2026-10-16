"""Batch identification — ARP once, optional switch ARP, bounded pool."""

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal

from ciscoman_core import database as db
from ciscoman_core import device_identification
from ciscoman_core import switch_arp

logger = logging.getLogger(__name__)


class IdentificationWorker(QThread):
    progress = Signal(int, int, object)
    error = Signal(str)
    switch_arp_note = Signal(str)

    def __init__(
        self,
        ip_list: list[str],
        switch_device: Optional[dict] = None,
        extra_arp: Optional[dict] = None,
    ):
        super().__init__()
        self.ip_list = list(ip_list)
        self.switch_device = switch_device
        self.extra_arp = dict(extra_arp or {})
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            if self.switch_device and not self.cancelled:
                table, raw = switch_arp.query_device_arp(self.switch_device)
                self.extra_arp.update(table)
                self.switch_arp_note.emit(
                    f"Switch ARP: {len(table)} entries from {self.switch_device.get('name', '')}"
                    if table
                    else f"Switch ARP query returned no entries ({raw[:160]})"
                )

            online_oui = db.get_setting("online_oui_lookup", "0") == "1"
            community = db.get_setting("snmp_community", "public")
            version = db.get_setting("snmp_version", "2c")
            user = db.get_setting("snmp_user", "")
            auth = db.get_setting("snmp_auth", "")

            def on_progress(done, total, ident):
                if not self.cancelled:
                    self.progress.emit(done, total, ident)

            device_identification.identify_hosts(
                self.ip_list,
                try_snmp=True,
                snmp_community=community,
                online_oui=online_oui,
                max_workers=8,
                progress_callback=on_progress,
                cancelled=lambda: self.cancelled,
                extra_arp=self.extra_arp or None,
                try_fingerprint=True,
                snmp_version=version,
                snmp_user=user,
                snmp_auth=auth,
            )
        except Exception as e:
            logger.exception("Identification worker error")
            self.error.emit(str(e))
