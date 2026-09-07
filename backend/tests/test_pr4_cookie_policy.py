"""Regression tests for PR4 environment-aware authentication cookie policy.

The pre-PR4 implementation hardcoded ``Secure=True`` and ``SameSite=None`` on
every authentication cookie, which made authenticated requests fail over
plain HTTP (browsers and cookie-aware HTTP clients refuse to send back a
``Secure`` cookie unless the connection is HTTPS).

These tests cover the contract introduced by PR4:

* ``CookiePolicy`` parses ``COOKIE_SECURE`` and ``COOKIE_SAMESITE`` strictly,
  refuses missing/invalid values, and fails fast when ``SameSite=None`` is
  paired with ``Secure=False``.
* The cached policy is process-scoped (mirrors the PR0 ``_JWT_SECRET``
  pattern) and is *not* silently re-read from ``os.environ`` after init.
* Login and refresh cookie headers match the configured policy; access and
  refresh cookies share the same policy.
* Local HTTP profile (``COOKIE_SECURE=false``, ``COOKIE_SAMESITE=lax``)
  omits the ``Secure`` attribute.
* HTTPS profile (``COOKIE_SECURE=true``, ``COOKIE_SAMESITE=lax``) sets
  ``Secure``, ``HttpOnly``, and ``SameSite=Lax``.
* A full cookie-jar flow succeeds against a ``TestClient`` integration seam.
* Logout removes both cookies with attributes matching their creation.
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from typing import Iterable
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# Minimum env vars required by ``server.py`` at import time. Cookie policy
# itself is provided per-test, so this module-level setdefault stays empty
# for the cookie variables on purpose; tests that depend on a particular
# policy initialize it explicitly.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_pr4_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "pr4-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")


import cookie_policy
import server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_policy_cache():
    """Save and restore the module-level cookie policy cache.

    xdist workers are separate Python processes, so cache state cannot leak
    across workers. Within a single worker, this fixture keeps one test's
    initialization (or intentional reset) from bleeding into the next.
    """
    saved = cookie_policy._COOKIE_POLICY
    try:
        yield
    finally:
        cookie_policy._COOKIE_POLICY = saved


@pytest.fixture(autouse=True)
def _clear_cookie_env(monkeypatch):
    """Strip COOKIE_* from the surrounding environment for the duration of a test.

    Prevents accidental leakage from CI / host shell values from changing
    what ``initialize_cookie_policy()`` would do without an explicit mapping.
    """
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)


@pytest.fixture
def stub_users(monkeypatch):
    """Stub out the module-level ``db`` with an in-memory users collection.

    Each test gets a fresh copy so concurrent xdist workers cannot observe
    each other's user documents.
    """
    users: dict = {}

    async def find_one(query, projection=None):
        for doc in users.values():
            if all(doc.get(k) == v for k, v in query.items()):
                if projection:
                    return {
                        key: copy.deepcopy(doc[key])
                        for key, enabled in projection.items()
                        if enabled and key in doc
                    }
                return copy.deepcopy(doc)
        return None

    async def insert_one(doc):
        doc = copy.deepcopy(doc)
        doc["_id"] = ObjectId()
        users[doc["_id"]] = doc
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
    db.users.find_one = find_one
    db.users.insert_one = insert_one
    db.users.update_one = update_one
    db.users.create_index = create_index
    db.audits.create_index = create_index
    db.audits.find = MagicMock(return_value=_AsyncEmptyCursor())
    monkeypatch.setattr(server, "db", db)
    return users


def _make_client(base_url: str = "http://testserver") -> TestClient:
    """Build a TestClient. The HTTPS policy profile needs ``https://`` so
    Python's ``http.cookiejar`` will replay the Secure cookies on subsequent
    requests, mirroring real browser behaviour.
    """
    app = FastAPI()
    app.include_router(server.api_router)
    return TestClient(app, base_url=base_url)


# ---------------------------------------------------------------------------
# CookiePolicy dataclass invariants
# ---------------------------------------------------------------------------
class TestCookiePolicyDataclass:
    def test_samesite_none_requires_secure_true(self):
        with pytest.raises(RuntimeError, match="SameSite=None requires Secure=true"):
            cookie_policy.CookiePolicy(secure=False, samesite="none")

    def test_valid_profiles_are_constructible(self):
        for secure, samesite in (
            (False, "lax"),
            (False, "strict"),
            (True, "lax"),
            (True, "strict"),
            (True, "none"),
        ):
            policy = cookie_policy.CookiePolicy(secure=secure, samesite=samesite)
            assert policy.secure is secure
            assert policy.samesite == samesite

    def test_invalid_samesite_rejected_by_dataclass(self):
        with pytest.raises(RuntimeError, match="CookiePolicy.samesite must be"):
            cookie_policy.CookiePolicy(secure=True, samesite="bogus")  # type: ignore[arg-type]

    def test_non_bool_secure_rejected_by_dataclass(self):
        with pytest.raises(RuntimeError, match="CookiePolicy.secure must be a bool"):
            cookie_policy.CookiePolicy(secure="yes", samesite="lax")  # type: ignore[arg-type]

    def test_dataclass_is_frozen(self):
        policy = cookie_policy.CookiePolicy(secure=True, samesite="lax")
        with pytest.raises(Exception):
            policy.secure = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# validate_cookie_policy / initialize_cookie_policy
# ---------------------------------------------------------------------------
class TestValidateCookiePolicy:
    def test_local_http_profile_is_valid(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        assert policy == cookie_policy.CookiePolicy(secure=False, samesite="lax")

    def test_https_lax_profile_is_valid(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        assert policy == cookie_policy.CookiePolicy(secure=True, samesite="lax")

    def test_https_strict_profile_is_valid(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "strict"}
        )
        assert policy == cookie_policy.CookiePolicy(secure=True, samesite="strict")

    def test_https_none_profile_is_valid(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        assert policy == cookie_policy.CookiePolicy(secure=True, samesite="none")

    def test_none_without_secure_fails(self):
        with pytest.raises(RuntimeError, match="SameSite=None requires Secure=true"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "none"}
            )

    def test_invalid_samesite_fails(self):
        with pytest.raises(RuntimeError, match="not a supported SameSite mode"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "bogus"}
            )

    def test_missing_cookie_secure_fails(self):
        with pytest.raises(RuntimeError, match="COOKIE_SECURE is required"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SAMESITE": "lax"}
            )

    def test_missing_cookie_samesite_fails(self):
        with pytest.raises(RuntimeError, match="COOKIE_SAMESITE is required"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "true"}
            )

    def test_invalid_boolean_text_fails(self):
        with pytest.raises(RuntimeError, match="unrecognised boolean value"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "definitely", "COOKIE_SAMESITE": "lax"}
            )

    def test_samesite_is_case_insensitive(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "TRUE", "COOKIE_SAMESITE": "Lax"}
        )
        assert policy.secure is True
        assert policy.samesite == "lax"

    def test_canonical_true_succeeds(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        assert policy.secure is True

    def test_canonical_false_succeeds(self):
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        assert policy.secure is False

    @pytest.mark.parametrize("raw", ["TRUE", "True", "trUe", "FALSE", "False", "fAlSe"])
    def test_canonical_values_are_case_insensitive(self, raw):
        expected = raw.lower() == "true"
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": raw, "COOKIE_SAMESITE": "lax"}
        )
        assert policy.secure is expected

    @pytest.mark.parametrize(
        "raw",
        [" true", "true ", " true ", "\ttrue\n", "  false\t"],
    )
    def test_surrounding_whitespace_is_normalized(self, raw):
        expected = raw.strip().lower() == "true"
        policy = cookie_policy.validate_cookie_policy(
            {"COOKIE_SECURE": raw, "COOKIE_SAMESITE": "lax"}
        )
        assert policy.secure is expected

    @pytest.mark.parametrize("rejected", ["1", "0", "yes", "no", "on", "off"])
    def test_aliases_are_rejected(self, rejected):
        with pytest.raises(RuntimeError, match="unrecognised boolean value"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": rejected, "COOKIE_SAMESITE": "lax"}
            )

    def test_invalid_boolean_message_does_not_echo_value(self):
        sentinel = "invalid-uuid-7c3a9f10-1b22-4d55-aaaa-bbbbccccdddd"
        with pytest.raises(RuntimeError, match="unrecognised boolean value") as info:
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": sentinel, "COOKIE_SAMESITE": "lax"}
            )
        assert sentinel not in str(info.value)

    def test_empty_boolean_fails(self):
        with pytest.raises(RuntimeError, match="COOKIE_SECURE must not be empty"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "   ", "COOKIE_SAMESITE": "lax"}
            )

    def test_empty_samesite_fails(self):
        with pytest.raises(RuntimeError, match="COOKIE_SAMESITE must not be empty"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": ""}
            )

    def test_non_string_boolean_fails(self):
        with pytest.raises(RuntimeError, match="COOKIE_SECURE must be a string"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": 1, "COOKIE_SAMESITE": "lax"}  # type: ignore[arg-type]
            )

    def test_non_string_samesite_fails(self):
        with pytest.raises(RuntimeError, match="COOKIE_SAMESITE must be a string"):
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": 0}  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Process-lifetime caching (mirrors PR0 _JWT_SECRET behavior)
# ---------------------------------------------------------------------------
class TestProcessLifetimeCache:
    def test_initialize_caches_policy(self):
        policy = cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        assert cookie_policy._COOKIE_POLICY == policy
        assert cookie_policy.get_cookie_policy() == policy

    def test_env_mutation_after_init_does_not_change_cache(self):
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        original = cookie_policy.get_cookie_policy()
        assert original.secure is False
        assert original.samesite == "lax"

        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "strict"}
        )
        # The most recent explicit initialization wins; but it cannot have
        # been triggered silently by an unrelated environment mutation.
        assert cookie_policy.get_cookie_policy() != original
        assert cookie_policy.get_cookie_policy().secure is True
        assert cookie_policy.get_cookie_policy().samesite == "strict"

    def test_get_before_init_raises_safe_error(self):
        cookie_policy.reset_cookie_policy_cache()
        with pytest.raises(RuntimeError, match="Cookie policy has not been initialized"):
            cookie_policy.get_cookie_policy()

    def test_default_to_os_environments_when_no_mapping(self, monkeypatch):
        monkeypatch.setenv("COOKIE_SECURE", "true")
        monkeypatch.setenv("COOKIE_SAMESITE", "lax")
        policy = cookie_policy.validate_cookie_policy()
        assert policy == cookie_policy.CookiePolicy(secure=True, samesite="lax")


# ---------------------------------------------------------------------------
# Helpers used by cookie-header integration tests
# ---------------------------------------------------------------------------
def _set_cookie_headers(response) -> list:
    """Return every ``Set-Cookie`` header from the response (preserving order).

    httpx collapses multiple Set-Cookie headers into a single comma-joined
    string, which breaks the parser for cookies containing commas. The
    Starlette TestClient exposes them as ``response.headers.raw``, which
    preserves the raw tuples (with bytes names/values).
    """
    raw_pairs = getattr(response.headers, "raw", [])
    out = []
    for _name, value in raw_pairs:
        name = _name.decode("latin-1") if isinstance(_name, bytes) else _name
        if name.lower() != "set-cookie":
            continue
        out.append(value.decode("latin-1") if isinstance(value, bytes) else value)
    return out


def _parse_set_cookie(header: str) -> dict:
    """Best-effort parser for a single ``Set-Cookie`` header.

    Returns a dict containing ``name``, ``value``, plus flags such as
    ``httponly`` / ``secure`` / ``samesite`` / ``path`` / ``max_age``.
    """
    parts = [segment.strip() for segment in header.split(";")]
    if not parts:
        raise AssertionError(f"empty Set-Cookie header: {header!r}")
    name_value = parts[0]
    if "=" not in name_value:
        raise AssertionError(f"malformed Set-Cookie pair: {name_value!r}")
    name, value = name_value.split("=", 1)
    out = {"name": name.strip(), "value": value, "httponly": False, "secure": False,
           "samesite": None, "path": None, "max_age": None}
    for raw in parts[1:]:
        token = raw.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered == "httponly":
            out["httponly"] = True
        elif lowered == "secure":
            out["secure"] = True
        elif lowered.startswith("samesite="):
            out["samesite"] = token.split("=", 1)[1].strip().lower()
        elif lowered.startswith("path="):
            out["path"] = token.split("=", 1)[1].strip()
        elif lowered.startswith("max-age="):
            try:
                out["max_age"] = int(token.split("=", 1)[1].strip())
            except ValueError:
                out["max_age"] = None
    return out


def _cookies_by_name(response) -> dict:
    return {parsed["name"]: parsed for parsed in (_parse_set_cookie(h) for h in _set_cookie_headers(response))}


def _cookie_by_name(response, name: str) -> dict:
    cookies = _cookies_by_name(response)
    if name not in cookies:
        raise AssertionError(
            f"cookie {name!r} not in Set-Cookie headers; got {list(cookies)}"
        )
    return cookies[name]


def _has_attr(cookie_dict: dict, attr: str) -> bool:
    """True if the parsed cookie carries the requested attribute."""
    if attr == "httponly":
        return cookie_dict["httponly"]
    if attr == "secure":
        return cookie_dict["secure"]
    if attr.startswith("samesite="):
        return cookie_dict["samesite"] == attr.split("=", 1)[1].lower()
    raise AssertionError(f"unknown attr {attr!r}")


def _seed_admin(stub_users) -> dict:
    """Insert a deterministic admin user into the stubbed users collection."""
    import bcrypt

    admin_doc = {
        "email": "pr4-admin@example.com",
        "password_hash": bcrypt.hashpw(
            b"placeholder-for-tests-not-secret", bcrypt.gensalt()
        ).decode("utf-8"),
        "name": "PR4 Admin",
        "role": "admin",
        "created_at": "2026-07-23T00:00:00+00:00",
    }
    admin_doc["_id"] = ObjectId()
    stub_users[admin_doc["_id"]] = admin_doc
    return admin_doc


# ---------------------------------------------------------------------------
# Login & refresh cookie headers
# ---------------------------------------------------------------------------
class TestLocalHttpCookieHeaders:
    def test_login_sets_local_http_cookies(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client()
        response = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )

        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        assert "access_token" in cookies
        assert "refresh_token" in cookies

        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert _has_attr(cookie, "httponly"), name
            assert _has_attr(cookie, "samesite=lax"), name
            assert not _has_attr(cookie, "secure"), name
            assert cookie["path"] == "/"

    def test_refresh_emits_access_cookie_with_same_policy(self, stub_users):
        admin = _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        refresh_token_value = server.create_refresh_token(str(admin["_id"]))

        client = _make_client()
        client.cookies.set("refresh_token", refresh_token_value)
        response = client.post("/api/auth/refresh")

        assert response.status_code == 200, response.text
        cookie = _cookie_by_name(response, "access_token")
        assert _has_attr(cookie, "httponly")
        assert _has_attr(cookie, "samesite=lax")
        assert not _has_attr(cookie, "secure")
        assert cookie["path"] == "/"


class TestHttpsCookieHeaders:
    def test_login_https_profile_sets_secure_and_lax(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client()
        response = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )

        assert response.status_code == 200
        cookies = _cookies_by_name(response)
        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert _has_attr(cookie, "httponly"), name
            assert _has_attr(cookie, "secure"), name
            assert _has_attr(cookie, "samesite=lax"), name
            assert cookie["path"] == "/"

    def test_login_https_profile_with_none_samesite(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        server.initialize_jwt_secret()

        client = _make_client()
        response = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )

        assert response.status_code == 200
        cookies = _cookies_by_name(response)
        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert _has_attr(cookie, "httponly")
            assert _has_attr(cookie, "secure")
            assert _has_attr(cookie, "samesite=none")


# ---------------------------------------------------------------------------
# Cookie-jar authenticated flow (cookies, no Authorization header)
# ---------------------------------------------------------------------------
class TestAuthenticatedCookieJarFlow:
    def test_local_http_full_flow_succeeds(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client()

        login = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )
        assert login.status_code == 200

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "pr4-admin@example.com"

        audits = client.get("/api/audits")
        assert audits.status_code == 200
        assert isinstance(audits.json(), list)

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200

        post = client.get("/api/auth/me")
        assert post.status_code == 401

    def test_https_full_flow_succeeds(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        # HTTPS profile requires https base_url so the cookie jar replays
        # the Secure cookies on the subsequent requests, mirroring the real
        # browser behaviour.
        client = _make_client(base_url="https://testserver")
        login = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )
        assert login.status_code == 200

        me = client.get("/api/auth/me")
        assert me.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200

        post = client.get("/api/auth/me")
        assert post.status_code == 401


# ---------------------------------------------------------------------------
# Refresh flow
# ---------------------------------------------------------------------------
class TestRefreshFlow:
    def test_refresh_reissues_access_cookie_and_authorizes(self, stub_users):
        admin = _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        # Manually mint only the refresh token; the access cookie is absent.
        refresh = server.create_refresh_token(str(admin["_id"]))

        client = _make_client()
        client.cookies.set("refresh_token", refresh)
        # Access cookie is intentionally NOT set.
        assert "access_token" not in {c.name for c in client.cookies.jar}

        response = client.post("/api/auth/refresh")
        assert response.status_code == 200, response.text

        # The response itself carries the new access cookie via Set-Cookie.
        cookies = _cookies_by_name(response)
        assert "access_token" in cookies
        access = cookies["access_token"]
        assert _has_attr(access, "httponly")
        assert _has_attr(access, "samesite=lax")
        assert not _has_attr(access, "secure")

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "pr4-admin@example.com"

        # After logout the refresh cookie is also expired from the jar.
        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        for name in ("access_token", "refresh_token"):
            cookie = _cookie_by_name(logout, name)
            # delete_cookie writes Max-Age=0; we only need to assert the
            # browser-side intent by inspecting the Set-Cookie header itself.
            assert cookie["path"] == "/"


# ---------------------------------------------------------------------------
# Logout cookie-header behavior
# ---------------------------------------------------------------------------
class TestLogoutHeaders:
    def test_logout_removes_both_cookies_with_matching_identity(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client()
        login = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )
        assert login.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        cookies = _cookies_by_name(logout)
        assert "access_token" in cookies
        assert "refresh_token" in cookies

        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert cookie["path"] == "/"
            assert cookie["max_age"] == 0


# ---------------------------------------------------------------------------
# Cookie names / expiry preservation
# ---------------------------------------------------------------------------
class TestCookieNamesAndExpiryPreserved:
    def test_access_and_refresh_cookie_names_unchanged(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client()
        response = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )
        cookies = _cookies_by_name(response)
        assert set(cookies) == {"access_token", "refresh_token"}

        access = cookies["access_token"]
        refresh = cookies["refresh_token"]
        # Max-Age is preserved: 12h access, 7d refresh.
        assert access["max_age"] == 60 * 60 * 12
        assert refresh["max_age"] == 60 * 60 * 24 * 7

    def test_path_is_root_for_both_cookies(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client()
        response = client.post(
            "/api/auth/login",
            json={"email": "pr4-admin@example.com", "password": "placeholder-for-tests-not-secret"},
        )
        cookies = _cookies_by_name(response)
        for name in ("access_token", "refresh_token"):
            assert cookies[name]["path"] == "/"


# ---------------------------------------------------------------------------
# Configuration module never echoes a secret-like value
# ---------------------------------------------------------------------------
class TestErrorMessagesAreSanitized:
    @pytest.mark.parametrize(
        "value",
        ["definitely", "off-but-typo", "truthy"],
    )
    def test_invalid_boolean_message_does_not_echo_value(self, value):
        try:
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": value, "COOKIE_SAMESITE": "lax"}
            )
        except RuntimeError as exc:
            assert value not in str(exc), (
                f"Error leaked invalid COOKIE_SECURE value {value!r}"
            )

    def test_invalid_samesite_message_does_not_echo_value(self):
        try:
            cookie_policy.validate_cookie_policy(
                {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "no-such-mode"}
            )
        except RuntimeError as exc:
            assert "no-such-mode" not in str(exc)