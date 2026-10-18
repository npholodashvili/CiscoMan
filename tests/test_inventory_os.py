"""Inventory edit/delete and per-device OS handling."""

from cryptography.fernet import Fernet

from ciscoman_core import actions, config, database as db, network_utils as net


def _key():
    return Fernet.generate_key()


def test_edit_keeps_password_when_blank_and_changes_os(tmp_path):
    path = str(tmp_path / "inv.db")
    db.init_db(path)
    key = _key()
    did = db.add_device(key, "sw1", "10.0.0.1", "admin", "wrongpw", db_path=path)
    db.update_device(key, did, db_path=path, device_type="sophos_switch", name="SW-1")
    d = db.get_device_with_credentials(key, did, db_path=path)
    assert d["password"] == "wrongpw" and d["device_type"] == "sophos_switch"
    db.update_device(key, did, db_path=path, password="rightpw", secret="en")
    d = db.get_device_with_credentials(key, did, db_path=path)
    assert d["password"] == "rightpw" and d["secret"] == "en"
    db.update_device(key, did, db_path=path, secret="")
    assert db.get_device_with_credentials(key, did, db_path=path)["secret"] == ""
    db.delete_device(did, db_path=path)
    assert db.list_devices(db_path=path) == []


def test_upsert_keeps_user_chosen_os(tmp_path):
    path = str(tmp_path / "inv.db")
    db.init_db(path)
    key = _key()
    did = db.add_device(key, "sw", "10.0.0.2", "a", "p", device_type="sophos_switch", db_path=path)
    db.upsert_device(key, db_path=path, name="sw", ip="10.0.0.2", username="a",
                     password="p", device_type="cisco_ios", port=22)
    assert db.list_devices(db_path=path)[0]["device_type"] == "sophos_switch"


def test_every_supported_type_has_label_and_driver():
    from netmiko.ssh_dispatcher import CLASS_MAPPER
    for t in config.SUPPORTED_DEVICE_TYPES:
        assert config.device_type_label(t) != t
        assert net._available_driver(t) in CLASS_MAPPER


def test_non_cisco_devices_do_not_get_cisco_commands():
    for dtype in ("sophos_switch", "aruba_osswitch", "aruba_aoscx", "grandstream_switch"):
        visible = {a.id for a in actions.filter_actions(actions.ACTIONS, {dtype})}
        assert "show_run" not in visible and "set_access_vlan" not in visible
        assert {"custom_show", "custom_config"} <= visible
    sophos = {a.id for a in actions.filter_actions(actions.ACTIONS, {"sophos_switch"})}
    assert "sophos_show_run" in sophos
    ios = {a.id for a in actions.filter_actions(actions.ACTIONS, {"cisco_ios"})}
    assert "show_run" in ios and "sophos_show_run" not in ios


def test_running_config_command_per_platform():
    assert net.running_config_command({"device_type": "sophos_switch"}) == "show current running-config"
    assert net.running_config_command({"device_type": "cisco_ios"}) == "show running-config"
    assert net._build_params({"device_type": "sophos_switch", "ip": "1.1.1.1",
                              "username": "u"})["device_type"] == "cisco_ios"


def test_vendor_suggests_os():
    from ciscoman_core.device_identification import _suggest_device_type as s
    assert s("Sophos Ltd", None, None) == "sophos_switch"
    assert s("Grandstream Networks, Inc.", None, None) == "grandstream_switch"
    assert s("Hewlett Packard Enterprise", None, None) == "aruba_osswitch"
    assert s("Cisco Systems, Inc", None, None) == "cisco_ios"
