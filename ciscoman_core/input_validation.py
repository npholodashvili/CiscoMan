"""Input validation utilities for security."""

import ipaddress
import re
from typing import Optional


def validate_ip(ip: str) -> tuple[bool, Optional[str]]:
    """Validate IP address. Returns (is_valid, error_message)."""
    try:
        ipaddress.ip_address(ip.strip())
        return True, None
    except ValueError as e:
        return False, f"Invalid IP address: {e}"


def validate_vlan_id(vlan: int) -> tuple[bool, Optional[str]]:
    """Validate VLAN ID (1-4094). Returns (is_valid, error_message)."""
    if not (1 <= vlan <= 4094):
        return False, f"VLAN ID must be between 1 and 4094, got {vlan}"
    return True, None


def validate_interface_name(iface: str) -> tuple[bool, Optional[str]]:
    """Validate interface name format. Returns (is_valid, error_message)."""
    # Common Cisco interface patterns
    patterns = [
        r'^(?:Gigabit|Fast|TenGigabit|TwentyFiveGig|FortyGigabit)Ethernet\d+(/\d+)*$',
        r'^Ethernet\d+(/\d+)*$',
        r'^Port-channel\d+$',
        r'^Vlan\d+$',
        r'^Tunnel\d+$',
        r'^Loopback\d+$',
        r'^range\s+.+',  # Interface ranges
    ]
    
    iface = iface.strip()
    if not iface:
        return False, "Interface name cannot be empty"
    
    for pattern in patterns:
        if re.match(pattern, iface, re.IGNORECASE):
            return True, None
    
    return False, f"Invalid interface format: {iface}"


def validate_hostname(hostname: str) -> tuple[bool, Optional[str]]:
    """Validate hostname format. Returns (is_valid, error_message)."""
    if not hostname or len(hostname) > 63:
        return False, "Hostname must be 1-63 characters"
    
    # RFC 1123 hostname
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$', hostname):
        return False, "Invalid hostname format"
    
    return True, None


def sanitize_description(desc: str, max_len: int = 240) -> str:
    """Sanitize description field (remove control chars, limit length)."""
    # Remove control characters except space/tab
    clean = ''.join(c for c in desc if c.isprintable() or c in ' \t')
    return clean[:max_len].strip()
