"""Compact switch-face port view: colored tiles showing link state and labels."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QToolButton,
    QScrollArea, QFrame, QSizePolicy,
)

from ciscoman_core import port_status as ps

COLORS = {
    ps.UP: ("#16a34a", "#dcfce7"),
    ps.DOWN: ("#64748b", "#f1f5f9"),
    ps.DISABLED: ("#dc2626", "#fee2e2"),
    ps.UNKNOWN: ("#a16207", "#fef9c3"),
}


class PortTile(QToolButton):
    def __init__(self, port: dict, number: int, parent=None):
        super().__init__(parent)
        self.port = port
        vlan = port.get("vlan") or ""
        label = port.get("name") or (
            "trunk" if vlan.lower() == "trunk" else (f"v{vlan}" if vlan else "")
        )
        short = label[:6] + "…" if len(label) > 7 else label
        self.setText(f"{number}\n{short}" if short else str(number))
        self.setCheckable(True)
        self.setFixedSize(QSize(50, 38))
        border, bg = COLORS.get(port.get("status"), COLORS[ps.UNKNOWN])
        self.setStyleSheet(
            f"QToolButton {{ background:{bg}; border:2px solid {border}; border-radius:4px;"
            f" font-size:7pt; color:#0f172a; padding:0px; }}"
            f"QToolButton:checked {{ background:#bfdbfe; border:3px solid #1d4ed8; }}"
        )
        tip = [f"<b>{port['port']}</b>", f"Status: {port.get('status', '')}"]
        if port.get("name"):
            tip.append(f"Label: {port['name']}")
        if port.get("vlan"):
            tip.append(f"VLAN: {port['vlan']}")
        if port.get("speed"):
            tip.append(f"Speed: {port['speed']}")
        self.setToolTip("<br>".join(tip))


class PortFace(QWidget):
    """Tiles grouped by module, odd ports on top and even below like a real switch."""

    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tiles: list[PortTile] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

    def set_ports(self, ports: list[dict]):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tiles = []
        self.content_height = 0
        groups: "OrderedDict[str, list[tuple[int, dict]]]" = OrderedDict()
        for p in ports:
            prefix, num = ps.split_port(p["port"])
            groups.setdefault(prefix, []).append((num, p))
        for prefix, items in groups.items():
            items.sort(key=lambda x: x[0])
            row = QHBoxLayout()
            row.setSpacing(6)
            title = QLabel(f"<small><b>{prefix or 'Ports'}</b></small>")
            title.setFixedWidth(48)
            title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(title)
            grid = QGridLayout()
            grid.setSpacing(2)
            two_rows = len(items) >= 8
            for idx, (num, p) in enumerate(items):
                tile = PortTile(p, num)
                tile.toggled.connect(self._emit)
                self._tiles.append(tile)
                if two_rows:
                    grid.addWidget(tile, idx % 2, idx // 2)
                else:
                    grid.addWidget(tile, 0, idx)
            row.addLayout(grid)
            row.addStretch()
            holder = QWidget()
            holder.setLayout(row)
            rows = 2 if two_rows else 1
            holder.setFixedHeight(rows * 38 + (rows - 1) * 3 + 4)
            self.content_height += holder.height() + self._layout.spacing()
            self._layout.addWidget(holder)
        self._layout.addStretch()
        self.setMinimumHeight(self.content_height)

    def selected_ports(self) -> list[str]:
        return [t.port["port"] for t in self._tiles if t.isChecked()]

    def clear_selection(self):
        for t in self._tiles:
            t.blockSignals(True)
            t.setChecked(False)
            t.blockSignals(False)
        self._emit()

    def _emit(self, *_):
        self.selectionChanged.emit(self.selected_ports())


class PortPanel(QWidget):
    """Port face + summary + legend. Feed it with set_ports()."""

    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel("Load ports to see link state and labels.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.face = PortFace()
        self.face.selectionChanged.connect(self.selectionChanged)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.face)
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scroll.setFixedHeight(0)
        layout.addWidget(self.scroll)
        legend = QLabel(
            "<small><span style='color:#16a34a'>■</span> up &nbsp; "
            "<span style='color:#64748b'>■</span> down &nbsp; "
            "<span style='color:#dc2626'>■</span> disabled &nbsp; "
            "<span style='color:#1d4ed8'>■</span> selected. "
            "Click ports to pick them for the action; hover for details.</small>"
        )
        legend.setWordWrap(True)
        layout.addWidget(legend)

    def set_ports(self, ports: list[dict], device_name: str = ""):
        self.face.set_ports(ports)
        counts = {s: sum(1 for p in ports if p["status"] == s)
                  for s in (ps.UP, ps.DOWN, ps.DISABLED)}
        who = f"{device_name}: " if device_name else ""
        if ports:
            self.summary.setText(
                f"<b>{who}{len(ports)} ports</b>, {counts[ps.UP]} up, "
                f"{counts[ps.DOWN]} down, {counts[ps.DISABLED]} disabled"
            )
        else:
            self.summary.setText(f"{who}no ports could be read from the output.")
        h = self.face.content_height
        # +18 leaves room for the horizontal scrollbar on very wide switches.
        self.scroll.setFixedHeight(min(h + 18, 420) if ports else 0)

    def set_message(self, text: str):
        self.summary.setText(text)

    def selected_ports(self) -> list[str]:
        return self.face.selected_ports()
