# HDT-9: Wire SECRET_KEY and DEBUG to DJANGO_SECRET_KEY/DJANGO_DEBUG env vars

Complexity: low. Two edits in `app/config/settings.py`, no other file changes —
docker-compose.yml (web env, lines 25–26) and .env.example (lines 5–6) already
carry both vars.

## Edits

**1. SECRET_KEY (line 24)** — same `os.environ.get` pattern as HDT-3/HDT-4,
with the current insecure dev key as default so fresh clones work with zero setup:

```python
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-qeff72c%4kavwjfe_%*=+^$gnpd^p6!s9im!o9hw3+edsvt=me',
)
```

Keep the existing `# SECURITY WARNING: keep the secret key...` comment above it.

**2. DEBUG (line 27)** — explicit, case-insensitive truthy parse; default `'1'`
keeps DEBUG=True for dev when the var is unset:

```python
DEBUG = os.environ.get('DJANGO_DEBUG', '1').strip().lower() in ('1', 'true', 'yes')
```

Add a why-comment above it matching the file's style (cf. the ALLOWED_HOSTS
comment): compose/.env.example pass '1'/'0', and any unrecognized value falls
to False — a typo fails toward the safe (non-debug) side.
Keep the existing `# SECURITY WARNING: don't run with debug...` comment.

## DJANGO_DEBUG=0 + ALLOWED_HOSTS interaction (checked)

With DEBUG off, Django stops auto-substituting localhost/127.0.0.1/[::1] for an
empty ALLOWED_HOSTS. Checked: the ALLOWED_HOSTS default here is already the
explicit list `'localhost,127.0.0.1,0.0.0.0'` (settings.py lines 32–38, from
HDT-4), so `DJANGO_DEBUG=0` with DJANGO_ALLOWED_HOSTS unset still serves
correctly. No change needed.

## Acceptance criteria

- `python manage.py check` clean.
- Env-override smoke check shows both vars take effect, e.g.:
  `DJANGO_DEBUG=0 DJANGO_SECRET_KEY=test-key python manage.py diffsettings | grep -E 'DEBUG|SECRET_KEY'`
  → DEBUG False, SECRET_KEY test-key; and with no env vars set, defaults hold
  (DEBUG True, insecure dev key).
- Django test suite (telemetry, 12 tests) passes; e2e (Playwright/compose)
  suite unaffected.
- Commit style per recent history: imperative summary with `(HDT-9)` suffix,
  e.g. `Wire SECRET_KEY and DEBUG to DJANGO_* env vars (HDT-9)`.
