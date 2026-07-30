# HDT-4: Wire ALLOWED_HOSTS to DJANGO_ALLOWED_HOSTS env var

**Complexity:** low

## Symptom

`DisallowedHost at /` — `Invalid HTTP_HOST header: '0.0.0.0:8000'` when browsing
to `http://0.0.0.0:8000/`.

## Cause

`app/config/settings.py` has `ALLOWED_HOSTS = []` and ignores the
`DJANGO_ALLOWED_HOSTS` var that `docker-compose.yml` injects
(`localhost,127.0.0.1,0.0.0.0`).

With `DEBUG=True`, Django substitutes `['localhost', '127.0.0.1', '[::1]']` when
`ALLOWED_HOSTS` is empty — `0.0.0.0` is deliberately NOT in that list. This is
why the earlier HDT-3 verification passed: it curled `127.0.0.1`, which the
implicit list covers.

## Approach

Parse the comma-separated env var, matching the `os.environ.get` style already
established in HDT-3 (no new dependency):

```python
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')
    if h.strip()
]
```

`.strip()` and the truthiness filter keep a trailing comma or padded value from
producing an empty entry, which would silently never match any Host header.

Default mirrors `.env.example` so a bare `manage.py runserver` works without a
`.env` present.

## Out of scope — flag, do not change

`SECRET_KEY` and `DEBUG` are still hardcoded and still ignore
`DJANGO_SECRET_KEY` / `DJANGO_DEBUG`. The user has been told twice; they have
not asked for them. Not touching them here.

Note the ordering hazard to report: because `DEBUG` is hardcoded `True`, this
fix is what prevents a hard 400-on-everything the moment `DEBUG` is wired to
`DJANGO_DEBUG=0`. Wiring `DEBUG` before `ALLOWED_HOSTS` would have broken the
app outright.

## Acceptance criteria

1. `GET http://0.0.0.0:8000/` returns 200 (the reported failure).
2. `GET http://127.0.0.1:8000/` and `http://localhost:8000/` still return 200 —
   no regression from replacing the implicit debug list.
3. `manage.py check` passes.
4. A host NOT in the list still returns 400, proving the setting is enforced and
   not accidentally permissive (e.g. did not become `['*']`).
5. No new entries in `app/requirements.txt`.
