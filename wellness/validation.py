"""Server-side input validation (SR2, SR13, SR14)."""

import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

RIYADH = ZoneInfo("Asia/Riyadh")
DEVICE_ID_PATTERN = re.compile(r"DEV-[0-9A-F]{8}")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class ValidationError(ValueError):
    pass


# ---- SR14: registration data ----

def display_name(value):
    value = (value or "").strip()
    if not value or len(value) > 50:
        raise ValidationError("Display name must be 1 to 50 characters.")
    return value


def email(value):
    value = (value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(value):
        raise ValidationError("Enter a valid email address.")
    return value


def birth_year(value):
    try:
        year = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Enter a valid birth year.")
    age = datetime.now(RIYADH).year - year      # FR12, NFR7
    if age < 18 or age > 100:
        raise ValidationError("Age must be between 18 and 100.")
    return year


def weight(value):
    try:
        kg = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Enter a valid weight.")
    if not math.isfinite(kg) or kg < 20 or kg > 300:
        raise ValidationError("Weight must be between 20 and 300 kg.")
    return kg


# ---- SR2: password length ----

def password(value):
    value = value or ""
    if len(value) < 8 or len(value) > 128:
        raise ValidationError("Password must be 8 to 128 characters.")
    return value


# ---- SR13: device readings ----

def reading(data):
    """Returns (device_id, type, value, recorded_at in UTC)."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    device_id = data.get("device_id")
    reading_type = data.get("type")
    timestamp = data.get("timestamp")
    value = data.get("value")

    if not device_id:
        raise ValidationError("device_id is required.")
    if not isinstance(device_id, str) or not DEVICE_ID_PATTERN.fullmatch(device_id):
        raise ValidationError("device_id is not valid.")
    if not reading_type:
        raise ValidationError("type is required.")
    if not timestamp:
        raise ValidationError("timestamp is required.")
    if reading_type not in ("heart_rate", "steps", "sleep"):
        raise ValidationError("type must be heart_rate, steps or sleep.")

    try:
        recorded = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError("timestamp must be in ISO 8601 format.")
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=timezone.utc)
    try:
        recorded_at = recorded.astimezone(timezone.utc).isoformat(timespec="seconds")  # NFR5
    except OverflowError:
        raise ValidationError("timestamp is out of range.")

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("value must be a number.")
    if reading_type == "heart_rate" and not 30 <= value <= 220:
        raise ValidationError("Heart rate must be 30 to 220 bpm.")
    if reading_type == "steps" and (not isinstance(value, int) or value < 0):
        raise ValidationError("Step count must be a non-negative integer.")
    if reading_type == "sleep" and not 0 <= value <= 24:
        raise ValidationError("Sleep duration must be 0 to 24 hours.")

    return str(device_id), reading_type, value, recorded_at
