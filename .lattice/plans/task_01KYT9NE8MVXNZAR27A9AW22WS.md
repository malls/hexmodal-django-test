# HDT-17: API Enhancements for Search/Filter (HDT-16 dependency)

## Overview
Add three capabilities to `DeviceViewSet` to enable client-side search/filter UI (HDT-16):
1. Text search on `dev_eui` field
2. Status filter by `latest_status`
3. Additional ordering field `latest_status`

## Key Files
- `app/telemetry/views.py` — Update `DeviceViewSet`

## Implementation Plan

### 1. Add SearchFilter
DRF's `SearchFilter` enables `?search=device1` to search `dev_eui` field.
- Import `SearchFilter` from `rest_framework.filters`
- Add `filter_backends = [SearchFilter]` to viewset
- Add `search_fields = ['dev_eui']` to viewset
- Enables case-insensitive substring matching on dev_eui

### 2. Add Status Filter in get_queryset()
Extend existing `get_queryset()` method to filter by `?status=passing|failing|unknown`.
- Check for `status` query param
- Filter by `latest_status` if provided
- Maintains idempotency (no duplicates created by filter)

### 3. Expand ordering_fields
Add `'latest_status'` to existing `ordering_fields` list.
- Current: `['dev_eui', 'updated_at']`
- Updated: `['dev_eui', 'latest_status', 'updated_at']`
- Enables `?ordering=latest_status` or `?ordering=-latest_status`

## Code Changes

```python
# At top of DeviceViewSet class
from rest_framework.filters import SearchFilter

class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Device.objects.prefetch_related('failures')
    filter_backends = [SearchFilter]  # NEW
    search_fields = ['dev_eui']  # NEW
    ordering_fields = ['dev_eui', 'latest_status', 'updated_at']  # UPDATED
    ordering = ['dev_eui']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Existing failure_type filter
        failure_types = self.request.query_params.get('failure_type')
        if failure_types:
            types = [t.strip() for t in failure_types.split(',')]
            queryset = queryset.filter(
                failures__failure_type__in=types,
                failures__resolved_at__isnull=True
            ).distinct()
        
        # NEW: Status filter
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(latest_status=status)
        
        return queryset
```

## Testing
- No new tests needed (existing device list tests cover API behavior)
- Manual verification: test `?search=`, `?status=`, and `?ordering=` params

## Acceptance Criteria
1. ✓ `?search=device1` filters by dev_eui substring (case-insensitive)
2. ✓ `?status=passing` filters by latest_status
3. ✓ `?ordering=latest_status` sorts by latest_status ascending
4. ✓ `?ordering=-latest_status` sorts by latest_status descending
5. ✓ Query params can be combined: `?search=dev&status=failing&ordering=-updated_at`
6. ✓ SearchFilter works with existing failure_type filter
7. ✓ No regressions to existing API behavior

## Complexity
Low — straightforward additions to existing viewset, no schema changes.

## Time Estimate
5–10 minutes implementation + testing.
