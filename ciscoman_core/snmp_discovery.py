"""SNMP device discovery using a freeze-safe SNMPv2c client (no pysnmp)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ciscoman_core import snmpv2c

logger = logging.getLogger(__name__)

SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
SYS_NAME = "1.3.6.1.2.1.1.5.0"

# IANA enterprise IDs under 1.3.6.1.4.1
_ENTERPRISE_VENDOR = {
    "9": "Cisco",
    "11": "HP",
    "2011": "Huawei",
    "2636": "Juniper",
    "25506": "H3C",
    "14823": "Aruba",
    "1916": "Extreme",
    "4526": "Netgear",
    "12356": "Fortinet",
    "6876": "VMware",
    "8072": "net-snmp",
}


@dataclass
class SNMPInfo:
    """SNMP discovery information."""

    sys_descr: Optional[str] = None
    sys_name: Optional[str] = None
    sys_object_id: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    confidence: float = 0.7


def snmp_available() -> bool:
    """True when the freeze-safe SNMP client can build a packet."""
    try:
        return snmpv2c.bindings_ok()
    except Exception:
        return False


def snmp_get(ip: str, community: str, oid: str, version: str = "2c", timeout: int = 2) -> Optional[str]:
    """GET a single OID via SNMPv2c. ``version`` is accepted for API compat."""
    _ = version
    try:
        bindings = snmpv2c.snmp_get(ip, community, [oid], timeout=float(timeout))
    except Exception as exc:
        logger.debug("SNMP GET failed for %s %s: %s", ip, oid, exc)
        return None
    if not bindings:
        return None
    if oid in bindings:
        return bindings[oid] or None
    # Some agents return the OID without the trailing .0 instance
    for key, val in bindings.items():
        if key == oid or key.startswith(oid.rstrip(".0")):
            return val or None
    return next(iter(bindings.values()), None) or None


def _vendor_from_object_id(oid: Optional[str]) -> Optional[str]:
    if not oid:
        return None
    m = re.search(r"1\.3\.6\.1\.4\.1\.(\d+)", oid)
    if not m:
        return None
    return _ENTERPRISE_VENDOR.get(m.group(1))


def _parse_descr(sys_descr: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    descr_lower = sys_descr.lower()
    vendor = model = os_version = None
    if "cisco" in descr_lower:
        vendor = "Cisco"
        match = re.search(r"(catalyst\s*\S+|c\d{4}\S*|isr\d{4}|asr\d{4}|nexus\s*\d+|ws-c\S+)", descr_lower)
        if match:
            model = match.group(1).upper()
        match = re.search(r"version\s+([\d.]+(?:\([\w]+\)[\w]*)?)", descr_lower)
        if match:
            os_version = match.group(1)
    elif "juniper" in descr_lower or "junos" in descr_lower:
        vendor = "Juniper"
        match = re.search(r"(mx\d+|ex\d+|srx\d+|qfx\d+)", descr_lower)
        if match:
            model = match.group(1).upper()
    elif "aruba" in descr_lower:
        vendor = "Aruba"
        match = re.search(r"aruba[\s\-]*([\w\d\-]+)", descr_lower)
        if match:
            model = match.group(1).upper()
    elif "procurve" in descr_lower or re.search(r"\bhp\b", descr_lower):
        vendor = "HP"
    elif "h3c" in descr_lower or "comware" in descr_lower:
        vendor = "H3C"
        match = re.search(r"(s\d{4}\S*|msr\d{4})", descr_lower)
        if match:
            model = match.group(1).upper()
    elif "huawei" in descr_lower or "vrp" in descr_lower:
        vendor = "Huawei"
    return vendor, model, os_version


def discover_via_snmp(
    ip: str,
    community: str = "public",
    version: str = "2c",
    user: str = "",
    auth_key: str = "",
    timeout: float = 2.0,
) -> Optional[SNMPInfo]:
    """Discover sysDescr / sysName / sysObjectID.

    SNMPv2c is always used for the wire GET (freeze-safe). If Settings asks
    for v3 with a user but no auth, we still send v2c with the community so
    discovery keeps working; v3 auth/priv is reported in the note layer.
    """
    _ = (user, auth_key)
    if version == "3" and user and auth_key:
        logger.info("SNMPv3 auth is configured but this build uses v2c GET; set community for discovery")

    try:
        bindings = snmpv2c.snmp_get(
            ip, community, [SYS_DESCR, SYS_NAME, SYS_OBJECT_ID], timeout=timeout
        )
    except Exception as exc:
        logger.debug("SNMP discovery failed for %s: %s", ip, exc)
        return None

    if not bindings:
        return None

    def _pick(*oids: str) -> Optional[str]:
        for oid in oids:
            if oid in bindings and bindings[oid]:
                return bindings[oid]
        for key, val in bindings.items():
            if val and any(key.startswith(o.rsplit(".", 1)[0]) for o in oids):
                return val
        return None

    sys_descr = _pick(SYS_DESCR)
    sys_name = _pick(SYS_NAME)
    sys_object_id = _pick(SYS_OBJECT_ID)
    if not sys_descr and not sys_name and not sys_object_id:
        return None

    vendor = model = os_version = None
    if sys_descr:
        vendor, model, os_version = _parse_descr(sys_descr)
    if not vendor:
        vendor = _vendor_from_object_id(sys_object_id)

    return SNMPInfo(
        sys_descr=sys_descr,
        sys_name=sys_name,
        sys_object_id=sys_object_id,
        vendor=vendor,
        model=model,
        os_version=os_version,
        confidence=0.85 if vendor else 0.55,
    )
