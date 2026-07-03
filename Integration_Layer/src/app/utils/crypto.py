"""Fernet-based symmetric encryption for sensitive token fields.

Uses AES-128-CBC + HMAC-SHA256 from the ``cryptography`` package.  The key
must be a URL-safe base64-encoded 32-byte value.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

from cryptography.fernet import Fernet


def encrypt_token(plaintext: str, key: str) -> str:
    """Encrypt ``plaintext`` with Fernet; returns a URL-safe base64 string."""
    return Fernet(key.encode()).encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str, key: str) -> str:
    """Decrypt a Fernet-encrypted token.

    Raises ``cryptography.fernet.InvalidToken`` if the key is wrong or the
    ciphertext has been tampered with.
    """
    return Fernet(key.encode()).decrypt(ciphertext.encode()).decode()
