"""Settings read from environment variables, outside the source code (NFR13, SR18)."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


class Config:
    # NFR13: database connection setting
    DATABASE = os.environ.get("DATABASE", str(PROJECT_DIR / "instance" / "wellness.db"))

    # SR18: AES-256 key, base64-encoded, kept outside the source code and the database.
    # If DATA_KEY is not set, the key is read from (or created in) KEY_FILE.
    DATA_KEY = os.environ.get("DATA_KEY")
    RATE_LIMIT = 60   # SR27: requests per minute per client IP address
    KEY_FILE = os.environ.get("KEY_FILE", str(Path.home() / ".smart_wellness" / "data.key"))
