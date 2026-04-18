"""Tests for services/crypto.py — AES-256-GCM biomarker encryption."""

import pytest

from app.services.crypto import decrypt_biomarker, encrypt_biomarker

_KEY = "test-aes-key-32-bytes-xxxxxxxxxx"  # exactly 32 bytes (10 x's)


def test_encrypt_decrypt_roundtrip():
    data = {"glucose": 95, "cholesterol_ldl": 120, "hba1c": 5.4}
    ciphertext, iv = encrypt_biomarker(data, _KEY)

    # Ciphertext is opaque bytes, not the JSON plaintext
    assert isinstance(ciphertext, bytes)
    assert b"glucose" not in ciphertext
    assert b"95" not in ciphertext
    assert len(iv) == 12  # GCM standard

    decrypted = decrypt_biomarker(ciphertext, iv, _KEY)
    assert decrypted == data


def test_each_encryption_has_unique_iv():
    data = {"glucose": 95}
    _, iv1 = encrypt_biomarker(data, _KEY)
    _, iv2 = encrypt_biomarker(data, _KEY)
    assert iv1 != iv2


def test_wrong_key_fails():
    ciphertext, iv = encrypt_biomarker({"x": 1}, _KEY)
    with pytest.raises(Exception):  # cryptography raises InvalidTag
        decrypt_biomarker(ciphertext, iv, "WRONG-KEY-32-bytes-xxxxxxxxxx")


def test_tampered_ciphertext_fails():
    ciphertext, iv = encrypt_biomarker({"x": 1}, _KEY)
    tampered = bytes([ciphertext[0] ^ 0x01]) + ciphertext[1:]
    with pytest.raises(Exception):
        decrypt_biomarker(tampered, iv, _KEY)


def test_key_wrong_length_raises():
    with pytest.raises(ValueError, match="AES_KEY must be exactly 32 bytes"):
        encrypt_biomarker({"x": 1}, "too-short")

    with pytest.raises(ValueError, match="AES_KEY must be exactly 32 bytes"):
        encrypt_biomarker({"x": 1}, "x" * 33)


def test_nested_dict_roundtrip():
    data = {
        "panel": {"date": "2026-04-18", "lab": "Quest"},
        "values": {"glucose": 95, "ldl": 120},
        "notes": "fasting",
    }
    ciphertext, iv = encrypt_biomarker(data, _KEY)
    assert decrypt_biomarker(ciphertext, iv, _KEY) == data
