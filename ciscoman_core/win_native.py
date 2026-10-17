"""Windows-native helpers: hidden subprocesses, ARP/neighbor table, ICMP.

Never open a visible console. Prefer Win32 APIs (ctypes) over spawning
powershell/cmd. Subprocess is a last-resort fallback and always uses
CREATE_NO_WINDOW + a hidden STARTUPINFO.
"""

from __future__ import annotations

import ctypes
import ipaddress
import logging
import os
import re
import socket
import struct
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# winbase.h
CREATE_NO_WINDOW = 0x08000000
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0

# MIB_IPNET_TYPE_*
_MIB_IPNET_TYPE_INVALID = 2

# IcmpSendEcho
_IP_SUCCESS = 0


def hidden_startupinfo() -> Optional["subprocess.STARTUPINFO"]:
    """STARTUPINFO that keeps any spawned process off the desktop."""
    if os.name != "nt":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return si


def hidden_creationflags() -> int:
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def run_hidden(
    args: list[str],
    timeout: float = 10,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """Run a subprocess with no console window.

    Tests assert CREATE_NO_WINDOW / STARTF_USESHOWWINDOW are always set on Windows.
    """
    kwargs: dict = {
        "args": args,
        "capture_output": True,
        "timeout": timeout,
        "text": text,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        kwargs["startupinfo"] = hidden_startupinfo()
    return subprocess.run(**kwargs)


def parse_arp_a(output: str) -> dict[str, str]:
    """Parse `arp -a` text into {ip: MAC}.

    Handles English and locale-neutral rows:
      192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic
      10.0.0.1              aa:bb:cc:dd:ee:ff     static
    Skips multicast/broadcast and incomplete entries (ff-ff-ff-ff-ff-ff).
    """
    from ciscoman_core.mac_discovery import normalize_mac

    result: dict[str, str] = {}
    row = re.compile(
        r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})\s+",
        re.MULTILINE,
    )
    for ip, mac in row.findall(output):
        try:
            normalized = normalize_mac(mac)
        except ValueError:
            continue
        if normalized in {"FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"}:
            continue
        if ipaddress.ip_address(ip).is_multicast:
            continue
        result[ip] = normalized
    return result


def _get_arp_table_iphlpapi() -> dict[str, str]:
    """IPv4 neighbor table via GetIpNetTable (no process)."""
    from ciscoman_core.mac_discovery import normalize_mac

    iphlpapi = ctypes.windll.iphlpapi  # type: ignore[attr-defined]
    size = ctypes.c_ulong(0)
    # First call: ERROR_INSUFFICIENT_BUFFER (122) to learn size
    err = iphlpapi.GetIpNetTable(None, ctypes.byref(size), False)
    if size.value == 0:
        return {}

    buf = ctypes.create_string_buffer(size.value)
    err = iphlpapi.GetIpNetTable(buf, ctypes.byref(size), False)
    if err != 0:
        raise OSError(err, "GetIpNetTable failed")

    # MIB_IPNETTABLE: DWORD dwNumEntries; MIB_IPNETROW table[]
    # MIB_IPNETROW is 24 bytes on both 32/64-bit (all DWORD/BYTE[8])
    num = struct.unpack_from("<I", buf, 0)[0]
    offset = 4
    row_size = 24
    result: dict[str, str] = {}
    for _ in range(num):
        if offset + row_size > len(buf):
            break
        _idx, phys_len, phys, addr, typ = struct.unpack_from("<II8sII", buf, offset)
        offset += row_size
        if typ == _MIB_IPNET_TYPE_INVALID or phys_len < 6:
            continue
        ip = socket.inet_ntoa(struct.pack("<I", addr))
        try:
            mac = normalize_mac(phys[:6].hex())
        except ValueError:
            continue
        if mac in {"FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"}:
            continue
        try:
            if ipaddress.ip_address(ip).is_multicast:
                continue
        except ValueError:
            continue
        result[ip] = mac
    return result


def _get_arp_table_arp_a() -> dict[str, str]:
    """Last-resort: hidden `arp -a` (never PowerShell)."""
    completed = run_hidden(["arp", "-a"], timeout=8)
    return parse_arp_a(completed.stdout or "")


def get_arp_table() -> dict[str, str]:
    """Return {ip: MAC} for the local neighbor cache.

    Order: GetIpNetTable (ctypes) → hidden arp -a. Never launches PowerShell.
    """
    if sys.platform == "win32":
        try:
            table = _get_arp_table_iphlpapi()
            if table:
                return table
        except Exception as exc:
            logger.debug("GetIpNetTable failed, falling back to arp -a: %s", exc)
        try:
            return _get_arp_table_arp_a()
        except Exception as exc:
            logger.error("Hidden arp -a failed: %s", exc)
            return {}

    # Non-Windows (dev/CI): try `ip neigh` / `arp -a` hidden
    for args in (["ip", "neigh"], ["arp", "-a"], ["arp", "-an"]):
        try:
            completed = run_hidden(args, timeout=5)
            parsed = parse_arp_a(completed.stdout or "")
            if parsed:
                return parsed
            # `ip neigh`: "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
            from ciscoman_core.mac_discovery import normalize_mac

            extra: dict[str, str] = {}
            for line in (completed.stdout or "").splitlines():
                m = re.match(
                    r"(\d{1,3}(?:\.\d{1,3}){3})\s+.*lladdr\s+([0-9a-fA-F:.-]{11,17})",
                    line,
                )
                if m:
                    try:
                        extra[m.group(1)] = normalize_mac(m.group(2))
                    except ValueError:
                        continue
            if extra:
                return extra
        except Exception:
            continue
    return {}


def local_ipv4_networks() -> list[ipaddress.IPv4Network]:
    """On-link IPv4 networks from this machine's adapters."""
    nets: list[ipaddress.IPv4Network] = []
    if sys.platform == "win32":
        try:
            iphlpapi = ctypes.windll.iphlpapi  # type: ignore[attr-defined]
            size = ctypes.c_ulong(0)
            iphlpapi.GetIpAddrTable(None, ctypes.byref(size), False)
            buf = ctypes.create_string_buffer(size.value)
            if iphlpapi.GetIpAddrTable(buf, ctypes.byref(size), False) != 0:
                raise OSError("GetIpAddrTable failed")
            num = struct.unpack_from("<I", buf, 0)[0]
            # MIB_IPADDRROW: dwAddr, dwIndex, dwMask, dwBCastAddr, dwReasmSize, unused1, wType
            offset = 4
            for _ in range(num):
                addr, _idx, mask = struct.unpack_from("<III", buf, offset)
                offset += 24
                ip = socket.inet_ntoa(struct.pack("<I", addr))
                msk = socket.inet_ntoa(struct.pack("<I", mask))
                if ip.startswith("127."):
                    continue
                try:
                    nets.append(ipaddress.ip_network(f"{ip}/{msk}", strict=False))
                except ValueError:
                    continue
            if nets:
                return nets
        except Exception as exc:
            logger.debug("GetIpAddrTable failed: %s", exc)

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            nets.append(ipaddress.ip_network(f"{ip}/24", strict=False))
    except Exception:
        pass
    return nets


def is_on_link(ip: str, networks: Optional[list[ipaddress.IPv4Network]] = None) -> bool:
    """True if ip is on a locally attached L2 subnet (ARP can see its MAC)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in networks or local_ipv4_networks():
        if addr in net:
            return True
    return False


def icmp_echo(ip: str, timeout_ms: int = 1000) -> bool:
    """ICMP echo via Iphlpapi IcmpSendEcho (no console). Falls back to hidden ping."""
    if sys.platform == "win32":
        try:
            iphlpapi = ctypes.windll.iphlpapi  # type: ignore[attr-defined]
            handle = iphlpapi.IcmpCreateFile()
            if handle in (-1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
                raise OSError("IcmpCreateFile failed")
            try:
                dest = struct.unpack("<I", socket.inet_aton(ip))[0]
                request = ctypes.create_string_buffer(b"CiscoMan", 8)
                reply_size = ctypes.sizeof(ctypes.c_byte) * (8 + 8 + 20 + 8)
                reply = ctypes.create_string_buffer(reply_size)
                count = iphlpapi.IcmpSendEcho(
                    handle, dest, request, 8, None, reply, reply_size, timeout_ms
                )
                return count > 0
            finally:
                iphlpapi.IcmpCloseHandle(handle)
        except Exception as exc:
            logger.debug("IcmpSendEcho failed for %s: %s", ip, exc)

    # Hidden ping fallback — never a visible window
    count_flag = "-n" if os.name == "nt" else "-c"
    wait_args = ["-w", str(timeout_ms)] if os.name == "nt" else ["-W", str(max(1, timeout_ms // 1000))]
    try:
        completed = run_hidden(
            ["ping", count_flag, "1", *wait_args, ip],
            timeout=max(2, timeout_ms / 1000 + 1),
        )
        return completed.returncode == 0
    except Exception:
        return False
