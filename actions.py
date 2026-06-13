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
    save_after: bool = False  # offer 'write memory' for config actions
    use_textfsm: bool = False
    danger: bool = False

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
