"""Fiberstore NetworkOS specific Action Cards for S3700 series.

All commands verified against the S3700 Software Configuration Guide.
S3700 uses ``ge1``, ``fe1``, ``xe1`` port naming with dot-notation
for VLAN interfaces (``vlan1.10``) and different command syntax
from the S5800 FSOS v2.
"""

from actions.base import Action, Param

NETWORKOS_ACTIONS: list[Action] = [
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
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_port_status",
        name="Check Port Status",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists every interface with its link state (up/down), duplex and speed. "
            "Use it to see which ports are live."
        ),
        template="show interface",
        use_textfsm=False,
        platforms=["fiberstore_networkos"],
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
        template="show vlan",
        use_textfsm=False,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_ip_int_brief",
        name="Show IP Interfaces",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Summarizes Layer-3 interfaces with their IP address and up/down status."
        ),
        template="show ip interface brief",
        use_textfsm=False,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_ip_route",
        name="Show IP Route",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays the routing table: known networks, next-hop IPs and metrics."
        ),
        template="show ip route",
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_mac",
        name="Show MAC Address Table",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Maps learned MAC addresses to the physical port and VLAN where the "
            "switch last saw them."
        ),
        template="show mac-address-table",
        use_textfsm=False,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_version",
        name="Show Version / Model",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Reports the software version, model, uptime and serial number."
        ),
        template="show version",
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_interface_switchport",
        name="Show Interface Switchport",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays the administrative and operational VLAN mode and membership "
            "for each interface — access, trunk or hybrid, native VLAN, allowed VLANs."
        ),
        template="show interfaces switchport",
        use_textfsm=False,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_stp",
        name="Show Spanning Tree",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays spanning-tree state including root bridge, port roles, "
            "and forwarding state per interface."
        ),
        template="show spanning-tree mst",
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="show_mac_binding",
        name="Show Port Security / MAC Binding",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays all port security MAC binding entries configured on the switch."
        ),
        template="show port-security",
        use_textfsm=False,
        platforms=["fiberstore_networkos"],
    ),
    # ---- Port configuration (config) ----------------------------------------
    Action(
        id="set_access_vlan",
        name="Change Interface VLAN",
        category="Port Config",
        kind="config",
        explanation=(
            "Assigns a physical port to an access VLAN. This places the port "
            "into a network segment (untagged member)."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport access vlan {{ vlan }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface",
                  help="The port(s) to modify (e.g. ge1)."),
            Param("vlan", "Access VLAN ID", "int", default=1,
                  help="VLAN number (2-4094) to place the port into."),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_trunk",
        name="Configure Trunk Port",
        category="Port Config",
        kind="config",
        explanation=(
            "Sets a port to trunk mode — it carries multiple VLANs with 802.1Q "
            "tags. Optionally restrict allowed VLANs."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport mode trunk\n"
            "{% if allowed_vlans %}switchport trunk allowed vlan add {{ allowed_vlans }}{% endif %}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("allowed_vlans", "Allowed VLANs (comma-sep, optional)", "text",
                  default="", placeholder="10,20,30-40",
                  help="Leave blank to allow all VLANs."),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_description",
        name="Update Port Description",
        category="Port Config",
        kind="config",
        explanation=(
            "Sets a human-readable label on a port. It changes nothing functionally "
            "but documents what is plugged in."
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
        platforms=["fiberstore_networkos"],
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
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_portfast",
        name="Enable Spanning-Tree Portfast",
        category="Port Config",
        kind="config",
        explanation=(
            "Places a port in spanning-tree PortFast mode — skips listening and "
            "learning states so end-hosts connect immediately."
        ),
        template=(
            "interface {{ interface }}\n"
            "spanning-tree portfast"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_bpduguard",
        name="Enable BPDU Guard",
        category="Port Config",
        kind="config",
        explanation=(
            "Disables a port if it receives BPDUs — protects against accidental "
            "loops caused by rogue switches."
        ),
        template=(
            "interface {{ interface }}\n"
            "spanning-tree portfast bpdu-guard enable"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_pvid_dot1x",
        name="Set PVID (with 802.1X option)",
        category="Port Config",
        kind="config",
        explanation=(
            "Sets a port's PVID (access VLAN) and optionally enables 802.1X "
            "with a guest VLAN. Applies spanning-tree BPDU guard for port "
            "security. Two modes: with 802.1X (dot1x + guest-vlan) or "
            "without 802.1X (VLAN only)."
        ),
        template=(
            "interface {{ interface }}\n"
            "{% if enable_dot1x %}"
            "dot1x port-control auto\n"
            "dot1x guest-vlan {{ guest_vlan }}\n"
            "{% endif %}"
            "spanning-tree portfast bpdu-guard enable\n"
            "switchport access vlan {{ vlan }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface",
                  help="Port to configure, e.g. ge1, fe1"),
            Param("vlan", "Access VLAN ID", "int", default=100,
                  help="VLAN number (1-4094) to assign as the port's access VLAN."),
            Param("enable_dot1x", "Enable 802.1X + guest VLAN", "bool",
                  default=False,
                  help="Check to add dot1x port-control auto and guest-vlan."),
            Param("guest_vlan", "802.1X Guest VLAN ID", "int", default=5,
                  help="Guest VLAN used when 802.1X is enabled."),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_storm_control",
        name="Storm Control",
        category="Port Config",
        kind="config",
        explanation=(
            "Configures broadcast, multicast or unknown unicast storm control "
            "with a percentage threshold."
        ),
        template=(
            "interface {{ interface }}\n"
            "storm-control broadcast level {{ bcast_level }}\n"
            "storm-control multicast level {{ mcast_level }}\n"
            "storm-control dlf level {{ dlf_level }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("bcast_level", "Broadcast threshold (0.0-100.0%)", "text",
                  default="10.0", help="0.0 to disable."),
            Param("mcast_level", "Multicast threshold (0.0-100.0%)", "text",
                  default="100.0", help="0.0 to disable."),
            Param("dlf_level", "Unknown unicast (DLF) threshold (0.0-100.0%)", "text",
                  default="10.0", help="0.0 to disable."),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_rate_limit",
        name="Port Rate Limiting",
        category="Port Config",
        kind="config",
        explanation=(
            "Limits the ingress or egress data rate on a port. "
            "Rate must be a multiple of 64 kbps, minimum 64 kbps."
        ),
        template=(
            "interface {{ interface }}\n"
            "line-rate ingress {{ ingress_rate }}k\n"
            "line-rate egress {{ egress_rate }}k"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("ingress_rate", "Ingress rate limit (kbps, multiple of 64)", "int",
                  default=0, help="0 = no limit."),
            Param("egress_rate", "Egress rate limit (kbps, multiple of 64)", "int",
                  default=0, help="0 = no limit."),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_mac_binding",
        name="MAC Binding (Port Security)",
        category="Port Config",
        kind="config",
        explanation=(
            "Binds a specific MAC address to a port and VLAN. Only this MAC "
            "will be allowed to communicate through the port."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport port-security mac-address {{ mac_addr }} vlan {{ vlan_id }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("mac_addr", "MAC address", "text",
                  placeholder="0011.2233.4455",
                  help="MAC address in HHHH.HHHH.HHHH format"),
            Param("vlan_id", "VLAN ID", "int", default=1),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    # ---- Switch Config -------------------------------------------------------
    Action(
        id="create_vlan",
        name="Create VLAN",
        category="Switch Config",
        kind="config",
        explanation=(
            "Creates a new VLAN (network segment) in the switch database and optionally "
            "gives it a name. Ports can then be assigned to it."
        ),
        template=(
            "vlan database\n"
            "vlan {{ vlan }} name {{ vlan_name }}"
        ),
        params=[
            Param("vlan", "VLAN ID", "int", default=20),
            Param("vlan_name", "VLAN Name", "text", placeholder="ACCOUNTING"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="delete_vlan",
        name="Delete VLAN",
        category="Switch Config",
        kind="config",
        explanation=(
            "Deletes a VLAN from the switch database."
        ),
        template=(
            "vlan database\n"
            "no vlan {{ vlan }}"
        ),
        params=[
            Param("vlan", "VLAN ID", "int", default=20),
        ],
        save_after=True,
        danger=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_hostname",
        name="Set Hostname",
        category="Switch Config",
        kind="config",
        explanation=(
            "Changes the device name shown in the CLI prompt."
        ),
        template="hostname {{ hostname }}",
        params=[Param("hostname", "Hostname", "text", placeholder="SW-FLOOR2-ACCESS")],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="save_config",
        name="Save Configuration",
        category="Switch Config",
        kind="config",
        explanation=(
            "Saves the running-config to startup-config so changes survive a reboot."
        ),
        template="write",
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_svi_ip",
        name="Set SVI IP Address",
        category="Switch Config",
        kind="config",
        explanation=(
            "Configures an IP address on a switched virtual interface (VLAN "
            "sub-interface). This gives the switch an IP on that VLAN."
        ),
        template=(
            "interface vlan1.{{ vlan_id }}\n"
            "ip address {{ ip_address }}/{{ mask_length }}"
        ),
        params=[
            Param("vlan_id", "VLAN ID", "int", default=1),
            Param("ip_address", "IP Address", "text", placeholder="192.168.1.1"),
            Param("mask_length", "Subnet mask length", "int", default=24,
                  help="e.g. 24 for 255.255.255.0"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_mac_aging",
        name="Set MAC Aging Time",
        category="Switch Config",
        kind="config",
        explanation=(
            "Sets the length of time a dynamically learned MAC address remains "
            "in the address table after it is last used."
        ),
        template=(
            "mac-address-table aging-time {{ seconds }}"
        ),
        params=[
            Param("seconds", "Aging time (seconds)", "int", default=300,
                  help="10-1000000, or 0 to disable aging."),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="set_static_arp",
        name="Add Static ARP",
        category="Switch Config",
        kind="config",
        explanation=(
            "Adds a permanent static ARP entry to the ARP cache."
        ),
        template=(
            "arp {{ ip_address }} {{ mac_addr }}"
        ),
        params=[
            Param("ip_address", "IP Address", "text", placeholder="192.168.1.1"),
            Param("mac_addr", "MAC Address", "text",
                  placeholder="0011.2233.4455",
                  help="MAC address in HHHH.HHHH.HHHH format"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="enable_web",
        name="Enable Web Interface",
        category="Switch Config",
        kind="config",
        explanation=(
            "Enables the web management interface on the switch. "
            "Configure a management VLAN IP first, then enable the web "
            "server with optional credentials for login."
        ),
        template=(
            "web enable\n"
            "{% if username %}username {{ username }} password {{ password }}\n{% endif %}"
            "{% if mgmt_ip %}interface vlan1.{{ mgmt_vlan }}\n"
            "ip address {{ mgmt_ip }}/{{ mgmt_mask }}\n"
            "no shutdown\n{% endif %}"
        ),
        params=[
            Param("username", "Web login username", "text", default="admin",
                  placeholder="admin"),
            Param("password", "Web login password", "text", default="admin",
                  placeholder="admin"),
            Param("mgmt_vlan", "Management VLAN ID", "int", default=1,
                  help="VLAN for the management IP."),
            Param("mgmt_ip", "Management IP address (optional)", "text",
                  default="", placeholder="192.168.1.100"),
            Param("mgmt_mask", "Management mask length", "int", default=24,
                  help="e.g. 24 for 255.255.255.0"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    # ---- Routing & Tunnels ---------------------------------------------------
    Action(
        id="static_route",
        name="Add Static Route",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Installs a static route: traffic to the destination network is "
            "forwarded to the next-hop IP."
        ),
        template="ip route {{ network }}/{{ mask_length }} {{ next_hop }}",
        params=[
            Param("network", "Destination network", "text", placeholder="192.168.4.0"),
            Param("mask_length", "Subnet mask length", "int", default=24,
                  help="e.g. 24 for 255.255.255.0"),
            Param("next_hop", "Next-hop IP", "text", placeholder="192.168.3.2"),
        ],
        save_after=True,
        danger=True,
        platforms=["fiberstore_networkos"],
    ),
    # ---- Security ------------------------------------------------------------
    Action(
        id="standard_acl",
        name="Standard ACL",
        category="Security",
        kind="config",
        explanation=(
            "Creates a standard IP access-list that matches source IP addresses. "
            "Apply it to an interface to filter traffic."
        ),
        template=(
            "access-list {{ acl_num }} {{ action }} {{ source }}{% if source_wildcard %} {{ source_wildcard }}{% endif %}"
        ),
        params=[
            Param("acl_num", "ACL number (1-99, 1300-1999)", "int", default=1),
            Param("action", "Action (permit/deny)", "select",
                  options=["permit", "deny"], default="deny"),
            Param("source", "Source network or 'any'/'host x.x.x.x'", "text",
                  default="any", placeholder="192.168.1.0"),
            Param("source_wildcard", "Source wildcard mask (optional)", "text",
                  default="", placeholder="0.0.0.255"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
    ),
    Action(
        id="extended_acl",
        name="Extended ACL",
        category="Security",
        kind="config",
        explanation=(
            "Creates an extended IP access-list that matches source and "
            "destination IP/ports. Apply it to an interface to filter traffic."
        ),
        template=(
            "access-list {{ acl_num }} {{ action }} {{ protocol }} {{ source }} {{ source_wildcard }} {{ dest }} {{ dest_wildcard }}"
        ),
        params=[
            Param("acl_num", "ACL number (100-199, 2000-2699)", "int", default=100),
            Param("action", "Action (permit/deny)", "select",
                  options=["permit", "deny"], default="deny"),
            Param("protocol", "Protocol (ip/tcp/udp/icmp)", "text", default="ip",
                  placeholder="ip"),
            Param("source", "Source or 'any'/'host x.x.x.x'", "text",
                  default="any", placeholder="192.168.1.0"),
            Param("source_wildcard", "Source wildcard mask", "text",
                  default="", placeholder="0.0.0.255"),
            Param("dest", "Destination or 'any'/'host x.x.x.x'", "text",
                  default="any", placeholder="10.0.0.0"),
            Param("dest_wildcard", "Destination wildcard mask", "text",
                  default="", placeholder="0.0.0.255"),
        ],
        save_after=True,
        platforms=["fiberstore_networkos"],
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
                      placeholder="show interface ge1")],
        platforms=["fiberstore_networkos"],
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
                      placeholder="interface ge1\n description test")],
        save_after=True,
        danger=True,
        platforms=["fiberstore_networkos"],
    ),
]

# Export the actions list
ACTIONS = NETWORKOS_ACTIONS