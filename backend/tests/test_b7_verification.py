"""B7 — İbraz verification chain (public verify) contract testleri.

Kapsam (orijinal B7 sözleşmesi):
  1. canonical/snapshot verification input  → ``_compute_ibraz_hash``
  2. SHA-256                                 → hash uzunluğu/format
  3. persistent server-side record           → ``_persist_ibraz_record``
  4. opaque verification identifier          → ``verification_id`` (uuid hex)
  5. QR URL o ID'yi referanslar              → ``_build_verification_url``
  6. read-only verification endpoint         → ``GET /api/verify/{id}``
  7. public base URL (explicit config + safe dev fallback)
  8. false crypto/e-signature iddiası yok    → ``verification_type`` alanı

MongoDB mock'lanır; endpoint TestClient ile auth'sız çalıştırılır.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pytest


class FakeIbrazCollection:
    def __init__(self, records):
        self.records = list(records)

    async def find_one(self, query, projection=None, sort=None, **kwargs):
        matches = [r for r in self.records if all(r.get(k) == v for k, v in query.items())]
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda r: r.get(key, 0), reverse=(direction < 0))
        return matches[0] if matches else None

    async def insert_one(self, record):
        self.records.append(record)
        return type("Res", (), {"inserted_id": record.get("verification_id")})()


class FakeDB:
    def __init__(self, records):
        self.audit_ibraz = FakeIbrazCollection(records)


def _client_for_records(monkeypatch, records):
    import server
    monkeypatch.setattr(server, "db", FakeDB(records))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(server.api_router)
    # auth dependency override yok — verify endpoint public olmalı (401 dönmemeli)
    return TestClient(app)


# ============ 2. SHA-256 ============

class TestIbrazHash:
    def test_hash_is_sha256_hex(self):
        from server import _compute_ibraz_hash
        doc = {"state": "FINAL", "answers": {"1": "EVET"}, "dof_details": {}, "declarations_meta": {}}
        h = _compute_ibraz_hash("audit_abc", doc)
        assert len(h) == 64, "SHA-256 hex digest must be 64 chars"
        assert all(c in "0123456789abcdef" for c in h), "must be lowercase hex"


# ============ 4. opaque verification identifier ============

class TestOpaqueVerificationId:
    @pytest.mark.asyncio
    async def test_persist_generates_opaque_verification_id(self, monkeypatch):
        from server import _persist_ibraz_record
        fake_db = FakeDB([])
        import server
        monkeypatch.setattr(server, "db", fake_db)
        user = {"id": "u1", "name": "Test"}
        doc = {"state": "FINAL", "answers": {"1": "EVET"}, "dof_details": {}, "declarations_meta": {}}
        rec = await _persist_ibraz_record(fake_db, "audit_abc", doc, user=user)
        vid = rec.get("verification_id")
        assert vid, "verification_id must be present"
        assert len(vid) == 32, "uuid4().hex → 32 hex chars (opaque)"
        assert all(c in "0123456789abcdef" for c in vid)
        # Opaque: audit_id veya hash'in öngörülebilir alt dizesi değil.
        assert "audit_abc" not in vid
        assert vid != rec["ibraz_hash"][:32]

    @pytest.mark.asyncio
    async def test_same_hash_keeps_same_verification_id(self, monkeypatch):
        """Deterministic repeat-generation: aynı içerik → aynı verification_id."""
        from server import _persist_ibraz_record
        fake_db = FakeDB([])
        import server
        monkeypatch.setattr(server, "db", fake_db)
        user = {"id": "u1", "name": "Test"}
        doc = {"state": "FINAL", "answers": {"1": "EVET"}, "dof_details": {}, "declarations_meta": {}}
        rec1 = await _persist_ibraz_record(fake_db, "audit_abc", doc, user=user)
        rec2 = await _persist_ibraz_record(fake_db, "audit_abc", doc, user=user)
        assert rec1["verification_id"] == rec2["verification_id"]
        assert len(fake_db.audit_ibraz.records) == 1, "idempotent: single record"

    @pytest.mark.asyncio
    async def test_new_hash_new_verification_id(self, monkeypatch):
        from server import _persist_ibraz_record
        fake_db = FakeDB([])
        import server
        monkeypatch.setattr(server, "db", fake_db)
        user = {"id": "u1", "name": "Test"}
        doc1 = {"state": "FINAL", "answers": {"1": "EVET"}, "dof_details": {}, "declarations_meta": {}}
        doc2 = {"state": "FINAL", "answers": {"1": "EVET", "2": "HAYIR"}, "dof_details": {}, "declarations_meta": {}}
        rec1 = await _persist_ibraz_record(fake_db, "audit_abc", doc1, user=user)
        rec2 = await _persist_ibraz_record(fake_db, "audit_abc", doc2, user=user)
        assert rec1["verification_id"] != rec2["verification_id"]


# ============ 5. QR URL ============

class TestVerificationUrl:
    def test_url_references_verification_id(self):
        from server import _build_verification_url
        url = _build_verification_url("https://risk.isg-multi-tenant.local", "abc123")
        assert url == "https://risk.isg-multi-tenant.local/api/verify/abc123"
        assert "abc123" in url

    def test_url_strips_trailing_slash_from_base(self):
        from server import _build_verification_url
        assert _build_verification_url("https://x.example/", "id1") == "https://x.example/api/verify/id1"


# ============ 6/7/8. public verify endpoint ============

class TestVerifyEndpoint:
    RECORD = {
        "verification_id": "deadbeef" * 4,
        "audit_id": "65b0a7b5b5b5b5b5b5b5b5b5",
        "ibraz_hash": "a" * 64,
        "short_hash": "a" * 16,
        "state": "FINAL",
        "exported_at": "2026-08-14T00:00:00+00:00",
        "version": 1,
        "exported_by_user_id": "user_secret_id",
        "exported_by_user_name": "Gizli Kullanıcı",
        "ip": "203.0.113.7",
        "user_agent": "Secret-Agent/1.0",
    }

    def test_resolves_verification_id(self, monkeypatch):
        client = _client_for_records(monkeypatch, [self.RECORD])
        resp = client.get(f"/api/verify/{self.RECORD['verification_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["verified"] is True
        assert body["verification_id"] == self.RECORD["verification_id"]
        assert body["ibraz_hash"] == self.RECORD["ibraz_hash"]

    def test_unknown_verification_id_returns_404(self, monkeypatch):
        client = _client_for_records(monkeypatch, [self.RECORD])
        resp = client.get("/api/verify/unknown_id_xyz")
        assert resp.status_code == 404

    def test_empty_verification_id_returns_404(self, monkeypatch):
        client = _client_for_records(monkeypatch, [self.RECORD])
        resp = client.get("/api/verify/")
        assert resp.status_code == 404

    def test_response_does_not_leak_private_fields(self, monkeypatch):
        client = _client_for_records(monkeypatch, [self.RECORD])
        resp = client.get(f"/api/verify/{self.RECORD['verification_id']}")
        assert resp.status_code == 200
        body = resp.json()
        for forbidden in ("exported_by_user_id", "exported_by_user_name", "ip", "user_agent", "audit_id"):
            assert forbidden not in body, f"private field leaked: {forbidden}"

    def test_response_declares_integrity_not_signature(self, monkeypatch):
        client = _client_for_records(monkeypatch, [self.RECORD])
        resp = client.get(f"/api/verify/{self.RECORD['verification_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["verification_type"] == "sha256_integrity_hash"
        # "e-imza"/"nitelikli elektronik imza" iddiası taşımadığını açıkça belirtir.
        assert "değildir" in body["note"]

    def test_endpoint_is_public_no_auth_required(self, monkeypatch):
        """Auth'sız istek 401 DEĞİL; public read-only endpoint."""
        client = _client_for_records(monkeypatch, [self.RECORD])
        resp = client.get(f"/api/verify/{self.RECORD['verification_id']}")
        assert resp.status_code != 401
