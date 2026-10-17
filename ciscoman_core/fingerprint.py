"""SSH banner and HTTP/HTTPS title/server fingerprinting — stdlib only."""

from __future__ import annotations

import re
import socket
import ssl
from dataclasses import dataclass
from typing import Optional


@dataclass
class Fingerprint:
    ssh_banner: Optional[str] = None
    http_server: Optional[str] = None
    http_title: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    source: str = ""


_VENDOR_HINTS = (
    (r"cisco", "Cisco"),
    (r"junos|juniper", "Juniper"),
    (r"h3c|comware", "H3C"),
    (r"huawei|vrp", "Huawei"),
    (r"aruba", "Aruba"),
    (r"procurve|hp[_ ]?switch", "HP"),
    (r"fortinet|fortigate", "Fortinet"),
    (r"mikrotik|routeros", "MikroTik"),
    (r"ubiquiti|unifi|edgeos", "Ubiquiti"),
    (r"dropbear|openssh", None),
)


def grab_ssh_banner(ip: str, port: int = 22, timeout: float = 2.0) -> Optional[str]:
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            data = sock.recv(256)
        if not data:
            return None
        text = data.decode("latin-1", errors="replace").strip()
        first = text.splitlines()[0] if text else ""
        return first[:200] if first else None
    except OSError:
        return None


def grab_http(ip: str, port: int, use_tls: bool, timeout: float = 2.5) -> tuple[Optional[str], Optional[str]]:
    """Return (Server header, HTML title)."""
    try:
        raw = socket.create_connection((ip, port), timeout=timeout)
    except OSError:
        return None, None
    sock: socket.socket = raw
    try:
        if use_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(raw, server_hostname=ip)
        req = (
            f"GET / HTTP/1.0\r\nHost: {ip}\r\nUser-Agent: CiscoMan/2.0\r\n"
            f"Accept: text/html,*/*\r\nConnection: close\r\n\r\n"
        )
        sock.settimeout(timeout)
        sock.sendall(req.encode("ascii"))
        chunks: list[bytes] = []
        while sum(len(c) for c in chunks) < 8192:
            try:
                piece = sock.recv(2048)
            except OSError:
                break
            if not piece:
                break
            chunks.append(piece)
        blob = b"".join(chunks).decode("utf-8", errors="replace")
    except OSError:
        return None, None
    finally:
        try:
            sock.close()
        except OSError:
            pass

    server = None
    m = re.search(r"(?im)^server:\s*(.+)$", blob)
    if m:
        server = m.group(1).strip()
    title = None
    m = re.search(r"(?is)<title[^>]*>\s*([^<]{1,120})\s*</title>", blob)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    return server, title


def _hint_vendor(*texts: Optional[str]) -> Optional[str]:
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return None
    for pat, vendor in _VENDOR_HINTS:
        if vendor and re.search(pat, blob):
            return vendor
    return None


def fingerprint_host(ip: str, ports: Optional[list[int]] = None) -> Fingerprint:
    """Best-effort SSH + HTTP/HTTPS identity. Never raises."""
    ports = ports or [22, 80, 443]
    fp = Fingerprint()
    if 22 in ports:
        fp.ssh_banner = grab_ssh_banner(ip, 22)
        if fp.ssh_banner:
            fp.source = "ssh-banner"
            fp.vendor = _hint_vendor(fp.ssh_banner)
            # SSH-2.0-Cisco-1.25 / SSH-2.0-Cisco-2.0
            m = re.search(r"SSH-[\d.]+-(\S+)", fp.ssh_banner)
            if m and not fp.model:
                impl = m.group(1)
                if "cisco" in impl.lower():
                    fp.model = impl

    if 80 in ports:
        server, title = grab_http(ip, 80, False)
        fp.http_server = fp.http_server or server
        fp.http_title = fp.http_title or title
    if 443 in ports:
        server, title = grab_http(ip, 443, True)
        fp.http_server = fp.http_server or server
        fp.http_title = fp.http_title or title

    if fp.http_server or fp.http_title:
        if not fp.source:
            fp.source = "http"
        elif "http" not in fp.source:
            fp.source = f"{fp.source}+http"
        if not fp.vendor:
            fp.vendor = _hint_vendor(fp.http_server, fp.http_title)
    return fp
