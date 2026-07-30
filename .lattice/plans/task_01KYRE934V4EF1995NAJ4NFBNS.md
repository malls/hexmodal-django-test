# HDT-2 — Fix Docker build

**Complexity:** low

## Problem

`docker compose up` fails at context preparation:

```
unable to prepare context: unable to evaluate symlinks in Dockerfile path:
lstat /Users/forrest/Code/hexmodal-django-test/app/app: no such file or directory
```

The Django project was moved into `app/` and the Dockerfile followed it, but
`docker-compose.yml` and the Dockerfile itself were left in an inconsistent
state. There are four independent defects, all of which must be fixed for
`docker compose up` to work.

## Root causes

1. **`dockerfile:` is context-relative, not repo-relative.**
   `docker-compose.yml` has `context: ./app` + `dockerfile: ./app/Dockerfile`,
   so Docker resolves `app/app/Dockerfile`. This is the reported error.

2. **Dockerfile lost its `COPY requirements.txt` line and its `WORKDIR`.**
   Current `app/Dockerfile` runs `RUN pip install -r requirements.txt` with
   `WORKDIR /` and no preceding `COPY`, so the build would fail on the very next
   step even after (1) is fixed. `chown -R app:app /app` also references a
   directory that no longer exists as the workdir.

3. **Bind mount shadows the app with the wrong directory.**
   `volumes: - .:/app` mounts the repo root over `/app`. The repo root has no
   `manage.py`, so `command: python manage.py runserver` would fail at runtime.
   Must be `./app:/app`.

4. **Platform mismatch recurs on next run.**
   `~/.zshrc:137` exports `DOCKER_DEFAULT_PLATFORM=linux/amd64` globally, while
   the daemon is arm64. `DOCKER_BUILDKIT=0` is also exported, and the legacy
   builder ignores `--platform`, so builds produce arm64 images that compose
   then refuses to run as amd64. This is the error from the previous session and
   it is unfixed — it will reappear as soon as the build succeeds.
   The global amd64 default is presumably intentional (ECR deploys), so override
   per-project rather than removing it. `mise` is installed and `mise.toml`
   already exists, so put the override in `mise.toml [env]`.

## Secondary issue in scope

`.dockerignore` lives at the repo root, but the build context is now `./app`.
Docker only reads `<context>/.dockerignore`, so the ignore rules are silently
inert — `__pycache__/` and `.venv/` would be copied into the image. Add
`app/.dockerignore`.

## Out of scope — flag to user, do not fix here

- `app/config/settings.py` uses `sqlite3` and `ALLOWED_HOSTS = []`. It ignores
  the `POSTGRES_*` and `DJANGO_*` env vars compose passes in. The web service
  will start but will not talk to the `db` service.
- `app/hex/` is five empty files (a dead `startproject` stub). `manage.py`
  points at `config.settings`.
- `core/` is a Django app at the repo root — outside the `./app` build context
  and absent from `INSTALLED_APPS`.

Each deserves its own task.

## Changes

| File | Change |
|------|--------|
| `docker-compose.yml` | `dockerfile: ./app/Dockerfile` → `dockerfile: Dockerfile` |
| `docker-compose.yml` | `volumes: - .:/app` → `- ./app:/app` |
| `app/Dockerfile` | `WORKDIR /` → `WORKDIR /app` |
| `app/Dockerfile` | restore `COPY requirements.txt .` before the `pip install` |
| `mise.toml` | add `[env]` overrides: `DOCKER_DEFAULT_PLATFORM=linux/arm64`, `DOCKER_BUILDKIT=1`, `COMPOSE_DOCKER_CLI_BUILD=1` |
| `app/.dockerignore` | new — move the root `.dockerignore` rules into the build context |

## Acceptance criteria

1. `docker compose build web` completes without error.
2. Built image architecture is `arm64`, and `docker compose up` starts the `web`
   container without the platform-mismatch error.
3. `docker compose run --rm web python manage.py check` passes inside the
   container (proves the bind mount exposes `manage.py` at `/app`).
4. Stale `hexmodal-django-test-web` image removed first, so the arm64 rebuild is
   not skipped by cache.
5. Out-of-scope findings reported to the user, not silently fixed.
