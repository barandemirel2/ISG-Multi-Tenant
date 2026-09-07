"""Regression tests for PR0 baseline security and deployment safety.

These tests are deliberately self-contained: they import the backend module
directly (after seeding the minimum required environment variables) and stub
out the Mongo client so they do not depend on a running database.

A non-production placeholder password is only used to satisfy the
ADMIN_PASSWORD environment check during ``on_startup``. It is never logged,
asserted on as a literal, or echoed in failure output.

The tests are organized into four concerns matching the PR0 follow-up fixes:

* Process-lifetime JWT secret freeze (Fix 1).
* No repository filesystem side effects (Fix 2) — proven by spying on the
  ``Path`` methods visible to ``backend.server`` so the absolute-path write
  performed by the original implementation cannot slip through.
* Behavioral (not source-text) verification of the credential-write removal
  invariant (Fix 3).
* Infrastructure configuration: Dockerfile healthcheck and compose port
  bindings (Fix 4).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Minimum env vars required by ``server.py`` at import time. The placeholder
# JWT_SECRET keeps import-time side effects benign; individual tests override
# this as needed. The placeholder ADMIN_PASSWORD is never printed by any
# assertion (it is only used to assert it is *absent* from logs and artifacts).
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_pr0_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "pr0-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")


def _stub_db():
    """Return an async-friendly stub for the module-level ``db`` object."""

    async def _noop(*_args, **_kwargs):
        return None

    async def _find_none(*_args, **_kwargs):
        return None

    async def _insert(*_args, **_kwargs):
        return MagicMock(inserted_id="pr0-test-id")

    async def _empty_cursor(*_args, **_kwargs):
        # async generator yielding nothing (load_templates_cache iterates it)
        if False:
            yield None

    db = MagicMock()
    db.users.create_index = _noop
    db.audits.create_index = _noop
    db.users.find_one = _find_none
    db.users.insert_one = _insert
    db.users.update_one = _noop
    # Phase 2B (S18/S20): on_startup artık template seed + ibraz index'lerini
    # de kurar. Bu collection'ları stub'lamazsak MagicMock `await` edilemez.
    db.templates.create_index = _noop
    db.templates.find_one = _find_none
    db.templates.insert_one = _insert
    db.templates.find = _empty_cursor
    db.audit_ibraz.create_index = _noop
    return db


@pytest.fixture(autouse=True)
def _isolate_jwt_cache():
    """Save and restore the module-level JWT secret cache.

    Each xdist worker is its own Python process, so cache state cannot leak
    across workers. Within a single worker, this fixture guarantees that one
    test's initialization (or intentional reset) does not bleed into the
    next test.
    """
    import server
    saved = server._JWT_SECRET
    try:
        yield
    finally:
        server._JWT_SECRET = saved


# ---------------------------------------------------------------------------
# Pure unit tests for the JWT secret validator
# ---------------------------------------------------------------------------
class TestValidateJwtSecret:
    def test_missing_secret_rejected(self):
        from server import validate_jwt_secret

        with pytest.raises(RuntimeError, match="JWT_SECRET is required"):
            validate_jwt_secret(None)

    def test_empty_secret_rejected(self):
        from server import validate_jwt_secret

        with pytest.raises(RuntimeError, match="empty or whitespace-only"):
            validate_jwt_secret("")

    def test_whitespace_only_secret_rejected(self):
        from server import validate_jwt_secret

        with pytest.raises(RuntimeError, match="empty or whitespace-only"):
            validate_jwt_secret("   \t\n  ")

    def test_short_secret_rejected(self):
        from server import validate_jwt_secret

        with pytest.raises(RuntimeError, match="at least 32 characters"):
            validate_jwt_secret("a" * 31)

    def test_non_string_secret_rejected(self):
        from server import validate_jwt_secret

        with pytest.raises(RuntimeError, match="must be a string"):
            validate_jwt_secret(12345)

    def test_min_length_secret_accepted(self):
        from server import validate_jwt_secret

        secret = "a" * 32
        assert validate_jwt_secret(secret) == secret

    def test_long_secret_accepted(self):
        from server import validate_jwt_secret

        secret = "a" * 64
        assert validate_jwt_secret(secret) == secret

    def test_surrounding_whitespace_trimmed(self):
        from server import validate_jwt_secret

        inner = "a" * 32
        assert validate_jwt_secret(f"  {inner}  ") == inner


# ---------------------------------------------------------------------------
# Process-lifetime JWT secret behavior (Fix 1)
# ---------------------------------------------------------------------------
class TestJwtSecretProcessLifetime:
    def test_initialize_rejects_missing_secret(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        from server import initialize_jwt_secret

        with pytest.raises(RuntimeError, match="JWT_SECRET is required"):
            initialize_jwt_secret()

    def test_initialize_rejects_blank_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "")
        from server import initialize_jwt_secret

        with pytest.raises(RuntimeError, match="empty or whitespace-only"):
            initialize_jwt_secret()

    def test_initialize_rejects_short_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "a" * 31)
        from server import initialize_jwt_secret

        with pytest.raises(RuntimeError, match="at least 32 characters"):
            initialize_jwt_secret()

    def test_initialize_stores_valid_secret(self, monkeypatch):
        import server
        secret = "x" * 48
        monkeypatch.setenv("JWT_SECRET", secret)

        returned = server.initialize_jwt_secret()

        assert server._JWT_SECRET == secret
        assert returned == secret

    def test_get_jwt_secret_returns_initialized_value(self, monkeypatch):
        import server
        secret = "y" * 48
        monkeypatch.setenv("JWT_SECRET", secret)
        server.initialize_jwt_secret()

        assert server.get_jwt_secret() == secret

    def test_env_mutation_after_init_does_not_change_cached_secret(
        self, monkeypatch
    ):
        import server
        initial = "i" * 48
        later = "l" * 48
        monkeypatch.setenv("JWT_SECRET", initial)
        server.initialize_jwt_secret()
        assert server.get_jwt_secret() == initial

        monkeypatch.setenv("JWT_SECRET", later)

        # The cached value must NOT change just because the environment did.
        assert server.get_jwt_secret() == initial
        assert server.get_jwt_secret() != later

    def test_token_signing_and_verification_use_cached_secret_after_env_mutation(
        self, monkeypatch
    ):
        import jwt as pyjwt
        import server
        initial = "initial-secret-1234567890-abcdefghijklmnop-32chars"
        later = "mutated-secret-1234567890-ABCDEFGHIJKLMNOP-32chars"
        monkeypatch.setenv("JWT_SECRET", initial)
        server.initialize_jwt_secret()

        monkeypatch.setenv("JWT_SECRET", later)

        token = server.create_access_token("user-id-123", "user@example.com")

        # The token must verify with the original (cached) secret and fail
        # with the post-init environment value.
        decoded = pyjwt.decode(
            token, initial, algorithms=[server.JWT_ALGORITHM]
        )
        assert decoded["sub"] == "user-id-123"
        assert decoded["email"] == "user@example.com"
        assert decoded["type"] == "access"

        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(token, later, algorithms=[server.JWT_ALGORITHM])

    def test_get_jwt_secret_before_init_raises_safe_error(self, monkeypatch):
        import server
        # Force the cache into the uninitialized state for this test.
        server._JWT_SECRET = None

        with pytest.raises(
            RuntimeError, match="JWT secret has not been initialized"
        ):
            server.get_jwt_secret()

    def test_get_jwt_secret_error_does_not_echo_secret(self, monkeypatch):
        import server
        distinctive = "must-not-appear-in-error-aaaa1111bbbb2222cccc"
        monkeypatch.setenv("JWT_SECRET", distinctive[:5])  # too short on purpose
        server._JWT_SECRET = None
        try:
            with pytest.raises(RuntimeError) as exc:
                server.get_jwt_secret()
        except RuntimeError:
            # If get_jwt_secret somehow didn't raise, fall through to the
            # initialize call below which is guaranteed to raise on a short
            # secret. Either error message must be secret-free.
            pass
        # Independently: initializing with the short distinctive value must
        # also raise without leaking the value.
        with pytest.raises(RuntimeError) as exc:
            server.initialize_jwt_secret()
        rendered = str(exc.value)
        assert distinctive not in rendered
        assert distinctive[:5] not in rendered


# ---------------------------------------------------------------------------
# Admin credential write removal — behavioral only (Fix 2, Fix 3)
# ---------------------------------------------------------------------------
class TestNoAdminCredentialFile:
    def test_startup_does_not_create_credential_artifact(self, monkeypatch):
        """``on_startup`` must not invoke ``Path`` primitives that write a
        credential artifact.

        The original implementation called:

            creds_path = Path("/app/memory")
            creds_path.mkdir(parents=True, exist_ok=True)
            (creds_path / "test_credentials.md").write_text(
                f"# Test Credentials\\n...{os.environ['ADMIN_PASSWORD']}...",
                encoding="utf-8",
            )

        ``monkeypatch.chdir`` does not intercept that call because the path
        is absolute. Instead we install in-memory spies on the ``Path``
        methods visible to ``backend.server``. Every ``mkdir`` and
        ``write_text`` attempt performed by the production code is captured
        and then asserted against the credential-artifact contract.
        """
        import server

        # Ensure JWT validation passes; the placeholder from the module-level
        # defaults is valid (48 chars).
        monkeypatch.setenv("JWT_SECRET", "x" * 48)
        # Reset the cache so startup re-initializes from the current env.
        server._JWT_SECRET = None

        mkdir_attempts = []
        write_attempts = []

        def spy_mkdir(path_obj, *args, **kwargs):
            mkdir_attempts.append((str(path_obj), args, kwargs))
            return None

        def spy_write_text(path_obj, data, *args, **kwargs):
            write_attempts.append((str(path_obj), str(data), args, kwargs))
            return len(str(data))

        # Patch on the class so any Path(...) instance method is captured.
        # This works because ``backend.server`` does ``from pathlib import Path``;
        # ``server.Path`` is the very class object that backs every Path()
        # call made from server.py.
        monkeypatch.setattr(server.Path, "mkdir", spy_mkdir)
        monkeypatch.setattr(server.Path, "write_text", spy_write_text)

        with patch("server.db", _stub_db()):
            asyncio.run(server.on_startup())

        placeholder = os.environ["ADMIN_PASSWORD"]

        attempts = []
        for path_str, args, kwargs in mkdir_attempts:
            attempts.append(("mkdir", path_str, ""))
        for path_str, data, _args, _kwargs in write_attempts:
            attempts.append(("write_text", path_str, data))

        # 1. No attempt may target the historical absolute path or filename.
        for kind, path_str, _data in attempts:
            assert "/app/memory" not in path_str, (
                f"on_startup invoked {kind} on an absolute /app/memory "
                f"path: {path_str!r}"
            )
            assert "test_credentials.md" not in path_str, (
                f"on_startup invoked {kind} on test_credentials.md: {path_str!r}"
            )

        # 2. No write may contain the configured placeholder password or the
        #    literal ADMIN_PASSWORD token from the removed artifact.
        for kind, path_str, data in attempts:
            assert placeholder not in data, (
                f"on_startup {kind} wrote a value containing the "
                f"ADMIN_PASSWORD placeholder: {path_str!r}"
            )
            assert "ADMIN_PASSWORD" not in data, (
                f"on_startup {kind} wrote a value containing the literal "
                f"ADMIN_PASSWORD token: {path_str!r}"
            )

        # 3. Nothing should resemble a credential artifact. Heuristic markers
        #    from the removed implementation.
        for _kind, _path_str, data in attempts:
            assert "Test Credentials" not in data, (
                "on_startup wrote content resembling the removed credential "
                "artifact ('Test Credentials' header)"
            )
            assert "## Admin" not in data or "Password:" not in data, (
                "on_startup wrote content resembling an admin-credential block"
            )

    def test_path_spy_detects_historical_absolute_path_write(self, monkeypatch):
        """Mutation sensitivity: prove the spy mechanism catches the
        historical ``/app/memory/test_credentials.md`` write before any
        production-code change is allowed to ship.

        The test re-installs the same spies used by the main regression
        test and then intentionally performs the historical absolute-path
        write through the patched ``Path`` methods. If the spies do not
        fire, this test fails and the regression test above cannot be
        trusted to catch the original behavior.
        """
        import server

        mkdir_attempts = []
        write_attempts = []

        def spy_mkdir(path_obj, *args, **kwargs):
            mkdir_attempts.append(str(path_obj))
            return None

        def spy_write_text(path_obj, data, *args, **kwargs):
            write_attempts.append((str(path_obj), str(data)))
            return len(str(data))

        monkeypatch.setattr(server.Path, "mkdir", spy_mkdir)
        monkeypatch.setattr(server.Path, "write_text", spy_write_text)

        # Reproduce the original block exactly, using the same primitives.
        creds_path = server.Path("/app/memory")
        creds_path.mkdir(parents=True, exist_ok=True)
        artifact = (
            "# Test Credentials\n\n## Admin\n"
            "- Email: admin@example.com\n"
            "- Password: placeholder-for-tests-not-secret\n"
            "- Role: admin\n"
        )
        (creds_path / "test_credentials.md").write_text(artifact, encoding="utf-8")

        assert any("/app/memory" in p for p in mkdir_attempts), (
            "Spy did not capture mkdir on /app/memory"
        )
        assert any(
            p.endswith("/app/memory/test_credentials.md") for p, _ in write_attempts
        ), (
            "Spy did not capture write_text targeting "
            "/app/memory/test_credentials.md"
        )
        flat = "\n".join(data for _p, data in write_attempts)
        assert "placeholder-for-tests-not-secret" in flat, (
            "Spy did not capture placeholder password in the written content"
        )
        assert "Test Credentials" in flat, (
            "Spy did not capture credential-artifact marker in written content"
        )

    def test_on_startup_does_not_log_password(self, caplog):
        """The plaintext admin password must never appear in any log record."""
        import logging
        import server

        # Make sure JWT init succeeds (using the module default env).
        server._JWT_SECRET = None

        placeholder = os.environ["ADMIN_PASSWORD"]
        with patch("server.db", _stub_db()):
            with caplog.at_level(logging.INFO):
                asyncio.run(server.on_startup())

        rendered = "\n".join(record.getMessage() for record in caplog.records)
        assert placeholder not in rendered, (
            "ADMIN_PASSWORD must not be logged"
        )


# ---------------------------------------------------------------------------
# Health endpoint (Docker healthcheck target)
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    def test_api_root_accessible_without_auth(self):
        from fastapi.testclient import TestClient
        from server import app

        with patch("server.db", _stub_db()):
            client = TestClient(app)
            response = client.get("/api/")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("status") == "ok"
        # Health response must not leak secrets or user data.
        rendered = str(body)
        assert "JWT_SECRET" not in rendered
        assert "password" not in rendered.lower()

    def test_api_root_does_not_require_authorization_header(self):
        from fastapi.testclient import TestClient
        from server import app

        with patch("server.db", _stub_db()):
            client = TestClient(app)
            response = client.get(
                "/api/",
                headers={"Authorization": ""},
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Infrastructure configuration tests (Fix 4)
# ---------------------------------------------------------------------------
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestBackendDockerfileHealthcheck:
    """Verify the backend Dockerfile's HEALTHCHECK target.

    The previous healthcheck pointed at /api/questions which requires
    authentication and returned 401, breaking container health. The
    fix is an unauthenticated GET /api/. This test inspects the file
    content because the configuration itself is the behavior under test.

    The URL is now ``http://localhost:${PORT:-8000}/api/`` so that
    Railway / other PaaS overlays can supply PORT at runtime; the
    endpoint (``/api/``) and the loopback host (``localhost``) are
    unchanged. The assertion checks the endpoint and the default port
    without locking the literal URL string.
    """

    @property
    def dockerfile_path(self) -> Path:
        return BACKEND_DIR / "Dockerfile"

    def test_healthcheck_line_targets_api_root(self):
        text = _read(self.dockerfile_path)
        healthcheck_lines = [
            line for line in text.splitlines() if line.strip().startswith("CMD")
            and "curl" in line and "localhost" in line
        ]
        assert healthcheck_lines, "Expected a curl-based HEALTHCHECK CMD"
        joined = " ".join(healthcheck_lines)
        assert "/api/" in joined, (
            f"Healthcheck must target /api/, got: {joined!r}"
        )
        # The Railway adaptation keeps the same default port (8000) when
        # PORT is unset; the URL must reference it so the local container
        # still probes the right endpoint with no env override.
        assert "8000" in joined, (
            f"Healthcheck must default to port 8000 when PORT is unset, "
            f"got: {joined!r}"
        )

    def test_healthcheck_does_not_target_api_questions(self):
        text = _read(self.dockerfile_path)
        # The healthcheck command must not point at an authenticated route.
        assert "/api/questions" not in text, (
            "HEALTHCHECK must not target /api/questions (it requires auth)"
        )


class TestDevComposeMongoPort:
    """Verify the dev compose file binds MongoDB to loopback only."""

    @property
    def compose_path(self) -> Path:
        return REPO_ROOT / "docker-compose.yml"

    def test_mongo_published_to_loopback_only(self):
        text = _read(self.compose_path)
        assert "127.0.0.1:27017:27017" in text, (
            "Dev mongo must publish to 127.0.0.1:27017:27017"
        )

    def test_mongo_not_published_to_all_interfaces(self):
        text = _read(self.compose_path)
        # Any host binding that exposes Mongo on non-loopback interfaces is
        # disallowed in the dev compose file.
        assert '"0.0.0.0:27017:27017"' not in text
        assert '"27017:27017"' not in text, (
            "Bare '27017:27017' would publish Mongo on all interfaces"
        )


class TestProdComposeMongoPort:
    """Verify the production compose file does not expose MongoDB to host."""

    @property
    def compose_path(self) -> Path:
        return REPO_ROOT / "docker-compose.prod.yml"

    def test_mongo_service_has_no_published_ports(self):
        text = _read(self.compose_path)
        # The prod compose file must not publish any mongo ports to the
        # host. A robust text-level check: assert that the substring
        # "27017" appears only inside the internal MONGO_URL value, not as
        # a published host port.
        assert "127.0.0.1:27017" not in text, (
            "Prod compose must not publish Mongo on the host"
        )
        assert "0.0.0.0:27017" not in text
        # The only legitimate reference to 27017 in prod is the internal
        # container-side MONGO_URL.
        for line in text.splitlines():
            stripped = line.strip()
            if "27017" in stripped and not stripped.startswith("-"):
                # Allow MONGO_URL: mongodb://mongo:27017 (internal only).
                assert "MONGO_URL" in stripped or "mongodb://mongo" in stripped, (
                    f"Unexpected 27017 reference in prod compose: {line!r}"
                )
