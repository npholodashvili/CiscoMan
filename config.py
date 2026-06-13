"""Central configuration, environment handling, and master-password / key-derivation logic.

Security model
--------------
The Fernet key that encrypts device credentials at rest is NEVER stored on disk.
It is derived from the master password at login using PBKDF2-HMAC-SHA256 with a
random per-install salt. A small verification token (an encrypted known value)
is stored so we can validate the entered password and the derived key in one step.

Consequence: if the master password is lost, stored device credentials are
unrecoverable. That is the intended property.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- Optional .env loading (no hard dependency on python-dotenv) ---------------


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --- Tunable settings ---------------------------------------------------------

DB_PATH: str = os.environ.get("CISCOMAN_DB_PATH", "network_inventory.db")
SESSION_TIMEOUT_MIN: int = _env_int("CISCOMAN_SESSION_TIMEOUT_MIN", 20)
DEFAULT_SSH_PORT: int = _env_int("CISCOMAN_SSH_PORT", 22)
SCAN_WORKERS: int = _env_int("CISCOMAN_SCAN_WORKERS", 100)
EXEC_WORKERS: int = _env_int("CISCOMAN_EXEC_WORKERS", 8)
SCAN_TIMEOUT: float = _env_float("CISCOMAN_SCAN_TIMEOUT", 0.6)
SSH_TIMEOUT: int = _env_int("CISCOMAN_SSH_TIMEOUT", 20)

# PBKDF2 work factor. High enough to be costly to brute force, fast enough for login.
KDF_ITERATIONS: int = 600_000
_VERIFY_PLAINTEXT: bytes = b"CiscoMan::key-verification::v1"

# Netmiko device types we expose in the UI. Default is cisco_ios; the rest keep
# the tool useful as the network is upgraded / expanded.
SUPPORTED_DEVICE_TYPES: tuple[str, ...] = (
    "cisco_ios",
    "cisco_xe",
    "cisco_nxos",
    "cisco_xr",
    "cisco_asa",
    "cisco_s300",
)


# --- Key derivation -----------------------------------------------------------


def generate_salt() -> bytes:
    return os.urandom(16)


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a urlsafe-base64 Fernet key from a password + salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def make_verify_token(key: bytes) -> str:
    """Encrypt a known value so we can later confirm a derived key is correct."""
    return Fernet(key).encrypt(_VERIFY_PLAINTEXT).decode("ascii")


def key_matches_token(key: bytes, token: str) -> bool:
    try:
        return Fernet(key).decrypt(token.encode("ascii")) == _VERIFY_PLAINTEXT
    except (InvalidToken, ValueError):
        return False


def encrypt_value(key: bytes, plaintext: str) -> str:
    if plaintext is None:
        plaintext = ""
    return Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_value(key: bytes, token: str) -> str:
    if not token:
        return ""
    return Fernet(key).decrypt(token.encode("ascii")).decode("utf-8")


@dataclass
class Session:
    """In-memory authenticated session. Holds the derived key; never persisted."""

    key: bytes
    started_at: float
    last_active: float
