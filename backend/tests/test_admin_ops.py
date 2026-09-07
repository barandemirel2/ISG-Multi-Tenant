"""Admin ops endpoint'leri — S20 retention/backup yönetimi.

Senkron TestClient ile yazıldı; ``pytest-asyncio`` gerektirmez.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── helpers ────────────────────────────────────────────────────────────

def _admin_user():
    return {
        "id": "admin1",
        "email": "admin@test.com",
        "name": "Test Admin",
        "role": "admin",
    }


def _regular_user():
    return {
        "id": "user1",
        "email": "user@test.com",
        "name": "Test User",
        "role": "user",
    }


def _override_user(app, user):
    """get_current_user dependency'sini user ile override et."""
    from server import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture
def app_with_overrides():
    """Test başına temiz app + override fixture."""
    import server
    app = server.app
    app.dependency_overrides.clear()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def fresh_client(app_with_overrides):
    """Her test için yeni bir TestClient — event loop çakışmasını önler.

    TestClient.__exit__ her kullanımda event loop'u kapatır; aynı client'i
    testler arası paylaşırsak "Event loop is closed" hatası alırız. Bu
    fixture her test için yeni bir loop açar.
    """
    from fastapi.testclient import TestClient
    # Client'i context manager disinda olustur; .close() ile temizle
    client = TestClient(app_with_overrides)
    yield client
    client.close()


# ─── /api/admin/archive-expired ─────────────────────────────────────────

def test_archive_expired_requires_admin(app_with_overrides, fresh_client):
    _override_user(app_with_overrides, _regular_user())
    resp = fresh_client.post("/api/admin/archive-expired")
    assert resp.status_code == 403, f"403 bekleniyordu, gelen: {resp.status_code}"
    assert "admin" in resp.json()["detail"].lower()


def test_archive_expired_admin_path(app_with_overrides, fresh_client):
    _override_user(app_with_overrides, _admin_user())
    with patch("audit_log.archive_expired_audits", new=AsyncMock(return_value=42)):
        with patch("server.log_action", new=AsyncMock()):
            resp = fresh_client.post("/api/admin/archive-expired")
            assert resp.status_code == 200, (
                f"200 bekleniyordu, gelen: {resp.status_code} body: {resp.text}"
            )
            data = resp.json()
            assert data["ok"] is True
            assert data["archived_count"] == 42


def test_archive_expired_zero_count(app_with_overrides, fresh_client):
    _override_user(app_with_overrides, _admin_user())
    with patch("audit_log.archive_expired_audits", new=AsyncMock(return_value=0)):
        with patch("server.log_action", new=AsyncMock()):
            resp = fresh_client.post("/api/admin/archive-expired")
            assert resp.status_code == 200
            assert resp.json()["archived_count"] == 0


# ─── /api/admin/retention-status ────────────────────────────────────────

def test_retention_status_requires_admin(app_with_overrides, fresh_client):
    _override_user(app_with_overrides, _regular_user())
    resp = fresh_client.get("/api/admin/retention-status")
    assert resp.status_code == 403


def test_retention_status_admin(app_with_overrides, fresh_client):
    _override_user(app_with_overrides, _admin_user())

    async def fake_count(q):
        if q == {}:
            return 10
        if q == {"is_archived": True}:
            return 3
        if "retention_until" in q and "is_archived" in q:
            return 1
        return 0

    fake_db = MagicMock()
    fake_db.audits.count_documents = fake_count

    with patch("server.db", fake_db):
        resp = fresh_client.get("/api/admin/retention-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "now" in data
        assert data["total_audits"] == 10
        assert data["archived_audits"] == 3
        assert data["active_audits"] == 7
        assert data["expired_pending_archive"] == 1
        assert data["retention_years"] == 6


# ─── /api/admin/backup ──────────────────────────────────────────────────

def test_backup_trigger_requires_admin(app_with_overrides, fresh_client):
    _override_user(app_with_overrides, _regular_user())
    resp = fresh_client.post("/api/admin/backup")
    assert resp.status_code == 403


def test_backup_trigger_admin(app_with_overrides, fresh_client):
    """B9 — admin/backup honest no-op.

    Production backup'ı ``scripts/backup_mongo.sh`` shell cron tarafından
    alınır. Bu endpoint artık no-op; ``audit_log``'a sahte bir "success"
    kayıt yazmaz.
    """
    _override_user(app_with_overrides, _admin_user())
    with patch("server.log_action", new=AsyncMock()) as mock_log:
        resp = fresh_client.post("/api/admin/backup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data.get("action") == "noop", "B9 — endpoint must declare noop"
        assert data.get("deprecated") is True
        assert "shell" in data["message"].lower() or "cron" in data["message"].lower()

        # B9 — ``log_action`` çağrılmamalı: endpoint artık forensic event
        # değil (audit_log'a sahte success yazmak zaten yanlıştı).
        assert not mock_log.called, "B9 — noop endpoint must not write audit_log"
