# HDT-3: Wire settings.py DATABASES to POSTGRES_* env vars

**Complexity:** low

## Scope

`app/config/settings.py` DATABASES only. Explicitly requested by the user.

## Current state

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "mydb", "USER": "...", "PASSWORD": "...", "HOST": "localhost", "PORT": "5432",
    }
}
```

Engine is already correct (`psycopg[binary]==3.3.4` is in `app/requirements.txt`),
but the credentials are literal placeholders, so the container cannot reach the
`db` service.

## Env vars available

`docker-compose.yml` injects these into the `web` service:

| Var | Compose value | Default in `.env.example` |
|-----|---------------|---------------------------|
| `POSTGRES_DB` | `${POSTGRES_DB:-hexmodal}` | `hexmodal` |
| `POSTGRES_USER` | `${POSTGRES_USER:-hexmodal}` | `hexmodal` |
| `POSTGRES_PASSWORD` | `${POSTGRES_PASSWORD:-hexmodal}` | `hexmodal` |
| `POSTGRES_HOST` | `db` (hardcoded) | not present |
| `POSTGRES_PORT` | `5432` (hardcoded) | `5432` |

Note `POSTGRES_HOST` is absent from `.env.example` because compose hardcodes it
to the service name. Default it to `localhost` in settings so a non-Docker local
run (mise venv + host Postgres) also works.

## Approach

Read all five values via `os.environ.get` with defaults matching `.env.example`.
Use `os.environ.get` rather than adding a dependency — `django-environ` and
`python-dotenv` are not in `app/requirements.txt` and the task does not call for
a new dependency. Compose already loads the root `.env` and passes values through
as real environment variables, so no dotenv parsing is needed.

`import os` must be added — the file currently imports only `pathlib.Path`.

## Out of scope — do NOT change

Still hardcoded and still wrong, but not part of this request (flag to user):
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS = []`. Compose injects
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS`, all ignored.

## Acceptance criteria

1. `docker compose run --rm web python manage.py check` passes.
2. `docker compose run --rm web python manage.py migrate` applies the 18 pending
   migrations against the `db` service (not sqlite).
3. Migrations are visible in Postgres itself — verify via `psql` in the `db`
   container that `django_migrations` is populated, proving the app connected to
   the real service rather than a container-local file.
4. `GET /` still returns 200 with the stack up.
5. No new entries in `app/requirements.txt`.
