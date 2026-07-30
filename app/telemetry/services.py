"""Pure decode/parse helpers for payload ingest.

No ORM in here — models stay thin (HDT-5 decision) and these stay trivially
unit-testable. The view owns persistence and transaction boundaries.
"""
import base64
import datetime

from django.utils.dateparse import parse_datetime

from .models import Status


def decode_payload(data_b64):
    """Return (decoded_hex, status) for an already-validated base64 string.

    Status compares the *integer value* big-endian, not the byte pattern, so
    b'\\x00\\x01' still passes — PROMPT.md says "if the value of the data is
    1", and a device that widens its payload from 1 to 2 bytes keeps working.
    """
    raw = base64.b64decode(data_b64)
    # b'' can only reach here if validation is bypassed; int.from_bytes gives
    # 0 for it, so the function stays total and lands on failing.
    value = int.from_bytes(raw, 'big')
    status = Status.PASSING if value == 1 else Status.FAILING
    return raw.hex(), status


def extract_received_at(rx_info):
    """Pull rxInfo[0].time as an aware datetime, or None.

    Missing/unparseable gateway time is a data condition, not a client error,
    so every failure mode returns None rather than raising.
    """
    if not rx_info or not isinstance(rx_info[0], dict):
        return None
    time_str = rx_info[0].get('time')
    if not isinstance(time_str, str):
        return None
    parsed = parse_datetime(time_str)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        # Gateway timestamps are conventionally UTC and the PROMPT example is
        # naive; assuming UTC beats Django guessing (and warning) at save time.
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed
