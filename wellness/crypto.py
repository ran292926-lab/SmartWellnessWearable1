"""Password hashing, encryption of stored values and device-token hashing."""

import base64
import hashlib
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


# ---- SR1: salted Argon2id, 19 MiB memory, 2 iterations, parallelism 1 ----

def hash_password(password):
    kdf = Argon2id(salt=os.urandom(16), length=32, iterations=2, lanes=1, memory_cost=19456)
    return kdf.derive_phc_encoded(password.encode())


def verify_password(password, stored_hash):
    try:
        Argon2id.verify_phc_encoded(password.encode(), stored_hash)
        return True
    except InvalidKey:
        return False


# ---- SR17: AES-256 encryption of stored values ----
# ---- SR18: key kept outside the source code and the database ----

_aes = None


def load_key(config):
    global _aes
    if config.get("DATA_KEY"):
        key = base64.b64decode(config["DATA_KEY"])
    else:
        key_file = Path(config["KEY_FILE"])
        if not key_file.exists():
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(base64.b64encode(AESGCM.generate_key(bit_length=256)))
        key = base64.b64decode(key_file.read_bytes())
    _aes = AESGCM(key)


def encrypt(value):
    nonce = os.urandom(12)
    return nonce + _aes.encrypt(nonce, str(value).encode(), None)


def decrypt(blob):
    return _aes.decrypt(blob[:12], blob[12:], None).decode()


# ---- SR9: device token stored on the server only as a hash ----

def new_token():
    return secrets.token_urlsafe(32)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


# ---- SR20: 8-character contact ID from a cryptographically secure generator ----

def new_contact_id():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(chars) for _ in range(8))
