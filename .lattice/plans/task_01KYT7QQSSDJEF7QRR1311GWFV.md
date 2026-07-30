# HDT-11: Device Health Configuration

## Overview
Build a configuration system for device health thresholds. Each device can have customized limits for temperature, humidity, reporting frequency, and inactivity detection.

## Key Files to Create/Modify
- `telemetry/models.py` — Add `DeviceHealthConfig` model
- `telemetry/serializers.py` — Add `DeviceHealthConfigSerializer`
- `telemetry/views.py` — Add `DeviceHealthConfigViewSet`
- `telemetry/admin.py` — Register config in Django admin
- `telemetry/urls.py` — Wire up config viewset
- `telemetry/tests.py` — Add config tests

## Implementation Plan

### 1. Create DeviceHealthConfig Model
```python
class DeviceHealthConfig(models.Model):
    device = ForeignKey(Device, on_delete=CASCADE, related_name='health_config')
    inactivity_window_seconds = IntegerField(default=3600)
    temp_min = FloatField(default=-10)
    temp_max = FloatField(default=50)
    humidity_min = FloatField(default=0)
    humidity_max = FloatField(default=100)
    expected_frequency_seconds = IntegerField(default=600)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('device',)]  # One config per device
```

### 2. Create Serializer & ViewSet
- `DeviceHealthConfigSerializer` — CRUD serializer with validation
- `DeviceHealthConfigViewSet` — ViewSet at `/api/payloads/devices/{id}/health-config/`
- Allow GET/PUT/PATCH for retrieving and updating config
- Validation: all values must be positive/reasonable

### 3. Add Admin Interface
- Register `DeviceHealthConfig` in `admin.py`
- Display device dev_eui, all config fields
- Make editable in admin

### 4. Clean Up Device Model
- Remove the incomplete `acceptedRanges` and `updateFrequency` fields from Device
- (They'll be part of DeviceHealthConfig instead)
- Create migration to drop these columns

## Acceptance Criteria
1. Can create/update health config via API
2. Config values have sensible defaults and validation
3. Can view config in admin interface
4. Tests pass for CRUD operations and validation
5. Defaults work when no explicit config is set

## Dependencies
- Depends on: nothing (foundational for HDT-12, 13, 14)
- Required by: HDT-12, 13, 14 (detection checks will read this config)

## Notes
- Each device can have exactly one config (one-to-one relationship)
- Config will be read by health check workers/signals
- Defaults should be sensible for typical indoor sensor scenarios
