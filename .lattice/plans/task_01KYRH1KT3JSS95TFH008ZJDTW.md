# Plan: HDT-7 — Payload ingest endpoint with fCnt dedupe and base64 decode

Task: task_01KYRH1KT3JSS95TFH008ZJDTW
Complexity: medium

## Scope

One POST endpoint (`POST /api/payloads/`) that ingests the PROMPT.md payload shape,
persists it, decodes `data` (base64 → hex → integer), marks the payload
passing/failing, and updates `Device.latest_status`. Plus serializer, URLs, tests,
and README documentation. No model changes, no new migrations.

Decisions inherited from the task description (not re-litigated here): camelCase→
snake_case via serializer `source=`; `get_or_create` for unknown devEUI; duplicate
fCnt → 409 with IntegrityError handled; persist-then-decode ordering; raw base64
kept verbatim in `Payload.data` with hex in `decoded_hex`; `received_at` from
`rxInfo[0].time`.

## Serializer design — `app/telemetry/serializers.py` (new)

**`PayloadIngestSerializer(serializers.Serializer)` — a plain Serializer, not a
ModelSerializer.** Justification:

- Nearly every field needs a `source=` rename and `devEUI` is not a `Payload`
  model field at all (it resolves to a `device` FK), so ModelSerializer's field
  introspection buys almost nothing — we'd redeclare everything anyway.
- The HDT-5 review noted a ModelSerializer would inherit a
  `UniqueTogetherValidator` from the `(device, f_cnt)` constraint, but only if
  `device` were a serializer field — it isn't (we take `devEUI`), so the
  validator would either not attach or attach wrongly. A plain Serializer removes
  the ambiguity.
- **The duplicate check lives in the DB constraint alone**: the view catches
  `IntegrityError` → 409. Do NOT add a serializer-level uniqueness query
  (`Payload.objects.filter(device=..., f_cnt=...).exists()`): it races — two
  concurrent POSTs of the same frame both pass the check and one still hits the
  constraint, so the IntegrityError path must exist regardless. A pre-check adds
  a query and a false sense of safety without removing any code.

Declared fields (wire name = field name, `source=` maps to internal name):

| Wire field | Declaration | Notes |
|---|---|---|
| `fCnt` | `IntegerField(source='f_cnt', min_value=0)` | required; min_value=0 matches PositiveBigIntegerField |
| `devEUI` | `CharField(source='dev_eui', max_length=16)` | required; max_length matches the model column so the DB can't reject it. No hex-format validation — the model deliberately left format policy open, and being permissive here keeps ingest tolerant; note this in a comment. |
| `data` | `CharField()` | required, `allow_blank=False` (default) so `data: ""` → 400 |
| `rxInfo` | `ListField(source='rx_info', required=False, default=list)` | ListField (not JSONField) so a non-list body is a 400 — we index `[0]` later |
| `txInfo` | `DictField(source='tx_info', required=False, default=dict)` | |

**base64 validation** — `validate_data(self, value)`:
- `base64.b64decode(value, validate=True)` inside try/except
  `(binascii.Error, ValueError)` → `serializers.ValidationError` → DRF 400.
- Reject decoded payloads longer than 32 bytes (`decoded_hex` is
  `CharField(max_length=64)`; without this check an oversized payload becomes a
  Postgres DataError/500 instead of a 400).
- Empty decoded bytes can only come from `data: ""`, which `allow_blank=False`
  already rejects, so no separate empty-bytes branch is needed — but the decode
  helper still guards `b''` defensively (treated as failing) so it stays a total
  function.

Serializer is validation + field mapping only. `received_at` extraction and all
persistence happen in the view/service layer (below), so `serializer.validated_data`
comes out as `{'f_cnt', 'dev_eui', 'data', 'rx_info', 'tx_info'}`.

## Decode + status + received_at logic — `app/telemetry/services.py` (new)

Pure functions, no ORM — models stay thin (HDT-5 decision), and pure functions are
trivially unit-testable. NOT in `model.save()`.

**`decode_payload(data_b64: str) -> tuple[str, str]`** returns `(decoded_hex, status)`:
1. `raw = base64.b64decode(data_b64)` (already validated upstream).
2. `decoded_hex = raw.hex()` — lowercase, **no `0x` prefix**: `'AQ==' → '01'`.
3. `value = int.from_bytes(raw, 'big')` (returns 0 for `b''`).
4. `status = Status.PASSING if value == 1 else Status.FAILING`.

**Multi-byte decision: integer comparison, so leading zero bytes still pass.**
`b'\x01'` → 1 → passing, and `b'\x00\x01'` (`'AAE='`) → 1 → passing.
Justification: PROMPT.md says "if the **value** of the data is 1" — value
semantics, not byte-pattern semantics. `int.from_bytes` is the natural reading of
a big-endian sensor word, and a device that widens its payload from 1 to 2 bytes
keeps working. A test pins this behavior.

**`extract_received_at(rx_info: list) -> datetime | None`**:
- Return `None` (never an error) when `rx_info` is empty, `rx_info[0]` is not a
  dict, `time` is absent, or the string doesn't parse. Missing gateway time is a
  data condition, not a client error.
- Parse with `django.utils.dateparse.parse_datetime`.
- **Naive-datetime handling**: the PROMPT example `'2022-07-19T11:00:00'` is
  naive and `USE_TZ=True`, so storing it as-is raises a `RuntimeWarning` and
  guesses. If the parsed datetime is naive, make it aware **assuming UTC**
  (`dt.replace(tzinfo=datetime.timezone.utc)` /
  `timezone.make_aware(dt, datetime.timezone.utc)`); gateway timestamps are
  conventionally UTC and the project's `TIME_ZONE` is UTC. Aware inputs
  (`...Z`, `+02:00`) pass through untouched.

## View design — `app/telemetry/views.py` (rewrite)

**`PayloadIngestView(APIView)`, POST only.** Justification vs alternatives:
- `generics.CreateAPIView` wants `serializer.save()` to be the whole story and
  returns `serializer.data` — our response includes server-computed fields
  (`id`, `status`, `decodedHex`) not in the input serializer, and we need the
  IntegrityError→409 wrap around the atomic block. Bending CreateAPIView's hooks
  (`perform_create` + a second read-serializer) is more machinery than a 25-line
  `post()`.
- `@api_view` works but gives up the class seam for no gain.
- No per-view `authentication_classes`/`permission_classes` — HDT-6's global
  defaults (`TokenAuthentication` + `IsAuthenticated`) apply; unauthenticated
  requests get 401 with no code here.

`post()` flow:
1. `serializer.is_valid(raise_exception=True)` → DRF default 400 body on failure.
2. Compute `decoded_hex, status = decode_payload(...)` and
   `received_at = extract_received_at(...)` (pure, pre-transaction).
3. ```
   try:
       with transaction.atomic():
           device, _ = Device.objects.get_or_create(dev_eui=...)
           payload = Payload.objects.create(device, f_cnt, data, rx_info,
                                            tx_info, received_at)   # status='unknown'
           payload.decoded_hex = decoded_hex; payload.status = status
           payload.save(update_fields=['decoded_hex', 'status'])
           device.latest_status = status
           device.save(update_fields=['latest_status', 'updated_at'])
   except IntegrityError:
       return 409
   ```
   - **`except IntegrityError` sits OUTSIDE `transaction.atomic()`** — catching
     inside a broken atomic block raises `TransactionManagementError` on the next
     query. This is the load-bearing detail of the 409 path.
   - Create-then-update honors the persist-then-decode ordering decision (the
     row exists with `status='unknown'` before decode results are applied) while
     keeping everything in one transaction so no `unknown` state is ever visible
     to other transactions and a failure rolls back cleanly.
   - `get_or_create` is safe inside the outer atomic: Django wraps its inner
     create in a savepoint, so a concurrent-registration IntegrityError on
     `dev_eui` is retried as a get without poisoning the transaction.
   - `device.save(update_fields=...)` (not queryset `.update()`) so `auto_now`
     still touches `updated_at`.
4. Responses (camelCase, matching the wire format):
   - **201**: `{"id", "devEUI", "fCnt", "status", "decodedHex", "receivedAt"}` —
     hand-built dict; a second serializer for six keys is overkill.
   - **409**: `{"detail": "Duplicate payload: fCnt <n> already recorded for device <devEUI>."}`
   - **400**: DRF default field-error body (from `raise_exception=True`).
   - **401**: DRF default `{"detail": "Authentication credentials were not provided."}` (global config, nothing to write).

**Concurrency/ordering note (documented, not solved):** `latest_status` means
"status of the most recently *ingested* payload". A delayed older frame (lower
fCnt arriving late) will overwrite a newer status. Fixing this needs fCnt- or
received_at-guarded updates and a policy for resets — out of scope; record the
simplification in a code comment and the README.

## URLs

- **`app/telemetry/urls.py` (new)**: `app_name = 'telemetry'`;
  `path('', PayloadIngestView.as_view(), name='payload-ingest')`.
- **`app/config/urls.py`**: add `path('api/payloads/', include('telemetry.urls'))`.
- Endpoint: **`POST /api/payloads/`**. Resource-noun path leaves room for sibling
  routes (`api/devices/`) later; POST-only because the view defines only `post`
  (anything else → 405).
- Tests use `reverse('telemetry:payload-ingest')`.

## Tests — `app/telemetry/tests.py` (rewrite)

Use `rest_framework.test.APITestCase`. Shared `setUp`: create a `User`, a
`Token`, and call `self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')`;
keep the PROMPT.md example body as a helper that returns a fresh dict.

Cases (each is one test method):
1. **Happy path, exact PROMPT.md example** → 201; one `Payload` row with
   `data == 'AQ=='` (verbatim), `decoded_hex == '01'`, `status == 'passing'`,
   `f_cnt == 100`; `Device` auto-created with `dev_eui == 'abcdabcdabcdabcd'`
   and `latest_status == 'passing'`; response body has `devEUI`, `fCnt`,
   `status`, `decodedHex`, `id`.
2. **received_at parsed from rxInfo[0].time** → stored `received_at ==
   datetime(2022, 7, 19, 11, 0, 0, tzinfo=utc)` (asserts the assume-UTC rule).
3. **Empty rxInfo list** (`"rxInfo": []`) → 201, `received_at is None`.
4. **Duplicate fCnt, same device** → second POST returns 409 with `detail`;
   `Payload.objects.count() == 1`; device `latest_status` unchanged.
5. **Same fCnt, different device** → 201; two payload rows; two devices.
6. **Failing value**: `data == 'AA=='` → 201, `decoded_hex == '00'`,
   payload `failing`, device `latest_status == 'failing'`.
7. **Multi-byte value 1**: `data == 'AAE='` (`b'\x00\x01'`) → 201,
   `decoded_hex == '0001'`, status `passing` (pins the integer-comparison rule).
8. **Malformed base64** (`data == '!!!not-base64!!!'`) → 400, no rows created.
9. **Missing required field** (omit `data`; optionally also `fCnt`) → 400.
10. **Unauthenticated** → `self.client.credentials()` cleared, POST → 401, no rows.
11. **Existing device reused**: two POSTs, same devEUI, fCnt 100 then 101 →
    201 both, `Device.objects.count() == 1`, `latest_status` follows the second.

**How tests run (DB required):** tests hit a real Postgres; Django creates/drops
the test database (`test_hexmodal`) and the compose `hexmodal` user is a
superuser inside the postgres image, so no extra grants needed. Canonical
command (works with only the db service up):

```
docker compose up -d db
docker compose run --rm web python manage.py test telemetry
```

(`docker compose exec web ...` also works when the web service is already up.)
Running on the host instead: this repo's `.env` maps Postgres to host port 5432, so it's
`cd app && POSTGRES_PORT=5432 python manage.py test telemetry` with the repo's
`.venv`/mise environment active. Put the compose variant in the README as the
supported path.

## README

Add under the existing `## API authentication` section (keep its `<!-- AI -->`
region style):
- **`## Payload ingest`**: endpoint `POST /api/payloads/`; full working curl:
  `curl -s -X POST http://localhost:8000/api/payloads/ -H 'Authorization: Token <key>' -H 'Content-Type: application/json' -d '<exact PROMPT.md example JSON>'`;
  the 201 response body; decode rule (base64 → hex, integer value 1 ⇒ passing,
  else failing); 409 on duplicate `(devEUI, fCnt)` with example body; 400/401
  one-liners.
- Behavior notes: unknown devEUI auto-registers a Device (no provisioning flow
  yet — change here if ingest should reject unknown devices);
  `latest_status` reflects the most recently ingested payload, not the highest
  fCnt; naive `rxInfo[0].time` values are assumed UTC.
- **`## Running tests`**: the two commands from the Tests section above.

## File-by-file change list

| File | Change |
|---|---|
| `app/telemetry/serializers.py` | NEW — `PayloadIngestSerializer` (plain Serializer, camelCase→snake via `source=`, base64 + length validation) |
| `app/telemetry/services.py` | NEW — `decode_payload()`, `extract_received_at()` (pure functions) |
| `app/telemetry/views.py` | REWRITE — `PayloadIngestView(APIView)` with atomic persist-then-decode flow, IntegrityError→409 |
| `app/telemetry/urls.py` | NEW — `app_name='telemetry'`, named route `payload-ingest` |
| `app/config/urls.py` | EDIT — `include('telemetry.urls')` under `api/payloads/` |
| `app/telemetry/tests.py` | REWRITE — 11 APITestCase methods above |
| `README.md` | EDIT — payload-ingest docs + running-tests section |

No changes to models, migrations, settings, requirements, or docker-compose.

## Acceptance criteria

**DB-optional (reviewer without Postgres running):**
1. `cd app && python manage.py check` → "System check identified no issues".
2. `cd app && python manage.py makemigrations --check --dry-run` → "No changes
   detected" (this task must not generate migrations; neither command needs a
   live DB connection).
3. Code review: no uniqueness pre-check query in the serializer; IntegrityError
   caught outside the atomic block; no business logic in model `save()`;
   `Payload.data` stored verbatim.

**DB-required (compose db up):**
4. `docker compose up -d db && docker compose run --rm web python manage.py test telemetry`
   → all tests pass (expected: 11 tests, OK).
5. Manual curl flow (optional, needs `docker compose up` + a token per README):
   PROMPT.md body → 201 with `"decodedHex": "01"`, `"status": "passing"`;
   repeat same body → 409; `data: "AA=="` with new fCnt → `"status": "failing"`;
   no token → 401.
