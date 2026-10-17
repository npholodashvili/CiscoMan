"""Frozen-build self-test. Exit 0 only if SNMP client and OUI DB work."""

from __future__ import annotations

import sys
from pathlib import Path


def _write_report(text: str) -> None:
    """Windowed (console=False) builds hide stdout; persist the report."""
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).resolve().parent / "selftest-result.txt")
    try:
        from ciscoman_core import config

        paths.append(Path(config.LOG_DIR) / "selftest-result.txt")
    except Exception:
        pass
    paths.append(Path.cwd() / "selftest-result.txt")
    seen: set[Path] = set()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:
            continue


def run_selftest() -> int:
    errors: list[str] = []
    lines: list[str] = []

    def check(ok: bool, msg: str) -> None:
        status = "OK" if ok else "FAIL"
        line = f"[{status}] {msg}"
        print(line, flush=True)
        lines.append(line)
        if not ok:
            errors.append(msg)

    try:
        from ciscoman_core import fingerprint, mac_discovery, snmp_discovery, snmpv2c
        from ciscoman_core import switch_arp
    except Exception as exc:
        text = f"[FAIL] imports: {exc}\nselftest FAILED\n"
        print(text, flush=True)
        _write_report(text)
        return 2

    check(snmp_discovery.snmp_available(), "SNMP client available (encode/decode GET)")
    pkt = snmpv2c.encode_get_request("public", ["1.3.6.1.2.1.1.1.0"], request_id=1)
    check(pkt[0] == 0x30 and b"public" in pkt, "SNMPv2c GetRequest encodes")
    check(len(pkt) > 20, "SNMP packet has payload")

    resp = snmpv2c.encode_get_response(
        "public", {"1.3.6.1.2.1.1.5.0": "SW-CORE-01"}, request_id=9
    )
    decoded = snmpv2c.decode_get_response(resp)
    check(decoded.get("1.3.6.1.2.1.1.5.0") == "SW-CORE-01", "SNMPv2c GetResponse decodes")

    oui = mac_discovery.find_oui_db()
    check(oui is not None and Path(oui).is_file(), f"OUI database found ({oui})")
    vendor = mac_discovery.lookup_oui_offline("00:00:0C:11:22:33")
    check(bool(vendor) and "Cisco" in (vendor or ""), f"OUI lookup Cisco -> {vendor}")

    sample = (
        "Internet  10.10.110.71           2   0000.0c11.2233  ARPA   Vlan110\n"
        "10.10.110.120  00-1b-21-3a-4c-5d  D\n"
        "10.10.110.80   00aa-bbcc-ddee  110  GE1/0/1  20 D\n"
    )
    parsed = switch_arp.parse_arp_table(sample)
    check(parsed.get("10.10.110.71") == "00:00:0C:11:22:33", "parse Cisco ARP")
    check(parsed.get("10.10.110.120") == "00:1B:21:3A:4C:5D", "parse dashed ARP")
    check(parsed.get("10.10.110.80") == "00:AA:BB:CC:DD:EE", "parse H3C 4-4-4 ARP")

    check(callable(fingerprint.grab_ssh_banner), "fingerprint module loaded")

    if errors:
        report = "\n".join(lines) + f"\nselftest FAILED ({len(errors)} check(s))\n"
        print(f"selftest FAILED ({len(errors)} check(s))", flush=True)
        _write_report(report)
        return 1
    report = "\n".join(lines) + "\nselftest PASSED\n"
    print("selftest PASSED", flush=True)
    _write_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(run_selftest())
