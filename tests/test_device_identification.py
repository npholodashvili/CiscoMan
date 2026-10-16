"""Tests for device identification."""

import pytest
from ciscoman_core import device_identification


def test_device_identity_to_dict():
    """Test DeviceIdentity serialization."""
    ident = device_identification.DeviceIdentity(
        ip="192.168.1.1",
        mac="00:00:0C:11:22:33",
        hostname="switch1",
        vendor="Cisco",
        model="C2960",
        sources=["arp", "oui-db"],
        confidence=0.9
    )
    
    data = ident.to_dict()
    assert data["ip"] == "192.168.1.1"
    assert data["mac"] == "00:00:0C:11:22:33"
    assert data["hostname"] == "switch1"
    assert data["vendor"] == "Cisco"
    assert "oui-db" in data["sources"]
    assert "90%" in data["confidence"]


def test_identify_device_no_network():
    """Test device identification without network access."""
    # This should not crash even if IP is unreachable
    ident = device_identification.identify_device(
        "192.168.255.254",
        try_snmp=False,
        ping_first=False
    )
    
    # May return None or partial info
    assert ident is None or isinstance(ident, device_identification.DeviceIdentity)


def test_format_identification_summary():
    """Test summary formatting."""
    ident = device_identification.DeviceIdentity(
        ip="192.168.1.1",
        mac="00:00:0C:11:22:33",
        hostname="switch1",
        vendor="Cisco",
        model="C2960",
        sources=["arp", "oui-db"],
        confidence=0.85
    )
    
    summary = device_identification.format_identification_summary(ident)
    assert "192.168.1.1" in summary
    assert "Cisco" in summary
    assert "switch1" in summary
    assert "85%" in summary
