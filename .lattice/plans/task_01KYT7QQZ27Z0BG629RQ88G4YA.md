# HDT-12: Inactivity Detection

## Overview
Detect and flag devices that haven't reported a payload within their configured `inactivity_window_seconds`. Create/resolve DeviceFailure records as devices go inactive/active.

## Key Files to Create/Modify
- `telemetry/services.py` — Add `check_device_inactivity()` function
- `telemetry/models.py` — Add helper method `Device.is_inactive()` (optional)
- `telemetry/management/commands/check_inactivity.py` — Management command
- `telemetry/tests.py` — Add inactivity detection tests

## Implementation Plan

### 1. Create Service Function
```python
def check_device_inactivity():
    """Flag devices with no payload in configured window."""
    now = timezone.now()
    for device in Device.objects.all():
        config = device.health_config  # OneToOne, auto-created if needed
        window = timedelta(seconds=config.inactivity_window_seconds)
        cutoff = now - window
        
        latest_payload = device.payloads.filter(created_at__gte=cutoff).exists()
        has_active_failure = device.failures.filter(
            failure_type='inactivity',
            resolved_at__isnull=True
        ).exists()
        
        if not latest_payload and not has_active_failure:
            DeviceFailure.objects.create(
                device=device,
                failure_type='inactivity',
                details={'checked_at': now.isoformat()}
            )
        elif latest_payload and has_active_failure:
            device.failures.filter(
                failure_type='inactivity',
                resolved_at__isnull=True
            ).update(resolved_at=now)
```

### 2. Create Management Command
- Command at `telemetry/management/commands/check_inactivity.py`
- Callable as `python manage.py check_inactivity`
- Useful for testing and scheduled runs (cron, celery, APScheduler)

### 3. Auto-Create Config for Devices Without One
- If device has no health_config, create one with defaults
- Use `get_or_create()` pattern

### 4. Add Tests
- Test inactive device detection
- Test resolution when device becomes active again
- Test config defaults apply when no explicit config
- Test idempotency (no duplicate failures)

## Acceptance Criteria
1. Can detect devices inactive for longer than configured window
2. Creates DeviceFailure with type='inactivity'
3. Resolves failure when device reports a payload
4. Works with default config if none exists
5. Idempotent (multiple runs don't create duplicate failures)
6. Tests pass for all scenarios

## Dependencies
- Depends on: HDT-11 (DeviceHealthConfig must exist)
- Triggers: device inactivity status visible in HDT-15 API

## Notes
- Inactivity check should be idempotent (safe to run multiple times)
- Use timezone.now() for all time comparisons (UTC)
- Avoid N+1 queries: use select_related/prefetch_related for config lookups
- Can be triggered periodically (e.g., every 5 minutes) or on payload arrival
