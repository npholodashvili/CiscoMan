"""Device identification: ARP (local or switch), OUI, SNMP, SSH/HTTP, DNS."""

from __future__ import annotations

import logging
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from ciscoman_core import database as db
from ciscoman_core import fingerprint as fingerprint_mod
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
    ssh_banner: Optional[str] = None
    http_title: Optional[str] = None

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
        if "snmp" in self.sources and any(s.startswith("oui") for s in self.sources):
            return "SNMP + OUI"
        if "snmp" in self.sources:
            return "SNMP"
        if "switch-arp" in self.sources and any(s.startswith("oui") for s in self.sources):
            return "Switch ARP + OUI"
        if "ssh-banner" in self.sources:
            return "SSH banner"
        if "http" in self.sources:
            return "HTTP fingerprint"
        if "lldp" in self.sources or "cdp" in self.sources:
            return "LLDP/CDP"
        if any(s.startswith("oui") for s in self.sources):
            return "OUI vendor only"
        if "switch-arp" in self.sources:
            return "Switch ARP"
        if "arp" in self.sources:
            return "ARP (no vendor)"
        if "dns" in self.sources:
            return "DNS only"
        if not self.on_link:
            return "Remote subnet (no ARP)"
        return "Unknown"

    @property
    def identified(self) -> bool:
        return bool(self.vendor or self.hostname or self.mac or self.model or self.ssh_banner)


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


def _apply_mac(result: DeviceIdentity, mac: str, online_oui: bool, source: str = "arp") -> None:
    result.mac = mac
    if source not in result.sources:
        result.sources.append(source)
    mac_info = mac_discovery.identify_mac(mac, online_enabled=online_oui)
    if mac_info:
        result.mac_info = mac_info
        if not result.vendor:
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


def _compose_note(result: DeviceIdentity, community: str, tried_snmp: bool, tried_fp: bool) -> str:
    if result.identified and result.on_link:
        return result.note
    if result.identified and not result.on_link:
        bits = ["Remote subnet — no local ARP MAC"]
        if "snmp" in result.sources:
            bits.append("identity from SNMP")
        if "switch-arp" in result.sources:
            bits.append("MAC from switch ARP")
        if "ssh-banner" in result.sources:
            bits.append("SSH banner")
        if "http" in result.sources:
            bits.append("HTTP")
        return "; ".join(bits) + "."
    reasons = []
    if not result.on_link:
        reasons.append(
            "Remote subnet: this PC's ARP table cannot see the host MAC"
        )
    elif not result.mac:
        reasons.append("On-link but no neighbor entry after the scan")
    if tried_snmp:
        reasons.append(f"SNMP community '{community}' did not answer on UDP/161")
    if tried_fp:
        reasons.append("no SSH banner and no HTTP/HTTPS title")
    reasons.append("query a gateway/switch ARP table, or set the correct SNMP community in Settings")
    return ". ".join(reasons) + "."


def identify_device(
    ip: str,
    try_snmp: bool = True,
    snmp_community: Optional[str] = None,
    online_oui: bool = False,
    ping_first: bool = False,
    arp_table: Optional[dict[str, str]] = None,
    local_nets: Optional[list] = None,
    extra_arp: Optional[dict[str, str]] = None,
    try_fingerprint: bool = True,
    snmp_version: str = "2c",
    snmp_user: str = "",
    snmp_auth: str = "",
) -> DeviceIdentity:
    """Identify one host. Prefer identify_hosts() so ARP is only read once."""
    _ = ping_first
    result = DeviceIdentity(ip=ip)
    nets = local_nets if local_nets is not None else win_native.local_ipv4_networks()
    result.on_link = win_native.is_on_link(ip, nets)

    table = dict(arp_table if arp_table is not None else win_native.get_arp_table())
    if extra_arp:
        table.update(extra_arp)

    mac = table.get(ip)
    mac_source = "switch-arp" if extra_arp and extra_arp.get(ip) and (
        not arp_table or ip not in (arp_table or {})
    ) else "arp"
    if mac:
        _apply_mac(result, mac, online_oui, source=mac_source)

    community = snmp_community or db.get_setting("snmp_community", "public")
    if try_snmp:
        try:
            snmp_info = snmp_discovery.discover_via_snmp(
                ip, community, version=snmp_version, user=snmp_user, auth_key=snmp_auth
            )
        except Exception as exc:
            logger.debug("SNMP failed for %s: %s", ip, exc)
            snmp_info = None
        if snmp_info:
            _apply_snmp(result, snmp_info)

    if try_fingerprint:
        try:
            fp = fingerprint_mod.fingerprint_host(ip)
        except Exception as exc:
            logger.debug("Fingerprint failed for %s: %s", ip, exc)
            fp = None
        if fp:
            result.ssh_banner = fp.ssh_banner
            result.http_title = fp.http_title
            if fp.ssh_banner and "ssh-banner" not in result.sources:
                result.sources.append("ssh-banner")
                result.confidence = max(result.confidence, 0.45)
            if (fp.http_server or fp.http_title) and "http" not in result.sources:
                result.sources.append("http")
                result.confidence = max(result.confidence, 0.4)
            if fp.vendor and not result.vendor:
                result.vendor = fp.vendor
            if fp.model and not result.model:
                result.model = fp.model

    if not result.hostname:
        name = _reverse_dns(ip)
        if name:
            result.hostname = name
            result.sources.append("dns")
            result.confidence = max(result.confidence, 0.35)

    result.device_type = _suggest_device_type(result.vendor, result.model, result.os_version)
    if len(result.sources) >= 2:
        result.confidence = min(1.0, result.confidence + 0.1)
    result.note = _compose_note(result, community, try_snmp, try_fingerprint)
    return result


def identify_hosts(
    ips: list[str],
    try_snmp: bool = True,
    snmp_community: Optional[str] = None,
    online_oui: bool = False,
    max_workers: int = 8,
    progress_callback=None,
    cancelled=None,
    extra_arp: Optional[dict[str, str]] = None,
    try_fingerprint: bool = True,
    snmp_version: str = "2c",
    snmp_user: str = "",
    snmp_auth: str = "",
) -> list[DeviceIdentity]:
    """Identify many hosts: one local ARP read, bounded pool for SNMP/DNS/HTTP."""
    table = win_native.get_arp_table()
    nets = win_native.local_ipv4_networks()
    community = snmp_community
    if try_snmp and not community:
        community = db.get_setting("snmp_community", "public")
        snmp_version = db.get_setting("snmp_version", snmp_version)
        snmp_user = db.get_setting("snmp_user", snmp_user)
        snmp_auth = db.get_setting("snmp_auth", snmp_auth)
    online_oui = online_oui or db.get_setting("online_oui_lookup", "0") == "1"
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
            extra_arp=extra_arp,
            try_fingerprint=try_fingerprint,
            snmp_version=snmp_version,
            snmp_user=snmp_user,
            snmp_auth=snmp_auth,
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
    if ident.ssh_banner:
        lines.append(f"  SSH: {ident.ssh_banner}")
    if ident.device_type:
        lines.append(f"  Suggested Type: {ident.device_type}")
    lines.append(f"  Sources: {', '.join(ident.sources) or ident.source_label}")
    lines.append(f"  Confidence: {ident.confidence:.0%}")
    if ident.note:
        lines.append(f"  Note: {ident.note}")
    return "\n".join(lines)
