<!-- AI -->
# hexmodal-django-test

Django + DRF service that ingests IoT uplink payloads: token-authenticated
POST, per-device `fCnt` duplicate rejection, base64→hex decode, and a
passing/failing status tracked on each device.

Quick start from a fresh clone:

```
cp .env.example .env        # optional — compose falls back to the same defaults
docker compose up -d
docker compose exec web python manage.py migrate
```

`POSTGRES_PORT` in `.env` is the host-side port Postgres is published on
(5432 in `.env.example`).

If compose fails with a platform mismatch ("image's platform does not match"
or an exec format error), your shell exports a `DOCKER_DEFAULT_PLATFORM` that
disagrees with your Docker daemon — override it in the gitignored
`mise.local.toml`; see the comment in `mise.toml`.

<!-- handwritten -->
To start the service: 
`docker compose up`

To set up to run python commands locally
```
brew install mise
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
exec zsh
pip install -r app/requirements.txt
```

To view/edit project management issues:
```
pip install lattice-tracker
lattice dashboard
```

To view the local database (port = `POSTGRES_PORT` from your `.env`)
`psql postgres://hexmodal:hexmodal@localhost:5433/hexmodal`

<!-- AI -->
## API authentication

The API uses DRF token auth; every request needs a token. One-time setup
(drop the `docker compose exec web` prefix to run locally instead):
```
docker compose exec web python manage.py migrate            # creates the token table
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py drf_create_token <username>
```

Requests send the header: `Authorization: Token <key>`

## Payload ingest

`POST /api/payloads/` ingests one uplink frame:

```
curl -s -X POST http://localhost:8000/api/payloads/ \
  -H 'Authorization: Token <key>' \
  -H 'Content-Type: application/json' \
  -d '{"fCnt": 100, "devEUI": "abcdabcdabcdabcd", "data": "AQ==", "rxInfo": [{"gatewayID": "1234123412341234", "name": "G1", "time": "2022-07-19T11:00:00", "rssi": -57, "loRaSNR": 10}], "txInfo": {"frequency": 86810000, "dr": 5}}'
```

201 response:

```json
{"id": 1, "devEUI": "abcdabcdabcdabcd", "fCnt": 100, "status": "passing", "decodedHex": "01", "receivedAt": "2022-07-19T11:00:00Z"}
```

Decode rule: `data` is base64, stored verbatim and decoded to hex
(`AQ==` → `01`). If the decoded integer value is 1 the payload is
`passing`, otherwise `failing`; the device's `latest_status` is updated to
match.

Error responses:
- **409** — duplicate `(devEUI, fCnt)`:
  `{"detail": "Duplicate payload: fCnt 100 already recorded for device abcdabcdabcdabcd."}`
- **400** — invalid body (missing fields, malformed base64), DRF field-error format.
- **401** — missing/invalid token.

Behavior notes:
- An unknown `devEUI` auto-registers a Device — there is no provisioning
  flow yet; change the `get_or_create` in `telemetry/views.py` if ingest
  should reject unknown devices.
- `latest_status` reflects the most recently *ingested* payload, not the
  highest `fCnt` — a delayed older frame overwrites a newer status.
- Naive `rxInfo[0].time` values are assumed UTC.

## Running tests

```
docker compose up -d db
docker compose run --rm web python manage.py test telemetry
```

Or on the host (`POSTGRES_PORT` must match your `.env` — 5432 here):

```
cd app && POSTGRES_PORT=5433 python manage.py test telemetry
```

## End-to-end tests

Playwright API tests in `e2e/` exercise the running compose stack over real
HTTP (real token auth, real Postgres). Prerequisite — stack up and migrated:

```
docker compose up -d && docker compose exec web python manage.py migrate
```

Install the test deps into the mise venv (no `playwright install` needed —
the tests are API-only and use no browser):

```
pip install -r e2e/requirements.txt
```

Run from the repo root:

```
pytest e2e/ -v
```

Token provisioning is automatic: the suite creates/reuses an `e2e` user and
its token via `docker compose exec`. Overrides:

- `E2E_BASE_URL` — target base URL (default `http://localhost:8000`)
- `E2E_TOKEN` — use this token verbatim and skip auto-provisioning

## Device Health Monitoring

Beyond basic passing/failing status, the system detects three types of device failures:

### Out-of-Range Detection

When a payload's temperature or humidity readings exceed configured bounds, a
failure is recorded. Resolves automatically when readings return to normal.

**Configuration:**
- Temperature min/max (default: -10°C to 50°C)
- Humidity min/max (default: 0% to 100%)

Triggered on each payload ingest (automatic).

### Inactivity Detection

When a device doesn't send any payload within the configured inactivity window,
a failure is recorded. Resolves when a payload arrives.

**Configuration:**
- `inactivity_window_seconds` (default: 3600 seconds = 1 hour)

Run periodic check:
```bash
docker compose exec web python manage.py check_inactivity
```

Schedule this command to run every 5-10 minutes via cron, Celery, or similar.

### Frequency Anomaly Detection

When the gap between consecutive payloads exceeds 1.5× the expected frequency,
a failure is recorded. Resolves when frequency improves.

**Configuration:**
- `expected_frequency_seconds` (default: 600 seconds)
- Threshold: `expected_frequency × 1.5` (default: 900 seconds)

Triggered on each payload ingest (automatic).

## Health Configuration

Each device has a `DeviceHealthConfig` that stores thresholds. Created automatically
on first use with defaults; customize via:

**API endpoint:**
```
GET/PUT /api/payloads/health-configs/?device_id=<id>
```

**Example:**
```json
{
  "device": 1,
  "inactivity_window_seconds": 3600,
  "temp_min": -10,
  "temp_max": 50,
  "humidity_min": 0,
  "humidity_max": 100,
  "expected_frequency_seconds": 600
}
```

**Django admin:**
Navigate to `/admin/telemetry/devicehealthconfig/` to edit thresholds for any device.

## Device Search & Filter Dashboard

After logging in to the admin panel at `/admin/`, visit the device health dashboard:

```
http://localhost:8000/devices/
```

**Features:**
- **Search** by device dev_eui (substring, case-insensitive)
- **Filter by status** — Passing, Failing, or Unknown
- **Filter by failure type** — Inactivity, Out of Range, or Frequency Anomaly
- **Sort** by device ID, status, or last activity
- **Pagination** with prev/next controls
- **Device detail view** showing active failures and health configuration
- **Responsive design** — works on mobile, tablet, and desktop
- **Light/dark mode** support

Click any device row to see detailed failure information and configuration.

## Device Status API

Query devices and failures via the API:

**List devices:**
```bash
curl -H 'Authorization: Token <key>' \
  'http://localhost:8000/api/payloads/devices/'
```

**Query parameters:**
- `search=device1` — Search by dev_eui (substring)
- `status=passing|failing|unknown` — Filter by status
- `failure_type=inactivity,out_of_range,frequency_anomaly` — Filter by failure types (comma-separated)
- `ordering=dev_eui|-dev_eui|latest_status|-latest_status|updated_at|-updated_at` — Sort results
- `page=2` — Pagination (20 per page)

**Examples:**
```bash
# All failing devices
curl -H 'Authorization: Token <key>' \
  'http://localhost:8000/api/payloads/devices/?status=failing'

# Devices with inactivity failures
curl -H 'Authorization: Token <key>' \
  'http://localhost:8000/api/payloads/devices/?failure_type=inactivity'

# Search and filter combined
curl -H 'Authorization: Token <key>' \
  'http://localhost:8000/api/payloads/devices/?search=kitchen&status=failing&failure_type=out_of_range'
```

**Device detail:**
```bash
curl -H 'Authorization: Token <key>' \
  'http://localhost:8000/api/payloads/devices/<id>/'
```

Response includes active failures with details (timestamps, readings, thresholds).