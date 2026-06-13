"""SQLite persistence layer for CiscoMan.

Tables
------
app_meta          : key/value store (salt, verify token, schema version)
devices           : inventory; SSH password + enable secret stored Fernet-encrypted
audit_log         : every command/config push with status + captured output
config_snapshots  : running-config backups (content encrypted at rest)

All functions that touch secrets require the session ``key`` (bytes) derived from
the master password. Metadata reads (listing devices) do not need the key.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator, Optional

import config

SCHEMA_VERSION = 1


@contextmanager
def _connect(db_path: str = config.DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                ip           TEXT NOT NULL,
                device_type  TEXT NOT NULL DEFAULT 'cisco_ios',
                port         INTEGER NOT NULL DEFAULT 22,
                location     TEXT NOT NULL DEFAULT '',
                group_name   TEXT DEFAULT '',
                username     TEXT NOT NULL,
                enc_password TEXT NOT NULL,
                enc_secret   TEXT DEFAULT '',
                created_at   REAL NOT NULL,
                last_seen    REAL,
                UNIQUE (ip, port)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                device_id   INTEGER,
                device_name TEXT,
                ip          TEXT,
                action      TEXT,
                command     TEXT,
                status      TEXT,
                output      TEXT,
                error       TEXT
            );

            CREATE TABLE IF NOT EXISTS config_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id   INTEGER,
                device_name TEXT,
                ip          TEXT,
                ts          REAL NOT NULL,
                label       TEXT,
                enc_content TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply lightweight, idempotent column additions for older databases."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)").fetchall()}
    if "is_demo" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0")
    if "location" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN location TEXT NOT NULL DEFAULT ''")


# --- Master password / key bootstrap -----------------------------------------


def is_initialized(db_path: str = config.DB_PATH) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM app_meta WHERE key = 'verify_token'"
        ).fetchone()
    return row is not None


def set_master_password(password: str, db_path: str = config.DB_PATH) -> bytes:
    """First-time setup: generate salt, derive key, store verification token."""
    salt = config.generate_salt()
    key = config.derive_key(password, salt)
    token = config.make_verify_token(key)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('salt', ?)",
            (salt.hex(),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('verify_token', ?)",
            (token,),
        )
    return key


def verify_master_password(password: str, db_path: str = config.DB_PATH) -> Optional[bytes]:
    """Return the derived key if the password is correct, else None."""
    with _connect(db_path) as conn:
        salt_row = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'salt'"
        ).fetchone()
        token_row = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'verify_token'"
        ).fetchone()
    if not salt_row or not token_row:
        return None
    key = config.derive_key(password, bytes.fromhex(salt_row["value"]))
    return key if config.key_matches_token(key, token_row["value"]) else None


def change_master_password(
    key: bytes, new_password: str, db_path: str = config.DB_PATH
) -> bytes:
    """Re-encrypt every stored secret under a key derived from the new password."""
    new_salt = config.generate_salt()
    new_key = config.derive_key(new_password, new_salt)
    with _connect(db_path) as conn:
        devices = conn.execute(
            "SELECT id, enc_password, enc_secret FROM devices"
        ).fetchall()
        for d in devices:
            pwd = config.decrypt_value(key, d["enc_password"])
            sec = config.decrypt_value(key, d["enc_secret"]) if d["enc_secret"] else ""
            conn.execute(
                "UPDATE devices SET enc_password = ?, enc_secret = ? WHERE id = ?",
                (
                    config.encrypt_value(new_key, pwd),
                    config.encrypt_value(new_key, sec) if sec else "",
                    d["id"],
                ),
            )
        snaps = conn.execute("SELECT id, enc_content FROM config_snapshots").fetchall()
        for s in snaps:
            content = config.decrypt_value(key, s["enc_content"])
            conn.execute(
                "UPDATE config_snapshots SET enc_content = ? WHERE id = ?",
                (config.encrypt_value(new_key, content), s["id"]),
            )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('salt', ?)",
            (new_salt.hex(),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('verify_token', ?)",
            (config.make_verify_token(new_key),),
        )
    return new_key


# --- Device CRUD --------------------------------------------------------------


def add_device(
    key: bytes,
    name: str,
    ip: str,
    username: str,
    password: str,
    secret: str = "",
    device_type: str = "cisco_ios",
    port: int = config.DEFAULT_SSH_PORT,
    location: str = "",
    group_name: str = "",
    is_demo: int = 0,
    db_path: str = config.DB_PATH,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO devices
                (name, ip, device_type, port, location, group_name, username,
                 enc_password, enc_secret, created_at, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                ip,
                device_type,
                int(port),
                location,
                group_name,
                username,
                config.encrypt_value(key, password),
                config.encrypt_value(key, secret) if secret else "",
                time.time(),
                int(is_demo),
            ),
        )
        return int(cur.lastrowid)


def upsert_device(key: bytes, db_path: str = config.DB_PATH, **fields) -> int:
    """Insert or, on (ip, port) conflict, update an existing device."""
    existing = None
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM devices WHERE ip = ? AND port = ?",
            (fields["ip"], int(fields.get("port", config.DEFAULT_SSH_PORT))),
        ).fetchone()
    if existing:
        update_device(key, existing["id"], db_path=db_path, **fields)
        return int(existing["id"])
    return add_device(key, db_path=db_path, **fields)


def update_device(
    key: bytes, device_id: int, db_path: str = config.DB_PATH, **fields
) -> None:
    columns = []
    values = []
    simple = {"name", "ip", "device_type", "port", "location", "group_name", "username"}
    for col in simple:
        if col in fields and fields[col] is not None:
            columns.append(f"{col} = ?")
            values.append(int(fields[col]) if col == "port" else fields[col])
    if fields.get("password"):
        columns.append("enc_password = ?")
        values.append(config.encrypt_value(key, fields["password"]))
    if "secret" in fields and fields["secret"] is not None:
        columns.append("enc_secret = ?")
        values.append(
            config.encrypt_value(key, fields["secret"]) if fields["secret"] else ""
        )
    if not columns:
        return
    values.append(device_id)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE devices SET {', '.join(columns)} WHERE id = ?", values
        )


def delete_device(device_id: int, db_path: str = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))


def list_devices(db_path: str = config.DB_PATH) -> list[dict]:
    """Metadata only; no decryption."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, name, ip, device_type, port, location, group_name, username,
                   created_at, last_seen, is_demo
            FROM devices ORDER BY location, group_name, name, ip
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_locations(db_path: str = config.DB_PATH) -> list[str]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT location FROM devices WHERE location != '' ORDER BY location"
        ).fetchall()
    return [r["location"] for r in rows]


def list_groups(location: str | None = None, db_path: str = config.DB_PATH) -> list[str]:
    with _connect(db_path) as conn:
        if location:
            rows = conn.execute(
                "SELECT DISTINCT group_name FROM devices WHERE group_name != '' AND location = ? ORDER BY group_name",
                (location,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT group_name FROM devices WHERE group_name != '' ORDER BY group_name"
            ).fetchall()
    return [r["group_name"] for r in rows]


def get_device_with_credentials(
    key: bytes, device_id: int, db_path: str = config.DB_PATH
) -> Optional[dict]:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["password"] = config.decrypt_value(key, d.pop("enc_password"))
    d["secret"] = config.decrypt_value(key, d.pop("enc_secret")) if d.get("enc_secret") else ""
    return d


DEMO_DEVICES = [
    # name, ip, location, group, device_type
    ("SW-CORE-01", "198.51.100.1", "HQ Tbilisi", "Core", "cisco_ios"),
    ("SW-FLOOR1-ACCESS", "198.51.100.11", "HQ Tbilisi", "Floor-1", "cisco_ios"),
    ("SW-FLOOR2-ACCESS", "198.51.100.12", "HQ Tbilisi", "Floor-2", "cisco_ios"),
    ("SW-BR1-ACCESS", "198.51.100.21", "Branch Batumi", "Floor-1", "cisco_ios"),
    ("SW-BR2-ACCESS", "198.51.100.31", "Warehouse Rustavi", "Main Hall", "cisco_ios"),
    ("NX-DEMO-CORE", "198.51.100.50", "HQ Tbilisi", "Core", "cisco_nxos"),
    ("FW-DEMO-EDGE", "198.51.100.51", "HQ Tbilisi", "Edge", "cisco_asa"),
]


def seed_demo_devices(key: bytes, db_path: str = config.DB_PATH) -> int:
    """Insert offline simulator devices for visual testing. Skips existing IPs."""
    existing = {d["ip"] for d in list_devices(db_path=db_path)}
    added = 0
    for name, ip, location, group, dtype in DEMO_DEVICES:
        if ip in existing:
            continue
        add_device(
            key, name=name, ip=ip, username="demo", password="demo",
            secret="demo", device_type=dtype, port=config.DEFAULT_SSH_PORT,
            location=location, group_name=group, is_demo=1, db_path=db_path,
        )
        added += 1
    return added


def mark_seen(device_id: int, db_path: str = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE devices SET last_seen = ? WHERE id = ?", (time.time(), device_id)
        )


# --- Audit log ----------------------------------------------------------------


def log_action(
    device_id: Optional[int],
    device_name: str,
    ip: str,
    action: str,
    command: str,
    status: str,
    output: str = "",
    error: str = "",
    db_path: str = config.DB_PATH,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO audit_log
                (ts, device_id, device_name, ip, action, command, status, output, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                device_id,
                device_name,
                ip,
                action,
                command[:20000],
                status,
                output[:50000],
                error[:5000],
            ),
        )


def get_audit_log(limit: int = 500, db_path: str = config.DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def clear_audit_log(db_path: str = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM audit_log")


# --- Config snapshots (encrypted at rest) ------------------------------------


def save_snapshot(
    key: bytes,
    device_id: Optional[int],
    device_name: str,
    ip: str,
    content: str,
    label: str = "",
    db_path: str = config.DB_PATH,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO config_snapshots
                (device_id, device_name, ip, ts, label, enc_content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                device_name,
                ip,
                time.time(),
                label,
                config.encrypt_value(key, content),
            ),
        )
        return int(cur.lastrowid)


def list_snapshots(
    device_id: Optional[int] = None, db_path: str = config.DB_PATH
) -> list[dict]:
    with _connect(db_path) as conn:
        if device_id is None:
            rows = conn.execute(
                "SELECT id, device_id, device_name, ip, ts, label FROM config_snapshots ORDER BY ts DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, device_id, device_name, ip, ts, label FROM config_snapshots WHERE device_id = ? ORDER BY ts DESC",
                (device_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_snapshot_content(
    key: bytes, snapshot_id: int, db_path: str = config.DB_PATH
) -> Optional[str]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT enc_content FROM config_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
    if not row:
        return None
    return config.decrypt_value(key, row["enc_content"])


def delete_snapshot(snapshot_id: int, db_path: str = config.DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM config_snapshots WHERE id = ?", (snapshot_id,))


# --- CSV import / export ------------------------------------------------------

CSV_COLUMNS = ["name", "ip", "device_type", "port", "location", "group_name", "username", "password", "secret"]


def export_devices_csv(db_path: str = config.DB_PATH, include_secrets: bool = False) -> str:
    """Export inventory metadata. Secrets are intentionally NOT exported."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "ip", "device_type", "port", "location", "group_name", "username"])
    for d in list_devices(db_path=db_path):
        writer.writerow(
            [d["name"], d["ip"], d["device_type"], d["port"], d["location"],
             d["group_name"], d["username"]]
        )
    return buf.getvalue()


def import_devices_csv(key: bytes, csv_text: str, db_path: str = config.DB_PATH) -> tuple[int, list[str]]:
    """Import devices from CSV. Returns (count_imported, errors)."""
    reader = csv.DictReader(io.StringIO(csv_text))
    imported = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        try:
            if not row.get("ip") or not row.get("username"):
                errors.append(f"Row {i}: missing required ip/username")
                continue
            upsert_device(
                key,
                db_path=db_path,
                name=row.get("name") or row["ip"],
                ip=row["ip"].strip(),
                username=row["username"].strip(),
                password=row.get("password", ""),
                secret=row.get("secret", ""),
                device_type=(row.get("device_type") or "cisco_ios").strip(),
                port=int(row.get("port") or config.DEFAULT_SSH_PORT),
                location=(row.get("location") or "").strip(),
                group_name=(row.get("group_name") or "").strip(),
            )
            imported += 1
        except Exception as exc:  # noqa: BLE001 - report per-row, keep going
            errors.append(f"Row {i}: {exc}")
    return imported, errors
