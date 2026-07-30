# HDT-8: Add Playwright end-to-end tests against the running compose stack

## Scope

Black-box e2e tests that hit the real compose stack (web on
`http://localhost:8000` + Postgres + DRF token auth) over real HTTP,
verifying PROMPT.md behavior end to end. No application code changes.
Re-runnable forever against a persistent DB.

## Decisions

### Runner: Python Playwright, plain `playwright` package + `pytest` (no pytest-playwright)

- The repo is Python-only (mise-managed Python 3.14 venv, Django, no
  package.json). Node Playwright would introduce a second toolchain for zero
  benefit — rejected.
- These are pure API tests. Playwright's **APIRequestContext**
  (`playwright.sync_api.sync_playwright` → `p.request.new_context(...)`)
  needs **no browsers**: do NOT run `playwright install`, no browser download,
  no `page`/`browser` fixtures.
- `pytest-playwright` was weighed and rejected: its value is browser/page
  fixtures, `--headed`, tracing, `--base-url` plumbing (via pytest-base-url +
  python-slugify deps). For an APIRequestContext-only suite that's dead
  weight; the two fixtures we need are ~20 lines of conftest. Keeps the
  footprint honest for a repo whose only test infra is Django's runner.
- **Verified on this machine**: `pip install --dry-run playwright pytest`
  resolves cleanly on the venv's Python 3.14.6 → playwright 1.61.0,
  greenlet 3.5.4, pyee 13.0.1, pytest 9.1.1. No 3.14 compatibility risk.

### Layout: top-level `e2e/` directory

Dev-only deps must NOT go into `app/requirements.txt` — the Dockerfile
(`app/Dockerfile`, build context `./app`) does `COPY requirements.txt` +
`pip install -r`, so anything added there ships in the app image. A repo-root
`e2e/` directory is outside the build context entirely; the image cannot
change.

```
e2e/
  requirements.txt   # playwright, pytest (pin the resolved versions)
  conftest.py        # fixtures below
  test_ingest.py     # the 8 tests
```

No pytest.ini/pyproject needed; run as `pytest e2e/ -v` from the repo root
(or `pytest -v` inside `e2e/`). Install into the existing mise venv:
`pip install -r e2e/requirements.txt`.

### conftest.py fixtures

- `base_url` (session): `os.environ.get("E2E_BASE_URL", "http://localhost:8000")`.
- `compose_exec` helper: runs
  `docker compose exec -T web python manage.py ...` via `subprocess.run`
  from the repo root (derive root as `Path(__file__).parent.parent` so cwd
  doesn't matter).
- `auth_token` (session): token provisioning, see below. If `E2E_TOKEN` is
  set in the env, use it verbatim and skip provisioning (decouples from
  compose for anyone pointing at a remote stack).
- `api` (session): authenticated `APIRequestContext` —
  `p.request.new_context(base_url=base_url, extra_http_headers={"Authorization": f"Token {token}"})`,
  disposed at session end.
- `anon_api` (session): unauthenticated context for the 401 tests (plus a
  per-test wrong-token context built inline).
- `fresh_dev_eui` (function): `uuid.uuid4().hex[:16]` — 16 lowercase hex
  chars, matches `dev_eui = CharField(max_length=16)`; a fresh EUI per test
  per run is what makes the suite re-runnable against a persistent DB with
  no cleanup.
- **Fail-fast reachability check** (session, autouse or folded into `api`):
  before any test, `POST {base_url}/api/payloads/` with no auth must answer
  HTTP 401 (any HTTP answer proves the stack is up). On connection error,
  `pytest.exit()` with:
  `"API not reachable at {base_url}. Start the stack first: docker compose up -d && docker compose exec web python manage.py migrate"`.
  Do NOT have pytest orchestrate compose — fragile and slow; assume the
  stack is already up.

### Token provisioning: option (a) — `docker compose exec` shell one-liner, no app code

Chosen over a management command. Rationale: a `manage.py e2e_token` command
would live in `app/telemetry/management/` and therefore ship in the
production image — a token-minting command baked into the deployable
artifact is worse than test-side coupling to compose (which the e2e suite
already requires by definition). Option (c) (require the human to export
E2E_TOKEN) fails the "non-interactive, automatic" requirement — kept only as
an override.

Implementation (session fixture, subprocess):

```
docker compose exec -T web python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
u, _ = get_user_model().objects.get_or_create(username='e2e')
t, _ = Token.objects.get_or_create(user=u)
print(t.key)
"
```

Idempotent (both `get_or_create`s), non-interactive, prints only the key —
fixture takes `stdout.strip().splitlines()[-1]`. On non-zero exit,
`pytest.exit()` with the captured stderr and the same "start the stack"
hint.

### Observing the `latest_status` flip

The API has no GET endpoint. Options considered:

1. Assert via the second POST's 201 body only — weakest: `status` in the 201
   body is the *payload's* status, computed pre-save; it does not prove the
   Device row flipped.
2. Add a GET endpoint — rejected, new API surface out of scope.
3. Read `Device.latest_status` through
   `docker compose exec -T web python manage.py shell -c` — **chosen**. It
   reads the real Postgres row via the running app, driven externally from
   the test host, and reuses the exact mechanism token provisioning already
   uses. Strongest externally-observable assertion without new surface.

Helper in conftest: `get_device_status(dev_eui)` → runs
`shell -c "from telemetry.models import Device; print(Device.objects.get(dev_eui='<eui>').latest_status)"`
(EUI is fixture-generated hex, so interpolation is safe) and returns the
last stdout line.

### Test cases (`e2e/test_ingest.py`, 8 tests)

All POSTs go to `/api/payloads/` with `Content-Type: application/json`.
`BODY(dev_eui, f_cnt=100, data="AQ==")` helper builds the PROMPT.md example
body (rxInfo with `"time": "2022-07-19T11:00:00"`, txInfo) with the fields
swapped in.

1. **Happy path**: PROMPT.md example body with a fresh devEUI → 201. Assert
   the full camelCase response shape: `id` (int), `devEUI` == sent,
   `fCnt` == 100, `status` == `"passing"`, `decodedHex` == `"01"`,
   `receivedAt` == `"2022-07-19T11:00:00Z"` (naive rxInfo time assumed UTC,
   DRF renders trailing-Z).
2. **Duplicate devEUI+fCnt** → second identical POST answers 409 with
   `detail` == `"Duplicate payload: fCnt 100 already recorded for device <eui>."`.
3. **Same fCnt, different devEUI** → 201 (dedupe is per-device).
4. **Status flip**: POST `data="AA=="` (fCnt 1) to a fresh device → 201 with
   `status` == `"failing"`; `get_device_status(eui)` == `"failing"`. Then
   POST `data="AQ=="` fCnt 2 same device → 201 `"passing"`;
   `get_device_status(eui)` == `"passing"`. Proves the Device row flip in
   Postgres, not just the payload status.
5. **No token** → 401 (`anon_api`), body has `detail`.
6. **Wrong token** → 401 (context with `Authorization: Token <garbage>`).
7. **Malformed base64** (`data="!!!not-base64!!!"`) → 400 with DRF
   field-error shape: `{"data": ["Not valid base64."]}`.
8. **fCnt overflow** (`fCnt = 2**63`) → 400 with a `fCnt` field error —
   regression pin from the HDT-7 review (bigint bound in
   `PayloadIngestSerializer`).

Re-runnability: every test uses fresh `uuid4`-derived devEUIs; no test
depends on cleanup; the `e2e` user/token get_or_create is idempotent.

### README: new "End-to-end tests" section

After "Running tests". Content:

- Prerequisites: stack up + migrated —
  `docker compose up -d && docker compose exec web python manage.py migrate`.
  Nothing else; token provisioning is automatic (creates/reuses an `e2e`
  user + token via `docker compose exec`).
- Setup: `pip install -r e2e/requirements.txt` (into the mise venv; no
  `playwright install` needed — API-only tests use no browser).
- Run: `pytest e2e/ -v`.
- Overrides: `E2E_BASE_URL` (default `http://localhost:8000`), `E2E_TOKEN`
  (skip auto-provisioning).

## File-by-file change list

| File | Change |
|------|--------|
| `e2e/requirements.txt` | new — pinned `playwright==1.61.0`, `pytest==9.1.1` |
| `e2e/conftest.py` | new — fixtures: base_url, auth_token (compose-exec provisioning + E2E_TOKEN override), api/anon_api contexts, fresh_dev_eui, reachability fail-fast, get_device_status helper |
| `e2e/test_ingest.py` | new — the 8 tests above |
| `README.md` | new "End-to-end tests" section |
| `.lattice/` | task/plan/event updates committed with the work |

Explicitly unchanged: `app/requirements.txt`, `app/Dockerfile`, everything
under `app/` (no migrations, no management commands, no settings).

## Acceptance criteria (cold reviewer, runnable)

1. From repo root with the venv active: `pip install -r e2e/requirements.txt`
   succeeds on Python 3.14; **no** `playwright install` step anywhere.
2. `docker compose up -d` + `docker compose exec web python manage.py migrate`,
   then `pytest e2e/ -v` → **8 tests, all passing**.
3. Immediately re-run `pytest e2e/ -v` with no cleanup → **8/8 passing again**
   (re-runnability against the persistent DB proven).
4. With the stack down (`docker compose down`), `pytest e2e/ -v` fails fast
   with the "API not reachable … docker compose up" message — no hangs, no
   tracebacks-as-UX.
5. `git diff` shows no changes under `app/` — image contents unchanged,
   `app/requirements.txt` untouched; `docker compose exec web python manage.py check`
   still clean.
6. README documents prerequisites, install, run command, and the two env
   overrides.
