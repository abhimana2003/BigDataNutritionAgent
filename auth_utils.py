import hashlib
import hmac
import os
from typing import Tuple


def hash_password(password: str, salt_hex: str = None) -> Tuple[str, str]:
    if salt_hex is None:
        salt = os.urandom(16)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        390000,
    ).hex()
    return salt_hex, digest


def verify_password(password: str, salt_hex: str, expected_digest_hex: str) -> bool:
    if not salt_hex or not expected_digest_hex:
        return False
    _, candidate = hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(candidate, expected_digest_hex)
