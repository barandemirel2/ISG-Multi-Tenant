"""DOCS_ENABLED contract — FastAPI documentation surface configuration.

The Railway UAT adaptation exposes /docs, /redoc, and /openapi.json by
default (local dev convenience) and lets the deployment operator turn
them off explicitly via ``DOCS_ENABLED=false``. These tests pin:

* The strict parser only accepts ``true`` / ``false`` (case-insensitive).
  Aliases such as ``1`` / ``0`` / ``yes`` / ``on`` are rejected.
* Unset / empty DOCS_ENABLED defaults to ``True`` (local dev).
* Invalid values raise a sanitized RuntimeError.
* The FastAPI app constructed by ``server.py`` honors the resolved
  contract: docs enabled by default, disabled when DOCS_ENABLED=false,
  enabled when explicitly set to ``true``.
* When disabled, the HTTP routes return 404 (the docs are not served).
* When enabled, the routes return 200.

Tests that need to exercise the live FastAPI app with a different
``DOCS_ENABLED`` value use ``importlib.reload`` so the module-level
``_DOCS_KWARGS`` is re-evaluated against the patched environment. The
reload is scoped to a single test class; existing tests in the same
xdist worker are not affected because ``loadscope`` pins each test
class to its own worker.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Minimum env vars required by ``server.py`` at import time. These are
# shared across the whole module so the imports below succeed in the
# pytest collection phase too.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_docs_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "docs-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")


import docs_config  # noqa: E402


# ---------------------------------------------------------------------------
# Pure parser tests
# ---------------------------------------------------------------------------
class TestParseDocsEnabled:
    """Strict parser contract — no FastAPI app involved."""

    def test_unset_returns_true(self):
        assert docs_config.parse_docs_enabled({}) is True

    def test_empty_string_returns_true(self):
        assert docs_config.parse_docs_enabled({"DOCS_ENABLED": ""}) is True

    def test_whitespace_only_returns_true(self):
        assert docs_config.parse_docs_enabled({"DOCS_ENABLED": "   "}) is True

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", " true ", "tRuE"])
    def test_true_literal_accepted(self, value):
        assert docs_config.parse_docs_enabled({"DOCS_ENABLED": value}) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", " false ", "fAlSe"])
    def test_false_literal_accepted(self, value):
        assert docs_config.parse_docs_enabled({"DOCS_ENABLED": value}) is False

    @pytest.mark.parametrize(
        "value",
        ["1", "0", "yes", "no", "on", "off", "enabled", "disabled", "maybe"],
    )
    def test_invalid_values_rejected(self, value):
        with pytest.raises(RuntimeError, match="DOCS_ENABLED"):
            docs_config.parse_docs_enabled({"DOCS_ENABLED": value})

    def test_non_string_rejected(self):
        with pytest.raises(RuntimeError, match="DOCS_ENABLED"):
            docs_config.parse_docs_enabled({"DOCS_ENABLED": 1})  # type: ignore[arg-type]

    def test_none_explicit_env_returns_true(self):
        # Explicit None mapping — same as mapping without the key.
        assert docs_config.parse_docs_enabled(None) is True


# ---------------------------------------------------------------------------
# URL resolver tests
# ---------------------------------------------------------------------------
class TestResolveDocsKwargs:
    """The resolver returns the FastAPI constructor kwargs."""

    def test_enabled_returns_defaults(self):
        kwargs = docs_config.resolve_docs_kwargs({"DOCS_ENABLED": "true"})
        assert kwargs == {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }

    def test_disabled_returns_none_for_all_three(self):
        kwargs = docs_config.resolve_docs_kwargs({"DOCS_ENABLED": "false"})
        assert kwargs == {
            "docs_url": None,
            "redoc_url": None,
            "openapi_url": None,
        }

    def test_unset_returns_defaults(self):
        kwargs = docs_config.resolve_docs_kwargs({})
        assert kwargs == {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }


# ---------------------------------------------------------------------------
# FastAPI app integration
# ---------------------------------------------------------------------------
@pytest.fixture
def _reloaded_server(monkeypatch):
    """Reload the ``server`` module with a patched ``DOCS_ENABLED`` value.

    Each test that uses this fixture sets ``DOCS_ENABLED`` via
    ``monkeypatch.setenv`` (or leaves it unset via ``monkeypatch.delenv``)
    before the fixture body runs, then yields the freshly-imported
    ``server`` module. After the test, monkeypatch restores the original
    environment, and we reload once more so the module-level
    ``_DOCS_KWARGS`` no longer leaks the test value into other tests.
    """

    def _reload_with_env(value):
        if value is None:
            monkeypatch.delenv("DOCS_ENABLED", raising=False)
        else:
            monkeypatch.setenv("DOCS_ENABLED", value)
        import server
        importlib.reload(server)
        return server

    yield _reload_with_env

    # Restore the original environment state for the rest of the suite.
    monkeypatch.delenv("DOCS_ENABLED", raising=False)
    import server
    importlib.reload(server)


class TestFastAPIDocsContract:
    """The actual ``server.app`` honors the resolved configuration."""

    def test_default_dev_docs_enabled(self, _reloaded_server):
        server = _reloaded_server(None)
        assert server.app.docs_url == "/docs"
        assert server.app.redoc_url == "/redoc"
        assert server.app.openapi_url == "/openapi.json"

    def test_env_true_keeps_docs_enabled(self, _reloaded_server):
        server = _reloaded_server("true")
        assert server.app.docs_url == "/docs"
        assert server.app.redoc_url == "/redoc"
        assert server.app.openapi_url == "/openapi.json"

    def test_env_false_disables_all_three_routes(self, _reloaded_server):
        server = _reloaded_server("false")
        assert server.app.docs_url is None
        assert server.app.redoc_url is None
        assert server.app.openapi_url is None


# ---------------------------------------------------------------------------
# HTTP-route tests via TestClient — proves the contract reaches the wire
# ---------------------------------------------------------------------------
@pytest.fixture
def _client_with_docs_env(monkeypatch):
    """Reload server with a configured DOCS_ENABLED, yield a TestClient.

    Tests call ``_client_with_docs_env(value)`` to get a fresh
    ``TestClient`` whose app was constructed with the requested docs
    flag. The original environment is restored after the test.
    """

    def _build(value):
        if value is None:
            monkeypatch.delenv("DOCS_ENABLED", raising=False)
        else:
            monkeypatch.setenv("DOCS_ENABLED", value)
        import server
        importlib.reload(server)
        from fastapi.testclient import TestClient
        client = TestClient(server.app)
        return client

    yield _build

    monkeypatch.delenv("DOCS_ENABLED", raising=False)
    import server
    importlib.reload(server)


class TestDocsRoutesHTTP:
    """End-to-end check: the docs surface is actually served (or not)."""

    def test_default_dev_serves_docs(self, _client_with_docs_env):
        client = _client_with_docs_env(None)
        # /docs redirects to /openapi.json which is the actual Swagger UI;
        # we check the openapi.json route directly to assert the contract.
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200

    def test_env_true_serves_docs(self, _client_with_docs_env):
        client = _client_with_docs_env("true")
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200

    def test_env_false_returns_404(self, _client_with_docs_env):
        client = _client_with_docs_env("false")
        # FastAPI returns 404 for routes that were registered with None.
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404

    def test_app_routes_still_respond_when_docs_disabled(self, _client_with_docs_env):
        # Disabling the docs surface must not affect application routes.
        client = _client_with_docs_env("false")
        response = client.get("/api/")
        assert response.status_code == 200
        assert response.json() == {
            "message": "ABCD Tech Solutions Risk Analiz API",
            "status": "ok",
        }
