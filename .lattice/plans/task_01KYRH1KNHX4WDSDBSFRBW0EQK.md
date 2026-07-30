# HDT-6: Configure DRF token authentication

Complexity: low. Settings-only change plus README docs. Scope decided in the task
description (do not re-litigate): built-in `TokenAuthentication`, API-wide
`IsAuthenticated` default, `rest_framework.authtoken` in INSTALLED_APPS, README docs.
No endpoint code (that is HDT-7).

## Edits

### 1. `app/config/settings.py`

**INSTALLED_APPS** — add `'rest_framework.authtoken'` directly after the existing
`'rest_framework'` entry (line 52), before `'telemetry'`, with a short comment in the
file's existing style (see the `# DRF is the seam...` comment above `rest_framework`):

```python
    'rest_framework',
    # Stores DB-backed API tokens for TokenAuthentication (HDT-6). Ships its own
    # migration; applied by the normal 'manage.py migrate', nothing generated here.
    'rest_framework.authtoken',
    'telemetry',
```

**REST_FRAMEWORK dict** — new top-level setting placed after `WSGI_APPLICATION`
(line 83) and before the `# Database` section, matching the file's section-comment
style:

```python
# REST Framework
# Token auth + authenticated-by-default so no future view can accidentally ship
# open. Create tokens with 'manage.py drf_create_token <username>' (see README).

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

Exactly those two keys — nothing else in the dict.

### 2. Migrations — nothing generated in-repo

`rest_framework.authtoken` ships its own migrations inside the package. Nothing to
commit. **How migrations run in this project:** there is no automatic migrate —
docker-compose's web command is only `runserver` and the Dockerfile CMD likewise;
migrations are applied manually (`docker compose exec web python manage.py migrate`,
or `python manage.py migrate` locally). Reviewer verifies via
`makemigrations --check --dry-run` (no app changes) and by confirming no new files
under any `migrations/` dir in the diff.

### 3. `README.md` — API authentication section

Append a new section at the end of the file (after the psql line — the file's flow is
"start service → local setup → lattice → database", so auth setup slots naturally at
the end). Content, matching the README's terse style:

- Apply migrations first (creates the token table):
  `docker compose exec web python manage.py migrate` (or `python manage.py migrate` locally)
- Create a user: `docker compose exec web python manage.py createsuperuser`
- Create a token: `docker compose exec web python manage.py drf_create_token <username>`
  (local equivalents: same commands without the `docker compose exec web` prefix)
- Requests send the header: `Authorization: Token <key>`

## Working-tree hazard (MUST READ)

The tree has uncommitted `.lattice/` changes and `README.md` is `MM` (staged + unstaged
edits from another session — the unstaged part adds the psql line and the file has no
trailing newline). The implementer must:

1. Run `git diff README.md` first and make its edit on top of the **current
   working-tree content** — never revert or drop the psql addition.
2. Stage only its own files: `app/config/settings.py`, `README.md`, and the relevant
   `.lattice/` task files. No `git add -A` / `git add .`.

## Acceptance criteria (cold-reviewable)

- `python manage.py check` exits clean.
- `python manage.py makemigrations --check --dry-run` reports no changes.
- `REST_FRAMEWORK` dict contains exactly `DEFAULT_AUTHENTICATION_CLASSES:
  [TokenAuthentication]` and `DEFAULT_PERMISSION_CLASSES: [IsAuthenticated]`.
- `'rest_framework.authtoken'` present in INSTALLED_APPS.
- README documents migrate + createsuperuser + drf_create_token + the
  `Authorization: Token <key>` header, for both docker compose and local runs.
- No endpoint/view/url/serializer code added; no new migration files in the diff.
- Pre-existing README psql line still present.
