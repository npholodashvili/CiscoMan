"""MAC address discovery and OUI vendor identification."""

from __future__ import annotations

import logging
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ciscoman_core import config
from ciscoman_core import win_native

logger = logging.getLogger(__name__)


@dataclass
class MACInfo:
    """MAC address information."""
    mac: str
    vendor: str
    source: str  # "oui-db", "oui-online", "cache"
    confidence: float  # 0.0 to 1.0


def normalize_mac(mac: str) -> str:
    """Normalize MAC address to XX:XX:XX:XX:XX:XX format."""
    import re

    clean = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    return ":".join(clean[i : i + 2].upper() for i in range(0, 12, 2))


def get_oui_prefix(mac: str) -> str:
    """Extract OUI prefix (first 6 hex digits) from MAC."""
    return normalize_mac(mac).replace(":", "")[:6].upper()


def find_oui_db() -> Optional[Path]:
    """Locate the bundled or user-upgraded IEEE OUI database.

    Search order:
    1. %LOCALAPPDATA%\\CiscoMan\\oui.db (user-updated)
    2. PyInstaller _MEIPASS/ciscoman_core/oui.db
    3. Next to the frozen executable
    4. Source tree ciscoman_core/oui.db
    """
    candidates: list[Path] = [
        config.get_data_dir() / "oui.db",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "ciscoman_core" / "oui.db")
        candidates.append(Path(meipass) / "oui.db")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ciscoman_core" / "oui.db")
        candidates.append(Path(sys.executable).resolve().parent / "oui.db")
    candidates.append(Path(__file__).resolve().parent / "oui.db")

    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def _oui_entry_count(path: Path) -> int:
    """Number of vendor prefixes in an OUI database (0 if unreadable)."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM oui").fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return 0


def _bundled_oui_db() -> Optional[Path]:
    """The OUI database shipped with the app (not the user data copy)."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "ciscoman_core" / "oui.db")
        candidates.append(Path(meipass) / "oui.db")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ciscoman_core" / "oui.db")
        candidates.append(Path(sys.executable).resolve().parent / "oui.db")
    candidates.append(Path(__file__).resolve().parent / "oui.db")
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


_oui_db_checked: Optional[Path] = None


def ensure_oui_db() -> Optional[Path]:
    """Copy the bundled OUI DB into the user data dir so Settings can update it.

    The user copy is replaced whenever the bundled database has more vendor
    prefixes, so an app upgrade with a bigger IEEE list takes effect instead
    of being shadowed by an old copy in %LOCALAPPDATA%\\CiscoMan.
    """
    global _oui_db_checked
    if _oui_db_checked is not None and _oui_db_checked.exists():
        return _oui_db_checked
    bundled = _bundled_oui_db()
    dest = config.get_data_dir() / "oui.db"
    result = find_oui_db()
    if bundled is not None and bundled.resolve() != dest.resolve():
        try:
            if not dest.exists() or _oui_entry_count(dest) < _oui_entry_count(bundled):
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(".tmp")
                tmp.write_bytes(bundled.read_bytes())
                tmp.replace(dest)
                logger.info("Installed bundled OUI database (%d prefixes)", _oui_entry_count(dest))
            result = dest
        except OSError as exc:
            logger.debug("Could not copy OUI db to data dir: %s", exc)
            result = bundled
    _oui_db_checked = result
    return result


def restore_bundled_oui_db() -> Optional[Path]:
    """Force-replace the user copy with the bundled database."""
    global _oui_db_checked
    bundled = _bundled_oui_db()
    if bundled is None:
        return None
    dest = config.get_data_dir() / "oui.db"
    if bundled.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bundled.read_bytes())
    _oui_db_checked = None
    return dest


def get_arp_table_windows() -> dict[str, str]:
    """Compatibility wrapper — reads the neighbor table once, no PowerShell."""
    return win_native.get_arp_table()


def get_arp_table() -> dict[str, str]:
    return win_native.get_arp_table()


def ping_to_populate_arp(ip: str, timeout: int = 1) -> bool:
    """ICMP echo with no console window (IcmpSendEcho / hidden ping)."""
    return win_native.icmp_echo(ip, timeout_ms=max(200, int(timeout * 1000)))


def lookup_oui_offline(mac: str) -> Optional[str]:
    """Look up vendor from the local OUI database."""
    try:
        oui = get_oui_prefix(mac)
        db_path = ensure_oui_db()
        if db_path is None:
            logger.warning("OUI database not found, cannot perform offline lookup")
            return None

        conn = sqlite3.connect(str(db_path))
        try:
            # Longest match first: MA-S (36-bit), MA-M (28-bit), then MA-L (24-bit).
            hexmac = normalize_mac(mac).replace(":", "")
            row = None
            for length in (9, 7, 6):
                row = conn.execute(
                    "SELECT vendor FROM oui WHERE prefix = ?", (hexmac[:length],)
                ).fetchone()
                if row:
                    break
        finally:
            conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error("OUI offline lookup failed: %s", e)
        return None


def lookup_oui_online(mac: str) -> Optional[str]:
    """Look up vendor from macvendors.com (opt-in, rate-limited, cached)."""
    try:
        import requests

        oui = get_oui_prefix(mac)
        cached = _get_cached_oui(oui)
        if cached:
            return cached

        time.sleep(1.1)
        response = requests.get(f"https://api.macvendors.com/{mac}", timeout=5)
        if response.status_code == 200:
            vendor = response.text.strip()
            if vendor and "error" not in vendor.lower():
                _cache_oui(oui, vendor)
                return vendor
        return None
    except Exception as e:
        logger.debug("OUI online lookup failed: %s", e)
        return None


def _get_cached_oui(oui: str) -> Optional[str]:
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        try:
            row = conn.execute(
                "SELECT vendor, timestamp FROM oui_cache WHERE prefix = ?", (oui,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            vendor, timestamp = row
            if time.time() - timestamp < 90 * 86400:
                return vendor
        return None
    except Exception:
        return None


def _cache_oui(oui: str, vendor: str) -> None:
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO oui_cache (prefix, vendor, timestamp) VALUES (?, ?, ?)",
                (oui, vendor, int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("Failed to cache OUI: %s", e)


def identify_mac(mac: str, online_enabled: bool = False) -> Optional[MACInfo]:
    """Identify vendor from a MAC using the offline DB, then optional online."""
    try:
        normalized = normalize_mac(mac)
    except ValueError as e:
        logger.error("Invalid MAC address: %s", e)
        return None

    vendor = lookup_oui_offline(normalized)
    if vendor:
        return MACInfo(mac=normalized, vendor=vendor, source="oui-db", confidence=0.9)

    if online_enabled:
        vendor = lookup_oui_online(normalized)
        if vendor:
            return MACInfo(mac=normalized, vendor=vendor, source="oui-online", confidence=0.85)
    return None
