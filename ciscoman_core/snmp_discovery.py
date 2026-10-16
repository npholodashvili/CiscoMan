"""SNMP-based device discovery and enrichment."""

from __future__ import annotations

import logging
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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


def snmp_get(ip: str, community: str, oid: str, version: str = "2c", timeout: int = 2) -> Optional[str]:
    """Perform SNMP GET operation.
    
    Args:
        ip: Target IP address
        community: SNMP community string
        oid: OID to query
        version: SNMP version ("1", "2c")
        timeout: Timeout in seconds
        
    Returns:
        Value as string or None if failed
    """
    try:
        # Use pysnmp if available
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity
        )
        
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=0 if version == "1" else 1),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            logger.debug(f"SNMP error: {errorIndication}")
            return None
        elif errorStatus:
            logger.debug(f"SNMP error: {errorStatus.prettyPrint()}")
            return None
        else:
            for varBind in varBinds:
                return str(varBind[1])
        
        return None
        
    except ImportError:
        logger.warning("pysnmp not available, SNMP discovery disabled")
        return None
    except Exception as e:
        logger.debug(f"SNMP GET failed for {ip}: {e}")
        return None


def discover_via_snmp(ip: str, community: str = "public", version: str = "2c") -> Optional[SNMPInfo]:
    """Discover device information via SNMP.
    
    Args:
        ip: Target IP address
        community: SNMP community string (default: "public")
        version: SNMP version ("1", "2c", "3")
        
    Returns:
        SNMPInfo or None if discovery failed
    """
    if version == "3":
        logger.warning("SNMPv3 not yet implemented")
        return None
    
    try:
        # Query standard MIB-II objects
        sys_descr = snmp_get(ip, community, "1.3.6.1.2.1.1.1.0", version)
        sys_name = snmp_get(ip, community, "1.3.6.1.2.1.1.5.0", version)
        sys_object_id = snmp_get(ip, community, "1.3.6.1.2.1.1.2.0", version)
        
        if not sys_descr and not sys_name:
            return None
        
        # Parse vendor and model from sysDescr
        vendor = None
        model = None
        os_version = None
        
        if sys_descr:
            descr_lower = sys_descr.lower()
            
            # Cisco patterns
            if "cisco" in descr_lower:
                vendor = "Cisco"
                # Extract model
                match = re.search(r'(catalyst|c\d{4}|isr\d{4}|asr\d{4}|nexus\s*\d{4})', descr_lower)
                if match:
                    model = match.group(1).upper()
                # Extract IOS version
                match = re.search(r'version\s+([\d\.]+\([\w\)]+)', descr_lower)
                if match:
                    os_version = match.group(1)
            
            # Juniper patterns
            elif "juniper" in descr_lower or "junos" in descr_lower:
                vendor = "Juniper"
                match = re.search(r'(mx\d+|ex\d+|srx\d+|qfx\d+)', descr_lower)
                if match:
                    model = match.group(1).upper()
            
            # HP/Aruba patterns
            elif "hp" in descr_lower or "procurve" in descr_lower or "aruba" in descr_lower:
                vendor = "HP/Aruba"
                match = re.search(r'(procurve|aruba)[\s\-]*([\w\d\-]+)', descr_lower)
                if match:
                    model = match.group(2).upper()
            
            # H3C patterns
            elif "h3c" in descr_lower or "comware" in descr_lower:
                vendor = "H3C"
                match = re.search(r'(s\d{4}|msr\d{4})', descr_lower)
                if match:
                    model = match.group(1).upper()
        
        return SNMPInfo(
            sys_descr=sys_descr,
            sys_name=sys_name,
            sys_object_id=sys_object_id,
            vendor=vendor,
            model=model,
            os_version=os_version,
            confidence=0.85 if vendor else 0.5
        )
        
    except Exception as e:
        logger.error(f"SNMP discovery failed for {ip}: {e}")
        return None


# Import re for pattern matching
import re
