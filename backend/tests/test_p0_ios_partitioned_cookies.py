"""P0 — Regression tests for iOS Safari / WebKit cross-site session persistence.

Symptom (production)
--------------------
On split-host deployments (e.g. Railway frontend + backend on different
domains), iOS WebKit / Safari ITP ("Prevent Cross-Site Tracking") silently
drops ``SameSite=None; Secure`` cookies unless the CHIPS ``Partitioned``
attribute is present.

Root cause & Fix contract
-------------------------
* Cookies emitted under ``COOKIE_SAMESITE=none`` and ``COOKIE_SECURE=true``
  must carry ``; Partitioned`` so iOS WebKit stores them in its partitioned
  cookie jar.
* All auth lifecycle write paths must follow the contract:
    - POST /api/auth/login
    - POST /api/auth/register (when registration gate is enabled)
    - POST /api/auth/refresh
    - POST /api/auth/logout (clear cookies must also be Partitioned)
* First-party / Lax profiles (``COOKIE_SAMESITE=lax``) must NOT emit
  ``Partitioned`` and must remain identical to Starlette's baseline.
* The security invariant (no insecure ``SameSite=None``) is strictly preserved.
* Multiple Set-Cookie headers must remain distinct (not collapsed).
* ``Partitioned`` must not be duplicated.
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import bcrypt
import pytest
from bson import ObjectId
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_p0_ios_partitioned")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "ios-partitioned-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")

import cookie_policy
import registration_config
import server  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_policy_cache():
    saved = cookie_policy._COOKIE_POLICY
    try:
        yield
    finally:
        cookie_policy._COOKIE_POLICY = saved


@pytest.fixture(autouse=True)
def _isolate_registration_gate():
    saved = registration_config._PUBLIC_REGISTRATION_ENABLED
    try:
        yield
    finally:
        registration_config._PUBLIC_REGISTRATION_ENABLED = saved


@pytest.fixture(autouse=True)
def _clear_cookie_env(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)


@pytest.fixture
def stub_users(monkeypatch):
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
    db.templates.create_index = create_index
    db.audit_log = MagicMock()
    db.audit_log.insert_one = MagicMock(return_value=MagicMock(inserted_id="x"))
    db.audit_log.create_index = create_index
    db.audit_ibraz = MagicMock()
    db.audit_ibraz.create_index = create_index
    monkeypatch.setattr(server, "db", db)
    return users


def _make_client(base_url: str = "https://testserver") -> TestClient:
    app = FastAPI()
    app.include_router(server.api_router)
    return TestClient(app, base_url=base_url)


def _set_cookie_headers(response) -> List[str]:
    raw_pairs = getattr(response.headers, "raw", [])
    out: List[str] = []
    for name, value in raw_pairs:
        n = name.decode("latin-1") if isinstance(name, bytes) else name
        if n.lower() != "set-cookie":
            continue
        out.append(value.decode("latin-1") if isinstance(value, bytes) else value)
    return out


def _parse_set_cookie(header: str) -> dict:
    parts = [segment.strip() for segment in header.split(";")]
    if not parts:
        raise AssertionError(f"empty Set-Cookie header: {header!r}")
    name_value = parts[0]
    if "=" not in name_value:
        raise AssertionError(f"malformed Set-Cookie pair: {name_value!r}")
    name, value = name_value.split("=", 1)
    out = {
        "name": name.strip(),
        "value": value,
        "httponly": False,
        "secure": False,
        "samesite": None,
        "path": None,
        "max_age": None,
        "partitioned": False,
    }
    for raw in parts[1:]:
        token = raw.strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered == "httponly":
            out["httponly"] = True
        elif lowered == "secure":
            out["secure"] = True
        elif lowered == "partitioned":
            out["partitioned"] = True
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
    return {p["name"]: p for p in (_parse_set_cookie(h) for h in _set_cookie_headers(response))}


def _seed_admin(stub_users) -> dict:
    admin_doc = {
        "email": "ios-partitioned-admin@example.com",
        "password_hash": bcrypt.hashpw(
            b"placeholder-for-tests-not-secret", bcrypt.gensalt()
        ).decode("utf-8"),
        "name": "iOS Partitioned Admin",
        "role": "admin",
        "created_at": "2026-08-23T00:00:00+00:00",
    }
    admin_doc["_id"] = ObjectId()
    stub_users[admin_doc["_id"]] = admin_doc
    return admin_doc


# ---------------------------------------------------------------------------
# 1. Login Cookie Contract
# ---------------------------------------------------------------------------
class TestLoginPartitionedContract:
    def test_login_cross_site_emits_partitioned(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        response = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        assert set(cookies) == {"access_token", "refresh_token"}

        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert cookie["secure"] is True
            assert cookie["samesite"] == "none"
            assert cookie["httponly"] is True
            assert cookie["path"] == "/"
            assert cookie["partitioned"] is True

    def test_login_first_party_lax_does_not_emit_partitioned(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        response = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert cookie["secure"] is True
            assert cookie["samesite"] == "lax"
            assert cookie["httponly"] is True
            assert cookie["path"] == "/"
            assert cookie["partitioned"] is False

    def test_login_local_http_does_not_emit_partitioned(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="http://testserver")
        response = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert cookie["secure"] is False
            assert cookie["samesite"] == "lax"
            assert cookie["partitioned"] is False


# ---------------------------------------------------------------------------
# 2. Register Cookie Contract
# ---------------------------------------------------------------------------
class TestRegisterPartitionedContract:
    def test_register_cross_site_emits_partitioned(self, stub_users):
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        registration_config.set_public_registration_enabled_for_tests(True)
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "name": "New User",
            },
        )
        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        assert set(cookies) == {"access_token", "refresh_token"}

        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert cookie["secure"] is True
            assert cookie["samesite"] == "none"
            assert cookie["httponly"] is True
            assert cookie["path"] == "/"
            assert cookie["partitioned"] is True

    def test_register_first_party_lax_does_not_emit_partitioned(self, stub_users):
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        registration_config.set_public_registration_enabled_for_tests(True)
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "name": "New User",
            },
        )
        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        for name in ("access_token", "refresh_token"):
            assert cookies[name]["partitioned"] is False
            assert cookies[name]["samesite"] == "lax"


# ---------------------------------------------------------------------------
# 3. Refresh Cookie Contract
# ---------------------------------------------------------------------------
class TestRefreshPartitionedContract:
    def test_refresh_emits_partitioned_access_cookie_on_cross_site(self, stub_users):
        admin = _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        server.initialize_jwt_secret()

        refresh_value = server.create_refresh_token(str(admin["_id"]))

        client = _make_client(base_url="https://testserver")
        client.cookies.set("refresh_token", refresh_value)
        response = client.post("/api/auth/refresh")

        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        assert "access_token" in cookies, cookies

        access = cookies["access_token"]
        assert access["secure"] is True
        assert access["samesite"] == "none"
        assert access["httponly"] is True
        assert access["path"] == "/"
        assert access["partitioned"] is True

    def test_refresh_first_party_lax_does_not_emit_partitioned(self, stub_users):
        admin = _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        refresh_value = server.create_refresh_token(str(admin["_id"]))

        client = _make_client(base_url="https://testserver")
        client.cookies.set("refresh_token", refresh_value)
        response = client.post("/api/auth/refresh")

        assert response.status_code == 200, response.text
        cookies = _cookies_by_name(response)
        assert "access_token" in cookies
        assert cookies["access_token"]["partitioned"] is False


# ---------------------------------------------------------------------------
# 4. Logout Cookie Contract
# ---------------------------------------------------------------------------
class TestLogoutPartitionedContract:
    def test_logout_cross_site_emits_partitioned_clear(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        login = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        assert login.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200

        cookies = _cookies_by_name(logout)
        for name in ("access_token", "refresh_token"):
            cookie = cookies[name]
            assert cookie["path"] == "/"
            assert cookie["max_age"] == 0
            assert cookie["secure"] is True
            assert cookie["samesite"] == "none"
            assert cookie["partitioned"] is True

    def test_logout_first_party_lax_does_not_emit_partitioned(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        login = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        assert login.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        cookies = _cookies_by_name(logout)
        for name in ("access_token", "refresh_token"):
            assert cookies[name]["partitioned"] is False
            assert cookies[name]["max_age"] == 0


# ---------------------------------------------------------------------------
# 5. Header Structure and Deduplication
# ---------------------------------------------------------------------------
class TestHeaderStructureAndDeduplication:
    def test_multiple_set_cookie_headers_remain_separate(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")
        response = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        raw_headers = _set_cookie_headers(response)
        # Must be exactly 2 distinct Set-Cookie headers, not collapsed into 1
        assert len(raw_headers) == 2
        assert any(h.startswith("access_token=") for h in raw_headers)
        assert any(h.startswith("refresh_token=") for h in raw_headers)

    def test_partitioned_not_duplicated_on_repeated_processing(self):
        resp = Response()
        resp.set_cookie(
            key="access_token",
            value="sample",
            httponly=True,
            secure=True,
            samesite="none",
            max_age=3600,
            path="/",
        )
        server._stamp_partitioned(resp)
        server._stamp_partitioned(resp)

        raw_set_cookies = [
            v.decode("latin-1") if isinstance(v, bytes) else v
            for k, v in resp.raw_headers
            if (k.decode("latin-1") if isinstance(k, bytes) else k).lower() == "set-cookie"
        ]
        assert len(raw_set_cookies) == 1
        header = raw_set_cookies[0]
        # Partitioned should appear exactly once
        parts = [p.strip().lower() for p in header.split(";")]
        assert parts.count("partitioned") == 1

    def test_unrelated_headers_unmodified(self):
        resp = Response(
            content=b"ok",
            headers={"Content-Type": "application/json", "X-Custom-Header": "custom-val"},
        )
        resp.set_cookie(
            key="test",
            value="val",
            httponly=True,
            secure=True,
            samesite="none",
            max_age=3600,
            path="/",
        )
        original_custom = [
            (k, v) for k, v in resp.raw_headers
            if (k.decode("latin-1") if isinstance(k, bytes) else k).lower() == "x-custom-header"
        ]
        server._stamp_partitioned(resp)
        after_custom = [
            (k, v) for k, v in resp.raw_headers
            if (k.decode("latin-1") if isinstance(k, bytes) else k).lower() == "x-custom-header"
        ]
        assert original_custom == after_custom


# ---------------------------------------------------------------------------
# 6. Security Invariants
# ---------------------------------------------------------------------------
class TestSecurityInvariants:
    def test_cookie_policy_rejects_insecure_none(self):
        with pytest.raises(RuntimeError, match="SameSite=None requires Secure=true"):
            cookie_policy.initialize_cookie_policy(
                {"COOKIE_SECURE": "false", "COOKIE_SAMESITE": "none"}
            )

    def test_stamp_partitioned_never_stamps_insecure_cookie(self):
        resp = Response()
        resp.set_cookie(
            key="test",
            value="val",
            httponly=True,
            secure=False,
            samesite="none",
            max_age=3600,
            path="/",
        )
        server._stamp_partitioned(resp)
        raw_set_cookies = [
            v.decode("latin-1") if isinstance(v, bytes) else v
            for k, v in resp.raw_headers
            if (k.decode("latin-1") if isinstance(k, bytes) else k).lower() == "set-cookie"
        ]
        assert len(raw_set_cookies) == 1
        assert "partitioned" not in raw_set_cookies[0].lower()


# ---------------------------------------------------------------------------
# 7. End-to-End Cross-Site Auth Lifecycle
# ---------------------------------------------------------------------------
class TestCrossSiteEndToEndFlow:
    def test_full_cross_site_auth_lifecycle(self, stub_users):
        _seed_admin(stub_users)
        cookie_policy.initialize_cookie_policy(
            {"COOKIE_SECURE": "true", "COOKIE_SAMESITE": "none"}
        )
        server.initialize_jwt_secret()

        client = _make_client(base_url="https://testserver")

        # 1. Login
        login = client.post(
            "/api/auth/login",
            json={
                "email": "ios-partitioned-admin@example.com",
                "password": "placeholder-for-tests-not-secret",
            },
        )
        assert login.status_code == 200
        login_cookies = _cookies_by_name(login)
        assert login_cookies["access_token"]["partitioned"] is True
        assert login_cookies["refresh_token"]["partitioned"] is True

        # 2. /auth/me
        me = client.get("/api/auth/me")
        assert me.status_code == 200, me.text
        assert me.json()["email"] == "ios-partitioned-admin@example.com"

        # 3. Simulate access token expiry and refresh
        client.cookies.delete("access_token", domain="testserver.local", path="/")
        refresh = client.post("/api/auth/refresh")
        assert refresh.status_code == 200, refresh.text
        refresh_cookies = _cookies_by_name(refresh)
        assert refresh_cookies["access_token"]["partitioned"] is True

        # 4. Authenticated request after refresh
        me_after = client.get("/api/auth/me")
        assert me_after.status_code == 200, me_after.text

        # 5. Logout
        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        logout_cookies = _cookies_by_name(logout)
        assert logout_cookies["access_token"]["partitioned"] is True
        assert logout_cookies["refresh_token"]["partitioned"] is True
