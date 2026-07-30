# HDT-10: Expanded functionality

## Overview
Build a device health monitoring system that automatically detects and flags problems with sensor devices. The system needs to support configurable health thresholds and provide APIs/UI for viewing device status.

## Breakdown into Sub-tasks

### HDT-10.1: Device Health Configuration
- Create `DeviceHealthConfig` model to store configurable thresholds (inactivity window, temp range, humidity range, expected reporting frequency)
- Add admin interface to configure thresholds per device or globally
- **Acceptance**: Can create/update health config with thresholds, tests pass

### HDT-10.2: Inactivity Detection
- Implement check: flag device if no payload received in N seconds (configurable)
- Store failure reason on Device or create `DeviceFailure` model
- **Acceptance**: Can detect inactive devices, tests pass

### HDT-10.3: Out-of-Range Detection
- Implement check: flag device if temperature/humidity outside configured ranges
- Validate against payload's `object.temperature` and `object.humidity` fields
- **Acceptance**: Can detect out-of-range readings, tests pass

### HDT-10.4: Frequency Anomaly Detection
- Implement check: flag device if reporting less frequently than expected
- Calculate inter-arrival times for payloads, compare against threshold
- **Acceptance**: Can detect frequency anomalies, tests pass

### HDT-10.5: Device Status API
- Create DRF endpoint to retrieve device status and active failures
- Support filtering by failure type (inactivity, out-of-range, frequency)
- **Acceptance**: API returns correct device status and failures, tests pass

### HDT-10.6: Device Search/Filter UI
- Build frontend to search/filter devices by failure type
- Display device status and last activity timestamp
- **Acceptance**: Can search devices and see statuses in UI, e2e tests pass

## Approach
- Each sub-task should be independent and committable
- Use a `DeviceFailure` model to track failure reasons (cleaner than flags on Device)
- Health checks can run periodically via a management command or signal handler on payload create
- UI can leverage existing DRF endpoints
