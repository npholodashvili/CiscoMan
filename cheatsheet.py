"""Searchable cheat sheet: network admin glossary + links to runnable Action Cards.

Used by the Coach page. Entries are keyword-indexed so users can search
\"VLAN\", \"PoE\", \"GRE tunnel\", etc. and get plain-English help plus
one-click jump to Control Center.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import actions


@dataclass
class GlossaryEntry:
    term: str
    definition: str
    keywords: list[str] = field(default_factory=list)
    action_ids: list[str] = field(default_factory=list)
    category: str = "Glossary"


GLOSSARY: list[GlossaryEntry] = [
    GlossaryEntry(
        "VLAN (Virtual LAN)",
        "A logical broadcast domain — like a virtual wire segment. Access ports join "
        "one VLAN; trunk ports carry many VLANs with 802.1Q tags.",
        keywords=["vlan", "segment", "802.1q", "access", "trunk"],
        action_ids=["set_access_vlan", "create_vlan", "set_trunk", "show_vlan"],
        category="Switching",
    ),
    GlossaryEntry(
        "Access port",
        "A port assigned to a single VLAN. Devices on that port only see traffic "
        "in that VLAN (untagged frames).",
        keywords=["access", "port", "untagged"],
        action_ids=["set_access_vlan", "show_port_status"],
        category="Switching",
    ),
    GlossaryEntry(
        "Trunk port",
        "Carries traffic for multiple VLANs between switches. Uses dot1q tags on "
        "each frame. Common on upl links.",
        keywords=["trunk", "uplink", "dot1q", "tagged"],
        action_ids=["set_trunk"],
        category="Switching",
    ),
    GlossaryEntry(
        "PoE (Power over Ethernet)",
        "Delivers DC power to phones, APs, and cameras over the Ethernet cable. "
        "Controlled per-port with `power inline auto` (enable) or `never` (disable).",
        keywords=["poe", "power", "inline", "phone", "ap", "watt"],
        action_ids=["show_power_inline", "poe_enable", "poe_disable"],
        category="Power",
    ),
    GlossaryEntry(
        "SVI (Switched Virtual Interface)",
        "A Layer-3 interface tied to a VLAN (interface Vlan10). Gives the switch "
        "an IP address on that VLAN — used as default gateway for clients.",
        keywords=["svi", "vlan interface", "gateway", "layer3", "l3"],
        action_ids=["set_svi_ip", "show_ip_int_brief"],
        category="Routing",
    ),
    GlossaryEntry(
        "Static route",
        "Tells the switch how to reach a remote network: `ip route <net> <mask> "
        "<next-hop>`. The next-hop is usually another router's IP.",
        keywords=["route", "static", "routing", "next-hop", "gateway"],
        action_ids=["static_route", "show_ip_route"],
        category="Routing",
    ),
    GlossaryEntry(
        "GRE tunnel",
        "Encapsulates packets inside another protocol so sites connect over an "
        "untrusted network. Defined with `interface TunnelX`, tunnel source, "
        "and tunnel destination. Often paired with IPsec for encryption.",
        keywords=["gre", "tunnel", "vpn", "site-to-site", "overlay"],
        action_ids=["gre_tunnel", "ipsec_site_to_site", "show_ip_int_brief", "show_crypto"],
        category="Routing",
    ),
    GlossaryEntry(
        "IPsec VPN",
        "Encrypts traffic between sites using ISAKMP (key exchange) and IPsec "
        "transform sets. Applied via crypto map on a physical interface.",
        keywords=["ipsec", "isakmp", "crypto", "vpn", "site-to-site", "psk"],
        action_ids=["ipsec_site_to_site", "show_crypto", "gre_tunnel"],
        category="Routing",
    ),
    GlossaryEntry(
        "Spanning Tree / Portfast",
        "STP prevents loops in L2 networks. Portfast on access ports skips "
        "listening/learning so PCs/phones connect faster.",
        keywords=["stp", "spanning-tree", "portfast", "loop", "bpdu"],
        action_ids=["set_portfast", "set_bpduguard", "show_stp"],
        category="Layer 2",
    ),
    GlossaryEntry(
        "DHCP Snooping",
        "Blocks rogue DHCP servers by binding MAC to IP on trusted ports only.",
        keywords=["dhcp", "snooping", "trust", "rogue", "server"],
        action_ids=["enable_dhcp_snooping", "set_dhcp_snoop_trust", "show_dhcp_snoop"],
        category="Layer 2",
    ),
    GlossaryEntry(
        "802.1X",
        "Port-based network access control — clients authenticate (usually via "
        "RADIUS) before the switch forwards traffic.",
        keywords=["802.1x", "dot1x", "radius", "nacs", "authentication"],
        action_ids=["dot1x_port"],
        category="Security",
    ),
    GlossaryEntry(
        "QoS / DSCP trust",
        "Quality of Service — prioritizes voice/video traffic. Trust DSCP "
        "honors markings on incoming frames.",
        keywords=["qos", "dscp", "cos", "voice", "priority"],
        action_ids=["set_trust_dscp"],
        category="Layer 2",
    ),
    GlossaryEntry(
        "CDP (Cisco Discovery Protocol)",
        "Cisco-proprietary neighbor discovery. Shows directly connected devices, "
        "ports, and platform — useful for mapping without LLDP.",
        keywords=["cdp", "neighbor", "topology", "discovery"],
        action_ids=["show_cdp"],
        category="Diagnostics",
    ),
    GlossaryEntry(
        "MAC address table",
        "Maps learned MAC addresses to physical ports and VLANs. Use it to find "
        "which port a device is plugged into.",
        keywords=["mac", "address", "table", "cam", "fingerprint"],
        action_ids=["show_mac"],
        category="Diagnostics",
    ),
    GlossaryEntry(
        "Running-config vs Startup-config",
        "Running-config is what's active in RAM now. Startup-config is saved "
        "to flash and loaded on reboot. Use `write memory` to persist changes.",
        keywords=["running", "startup", "write memory", "save", "startup"],
        action_ids=["show_run", "save_config"],
        category="Operations",
    ),
    GlossaryEntry(
        "Enable secret",
        "Password required to enter privileged EXEC mode (`enable`). Without it "
        "you can only run show commands, not config.",
        keywords=["enable", "secret", "privileged", "exec"],
        action_ids=[],
        category="Security",
    ),
    GlossaryEntry(
        "Extended ACL",
        "Access Control List — permit/deny rules for traffic. Extended ACLs match "
        "source/dest IP and ports. Applied to interfaces or used in route-maps.",
        keywords=["acl", "access-list", "firewall", "permit", "deny"],
        action_ids=["extended_acl"],
        category="Security",
    ),
    GlossaryEntry(
        "Voice VLAN",
        "Separate VLAN for IP phones. The phone tags voice traffic; PCs on the "
        "same cable stay on the data VLAN (often via CDP/LLDP-MED).",
        keywords=["voice", "phone", "qos", "medi"],
        action_ids=["set_voice_vlan"],
        category="Switching",
    ),
    GlossaryEntry(
        "Shutdown (interface)",
        "Administratively disables a port. Traffic stops immediately even if "
        "a cable is connected. Re-enable with `no shutdown`.",
        keywords=["shutdown", "disable", "port", "admin down"],
        action_ids=["port_updown"],
        category="Switching",
    ),
]


def _norm(s: str) -> str:
    return s.lower().strip()


def search(query: str = "") -> dict:
    """Return {glossary: [...], actions: [...]} matching query (empty = all glossary)."""
    q = _norm(query)
    glossary_hits = []
    for entry in GLOSSARY:
        if not q:
            glossary_hits.append(entry)
            continue
        hay = " ".join([entry.term, entry.definition] + entry.keywords).lower()
        if q in hay or any(q in _norm(k) for k in entry.keywords):
            glossary_hits.append(entry)

    action_ids: set[str] = set()
    for e in glossary_hits:
        action_ids.update(e.action_ids)
    if q:
        for a in actions.ACTIONS:
            hay = " ".join([a.name, a.category, a.explanation]).lower()
            if q in hay:
                action_ids.add(a.id)

    action_hits = [actions.get_action(aid) for aid in action_ids if aid in actions.ACTIONS_BY_ID]
    return {"glossary": glossary_hits, "actions": action_hits}


def categories() -> list[str]:
    return list(dict.fromkeys(e.category for e in GLOSSARY))
