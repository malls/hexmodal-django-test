import os
import subprocess
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Error, sync_playwright

# Derive the repo root from this file so compose commands work no matter
# where pytest is invoked from.
REPO_ROOT = Path(__file__).parent.parent

COMPOSE_HINT = (
    'Start the stack first: docker compose up -d '
    '&& docker compose exec web python manage.py migrate'
)

# Idempotent (both get_or_create), non-interactive, prints only the key.
TOKEN_SNIPPET = (
    'from django.contrib.auth import get_user_model\n'
    'from rest_framework.authtoken.models import Token\n'
    "u, _ = get_user_model().objects.get_or_create(username='e2e')\n"
    't, _ = Token.objects.get_or_create(user=u)\n'
    'print(t.key)\n'
)


def manage_shell(code):
    """Run a snippet in the web container's Django shell, return last stdout line."""
    result = subprocess.run(
        [
            'docker', 'compose', 'exec', '-T', 'web',
            'python', 'manage.py', 'shell', '-c', code,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'docker compose exec failed:\n{result.stderr.strip()}\n{COMPOSE_HINT}'
        )
    return result.stdout.strip().splitlines()[-1]


@pytest.fixture(scope='session')
def base_url():
    return os.environ.get('E2E_BASE_URL', 'http://localhost:8000')


@pytest.fixture(scope='session')
def playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope='session', autouse=True)
def _stack_reachable(playwright, base_url):
    # Any HTTP answer (expected: 401) proves the stack is up; only a
    # connection-level error means it is not. Fail fast with a hint rather
    # than letting every test error out with a raw traceback.
    context = playwright.request.new_context(base_url=base_url)
    try:
        context.post('/api/payloads/')
    except Error:
        pytest.exit(f'API not reachable at {base_url}. {COMPOSE_HINT}')
    finally:
        context.dispose()


@pytest.fixture(scope='session')
def auth_token(_stack_reachable):
    token = os.environ.get('E2E_TOKEN')
    if token:
        return token
    try:
        return manage_shell(TOKEN_SNIPPET)
    except RuntimeError as exc:
        pytest.exit(f'Token provisioning failed. {exc}')


@pytest.fixture(scope='session')
def api(playwright, base_url, auth_token):
    context = playwright.request.new_context(
        base_url=base_url,
        extra_http_headers={'Authorization': f'Token {auth_token}'},
    )
    yield context
    context.dispose()


@pytest.fixture(scope='session')
def anon_api(playwright, base_url):
    context = playwright.request.new_context(base_url=base_url)
    yield context
    context.dispose()


@pytest.fixture
def fresh_dev_eui():
    # A fresh 16-hex-char EUI per test per run is what makes the suite
    # re-runnable against a persistent DB with no cleanup.
    return uuid.uuid4().hex[:16]


@pytest.fixture(scope='session')
def get_device_status():
    """Read Device.latest_status from the real Postgres via the running app."""

    def _get(dev_eui):
        # dev_eui is fixture-generated hex, so interpolation is safe.
        return manage_shell(
            'from telemetry.models import Device\n'
            f"print(Device.objects.get(dev_eui='{dev_eui}').latest_status)\n"
        )

    return _get
