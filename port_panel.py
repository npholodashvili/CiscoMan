"""Visual switch-face port layout for the port picker.

Renders physical ports in a numbered grid (like the front panel) with
status-colored labels and checkboxes — easier for admins than reading Gi1/0/x strings.
"""

from __future__ import annotations

import re

import streamlit as st


def port_index(port_name: str) -> int:
    """Extract trailing port number from e.g. GigabitEthernet1/0/5 -> 5."""
    m = re.search(r"/(\d+)\s*$", port_name.replace(" ", ""))
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d+)\s*$", port_name)
    return int(m2.group(1)) if m2 else 0


def _status_style(status: str) -> tuple[str, str]:
    s = (status or "").lower()
    if s in ("connected", "up"):
        return "#22c55e", "🟢"
    if s in ("disabled", "shutdown", "err-disabled"):
        return "#ef4444", "🔴"
    if s in ("notconnect", "down", "notconnect"):
        return "#94a3b8", "⚫"
    return "#64748b", "❔"


def render_switch_face(
    ports: list[dict],
    selected: set[str],
    prefix: str,
    cols_per_row: int = 6,
) -> set[str]:
    """Draw numbered port grid; return updated selection set."""
    if not ports:
        return selected

    indexed = sorted(
        [(port_index(p["port"]), p) for p in ports],
        key=lambda x: x[0],
    )
    st.caption(
        "Switch face — tick ports to select. "
        "🟢 connected · ⚫ down · 🔴 disabled"
    )
    new_sel = set(selected)
    row: list[tuple[int, dict]] = []
    for item in indexed:
        row.append(item)
        if len(row) >= cols_per_row:
            _render_row(row, selected, new_sel, prefix)
            row = []
    if row:
        _render_row(row, selected, new_sel, prefix)
    return new_sel


def _render_row(
    row: list[tuple[int, dict]],
    selected: set[str],
    new_sel: set[str],
    prefix: str,
) -> None:
    cols = st.columns(len(row))
    for col, (_, p) in zip(cols, row):
        with col:
            color, icon = _status_style(p.get("status", ""))
            vlan = p.get("vlan") or ""
            hint = f"vlan {vlan}" if vlan and vlan != "trunk" else (p.get("name") or "")[:10]
            st.markdown(
                f"<div style='text-align:center;padding:6px;border-radius:6px;"
                f"background:{color}22;border:2px solid {color}'>"
                f"<b>{icon} {p['port']}</b><br/>"
                f"<span style='font-size:0.75em'>{hint}</span></div>",
                unsafe_allow_html=True,
            )
            checked = st.checkbox(
                "Select",
                value=p["port"] in selected,
                key=f"{prefix}_face_{p['port']}",
                label_visibility="collapsed",
            )
            if checked:
                new_sel.add(p["port"])
            elif p["port"] in new_sel:
                new_sel.discard(p["port"])
