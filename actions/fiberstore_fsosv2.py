"""Fiberstore (FS.com) specific Action Cards for S5800 series.

All commands verified against the S5800 CLI Reference Guide.
FSOS uses ``interface eth-0-1`` port naming and space-separated
interface type names (e.g. ``GigabitEthernet 1/0/1``).
"""

from actions.base import Action, Param

FSOS_ACTIONS: list[Action] = [
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
        platforms=["fiberstore_fsosv2"],
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
        template="show interface status",
        use_textfsm=False,
        platforms=["fiberstore_fsosv2"],
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
        template="show vlan all",
        use_textfsm=False,
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="show_interface_switchport",
        name="Show Interface Switchport",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays the administrative and operational VLAN mode and membership "
            "for each interface — access or trunk, native VLAN, allowed VLANs."
        ),
        template="show interfaces switchport",
        use_textfsm=False,
        platforms=["fiberstore_fsosv2"],
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
        template="show spanning-tree",
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="show_lldp",
        name="Show LLDP Neighbors",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists directly connected LLDP neighbors with device ID, local/remote "
            "port, platform and capabilities."
        ),
        template="show lldp neighbors detail",
        use_textfsm=False,
        platforms=["fiberstore_fsosv2"],
    ),
    # ---- Port configuration (config) ----------------------------------------
    Action(
        id="set_access_vlan",
        name="Change Interface VLAN",
        category="Port Config",
        kind="config",
        explanation=(
            "Assigns a physical port to an access VLAN. This places the port "
            "into a network segment, so the connected device joins that broadcast domain."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport access vlan {{ vlan }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface",
                  help="The port(s) to modify."),
            Param("vlan", "Access VLAN ID", "int", default=1,
                  help="VLAN number (1-4094) to place the port into."),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
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
            "switchport trunk native vlan {{ native_vlan }}\n"
            "{% if allowed_vlans %}switchport trunk allowed vlan add {{ allowed_vlans }}{% endif %}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("native_vlan", "Native VLAN", "int", default=1,
                  help="Untagged VLAN on the trunk."),
            Param("allowed_vlans", "Allowed VLANs (comma-sep, optional)", "text",
                  default="", placeholder="10,20,30-40",
                  help="Leave blank to allow all VLANs."),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
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
            "spanning-tree edgeport\n"
            "spanning-tree edgeport bpdu-guard enable"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
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
            "spanning-tree edgeport bpdu-guard enable"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="set_storm_control",
        name="Storm Control",
        category="Port Config",
        kind="config",
        explanation=(
            "Configures broadcast, multicast or unknown unicast storm control "
            "with a percentage or PPS threshold."
        ),
        template=(
            "interface {{ interface }}\n"
            "storm-control broadcast level {{ bcast_level }}\n"
            "storm-control multicast level {{ mcast_level }}\n"
            "storm-control unicast level {{ ucast_level }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("bcast_level", "Broadcast threshold (0.00-100.00%)", "text",
                  default="80.00", help="0.00 to disable."),
            Param("mcast_level", "Multicast threshold (0.00-100.00%)", "text",
                  default="80.00", help="0.00 to disable."),
            Param("ucast_level", "Unknown unicast threshold (0.00-100.00%)", "text",
                  default="80.00", help="0.00 to disable."),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="set_flow_control",
        name="Flow Control",
        category="Port Config",
        kind="config",
        explanation=(
            "Enables or disables 802.3x flow control (pause frames) on a port. "
            "Useful for preventing packet loss during congestion."
        ),
        template=(
            "interface {{ interface }}\n"
            "flowcontrol send {{ send }}\n"
            "flowcontrol receive {{ receive }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("send", "Send (on/off)", "select",
                  options=["on", "off"], default="on"),
            Param("receive", "Receive (on/off)", "select",
                  options=["on", "off"], default="on"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="set_loopback_detect",
        name="Loopback Detection",
        category="Port Config",
        kind="config",
        explanation=(
            "Enables loopback detection on a port — the switch periodically sends "
            "detection packets and shuts down / blocks the port if a loop is found."
        ),
        template=(
            "interface {{ interface }}\n"
            "loopback-detect enable\n"
            "loopback-detect action {{ action }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("action", "Action on loop (shutdown/trap/block)", "select",
                  options=["shutdown", "trap", "block"], default="shutdown"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="set_voice_vlan",
        name="Set Voice VLAN",
        category="Port Config",
        kind="config",
        explanation=(
            "Configures a voice VLAN on an access port — IP phone traffic is "
            "tagged on the voice VLAN while the PC stays on the data VLAN."
        ),
        template=(
            "interface {{ interface }}\n"
            "switchport mode access\n"
            "switchport access vlan {{ data_vlan }}\n"
            "voice vlan enable"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("data_vlan", "Data VLAN ID", "int", default=1),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="dot1x_port",
        name="Enable 802.1X",
        category="Port Config",
        kind="config",
        explanation=(
            "Enables 802.1X port-based access control — the switch will require "
            "client authentication via RADIUS before forwarding traffic."
        ),
        template=(
            "interface {{ interface }}\n"
            "dot1x port-control auto"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    # ---- PoE -----------------------------------------------------------------
    Action(
        id="poe_enable",
        name="Enable PoE",
        category="PoE",
        kind="config",
        explanation=(
            "Turns on Power over Ethernet for the selected ports — the switch "
            "will supply power if the device requests it."
        ),
        template=(
            "interface {{ interface }}\n"
            "power inline auto"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="poe_disable",
        name="Disable PoE",
        category="PoE",
        kind="config",
        explanation=(
            "Stops delivering power on the selected ports. The connected device "
            "must use its own power supply."
        ),
        template=(
            "interface {{ interface }}\n"
            "power inline never"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    # ---- Switch Config -------------------------------------------------------
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
            "vlan database\n"
            "vlan {{ vlan }} name {{ vlan_name }}"
        ),
        params=[
            Param("vlan", "VLAN ID", "int", default=20),
            Param("vlan_name", "VLAN Name", "text", placeholder="ACCOUNTING"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
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
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="save_config",
        name="Save Configuration",
        category="Switch Config",
        kind="config",
        explanation=(
            "Saves the running-config to startup-config so changes survive a reboot."
        ),
        template="",
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="set_svi_ip",
        name="Set SVI IP Address",
        category="Switch Config",
        kind="config",
        explanation=(
            "Configures an IP address on a switched virtual interface (VLAN "
            "interface). This gives the switch an IP on that VLAN."
        ),
        template=(
            "interface vlan {{ vlan_id }}\n"
            "ip address {{ ip_address }} {{ subnet_mask }}"
        ),
        params=[
            Param("vlan_id", "VLAN ID", "int", default=1),
            Param("ip_address", "IP Address", "text", placeholder="192.168.1.1"),
            Param("subnet_mask", "Subnet Mask", "text", default="255.255.255.0"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="enable_dhcp_snooping",
        name="Enable DHCP Snooping (global)",
        category="Switch Config",
        kind="config",
        explanation=(
            "Globally enables DHCP snooping on the switch and enables it on "
            "specified VLANs."
        ),
        template=(
            "ip dhcp snooping\n"
            "ip dhcp snooping vlan {{ vlans }}"
        ),
        params=[
            Param("vlans", "VLANs (comma-sep, range ok)", "text",
                  default="1", placeholder="10,20,30-40"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="set_dhcp_snoop_trust",
        name="Trust DHCP Snooping",
        category="Port Config",
        kind="config",
        explanation=(
            "Marks a port as trusted for DHCP snooping — it is allowed to send "
            "DHCP server responses. Typically enabled on uplinks."
        ),
        template=(
            "interface {{ interface }}\n"
            "ip dhcp snooping trust"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="banner_motd",
        name="Set MOTD Banner",
        category="Switch Config",
        kind="config",
        explanation=(
            "Sets a message-of-the-day banner that appears on all connected "
            "terminals before login."
        ),
        template=(
            "banner motd #{{ message }}#"
        ),
        params=[
            Param("message", "Banner message", "textarea",
                  placeholder="Authorized access only"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="enable_ssh",
        name="Enable SSH Server",
        category="Switch Config",
        kind="config",
        explanation=(
            "Enables the SSH server on the switch for secure remote management. "
            "Must have a host key configured first."
        ),
        template=(
            "ip ssh server enable"
        ),
        platforms=["fiberstore_fsosv2"],
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
        template="ip route {{ network }} {{ mask }} {{ next_hop }}",
        params=[
            Param("network", "Destination network", "text", placeholder="10.0.0.0"),
            Param("mask", "Destination mask", "text", default="255.255.255.0"),
            Param("next_hop", "Next-hop IP", "text", placeholder="192.168.1.254"),
        ],
        save_after=True,
        danger=True,
        platforms=["fiberstore_fsosv2"],
    ),
    # ---- Security ------------------------------------------------------------
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
            "ip access-list extended {{ acl_name }}\n"
            "{% for line in acl_entries.splitlines() if line.strip() %}"
            " {{ line.strip() }}\n"
            "{% endfor %}"
        ),
        params=[
            Param("acl_name", "ACL name", "text", placeholder="DENY-TELNET"),
            Param("acl_entries", "ACL entries (one per line)", "textarea",
                  placeholder="deny tcp any any eq 23\npermit ip any any"),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
    ),
    Action(
        id="port_security",
        name="Port Security (MAC limit)",
        category="Security",
        kind="config",
        explanation=(
            "Limits the number of MAC addresses that can be learned on a port. "
            "Excess traffic is dropped or the port is disabled."
        ),
        template=(
            "interface {{ interface }}\n"
            "port-security max-mac-count {{ max_mac }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("max_mac", "Max MAC addresses", "int", default=5,
                  help="1-128 max learned addresses."),
        ],
        save_after=True,
        platforms=["fiberstore_fsosv2"],
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
                      placeholder="show interface eth-0-1")],
        platforms=["fiberstore_fsosv2"],
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
                      placeholder="interface eth-0-1\n description test")],
        save_after=True,
        danger=True,
        platforms=["fiberstore_fsosv2"],
    ),
]

# Export the actions list
ACTIONS = FSOS_ACTIONS