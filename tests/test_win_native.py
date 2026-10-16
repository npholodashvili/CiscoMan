"""ARP parse + hidden-subprocess guarantees."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

from ciscoman_core import win_native
from ciscoman_core.win_native import CREATE_NO_WINDOW, STARTF_USESHOWWINDOW, parse_arp_a, run_hidden


SAMPLE_ARP_A = """
Interface: 192.168.1.50 --- 0xc
  Internet Address      Physical Address      Type
  192.168.1.1           00-00-0c-07-ac-01     dynamic
  192.168.1.10          aa-bb-cc-dd-ee-ff     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static

Interface: 10.0.0.5 --- 0xd
  10.0.0.1              00-1B-21-3A-4C-5D     dynamic
"""


def test_parse_arp_a_extracts_unicast_only():
    table = parse_arp_a(SAMPLE_ARP_A)
    assert table["192.168.1.1"] == "00:00:0C:07:AC:01"
    assert table["192.168.1.10"] == "AA:BB:CC:DD:EE:FF"
    assert table["10.0.0.1"] == "00:1B:21:3A:4C:5D"
    assert "192.168.1.255" not in table
    assert "224.0.0.22" not in table


def test_run_hidden_sets_create_no_window_and_hidden_startupinfo():
    """Any subprocess helper must hide the console — this is what made the PC unusable."""
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch.object(subprocess, "run", side_effect=fake_run):
        with patch.object(os, "name", "nt"):
            # Force Windows branch even on Linux CI
            orig = win_native.os.name
            try:
                win_native.os.name = "nt"
                run_hidden(["arp", "-a"], timeout=2)
            finally:
                win_native.os.name = orig

    assert captured["creationflags"] == CREATE_NO_WINDOW
    assert captured["startupinfo"] is not None
    assert captured["startupinfo"].dwFlags & STARTF_USESHOWWINDOW
    assert captured["startupinfo"].wShowWindow == 0
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["capture_output"] is True


def test_mac_discovery_never_calls_powershell():
    """Identification must not spawn a PowerShell.exe process."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "ciscoman_core"
    forbidden = ('"powershell"', "'powershell'", "powershell.exe", "pwsh.exe")
    for name in ("mac_discovery.py", "win_native.py", "device_identification.py"):
        text = (root / name).read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{name} still launches {token}"


def test_get_arp_table_uses_hidden_fallback(monkeypatch):
    """If the Win32 API is unavailable, fallback is hidden arp -a — not a visible window."""
    from ciscoman_core import mac_discovery

    monkeypatch.setattr(win_native, "_get_arp_table_iphlpapi", lambda: (_ for _ in ()).throw(OSError("no api")))

    called = {}

    def fake_hidden(args, timeout=8):
        called["args"] = args
        result = MagicMock()
        result.stdout = SAMPLE_ARP_A
        result.stderr = ""
        result.returncode = 0
        return result

    monkeypatch.setattr(win_native, "run_hidden", fake_hidden)
    monkeypatch.setattr(win_native.sys, "platform", "win32")
    table = mac_discovery.get_arp_table()
    assert called["args"] == ["arp", "-a"]
    assert table["192.168.1.1"] == "00:00:0C:07:AC:01"
