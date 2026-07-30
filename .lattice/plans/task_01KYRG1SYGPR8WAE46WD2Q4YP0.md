# HDT-5: Add Device and Payload model boilerplate

**Complexity:** medium

## Scope

Declarative scaffolding only, so the human can drop in the endpoint without
fighting the schema:

1. New Django app at `app/telemetry/` (sibling of `app/config/`).
2. `Device` and `Payload` models — fields, choices, constraints, indexes,
   `__str__`. No behaviour.
3. Initial migration, generated and committed.
4. Admin registration for both models.
5. `INSTALLED_APPS` gains `rest_framework` and `telemetry`.

## Out of scope — the human finishes these

Do not write any of this, not even a stub with logic in it:

- base64 -> hex decode of `data`
- the passing/failing rule (`hex == 1` -> passing)
- serializers, views, the DRF endpoint, `urls.py` wiring
- token auth: **do not** add `rest_framework.authtoken` to `INSTALLED_APPS` and
  **do not** add a `REST_FRAMEWORK = {...}` settings dict. `authtoken` ships its
  own migration and its own `Token` table; adding it now would silently commit
  the human to DRF's token model before they've chosen an auth approach. It is a
  one-line addition for them later.
- tests
- any `save()` override, signal, or manager method that mutates
  `Device.latest_status`. That update is the human's call (view, serializer,
  signal, or Celery task — `celery` is already in `requirements.txt`), and
  burying it in `save()` would take the choice away.

`views.py`, `tests.py` etc. as generated empty by `startapp` are fine — leave
them exactly as generated.

## App name: `telemetry`

Rejected alternatives and why:

- `devices` — `Payload` is the higher-volume model of the two; filing it under
  an app named after the other model reads wrong (`devices.models.Payload`).
- `payloads` — same problem mirrored.
- `api` — names the transport, not the domain, and would collide conceptually
  with the human's future endpoint module placement.
- `core` — meaningless; every future thing lands in it.

`telemetry` names the domain (device telemetry ingestion), covers both models
without privileging either, and reads correctly at the import site:
`from telemetry.models import Device, Payload`. Both models stay in one app so
the FK is intra-app and there is no migration dependency ordering to manage.

Path: `app/telemetry/` — must be next to `config/`, because `app/` is the
Docker `WORKDIR` and the only thing on `sys.path`.

## Field naming: snake_case in the model, camelCase mapped in the serializer

The wire format is camelCase (`fCnt`, `devEUI`, `rxInfo`, `txInfo`). The models
use snake_case (`f_cnt`, `dev_eui`, `rx_info`, `tx_info`).

Rationale: Django/PEP 8 convention, and camelCase attributes break every reader's
expectations in the ORM, admin, and shell (`Device.objects.filter(devEUI=...)`
looks like a bug). The wire format is a *transport* concern and belongs in the
serializer, which the human is writing anyway — `serializers.IntegerField(source='f_cnt')`
under the wire name, one line per renamed field, and only 4 fields need it.
Do not add a camel-case dependency (`djangorestframework-camel-case`) — no new
requirements in this task.

`data` keeps its wire name because it is already snake-case-clean; renaming it to
`raw_data` would add a mapping for no readability gain. Note this consistency
rule in a comment so the human doesn't "fix" it.

## Models

Put a single shared `TextChoices` class in `telemetry/models.py`, module level,
above both models. Both `Device.latest_status` and `Payload.status` reference it
(DRY — one source of truth for the vocabulary, and the human's decode logic
imports the same symbol). A separate `choices.py`/`constants.py` is not worth the
indirection for a two-model app; `from telemetry.models import Status` is fine.

```python
class Status(models.TextChoices):
    PASSING = 'passing', 'Passing'
    FAILING = 'failing', 'Failing'
    UNKNOWN = 'unknown', 'Unknown'
```

`UNKNOWN` exists so a `Device` can be created by the first inbound payload
*before* anything has been decoded, and so a `Payload` row can be persisted
before (or despite a failure in) the decode step. Without it the implementation
would be forced to either decode inside `save()` or make the field nullable —
both worse.

### Device

| Field | Definition | Why |
|---|---|---|
| `dev_eui` | `CharField(max_length=16, unique=True)` | The natural key — PROMPT links Payload to Device *through* devEUI. 16 hex chars per the LoRaWAN EUI-64 and the PROMPT example. `unique=True` gives the lookup index for free, so no extra `db_index`. Kept as its own field with a plain `BigAutoField` pk rather than `primary_key=True`, so the FK column stays 8 bytes and a devEUI correction doesn't cascade. |
| `latest_status` | `CharField(max_length=16, choices=Status.choices, default=Status.UNKNOWN)` | PROMPT: "Each Device should keep track of their latest status value". Not nullable — `UNKNOWN` carries that meaning. `max_length=16` rather than the exact 7: varchar headroom is free in Postgres and saves a migration if the human adds a longer value. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Audit. |
| `updated_at` | `DateTimeField(auto_now=True)` | Cheap "last touched" signal; `auto_now` is field config, not business logic. |

No `RegexValidator` on `dev_eui`. Considered and deliberately rejected: model
validators propagate into `ModelSerializer`, so it would inject validation
behaviour the human didn't write, surfacing as an error shape they didn't choose
(and rejecting their own short test fixtures). Leave a comment naming it as the
seam instead.

Also rejected: `name`, `last_seen_at`. Neither appears in PROMPT (`rxInfo[].name`
is the *gateway* name, not the device), and speculative columns are the thing
that causes migration churn.

`__str__` returns `self.dev_eui`.

### Payload

| Field | Definition | Why |
|---|---|---|
| `device` | `ForeignKey('Device', on_delete=models.CASCADE, related_name='payloads')` | `CASCADE`: a payload has no meaning without its device; this is an append-only ingest log, not a ledger. `related_name='payloads'` makes `device.payloads.latest(...)` read well for whoever implements the status update. |
| `f_cnt` | `PositiveBigIntegerField()` | **Not** `PositiveIntegerField` — that maps to Postgres `integer` (max 2147483647), while a LoRaWAN frame counter is 32-bit unsigned (max 4294967295). A device near the top of its counter range would fail to insert. `PositiveBigIntegerField` covers it and keeps the `>= 0` check constraint. |
| `data` | `TextField()` | The base64 string exactly as received, kept verbatim so the decode is re-runnable and debuggable. `TextField` over `CharField` because payload length varies and Postgres stores both identically — a guessed `max_length` would just be a future migration. |
| `decoded_hex` | `CharField(max_length=64, blank=True, default='')` | The human's decode output. `blank=True, default=''` (not `null=True`) per Django's don't-use-NULL-on-string-fields convention — one empty state, not two. Optional so a row can be written before the decode exists: **this is the field the human fills in, and it must not require a migration to start using.** |
| `status` | `CharField(max_length=16, choices=Status.choices, default=Status.UNKNOWN)` | Per-payload passing/failing verdict. Defaults to `UNKNOWN` so persistence and decode are independently orderable. |
| `rx_info` | `JSONField(default=list, blank=True)` | `rxInfo` is a *list* of gateway dicts. `default=list` — the callable, never a mutable `[]` literal. Stored whole rather than normalised into a Gateway model: out of scope, and PROMPT never queries it. |
| `tx_info` | `JSONField(default=dict, blank=True)` | `txInfo` is a single dict (`frequency`, `dr`). Same reasoning. |
| `received_at` | `DateTimeField(null=True, blank=True)` | Device/gateway-reported time. Nullable **on purpose**: the PROMPT payload has no top-level timestamp — the only time present is `rxInfo[0].time`, and extracting it is the human's parsing work. Nullable now means they can populate it later with zero schema change. |
| `created_at` | `DateTimeField(auto_now_add=True)` | Server ingest time. Deliberately distinct from `received_at`, which is what the device claims. |

`__str__` returns something like `f'{self.device.dev_eui} fCnt={self.f_cnt}'`
(admin uses `list_select_related` so this doesn't N+1).

### Meta

```python
class Meta:
    ordering = ('-created_at',)
    constraints = [
        models.UniqueConstraint(
            fields=('device', 'f_cnt'), name='unique_device_f_cnt'
        ),
    ]
    indexes = [
        models.Index(
            fields=('device', '-created_at'), name='payload_device_recent_idx'
        ),
    ]
```

**The duplicate-detection constraint.** PROMPT: "The fCnt field on the payload
object should be used to ensure that it is not a duplicate message." `fCnt` is
scoped *per device* — two different devices legitimately both send `fCnt: 100` —
so the constraint is on the pair `(device, f_cnt)`, never on `f_cnt` alone. A DB
constraint (rather than only a serializer check) is the right floor: it holds
under concurrent POSTs of the same message, which a read-then-write check in the
view does not.

**Seam left for the human, and it must be commented in the model:** a LoRaWAN
frame counter is not unique per device forever — it resets to 0 when the device
rejoins the network (new session) and wraps at its width. So this constraint will
eventually reject a *legitimate* post-reset payload as a duplicate. That is an
acceptable, explicit simplification for this exercise, and the human has two
escape hatches without a redesign: add a session/epoch column to the
constraint's `fields`, or catch `IntegrityError` in the view and answer
`200`/`409` deliberately instead of letting it 500. Say this in a comment so the
next reader knows it was a decision, not an oversight.

**Index choice.** `unique_device_f_cnt` already creates a btree on
`(device, f_cnt)`, which serves the duplicate lookup — no separate index needed
for it. The one query the feature actually needs and that constraint does *not*
serve is "most recent payload for this device" (how `Device.latest_status` gets
maintained), hence the `(device, -created_at)` composite. Skipping: an index on
`status` (two-value column, useless selectivity) and on `received_at` (nothing
queries it yet). `ordering = ('-created_at',)` gives the admin and any listing a
sane recent-first default.

`Device` needs no explicit `Meta` indexes — `unique=True` on `dev_eui` covers its
only lookup.

## Settings

Add to `INSTALLED_APPS` in `app/config/settings.py`, third-party then local:

```python
    # DRF is the seam for the payload ingest endpoint (see PROMPT.md); the
    # endpoint itself is not built here. djangorestframework is already pinned
    # in requirements.txt.
    'rest_framework',

    'telemetry',
```

Match the file's existing style: single quotes, and comments that say *why*
rather than restating the code (see the `ALLOWED_HOSTS` and `DATABASES` comments
already in that file).

`DEFAULT_AUTO_FIELD` is **not** needed: Django 6.0's global default is already
`django.db.models.BigAutoField` (verified against the installed 6.0.7), so there
are no `models.W042` warnings. Keep whatever `default_auto_field` line `startapp`
writes into `telemetry/apps.py` — it's redundant but it is the generated
boilerplate and removing it is noise.

**Do not touch the unrelated whitespace-only change already uncommitted in
`app/config/settings.py`** (two blank lines removed around the `DATABASES`
block). It isn't yours; leave it exactly as it is and only add the two
`INSTALLED_APPS` entries.

## Admin

`app/telemetry/admin.py`, using the `@admin.register` decorator form:

- `DeviceAdmin`: `list_display = ('dev_eui', 'latest_status', 'updated_at', 'created_at')`,
  `list_filter = ('latest_status',)`, `search_fields = ('dev_eui',)`,
  `readonly_fields = ('created_at', 'updated_at')`.
  `search_fields` is load-bearing — `PayloadAdmin.autocomplete_fields` requires it.
- `PayloadAdmin`: `list_display = ('device', 'f_cnt', 'status', 'decoded_hex', 'received_at', 'created_at')`,
  `list_filter = ('status',)`, `search_fields = ('device__dev_eui',)`,
  `list_select_related = ('device',)` (kills the N+1 from rendering `device` in
  `list_display`), `autocomplete_fields = ('device',)` (a plain FK dropdown
  renders every device on the add form), `readonly_fields = ('created_at',)`.

## Migration

`makemigrations` does **not** require a live Postgres. It builds state from disk;
its only DB touch is `check_consistent_history()`, which is wrapped in a
try/except and degrades to a printed warning when the connection fails. So this
runs against the local `.venv` with the DB down — an "error checking a consistent
migration history" warning in that case is benign.

Commands must run from `app/` (that's where `manage.py` lives and what
`config.settings` assumes). Use the **absolute** venv interpreter path — a
relative `../.venv/bin/python` produces `RuntimeWarning: Unexpected value in
sys.prefix` noise:

```bash
cd /Users/forrest/Code/hexmodal-django-test/app
/Users/forrest/Code/hexmodal-django-test/.venv/bin/python manage.py startapp telemetry
/Users/forrest/Code/hexmodal-django-test/.venv/bin/python manage.py makemigrations telemetry
```

No env vars needed: `manage.py` sets `DJANGO_SETTINGS_MODULE`, and the
`POSTGRES_*` / `DJANGO_ALLOWED_HOSTS` settings all have working defaults.
(`mise` also auto-activates `.venv`, so a bare `python manage.py ...` works in an
interactive shell — the absolute path is for non-interactive tool calls.)

Verified present: `.venv/bin/django-admin`, and the venv has Django 6.0.7, DRF
3.17.1, psycopg 3.3.4 installed.

The generated `app/telemetry/migrations/0001_initial.py` **must be committed** —
compose runs `runserver`, not `migrate`, so an uncommitted migration means the
next person's `manage.py migrate` invents its own.

## File-by-file change list

| File | Change |
|---|---|
| `app/telemetry/__init__.py` | new, empty (from `startapp`) |
| `app/telemetry/apps.py` | new, as generated (`TelemetryConfig`) |
| `app/telemetry/models.py` | `Status` TextChoices, `Device`, `Payload` |
| `app/telemetry/admin.py` | register both models |
| `app/telemetry/migrations/__init__.py` | new, empty |
| `app/telemetry/migrations/0001_initial.py` | generated, committed |
| `app/telemetry/views.py`, `tests.py` | new, left exactly as generated (empty) |
| `app/config/settings.py` | `+'rest_framework'`, `+'telemetry'` in `INSTALLED_APPS` only |

Not touched: `app/requirements.txt` (DRF already pinned), `app/config/urls.py`,
`docker-compose.yml`, `README.md`.

## Acceptance criteria

All commands run from `/Users/forrest/Code/hexmodal-django-test/app` with
`PY=/Users/forrest/Code/hexmodal-django-test/.venv/bin/python`.

1. `$PY manage.py check` → `System check identified no issues`, exit 0.
2. `$PY manage.py makemigrations --check --dry-run` → `No changes detected`,
   exit 0. This is the real test that the committed migration matches the models.
3. `app/telemetry/migrations/0001_initial.py` exists, is tracked by git, and
   contains: `CreateModel` for `Device` and `Payload`, the
   `UniqueConstraint` named `unique_device_f_cnt` over `('device', 'f_cnt')`, and
   the `payload_device_recent_idx` index.
4. Models and choices import cleanly:
   `$PY -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from telemetry.models import Device, Payload, Status; print(Status.choices)"`
   prints all three of passing/failing/unknown.
5. `INSTALLED_APPS` contains `rest_framework` and `telemetry`. It does **not**
   contain `rest_framework.authtoken`, and no `REST_FRAMEWORK` dict was added.
6. No business logic:
   `grep -n 'def save\|b64\|base64\|def clean' app/telemetry/*.py` finds nothing.
   No serializer, no view body, no URL route, no test added.
7. `app/requirements.txt` unchanged; no new dependency anywhere.
8. `f_cnt` is `PositiveBigIntegerField`, not `PositiveIntegerField` — confirm this
   one specifically, it is the easiest field to get wrong.
9. Style matches the repo: single quotes throughout, comments explain *why*. The
   two intentional seams — the `(device, f_cnt)` reset/wrap caveat and the absent
   `dev_eui` format validator — are commented in `models.py`, not left implicit.
10. The pre-existing whitespace-only diff in `app/config/settings.py` is still
    present and unreverted.

Optional, not required (needs Docker up): `docker compose up -d db` then
`$PY manage.py migrate` applies cleanly against Postgres.
