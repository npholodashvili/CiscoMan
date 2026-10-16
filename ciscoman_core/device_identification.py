"""Combined device identification using MAC/OUI, SNMP, and LLDP/CDP."""

from __future__ import annotations

import logging
from typing import Optional
from dataclasses import dataclass, field

from ciscoman_core import mac_discovery, snmp_discovery, database as db

logger = logging.getLogger(__name__)


@dataclass
class DeviceIdentity:
    """Complete device identification result."""
    ip: str
    mac: Optional[str] = None
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    device_type: Optional[str] = None  # Suggested netmiko device_type
    
    # Source attribution
    sources: list[str] = field(default_factory=list)  # e.g. ["oui-db", "snmp", "arp"]
    confidence: float = 0.0  # 0.0 to 1.0
    snmp_info: Optional[snmp_discovery.SNMPInfo] = None
    mac_info: Optional[mac_discovery.MACInfo] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "model": self.model,
            "os_version": self.os_version,
            "device_type": self.device_type,
            "sources": ", ".join(self.sources),
            "confidence": f"{self.confidence:.0%}"
        }


def identify_device(
    ip: str,
    try_snmp: bool = True,
    snmp_community: Optional[str] = None,
    online_oui: bool = False,
    ping_first: bool = True
) -> Optional[DeviceIdentity]:
    """Identify a device using all available methods.
    
    Args:
        ip: Target IP address
        try_snmp: Whether to try SNMP discovery
        snmp_community: SNMP community string (default from settings)
        online_oui: Whether to use online OUI lookup
        ping_first: Ping before ARP lookup
        
    Returns:
        DeviceIdentity or None if no identification possible
    """
    result = DeviceIdentity(ip=ip)
    
    # Step 1: Try to get MAC address from ARP
    if ping_first:
        logger.debug(f"Pinging {ip} to populate ARP cache")
        mac_discovery.ping_to_populate_arp(ip)
    
    arp_table = mac_discovery.get_arp_table_windows()
    mac = arp_table.get(ip)
    
    if mac:
        result.mac = mac
        result.sources.append("arp")
        logger.debug(f"Found MAC {mac} for {ip} in ARP table")
        
        # Step 2: OUI lookup on MAC
        mac_info = mac_discovery.identify_mac(mac, online_enabled=online_oui)
        if mac_info:
            result.mac_info = mac_info
            result.vendor = mac_info.vendor
            result.sources.append(mac_info.source)
            result.confidence = max(result.confidence, mac_info.confidence * 0.7)
            logger.debug(f"OUI lookup: {mac_info.vendor} (source: {mac_info.source})")
    
    # Step 3: SNMP discovery
    if try_snmp:
        if not snmp_community:
            snmp_community = db.get_setting("snmp_community", "public")
        
        logger.debug(f"Trying SNMP discovery on {ip}")
        snmp_info = snmp_discovery.discover_via_snmp(ip, snmp_community)
        
        if snmp_info:
            result.snmp_info = snmp_info
            result.sources.append("snmp")
            result.hostname = snmp_info.sys_name
            
            # SNMP data overrides OUI if more specific
            if snmp_info.vendor:
                result.vendor = snmp_info.vendor
                result.confidence = max(result.confidence, snmp_info.confidence)
            
            if snmp_info.model:
                result.model = snmp_info.model
            
            if snmp_info.os_version:
                result.os_version = snmp_info.os_version
            
            logger.debug(f"SNMP discovery: {snmp_info.vendor} {snmp_info.model}")
    
    # Step 4: Suggest device_type based on vendor
    if result.vendor:
        vendor_lower = result.vendor.lower()
        
        if "cisco" in vendor_lower:
            # Check for specific platforms
            if result.model and "nexus" in result.model.lower():
                result.device_type = "cisco_nxos"
            elif result.model and ("asr" in result.model.lower() or "isr" in result.model.lower()):
                result.device_type = "cisco_ios"
            elif result.os_version and "xe" in result.os_version.lower():
                result.device_type = "cisco_xe"
            else:
                result.device_type = "cisco_ios"
        
        elif "juniper" in vendor_lower:
            result.device_type = "juniper_junos"
        
        elif "hp" in vendor_lower or "aruba" in vendor_lower:
            if "aruba" in vendor_lower:
                result.device_type = "aruba_os"
            else:
                result.device_type = "hp_procurve"
        
        elif "h3c" in vendor_lower:
            result.device_type = "hp_comware"
        
        elif "vmware" in vendor_lower:
            result.device_type = None  # Not a network device
        
        elif "intel" in vendor_lower or "foxconn" in vendor_lower:
            result.device_type = None  # Likely a PC/server
    
    # Only return if we got something useful
    if result.sources:
        # Boost confidence if we have multiple sources
        if len(result.sources) >= 2:
            result.confidence = min(1.0, result.confidence + 0.1)
        
        return result
    
    return None


def format_identification_summary(ident: DeviceIdentity) -> str:
    """Format identification result as human-readable summary."""
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
    
    lines.append(f"  Sources: {', '.join(ident.sources)}")
    lines.append(f"  Confidence: {ident.confidence:.0%}")
    
    return "\n".join(lines)
