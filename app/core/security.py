from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def api_key_prefix(api_key: str) -> str:
    return api_key[:12]


def hash_api_key(api_key: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(api_key.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    salt_b64, digest_b64 = stored_hash.split(":", maxsplit=1)
    salt = base64.b64decode(salt_b64.encode())
    expected = base64.b64decode(digest_b64.encode())
    actual = hashlib.scrypt(api_key.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(actual, expected)
