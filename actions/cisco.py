"""Cisco IOS/XE/NX-OS/ASA specific Action Cards."""

from actions.base import Action, Param

CISCO_ACTIONS: list[Action] = [
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        template="show mac address-table",
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"],
    ),
    Action(
        id="show_cdp",
        name="Show CDP Neighbors",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Lists directly connected Cisco devices discovered via CDP, showing "
            "device ID, local/remote port and platform."
        ),
        template="show cdp neighbors detail",
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
    ),
    Action(
        id="show_stp",
        name="Show Spanning Tree",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Displays spanning-tree state per VLAN/port, including root bridge, "
            "port role (root/designated/alternate) and status."
        ),
        template="show spanning-tree",
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
    ),
    Action(
        id="show_power_inline",
        name="Show PoE Status",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Shows power consumption and class for each PoE-capable port."
        ),
        template="show power inline",
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="show_dhcp_snoop",
        name="Show DHCP Snooping",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Shows DHCP snooping binding table and trust state per port."
        ),
        template="show ip dhcp snooping binding",
        use_textfsm=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="show_crypto",
        name="Show Crypto / IPsec",
        category="Diagnostics",
        kind="show",
        explanation=(
            "Summarises active IPsec tunnels, ISAKMP SA, and crypto-map bindings."
        ),
        template="show crypto ipsec sa",
        platforms=["cisco_ios", "cisco_xe", "cisco_asa"],
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
        platforms=["cisco_ios", "cisco_xe"],
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
            "switchport trunk encapsulation dot1q\n"
            "switchport mode trunk\n"
            "switchport trunk native vlan {{ native_vlan }}\n"
            "{% if allowed_vlans %}switchport trunk allowed vlan {{ allowed_vlans }}{% endif %}"
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
        platforms=["cisco_ios", "cisco_xe"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
            "spanning-tree portfast\n"
            "spanning-tree bpduguard enable"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe"],
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
            "spanning-tree bpduguard enable"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe"],
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
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="set_trust_dscp",
        name="Trust QoS DSCP / Cos",
        category="Port Config",
        kind="config",
        explanation=(
            "Configures the port to trust incoming DSCP or CoS markings for QoS "
            "queuing. Common on uplinks that carry voice."
        ),
        template=(
            "interface {{ interface }}\n"
            "mls qos trust dscp"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe"],
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
            "switchport voice vlan {{ voice_vlan }}"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
            Param("data_vlan", "Data VLAN ID", "int", default=1),
            Param("voice_vlan", "Voice VLAN ID", "int", default=100),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="dot1x_port",
        name="Enable 802.1X (port-control auto)",
        category="Port Config",
        kind="config",
        explanation=(
            "Sets the port to 802.1X port-control auto — the switch will require "
            "client authentication via RADIUS before forwarding traffic."
        ),
        template=(
            "interface {{ interface }}\n"
            "authentication port-control auto\n"
            "dot1x pae authenticator"
        ),
        params=[
            Param("interface", "Port(s)", "interface"),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe"],
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
        platforms=["cisco_ios", "cisco_xe"],
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
        platforms=["cisco_ios", "cisco_xe"],
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
            "vlan {{ vlan }}\n"
            "name {{ vlan_name }}"
        ),
        params=[
            Param("vlan", "VLAN ID", "int", default=20),
            Param("vlan_name", "VLAN Name", "text", placeholder="ACCOUNTING"),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
    ),
    Action(
        id="save_config",
        name="Save Configuration",
        category="Switch Config",
        kind="config",
        explanation=(
            "Saves the running-config to startup-config so changes survive a reboot."
        ),
        template="",  # handled via save flag
        save_after=True,
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"],
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
        platforms=["cisco_ios", "cisco_xe"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos"],
    ),
    Action(
        id="gre_tunnel",
        name="Add GRE Tunnel",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Creates a GRE tunnel interface. GRE encapsulates arbitrary L3 "
            "packets between tunnel source and destination — often paired with IPsec."
        ),
        template=(
            "interface tunnel{{ tunnel_id }}\n"
            "tunnel source {{ source }}\n"
            "tunnel destination {{ destination }}\n"
            "ip address {{ ip_address }} {{ subnet_mask }}"
        ),
        params=[
            Param("tunnel_id", "Tunnel ID", "int", default=0),
            Param("source", "Source IP / interface", "text",
                  placeholder="192.168.1.1"),
            Param("destination", "Destination IP", "text",
                  placeholder="10.0.0.1"),
            Param("ip_address", "Tunnel IP", "text", placeholder="172.16.0.1"),
            Param("subnet_mask", "Subnet Mask", "text", default="255.255.255.0"),
        ],
        save_after=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="ipsec_site_to_site",
        name="IPsec Site-to-Site VPN",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Deploys an IPsec site-to-site VPN — ISAKMP policy, transform set, "
            "crypto ACL, and crypto map applied to the outside interface."
        ),
        template=(
            "crypto isakmp policy {{ isakmp_priority }}\n"
            "encryption aes 256\n"
            "hash sha256\n"
            "group 14\n"
            "authentication pre-share\n"
            "lifetime 86400\n"
            "!\n"
            "crypto isakmp key {{ psk }} address {{ peer_ip }}\n"
            "!\n"
            "crypto ipsec transform-set {{ transform }} esp-aes 256 esp-sha-hmac\n"
            "!\n"
            "ip access-list extended {{ acl_name }}\n"
            "permit ip {{ local_net }} {{ local_mask }} {{ remote_net }} {{ remote_mask }}\n"
            "!\n"
            "crypto map {{ crypto_map }} 10 ipsec-isakmp\n"
            "set peer {{ peer_ip }}\n"
            "set transform-set {{ transform }}\n"
            "match address {{ acl_name }}\n"
            "!\n"
            "interface {{ outside_iface }}\n"
            "crypto map {{ crypto_map }}"
        ),
        params=[
            Param("isakmp_priority", "ISAKMP priority", "int", default=1),
            Param("psk", "Pre-shared key", "text",
                  default="CiscoManSecret123!", help="Shared secret for auth."),
            Param("peer_ip", "Peer (remote router) IP", "text",
                  placeholder="10.0.0.2"),
            Param("transform", "Transform set name", "text", default="AES256-SHA"),
            Param("acl_name", "Crypto ACL name", "text", default="VPN-ACL"),
            Param("local_net", "Local network", "text", placeholder="192.168.0.0"),
            Param("local_mask", "Local mask", "text", default="255.255.255.0"),
            Param("remote_net", "Remote network", "text", placeholder="10.0.0.0"),
            Param("remote_mask", "Remote mask", "text", default="255.255.255.0"),
            Param("outside_iface", "Outside interface", "text", placeholder="GigabitEthernet0/0/0"),
        ],
        save_after=True,
        danger=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="dmvpn_hub",
        name="DMVPN Hub Setup",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Configures the DMVPN hub — GRE multipoint tunnel, NHRP with "
            "server role, and IPsec protection. Deploy this first, then spokes."
        ),
        template=(
            "crypto isakmp policy 10\n"
            "encryption aes 256\n"
            "hash sha256\n"
            "group 14\n"
            "authentication pre-share\n"
            "lifetime 86400\n"
            "!\n"
            "crypto isakmp key {{ psk }} address 0.0.0.0 0.0.0.0\n"
            "!\n"
            "crypto ipsec transform-set DMVPN-IPSEC esp-aes 256 esp-sha-hmac\n"
            "mode transport\n"
            "!\n"
            "crypto ipsec profile DMVPN-PROFILE\n"
            "set transform-set DMVPN-IPSEC\n"
            "!\n"
            "interface Tunnel0\n"
            "ip address {{ tunnel_ip }} {{ tunnel_mask }}\n"
            "ip mtu 1400\n"
            "ip nhrp authentication {{ nhrp_key }}\n"
            "ip nhrp map multicast dynamic\n"
            "ip nhrp network-id {{ network_id }}\n"
            "ip nhrp holdtime 600\n"
            "tunnel source {{ source }}\n"
            "tunnel mode gre multipoint\n"
            "tunnel key {{ gre_key }}\n"
            "tunnel protection ipsec profile DMVPN-PROFILE"
        ),
        params=[
            Param("psk", "Pre-shared key", "text", default="CiscoManVPN!"),
            Param("tunnel_ip", "Tunnel IP (hub)", "text", placeholder="172.16.0.1"),
            Param("tunnel_mask", "Tunnel mask", "text", default="255.255.255.0"),
            Param("nhrp_key", "NHRP authentication key", "text", default="nhrp-secret"),
            Param("network_id", "NHRP network-id", "int", default=100),
            Param("source", "Hub outside interface / IP", "text",
                  placeholder="GigabitEthernet0/0/0"),
            Param("gre_key", "GRE tunnel key", "int", default=0),
        ],
        save_after=True,
        danger=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    Action(
        id="dmvpn_spoke",
        name="DMVPN Spoke Setup",
        category="Routing & Tunnels",
        kind="config",
        explanation=(
            "Configures a DMVPN spoke — connects to the hub with matching "
            "PSK, NHRP network-id and transform set."
        ),
        template=(
            "crypto isakmp policy 10\n"
            "encryption aes 256\n"
            "hash sha256\n"
            "group 14\n"
            "authentication pre-share\n"
            "lifetime 86400\n"
            "!\n"
            "crypto isakmp key {{ psk }} address {{ hub_ip }}\n"
            "!\n"
            "crypto ipsec transform-set DMVPN-IPSEC esp-aes 256 esp-sha-hmac\n"
            "mode transport\n"
            "!\n"
            "crypto ipsec profile DMVPN-PROFILE\n"
            "set transform-set DMVPN-IPSEC\n"
            "!\n"
            "interface Tunnel0\n"
            "ip address {{ tunnel_ip }} {{ tunnel_mask }}\n"
            "ip mtu 1400\n"
            "ip nhrp authentication {{ nhrp_key }}\n"
            "ip nhrp map {{ hub_tunnel_ip }} {{ hub_ip }}\n"
            "ip nhrp map multicast {{ hub_ip }}\n"
            "ip nhrp network-id {{ network_id }}\n"
            "ip nhrp nhs {{ hub_tunnel_ip }}\n"
            "ip nhrp holdtime 600\n"
            "tunnel source {{ source }}\n"
            "tunnel destination {{ hub_ip }}\n"
            "tunnel key {{ gre_key }}\n"
            "tunnel protection ipsec profile DMVPN-PROFILE"
        ),
        params=[
            Param("psk", "Pre-shared key (must match hub)", "text", default="CiscoManVPN!"),
            Param("hub_ip", "Hub public IP", "text", placeholder="1.2.3.4"),
            Param("hub_tunnel_ip", "Hub tunnel IP", "text", placeholder="172.16.0.1"),
            Param("tunnel_ip", "Spoke tunnel IP", "text", placeholder="172.16.0.2"),
            Param("tunnel_mask", "Tunnel mask", "text", default="255.255.255.0"),
            Param("nhrp_key", "NHRP authentication key (match hub)", "text", default="nhrp-secret"),
            Param("network_id", "NHRP network-id (match hub)", "int", default=100),
            Param("source", "Spoke outside interface / IP", "text",
                  placeholder="GigabitEthernet0/0/0"),
            Param("gre_key", "GRE tunnel key (match hub)", "int", default=0),
        ],
        save_after=True,
        danger=True,
        platforms=["cisco_ios", "cisco_xe"],
    ),
    # ---- Security ------------------------------------------------------------
    Action(
        id="extended_acl",
        name="Extended ACL",
        category="Security",
        kind="config",
        explanation=(
            "Creates an extended IP access-list that matches source and "
            "destination IP/ports. Apply it to an interface via the action page."
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"],
    ),
    # ---- NX-OS specific ------------------------------------------------------
    Action(
        id="nxos_show_vpc",
        name="Show vPC Status",
        category="NX-OS",
        kind="show",
        explanation=(
            "Displays the vPC (Virtual Port Channel) status — peer, keepalive, "
            "consistency and per-member state."
        ),
        template="show vpc",
        platforms=["cisco_nxos"],
    ),
    Action(
        id="nxos_vpc_domain",
        name="Configure vPC Domain",
        category="NX-OS",
        kind="config",
        explanation=(
            "Creates or updates a vPC domain with peer-link, keepalive (using mgmt0), "
            "and a consistent VLAN list."
        ),
        template=(
            "vpc domain {{ domain_id }}\n"
            "role priority {{ priority }}\n"
            "peer-keepalive destination {{ peer_ip }} source {{ local_ip }} vrf management\n"
            "peer gateway\n"
            "auto-recovery\n"
            "delay restore 120\n"
            "ip arp synchronize"
        ),
        params=[
            Param("domain_id", "vPC domain ID", "int", default=100),
            Param("priority", "Role priority (lower = primary)", "int", default=32667),
            Param("peer_ip", "Peer mgmt0 IP", "text", placeholder="10.1.1.2"),
            Param("local_ip", "Local mgmt0 IP", "text", placeholder="10.1.1.1"),
        ],
        save_after=True,
        danger=True,
        platforms=["cisco_nxos"],
    ),
    Action(
        id="nxos_show_lldp",
        name="Show LLDP Neighbors",
        category="NX-OS",
        kind="show",
        explanation=(
            "Lists directly connected LLDP neighbors on a Nexus switch."
        ),
        template="show lldp neighbors detail",
        use_textfsm=True,
        platforms=["cisco_nxos"],
    ),
    # ---- ASA specific --------------------------------------------------------
    Action(
        id="asa_nameif",
        name="Configure ASA Interface (nameif)",
        category="ASA",
        kind="config",
        explanation=(
            "Assigns a security zone name and security-level to an ASA interface, "
            "then sets the IP address. ASA uses named zones for ACL and NAT."
        ),
        template=(
            "interface {{ interface }}\n"
            "nameif {{ nameif }}\n"
            "security-level {{ sec_level }}\n"
            "ip address {{ ip_address }} {{ subnet_mask }}\n"
            "no shutdown"
        ),
        params=[
            Param("interface", "Interface", "text", placeholder="GigabitEthernet0/0"),
            Param("nameif", "Name / security zone", "text", placeholder="outside"),
            Param("sec_level", "Security level (0-100)", "int", default=0),
            Param("ip_address", "IP Address", "text", placeholder="192.168.1.1"),
            Param("subnet_mask", "Subnet Mask", "text", default="255.255.255.0"),
        ],
        save_after=True,
        platforms=["cisco_asa"],
    ),
    Action(
        id="asa_show_conn",
        name="Show ASA Connections",
        category="ASA",
        kind="show",
        explanation=(
            "Shows active connections flowing through the ASA, including NAT/xlate state."
        ),
        template="show conn detail",
        platforms=["cisco_asa"],
    ),
    Action(
        id="asa_show_xlate",
        name="Show ASA NAT Translations",
        category="ASA",
        kind="show",
        explanation=(
            "Shows active NAT (xlate) entries on the ASA — handy for debugging "
            "NAT policy issues."
        ),
        template="show xlate",
        platforms=["cisco_asa"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"],
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
        platforms=["cisco_ios", "cisco_xe", "cisco_nxos", "cisco_asa"],
    ),
]