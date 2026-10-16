"""Action Cards: the educational, pre-built task catalog.

Each action carries:
- a plain-English explanation ("The Coach")
- a Jinja2 template that renders the exact Cisco IOS CLI ("Show CLI Preview")
- typed parameters so the UI can build proper inputs
- kind: 'show' (read-only exec) or 'config' (changes the device)

Add new actions by appending to ACTIONS. Nothing else needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment, StrictUndefined

_jinja = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


@dataclass
class Param:
    key: str
    label: str
    kind: str = "text"  # text | int | textarea | select | bool
    default: Any = ""
    help: str = ""
    options: list[str] = field(default_factory=list)
    placeholder: str = ""


@dataclass
class Action:
    id: str
    name: str
    category: str
    kind: str  # 'show' or 'config'
    explanation: str
    template: str
    params: list[Param] = field(default_factory=list)
    save_after: bool = False
    use_textfsm: bool = False
    danger: bool = False
    platforms: list[str] = field(default_factory=lambda: ["all"])
    """'all' or family tags: ios, nxos, asa, xr."""

    def render(self, values: dict) -> list[str]:
        """Render the Jinja template into a list of CLI lines."""
        rendered = _jinja.from_string(self.template).render(**values)
        return [ln.rstrip() for ln in rendered.splitlines() if ln.strip()]


# --- Catalog ------------------------------------------------------------------

ACTIONS: list[Action] = [
    # ---- Diagnostics (show) --------------------------------------------------
    Action(
        id="show_run",
        name="Show Running Config",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays the device's active configuration currently held in RAM. "
            "This is what the switch is doing right now, including any unsaved changes."
        ),
        template="show running-config",
    ),
    Action(
        id="show_port_status",
        name="Check Port Status",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists every interface with its link state (connected/notconnect), "
            "assigned VLAN, duplex and speed. Use it to see which ports are live."
        ),
        template="show interfaces status",
        use_textfsm=True,
    ),
    Action(
        id="show_vlan",
        name="Show VLANs",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Shows all VLANs configured on the switch and which access ports belong "
            "to each. VLANs are logical network segments that isolate traffic."
        ),
        template="show vlan brief",
        use_textfsm=True,
    ),
    Action(
        id="show_ip_int_brief",
        name="Show IP Interfaces",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Summarizes Layer-3 interfaces with their IP address and up/down status. "
            "Handy for finding the management IP and SVIs."
        ),
        template="show ip interface brief",
        use_textfsm=True,
    ),
    Action(
        id="show_mac",
        name="Show MAC Address Table",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Maps learned MAC addresses to the physical port and VLAN where the "
            "switch last saw them. Useful for locating which port a device is on."
        ),
        template="show mac address-table",
        use_textfsm=True,
    ),
    Action(
        id="show_cdp",
        name="Show Neighbors (CDP)",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists directly-connected Cisco neighbors discovered via CDP, including "
            "the remote device ID and the local/remote ports. Great for mapping topology."
        ),
        template="show cdp neighbors detail",
    ),
    Action(
        id="show_version",
        name="Show Version / Model",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Reports the IOS version, model, uptime and serial number. Use it to "
            "confirm exactly what hardware and software you are managing."
        ),
        template="show version",
    ),
    Action(
        id="show_ip_route",
        name="Show IP Routing Table",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists routes the switch knows — connected, static, and learned. "
            "Use it to verify default gateways and tunnel destinations."
        ),
        template="show ip route",
    ),
    Action(
        id="show_power_inline",
        name="Show PoE Status",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Shows Power over Ethernet status per port: whether PoE is on, "
            "power draw in watts, and device class. Requires PoE-capable hardware."
        ),
        template="show power inline",
    ),
    Action(
        id="show_stp",
        name="Show Spanning Tree",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays spanning-tree state — which VLAN is root, port roles (designated, "
            "root, blocked). Use before/after changing portfast or BPDU guard."
        ),
        template="show spanning-tree summary",
    ),
    Action(
        id="show_dhcp_snoop",
        name="Show DHCP Snooping",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists DHCP snooping bindings and trusted ports. Confirms snooping is "
            "active and which MAC/IP pairs were learned."
        ),
        template="show ip dhcp snooping",
    ),
    Action(
        id="show_crypto",
        name="Show Crypto / VPN Status",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Shows IPsec security associations, ISAKMP peers, and crypto map status "
            "after bringing up site-to-site VPNs."
        ),
        template="show crypto session\nshow crypto isakmp sa",
    ),
    # ---- Port configuration (config) ----------------------------------------
    Action(
        id="set_access_vlan",
        name="Change Interface VLAN",
        category="Port Config",
        kind="config",
        explanation=(
            "Assigns a physical port to an access VLAN. Example: 'switchport access "
            "vlan 20' places this port into Network Segment 20, so the connected "
            "device joins that broadcast domain."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport mode access\n"
            "switchport access vlan {{ vlan }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface",
                  help="The port(s) to modify."),
            Param("vlan", "Access VLAN ID", "int", default=1,
                  help="VLAN number (1-4094) to place the port into."),
        ],
        save_after=True,
    ),
    Action(
        id="set_description",
        name="Update Port Description",
        category="Port Config",
        kind="config",
        explanation=(
            "Sets a human-readable label on a port. It changes nothing functionally "
            "but documents what is plugged in, e.g. 'Printer - 2nd Floor'."
        ),
        template=(
            "interface {{ interface }}\n"
            "description {{ description }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("description", "Description", "text", placeholder="Uplink to core"),
        ],
        save_after=True,
    ),
    Action(
        id="port_updown",
        name="Enable / Disable Port",
        category="Port Config",
        kind="config",
        explanation=(
            "Administratively turns a port on ('no shutdown') or off ('shutdown'). "
            "Disabling a port instantly drops whatever is connected to it."
        ),
        template=(
            "interface {{ interface }}\n"
            "{{ 'no shutdown' if enable else 'shutdown' }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("enable", "Enable port (uncheck = shutdown)", "bool", default=True),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="set_voice_vlan",
        name="Set Voice VLAN",
        category="Port Config",
        kind="config",
        explanation=(
            "Configures a port for an IP phone: data devices use the access VLAN "
            "while the phone tags its traffic into the voice VLAN over the same cable."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport mode access\n"
            "switchport access vlan {{ data_vlan }}\n"
            "switchport voice vlan {{ voice_vlan }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("data_vlan", "Data VLAN", "int", default=10),
            Param("voice_vlan", "Voice VLAN", "int", default=100),
        ],
        save_after=True,
    ),
    Action(
        id="set_trunk",
        name="Configure Trunk Port",
        category="Port Config",
        kind="config",
        explanation=(
            "Turns a port into a trunk that carries multiple VLANs to another switch "
            "or AP. The allowed list restricts which VLANs may cross the link."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport trunk encapsulation dot1q\n"
            "switchport mode trunk\n"
            "switchport trunk allowed vlan {{ allowed }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("allowed", "Allowed VLANs", "text", default="all",
                  placeholder="10,20,30 or all"),
        ],
        save_after=True,
        danger=True,
    ),
    # ---- PoE (config + already has show in Diagnostics) ----------------------
    Action(
        id="poe_enable",
        name="Enable PoE on Port(s)",
        category="PoE",
        kind="config",
        explanation=(
            "Turns on Power over Ethernet for the selected port(s). The switch "
            "will negotiate power class with the connected device (phone, AP, camera). "
            "Requires a PoE-capable switch and `power inline auto`."
        ),
        template=(
            "interface {{ interface }}\n"
            "power inline auto"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
    ),
    Action(
        id="poe_disable",
        name="Disable PoE on Port(s)",
        category="PoE",
        kind="config",
        explanation=(
            "Stops delivering power on the port (`power inline never`). Use when "
            "a port must never power a device even if something is plugged in."
        ),
        template=(
            "interface {{ interface }}\n"
            "power inline never"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
        danger=True,
    ),
    Action(
        id="create_vlan",
        name="Create VLAN",
        category="Switch Config",
        kind="config",
        explanation=(
            "Creates a new VLAN (network segment) in the switch database and gives "
            "it a name. Ports can then be assigned to it."
        ),
        template=(
            "vlan {{ vlan }}\n"
            "name {{ vlan_name }}"
        ),
        params=[
            Param("vlan", "VLAN ID", "int", default=20),
            Param("vlan_name", "VLAN Name", "text", placeholder="ACCOUNTING"),
        ],
        save_after=True,
    ),
    Action(
        id="set_hostname",
        name="Set Hostname",
        category="Switch Config",
        kind="config",
        explanation=(
            "Changes the device name shown in the CLI prompt. Purely cosmetic but "
            "essential for keeping large fleets identifiable."
        ),
        template="hostname {{ hostname }}",
        params=[Param("hostname", "Hostname", "text", placeholder="SW-FLOOR2-ACCESS")],
        save_after=True,
    ),
    Action(
        id="save_config",
        name="Save Configuration",
        category="Switch Config",
        kind="config",
        explanation=(
            "Copies the running-config to startup-config ('write memory') so changes "
            "survive a reboot. Without this, edits are lost on power cycle."
        ),
        template="",  # handled via save flag; no config lines needed
        save_after=True,
    ),
    Action(
        id="set_svi_ip",
        name="Assign IP to VLAN (SVI)",
        category="Switch Config",
        kind="config",
        explanation=(
            "Creates or updates a Switched Virtual Interface (interface VlanX) with "
            "an IP address. This is how a switch becomes the default gateway "
            "for devices on that VLAN."
        ),
        template=(
            "interface Vlan{{ vlan }}\n"
            "ip address {{ ip }} {{ mask }}"
        ),
        params=[
            Param("vlan", "VLAN ID", "vlan", default=1,
                  help="VLAN that gets the IP (creates SVI if missing)."),
            Param("ip", "IP address", "text", placeholder="192.168.10.1"),
            Param("mask", "Subnet mask", "text", default="255.255.255.0"),
        ],
        save_after=True,
        danger=True,
    ),
    # ---- Routing & Tunnels ---------------------------------------------------
    Action(
        id="static_route",
        name="Add Static Route",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Installs a static route: traffic to the destination network is "
            "forwarded to the next-hop IP (usually another router on a directly "
            "connected segment)."
        ),
        template="ip route {{ network }} {{ mask }} {{ next_hop }}",
        params=[
            Param("network", "Destination network", "text", placeholder="10.0.0.0"),
            Param("mask", "Destination mask", "text", default="255.255.255.0"),
            Param("next_hop", "Next-hop IP", "text", placeholder="192.168.1.254"),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="gre_tunnel",
        name="Create GRE Tunnel",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Builds a GRE tunnel interface — a virtual point-to-point link over "
            "an IP network. Specify tunnel number, inner IP, physical source "
            "interface, and remote peer IP. Often combined with IPsec (not in this "
            "wizard) for encryption."
        ),
        template=(
            "interface Tunnel{{ tunnel_id }}\n"
            " tunnel mode gre ip\n"
            " ip address {{ tunnel_ip }} {{ tunnel_mask }}\n"
            " tunnel source {{ source }}\n"
            " tunnel destination {{ destination }}"
        ),
        params=[
            Param("tunnel_id", "Tunnel number", "int", default=0),
            Param("tunnel_ip", "Tunnel IP (this end)", "text", placeholder="10.255.0.1"),
            Param("tunnel_mask", "Tunnel mask", "text", default="255.255.255.252"),
            Param("source", "Source interface", "text", placeholder="GigabitEthernet1/0/24",
                  help="Local interface toward the remote site."),
            Param("destination", "Remote peer IP", "text", placeholder="203.0.113.50",
                  help="Public or routable IP of the far-end router."),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="ipsec_site_to_site",
        name="IPsec Site-to-Site VPN",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Full IOS site-to-site IPsec wizard: ISAKMP policy + pre-shared key, "
            "IPsec transform-set, crypto map on a physical interface, and ACL "
            "matching traffic to encrypt. Pair with an existing GRE tunnel or route "
            "to remote networks. Requires reachable peer and matching config on far end."
        ),
        template=(
            "crypto isakmp policy {{ policy_name }}\n"
            " encr {{ encryption }}\n"
            " authentication pre-share\n"
            " group {{ dh_group }}\n"
            "crypto isakmp key {{ key_name }} address {{ peer_ip }} key {{ psk }}\n"
            "crypto ipsec transform-set {{ transform_name }} esp-aes esp-sha-hmac\n"
            "crypto map {{ map_name }} {{ map_seq }} ipsec-isakmp\n"
            " set peer {{ peer_ip }}\n"
            " set transform-set {{ transform_name }}\n"
            " set security-association lifetime seconds {{ sa_lifetime }}\n"
            " match address {{ acl_name }}\n"
            "access-list {{ acl_name }} permit ip {{ local_net }} {{ local_wild }} {{ remote_net }} {{ remote_wild }}\n"
            "interface {{ phy_interface }}\n"
            " crypto map {{ map_name }}"
        ),
        params=[
            Param("policy_name", "ISAKMP policy name", "text", default="VPN-POLICY"),
            Param("key_name", "ISAKMP key name", "text", default="VPN-KEY"),
            Param("psk", "Pre-shared key", "text", placeholder="long-random-secret"),
            Param("peer_ip", "Peer router IP", "text", placeholder="203.0.113.50"),
            Param("encryption", "Encryption", "select", default="aes 256",
                  options=["aes 128", "aes 256", "3des"]),
            Param("dh_group", "DH group", "select", default="2", options=["2", "5", "14"]),
            Param("transform_name", "Transform-set name", "text", default="VPN-TS"),
            Param("map_name", "Crypto map name", "text", default="VPN-MAP"),
            Param("map_seq", "Crypto map sequence", "int", default=10),
            Param("sa_lifetime", "SA lifetime (seconds)", "int", default=3600),
            Param("acl_name", "ACL name", "text", default="VPN-ACL"),
            Param("local_net", "Local network", "text", default="10.0.0.0"),
            Param("local_wild", "Local wildcard", "text", default="0.0.255.255"),
            Param("remote_net", "Remote network", "text", default="172.16.0.0"),
            Param("remote_wild", "Remote wildcard", "text", default="0.0.255.255"),
            Param("phy_interface", "Physical interface", "text",
                  placeholder="GigabitEthernet1/0/24"),
        ],
        save_after=True,
        danger=True,
    ),
    # ---- Layer 2 (STP, DHCP snooping, QoS) --------------------------------
    Action(
        id="enable_dhcp_snooping",
        name="Enable DHCP Snooping (global)",
        category="Layer 2",
        kind="config",
        explanation=(
            "Turns on DHCP snooping switch-wide. Untrusted ports cannot originate "
            "DHCP offers — mitigates rogue DHCP servers. Pair with trust on upl ports."
        ),
        template="ip dhcp snooping",
        save_after=True,
    ),
    Action(
        id="set_dhcp_snoop_trust",
        name="Trust Port (DHCP Snooping)",
        category="Layer 2",
        kind="config",
        explanation=(
            "Marks a port as trusted for DHCP snooping — allows DHCP messages from "
            "devices on that port (typical on upl to another switch)."
        ),
        template=(
            "interface {{ interface }}\n"
            "ip dhcp snooping trust"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
    ),
    Action(
        id="set_portfast",
        name="Enable Portfast",
        category="Layer 2",
        kind="config",
        explanation=(
            "spanning-tree portfast skips listening/learning on access ports so "
            "end devices come up faster. Never use on trunk/uplink ports."
        ),
        template=(
            "interface {{ interface }}\n"
            "spanning-tree portfast"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
    ),
    Action(
        id="set_bpduguard",
        name="Enable BPDU Guard",
        category="Layer 2",
        kind="config",
        explanation=(
            "spanning-tree bpduguard enable shuts the port if it receives BPDUs — "
            "blocks unauthorized switches/hubs on access ports."
        ),
        template=(
            "interface {{ interface }}\n"
            "spanning-tree bpduguard enable"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
    ),
    Action(
        id="set_trust_dscp",
        name="Trust QoS DSCP",
        category="Layer 2",
        kind="config",
        explanation=(
            "mls qos trust dscp honors Differentiated Services Code Point markings "
            "on incoming frames so voice/video traffic can be prioritized."
        ),
        template=(
            "interface {{ interface }}\n"
            "mls qos trust dscp"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
    ),
    Action(
        id="dot1x_port",
        name="Enable 802.1X Port Control",
        category="Security",
        kind="config",
        explanation=(
            "dot1x port-control auto requires clients to authenticate (via RADIUS) "
            "before the port forwards traffic. Requires AAA/RADIUS configured."
        ),
        template=(
            "interface {{ interface }}\n"
            "dot1x port-control auto"
        ),
        params=[Param("interface", "Port(s)", "interface")],
        save_after=True,
        danger=True,
    ),
    # ---- Security -----------------------------------------------------------
    Action(
        id="extended_acl",
        name="Add Extended ACL Rule",
        category="Security",
        kind="config",
        explanation=(
            "Adds one line to an extended IP access-list. Extended ACLs filter "
            "traffic by source/destination. Rules are evaluated in order; "
            "implicit deny-all at the end."
        ),
        template=(
            "ip access-list extended {{ acl_name }}\n"
            "{{ permit_deny }} {{ protocol }} {{ source }} {{ destination }}"
        ),
        params=[
            Param("acl_name", "ACL name", "text", placeholder="BLOCK_GUEST"),
            Param("permit_deny", "Action", "select", default="deny",
                  options=["permit", "deny"]),
            Param("protocol", "Protocol", "select", default="ip",
                  options=["ip", "tcp", "udp", "icmp"]),
            Param("source", "Source", "text", default="any",
                  placeholder="any or 192.168.1.0 0.0.0.255"),
            Param("destination", "Destination", "text", default="any"),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="dmvpn_hub",
        name="DMVPN Hub (GRE multipoint + NHRP)",
        category="Routing & Tunnels",
        kind="config",
        platforms=["ios"],
        explanation=(
            "Hub side of a DMVPN cloud: GRE multipoint tunnel with NHRP network-id, "
            "IPsec profile, and ISAKMP key for any spoke (0.0.0.0). Deploy before "
            "spokes; match PSK, transform-set, and NHRP settings on each spoke."
        ),
        template=(
            "crypto isakmp policy {{ policy_name }}\n"
            " encr {{ encryption }}\n"
            " authentication pre-share\n"
            " group {{ dh_group }}\n"
            "crypto isakmp key {{ key_name }} address 0.0.0.0 0.0.0.0 key {{ psk }}\n"
            "crypto ipsec transform-set {{ transform_name }} esp-aes esp-sha-hmac\n"
            "crypto ipsec profile {{ profile_name }}\n"
            " set transform-set {{ transform_name }}\n"
            " set ikev2 profile default\n"
            "interface Tunnel{{ tunnel_id }}\n"
            " ip address {{ hub_tunnel_ip }} {{ hub_tunnel_mask }}\n"
            " no ip redirects\n"
            " ip nhrp network-id {{ nhrp_id }}\n"
            " ip nhrp authentication {{ nhrp_key }}\n"
            " ip nhrp map {{ hub_public_ip }} {{ nhrp_id }} multicast\n"
            " tunnel source {{ source_if }}\n"
            " tunnel mode gre multipoint\n"
            " tunnel key {{ gre_key }}\n"
            " tunnel protection ipsec profile {{ profile_name }}"
        ),
        params=[
            Param("policy_name", "ISAKMP policy", "text", default="DMVPN-POLICY"),
            Param("key_name", "ISAKMP key name", "text", default="DMVPN-KEY"),
            Param("psk", "Pre-shared key (shared with spokes)", "text", placeholder="long-random-key"),
            Param("encryption", "Encryption", "select", default="aes 256",
                  options=["aes 128", "aes 256"]),
            Param("dh_group", "DH group", "select", default="14", options=["2", "5", "14"]),
            Param("transform_name", "Transform-set", "text", default="DMVPN-TS"),
            Param("profile_name", "IPsec profile", "text", default="DMVPN-PROF"),
            Param("tunnel_id", "Tunnel number", "int", default=0),
            Param("hub_tunnel_ip", "Hub tunnel IP", "text", default="10.255.0.254"),
            Param("hub_tunnel_mask", "Hub tunnel mask", "text", default="255.255.255.252"),
            Param("hub_public_ip", "Hub public IP (NHRP map)", "text", placeholder="203.0.113.1"),
            Param("nhrp_id", "NHRP network-id", "int", default=1),
            Param("nhrp_key", "NHRP authentication key", "text", default="nhrp-secret"),
            Param("gre_key", "GRE tunnel key", "text", default="gre123"),
            Param("source_if", "Source interface (WAN)", "text", default="GigabitEthernet1/0/24"),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="dmvpn_spoke",
        name="DMVPN Spoke (GRE + IPsec profile)",
        category="Routing & Tunnels",
        kind="config",
        platforms=["ios"],
        explanation=(
            "Hub-and-spoke DMVPN spoke: GRE multipoint tunnel protected by IPsec "
            "profile, plus ISAKMP to the hub. Requires matching hub config and "
            "routing protocol on both ends."
        ),
        template=(
            "crypto isakmp policy {{ policy_name }}\n"
            " encr {{ encryption }}\n"
            " authentication pre-share\n"
            " group {{ dh_group }}\n"
            "crypto isakmp key {{ key_name }} address {{ hub_ip }} key {{ psk }}\n"
            "crypto ipsec transform-set {{ transform_name }} esp-aes esp-sha-hmac\n"
            "crypto ipsec profile {{ profile_name }}\n"
            " set transform-set {{ transform_name }}\n"
            " set ikev2 profile default\n"
            "interface Tunnel{{ tunnel_id }}\n"
            " tunnel mode gre multipoint\n"
            " ip address {{ tunnel_ip }} {{ tunnel_mask }}\n"
            " tunnel source {{ source_if }}\n"
            " tunnel destination {{ hub_ip }}\n"
            " tunnel protection ipsec profile {{ profile_name }}"
        ),
        params=[
            Param("policy_name", "ISAKMP policy", "text", default="DMVPN-POLICY"),
            Param("key_name", "ISAKMP key name", "text", default="DMVPN-KEY"),
            Param("psk", "Pre-shared key", "text", placeholder="long-random-key"),
            Param("hub_ip", "Hub public IP", "text", placeholder="203.0.113.1"),
            Param("encryption", "Encryption", "select", default="aes 256",
                  options=["aes 128", "aes 256"]),
            Param("dh_group", "DH group", "select", default="14", options=["2", "5", "14"]),
            Param("transform_name", "Transform-set", "text", default="DMVPN-TS"),
            Param("profile_name", "IPsec profile", "text", default="DMVPN-PROF"),
            Param("tunnel_id", "Tunnel number", "int", default=0),
            Param("tunnel_ip", "Tunnel IP", "text", default="10.255.0.1"),
            Param("tunnel_mask", "Tunnel mask", "text", default="255.255.255.252"),
            Param("source_if", "Source interface", "text", default="GigabitEthernet1/0/24"),
        ],
        save_after=True,
        danger=True,
    ),
    # ---- NX-OS ----------------------------------------------------------------
    Action(
        id="nxos_show_vpc",
        name="Show vPC Status",
        category="NX-OS",
        kind="show",
        platforms=["nxos"],
        explanation="Shows Virtual Port Channel status — peer-link and keepalive on Nexus switches.",
        template="show vpc brief",
    ),
    Action(
        id="nxos_vpc_domain",
        name="Configure vPC Domain",
        category="NX-OS",
        kind="config",
        platforms=["nxos"],
        explanation=(
            "Creates a vPC domain on Nexus: feature vpc, domain ID, peer-link, "
            "and optional peer-keepalive destination."
        ),
        template=(
            "feature vpc\n"
            "vpc domain {{ domain_id }}\n"
            " peer-link {{ peer_link }}\n"
            " role priority {{ priority }}\n"
            " keepalive destination {{ keepalive_dst }}"
        ),
        params=[
            Param("domain_id", "Domain ID", "int", default=1),
            Param("peer_link", "Peer-link port-channel", "text", default="port-channel1"),
            Param("priority", "Role priority", "int", default=100),
            Param("keepalive_dst", "Keepalive dest IP", "text", placeholder="192.168.1.2"),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="nxos_show_lldp",
        name="Show LLDP Neighbors",
        category="NX-OS",
        kind="show",
        platforms=["nxos"],
        explanation="LLDP neighbor table on Nexus (like CDP on IOS).",
        template="show lldp neighbors",
    ),
    Action(
        id="nxos_show_version",
        name="Show NX-OS Version",
        category="NX-OS",
        kind="show",
        platforms=["nxos"],
        explanation="Software version, platform, and uptime on a Nexus switch.",
        template="show version",
    ),
    Action(
        id="nxos_show_run",
        name="Show Running Config (NX-OS)",
        category="NX-OS",
        kind="show",
        platforms=["nxos"],
        explanation="Active configuration on Nexus — same idea as IOS show run.",
        template="show running-config",
    ),
    Action(
        id="nxos_int_status",
        name="Show Interface Status (NX-OS)",
        category="NX-OS",
        kind="show",
        platforms=["nxos"],
        explanation="Port link state and VLAN assignment on Nexus switches.",
        template="show interface status",
        use_textfsm=True,
    ),
    # ---- ASA ------------------------------------------------------------------
    Action(
        id="asa_show_conn",
        name="Show Active Connections",
        category="ASA",
        kind="show",
        platforms=["asa"],
        explanation="Lists active connections through the ASA firewall.",
        template="show conn",
    ),
    Action(
        id="asa_show_xlate",
        name="Show xlate (NAT) Table",
        category="ASA",
        kind="show",
        platforms=["asa"],
        explanation="Shows current translation (NAT) entries on ASA.",
        template="show xlate",
    ),
    Action(
        id="asa_nameif",
        name="Name Firewall Interface",
        category="ASA",
        kind="config",
        platforms=["asa"],
        explanation=(
            "Assigns a logical name (outside/inside/dmz) to a physical ASA interface."
        ),
        template=(
            "interface {{ interface }}\n"
            " nameif {{ if_name }}"
        ),
        params=[
            Param("interface", "Interface", "text", placeholder="GigabitEthernet0/0"),
            Param("if_name", "Name", "select", default="outside",
                  options=["outside", "inside", "dmz"]),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="asa_show_version",
        name="Show ASA Version",
        category="ASA",
        kind="show",
        platforms=["asa"],
        explanation="ASA software version, model, and uptime.",
        template="show version",
    ),
    Action(
        id="asa_show_run",
        name="Show Running Config (ASA)",
        category="ASA",
        kind="show",
        platforms=["asa"],
        explanation="Active firewall configuration.",
        template="show running-config",
    ),
    Action(
        id="asa_access_list",
        name="Add Extended ACL Rule",
        category="ASA",
        kind="config",
        platforms=["asa"],
        explanation=(
            "Adds a line to an extended access-list on ASA. Use for permit/deny "
            "before applying the ACL to an interface."
        ),
        template="access-list {{ acl_name }} {{ action }} {{ protocol }} {{ source }} {{ destination }}",
        params=[
            Param("acl_name", "ACL name", "text", default="OUTSIDE_IN"),
            Param("action", "Action", "select", default="permit", options=["permit", "deny"]),
            Param("protocol", "Protocol", "select", default="ip",
                  options=["ip", "tcp", "udp", "icmp"]),
            Param("source", "Source", "text", default="any"),
            Param("destination", "Destination", "text", default="any"),
        ],
        save_after=True,
        danger=True,
    ),
    # ---- H3C Comware ---------------------------------------------------------
    Action(
        id="comware_show_version",
        name="Show Version (Comware)",
        category="Comware",
        kind="show",
        platforms=["comware"],
        explanation="H3C Comware software version, model, and uptime.",
        template="display version",
    ),
    Action(
        id="comware_show_interfaces",
        name="Show Interfaces (Comware)",
        category="Comware",
        kind="show",
        platforms=["comware"],
        explanation="Display all interface status and statistics.",
        template="display interface",
    ),
    Action(
        id="comware_show_vlan",
        name="Show VLAN (Comware)",
        category="Comware",
        kind="show",
        platforms=["comware"],
        explanation="Display VLAN configuration and port assignments.",
        template="display vlan",
    ),
    Action(
        id="comware_show_current",
        name="Show Current Config (Comware)",
        category="Comware",
        kind="show",
        platforms=["comware"],
        explanation="Display the current running configuration.",
        template="display current-configuration",
    ),
    Action(
        id="comware_set_vlan",
        name="Set Access VLAN (Comware)",
        category="Comware",
        kind="config",
        platforms=["comware"],
        explanation="Assign a port to an access VLAN on H3C Comware switches.",
        template="""interface {{ interface }}
port access vlan {{ vlan }}""",
        params=[
            Param("interface", "Interface", "interface"),
            Param("vlan", "VLAN ID", "vlan", default="1"),
        ],
        save_after=True,
        danger=True,
    ),
    Action(
        id="comware_set_description",
        name="Set Port Description (Comware)",
        category="Comware",
        kind="config",
        platforms=["comware"],
        explanation="Set a description on a Comware interface.",
        template="""interface {{ interface }}
description {{ description }}""",
        params=[
            Param("interface", "Interface", "interface"),
            Param("description", "Description", "text", placeholder="e.g. Uplink to Core"),
        ],
        save_after=True,
    ),
    Action(
        id="comware_save_config",
        name="Save Configuration (Comware)",
        category="Comware",
        kind="config",
        platforms=["comware"],
        explanation="Save running config to startup config (Comware uses 'save' command).",
        template="save force",
        save_after=False,
    ),
    
    # ---- Custom escape hatch -------------------------------------------------
    Action(
        id="custom_show",
        name="Custom Show Command(s)",
        category="Custom",
        kind="show",
        explanation=(
            "Run any read-only exec command(s) you type. One command per line. "
            "Output is captured per device."
        ),
        template="{{ commands }}",
        params=[Param("commands", "Commands (one per line)", "textarea",
                      placeholder="show interfaces description")],
    ),
    Action(
        id="custom_config",
        name="Custom Config Lines",
        category="Custom",
        kind="config",
        explanation=(
            "Push any configuration lines you type, exactly as you'd enter them in "
            "config mode. One command per line. Use with care."
        ),
        template="{{ commands }}",
        params=[Param("commands", "Config lines (one per line)", "textarea",
                      placeholder="interface Gi1/0/1\n description test")],
        save_after=True,
        danger=True,
    ),
]

ACTIONS_BY_ID: dict[str, Action] = {a.id: a for a in ACTIONS}
CATEGORIES: list[str] = list(dict.fromkeys(a.category for a in ACTIONS))


def get_action(action_id: str) -> Action:
    return ACTIONS_BY_ID[action_id]


def platform_family(device_type: str) -> str:
    mapping = {
        "cisco_ios": "ios",
        "cisco_xe": "ios",
        "cisco_nxos": "nxos",
        "cisco_xr": "xr",
        "cisco_asa": "asa",
        "cisco_s300": "ios",
        "hp_comware": "comware",
    }
    return mapping.get(device_type, "ios")


def action_visible(action: Action, device_types: set[str]) -> bool:
    if "all" in action.platforms:
        return True
    families = {platform_family(dt) for dt in device_types}
    return bool(families & set(action.platforms))


def filter_actions(action_list: list[Action], device_types: set[str]) -> list[Action]:
    if not device_types:
        return action_list
    return [a for a in action_list if action_visible(a, device_types)]
