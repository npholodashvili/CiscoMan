"""Tests for action rendering."""

import pytest
from ciscoman_core import actions


def test_action_catalog_loads():
    """Verify action catalog loads without errors."""
    assert len(actions.ACTIONS) > 0
    assert actions.ACTIONS_BY_ID
    assert actions.CATEGORIES


def test_set_access_vlan_renders():
    """Test VLAN assignment action renders correctly."""
    action = actions.get_action("set_access_vlan")
    assert action is not None
    
    result = action.render({"interface": "GigabitEthernet1/0/1", "vlan": 10})
    assert len(result) > 0
    assert "interface GigabitEthernet1/0/1" in result
    assert "switchport access vlan 10" in result


def test_port_description_renders():
    """Test port description action renders correctly."""
    action = actions.get_action("set_description")
    assert action is not None
    
    result = action.render({
        "interface": "GigabitEthernet1/0/5",
        "description": "Test Port"
    })
    assert len(result) > 0
    assert "interface GigabitEthernet1/0/5" in result
    assert "description Test Port" in result


def test_interface_range_renders():
    """Test interface range rendering."""
    action = actions.get_action("port_updown")
    assert action is not None
    
    result = action.render({
        "interface": "range GigabitEthernet1/0/1 - 10",
        "enable": True
    })
    assert len(result) > 0
    assert "interface range GigabitEthernet1/0/1 - 10" in result
    assert "no shutdown" in result


def test_action_platform_filtering():
    """Test platform-specific action filtering."""
    ios_types = {"cisco_ios"}
    nxos_types = {"cisco_nxos"}
    
    all_actions = actions.ACTIONS
    ios_actions = actions.filter_actions(all_actions, ios_types)
    nxos_actions = actions.filter_actions(all_actions, nxos_types)
    
    assert len(ios_actions) > 0
    assert len(nxos_actions) > 0
