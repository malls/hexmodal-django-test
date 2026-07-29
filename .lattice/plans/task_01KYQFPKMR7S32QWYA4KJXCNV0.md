# HDT-1: Add docker-compose with Django, Postgres, and RabbitMQ services

## Context

The repo currently contains no application code — only `PROMPT.md`, `CLAUDE.md`, `agents.md`, and `.lattice/`.
`PROMPT.md` describes the eventual app: a Django + DRF service that ingests IoT payloads
(Device / Payload models, token auth, base64→hex decode, fCnt dedupe).

This task delivers only the container orchestration layer that the app will run on.

## Scope

**In scope:**
- `docker-compose.yml` with three services: `web` (Django), `db` (Postgres), `rabbitmq`
- `Dockerfile` for the Django service
- `requirements.txt` with the dependencies the compose file assumes (Django, DRF, psycopg, celery)
- `.env.example` documenting the environment variables the compose file consumes
- `.dockerignore`

**Out of scope (explicitly not built here):**
- The Django project itself (`manage.py`, settings, apps, models, endpoints). The compose
  file is written to run `manage.py` once that exists.
- CI, production compose overlay, TLS.

## Approach

### `docker-compose.yml`
- `db`: `postgres:16-alpine`, named volume `postgres_data`, healthcheck via `pg_isready`,
  credentials from env with sane defaults.
- `rabbitmq`: `rabbitmq:3-management-alpine`, ports 5672 (AMQP) + 15672 (management UI),
  named volume `rabbitmq_data`, healthcheck via `rabbitmq-diagnostics check_port_connectivity`.
- `web`: built from local `Dockerfile`, mounts the source dir for live reload, port 8000,
  `depends_on` both `db` and `rabbitmq` with `condition: service_healthy` so Django does not
  boot before Postgres accepts connections.
- Env plumbed via discrete `POSTGRES_*` vars and `CELERY_BROKER_URL`.

### `Dockerfile`
- `python:3.12-slim` base; use `psycopg[binary]` so no compilers are needed.
- Non-root user, `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`.
- Requirements copied and installed before source for layer caching.

## Key files

- `docker-compose.yml` (new)
- `Dockerfile` (new)
- `requirements.txt` (new)
- `.env.example` (new)
- `.dockerignore` (new)

## Acceptance criteria

1. `docker compose config` parses without error.
2. `docker compose up db rabbitmq` brings both to a healthy state.
3. The `web` service definition references `manage.py runserver 0.0.0.0:8000` and waits on
   healthy `db` and `rabbitmq`.
4. Postgres and RabbitMQ data persist across `docker compose down` (named volumes, not
   anonymous).
5. No secrets committed — `.env.example` holds placeholders only.

## Complexity

low
