"""Combined device identification using MAC/OUI, SNMP, and reverse DNS.

Identification is designed for batch use:
- Neighbor/ARP table is read **once** (Win32 GetIpNetTable or hidden arp -a).
- No per-IP PowerShell or visible console.
- Hosts on other L2 subnets cannot have a MAC via ARP; we say so and fall
  back to SNMP / reverse DNS.
"""

from __future__ import annotations

import logging
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from ciscoman_core import database as db
from ciscoman_core import mac_discovery
from ciscoman_core import snmp_discovery
from ciscoman_core import win_native

logger = logging.getLogger(__name__)


@dataclass
class DeviceIdentity:
    """Complete device identification result. Always produced for a scanned IP."""

    ip: str
    mac: Optional[str] = None
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    device_type: Optional[str] = None
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    snmp_info: Optional[snmp_discovery.SNMPInfo] = None
    mac_info: Optional[mac_discovery.MACInfo] = None
    note: str = ""
    on_link: bool = True

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "model": self.model,
            "os_version": self.os_version,
            "device_type": self.device_type,
            "sources": ", ".join(self.sources),
            "confidence": f"{self.confidence:.0%}",
            "note": self.note,
        }

    @property
    def source_label(self) -> str:
        if "snmp" in self.sources and ("oui-db" in self.sources or "oui-online" in self.sources):
            return "SNMP + OUI"
        if "snmp" in self.sources:
            return "SNMP"
        if "lldp" in self.sources or "cdp" in self.sources:
            return "LLDP/CDP"
        if "oui-db" in self.sources or "oui-online" in self.sources:
            return "OUI vendor only"
        if "arp" in self.sources:
            return "ARP (no vendor)"
        if "dns" in self.sources:
            return "DNS only"
        if not self.on_link:
            return "Remote subnet (no ARP)"
        return "Unknown"

    @property
    def identified(self) -> bool:
        return bool(self.vendor or self.hostname or self.mac or self.model)


def _suggest_device_type(vendor: Optional[str], model: Optional[str], os_version: Optional[str]) -> Optional[str]:
    if not vendor:
        return None
    v = vendor.lower()
    m = (model or "").lower()
    o = (os_version or "").lower()
    if "cisco" in v:
        if "nexus" in m:
            return "cisco_nxos"
        if "xe" in o:
            return "cisco_xe"
        return "cisco_ios"
    if "juniper" in v:
        return "juniper_junos"
    if "aruba" in v:
        return "aruba_os"
    if "hp" in v:
        return "hp_procurve"
    if "h3c" in v:
        return "hp_comware"
    return None


def _reverse_dns(ip: str) -> Optional[str]:
    try:
        name, _aliases, _ = socket.gethostbyaddr(ip)
        return name.rstrip(".")
    except Exception:
        return None


def _apply_mac(result: DeviceIdentity, mac: str, online_oui: bool) -> None:
    result.mac = mac
    if "arp" not in result.sources:
        result.sources.append("arp")
    mac_info = mac_discovery.identify_mac(mac, online_enabled=online_oui)
    if mac_info:
        result.mac_info = mac_info
        result.vendor = mac_info.vendor
        result.sources.append(mac_info.source)
        result.confidence = max(result.confidence, mac_info.confidence * 0.7)


def _apply_snmp(result: DeviceIdentity, snmp_info: snmp_discovery.SNMPInfo) -> None:
    result.snmp_info = snmp_info
    if "snmp" not in result.sources:
        result.sources.append("snmp")
    if snmp_info.sys_name and not result.hostname:
        result.hostname = snmp_info.sys_name
    if snmp_info.vendor:
        result.vendor = snmp_info.vendor
        result.confidence = max(result.confidence, snmp_info.confidence)
    if snmp_info.model:
        result.model = snmp_info.model
    if snmp_info.os_version:
        result.os_version = snmp_info.os_version


def identify_device(
    ip: str,
    try_snmp: bool = True,
    snmp_community: Optional[str] = None,
    online_oui: bool = False,
    ping_first: bool = False,
    arp_table: Optional[dict[str, str]] = None,
    local_nets: Optional[list] = None,
) -> DeviceIdentity:
    """Identify one host. Prefer identify_hosts() so ARP is only read once.

    ping_first is ignored for per-IP subprocesses — use a single ICMP sweep
    from the worker if you need to populate the neighbor cache.
    """
    _ = ping_first  # kept for call-site compatibility; must not spawn per-IP
    result = DeviceIdentity(ip=ip)
    nets = local_nets if local_nets is not None else win_native.local_ipv4_networks()
    result.on_link = win_native.is_on_link(ip, nets)

    table = arp_table if arp_table is not None else win_native.get_arp_table()
    mac = table.get(ip)
    if mac:
        _apply_mac(result, mac, online_oui)
    elif not result.on_link:
        result.note = (
            "Remote subnet — this PC has no L2 ARP entry. "
            "MAC requires SNMP or a switch/router ARP table."
        )
    else:
        result.note = "On-link but no neighbor entry. Host may have gone quiet after the scan."

    if try_snmp:
        community = snmp_community or db.get_setting("snmp_community", "public")
        try:
            snmp_info = snmp_discovery.discover_via_snmp(ip, community)
        except Exception as exc:
            logger.debug("SNMP failed for %s: %s", ip, exc)
            snmp_info = None
        if snmp_info:
            _apply_snmp(result, snmp_info)
            if not result.on_link:
                result.note = "Remote subnet; identity from SNMP (no local ARP)."

    if not result.hostname:
        name = _reverse_dns(ip)
        if name:
            result.hostname = name
            result.sources.append("dns")
            result.confidence = max(result.confidence, 0.35)

    result.device_type = _suggest_device_type(result.vendor, result.model, result.os_version)
    if len(result.sources) >= 2:
        result.confidence = min(1.0, result.confidence + 0.1)
    return result


def identify_hosts(
    ips: list[str],
    try_snmp: bool = True,
    snmp_community: Optional[str] = None,
    online_oui: bool = False,
    max_workers: int = 8,
    progress_callback=None,
    cancelled=None,
) -> list[DeviceIdentity]:
    """Identify many hosts: one ARP read, bounded thread pool for SNMP/DNS."""
    table = win_native.get_arp_table()
    nets = win_native.local_ipv4_networks()
    community = snmp_community or db.get_setting("snmp_community", "public")
    results: dict[str, DeviceIdentity] = {}
    total = len(ips)

    def _one(ip: str) -> DeviceIdentity:
        return identify_device(
            ip,
            try_snmp=try_snmp,
            snmp_community=community,
            online_oui=online_oui,
            arp_table=table,
            local_nets=nets,
        )

    workers = max(1, min(max_workers, total or 1))
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, ip): ip for ip in ips}
        for fut in as_completed(futures):
            if cancelled is not None and cancelled():
                for pending in futures:
                    pending.cancel()
                break
            ip = futures[fut]
            try:
                ident = fut.result()
            except Exception as exc:
                logger.error("Identification failed for %s: %s", ip, exc)
                ident = DeviceIdentity(ip=ip, note=str(exc))
            results[ip] = ident
            done += 1
            if progress_callback:
                progress_callback(done, total, ident)

    # Stable order matching the input list
    return [results[ip] for ip in ips if ip in results]


def format_identification_summary(ident: DeviceIdentity) -> str:
    lines = [f"Device: {ident.ip}"]
    if ident.hostname:
        lines.append(f"  Hostname: {ident.hostname}")
    if ident.mac:
        lines.append(f"  MAC: {ident.mac}")
    if ident.vendor:
        lines.append(f"  Vendor: {ident.vendor}")
    if ident.model:
        lines.append(f"  Model: {ident.model}")
    if ident.os_version:
        lines.append(f"  OS: {ident.os_version}")
    if ident.device_type:
        lines.append(f"  Suggested Type: {ident.device_type}")
    lines.append(f"  Sources: {', '.join(ident.sources) or ident.source_label}")
    lines.append(f"  Confidence: {ident.confidence:.0%}")
    if ident.note:
        lines.append(f"  Note: {ident.note}")
    return "\n".join(lines)
