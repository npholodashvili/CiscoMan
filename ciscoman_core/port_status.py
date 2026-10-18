"""Read a switch's port list (link state, VLAN, description) for the port panel.

Works per platform family. Cisco uses TextFSM when available; everything else
(and Cisco without TextFSM) goes through a header-aligned table parser, plus a
block parser for Sophos' verbose "show interfaces" output.
"""

from __future__ import annotations

import re
from typing import Optional

try:
    from ciscoman_core import network_utils as net
    from ciscoman_core import actions
except ImportError:  # pragma: no cover
    import network_utils as net  # type: ignore
    import actions  # type: ignore

# family -> (commands, use_textfsm)
PORT_COMMANDS: dict[str, tuple[list[str], bool]] = {
    "ios": (["show interfaces status"], True),
    "nxos": (["show interface status"], True),
    "asa": (["show interface ip brief"], False),
    "xr": (["show ip interface brief"], False),
    "comware": (["display interface brief"], False),
    "procurve": (["show interfaces brief", "show name"], False),
    "aoscx": (["show interface brief"], False),
    "sophos": (["show interfaces"], False),
    "grandstream": (["show interface brief"], False),
}

UP, DOWN, DISABLED, UNKNOWN = "up", "down", "disabled", "unknown"

_PORT_HEADERS = ("port", "interface")
_STATUS_HEADERS = ("status", "link")
_VLAN_HEADERS = ("vlan", "pvid", "native")
_NAME_HEADERS = ("name", "description")
_ENABLED_HEADERS = ("enabled",)
_SPEED_HEADERS = ("speed",)


def normalize_status(value: str, enabled: str = "") -> str:
    v = (value or "").strip().lower()
    e = (enabled or "").strip().lower()
    if e in ("no", "false", "disabled"):
        return DISABLED
    if v.startswith(("disabled", "err-dis", "adm", "administratively", "shutdown")):
        return DISABLED
    if v.startswith(("connected", "up")):
        return UP
    if v.startswith(("notconnect", "down", "notpresent", "sfpabsent", "inactive", "monitoring")):
        return DOWN
    return UNKNOWN


def _looks_like_port(token: str) -> bool:
    return bool(re.search(r"\d", token)) and not set(token) <= set("-+=|")


def _clean(v: str) -> str:
    v = (v or "").strip().strip("|").strip()
    return "" if v in ("--", "-", "n/a") else v


def _columns(header: str) -> list[tuple[str, int]]:
    return [(m.group(0).lower(), m.start()) for m in re.finditer(r"[^\s|]+", header)]


def _slice(row: str, starts: list[int], i: int) -> str:
    start = starts[i]
    # If a value spills left past its header, back up to the start of the word.
    while 0 < start < len(row) and row[start - 1] != " " and row[start] != " ":
        start -= 1
    end = starts[i + 1] if i + 1 < len(starts) else len(row)
    while end < len(row) and 0 < end and row[end - 1] != " " and row[end] != " ":
        end += 1
    return row[start:end] if start < len(row) else ""


def parse_table(text: str) -> list[dict]:
    """Parse any 'Port ... Status ...' style table aligned under a header."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        cols = _columns(line)
        names = [c for c, _ in cols]
        if not names or names[0] not in _PORT_HEADERS:
            continue
        if not any(n in _STATUS_HEADERS for n in names):
            continue
        starts = [s for _, s in cols]
        ports = []
        for row in lines[idx + 1:]:
            if not row.strip():
                if ports:
                    break
                continue
            first = row.split()[0]
            if not _looks_like_port(first):
                continue
            fields = {names[i]: _clean(_slice(row, starts, i)) for i in range(len(names))}
            port = first
            pick = lambda keys: next((fields[k] for k in names if k in keys and fields.get(k)), "")
            ports.append({
                "port": port,
                "status": normalize_status(pick(_STATUS_HEADERS), pick(_ENABLED_HEADERS)),
                "vlan": pick(_VLAN_HEADERS),
                "name": pick(_NAME_HEADERS),
                "speed": pick(_SPEED_HEADERS),
            })
        if ports:
            return ports
    return []


def parse_names(text: str) -> dict[str, str]:
    """HP/Aruba 'show name' style: Port | Type | Name  ->  {port: name}."""
    out: dict[str, str] = {}
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        cols = _columns(line)
        names = [c for c, _ in cols]
        if names and names[0] == "port" and "name" in names:
            starts = [s for _, s in cols]
            ni = names.index("name")
            for row in lines[idx + 1:]:
                if not row.strip() or not _looks_like_port(row.split()[0]):
                    continue
                name = _clean(_slice(row, starts, ni))
                if name:
                    out[row.split()[0]] = name
            break
    return out


_BLOCK_RE = re.compile(
    r"^(?P<port>[A-Za-z][\w\-]*\s?\d+(?:/\d+)+)\s+(?P<admin>up|down|administratively down)"
    r"(?:,\s*line protocol is\s+(?P<proto>\w+))?", re.I,
)


def parse_blocks(text: str) -> list[dict]:
    """Verbose per-interface output ('Gi0/1 up, line protocol is up ...')."""
    ports: list[dict] = []
    current: Optional[dict] = None
    for line in text.splitlines():
        m = _BLOCK_RE.match(line.strip())
        if m:
            admin = m.group("admin").lower()
            proto = (m.group("proto") or admin).lower()
            status = DISABLED if admin.startswith("admin") else (UP if proto == "up" else DOWN)
            current = {"port": m.group("port").replace(" ", ""), "status": status,
                       "vlan": "", "name": "", "speed": ""}
            ports.append(current)
            continue
        if current is not None:
            d = re.search(r"description\s*[:=]?\s*(.+)$", line, re.I)
            if d and not current["name"]:
                current["name"] = _clean(d.group(1).strip().strip('"'))
            p = re.search(r"\bpvid\s*[:=]?\s*(\d+)", line, re.I)
            if p and not current["vlan"]:
                current["vlan"] = p.group(1)
    return ports


def parse_textfsm_rows(rows: list) -> list[dict]:
    ports = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        row = {str(k).lower(): v for k, v in raw.items()}
        port = row.get("port") or row.get("interface") or ""
        if not port:
            continue
        vlan = row.get("vlan_id") or row.get("vlan") or ""
        ports.append({
            "port": str(port),
            "status": normalize_status(str(row.get("status", ""))),
            "vlan": str(vlan),
            "name": str(row.get("name") or row.get("description") or ""),
            "speed": str(row.get("speed", "")),
        })
    return ports


def parse_output(family: str, output: str, parsed: Optional[list] = None) -> list[dict]:
    ports = parse_textfsm_rows(parsed) if parsed else []
    if ports:
        return ports
    sections = re.split(r"(?m)^# (.+)$", output or "")
    # sections = [pre, cmd1, out1, cmd2, out2, ...]
    texts = {sections[i].strip(): sections[i + 1] for i in range(1, len(sections) - 1, 2)}
    if not texts:
        texts = {"": output or ""}
    names: dict[str, str] = {}
    for cmd, text in texts.items():
        if cmd.startswith("show name"):
            names = parse_names(text)
            continue
        found = parse_table(text) or parse_blocks(text)
        if found:
            ports = found
    if names:
        for p in ports:
            p["name"] = p["name"] or names.get(p["port"], "")
    return ports


def fetch_ports(device: dict) -> "net.ExecResult":
    """Run the platform's port-status command(s); result.parsed = port dicts."""
    fam = actions.platform_family(device.get("device_type") or "cisco_ios")
    cmds, use_tfsm = PORT_COMMANDS.get(fam, (["show interfaces status"], False))
    res = net.run_show_commands(device, cmds, use_textfsm=use_tfsm)
    if res.success:
        res.parsed = parse_output(fam, res.output, res.parsed)
    return res


# --- helpers for the UI --------------------------------------------------------

_TYPE_ABBR = [
    ("hundredgigabitethernet", "Hu"), ("fortygigabitethernet", "Fo"),
    ("twentyfivegige", "Twe"), ("tengigabitethernet", "Te"),
    ("twogigabitethernet", "Tw"), ("fivegigabitethernet", "Fi"),
    ("gigabitethernet", "Gi"), ("fastethernet", "Fa"), ("ethernet", "Eth"),
]


def short_name(port: str) -> str:
    low = port.lower()
    for full, abbr in _TYPE_ABBR:
        if low.startswith(full):
            return abbr + port[len(full):].strip()
    return port


def split_port(port: str) -> tuple[str, int]:
    """'Gi1/0/12' -> ('Gi1/0/', 12); '5' -> ('', 5)."""
    s = short_name(port)
    m = re.match(r"^(.*?)(\d+)$", s)
    if not m:
        return s, 0
    return m.group(1), int(m.group(2))


def interface_expression(ports: list[str], family: str) -> str:
    """Value for an action's interface field from selected ports."""
    if not ports:
        return ""
    if len(ports) == 1:
        return ports[0]
    if family in ("ios", "nxos"):
        return "range " + ", ".join(ports)
    if family == "procurve":
        return ",".join(ports)
    return ports[0]
