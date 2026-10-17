"""SNMPv2c encoder, ARP parsers, selftest, switch ARP."""

from ciscoman_core import snmpv2c, snmp_discovery, switch_arp, selftest, fingerprint


def test_snmp_available():
    assert snmp_discovery.snmp_available()


def test_snmp_get_request_encodes_community_and_oid():
    pkt = snmpv2c.encode_get_request("public", ["1.3.6.1.2.1.1.1.0"], request_id=42)
    assert pkt[0] == 0x30
    assert b"public" in pkt
    # GetRequest PDU
    assert 0xA0 in pkt


def test_snmp_get_response_roundtrip():
    resp = snmpv2c.encode_get_response(
        "public",
        {
            "1.3.6.1.2.1.1.1.0": "Cisco IOS Software, C2960X Software, Version 15.2(7)E3",
            "1.3.6.1.2.1.1.5.0": "SW-CORE-01",
        },
        request_id=7,
    )
    decoded = snmpv2c.decode_get_response(resp)
    assert decoded["1.3.6.1.2.1.1.5.0"] == "SW-CORE-01"
    assert "Cisco" in decoded["1.3.6.1.2.1.1.1.0"]


def test_parse_cisco_and_h3c_arp():
    cisco = (
        "Protocol  Address          Age (min)  Hardware Addr   Type   Interface\n"
        "Internet  10.10.110.71           2   0000.0c11.2233  ARPA   Vlan110\n"
        "Internet  10.10.110.1            -   0000.0c07.ac01  ARPA   Vlan110\n"
    )
    table = switch_arp.parse_arp_table(cisco)
    assert table["10.10.110.71"] == "00:00:0C:11:22:33"
    h3c = "10.10.110.120    00aa-bbcc-ddee   110   GE1/0/5   20 D\n"
    table2 = switch_arp.parse_arp_table(h3c)
    assert table2["10.10.110.120"] == "00:AA:BB:CC:DD:EE"


def test_vendor_from_sysobjectid():
    info = snmp_discovery.SNMPInfo(sys_object_id="1.3.6.1.4.1.9.1.1208")
    assert snmp_discovery._vendor_from_object_id(info.sys_object_id) == "Cisco"
    assert snmp_discovery._vendor_from_object_id("1.3.6.1.4.1.25506.1.1") == "H3C"


def test_parse_descr_cisco():
    v, m, o = snmp_discovery._parse_descr(
        "Cisco IOS Software, C2960X Software, Version 15.2(7)E3"
    )
    assert v == "Cisco"
    assert o and "15.2" in o


def test_selftest_passes():
    assert selftest.run_selftest() == 0


def test_ssh_banner_vendor_hint(monkeypatch):
    monkeypatch.setattr(
        fingerprint, "grab_ssh_banner", lambda ip, port=22, timeout=2.0: "SSH-2.0-Cisco-1.25"
    )
    monkeypatch.setattr(fingerprint, "grab_http", lambda *a, **k: (None, None))
    fp = fingerprint.fingerprint_host("10.10.110.71", ports=[22])
    assert fp.vendor == "Cisco"
    assert fp.source == "ssh-banner"


def test_query_device_arp_uses_simulator():
    from ciscoman_core import database as db

    db.init_db()
    if not db.is_initialized():
        key = db.set_master_password("test_password_12345")
    else:
        key = db.verify_master_password("test_password_12345")
    db.seed_demo_devices(key)
    devices = [d for d in db.list_devices() if d.get("is_demo")]
    assert devices
    full = db.get_device_with_credentials(key, devices[0]["id"])
    table, raw = switch_arp.query_device_arp(full)
    assert table
    assert any(mac.upper().startswith("00:00:0C") for mac in table.values())
    assert "Internet" in raw or "Hardware" in raw
