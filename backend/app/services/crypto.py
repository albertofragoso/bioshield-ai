"""AES-256-GCM encryption for biomarker data.

Per PRD §5 (Privacidad de Datos): medical data is AES-256 encrypted at rest.
Decrypted values live only in local variables during request processing and
are never persisted to logs or temp storage.

Key handling: the AES key comes from Settings.aes_key (env var AES_KEY).
Must be exactly 32 ASCII bytes (256 bits). KMS integration is the production
upgrade path — tracked in backend/reviews/18-04.md.
"""

import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_IV_LEN = 12  # GCM standard IV length in bytes
_KEY_LEN = 32  # AES-256


def _load_key(aes_key: str) -> bytes:
    key_bytes = aes_key.encode("utf-8")
    if len(key_bytes) != _KEY_LEN:
        raise ValueError(
            f"AES_KEY must be exactly {_KEY_LEN} bytes (got {len(key_bytes)})"
        )
    return key_bytes


def encrypt_biomarker(data: dict, aes_key: str) -> tuple[bytes, bytes]:
    """Encrypt a biomarker dict. Returns (ciphertext, iv)."""
    key = _load_key(aes_key)
    iv = os.urandom(_IV_LEN)
    plaintext = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(iv, plaintext, associated_data=None)
    return ciphertext, iv


def decrypt_biomarker(ciphertext: bytes, iv: bytes, aes_key: str) -> dict:
    """Decrypt biomarker bytes back to a dict. Raises on tampering/bad key."""
    key = _load_key(aes_key)
    plaintext = AESGCM(key).decrypt(iv, ciphertext, associated_data=None)
    return json.loads(plaintext.decode("utf-8"))
