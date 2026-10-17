"""SSH host key management with Trust-On-First-Use (TOFU)."""

import hashlib
from pathlib import Path
from typing import Optional

from ciscoman_core import config


class HostKeyStore:
    """Simple TOFU host key store using SHA256 fingerprints."""
    
    def __init__(self, known_hosts_path: Optional[Path] = None):
        self.path = known_hosts_path or config.SSH_KNOWN_HOSTS
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keys = self._load()
    
    def _load(self) -> dict[str, str]:
        """Load known host keys from file."""
        keys = {}
        if not self.path.exists():
            return keys
        
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2:
                            host_port, fingerprint = parts[0], parts[1]
                            keys[host_port] = fingerprint
        except OSError:
            pass
        
        return keys
    
    def _save(self) -> None:
        """Save known host keys to file."""
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                f.write("# CiscoMan SSH known hosts (TOFU)\n")
                f.write("# Format: host:port SHA256:fingerprint\n")
                for host_port, fingerprint in sorted(self._keys.items()):
                    f.write(f"{host_port} {fingerprint}\n")
        except OSError:
            pass
    
    def get_key(self, host: str, port: int = 22) -> Optional[str]:
        """Get stored fingerprint for host:port."""
        return self._keys.get(f"{host}:{port}")
    
    def add_key(self, host: str, port: int, fingerprint: str) -> None:
        """Add/update host key fingerprint."""
        self._keys[f"{host}:{port}"] = fingerprint
        self._save()
    
    def verify_key(self, host: str, port: int, fingerprint: str) -> tuple[bool, Optional[str]]:
        """
        Verify host key against stored value.
        
        Returns:
            (is_valid, stored_fingerprint)
            - (True, stored) if fingerprint matches stored
            - (True, None) if first connection (TOFU)
            - (False, stored) if fingerprint mismatch
        """
        stored = self.get_key(host, port)
        if stored is None:
            # First connection - trust on first use
            self.add_key(host, port, fingerprint)
            return True, None
        
        if stored == fingerprint:
            return True, stored
        
        # Key mismatch - potential MITM
        return False, stored
    
    @staticmethod
    def fingerprint_from_netmiko_key(key) -> str:
        """Generate SHA256 fingerprint from a Netmiko SSH key object."""
        # key should be a paramiko.PKey subclass
        try:
            key_bytes = key.asbytes()
            digest = hashlib.sha256(key_bytes).hexdigest()
            # Format as SSH-style fingerprint
            return f"SHA256:{digest}"
        except Exception:
            return ""


# Global instance
_host_key_store: Optional[HostKeyStore] = None


def get_host_key_store() -> HostKeyStore:
    """Get the global host key store instance."""
    global _host_key_store
    if _host_key_store is None:
        _host_key_store = HostKeyStore()
    return _host_key_store
