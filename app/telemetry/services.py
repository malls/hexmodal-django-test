"""Pure decode/parse helpers for payload ingest.

No ORM in here — models stay thin (HDT-5 decision) and these stay trivially
unit-testable. The view owns persistence and transaction boundaries.
"""
import base64
import datetime

from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.db.models import Max

from .models import Status, Device, DeviceFailure, DeviceHealthConfig


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


def check_payload_failing(payload):
    """Flag if payload has failing status (decoded value ≠ 1).

    Creates a failure when payload status is failing, resolves when
    a passing payload arrives. Returns True if failing, False otherwise.
    """
    device = payload.device
    is_failing = payload.status == Status.FAILING

    has_active_failure = device.failures.filter(
        failure_type='payload_failing',
        resolved_at__isnull=True
    ).exists()

    if is_failing and not has_active_failure:
        DeviceFailure.objects.create(
            device=device,
            failure_type='payload_failing',
            details={
                'payload_id': payload.id,
                'decoded_hex': payload.decoded_hex,
                'f_cnt': payload.f_cnt,
                'received_at': payload.received_at.isoformat() if payload.received_at else None,
            }
        )
    elif not is_failing and has_active_failure:
        device.failures.filter(
            failure_type='payload_failing',
            resolved_at__isnull=True
        ).update(resolved_at=timezone.now())

    return is_failing


def check_payload_out_of_range(payload):
    """Flag if payload readings exceed configured ranges for device.

    Checks temperature and humidity against DeviceHealthConfig bounds.
    Creates out_of_range failure once when readings go out, resolves when
    readings return to normal. Returns True if out of range, False otherwise.
    """
    device = payload.device
    config, _ = DeviceHealthConfig.objects.get_or_create(device=device)
    readings = payload.object or {}

    temp = readings.get('temperature')
    humidity = readings.get('humidity')

    out_of_range_fields = []
    is_out_of_range = False

    if temp is not None:
        if not (config.temp_min <= temp <= config.temp_max):
            is_out_of_range = True
            out_of_range_fields.append('temperature')

    if humidity is not None:
        if not (config.humidity_min <= humidity <= config.humidity_max):
            is_out_of_range = True
            out_of_range_fields.append('humidity')

    has_active_failure = device.failures.filter(
        failure_type='out_of_range',
        resolved_at__isnull=True
    ).exists()

    if is_out_of_range and not has_active_failure:
        DeviceFailure.objects.create(
            device=device,
            failure_type='out_of_range',
            details={
                'out_of_range_fields': out_of_range_fields,
                'temperature': temp,
                'humidity': humidity,
                'config': {
                    'temp_min': config.temp_min,
                    'temp_max': config.temp_max,
                    'humidity_min': config.humidity_min,
                    'humidity_max': config.humidity_max,
                },
                'payload_id': payload.id,
            }
        )
    elif not is_out_of_range and has_active_failure:
        device.failures.filter(
            failure_type='out_of_range',
            resolved_at__isnull=True
        ).update(resolved_at=timezone.now())

    return is_out_of_range


def check_device_frequency(device):
    """Flag if recent payloads indicate slower reporting frequency than expected.

    Analyzes the gap between the last two payloads. If the gap exceeds
    1.5x the configured expected_frequency_seconds, flags an anomaly.
    The 1.5x tolerance avoids false positives from brief delays.

    Returns True if frequency is anomalous, False otherwise.
    """
    config, _ = DeviceHealthConfig.objects.get_or_create(device=device)

    recent = device.payloads.order_by('-created_at')[:2]
    if len(recent) < 2:
        return False

    newer = recent[0]
    older = recent[1]

    gap_seconds = (newer.created_at - older.created_at).total_seconds()
    threshold = config.expected_frequency_seconds * 1.5

    is_slow = gap_seconds > threshold

    has_active_failure = device.failures.filter(
        failure_type='frequency_anomaly',
        resolved_at__isnull=True
    ).exists()

    if is_slow and not has_active_failure:
        DeviceFailure.objects.create(
            device=device,
            failure_type='frequency_anomaly',
            details={
                'gap_seconds': gap_seconds,
                'expected_frequency_seconds': config.expected_frequency_seconds,
                'threshold_seconds': threshold,
                'older_payload_id': older.id,
                'newer_payload_id': newer.id,
                'older_created_at': older.created_at.isoformat(),
                'newer_created_at': newer.created_at.isoformat(),
            }
        )
    elif not is_slow and has_active_failure:
        device.failures.filter(
            failure_type='frequency_anomaly',
            resolved_at__isnull=True
        ).update(resolved_at=timezone.now())

    return is_slow


def check_device_inactivity():
    """Flag devices with no payload in configured inactivity window.

    For each device:
    1. Get or create its health config (uses defaults if missing)
    2. Find most recent payload time
    3. If older than inactivity_window_seconds, create inactivity failure
    4. If recent payload exists, resolve any active inactivity failures

    Idempotent: safe to call multiple times.
    """
    now = timezone.now()
    flagged = []
    resolved = []

    for device in Device.objects.all():
        config, _ = DeviceHealthConfig.objects.get_or_create(device=device)
        window = datetime.timedelta(seconds=config.inactivity_window_seconds)
        cutoff = now - window

        last_payload_time = device.payloads.aggregate(
            max_time=Max('created_at')
        )['max_time']

        has_active_failure = device.failures.filter(
            failure_type='inactivity',
            resolved_at__isnull=True
        ).exists()

        if last_payload_time is None:
            is_inactive = True
        else:
            is_inactive = last_payload_time < cutoff

        if is_inactive and not has_active_failure:
            failure = DeviceFailure.objects.create(
                device=device,
                failure_type='inactivity',
                details={
                    'last_payload_time': last_payload_time.isoformat() if last_payload_time else None,
                    'inactivity_window_seconds': config.inactivity_window_seconds,
                    'checked_at': now.isoformat(),
                }
            )
            flagged.append(failure)
        elif not is_inactive and has_active_failure:
            failures = device.failures.filter(
                failure_type='inactivity',
                resolved_at__isnull=True
            )
            count = failures.update(resolved_at=now)
            resolved.extend([f for f in failures])

    return {'flagged': flagged, 'resolved': resolved}
