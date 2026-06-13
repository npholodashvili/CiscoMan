"""Offline Cisco IOS simulator for visual testing without real hardware.

A demo device (``is_demo == 1``) is routed here instead of Netmiko. Each device
keeps an in-memory state (hostname, interfaces, VLANs) that ``show`` commands
read from and ``config`` commands mutate, so the demo behaves like a real switch:
change an access VLAN, then "Show Running Config" reflects it.

State lives for the lifetime of the Streamlit process. It is intentionally not
persisted - it's a sandbox.
"""

from __future__ import annotations

import random
import re
import threading
import time

_LONG_TYPES = (
    "GigabitEthernet", "FastEthernet", "TenGigabitEthernet", "TwentyFiveGigE",
    "FortyGigabitEthernet", "Port-channel", "Ethernet", "Vlan",
)
_ABBR = {
    "twe": "TwentyFiveGigE", "fo": "FortyGigabitEthernet", "te": "TenGigabitEthernet",
    "gi": "GigabitEthernet", "fa": "FastEthernet", "po": "Port-channel",
    "eth": "Ethernet", "vl": "Vlan",
}

_lock = threading.Lock()
_STATE: dict[str, dict] = {}

_MODEL = "WS-C2960X-24TS-L"
_IOS = "15.2(7)E3"


def _default_state(ip: str, name: str) -> dict:
    interfaces = {}
    for i in range(1, 9):
        port = f"GigabitEthernet1/0/{i}"
        connected = i % 3 != 0  # leave some "notconnect" for realism
        interfaces[port] = {
            "desc": "",
            "vlan": "1",
            "mode": "access",
            "voice_vlan": "",
            "shutdown": False,
            "status": "connected" if connected else "notconnect",
            "speed": "1000" if connected else "auto",
            "duplex": "a-full" if connected else "auto",
        }
    interfaces["GigabitEthernet1/0/24"] = {
        "desc": "Uplink to Core", "vlan": "trunk", "mode": "trunk", "voice_vlan": "",
        "shutdown": False, "status": "connected", "speed": "1000", "duplex": "a-full",
    }
    return {
        "hostname": name.replace(" ", "-"),
        "mgmt_ip": ip,
        "serial": "FCW" + "".join(random.choice("0123456789ABCDEF") for _ in range(8)),
        "uptime": f"{random.randint(1, 200)} days, {random.randint(0, 23)} hours",
        "interfaces": interfaces,
        "vlans": {1: "default", 10: "DATA", 100: "VOICE"},
    }


def _get(device: dict) -> dict:
    ip = device["ip"]
    with _lock:
        if ip not in _STATE:
            _STATE[ip] = _default_state(ip, device.get("name", ip))
        return _STATE[ip]


def reset(ip: str | None = None) -> None:
    with _lock:
        if ip is None:
            _STATE.clear()
        else:
            _STATE.pop(ip, None)


def prompt(device: dict) -> str:
    return _get(device)["hostname"] + "#"


# --- show command rendering ---------------------------------------------------


def _short(port: str) -> str:
    return port.replace("GigabitEthernet", "Gi").replace("FastEthernet", "Fa")


def _show_version(s: dict) -> str:
    return (
        f"Cisco IOS Software, C2960X Software, Version {_IOS}, RELEASE SOFTWARE (fc3)\n"
        f"{s['hostname']} uptime is {s['uptime']}\n"
        "System returned to ROM by power-on\n\n"
        "cisco " + _MODEL + " (APM86XXX) processor with 524288K bytes of memory.\n"
        f"Processor board ID {s['serial']}\n"
        "24 Gigabit Ethernet interfaces\n"
        "Base ethernet MAC Address       : 00:1A:2B:3C:4D:5E\n"
        f"Model number                    : {_MODEL}\n"
        f"System serial number            : {s['serial']}\n"
        "Configuration register is 0xF\n"
    )


def _show_interfaces_status(s: dict) -> str:
    lines = ["Port      Name               Status       Vlan       Duplex  Speed Type"]
    for port, d in s["interfaces"].items():
        name = (d["desc"][:18]) if d["desc"] else ""
        status = "disabled" if d["shutdown"] else d["status"]
        vlan = d["vlan"]
        lines.append(
            f"{_short(port):<9} {name:<18} {status:<12} {vlan:<10} "
            f"{d['duplex']:<7} {d['speed']:<5} 10/100/1000BaseTX"
        )
    return "\n".join(lines)


def _show_vlan_brief(s: dict) -> str:
    members: dict[str, list[str]] = {str(v): [] for v in s["vlans"]}
    for port, d in s["interfaces"].items():
        if d["mode"] == "access" and d["vlan"] in members:
            members[d["vlan"]].append(_short(port))
    lines = [
        "VLAN Name                             Status    Ports",
        "---- -------------------------------- --------- -------------------------------",
    ]
    for vid, vname in s["vlans"].items():
        ports = ", ".join(members.get(str(vid), []))
        lines.append(f"{vid:<4} {vname:<32} active    {ports}")
    return "\n".join(lines)


def _show_ip_int_brief(s: dict) -> str:
    lines = ["Interface              IP-Address      OK? Method Status                Protocol"]
    lines.append(f"Vlan1                  {s['mgmt_ip']:<15} YES NVRAM  up                    up")
    for port, d in s["interfaces"].items():
        st = "administratively down" if d["shutdown"] else (
            "up" if d["status"] == "connected" else "down")
        proto = "up" if (not d["shutdown"] and d["status"] == "connected") else "down"
        lines.append(f"{port:<22} unassigned      YES unset  {st:<21} {proto}")
    return "\n".join(lines)


def _show_mac(s: dict) -> str:
    lines = [
        "          Mac Address Table",
        "-------------------------------------------",
        "Vlan    Mac Address       Type        Ports",
        "----    -----------       --------    -----",
    ]
    rng = random.Random(s["serial"])
    for port, d in list(s["interfaces"].items())[:6]:
        if d["status"] == "connected" and not d["shutdown"]:
            mac = "00%02x.%04x.%04x" % (rng.randint(0, 255), rng.randint(0, 0xFFFF),
                                        rng.randint(0, 0xFFFF))
            lines.append(f"{d['vlan'] if d['vlan'] != 'trunk' else '1':<7} {mac}    DYNAMIC     {_short(port)}")
    return "\n".join(lines)


def _show_cdp(s: dict) -> str:
    return (
        "-------------------------\n"
        "Device ID: CORE-SW-01.lab\n"
        f"  IP address: {s['mgmt_ip'].rsplit('.', 1)[0]}.254\n"
        "Platform: cisco WS-C3850-48T,  Capabilities: Switch IGMP\n"
        "Interface: GigabitEthernet1/0/24,  Port ID (outgoing port): GigabitEthernet1/0/1\n"
        "Holdtime : 168 sec\n\n"
        "-------------------------\n"
        "Device ID: AP-LOBBY.lab\n"
        f"  IP address: {s['mgmt_ip'].rsplit('.', 1)[0]}.50\n"
        "Platform: cisco AIR-AP2802I,  Capabilities: Trans-Bridge\n"
        "Interface: GigabitEthernet1/0/5,  Port ID (outgoing port): GigabitEthernet0\n"
        "Holdtime : 142 sec\n"
    )


def _show_running_config(s: dict) -> str:
    out = [
        "Building configuration...", "",
        "Current configuration : 4096 bytes", "!",
        "version 15.2", "service timestamps debug datetime msec",
        "service timestamps log datetime msec", "!",
        f"hostname {s['hostname']}", "!",
    ]
    for vid, vname in s["vlans"].items():
        if vid == 1:
            continue
        out += [f"vlan {vid}", f" name {vname}", "!"]
    for port, d in s["interfaces"].items():
        out.append(f"interface {port}")
        if d["desc"]:
            out.append(f" description {d['desc']}")
        if d["mode"] == "trunk":
            out += [" switchport trunk encapsulation dot1q", " switchport mode trunk"]
        else:
            out.append(" switchport mode access")
            if d["vlan"] != "1":
                out.append(f" switchport access vlan {d['vlan']}")
            if d["voice_vlan"]:
                out.append(f" switchport voice vlan {d['voice_vlan']}")
        if d["shutdown"]:
            out.append(" shutdown")
        out.append("!")
    out += [
        "interface Vlan1", f" ip address {s['mgmt_ip']} 255.255.255.0", "!",
        "line con 0", "line vty 0 4", " login local", " transport input ssh", "!",
        "end", "",
    ]
    return "\n".join(out)


_SHOW_TABLE = {
    "show version": _show_version,
    "show interfaces status": _show_interfaces_status,
    "show interface status": _show_interfaces_status,
    "show vlan brief": _show_vlan_brief,
    "show vlan": _show_vlan_brief,
    "show ip interface brief": _show_ip_int_brief,
    "show mac address-table": _show_mac,
    "show mac-address-table": _show_mac,
    "show cdp neighbors detail": _show_cdp,
    "show cdp neighbors": _show_cdp,
    "show running-config": _show_running_config,
    "show run": _show_running_config,
}


def run_show(device: dict, command: str) -> str:
    time.sleep(random.uniform(0.2, 0.6))  # make progress bars visible
    s = _get(device)
    cmd = command.strip().lower()
    fn = _SHOW_TABLE.get(cmd)
    if fn:
        return fn(s)
    # Unknown show command: plausible-but-empty response.
    return f"{cmd}\n% (simulated) no output for this command"


# --- config command application ----------------------------------------------


def apply_config(device: dict, lines: list[str]) -> str:
    time.sleep(random.uniform(0.3, 0.8))
    s = _get(device)
    out_lines = [f"{s['hostname']}#configure terminal",
                 "Enter configuration commands, one per line.  End with CNTL/Z."]
    cur_ifaces: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("interface "):
            spec = line.split(None, 1)[1]
            if spec.lower().startswith("range "):
                cur_ifaces = _expand_range(s, spec[6:])
            else:
                ni = _normalize_iface(s, spec)
                cur_ifaces = [ni] if ni else []
            ctx = "config-if-range" if len(cur_ifaces) > 1 else "config-if"
            out_lines.append(f"{s['hostname']}({ctx})#" if cur_ifaces
                             else f"% Invalid interface {spec}")
        elif low.startswith("hostname "):
            s["hostname"] = line.split(None, 1)[1]
            cur_ifaces = []
        elif low.startswith("vlan "):
            try:
                vid = int(line.split()[1])
                s["vlans"].setdefault(vid, f"VLAN{vid}")
            except (ValueError, IndexError):
                pass
            cur_ifaces = []
        elif low.startswith("name ") and not cur_ifaces:
            # vlan name (best-effort: applies to last created vlan)
            if s["vlans"]:
                last = max(s["vlans"])
                s["vlans"][last] = line.split(None, 1)[1]
        elif cur_ifaces:
            for ifc in cur_ifaces:
                _apply_iface_cmd(s, ifc, low, line)
        out_lines.append("")
    out_lines.append(f"{s['hostname']}(config)#end")
    return "\n".join(out_lines)


def _normalize_iface(s: dict, name: str) -> str | None:
    """Expand abbreviations (Gi1/0/1 -> GigabitEthernet1/0/1) and create if valid."""
    name = name.strip()
    if not name.startswith(_LONG_TYPES):
        m = re.match(r"([A-Za-z\-]+)(.*)", name)
        if m:
            prefix, rest = m.group(1).lower(), m.group(2)
            for ab, full in _ABBR.items():
                if prefix == ab:
                    name = full + rest
                    break
    if name in s["interfaces"]:
        return name
    if name.startswith(_LONG_TYPES):
        s["interfaces"][name] = {
            "desc": "", "vlan": "1", "mode": "access", "voice_vlan": "",
            "shutdown": False, "status": "notconnect", "speed": "auto", "duplex": "auto",
        }
        return name
    return None


def _expand_range(s: dict, expr: str) -> list[str]:
    """Expand 'Gi1/0/1 - 8' and comma lists into individual interface names."""
    result: list[str] = []
    for token in expr.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            left, _, right = token.partition("-")
            left = _normalize_iface(s, left.strip())
            right = right.strip()
            if not left:
                continue
            prefix, _, last = left.rpartition("/")
            try:
                start = int(last)
                end = int(right.rpartition("/")[2]) if "/" in right else int(right)
            except ValueError:
                result.append(left)
                continue
            for n in range(start, end + 1):
                ni = _normalize_iface(s, f"{prefix}/{n}")
                if ni:
                    result.append(ni)
        else:
            ni = _normalize_iface(s, token)
            if ni:
                result.append(ni)
    return result


def _apply_iface_cmd(s: dict, iface: str, low: str, original: str) -> None:
    d = s["interfaces"][iface]
    if low.startswith("description "):
        d["desc"] = original.split(None, 1)[1]
    elif low == "switchport mode access":
        d["mode"] = "access"
    elif low == "switchport mode trunk":
        d["mode"] = "trunk"
        d["vlan"] = "trunk"
    elif low.startswith("switchport access vlan "):
        d["vlan"] = low.split()[-1]
        d["mode"] = "access"
    elif low.startswith("switchport voice vlan "):
        d["voice_vlan"] = low.split()[-1]
    elif low == "shutdown":
        d["shutdown"] = True
        d["status"] = "disabled"
    elif low == "no shutdown":
        d["shutdown"] = False
        d["status"] = "connected"


def save_config(device: dict) -> str:
    time.sleep(random.uniform(0.2, 0.5))
    return "Building configuration...\n[OK]"
