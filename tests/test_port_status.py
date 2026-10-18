"""Port panel parsing across platforms."""

from ciscoman_core import port_status as ps

CISCO = """Port      Name               Status       Vlan       Duplex  Speed Type
Gi1/0/1   AP Lobby 1         connected    10         a-full a-1000 10/100/1000BaseTX
Gi1/0/2                      notconnect   1            auto   auto 10/100/1000BaseTX
Gi1/0/3   old printer        disabled     20           auto   auto 10/100/1000BaseTX
"""
AOSCX = """Port      Native  Mode   Type           Enabled Status  Reason                  Speed   Description
          VLAN                                                                  (Mb/s)
--------------------------------------------------------------------------------------------------------
1/1/1     1       access 1GbT           yes     up                              1000    Camera 3
1/1/3     1       access 1GbT           no      down    Administratively down   --      --
"""
COMWARE = """Interface            Link Speed   Duplex Type PVID Description
GE1/0/1              UP   1G(a)   F(a)   A    1    Server room
GE1/0/3              ADM  auto    A      A    1
"""
SOPHOS = """Gi0/1 up, line protocol is up (connected)
Interface Description : Uplink
Gi0/2 up, line protocol is down (not connect)
"""


def _st(ports):
    return [(p["port"], p["status"], p["name"]) for p in ports]


def test_cisco_raw():
    assert _st(ps.parse_output("ios", "# show interfaces status\n" + CISCO)) == [
        ("Gi1/0/1", "up", "AP Lobby 1"), ("Gi1/0/2", "down", ""),
        ("Gi1/0/3", "disabled", "old printer"),
    ]


def test_aoscx_comware_sophos():
    assert _st(ps.parse_output("aoscx", AOSCX)) == [
        ("1/1/1", "up", "Camera 3"), ("1/1/3", "disabled", "")]
    assert _st(ps.parse_output("comware", COMWARE)) == [
        ("GE1/0/1", "up", "Server room"), ("GE1/0/3", "disabled", "")]
    assert _st(ps.parse_output("sophos", SOPHOS)) == [
        ("Gi0/1", "up", "Uplink"), ("Gi0/2", "down", "")]


def test_textfsm_rows_and_helpers():
    rows = [{"port": "Gi1/0/5", "name": "x", "status": "connected", "vlan_id": "10"}]
    assert ps.parse_output("ios", "", rows)[0]["vlan"] == "10"
    assert ps.split_port("GigabitEthernet1/0/12") == ("Gi1/0/", 12)
    assert ps.interface_expression(["Gi1/0/1", "Gi1/0/2"], "ios") == "range Gi1/0/1, Gi1/0/2"
