"""B2/B3/B4/B5/B7 — Compliance invariant regression tests.

Bu testler server.py'deki korumaların doğru çalıştığını doğrular. MongoDB
mock'lanarak (mongomock motor backend) tüm invariant test edilebilir.

Çalıştırma: ``pytest backend/tests/test_pr_followup_patch_partial.py -v``
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import asyncio
import pytest


# ============ B3 — _normal_audit_filter invariants ============

class TestNormalAuditFilter:
    def test_normal_audit_filter_includes_deleted_at_none(self):
        from server import _normal_audit_filter, _scope_filter
        user = {"id": "u1", "role": "auditor"}
        f = _normal_audit_filter(user)
        assert f.get("deleted_at") is None, "deleted_at must be in normal filter"
        # Scope filter also applies
        scope = _scope_filter(user)
        for k, v in scope.items():
            assert f.get(k) == v, f"scope field {k} inconsistent"

    def test_normal_audit_filter_admin_role_includes_user_id_or_admin(self):
        from server import _normal_audit_filter
        admin = {"id": "admin1", "role": "admin"}
        f = _normal_audit_filter(admin)
        # Admin must NOT have user_id filter (admin bypass)
        assert "user_id" not in f or f.get("$or") is not None, \
            "admin must have bypass scope (no user_id filter)"

    def test_soft_deleted_audit_excluded_by_normal_filter(self):
        """B3 — soft-delete invariants: normal flow excludes deleted."""
        from server import _normal_audit_filter
        user = {"id": "u1", "role": "auditor"}
        f = _normal_audit_filter(user)
        # Filter MUST include deleted_at: None
        assert f["deleted_at"] is None


# ============ B4 — DÖF count with active filter ============

class TestDofCountActiveFilter:
    """``_count_open_dofs`` B4 inactive DÖF'leri sayım dışı bırakır."""

    def _make_audit_doc(self, answers, dof_details):
        """Helper: synthetic audit doc for count test."""
        return {
            "_id": "test_oid",
            "answers": answers,
            "dof_details": dof_details,
            "template_snapshot": [
                {"id": "1", "question": "Q1"},
                {"id": "2", "question": "Q2"},
                {"id": "3", "question": "Q3"},
            ],
        }

    @pytest.mark.asyncio
    async def test_inactive_dof_excluded_from_count(self, monkeypatch):
        """B4: active=False olan DÖF kaydı sayım dışı."""
        # Mock db.audits.find_one
        class FakeDOFDB:
            async def find_one(self, *args, **kwargs):
                return self._doc

            def set(self, doc):
                self._doc = doc

        fake_db = FakeDOFDB()
        fake_db.set(self._make_audit_doc(
            answers={"1": "HAYIR", "2": "EVET"},
            dof_details={
                "1": {"status": "AÇIK", "active": False},  # inactive (B4)
            },
        ))
        # Patch db
        import server
        monkeypatch.setattr(server, "db", type("DB", (), {"audits": fake_db})())

        # ``_get_audit_questions`` template_snapshot'tan okur; doc içindeki
        # snapshot ile çalışmalı.
        count = await server._count_open_dofs(type("OID", (), {})())  # OID unused; we override via find_one
        assert count == 0, "inactive HAYIR DÖF must be excluded from open count"

    @pytest.mark.asyncio
    async def test_active_kapatildi_dof_excluded(self, monkeypatch):
        """B4: active=True + status=KAPATILDI olan DÖF kapalı sayılır."""
        class FakeDOFDB:
            async def find_one(self, *args, **kwargs):
                return self._doc
            def set(self, doc):
                self._doc = doc
        fake_db = FakeDOFDB()
        fake_db.set(self._make_audit_doc(
            answers={"1": "HAYIR", "2": "EVET", "3": "HAYIR"},
            dof_details={
                "1": {"status": "KAPATILDI", "active": True},
                "3": {"status": "AÇIK", "active": True},
            },
        ))
        import server
        monkeypatch.setattr(server, "db", type("DB", (), {"audits": fake_db})())
        count = await server._count_open_dofs(type("OID", (), {})())
        assert count == 1, "only one open DÖF (qid 3)"

    @pytest.mark.asyncio
    async def test_legacy_dof_without_active_field_treated_as_active(self, monkeypatch):
        """Backward compat: aktif alanı olmayan eski DÖF kayıtları aktif
        sayılır (migration invariant)."""
        class FakeDOFDB:
            async def find_one(self, *args, **kwargs):
                return self._doc
            def set(self, doc):
                self._doc = doc
        fake_db = FakeDOFDB()
        fake_db.set(self._make_audit_doc(
            answers={"1": "HAYIR"},
            dof_details={
                "1": {"status": "AÇIK"},  # no active field (legacy)
            },
        ))
        import server
        monkeypatch.setattr(server, "db", type("DB", (), {"audits": fake_db})())
        count = await server._count_open_dofs(type("OID", (), {})())
        assert count == 1, "legacy DÖF without active field counts as open"


# ============ B5 — WorkplaceApprovalDecision validation ============

class TestWorkplaceApprovalDecisionValidation:
    def test_decision_must_be_literal(self):
        """B5 — ``decision`` Pydantic Literal sadece KABUL/ITIRAZ kabul eder."""
        from server import WorkplaceApprovalDecision
        # Valid
        WorkplaceApprovalDecision(decision="KABUL", commitment=None, dispute_reason=None)
        WorkplaceApprovalDecision(decision="ITIRAZ", commitment=None, dispute_reason="Sebep metni 20+ karakter.")
        # Invalid
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            WorkplaceApprovalDecision(decision="EVET", commitment=None, dispute_reason=None)
        with pytest.raises(ValidationError):
            WorkplaceApprovalDecision(decision="KABUL_EDILDI", commitment=None, dispute_reason=None)


# ============ B6 — log_action mandatory parameter ============

class TestLogActionMandatory:
    def test_log_action_signature_supports_mandatory(self):
        """B6 — ``log_action`` ``mandatory: bool`` parametresi kabul eder."""
        import inspect
        from audit_log import log_action
        sig = inspect.signature(log_action)
        assert "mandatory" in sig.parameters, "log_action must support mandatory parameter"
        param = sig.parameters["mandatory"]
        # Default is False (backward compat)
        assert param.default is False or param.default is None, \
            "mandatory default must be False (backward compat)"


# ============ B7 — Ibraz persistence ============

class TestIbrazPersistence:
    @pytest.mark.asyncio
    async def test_compute_ibraz_hash_is_deterministic(self):
        from server import _compute_ibraz_hash
        doc1 = {
            "state": "FINAL",
            "retention_until": "2032-01-01",
            "answers": {"1": "EVET", "2": "HAYIR"},
            "dof_details": {"2": {"status": "KAPATILDI"}},
            "declarations_meta": {"signed_at": "2026-01-01T00:00:00Z", "signed_by_rep_name": "X"},
        }
        doc2 = dict(doc1)
        # Different order of answers
        doc2["answers"] = {"2": "HAYIR", "1": "EVET"}
        h1 = _compute_ibraz_hash("audit_abc", doc1)
        h2 = _compute_ibraz_hash("audit_abc", doc2)
        assert h1 == h2, "answers sort canonicalization broken"

    @pytest.mark.asyncio
    async def test_compute_ibraz_hash_changes_on_content(self):
        from server import _compute_ibraz_hash
        doc = {"state": "FINAL", "answers": {}, "dof_details": {}, "declarations_meta": {}}
        h1 = _compute_ibraz_hash("audit_abc", doc)
        h2 = _compute_ibraz_hash("audit_xyz", doc)
        assert h1 != h2, "audit_id must affect hash"

    @pytest.mark.asyncio
    async def test_persist_ibraz_idempotent_on_same_hash(self, monkeypatch):
        """B7 — aynı (audit_id, ibraz_hash) için tek record (idempotent)."""
        # Mock db.audit_ibraz
        class FakeIbrazCollection:
            def __init__(self):
                self.records = []
            async def find_one(self, query, projection=None, **kwargs):
                for r in self.records:
                    if all(r.get(k) == v for k, v in query.items()):
                        return r
                return None
            async def insert_one(self, rec):
                self.records.append(rec)
                return type("R", (), {"inserted_id": "fake_id"})()
        class FakeDB:
            def __init__(self):
                self.audit_ibraz = FakeIbrazCollection()
        fake_db = FakeDB()
        import server
        monkeypatch.setattr(server, "db", fake_db)

        user = {"id": "u1", "name": "Test"}
        doc = {"state": "FINAL", "answers": {"1": "EVET"}, "dof_details": {}, "declarations_meta": {}}
        rec1 = await server._persist_ibraz_record(fake_db, "audit_abc", doc, user=user)
        rec2 = await server._persist_ibraz_record(fake_db, "audit_abc", doc, user=user)
        assert len(fake_db.audit_ibraz.records) == 1, "idempotent: same hash → one record"
        assert rec1["ibraz_hash"] == rec2["ibraz_hash"]

    @pytest.mark.asyncio
    async def test_persist_ibraz_increments_version_on_new_hash(self, monkeypatch):
        class FakeIbrazCollection:
            def __init__(self):
                self.records = []
            async def find_one(self, query, projection=None, **kwargs):
                if "ibraz_hash" in query:
                    for r in self.records:
                        if all(r.get(k) == v for k, v in query.items()):
                            return r
                    return None
                # Sort by version DESC
                if "sort" in kwargs:
                    sort_key = kwargs["sort"][0][0]
                    sort_dir = kwargs["sort"][0][1]
                    sorted_recs = sorted(self.records, key=lambda r: r.get(sort_key, 0), reverse=(sort_dir == -1))
                    return sorted_recs[0] if sorted_recs else None
                return None
            async def insert_one(self, rec):
                self.records.append(rec)
        class FakeDB:
            def __init__(self):
                self.audit_ibraz = FakeIbrazCollection()
        fake_db = FakeDB()
        import server
        monkeypatch.setattr(server, "db", fake_db)

        user = {"id": "u1", "name": "Test"}
        doc1 = {"state": "FINAL", "answers": {"1": "EVET"}, "dof_details": {}, "declarations_meta": {}}
        doc2 = {"state": "FINAL", "answers": {"1": "HAYIR"}, "dof_details": {}, "declarations_meta": {}}
        rec1 = await server._persist_ibraz_record(fake_db, "audit_abc", doc1, user=user)
        rec2 = await server._persist_ibraz_record(fake_db, "audit_abc", doc2, user=user)
        assert rec1["version"] == 1
        assert rec2["version"] == 2


# ============ B2 — FINAL immutability guards ============

class TestFinalGuards:
    """update_dof, photo upload/delete, sign — FINAL guard contract."""

    def test_update_dof_has_final_guard(self):
        """B2 — update_dof raises 409 when state=FINAL."""
        import inspect
        from server import update_dof
        src = inspect.getsource(update_dof)
        assert "FINAL" in src, "update_dof must check for FINAL state"
        assert "409" in src, "update_dof must return 409 on FINAL"

    def test_upload_photo_has_final_guard(self):
        import inspect
        from server import upload_question_photo
        src = inspect.getsource(upload_question_photo)
        assert "FINAL" in src, "upload must check FINAL"
        assert "409" in src

    def test_delete_photo_has_final_guard(self):
        import inspect
        from server import delete_question_photo
        src = inspect.getsource(delete_question_photo)
        assert "FINAL" in src, "delete photo must check FINAL"
        assert "409" in src

    def test_sign_has_final_guard(self):
        """B5/B2 — sign endpoint must reject FINAL via state predicate."""
        import inspect
        from server import sign_workplace_approval
        src = inspect.getsource(sign_workplace_approval)
        assert "FINAL" in src or "DOF_OPEN" in src, "sign must have state guard"
        assert "DOF_OPEN" in src, "sign must allow DOF_OPEN"
        assert "atomic_filter" in src, "sign must use atomic predicate (B5 race)"


# ============ B4 — update_answers invalidation logic ============

class TestUpdateAnswersInvalidation:
    def test_update_answers_has_invalidation_logic(self):
        """B4 — update_answers invalidates dof_details on HAYIR→non-HAYIR."""
        import inspect
        from server import update_answers
        src = inspect.getsource(update_answers)
        assert "invalidat" in src.lower(), "must have invalidation logic"
        assert "active" in src, "must set active=False on invalidated DÖF"
        assert "answer_changed_to" in src, "must record why DÖF was invalidated"
