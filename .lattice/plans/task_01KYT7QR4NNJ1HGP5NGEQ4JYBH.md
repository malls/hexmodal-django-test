# HDT-13: Out-of-Range Detection

## Overview
Detect and flag when device readings (temperature/humidity) fall outside configured acceptable ranges. Create/resolve DeviceFailure records as readings move in and out of normal bounds.

## Key Files to Create/Modify
- `telemetry/services.py` — Add `check_payload_out_of_range()` function
- `telemetry/views.py` — Call detection function in PayloadIngestView
- `telemetry/tests.py` — Add out-of-range detection tests

## Implementation Plan

### 1. Create Service Function
```python
def check_payload_out_of_range(payload):
    """Check if payload readings exceed device health config ranges."""
    device = payload.device
    config = get_or_create_config(device)
    
    readings = payload.object  # {'temperature': 50.5, 'humidity': 75.0}
    if not readings:
        return None
    
    temp = readings.get('temperature')
    humidity = readings.get('humidity')
    
    is_out_of_range = False
    out_of_range_fields = []
    
    if temp is not None:
        if not (config.temp_min <= temp <= config.temp_max):
            is_out_of_range = True
            out_of_range_fields.append('temperature')
    
    if humidity is not None:
        if not (config.humidity_min <= humidity <= config.humidity_max):
            is_out_of_range = True
            out_of_range_fields.append('humidity')
    
    # Create failure if out of range and no active failure exists
    if is_out_of_range:
        if not device.failures.filter(
            failure_type='out_of_range',
            resolved_at__isnull=True
        ).exists():
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
    else:
        # Resolve any active out_of_range failures
        device.failures.filter(
            failure_type='out_of_range',
            resolved_at__isnull=True
        ).update(resolved_at=timezone.now())
```

### 2. Integrate with Payload Creation
- Call `check_payload_out_of_range(payload)` in PayloadIngestView after creating payload
- Handle None readings gracefully (no temp/humidity in payload)
- Store failure reference for monitoring

### 3. Add Tests
- Test out-of-range temperature detection
- Test out-of-range humidity detection
- Test both temp and humidity out of range
- Test readings within range (no failure)
- Test resolution when readings return to normal
- Test idempotency (no duplicate failures)
- Test missing readings (null values)

## Acceptance Criteria
1. Can detect temperature outside configured range
2. Can detect humidity outside configured range
3. Creates DeviceFailure with type='out_of_range'
4. Resolves failure when readings return to normal
5. Handles missing/null readings gracefully
6. Stores actual reading values in failure details
7. Idempotent (multiple payloads don't create duplicate failures)
8. Tests pass for all scenarios

## Dependencies
- Depends on: HDT-11 (DeviceHealthConfig), Payload.object field exists
- Triggers: out-of-range status visible in HDT-15 API

## Notes
- Payload.object contains decoded sensor readings: `{'temperature': X, 'humidity': Y}`
- Only flag once per out-of-range condition (even if multiple bad readings)
- Use stored readings in details for debugging/alerting
- Can be triggered on payload creation or by periodic batch check
- Null/missing readings should be ignored (not flagged as error)
