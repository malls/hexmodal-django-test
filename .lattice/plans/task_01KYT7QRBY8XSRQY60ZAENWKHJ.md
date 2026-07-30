# HDT-14: Frequency Anomaly Detection

## Overview
Detect when devices report payloads less frequently than configured. Flag when inter-arrival time between consecutive payloads exceeds expected_frequency_seconds threshold.

## Key Files to Create/Modify
- `telemetry/services.py` — Add `check_device_frequency()` function
- `telemetry/tests.py` — Add frequency anomaly detection tests

## Implementation Plan

### 1. Create Service Function
```python
def check_device_frequency(device):
    """Flag if recent payloads indicate slower reporting frequency than expected."""
    config, _ = DeviceHealthConfig.objects.get_or_create(device=device)
    
    # Get last 2 payloads to check inter-arrival time
    recent = device.payloads.order_by('-created_at')[:2]
    if len(recent) < 2:
        return False  # Need at least 2 payloads to measure gap
    
    older = recent[1]  # Older of the two
    newer = recent[0]  # Newer of the two
    
    gap_seconds = (newer.created_at - older.created_at).total_seconds()
    
    # Check if gap exceeds expected frequency (with reasonable tolerance)
    # Use 1.5x multiplier to avoid false positives from brief delays
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
```

### 2. Check Strategy
- Analyze last 2 payloads (most recent pair)
- Use 1.5x multiplier on expected_frequency_seconds as threshold
  - Avoids false positives from network jitter
  - Still catches sustained reporting delays
- Measure gap in seconds between creation times

### 3. Add Tests
- Test device with fewer than 2 payloads (no flag)
- Test gap within expected frequency (no flag)
- Test gap exceeding expected frequency (flag)
- Test resolution when frequency improves
- Test idempotency (no duplicate failures)
- Test tolerance margin (1.5x threshold)
- Test with multiple devices independently
- Test with custom expected_frequency_seconds

## Acceptance Criteria
1. Can detect when inter-arrival time exceeds expected frequency
2. Uses 1.5x multiplier to avoid false positives
3. Creates DeviceFailure with type='frequency_anomaly'
4. Requires at least 2 payloads to analyze
5. Resolves when device reports more frequently again
6. Stores gap time and threshold in failure details
7. Idempotent (multiple slow payloads create one failure)
8. Tests pass for all scenarios

## Dependencies
- Depends on: HDT-11 (DeviceHealthConfig)
- Can be called: periodically, on payload creation, or via management command

## Notes
- Frequency check uses last 2 payloads (minimal memory/performance impact)
- 1.5x tolerance accounts for network/processing delays
- Threshold stored in details for debugging
- Gap measured in seconds (created_at timestamps)
- Can be integrated into check_device_frequency management command
- Works independently: doesn't require inactivity or out-of-range checks
