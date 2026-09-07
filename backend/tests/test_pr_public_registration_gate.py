"""P0 — Public registration gate: ``ENABLE_PUBLIC_REGISTRATION`` contract.

This suite pins the security boundary that closes public account
creation in production/default posture. The gate is the **authoritative
backend control**; the frontend ``REACT_APP_PUBLIC_REGISTRATION_ENABLED``
flag is UX-only and never authoritative.

The contract under test
-----------------------

* When ``ENABLE_PUBLIC_REGISTRATION`` is **unset** (or empty), public
  registration is closed.
* When ``ENABLE_PUBLIC_REGISTRATION="false"`` (case-insensitive, optional
  surrounding whitespace), public registration is closed.
* When ``ENABLE_PUBLIC_REGISTRATION="true"`` (case-insensitive, optional
  surrounding whitespace), public registration is open and follows the
  pre-P0 contract verbatim.
* Aliases (``1`` / ``0`` / ``yes`` / ``on`` etc.) are rejected at
  parser time with a sanitized ``RuntimeError`` that does not echo the
  offending input back to the operator.
* The disabled branch MUST short-circuit before any observable side
  effect:

  - No ``db.users.insert_one`` call.
  - No new user document in the collection.
  - No ``Set-Cookie`` header in the response (no ``access_token`` /
    ``refresh_token``).
  - No auto-login: ``GET /api/auth/me`` afterwards is still 401.

* The enabled branch MUST keep the pre-P0 contract:

  - Returns ``200`` with ``{id, email, name, role}`` where ``role=="user"``.
  - Persists the user with a bcrypt ``password_hash`` and **never** the
    plaintext password.
  - Sets ``access_token`` and ``refresh_token`` cookies (auto-login).
  - Duplicate email still returns ``400`` with the legacy detail
    ("Bu e-posta zaten kayıtlı").
  - ``GET /api/auth/me`` afterwards is ``200``.

Test architecture notes
-----------------------

* Pure-parser tests live in :class:`TestParsePublicRegistrationEnabled`
  and never touch the FastAPI app — they exercise
  :func:`registration_config.parse_public_registration_enabled`
  directly.

* HTTP-contract tests use FastAPI ``TestClient`` with a stubbed
  ``server.db`` (deterministic in-memory ``users`` collection). The
  stub records every ``insert_one`` call so the disabled contract's
  "no side effects" assertion is **observable** rather than relying on
  mocks-of-mocks. xdist workers do not share state.

* The module-level ``_PUBLIC_REGISTRATION_ENABLED`` cache is
  overridden per test through
  :func:`registration_config.set_public_registration_enabled_for_tests`.
  The fixture restores the original value in ``finally`` so a test
  failure cannot leak gate state into the next test.
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Minimum env vars required by ``server.py`` at import time. The
# registration gate is intentionally left UNSET here so the
# "disabled by default" tests exercise the production-safe default.
# Tests that need an explicit enabled/disabled state override the
# cached gate value through the test-only helper, NOT by mutating
# ``os.environ`` after import.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_p0_registration_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "p0-registration-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")


import cookie_policy
import registration_config
import server  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — registration gate cache, db stub
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_registration_gate():
    """Save and restore the module-level gate cache around each test.

    xdist workers are separate processes so cache state cannot leak
    across workers. Within a single worker, this fixture keeps one
    test's intentional override from bleeding into the next.
    """
    saved = registration_config._PUBLIC_REGISTRATION_ENABLED
    try:
        yield
    finally:
        registration_config._PUBLIC_REGISTRATION_ENABLED = saved


@pytest.fixture
def stub_users():
    """Stub ``server.db.users`` with a deterministic, observable collection.

    * ``find_one`` does an equality match over the in-memory ``users``
      dict.
    * ``insert_one`` records its argument in ``inserted_docs`` (so
      tests can assert "no insert happened" with a length check) AND
      stores the doc so subsequent ``find_one`` can resolve it.
    * ``update_one`` and ``create_index`` are no-ops sufficient for the
      tests in this module (``register`` does not call them).

    The stub is attached as ``server.db`` so the route handler in
    ``server.py`` reaches it transparently.
    """
    users: Dict[ObjectId, Dict[str, Any]] = {}
    inserted_docs: List[Dict[str, Any]] = []

    async def find_one(query, projection=None):
        for doc in users.values():
            if all(doc.get(k) == v for k, v in query.items()):
                if projection:
                    return {
                        key: deepcopy(doc[key])
                        for key, enabled in projection.items()
                        if enabled and key in doc
                    }
                return deepcopy(doc)
        return None

    async def insert_one(doc):
        doc = deepcopy(doc)
        doc["_id"] = ObjectId()
        users[doc["_id"]] = doc
        inserted_docs.append(doc)
        return MagicMock(inserted_id=doc["_id"])

    async def update_one(query, update):
        for doc in users.values():
            if all(doc.get(k) == v for k, v in query.items()):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value

    async def create_index(*_args, **_kwargs):
        return None

    class _AsyncEmptyCursor:
        def sort(self, *args, **kwargs):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    db = MagicMock()
    db.users = MagicMock()
    db.users.find_one = find_one
    db.users.insert_one = insert_one
    db.users.update_one = update_one
    db.users.create_index = create_index
    db.audits = MagicMock()
    db.audits.find = MagicMock(return_value=_AsyncEmptyCursor())
    db.audits.create_index = create_index
    db.templates = MagicMock()
    db.templates.create_index = create_index
    db.audit_log = MagicMock()
    db.audit_log.insert_one = MagicMock(return_value=MagicMock(inserted_id="x"))
    db.audit_log.create_index = create_index
    db.audit_ibraz = MagicMock()
    db.audit_ibraz.create_index = create_index

    with patch.object(server, "db", db):
        yield {
            "users": users,
            "inserted_docs": inserted_docs,
        }


def _make_client(base_url: str = "http://testserver") -> TestClient:
    """Build a TestClient that includes the canonical api_router.

    Mirrors the recipe used by ``test_pr4_cookie_policy`` so cookie
    attributes and request semantics match the production app. The
    cookie policy is initialized here once per call to the local-HTTP
    profile (``secure=false``, ``samesite=lax``) — the same default
    used elsewhere in the deterministic suite. The enabled branch
    needs ``set_auth_cookies`` to reach ``get_cookie_policy`` and
    raise if the cache is empty; the disabled branch short-circuits
    before that, so it does not need the policy to be initialized,
    but initializing here keeps the helper symmetric.
    """
    cookie_policy.initialize_cookie_policy(
        {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
    )
    app = FastAPI()
    app.include_router(server.api_router)
    server.initialize_jwt_secret()
    return TestClient(app, base_url=base_url)


def _set_cookie_names(response) -> List[str]:
    """Return the cookie names set by the response (empty list if none)."""
    out: List[str] = []
    for header in response.headers.get_list("set-cookie"):
        # ``set-cookie`` carries a single cookie per header; the name is
        # the substring before the first ``=``.
        name = header.split("=", 1)[0].strip()
        out.append(name)
    return out


def _valid_register_payload(
    email: str = "alice@example.com", password: str = "TestPass123"
) -> Dict[str, str]:
    return {
        "email": email,
        "password": password,
        "name": "Alice",
    }


# ---------------------------------------------------------------------------
# Pure parser tests — no FastAPI app involved
# ---------------------------------------------------------------------------
class TestParsePublicRegistrationEnabled:
    """The strict-parser contract is the production-safe default."""

    def test_unset_returns_false(self):
        # Empty mapping == unset; must mirror the production default.
        assert registration_config.parse_public_registration_enabled({}) is False

    def test_empty_string_returns_false(self):
        assert registration_config.parse_public_registration_enabled(
            {"ENABLE_PUBLIC_REGISTRATION": ""}
        ) is False

    def test_whitespace_only_returns_false(self):
        # Surrounding whitespace == empty; mirrors docs_config's
        # tolerance but with the *flipped* (closed) default.
        assert registration_config.parse_public_registration_enabled(
            {"ENABLE_PUBLIC_REGISTRATION": "   "}
        ) is False

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", " true ", "tRuE"])
    def test_true_literal_accepted(self, value):
        assert registration_config.parse_public_registration_enabled(
            {"ENABLE_PUBLIC_REGISTRATION": value}
        ) is True

    @pytest.mark.parametrize(
        "value", ["false", "False", "FALSE", " false ", "fAlSe", "\tfalse\n"],
    )
    def test_false_literal_accepted(self, value):
        assert registration_config.parse_public_registration_enabled(
            {"ENABLE_PUBLIC_REGISTRATION": value}
        ) is False

    @pytest.mark.parametrize(
        "value",
        ["1", "0", "yes", "no", "on", "off", "enabled", "disabled", "maybe"],
    )
    def test_aliases_are_rejected(self, value):
        with pytest.raises(RuntimeError, match="ENABLE_PUBLIC_REGISTRATION"):
            registration_config.parse_public_registration_enabled(
                {"ENABLE_PUBLIC_REGISTRATION": value}
            )

    def test_non_string_rejected(self):
        with pytest.raises(RuntimeError, match="ENABLE_PUBLIC_REGISTRATION"):
            registration_config.parse_public_registration_enabled(
                {"ENABLE_PUBLIC_REGISTRATION": 1}  # type: ignore[arg-type]
            )

    def test_invalid_boolean_message_does_not_echo_value(self):
        sentinel = "invalid-uuid-9a8b7c6d-1234-4def-aaaa-bbbbccccdddd"
        with pytest.raises(RuntimeError, match="unrecognised boolean value") as info:
            registration_config.parse_public_registration_enabled(
                {"ENABLE_PUBLIC_REGISTRATION": sentinel}
            )
        assert sentinel not in str(info.value)


class TestIsPublicRegistrationEnabledHelper:
    """The :func:`is_public_registration_enabled` helper is the
    authoritative read path used by the route handler.
    """

    def test_helper_returns_cached_value(self):
        registration_config.set_public_registration_enabled_for_tests(True)
        assert registration_config.is_public_registration_enabled() is True
        registration_config.set_public_registration_enabled_for_tests(False)
        assert registration_config.is_public_registration_enabled() is False

    def test_helper_default_is_false(self):
        # Save current value, force default, restore.
        saved = registration_config._PUBLIC_REGISTRATION_ENABLED
        try:
            registration_config._PUBLIC_REGISTRATION_ENABLED = False
            assert registration_config.is_public_registration_enabled() is False
        finally:
            registration_config._PUBLIC_REGISTRATION_ENABLED = saved


# ---------------------------------------------------------------------------
# HTTP contract — disabled (the production-safe default)
# ---------------------------------------------------------------------------
class TestRegistrationDisabledByDefault:
    """With the gate unset or explicitly false, the endpoint MUST 404."""

    def test_post_register_returns_404_when_unset(self, stub_users):
        # ``ENABLE_PUBLIC_REGISTRATION`` is unset (module-level fixture
        # never sets it) — production-default posture.
        assert registration_config.is_public_registration_enabled() is False
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 404, response.text

    def test_post_register_returns_404_when_explicit_false(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(False)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 404, response.text


class TestRegistrationDisabledNoSideEffects:
    """Disabled branch MUST short-circuit before any observable effect."""

    def test_no_insert_one_called_when_disabled(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(False)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 404
        # The disabled branch MUST NOT touch db.users.insert_one at all.
        assert stub_users["inserted_docs"] == [], (
            "Disabled registration MUST NOT write to db.users; "
            f"got inserts: {stub_users['inserted_docs']!r}"
        )
        assert stub_users["users"] == {}

    def test_no_auth_cookies_when_disabled(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(False)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 404
        cookie_names = _set_cookie_names(response)
        assert "access_token" not in cookie_names, cookie_names
        assert "refresh_token" not in cookie_names, cookie_names

    def test_no_auto_login_after_disabled_register(self, stub_users):
        # Even if a client repeats the request, no auth cookies means
        # no auto-login. ``/api/auth/me`` is still 401.
        registration_config.set_public_registration_enabled_for_tests(False)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 404
        me = client.get("/api/auth/me")
        assert me.status_code == 401, me.text

    def test_disabled_404_is_idempotent_across_repeated_requests(
        self, stub_users
    ):
        # Two disabled requests with the same payload MUST both 404 and
        # never materialize any user record.
        registration_config.set_public_registration_enabled_for_tests(False)
        client = _make_client()
        for _ in range(2):
            response = client.post(
                "/api/auth/register", json=_valid_register_payload()
            )
            assert response.status_code == 404
        assert stub_users["inserted_docs"] == []
        assert stub_users["users"] == {}


# ---------------------------------------------------------------------------
# HTTP contract — enabled (pre-P0 contract preserved)
# ---------------------------------------------------------------------------
class TestRegistrationEnabled:
    """With the gate explicitly ``true``, the legacy contract is intact."""

    def test_enabled_returns_200_with_user_payload(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(True)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == "alice@example.com"
        assert body["name"] == "Alice"
        assert body["role"] == "user"
        # Legacy contract: response carries ``id`` (ObjectId-as-string).
        assert isinstance(body["id"], str) and len(body["id"]) == 24

    def test_enabled_persists_user_with_bcrypt_hash(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(True)
        client = _make_client()
        response = client.post(
            "/api/auth/register",
            json=_valid_register_payload(password="TestPass123"),
        )
        assert response.status_code == 200

        # Exactly one insert happened.
        assert len(stub_users["inserted_docs"]) == 1
        doc = stub_users["inserted_docs"][0]

        # ``password_hash`` MUST be a bcrypt hash, NOT plaintext.
        assert "password" not in doc, (
            "Plaintext password MUST NOT be persisted"
        )
        assert isinstance(doc.get("password_hash"), str)
        assert doc["password_hash"] != "TestPass123"
        assert doc["password_hash"].startswith("$2")
        # And the hash round-trips against the plaintext via the
        # existing ``verify_password`` helper.
        assert server.verify_password("TestPass123", doc["password_hash"]) is True

        # role=user (admin stays admin; no privilege escalation via register).
        assert doc["role"] == "user"

    def test_enabled_sets_auth_cookies(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(True)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 200
        cookie_names = _set_cookie_names(response)
        assert "access_token" in cookie_names, cookie_names
        assert "refresh_token" in cookie_names, cookie_names

    def test_enabled_auto_login_succeeds(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(True)
        client = _make_client()
        response = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert response.status_code == 200
        me = client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        me_body = me.json()
        assert me_body["email"] == "alice@example.com"
        assert me_body["role"] == "user"
        # ``password_hash`` MUST NOT leak via ``/auth/me``.
        assert "password_hash" not in me_body
        assert "password" not in me_body


class TestRegistrationDuplicateWhenEnabled:
    """Legacy duplicate-email behavior MUST be preserved when enabled."""

    def test_duplicate_email_returns_400(self, stub_users):
        registration_config.set_public_registration_enabled_for_tests(True)
        client = _make_client()
        first = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert first.status_code == 200, first.text
        # Second attempt with the same email MUST 400 with the legacy
        # "Bu e-posta zaten kayıtlı" detail.
        second = client.post(
            "/api/auth/register", json=_valid_register_payload()
        )
        assert second.status_code == 400, second.text
        # Body is ``{"detail": "..."}``; assert the exact legacy text.
        assert second.json()["detail"] == "Bu e-posta zaten kayıtlı"
        # Only one insert happened — the duplicate did not write.
        assert len(stub_users["inserted_docs"]) == 1


# ---------------------------------------------------------------------------
# Security-mismatch sanity — frontend flag cannot widen backend boundary
# ---------------------------------------------------------------------------
class TestFrontendFlagCannotWidenBackendBoundary:
    """Documenting the contract: even if a client claims to be in
    'frontend-enabled' mode, the backend gate is authoritative.
    """

    def test_frontend_enabled_flag_does_not_unblock_backend_when_disabled(
        self, stub_users
    ):
        # The route handler does NOT read any frontend-derived input —
        # it consults ``is_public_registration_enabled`` only. We model
        # this by asserting that no request header / body field can
        # toggle the gate at runtime.
        registration_config.set_public_registration_enabled_for_tests(False)
        client = _make_client()

        # Attempt with every plausible "frontend says it's on" trick.
        response = client.post(
            "/api/auth/register",
            json=_valid_register_payload(),
            headers={
                "X-Frontend-Public-Registration-Enabled": "true",
                "X-Enable-Public-Registration": "true",
                "X-Public-Registration": "true",
            },
        )
        assert response.status_code == 404
        assert stub_users["inserted_docs"] == []
        assert stub_users["users"] == {}


# ---------------------------------------------------------------------------
# Live source-shape guard — protects against accidental drift in
# ``server.register`` so the gate stays before any side effect.
# ---------------------------------------------------------------------------
class TestServerSourceShape:
    """Source-level check: the gate MUST run BEFORE any ``db.users`` or
    cookie operation. This is a defense-in-depth companion to the HTTP
    contract tests: if someone refactors the handler, they cannot
    silently move the gate below the side effects without breaking
    these checks.
    """

    def test_register_calls_helper_before_insert_one(self):
        src = Path(server.__file__).read_text(encoding="utf-8")
        # Extract just the ``register`` body — between the ``async def``
        # signature and the next top-level ``async def`` / ``@``.
        start = src.find("async def register(")
        assert start != -1, "register handler not found"
        # Walk forward to the next top-level ``@`` decorator or
        # ``async def`` declaration. Body ends just before that.
        end = src.find("\n\n\n", start)
        if end == -1:
            end = src.find("\n\n@", start)
        if end == -1:
            end = len(src)
        body = src[start:end]

        gate_idx = body.find("is_public_registration_enabled")
        insert_idx = body.find("db.users.insert_one")
        cookies_idx = body.find("set_auth_cookies")

        assert gate_idx != -1, (
            "register handler MUST consult is_public_registration_enabled"
        )
        assert insert_idx != -1, (
            "register handler MUST still insert into db.users (legacy path)"
        )
        assert cookies_idx != -1, (
            "register handler MUST still set auth cookies (legacy path)"
        )
        # Gate runs strictly BEFORE both side effects.
        assert gate_idx < insert_idx, (
            "is_public_registration_enabled() MUST run before db.users.insert_one"
        )
        assert gate_idx < cookies_idx, (
            "is_public_registration_enabled() MUST run before set_auth_cookies"
        )
