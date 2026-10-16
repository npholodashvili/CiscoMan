"""MAC address discovery and OUI vendor identification."""

from __future__ import annotations

import subprocess
import re
import logging
import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ciscoman_core import config

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
    # Remove all non-hex characters
    clean = re.sub(r'[^0-9a-fA-F]', '', mac)
    if len(clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    
    # Format as XX:XX:XX:XX:XX:XX
    return ':'.join(clean[i:i+2].upper() for i in range(0, 12, 2))


def get_oui_prefix(mac: str) -> str:
    """Extract OUI prefix (first 6 hex digits) from MAC."""
    normalized = normalize_mac(mac)
    return normalized.replace(':', '')[:6].upper()


def get_arp_table_windows() -> dict[str, str]:
    """Get ARP table from Windows using Get-NetNeighbor.
    
    Returns dict of {ip: mac}.
    """
    result = {}
    try:
        # Try PowerShell Get-NetNeighbor first (Windows 8+)
        output = subprocess.check_output(
            ['powershell', '-Command', 
             'Get-NetNeighbor | Where-Object {$_.State -eq "Reachable" -or $_.State -eq "Stale"} | Select-Object IPAddress, LinkLayerAddress'],
            text=True,
            timeout=10
        )
        
        # Parse output
        for line in output.splitlines():
            line = line.strip()
            if not line or 'IPAddress' in line or '---' in line:
                continue
            
            # Line format: "192.168.1.1    AA-BB-CC-DD-EE-FF"
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[0]
                mac = parts[1]
                try:
                    normalized = normalize_mac(mac)
                    result[ip] = normalized
                except ValueError:
                    continue
                    
    except Exception as e:
        logger.debug(f"Get-NetNeighbor failed, trying arp -a: {e}")
        
        try:
            # Fall back to arp -a
            output = subprocess.check_output(['arp', '-a'], text=True, timeout=10)
            
            # Parse arp -a output
            for line in output.splitlines():
                # Format: "  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic"
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([\da-fA-F\-:]+)', line)
                if match:
                    ip = match.group(1)
                    mac = match.group(2)
                    try:
                        normalized = normalize_mac(mac)
                        result[ip] = normalized
                    except ValueError:
                        continue
        except Exception as e:
            logger.error(f"Failed to get ARP table: {e}")
    
    return result


def ping_to_populate_arp(ip: str, timeout: int = 1) -> bool:
    """Ping an IP to populate ARP cache. Returns True if reachable."""
    try:
        subprocess.run(
            ['ping', '-n', '1', '-w', str(timeout * 1000), ip],
            capture_output=True,
            timeout=timeout + 1
        )
        return True
    except Exception:
        return False


def lookup_oui_offline(mac: str) -> Optional[str]:
    """Look up vendor from local OUI database.
    
    Returns vendor name or None if not found.
    """
    try:
        oui = get_oui_prefix(mac)
        
        db_path = config.get_data_dir() / "oui.db"
        if not db_path.exists():
            logger.warning("OUI database not found, cannot perform offline lookup")
            return None
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT vendor FROM oui WHERE prefix = ?", (oui,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        
        return None
        
    except Exception as e:
        logger.error(f"OUI offline lookup failed: {e}")
        return None


def lookup_oui_online(mac: str) -> Optional[str]:
    """Look up vendor from online API (macvendors.com).
    
    Returns vendor name or None if not found.
    Rate limited and cached.
    """
    try:
        import requests
        import time
        
        # Check cache first
        oui = get_oui_prefix(mac)
        cached = _get_cached_oui(oui)
        if cached:
            return cached
        
        # Rate limit: max 1 request per second
        time.sleep(1.1)
        
        # Query macvendors.com API
        url = f"https://api.macvendors.com/{mac}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            vendor = response.text.strip()
            if vendor and "error" not in vendor.lower():
                _cache_oui(oui, vendor)
                return vendor
        
        return None
        
    except Exception as e:
        logger.debug(f"OUI online lookup failed: {e}")
        return None


def _get_cached_oui(oui: str) -> Optional[str]:
    """Get cached OUI vendor from database."""
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT vendor, timestamp FROM oui_cache
            WHERE prefix = ?
        """, (oui,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            vendor, timestamp = row
            # Cache valid for 90 days
            import time
            if time.time() - timestamp < 90 * 86400:
                return vendor
        
        return None
        
    except Exception:
        return None


def _cache_oui(oui: str, vendor: str):
    """Cache OUI vendor in database."""
    try:
        import time
        conn = sqlite3.connect(str(config.DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO oui_cache (prefix, vendor, timestamp)
            VALUES (?, ?, ?)
        """, (oui, vendor, int(time.time())))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.debug(f"Failed to cache OUI: {e}")


def identify_mac(mac: str, online_enabled: bool = False) -> Optional[MACInfo]:
    """Identify vendor from MAC address.
    
    Args:
        mac: MAC address in any format
        online_enabled: Whether to use online lookup as fallback
        
    Returns:
        MACInfo or None if no vendor found
    """
    try:
        normalized = normalize_mac(mac)
    except ValueError as e:
        logger.error(f"Invalid MAC address: {e}")
        return None
    
    # Try offline database first
    vendor = lookup_oui_offline(normalized)
    if vendor:
        return MACInfo(
            mac=normalized,
            vendor=vendor,
            source="oui-db",
            confidence=0.9
        )
    
    # Try online if enabled
    if online_enabled:
        vendor = lookup_oui_online(normalized)
        if vendor:
            return MACInfo(
                mac=normalized,
                vendor=vendor,
                source="oui-online",
                confidence=0.85
            )
    
    return None


def init_oui_cache_table():
    """Initialize OUI cache table in database."""
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oui_cache (
                prefix TEXT PRIMARY KEY,
                vendor TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Failed to initialize OUI cache table: {e}")
