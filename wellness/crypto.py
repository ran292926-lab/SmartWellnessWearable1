"""Password hashing, encryption of stored values and device-token hashing."""

import base64
import hashlib
import hmac
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


# A real Argon2id hash of a random value, checked when the email is unknown so that
# the login takes the same time whether or not the account exists (Week 9 review, F2).
_dummy_hash = None


def verify_dummy_password(password):
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(16))
    verify_password(password, _dummy_hash)
    return False


def verify_password(password, stored_hash):
    try:
        Argon2id.verify_phc_encoded(password.encode(), stored_hash)
        return True
    except InvalidKey:
        return False


# ---- SR17: AES-256 encryption of stored values ----
# ---- SR18: key kept outside the source code and the database ----

_aes = None
_csrf_key = None


def load_key(config):
    global _aes, _csrf_key
    if config.get("DATA_KEY"):
        key = base64.b64decode(config["DATA_KEY"])
    else:
        key_file = Path(config["KEY_FILE"])
        if not key_file.exists():
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(base64.b64encode(AESGCM.generate_key(bit_length=256)))
        key_file.chmod(0o600)   # readable by the owner only, also for key files created earlier
        key = base64.b64decode(key_file.read_bytes())
    _aes = AESGCM(key)
    _csrf_key = hashlib.sha256(b"csrf-token-key" + key).digest()   # derived, never stored


# ---- Week 9 review, F3: the database stores only a hash of each session ID ----

def hash_session_id(session_id):
    return hashlib.sha256(session_id.encode()).hexdigest()


# ---- Week 9 review, F1: CSRF token tied to the session ----

def csrf_token(session_hash):
    return hmac.new(_csrf_key, session_hash.encode(), hashlib.sha256).hexdigest()


def csrf_valid(session_hash, token):
    return bool(token) and hmac.compare_digest(csrf_token(session_hash), token)


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
