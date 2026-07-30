# HDT-15: Device Status API

## Overview
Build DRF endpoints to expose device status and health failures. This provides the backend for device search/filter UIs and monitoring tools.

## Key Files to Create/Modify
- `telemetry/models.py` — Add `DeviceFailure` model to track failure reasons
- `telemetry/serializers.py` — Add `DeviceFailureSerializer` and `DeviceDetailSerializer`
- `telemetry/views.py` — Add `DeviceViewSet` with list/detail actions
- `telemetry/urls.py` — Register the viewset with DRF router

## Implementation Plan

### 1. Add DeviceFailure Model
```python
class DeviceFailure(models.Model):
    device = ForeignKey(Device)
    failure_type = CharField(choices=['inactivity', 'out_of_range', 'frequency_anomaly'])
    detected_at = DateTimeField(auto_now_add=True)
    resolved_at = DateTimeField(null=True)
    details = JSONField()  # flexible schema per failure type
```

### 2. Create Serializers
- `DeviceFailureSerializer` — Serialize failure records with timestamp and type
- `DeviceDetailSerializer` — Device + list of active (unresolved) failures
- `DeviceListSerializer` — Device with status, latest_status, count of active failures

### 3. Create ViewSet
- `DeviceViewSet` with `list()` and `retrieve()` actions
- Queryset: all devices with prefetch_related for failures
- Filtering: `?failure_type=inactivity,out_of_range` filters by active failure type
- Ordering: by device.dev_eui or updated_at

### 4. Wire Routes
- Register router in `urls.py` at `/api/devices/`
- Routes: GET `/api/devices/`, GET `/api/devices/{id}/`

## Acceptance Criteria
1. Can list all devices with status and active failure count
2. Can retrieve device detail with all active failures
3. Can filter by failure_type (supports multiple comma-separated types)
4. Tests pass for all list/detail/filter scenarios
5. Auth required (token auth from HDT-6 applies)

## Dependencies
- Depends on: nothing immediately (DeviceFailure will be populated by HDT-12, 13, 14)
- But the API structure should be ready for failures to arrive

## Notes
- DeviceFailure will be empty initially — the detection checks (HDT-12, 13, 14) will populate it
- API can still serve list/detail with empty failures — useful for UI development
- Filtering can be added incrementally as failure types are implemented
