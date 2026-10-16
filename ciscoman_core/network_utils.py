"""Network discovery and Netmiko SSH execution.

Scanning uses a privilege-free TCP connect scan to the SSH port (works on
Windows without admin / Npcap). SSH work uses Netmiko with graceful handling of
timeouts and auth failures so the UI never crashes on a bad device.
"""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import config
import simulator

try:
    import actions
except ImportError:
    actions = None  # pragma: no cover

try:
    from ntc_templates.parse import parse_output

    NTC_AVAILABLE = True
except Exception:  # noqa: BLE001
    NTC_AVAILABLE = False

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import (
        NetmikoAuthenticationException,
        NetmikoTimeoutException,
    )

    NETMIKO_AVAILABLE = True
except Exception:  # noqa: BLE001 - allow scanner-only use if netmiko missing
    NETMIKO_AVAILABLE = False

    class NetmikoTimeoutException(Exception):
        pass

    class NetmikoAuthenticationException(Exception):
        pass


# --- Scanning -----------------------------------------------------------------


def expand_targets(cidr_or_range: str) -> list[str]:
    """Accept a CIDR (192.168.1.0/24), single IP, or 'a.b.c.d-e' last-octet range."""
    text = cidr_or_range.strip()
    if "-" in text and "/" not in text:
        base, _, end = text.partition("-")
        base = base.strip()
        end = end.strip()
        start_ip = ipaddress.ip_address(base)
        if "." in end:
            end_ip = ipaddress.ip_address(end)
        else:
            prefix = base.rsplit(".", 1)[0]
            end_ip = ipaddress.ip_address(f"{prefix}.{end}")
        result = []
        cur = int(start_ip)
        while cur <= int(end_ip):
            result.append(str(ipaddress.ip_address(cur)))
            cur += 1
        return result
    net = ipaddress.ip_network(text, strict=False)
    if net.num_addresses <= 2:
        return [str(net.network_address)]
    return [str(h) for h in net.hosts()]


def _tcp_probe(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0
    except OSError:
        return False


def scan_network(
    cidr_or_range: str,
    port: int = config.DEFAULT_SSH_PORT,
    timeout: float = config.SCAN_TIMEOUT,
    workers: int = config.SCAN_WORKERS,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    host_found_callback: Optional[Callable[[str], None]] = None,
) -> list[str]:
    """Return IPs with the given TCP port open. progress_callback(done, total, ip)."""
    targets = expand_targets(cidr_or_range)
    total = len(targets)
    alive: list[str] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, min(workers, total or 1))) as pool:
        futures = {pool.submit(_tcp_probe, ip, port, timeout): ip for ip in targets}
        for fut in as_completed(futures):
            ip = futures[fut]
            done += 1
            if fut.result():
                alive.append(ip)
                if host_found_callback:
                    host_found_callback(ip)
            if progress_callback:
                progress_callback(done, total, ip)
    return sorted(alive, key=lambda x: ipaddress.ip_address(x))


# --- SSH execution ------------------------------------------------------------


@dataclass
class ExecResult:
    device_id: Optional[int]
    name: str
    ip: str
    success: bool
    output: str = ""
    error: str = ""
    parsed: Optional[list] = field(default=None)


def _build_params(device: dict) -> dict:
    params = {
        "device_type": device.get("device_type", "cisco_ios"),
        "host": device["ip"],
        "username": device["username"],
        "password": device.get("password", ""),
        "port": int(device.get("port", config.DEFAULT_SSH_PORT)),
        "timeout": config.SSH_TIMEOUT,
        "fast_cli": False,
    }
    if device.get("secret"):
        params["secret"] = device["secret"]
    return params


def _platform_family(device: dict) -> str:
    if actions is not None:
        return actions.platform_family(device.get("device_type", "cisco_ios"))
    dtype = device.get("device_type", "cisco_ios")
    return {"cisco_nxos": "nxos", "cisco_asa": "asa"}.get(dtype, "ios")


def _prepare_session(conn, device: dict) -> None:
    """Enable + disable paging for readable show output on IOS/NX-OS/ASA."""
    if device.get("secret"):
        try:
            conn.enable()
        except Exception:  # noqa: BLE001
            pass
    fam = _platform_family(device)
    try:
        if fam == "asa":
            conn.send_command("terminal pager 0", read_timeout=30)
        else:
            conn.send_command("terminal length 0", read_timeout=30)
    except Exception:  # noqa: BLE001
        pass


def interface_status_command(device: dict) -> tuple[str, bool]:
    """Return (show command, use_textfsm) for loading port lists."""
    fam = _platform_family(device)
    if fam == "nxos":
        return "show interface status", True
    if fam == "asa":
        return "show interface ip brief", False
    return "show interfaces status", True


def test_connection(device: dict) -> ExecResult:
    """Open a session and immediately close it; validates reachability + creds."""
    name = device.get("name", device["ip"])
    if device.get("is_demo"):
        return ExecResult(device.get("id"), name, device["ip"], True,
                          output=f"Connected (SIMULATED). Prompt: {simulator.prompt(device)}")
    if not NETMIKO_AVAILABLE:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Netmiko not installed")
    try:
        with ConnectHandler(**_build_params(device)) as conn:
            _prepare_session(conn, device)
            prompt = conn.find_prompt()
        return ExecResult(device.get("id"), name, device["ip"], True, output=f"Connected. Prompt: {prompt}")
    except NetmikoAuthenticationException:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Authentication failed")
    except NetmikoTimeoutException:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Connection timed out")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(device.get("id"), name, device["ip"], False, error=str(exc))


def run_show_commands(
    device: dict, commands: Iterable[str], use_textfsm: bool = False
) -> ExecResult:
    """Run one or more exec-level (show) commands."""
    name = device.get("name", device["ip"])
    cmds = [c for c in commands if c.strip()]
    if device.get("is_demo"):
        return _demo_show(device, name, cmds, use_textfsm)
    if not NETMIKO_AVAILABLE:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Netmiko not installed")
    try:
        with ConnectHandler(**_build_params(device)) as conn:
            _prepare_session(conn, device)
            chunks = []
            parsed_all = []
            for cmd in cmds:
                out = conn.send_command(cmd, use_textfsm=use_textfsm)
                if use_textfsm and isinstance(out, list):
                    parsed_all.extend(out)
                    chunks.append(f"# {cmd}\n(parsed {len(out)} rows)")
                else:
                    chunks.append(f"# {cmd}\n{out}")
            return ExecResult(
                device.get("id"),
                name,
                device["ip"],
                True,
                output="\n\n".join(chunks),
                parsed=parsed_all or None,
            )
    except NetmikoAuthenticationException:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Authentication failed")
    except NetmikoTimeoutException:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Connection timed out")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(device.get("id"), name, device["ip"], False, error=str(exc))


def send_config(device: dict, config_lines: Iterable[str], save: bool = False) -> ExecResult:
    """Push configuration commands; optionally 'write memory'."""
    name = device.get("name", device["ip"])
    lines = [c for c in config_lines if c.strip()]
    if device.get("is_demo"):
        out = simulator.apply_config(device, lines)
        if save:
            out += "\n" + simulator.save_config(device)
        return ExecResult(device.get("id"), name, device["ip"], True, output=out)
    if not NETMIKO_AVAILABLE:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Netmiko not installed")
    try:
        with ConnectHandler(**_build_params(device)) as conn:
            _prepare_session(conn, device)
            out = conn.send_config_set(lines)
            if save:
                out += "\n" + conn.save_config()
            return ExecResult(device.get("id"), name, device["ip"], True, output=out)
    except NetmikoAuthenticationException:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Authentication failed")
    except NetmikoTimeoutException:
        return ExecResult(device.get("id"), name, device["ip"], False, error="Connection timed out")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(device.get("id"), name, device["ip"], False, error=str(exc))


def _demo_show(device: dict, name: str, cmds: list[str], use_textfsm: bool) -> ExecResult:
    """Mirror run_show_commands using the offline simulator + real TextFSM parsing."""
    chunks = []
    parsed_all = []
    for cmd in cmds:
        out = simulator.run_show(device, cmd)
        if use_textfsm and NTC_AVAILABLE:
            try:
                rows = parse_output(
                    platform=device.get("device_type", "cisco_ios"), command=cmd, data=out
                )
            except Exception:  # noqa: BLE001
                rows = []
            if rows:
                parsed_all.extend(rows)
                chunks.append(f"# {cmd}\n(parsed {len(rows)} rows)\n{out}")
                continue
        chunks.append(f"# {cmd}\n{out}")
    return ExecResult(
        device.get("id"), name, device["ip"], True,
        output="\n\n".join(chunks), parsed=parsed_all or None,
    )


def get_running_config(device: dict) -> ExecResult:
    res = run_show_commands(device, ["show running-config"])
    if res.success:
        # Strip the leading "# show running-config" header we add.
        res.output = res.output.split("\n", 1)[-1] if res.output.startswith("#") else res.output
    return res


# --- Concurrent mass execution -----------------------------------------------


def mass_execute(
    devices: list[dict],
    task: Callable[[dict], ExecResult],
    workers: int = config.EXEC_WORKERS,
    progress_callback: Optional[Callable[[int, int, ExecResult], None]] = None,
) -> list[ExecResult]:
    """Run ``task`` against each device concurrently, reporting results as they finish."""
    results: list[ExecResult] = []
    total = len(devices)
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, min(workers, total or 1))) as pool:
        futures = {pool.submit(task, d): d for d in devices}
        for fut in as_completed(futures):
            dev = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # noqa: BLE001
                res = ExecResult(
                    dev.get("id"), dev.get("name", dev["ip"]), dev["ip"], False, error=str(exc)
                )
            results.append(res)
            done += 1
            if progress_callback:
                progress_callback(done, total, res)
    return results
