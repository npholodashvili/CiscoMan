"""CiscoMan - GUI for managing Cisco IOS devices without the CLI.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import difflib
import time
from datetime import datetime

import pandas as pd
import streamlit as st

import actions
from actions import ACTIONS, ACTIONS_BY_ID, get_action, action_visible, filter_actions, CATEGORIES
import cheatsheet
import config
import database as db
import network_utils as net
import port_panel
import tunnel_wizard
import wizard

st.set_page_config(page_title="CiscoMan", page_icon="🛰️", layout="wide")

db.init_db()


# --- Session helpers ----------------------------------------------------------


def _ts(epoch: float | None) -> str:
    if epoch is None:
        return "-"
    try:
        return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return "-"


def logout() -> None:
    for k in ("key", "login_time", "last_active"):
        st.session_state.pop(k, None)


def is_logged_in() -> bool:
    if "key" not in st.session_state:
        return False
    now = time.time()
    if now - st.session_state.get("last_active", now) > config.SESSION_TIMEOUT_MIN * 60:
        logout()
        return False
    st.session_state["last_active"] = now
    return True


def get_key() -> bytes:
    return st.session_state["key"]


# --- Auth screens -------------------------------------------------------------


def screen_setup() -> None:
    st.title("🛰️ CiscoMan - First-time setup")
    st.info(
        "Create a **master password**. It encrypts all stored device credentials. "
        "The encryption key is derived from this password and is never saved to disk — "
        "so if you lose it, stored credentials are unrecoverable. Choose wisely."
    )
    with st.form("setup"):
        p1 = st.text_input("Master password", type="password")
        p2 = st.text_input("Confirm master password", type="password")
        submitted = st.form_submit_button("Create master password", type="primary")
    if submitted:
        if len(p1) < 8:
            st.error("Use at least 8 characters.")
        elif p1 != p2:
            st.error("Passwords do not match.")
        else:
            key = db.set_master_password(p1)
            st.session_state["key"] = key
            st.session_state["login_time"] = time.time()
            st.session_state["last_active"] = time.time()
            st.rerun()


def screen_login() -> None:
    st.title("🛰️ CiscoMan - Login")
    with st.form("login"):
        pwd = st.text_input("Master password", type="password")
        submitted = st.form_submit_button("Unlock", type="primary")
    if submitted:
        key = db.verify_master_password(pwd)
        if key is None:
            st.error("Incorrect master password.")
        else:
            st.session_state["key"] = key
            st.session_state["login_time"] = time.time()
            st.session_state["last_active"] = time.time()
            st.rerun()


# --- Pages --------------------------------------------------------------------


def page_scanner() -> None:
    st.header("🔎 Network Scanner")
    st.caption(
        "Privilege-free TCP scan of the SSH port. Open ports usually mean a manageable device."
    )
    col1, col2, col3 = st.columns([2, 1, 1])
    target = col1.text_input("IP range", value="192.168.1.0/24",
                             help="CIDR (192.168.1.0/24), single IP, or 192.168.1.1-50")
    port = col2.number_input("Port", value=config.DEFAULT_SSH_PORT, min_value=1, max_value=65535)
    timeout = col3.number_input("Timeout (s)", value=float(config.SCAN_TIMEOUT),
                                min_value=0.1, max_value=10.0, step=0.1)

    if st.button("Start scan", type="primary"):
        prog = st.progress(0.0)
        status = st.empty()

        def cb(done: int, total: int, ip: str) -> None:
            prog.progress(done / total)
            status.write(f"Scanned {done}/{total} ... last: {ip}")

        try:
            alive = net.scan_network(target, port=int(port), timeout=float(timeout),
                                     progress_callback=cb)
            st.session_state["scan_results"] = alive
            status.success(f"Done. {len(alive)} host(s) with port {port} open.")
        except ValueError as exc:
            st.error(f"Invalid range: {exc}")

    alive = st.session_state.get("scan_results", [])
    if not alive:
        return

    st.subheader("Discovered hosts")
    known_ips = {d["ip"] for d in db.list_devices()}
    existing_locations = db.list_locations()
    bulk_location = st.text_input(
        "Default location for hosts added below", value="",
        placeholder="e.g. HQ Tbilisi",
        help="Applied to every host you add here; you can override per host.")
    if existing_locations:
        st.caption("Existing locations: " + ", ".join(existing_locations))
    with st.form("add_discovered"):
        st.caption("Fill in details and tick the hosts you want to save to inventory.")
        rows = []
        for ip in alive:
            already = ip in known_ips
            with st.expander(f"{ip}" + ("  (already in inventory)" if already else ""),
                             expanded=not already):
                c1, c2, c3 = st.columns(3)
                pick = c1.checkbox("Add", key=f"pick_{ip}", value=False, disabled=already)
                name = c1.text_input("Device name", key=f"name_{ip}", value=ip)
                location = c1.text_input("Location", key=f"loc_{ip}",
                                         value=bulk_location, placeholder="e.g. HQ Tbilisi")
                dtype = c2.selectbox("Device type", config.SUPPORTED_DEVICE_TYPES,
                                     key=f"type_{ip}")
                group = c2.text_input("Group", key=f"group_{ip}",
                                      value="", placeholder="e.g. Floor-2")
                user = c3.text_input("SSH username", key=f"user_{ip}")
                pw = c3.text_input("SSH password", key=f"pw_{ip}", type="password")
                sec = c3.text_input("Enable secret (optional)", key=f"sec_{ip}",
                                    type="password")
                rows.append((ip, pick, name, location, dtype, group, user, pw, sec))
        if st.form_submit_button("Save selected to inventory", type="primary"):
            added = 0
            for ip, pick, name, location, dtype, group, user, pw, sec in rows:
                if pick and user and pw:
                    db.add_device(get_key(), name=name, ip=ip, username=user,
                                  password=pw, secret=sec, device_type=dtype,
                                  port=int(port), location=location or bulk_location,
                                  group_name=group)
                    added += 1
            st.success(f"Added {added} device(s).") if added else st.warning(
                "Nothing added (need username + password on ticked hosts)."
            )
            if added:
                st.rerun()


def page_inventory() -> None:
    st.header("🗂️ Device Inventory")
    devices = db.list_devices()

    has_demo = any(d.get("is_demo") for d in devices)
    cdemo1, cdemo2 = st.columns([3, 1])
    cdemo1.caption(
        "No real switches handy? Add **offline demo devices** that respond to real "
        "commands via a built-in simulator — full UI works with zero hardware."
    )
    if cdemo2.button("🧪 Add demo devices", disabled=has_demo,
                     help="Already added" if has_demo else f"Add {len(db.DEMO_DEVICES)} simulated devices (IOS, NX-OS, ASA)"):
        added = db.seed_demo_devices(get_key())
        st.success(f"Added {added} demo device(s).")
        st.rerun()

    with st.expander("➕ Add a device manually"):
        with st.form("add_manual"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Device name")
            ip = c1.text_input("IP address")
            location = c1.text_input("Location", placeholder="HQ Tbilisi")
            group = c1.text_input("Group", placeholder="Floor-2")
            dtype = c2.selectbox("Device type", config.SUPPORTED_DEVICE_TYPES)
            port = c2.number_input("SSH port", value=config.DEFAULT_SSH_PORT,
                                   min_value=1, max_value=65535)
            user = c3.text_input("SSH username")
            pw = c3.text_input("SSH password", type="password")
            sec = c3.text_input("Enable secret (optional)", type="password")
            if st.form_submit_button("Add device", type="primary"):
                if not (name and ip and user and pw):
                    st.error("Name, IP, username and password are required.")
                else:
                    try:
                        db.add_device(get_key(), name=name, ip=ip, username=user,
                                      password=pw, secret=sec, device_type=dtype,
                                      port=int(port), location=location, group_name=group)
                        st.success(f"Added {name}.")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not add device: {exc}")

    if not devices:
        st.info("No devices yet. Use the Scanner or add one manually above.")
        return

    df = pd.DataFrame(devices)
    df["last_seen"] = df["last_seen"].apply(_ts)
    df["created_at"] = df["created_at"].apply(_ts)
    df["mode"] = df["is_demo"].apply(lambda x: "🧪 DEMO" if x else "🔌 live")
    st.dataframe(
        df[["id", "mode", "name", "ip", "device_type", "port", "location",
            "group_name", "username", "last_seen"]],
        use_container_width=True, hide_index=True,
    )

    st.subheader("Manage")
    loc_filter = st.selectbox("Filter by location", ["(all)"] + db.list_locations(),
                              key="inv_loc_filter")
    visible = [d for d in devices if loc_filter == "(all)" or d["location"] == loc_filter]
    labels = {
        f'{d["name"]} ({d["ip"]}) — {d["location"] or "no location"}': d for d in visible
    }
    if not labels:
        st.info("No devices in this location.")
        return
    selected = st.selectbox("Select a device", list(labels.keys()))
    dev = labels[selected]

    c1, c2, c3 = st.columns(3)
    if c1.button("🔌 Test connection"):
        with st.spinner(f"Connecting to {dev['ip']} ..."):
            full = db.get_device_with_credentials(get_key(), dev["id"])
            res = net.test_connection(full)
        if res.success:
            db.mark_seen(dev["id"])
            st.success(res.output)
        else:
            st.error(res.error)
        db.log_action(dev["id"], dev["name"], dev["ip"], "test_connection", "",
                      "success" if res.success else "failed",
                      res.output, res.error)

    if c2.button("🗑️ Delete device", type="secondary"):
        db.delete_device(dev["id"])
        st.warning(f"Deleted {dev['name']}.")
        st.rerun()

    with c3.popover("✏️ Edit"):
        with st.form("edit_dev"):
            e_name = st.text_input("Name", value=dev["name"])
            e_location = st.text_input("Location", value=dev["location"])
            e_group = st.text_input("Group", value=dev["group_name"])
            e_type = st.selectbox(
                "Device type", config.SUPPORTED_DEVICE_TYPES,
                index=config.SUPPORTED_DEVICE_TYPES.index(dev["device_type"])
                if dev["device_type"] in config.SUPPORTED_DEVICE_TYPES else 0,
            )
            e_user = st.text_input("Username", value=dev["username"])
            e_pw = st.text_input("New password (blank = keep)", type="password")
            e_sec = st.text_input("New enable secret (blank = keep)", type="password")
            if st.form_submit_button("Save changes", type="primary"):
                db.update_device(get_key(), dev["id"], name=e_name, location=e_location,
                                 group_name=e_group, device_type=e_type, username=e_user,
                                 password=e_pw or None,
                                 secret=e_sec if e_sec else None)
                st.success("Updated.")
                st.rerun()


def _param_input(param: actions.Param, key_prefix: str):
    wkey = f"{key_prefix}_{param.key}"
    if param.kind == "int":
        return st.number_input(param.label, value=int(param.default or 0), key=wkey,
                               help=param.help, step=1)
    if param.kind == "bool":
        return st.checkbox(param.label, value=bool(param.default), key=wkey,
                           help=param.help)
    if param.kind == "textarea":
        return st.text_area(param.label, value=str(param.default), key=wkey,
                            help=param.help, placeholder=param.placeholder)
    if param.kind == "select":
        return st.selectbox(param.label, param.options, key=wkey, help=param.help)
    return st.text_input(param.label, value=str(param.default), key=wkey,
                         help=param.help, placeholder=param.placeholder)


def page_control_center() -> None:
    st.header("🎛️ Command Control Center")
    devices = db.list_devices()
    if not devices:
        st.info("Add devices first (Scanner or Inventory).")
        return

    # --- Target selection -----------------------------------------------------
    st.subheader("1. Choose targets")
    picked_ids = _render_target_picker(devices, "cc")
    st.caption(f"{len(picked_ids)} device(s) selected.")
    target_types = _device_types_for_targets(devices, picked_ids)
    if target_types:
        families = sorted({actions.platform_family(dt) for dt in target_types})
        st.caption(
            f"Showing tasks compatible with selected platforms: {', '.join(families)}."
        )

    # --- Action selection via tabs -------------------------------------------
    st.subheader("2. Choose an action")
    st.caption("Pick a category tab, then a task. Settings and a live CLI preview appear below.")
    goto = st.session_state.pop("goto_action", None)
    goto_act = actions.ACTIONS_BY_ID.get(goto) if goto else None
    if goto_act:
        st.success(
            f"📌 **{goto_act.name}** — open the **{goto_act.category}** tab below."
        )

    # --- Action selection via tabs -------------------------------------------
    tabs = st.tabs([f"{_CAT_ICON.get(c, '•')} {c}" for c in actions.CATEGORIES])
    for tab, cat in zip(tabs, actions.CATEGORIES):
        with tab:
            cat_actions = actions.filter_actions(
                [a for a in actions.ACTIONS if a.category == cat],
                target_types,
            )
            if not cat_actions:
                st.info("No tasks in this category for the selected device types.")
                continue
            radio_key = f"act_radio_{cat}"
            if goto:
                match = next((a for a in cat_actions if a.id == goto), None)
                if match and radio_key not in st.session_state:
                    st.session_state[radio_key] = match
            action = st.radio(
                "Task", cat_actions, format_func=lambda a: a.name,
                key=radio_key, label_visibility="collapsed",
            )
            st.divider()
            _render_action_ui(action, picked_ids, devices)


_CAT_ICON = {
    "Diagnostics": "🔍",
    "Port Config": "🔌",
    "PoE": "⚡",
    "Switch Config": "🛠️",
    "Routing & Tunnels": "🛤️",
    "Layer 2": "🔗",
    "Security": "🔒",
    "NX-OS": "🔷",
    "ASA": "🛡️",
    "Custom": "⌨️",
}


def _device_types_for_targets(devices: list[dict], picked_ids: list[int]) -> set[str]:
    if not picked_ids:
        return set()
    return {d["device_type"] for d in devices if d["id"] in picked_ids}


def _render_target_picker(devices: list[dict], key_prefix: str = "tgt") -> list[int]:
    """Location/group filters + checkboxes; returns selected device ids."""
    colf1, colf2, colf3 = st.columns([2, 2, 2])
    loc_filter = colf1.selectbox(
        "Location", ["(all)"] + db.list_locations(), key=f"{key_prefix}_loc",
    )
    groups = db.list_groups(location=None if loc_filter == "(all)" else loc_filter)
    group_filter = colf2.selectbox("Group", ["(all)"] + groups, key=f"{key_prefix}_grp")
    pool = [
        d for d in devices
        if (loc_filter == "(all)" or d["location"] == loc_filter)
        and (group_filter == "(all)" or d["group_name"] == group_filter)
    ]
    select_all = colf3.checkbox(f"Select all shown ({len(pool)})", key=f"{key_prefix}_dev_all")
    picked_ids: list[int] = []
    if pool:
        by_location: dict[str, list[dict]] = {}
        for d in pool:
            by_location.setdefault(d["location"] or "No location", []).append(d)
        for loc, members in by_location.items():
            st.markdown(f"**📍 {loc}**")
            grid = st.columns(3)
            for i, d in enumerate(members):
                with grid[i % 3]:
                    tag = " 🧪" if d.get("is_demo") else ""
                    grp = f' · {d["group_name"]}' if d["group_name"] else ""
                    fam = actions.platform_family(d.get("device_type", "cisco_ios"))
                    if st.checkbox(
                        f'{d["name"]}{tag}  ·  {d["ip"]}{grp}  ·  {fam}',
                        key=f"{key_prefix}_{d['id']}", value=select_all,
                    ):
                        picked_ids.append(d["id"])
    return picked_ids


def _build_cli_lines(action: actions.Action, values: dict) -> list[str]:
    if action.id in ("custom_show", "custom_config"):
        return [ln.strip() for ln in str(values.get("commands", "")).splitlines()
                if ln.strip()]
    if action.id == "save_config":
        return []
    return action.render(values)


def _preview_text(action: actions.Action, cli_lines: list[str], save_after: bool) -> str:
    if action.id == "save_config":
        return "write memory"
    if action.kind == "config":
        txt = "configure terminal\n" + "\n".join(cli_lines)
        return txt + ("\nend\nwrite memory" if save_after else "\nend")
    return "\n".join(cli_lines)


def _render_action_ui(action: actions.Action, picked_ids: list, devices: list) -> None:
    st.info(f"**What this does:** {action.explanation}")
    if action.danger:
        st.warning("⚠️ This changes device behavior. Double-check your targets.")

    values = {}
    incomplete = False
    if action.params:
        for p in action.params:
            if p.kind == "interface":
                val = _interface_picker(p, action, picked_ids, devices)
                values[p.key] = val
                if not val:
                    incomplete = True
            elif p.kind == "vlan":
                val = _vlan_picker(p, action, picked_ids, devices)
                values[p.key] = val
                if not val:
                    incomplete = True
            else:
                values[p.key] = _param_input(p, action.id)

    if incomplete:
        cli_lines = None
        st.caption("➡️ Choose at least one port above to generate the commands.")
    else:
        try:
            cli_lines = _build_cli_lines(action, values)
        except Exception:  # noqa: BLE001 - missing params
            cli_lines = None
            st.caption("➡️ Fill in the settings above to generate the commands.")

    save_after = False
    if action.kind == "config" and action.save_after and action.id != "save_config":
        save_after = st.checkbox("Also save to startup-config (write memory)",
                                 value=False, key=f"save_{action.id}")

    # CLI preview
    show_preview = st.toggle("👁️ Show CLI Preview", value=True, key=f"prev_{action.id}",
                             help="See the exact Cisco IOS commands before sending.")
    if show_preview and cli_lines is not None and (cli_lines or action.id == "save_config"):
        st.code(_preview_text(action, cli_lines, save_after), language="bash")

    # Execute
    n = len(picked_ids)
    if not picked_ids:
        st.warning("⬆️ Select at least one target device in step 1.")
    can_run = bool(picked_ids) and cli_lines is not None and (
        cli_lines or action.id == "save_config")
    if action.kind == "config" and picked_ids:
        confirm = st.checkbox(f"I understand this will be sent to **{n}** device(s).",
                              key=f"confirm_{action.id}")
        can_run = can_run and confirm
    label = (f"🔍 Run on {n} device(s)" if action.kind == "show"
             else f"🚀 Push to {n} device(s)")
    if st.button(label, type="primary", disabled=not can_run, key=f"run_{action.id}"):
        _execute(action, cli_lines, save_after, picked_ids)


def _parse_port_line(parts: list[str]) -> dict | None:
    """Try to extract a port dict from a split interface status line.
    
    Handles both Cisco style (no space: GigabitEthernet1/0/1) and
    FSOS style (space: GigabitEthernet 1/0/1, AggregatePort 1).
    Returns None if the line is not a valid port entry.
    """
    if not parts:
        return None
    first = parts[0]
    has_digits = any(c.isdigit() for c in first)

    # FSOS style: first token is a known prefix with no digits, second token is the port number
    if not has_digits and len(parts) >= 3:
        # Guard: second token must contain digits or a '/' to be a valid port number
        second = parts[1]
        if not any(c.isdigit() or c == "/" for c in second):
            return None
        port = f"{first} {second}"
        # Status is at index 2, vlan at index 3 (may be empty/missing)
        status = parts[2] if len(parts) > 2 else ""
        vlan = parts[3] if len(parts) > 3 else ""
        # FSOS output has no separate description column
        return {"port": port, "status": status, "vlan": vlan, "name": ""}

    # Cisco style or numeric-only: check first token
    if has_digits and ("/" in first or first.isdigit()
        or first.startswith("Gigabit") or first.startswith("FastEthernet")
        or first.startswith("TenGigabit") or first.startswith("FortyGigabit")
        or first.startswith("TwentyFiveGigE") or first.startswith("Port-channel")
        or first.startswith("Vlan") or first.startswith("Management")
        or first.startswith("Gi") or first.startswith("Fa")
        or first.startswith("Te") or first.startswith("Twe")
        or first.startswith("Fo") or first.startswith("Po")
        or first.startswith("Eth") or first.startswith("Lo")
        or first.startswith("Mgmt")):
        return {
            "port": first,
            "status": parts[2] if len(parts) > 2 else "",
            "vlan": parts[3] if len(parts) > 3 else "",
            "name": parts[1] if len(parts) > 1 else "",
        }
    return None


def _fetch_ports(device: dict) -> tuple[bool, list[dict], str]:
    cmd, use_tfsm = net.interface_status_command(device)
    res = net.run_show_commands(device, [cmd], use_textfsm=use_tfsm)
    ports = []
    for raw in (res.parsed or []):
        row = {str(k).lower(): v for k, v in raw.items()}
        port = row.get("port") or row.get("interface") or row.get("name") or ""
        if not port:
            continue
        ports.append({
            "port": port, "status": row.get("status", ""),
            "vlan": row.get("vlan", ""), "name": row.get("name", ""),
        })
    if not ports and res.success and res.output:
        for line in res.output.splitlines():
            parts = line.split()
            parsed = _parse_port_line(parts)
            if parsed:
                ports.append(parsed)
    return res.success, ports, res.error


def _interface_expr(ports: list[str]) -> str:
    if not ports:
        return ""
    if len(ports) == 1:
        return ports[0]
    return "range " + ", ".join(ports)


def _interface_picker(param: actions.Param, action: actions.Action,
                      picked_ids: list, devices: list) -> str:
    prefix = f"if_{action.id}"
    st.markdown(f"**{param.label}**")
    mode = st.radio("Choose ports by", ["📋 Pick from a switch", "🔧 Build port name"],
                    horizontal=True, key=f"{prefix}_mode", label_visibility="collapsed")
    if mode.startswith("📋"):
        return _interface_from_device(prefix, picked_ids, devices)
    return _interface_builder(prefix)


def _fetch_vlans(device: dict) -> tuple[bool, list[tuple[int, str]], str]:
    fam = net._platform_family(device)
    is_fsos = fam == "fiberstore_fsosv2"
    is_netos = fam == "fiberstore_networkos"
    if is_fsos:
        vlan_cmd = "show vlan all"
    elif is_netos:
        vlan_cmd = "show vlan"
    else:
        vlan_cmd = "show vlan brief"
    res = net.run_show_commands(device, [vlan_cmd], use_textfsm=not (is_fsos or is_netos))
    vlans: list[tuple[int, str]] = []
    for raw in (res.parsed or []):
        row = {str(k).lower(): v for k, v in raw.items()}
        vid = row.get("vlan_id") or row.get("vlan")
        name = row.get("vlan_name") or row.get("name") or ""
        try:
            vlans.append((int(vid), str(name)))
        except (TypeError, ValueError):
            continue
    return res.success, vlans, res.error


def _vlan_picker(param: actions.Param, action: actions.Action,
                picked_ids: list, devices: list) -> int:
    prefix = f"vlan_{action.id}"
    st.markdown(f"**{param.label}**")
    candidates = [d for d in devices if d["id"] in picked_ids] or devices
    src_labels = {f'{d["name"]} ({d["ip"]})': d for d in candidates}
    csrc, cbtn = st.columns([3, 1])
    src_label = csrc.selectbox("Load VLAN list from", list(src_labels), key=f"{prefix}_src")
    src = src_labels[src_label]
    cache_key = f"{prefix}_vlans_{src['id']}"
    cbtn.markdown("<div style='height:1.8em'></div>", unsafe_allow_html=True)
    if cbtn.button("🔄 Load VLANs", key=f"{prefix}_load"):
        with st.spinner(f"Fetching VLANs from {src['name']} ..."):
            full = db.get_device_with_credentials(get_key(), src["id"])
            ok, vlans, err = _fetch_vlans(full)
        st.session_state[cache_key] = vlans
        if not ok:
            st.error(f"Could not read VLANs: {err}")
        elif not vlans:
            st.warning("No VLANs parsed — enter ID manually below.")
    vlans = st.session_state.get(cache_key, [])
    if vlans:
        labels = {f"VLAN {v} — {n}" if n else f"VLAN {v}": v for v, n in vlans}
        pick = st.selectbox("Choose VLAN", list(labels), key=f"{prefix}_pick")
        return int(labels[pick])
    return st.number_input(
        "VLAN ID (manual)", min_value=1, max_value=4094,
        value=int(param.default or 1), key=f"{prefix}_manual", help=param.help,
    )


def _interface_from_device(prefix: str, picked_ids: list, devices: list) -> str:
    candidates = [d for d in devices if d["id"] in picked_ids] or devices
    src_labels = {f'{d["name"]} ({d["ip"]})': d for d in candidates}
    csrc, cbtn = st.columns([3, 1])
    src_label = csrc.selectbox("Read ports from", list(src_labels), key=f"{prefix}_src")
    src = src_labels[src_label]
    cache_key = f"{prefix}_ports_{src['id']}"
    sel_key = f"{prefix}_selected"
    cbtn.markdown("<div style='height:1.8em'></div>", unsafe_allow_html=True)
    if cbtn.button("🔄 Load ports", key=f"{prefix}_load"):
        with st.spinner(f"Reading interfaces from {src['name']} ..."):
            full = db.get_device_with_credentials(get_key(), src["id"])
            ok, ports, err = _fetch_ports(full)
        st.session_state[cache_key] = ports
        st.session_state[sel_key] = set()
        if not ok:
            st.error(f"Could not read ports: {err}")
        elif not ports:
            st.warning("No interfaces parsed from this device.")
    ports = st.session_state.get(cache_key)
    if not ports:
        st.caption("Click **Load ports** — then tick the ports you want.")
        return ""

    selected: set[str] = set(st.session_state.get(sel_key, set()))
    ba, bb, bc = st.columns(3)
    if ba.button("☑️ All ports", key=f"{prefix}_ports_all"):
        st.session_state[sel_key] = {p["port"] for p in ports}
        st.rerun()
    if bb.button("☑️ Connected only", key=f"{prefix}_ports_conn"):
        st.session_state[sel_key] = {
            p["port"] for p in ports if p["status"] in ("connected", "up")
        }
        st.rerun()
    if bc.button("Clear selection", key=f"{prefix}_ports_clr"):
        st.session_state[sel_key] = set()
        st.rerun()

    st.caption("Tick each port to include it in this command:")
    view = st.radio(
        "Port view",
        ["🎛️ Switch face", "📋 Port list"],
        horizontal=True,
        key=f"{prefix}_view",
        label_visibility="collapsed",
    )
    if view.startswith("🎛️"):
        new_sel = port_panel.render_switch_face(ports, selected, prefix)
    else:
        ncols = 4
        cols = st.columns(ncols)
        new_sel = set()
        for i, p in enumerate(ports):
            bits = [p["status"] or "?"]
            if p["vlan"]:
                bits.append(f"vlan {p['vlan']}")
            if p.get("name"):
                bits.append(p["name"][:12])
            label = f'{p["port"]}  ({", ".join(bits)})'
            with cols[i % ncols]:
                if st.checkbox(label, value=p["port"] in selected, key=f"{prefix}_cb_{p['port']}"):
                    new_sel.add(p["port"])
    st.session_state[sel_key] = new_sel
    expr = _interface_expr(list(new_sel))
    if expr:
        st.caption(f"Target: `interface {expr}`")
    return expr


def _interface_builder(prefix: str) -> str:
    types = ["GigabitEthernet", "FastEthernet", "TenGigabitEthernet", "TwentyFiveGigE",
             "FortyGigabitEthernet", "Port-channel", "Vlan"]
    t = st.selectbox("Interface type", types, key=f"{prefix}_type")
    if t in ("Port-channel", "Vlan"):
        num = st.number_input("Number", min_value=1, value=1, step=1, key=f"{prefix}_num")
        expr = f"{t}{int(num)}"
        st.caption(f"Target: `interface {expr}`")
        return expr
    stacked = st.checkbox("Stacked / modular switch (e.g. 1/0/1)", value=True,
                          key=f"{prefix}_stk",
                          help="Most modern switches use Stack/Module/Port like Gi1/0/1.")
    if stacked:
        c1, c2, c3, c4 = st.columns(4)
        sw = c1.number_input("Stack/Switch", min_value=0, value=1, step=1, key=f"{prefix}_sw")
        mod = c2.number_input("Module", min_value=0, value=0, step=1, key=f"{prefix}_mod")
        p1 = c3.number_input("From port", min_value=1, value=1, step=1, key=f"{prefix}_p1")
        p2 = c4.number_input("To port", min_value=1, value=1, step=1, key=f"{prefix}_p2",
                             help="Set higher than 'From port' for a range.")
        base = f"{t}{int(sw)}/{int(mod)}"
    else:
        c1, c2, c3 = st.columns(3)
        mod = c1.number_input("Module", min_value=0, value=0, step=1, key=f"{prefix}_mod")
        p1 = c2.number_input("From port", min_value=1, value=1, step=1, key=f"{prefix}_p1")
        p2 = c3.number_input("To port", min_value=1, value=1, step=1, key=f"{prefix}_p2",
                             help="Set higher than 'From port' for a range.")
        base = f"{t}{int(mod)}"
    if int(p2) > int(p1):
        expr = f"range {base}/{int(p1)} - {int(p2)}"
    else:
        expr = f"{base}/{int(p1)}"
    st.caption(f"Target: `interface {expr}`")
    return expr


def _execute(action: actions.Action, cli_lines, save_after, picked_ids) -> None:
    key = get_key()
    targets = [db.get_device_with_credentials(key, did) for did in picked_ids]
    targets = [t for t in targets if t]

    # Build the per-device task.
    if action.kind == "show":
        def task(d):
            return net.run_show_commands(d, cli_lines, use_textfsm=action.use_textfsm)
        command_str = "\n".join(cli_lines)
    elif action.id == "save_config":
        def task(d):
            return net.send_config(d, [], save=True)
        command_str = "write memory"
    else:
        def task(d):
            return net.send_config(d, cli_lines, save=save_after)
        command_str = "\n".join(cli_lines)

    prog = st.progress(0.0)
    status = st.empty()
    placeholders = {}
    for t in targets:
        placeholders[t["id"]] = st.empty()
        placeholders[t["id"]].info(f"⏳ {t['name']} ({t['ip']}) — pending")

    def render_result(res: net.ExecResult) -> None:
        ph = placeholders.get(res.device_id)
        if ph is None:
            return
        with ph.container():
            if res.success:
                st.success(f"✅ {res.name} ({res.ip})")
            else:
                st.error(f"❌ {res.name} ({res.ip}) — {res.error}")
            if res.parsed:
                st.dataframe(pd.DataFrame(res.parsed), use_container_width=True,
                             hide_index=True)
            if res.output:
                with st.expander("Output"):
                    st.code(res.output)

    def cb(done: int, total: int, res: net.ExecResult) -> None:
        prog.progress(done / total)
        status.write(f"Completed {done}/{total}")
        render_result(res)
        if res.device_id is not None and res.success:
            db.mark_seen(res.device_id)
        db.log_action(res.device_id, res.name, res.ip, action.id, command_str,
                      "success" if res.success else "failed", res.output, res.error)
        # Auto-snapshot running-config pulls.
        if action.id == "show_run" and res.success and res.output:
            db.save_snapshot(key, res.device_id, res.name, res.ip, res.output,
                             label="auto: show run")

    results = net.mass_execute(targets, task, progress_callback=cb)
    ok = sum(1 for r in results if r.success)
    status.success(f"Finished: {ok}/{len(results)} succeeded.")


def page_backups() -> None:
    st.header("💾 Config Backups & Diff")
    st.caption("Running-config snapshots are encrypted at rest with your master key.")
    devices = db.list_devices()

    with st.expander("📥 Pull a fresh backup now"):
        if not devices:
            st.info("No devices in inventory.")
        else:
            labels = {f'{d["name"]} ({d["ip"]})': d for d in devices}
            sel = st.multiselect("Devices", list(labels.keys()))
            if st.button("Backup selected", type="primary", disabled=not sel):
                key = get_key()
                targets = [db.get_device_with_credentials(key, labels[s]["id"]) for s in sel]
                prog = st.progress(0.0)

                def cb(done, total, res):
                    prog.progress(done / total)
                    if res.success:
                        db.save_snapshot(key, res.device_id, res.name, res.ip,
                                         res.output, label="manual backup")
                    db.log_action(res.device_id, res.name, res.ip, "backup", "show running-config",
                                  "success" if res.success else "failed", "", res.error)

                results = net.mass_execute(targets, net.get_running_config,
                                           progress_callback=cb)
                ok = sum(1 for r in results if r.success)
                st.success(f"Backed up {ok}/{len(results)} device(s).")
                for r in results:
                    if not r.success:
                        st.error(f"{r.name} ({r.ip}): {r.error}")

    snaps = db.list_snapshots()
    if not snaps:
        st.info("No snapshots yet.")
        return

    sdf = pd.DataFrame(snaps)
    sdf["ts"] = sdf["ts"].apply(_ts)
    st.dataframe(sdf[["id", "device_name", "ip", "ts", "label"]],
                 use_container_width=True, hide_index=True)

    st.subheader("View / Diff")
    opt = {f'#{s["id"]} {s["device_name"]} @ {_ts(s["ts"])}': s["id"] for s in snaps}
    c1, c2 = st.columns(2)
    a_label = c1.selectbox("Snapshot A (older)", list(opt.keys()))
    b_label = c2.selectbox("Snapshot B (newer)", list(opt.keys()),
                           index=min(1, len(opt) - 1))
    key = get_key()
    a_txt = db.get_snapshot_content(key, opt[a_label]) or ""
    b_txt = db.get_snapshot_content(key, opt[b_label]) or ""

    tab_view, tab_diff = st.tabs(["View B", "Diff A → B"])
    with tab_view:
        st.code(b_txt)
        st.download_button("Download snapshot B", b_txt,
                           file_name=f"snapshot_{opt[b_label]}.txt")
    with tab_diff:
        diff = list(difflib.unified_diff(a_txt.splitlines(), b_txt.splitlines(),
                                         "A", "B", lineterm=""))
        if diff:
            st.code("\n".join(diff), language="diff")
        else:
            st.success("No differences between the two snapshots.")

    if st.button("🗑️ Delete snapshot B"):
        db.delete_snapshot(opt[b_label])
        st.rerun()


def page_audit() -> None:
    st.header("📜 Audit Log")
    logs = db.get_audit_log()
    if not logs:
        st.info("No activity logged yet.")
        return
    ldf = pd.DataFrame(logs)
    ldf["ts"] = ldf["ts"].apply(_ts)
    st.dataframe(
        ldf[["ts", "device_name", "ip", "action", "status", "command"]],
        use_container_width=True, hide_index=True,
    )
    with st.expander("Inspect a log entry"):
        ids = {f'#{l["id"]} {l["action"]} → {l["device_name"]} ({l["status"]})': l
               for l in logs}
        sel = st.selectbox("Entry", list(ids.keys()))
        entry = ids[sel]
        st.write(f"**Command:**")
        st.code(entry["command"] or "(none)")
        if entry["output"]:
            st.write("**Output:**")
            st.code(entry["output"])
        if entry["error"]:
            st.error(entry["error"])
    if st.button("Clear audit log"):
        db.clear_audit_log()
        st.rerun()


def page_quick_wizard() -> None:
    st.header("⚡ Quick Wizard")
    st.caption(
        "Simplest path: **devices → ports → intent → run**. "
        "No CLI knowledge required — preview shows exact commands."
    )
    devices = db.list_devices()
    if not devices:
        st.info("Add devices first (Scanner or Inventory).")
        return

    st.subheader("1. Targets")
    picked_ids = _render_target_picker(devices, "qw")
    st.caption(f"{len(picked_ids)} device(s) selected.")

    st.subheader("2. Ports")
    if not picked_ids:
        st.warning("Select at least one device above.")
    iface_expr = _interface_from_device("qw", picked_ids, devices) if picked_ids else ""

    st.subheader("3. What to do")
    target_types = _device_types_for_targets(devices, picked_ids)
    intents = wizard.INTENTS
    if target_types:
        intents = [
            i for i in wizard.INTENTS
            if actions.action_visible(actions.get_action(i.action_id), target_types)
        ]
    if not intents:
        st.warning("No wizard tasks match the selected device types.")
        return
    intent = st.radio(
        "Choose task",
        intents,
        format_func=lambda i: i.label,
        key="qw_intent",
    )
    st.info(f"**What this does:** {intent.explanation}")

    values: dict = {}
    if "vlan" in intent.extra_params:
        values["vlan"] = st.number_input("Access VLAN ID", min_value=1, max_value=4094,
                                         value=1, key="qw_vlan")
    if "description" in intent.extra_params:
        values["description"] = st.text_input("Description", key="qw_desc",
                                            placeholder="Printer - Floor 2")

    cli_lines = None
    action = None
    if iface_expr:
        try:
            action, cli_lines = wizard.build_cli(intent.id, iface_expr, values)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not build command: {exc}")

    save_after = False
    if action and action.kind == "config" and action.save_after:
        save_after = st.checkbox("Save to startup-config (write memory)", key="qw_save")

    if cli_lines is not None:
        st.subheader("4. Preview")
        preview = _preview_text(action, cli_lines, save_after) if action else ""
        st.code(preview, language="bash")

    st.subheader("5. Run")
    can_run = bool(picked_ids) and cli_lines and action
    if action and action.kind == "config" and picked_ids:
        can_run = can_run and st.checkbox(
            f"I understand this will be sent to **{len(picked_ids)}** device(s).",
            key="qw_confirm",
        )
    label = f"🚀 Apply to {len(picked_ids)} device(s)" if picked_ids else "Select devices first"
    if st.button(label, type="primary", disabled=not can_run, key="qw_run"):
        _execute(action, cli_lines, save_after, picked_ids)


def page_tunnel_wizard() -> None:
    st.header("🛤️ DMVPN Tunnel Wizard")
    st.caption(
        "Step-by-step hub or spoke setup — shared crypto, GRE multipoint, NHRP on the hub. "
        "Deploy the **hub first**, then spokes with matching PSK and NHRP network-id."
    )
    devices = db.list_devices()
    if not devices:
        st.info("Add devices first (Scanner or Inventory).")
        return

    st.subheader("1. Targets")
    picked_ids = _render_target_picker(devices, "tw")
    target_types = _device_types_for_targets(devices, picked_ids)
    if target_types:
        st.caption(
            "Platforms: " + ", ".join(sorted({actions.platform_family(dt) for dt in target_types}))
        )

    st.subheader("2. Hub or spoke")
    roles = tunnel_wizard.compatible_roles(target_types)
    if not roles:
        st.warning("DMVPN requires **IOS/XE** targets. Select IOS devices or add demo switches.")
        return
    role = st.radio(
        "Role",
        roles,
        format_func=lambda r: r.label,
        key="tw_role",
    )
    st.info(f"**What this does:** {role.explanation}")

    st.subheader("3. Settings & run")
    action = tunnel_wizard.action_for_role(role.id)
    _render_action_ui(action, picked_ids, devices)


def page_coach() -> None:
    st.header("📚 Coach & Cheat Sheet")
    st.caption(
        "Search network terms and tasks — learn what they mean, then jump straight "
        "to Control Center to run them."
    )
    query = st.text_input(
        "Search", placeholder="Try: VLAN, PoE, GRE tunnel, trunk, ACL, SVI…",
        key="cheat_search",
    )
    hits = cheatsheet.search(query)
    if query and not hits["glossary"] and not hits["actions"]:
        st.warning("No matches — try another keyword or browse all terms below.")

    if hits["glossary"]:
        st.subheader("Terms & concepts")
        for entry in hits["glossary"]:
            with st.expander(f"**{entry.term}** ({entry.category})"):
                st.write(entry.definition)
                if entry.action_ids:
                    st.markdown("**Related tasks:**")
                    for aid in entry.action_ids:
                        if aid not in actions.ACTIONS_BY_ID:
                            continue
                        act = actions.get_action(aid)
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"- **{act.name}** ({act.category})")
                        if c2.button("Open in Control Center", key=f"goto_{aid}_{entry.term[:8]}"):
                            st.session_state["goto_action"] = aid
                            st.session_state["pending_nav"] = "Control Center"
                            st.rerun()

    if hits["actions"]:
        st.subheader("Runnable tasks")
        for act in hits["actions"]:
            with st.expander(f"{act.name} — {act.category}"):
                st.info(act.explanation)
                if st.button("Configure in Control Center", key=f"goto_act_{act.id}"):
                    st.session_state["goto_action"] = act.id
                    st.session_state["pending_nav"] = "Control Center"
                    st.rerun()

    if not query:
        st.subheader("Browse by topic")
        for cat in cheatsheet.categories():
            st.markdown(f"**{cat}**")
            for entry in [e for e in cheatsheet.GLOSSARY if e.category == cat]:
                st.markdown(f"- **{entry.term}** — {entry.definition[:120]}…")


def page_settings() -> None:
    st.header("⚙️ Settings")

    st.subheader("Change master password")
    with st.form("change_pw"):
        cur = st.text_input("Current password", type="password")
        new1 = st.text_input("New password", type="password")
        new2 = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Change password", type="primary"):
            if db.verify_master_password(cur) is None:
                st.error("Current password is wrong.")
            elif len(new1) < 8 or new1 != new2:
                st.error("New password must be 8+ chars and match.")
            else:
                new_key = db.change_master_password(get_key(), new1)
                st.session_state["key"] = new_key
                st.success("Master password changed; all secrets re-encrypted.")

    st.subheader("Inventory import / export")
    c1, c2 = st.columns(2)
    with c1:
        csv_text = db.export_devices_csv()
        st.download_button("⬇️ Export inventory (CSV, no secrets)", csv_text,
                           file_name="ciscoman_inventory.csv")
        st.caption("Secrets are never exported.")
    with c2:
        up = st.file_uploader("⬆️ Import devices (CSV)", type=["csv"])
        st.caption("Columns: name,ip,device_type,port,location,group_name,username,password,secret")
        if up is not None and st.button("Import now"):
            count, errors = db.import_devices_csv(get_key(), up.read().decode("utf-8"))
            st.success(f"Imported/updated {count} device(s).")
            for e in errors:
                st.error(e)

    st.subheader("Session")
    st.write(f"Logged in: **{_ts(st.session_state.get('login_time'))}**")
    st.write(f"Auto-logout after **{config.SESSION_TIMEOUT_MIN} min** of inactivity.")
    st.write(f"Database: `{config.DB_PATH}`")


# --- Router -------------------------------------------------------------------


def main() -> None:
    if not db.is_initialized():
        screen_setup()
        return
    if not is_logged_in():
        screen_login()
        return

    # Apply deferred navigation before sidebar radio is created (Coach → Control Center).
    pending = st.session_state.pop("pending_nav", None)
    if pending:
        st.session_state["sidebar_nav"] = pending

    with st.sidebar:
        st.title("🛰️ CiscoMan")
        st.caption("Cisco IOS management, GUI-first.")
        devs = db.list_devices()
        m1, m2 = st.columns(2)
        m1.metric("Devices", len(devs))
        m2.metric("Locations", len(db.list_locations()))
        nav_options = [
            "Scanner", "Inventory", "Quick Wizard", "Tunnel Wizard", "Control Center",
            "Coach", "Backups", "Audit", "Settings",
        ]
        if "sidebar_nav" not in st.session_state:
            st.session_state["sidebar_nav"] = "Scanner"
        page = st.radio("Navigate", nav_options, key="sidebar_nav")
        st.divider()
        if not net.NETMIKO_AVAILABLE:
            st.error("Netmiko not installed — SSH actions disabled.")
        if st.button("🔒 Lock / Logout"):
            logout()
            st.rerun()

    pages = {
        "Scanner": page_scanner,
        "Inventory": page_inventory,
        "Quick Wizard": page_quick_wizard,
        "Tunnel Wizard": page_tunnel_wizard,
        "Control Center": page_control_center,
        "Coach": page_coach,
        "Backups": page_backups,
        "Audit": page_audit,
        "Settings": page_settings,
    }
    pages[page]()


if __name__ == "__main__":
    main()
