"""Tests for input validation."""

import pytest
from ciscoman_core import input_validation


def test_validate_ip():
    """Test IP address validation."""
    valid, err = input_validation.validate_ip("192.168.1.1")
    assert valid
    assert err is None
    
    valid, err = input_validation.validate_ip("10.0.0.1")
    assert valid
    
    valid, err = input_validation.validate_ip("999.999.999.999")
    assert not valid
    assert err is not None
    
    valid, err = input_validation.validate_ip("not an ip")
    assert not valid


def test_validate_vlan():
    """Test VLAN ID validation."""
    valid, err = input_validation.validate_vlan_id(10)
    assert valid
    assert err is None
    
    valid, err = input_validation.validate_vlan_id(1)
    assert valid
    
    valid, err = input_validation.validate_vlan_id(4094)
    assert valid
    
    valid, err = input_validation.validate_vlan_id(0)
    assert not valid
    
    valid, err = input_validation.validate_vlan_id(5000)
    assert not valid


def test_validate_interface():
    """Test interface name validation."""
    valid, err = input_validation.validate_interface_name("GigabitEthernet1/0/1")
    assert valid
    
    valid, err = input_validation.validate_interface_name("FastEthernet0/1")
    assert valid
    
    valid, err = input_validation.validate_interface_name("Port-channel10")
    assert valid
    
    valid, err = input_validation.validate_interface_name("Vlan100")
    assert valid
    
    valid, err = input_validation.validate_interface_name("range GigabitEthernet1/0/1 - 10")
    assert valid
    
    valid, err = input_validation.validate_interface_name("InvalidInterface")
    assert not valid


def test_sanitize_description():
    """Test description sanitization."""
    result = input_validation.sanitize_description("Normal description")
    assert result == "Normal description"
    
    result = input_validation.sanitize_description("  Spaces around  ")
    assert result == "Spaces around"
    
    long = "x" * 300
    result = input_validation.sanitize_description(long, max_len=240)
    assert len(result) == 240
