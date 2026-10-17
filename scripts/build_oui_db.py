"""Build the bundled MAC vendor (OUI) database.

Source: the Wireshark ``manuf`` file, which is generated from the IEEE
registries (MA-L /24, MA-M /28 and MA-S /36 assignments). Using it gives
CiscoMan brand identification for every registered vendor, not only Cisco.

Usage:
    python scripts/build_oui_db.py                 # download and build
    python scripts/build_oui_db.py path/to/manuf   # build from a local file

Output: ciscoman_core/oui.db with
    oui(prefix TEXT PRIMARY KEY, vendor TEXT)  prefix = 6, 7 or 9 hex digits
    meta(key TEXT PRIMARY KEY, value TEXT)     source, built, entries
"""

from __future__ import annotations

import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MANUF_URL = "https://www.wireshark.org/download/automated/data/manuf"
OUT = Path(__file__).resolve().parent.parent / "ciscoman_core" / "oui.db"


def parse_manuf(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) < 2:
            continue
        addr, short = parts[0], parts[1]
        vendor = parts[2] if len(parts) > 2 else short
        bits = 24
        if "/" in addr:
            addr, b = addr.split("/", 1)
            bits = int(b)
        hexdigits = addr.replace(":", "").replace("-", "").upper()
        if bits == 24:
            prefix = hexdigits[:6]
        elif bits == 28:
            prefix = hexdigits[:7]
        elif bits == 36:
            prefix = hexdigits[:9]
        else:
            continue  # other mask lengths are not vendor assignments
        if len(prefix) in (6, 7, 9) and all(c in "0123456789ABCDEF" for c in prefix):
            entries[prefix] = vendor
    return entries


def build(entries: dict[str, str], out: Path = OUT, source: str = MANUF_URL) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    try:
        conn.execute("CREATE TABLE oui (prefix TEXT PRIMARY KEY, vendor TEXT NOT NULL)")
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany("INSERT INTO oui VALUES (?, ?)", sorted(entries.items()))
        conn.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("source", source),
                ("built", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                ("entries", str(len(entries))),
            ],
        )
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    tmp.replace(out)
    return len(entries)


def main() -> None:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
        source = f"{MANUF_URL} (local copy)"
    else:
        print(f"Downloading {MANUF_URL} ...")
        req = urllib.request.Request(MANUF_URL, headers={"User-Agent": "CiscoMan"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        source = MANUF_URL
    count = build(parse_manuf(text), source=source)
    print(f"Wrote {count} vendor prefixes to {OUT}")


if __name__ == "__main__":
    main()
