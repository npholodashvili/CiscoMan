"""Parse Cisco / H3C ARP and MAC tables from a managed switch."""

from __future__ import annotations

import re
from typing import Optional

from ciscoman_core.mac_discovery import normalize_mac


_IP = r"(\d{1,3}(?:\.\d{1,3}){3})"
# Cisco dotted 0000.0c11.2233 and H3C dashed 00aa-bbcc-ddee (4-4-4)
_MAC_GROUP4 = r"([0-9a-fA-F]{4}[.\-][0-9a-fA-F]{4}[.\-][0-9a-fA-F]{4})"
# Windows / IEEE 00-1b-21-3a-4c-5d or 00:1b:21:3a:4c:5d
_MAC_DASH = r"([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})"
_MAC_CISCO = _MAC_GROUP4


def _norm(mac: str) -> Optional[str]:
    try:
        return normalize_mac(mac)
    except ValueError:
        return None


def parse_arp_table(text: str) -> dict[str, str]:
    """Parse `show ip arp` / `display arp` into {ip: mac}."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        ip_m = re.search(_IP, line)
        if not ip_m:
            continue
        ip = ip_m.group(1)
        mac = None
        m = re.search(_MAC_CISCO, line)
        if m:
            mac = _norm(m.group(1))
        if not mac:
            m = re.search(_MAC_DASH, line)
            if m:
                mac = _norm(m.group(1))
        if mac:
            result[ip] = mac
    return result


def parse_mac_table(text: str) -> dict[str, str]:
    """Parse `show mac address-table` — keyed by MAC (no IP). Rarely used alone."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        m = re.search(_MAC_CISCO, line)
        if m:
            mac = _norm(m.group(1))
            if mac:
                result[mac] = line.strip()
    return result


def query_device_arp(device: dict) -> tuple[dict[str, str], str]:
    """SSH (or simulator) to an inventory device and collect its ARP table.

    Returns (ip->mac, raw_combined_output).
    """
    from ciscoman_core import network_utils as net

    dtype = (device.get("device_type") or "cisco_ios").lower()
    if "comware" in dtype or "h3c" in dtype:
        commands = ["display arp"]
    else:
        commands = ["show ip arp", "show mac address-table"]
    res = net.run_show_commands(device, commands, use_textfsm=False)
    if not res.success:
        return {}, res.error or "switch ARP query failed"
    table = parse_arp_table(res.output or "")
    return table, res.output or ""
