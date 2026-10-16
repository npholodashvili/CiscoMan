"""Tests for MAC discovery and OUI identification."""

import pytest
from ciscoman_core import mac_discovery


def test_normalize_mac():
    """Test MAC address normalization."""
    # Various formats
    assert mac_discovery.normalize_mac("00:11:22:33:44:55") == "00:11:22:33:44:55"
    assert mac_discovery.normalize_mac("00-11-22-33-44-55") == "00:11:22:33:44:55"
    assert mac_discovery.normalize_mac("0011.2233.4455") == "00:11:22:33:44:55"
    assert mac_discovery.normalize_mac("001122334455") == "00:11:22:33:44:55"
    assert mac_discovery.normalize_mac("00:11:22:aa:bb:cc") == "00:11:22:AA:BB:CC"
    
    # Invalid
    with pytest.raises(ValueError):
        mac_discovery.normalize_mac("invalid")
    
    with pytest.raises(ValueError):
        mac_discovery.normalize_mac("00:11:22:33:44")  # Too short


def test_get_oui_prefix():
    """Test OUI prefix extraction."""
    assert mac_discovery.get_oui_prefix("00:11:22:33:44:55") == "001122"
    assert mac_discovery.get_oui_prefix("aa-bb-cc-dd-ee-ff") == "AABBCC"


def test_find_oui_db_bundled():
    path = mac_discovery.find_oui_db()
    assert path is not None
    assert path.is_file()


def test_lookup_oui_offline():
    """Test offline OUI lookup with bundled database."""
    # Cisco MAC
    vendor = mac_discovery.lookup_oui_offline("00:00:0C:AA:BB:CC")
    assert vendor is not None
    assert "Cisco" in vendor
    
    # Intel MAC
    vendor = mac_discovery.lookup_oui_offline("00:03:47:AA:BB:CC")
    assert vendor is not None
    assert "Intel" in vendor
    
    # Unknown OUI
    vendor = mac_discovery.lookup_oui_offline("FF:FF:FF:AA:BB:CC")
    assert vendor is None


def test_identify_mac():
    """Test MAC identification."""
    # Cisco MAC, offline only
    mac_info = mac_discovery.identify_mac("00:00:0C:11:22:33", online_enabled=False)
    assert mac_info is not None
    assert mac_info.mac == "00:00:0C:11:22:33"
    assert "Cisco" in mac_info.vendor
    assert mac_info.source == "oui-db"
    assert mac_info.confidence > 0.8
    
    # Unknown MAC, offline only
    mac_info = mac_discovery.identify_mac("FF:FF:FF:11:22:33", online_enabled=False)
    assert mac_info is None


def test_get_arp_table_windows():
    """Test ARP table retrieval (may be empty in test environment)."""
    arp_table = mac_discovery.get_arp_table_windows()
    assert isinstance(arp_table, dict)
    # May be empty in CI, just check it doesn't crash


def test_ping_to_populate_arp():
    """Test ping function (non-blocking)."""
    # Localhost should be reachable
    result = mac_discovery.ping_to_populate_arp("127.0.0.1", timeout=1)
    assert isinstance(result, bool)
