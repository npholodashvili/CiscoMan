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


def test_identify_device_uses_provided_arp_table():
    """ARP is injected — no subprocess, vendor comes from bundled OUI."""
    ident = device_identification.identify_device(
        "192.168.1.1",
        try_snmp=False,
        online_oui=False,
        arp_table={"192.168.1.1": "00:00:0C:11:22:33"},
        local_nets=[],
        try_fingerprint=False,
    )
    assert ident.mac == "00:00:0C:11:22:33"
    assert ident.vendor and "Cisco" in ident.vendor
    assert "oui-db" in ident.sources
    assert ident.identified


def test_identify_device_remote_subnet_note():
    """Hosts off-link must not pretend we have a MAC; UI gets an explicit note."""
    import ipaddress

    ident = device_identification.identify_device(
        "10.10.110.71",
        try_snmp=False,
        arp_table={},
        local_nets=[ipaddress.ip_network("192.168.1.0/24")],
        try_fingerprint=False,
    )
    assert ident.mac is None
    assert ident.on_link is False
    assert "Remote subnet" in ident.note
    assert ident.source_label.startswith("Remote subnet")


def test_identify_hosts_reads_arp_once(monkeypatch):
    calls = {"n": 0}

    def fake_arp():
        calls["n"] += 1
        return {"10.0.0.1": "00:00:0C:AA:BB:CC"}

    monkeypatch.setattr(
        "ciscoman_core.device_identification.win_native.get_arp_table", fake_arp
    )
    monkeypatch.setattr(
        "ciscoman_core.device_identification.win_native.local_ipv4_networks",
        lambda: [],
    )
    results = device_identification.identify_hosts(
        ["10.0.0.1", "10.0.0.2"],
        try_snmp=False,
        max_workers=2,
        try_fingerprint=False,
    )
    assert calls["n"] == 1
    assert results[0].vendor and "Cisco" in results[0].vendor
    assert results[1].mac is None


def test_identify_device_switch_arp_on_remote_subnet():
    """Routed hosts get MACs from a gateway/switch ARP table, then OUI."""
    import ipaddress

    ident = device_identification.identify_device(
        "10.10.110.71",
        try_snmp=False,
        online_oui=False,
        arp_table={},
        extra_arp={"10.10.110.71": "00:00:0C:11:22:33"},
        local_nets=[ipaddress.ip_network("10.10.40.0/23")],
        try_fingerprint=False,
    )
    assert ident.on_link is False
    assert ident.mac == "00:00:0C:11:22:33"
    assert ident.vendor and "Cisco" in ident.vendor
    assert "switch-arp" in ident.sources
    assert ident.identified
    assert "switch ARP" in ident.note or "Remote subnet" in ident.note


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
