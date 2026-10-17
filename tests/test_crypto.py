"""Tests for cryptographic functions."""

import pytest
from ciscoman_core import config


def test_key_derivation():
    """Test PBKDF2 key derivation."""
    salt = config.generate_salt()
    assert len(salt) == 16
    
    key1 = config.derive_key("test_password", salt)
    key2 = config.derive_key("test_password", salt)
    key3 = config.derive_key("different_password", salt)
    
    assert key1 == key2
    assert key1 != key3


def test_encrypt_decrypt_roundtrip():
    """Test encryption/decryption round-trip."""
    password = "test_password_123"
    salt = config.generate_salt()
    key = config.derive_key(password, salt)
    
    plaintext = "sensitive device password"
    encrypted = config.encrypt_value(key, plaintext)
    decrypted = config.decrypt_value(key, encrypted)
    
    assert decrypted == plaintext
    assert encrypted != plaintext


def test_verify_token():
    """Test master password verification token."""
    password = "master_password_123"
    salt = config.generate_salt()
    key = config.derive_key(password, salt)
    
    token = config.make_verify_token(key)
    assert config.key_matches_token(key, token)
    
    # Wrong key should not match
    wrong_key = config.derive_key("wrong_password", salt)
    assert not config.key_matches_token(wrong_key, token)


def test_secret_redaction():
    """Test secret redaction in commands."""
    cmd_with_psk = "crypto isakmp key MySecret123 address 10.0.0.1"
    redacted = config.redact_secrets(cmd_with_psk)
    assert "MySecret123" not in redacted
    assert "[REDACTED]" in redacted
    
    cmd_with_enable = "enable secret 5 $1$abcd$xyz"
    redacted = config.redact_secrets(cmd_with_enable)
    assert "$1$abcd$xyz" not in redacted
    assert "[REDACTED]" in redacted
    
    cmd_safe = "show running-config"
    redacted = config.redact_secrets(cmd_safe)
    assert redacted == cmd_safe
