"""Aşama 2A — ``create_audit`` snapshot + ``risk_overrides={}`` başlatma testleri.

Doğrulanan davranış:

* ``POST /api/audits`` çağrıldığında audit DB'ye şu alanlarla yazılır:

  * ``risk_overrides == {}``
  * ``template_snapshot`` dolu (``code``, ``version``, ``questions``)
  * ``template_snapshot.questions`` template'in questions listesi ile aynı uzunluk
  * ``template_snapshot.template_code`` cache'teki default template ile aynı

* Snapshot şablondan bağımsız kopyadır (liste kopyası). Sonradan template
  cache'te değişse bile snapshot içeriği değişmez.

* Cache'te default template yoksa → HTTP 500 + açıklayıcı hata.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from _phase_2a_helpers import (
    fake_db,
    fake_db_context,
    run_async,
    sample_audit_doc,
    sample_questions,
    sample_template_doc,
)


@pytest.fixture
def client():
    """FastAPI TestClient — ``app`` modül-level."""
    from fastapi.testclient import TestClient
    from server import app
    return TestClient(app)


class TestCreateAuditSnapshot:
    """``create_audit`` template snapshot ve override init."""

    def test_audit_has_template_snapshot(self):
        """Audit snapshot içeriyor (code + version + questions)."""
        tpl = sample_template_doc()
        with fake_db([tpl]):
            from server import create_audit, get_current_user
            from types import SimpleNamespace
            from datetime import datetime, timezone

            user = {"id": "u-1", "name": "Test Denetçi"}
            body = SimpleNamespace(
                restaurant_name="Restoran A",
                address="Adres A",
                audit_date="2026-01-15",
                denetci="",
            )

            # Pop the audit into the fake db (insert_one side effect).
            run_async(create_audit(body=body, current_user=user))
            inserted = list(__import__("server").db.audits.docs.values())[0]

            assert inserted["template_snapshot"] is not None
            assert inserted["template_snapshot"]["template_code"] == "isg_v1_default"
            assert inserted["template_snapshot"]["template_version"] == 1
            assert len(inserted["template_snapshot"]["questions"]) == 84

    def test_audit_has_empty_risk_overrides(self):
        """Yeni audit ``risk_overrides={}`` ile başlar."""
        from server import create_audit
        from types import SimpleNamespace

        tpl = sample_template_doc()
        with fake_db([tpl]):
            user = {"id": "u-2", "name": "Denetçi B"}
            body = SimpleNamespace(
                restaurant_name="R", address="A", audit_date="", denetci=""
            )
            run_async(create_audit(body=body, current_user=user))
            inserted = list(__import__("server").db.audits.docs.values())[0]
            assert inserted["risk_overrides"] == {}

    def test_snapshot_questions_isolated_from_template_cache(self):
        """Snapshot şablondan bağımsız bir liste kopyası — sonradan
        cache'te mutations olsa bile snapshot içeriği değişmez.
        """
        tpl = sample_template_doc()
        with fake_db([tpl]):
            from server import create_audit
            from types import SimpleNamespace

            user = {"id": "u-3", "name": "D"}
            body = SimpleNamespace(
                restaurant_name="R", address="A", audit_date="", denetci=""
            )
            run_async(create_audit(body=body, current_user=user))
            inserted = list(__import__("server").db.audits.docs.values())[0]
            snapshot_first_id = inserted["template_snapshot"]["questions"][0]["question"]

            # Template cache'te mutation yap
            __import__("server").TEMPLATES_CACHE["isg_v1_default"]["questions"][0]["question"] = "MUTATED"

            # Snapshot bağımsız olmalı
            assert inserted["template_snapshot"]["questions"][0]["question"] == snapshot_first_id
            assert inserted["template_snapshot"]["questions"][0]["question"] != "MUTATED"

    def test_create_audit_500_when_no_default_template(self):
        """Cache boşsa açıklayıcı 500."""
        from server import create_audit, HTTPException
        from types import SimpleNamespace

        with fake_db([]):  # boş template collection
            user = {"id": "u-4", "name": "D"}
            body = SimpleNamespace(
                restaurant_name="R", address="A", audit_date="", denetci=""
            )
            with pytest.raises(HTTPException) as exc:
                run_async(create_audit(body=body, current_user=user))
            assert exc.value.status_code == 500
            assert "template" in exc.value.detail.lower()

    def test_create_audit_persists_extended_meta_fields(self):
        """FIX D regression: ``restaurant_manager``, ``auditor_title``,
        ``branch_code``, ``audit_notes`` ``NewAuditPage`` form alanları
        AuditCreate'a eklenmiştir; ``create_audit`` bunları DB'ye yazar ve
        ``_serialize_audit`` response'a ekler. Baran öncesi contract'ta
        Pydantic ``extra="ignore"`` ile sessizce düşüyorlardı.
        """
        from server import _serialize_audit, create_audit
        from types import SimpleNamespace

        tpl = sample_template_doc()
        with fake_db([tpl]):
            user = {"id": "u-5", "name": "Test Denetçi"}
            body = SimpleNamespace(
                restaurant_name="Merkez Şube",
                address="Bağdat Cd. No:1",
                audit_date="2026-08-01",
                denetci="Denetçi A",
                restaurant_manager="Ahmet Yılmaz (Restoran Müdürü)",
                auditor_title="A Sınıfı İSG Uzmanı",
                branch_code="POP-104",
                audit_notes="Ön denetim notu: saha sıcaklık takibi sorunsuz.",
            )
            run_async(create_audit(body=body, current_user=user))
            inserted = list(__import__("server").db.audits.docs.values())[0]

            # DB'ye yazıldı
            assert inserted["restaurant_manager"] == "Ahmet Yılmaz (Restoran Müdürü)"
            assert inserted["auditor_title"] == "A Sınıfı İSG Uzmanı"
            assert inserted["branch_code"] == "POP-104"
            assert inserted["audit_notes"] == "Ön denetim notu: saha sıcaklık takibi sorunsuz."

            # Serialize response da alanları döner
            serialized = _serialize_audit(inserted, owner_name=user["name"])
            assert serialized["restaurant_manager"] == "Ahmet Yılmaz (Restoran Müdürü)"
            assert serialized["auditor_title"] == "A Sınıfı İSG Uzmanı"
            assert serialized["branch_code"] == "POP-104"
            assert serialized["audit_notes"] == "Ön denetim notu: saha sıcaklık takibi sorunsuz."

    def test_create_audit_omits_blank_extended_fields(self):
        """Extended alanlar boş gönderildiğinde DB'de boş string olarak yazılır
        (silinmez); response da bu davranışı korur. Frontend ``NewAuditPage``
        boş default'lar gönderiyor — bunlar 500 veya hata tetiklememelidir.
        """
        from server import _serialize_audit, create_audit
        from types import SimpleNamespace

        tpl = sample_template_doc()
        with fake_db([tpl]):
            user = {"id": "u-6", "name": "D"}
            body = SimpleNamespace(
                restaurant_name="R",
                address="A",
                audit_date="",
                denetci="",
                restaurant_manager="",
                auditor_title="",
                branch_code="",
                audit_notes="",
            )
            run_async(create_audit(body=body, current_user=user))
            inserted = list(__import__("server").db.audits.docs.values())[0]
            assert inserted["restaurant_manager"] == ""
            assert inserted["auditor_title"] == ""
            assert inserted["branch_code"] == ""
            assert inserted["audit_notes"] == ""
            serialized = _serialize_audit(inserted, owner_name="")
            assert serialized["restaurant_manager"] == ""
            assert serialized["auditor_title"] == ""
            assert serialized["branch_code"] == ""
            assert serialized["audit_notes"] == ""


class TestSerializeAuditFields:
    """``_serialize_audit`` yeni alanlar + template bilgisi."""

    def test_new_audit_serializes_template_code_and_version(self):
        from server import _serialize_audit
        tpl = sample_template_doc()
        with fake_db([tpl]):
            doc = sample_audit_doc(with_snapshot=True, template=tpl)
            serialized = _serialize_audit(doc, owner_name="Owner")
            assert serialized["template_code"] == "isg_v1_default"
            assert serialized["template_version"] == 1
            assert serialized["is_legacy"] is False
            assert serialized["risk_overrides"] == {}

    def test_legacy_audit_serializes_without_template_fields(self):
        """Snapshot'sız audit → ``is_legacy=True``, template_code yok."""
        from server import _serialize_audit
        with fake_db([]):
            doc = sample_audit_doc(with_snapshot=False)
            serialized = _serialize_audit(doc, owner_name="")
            assert serialized["is_legacy"] is True
            assert "template_code" not in serialized
            assert "template_version" not in serialized

    def test_include_snapshot_flag(self):
        """``include_snapshot=True`` → snapshot response'a eklenir."""
        from server import _serialize_audit
        with fake_db([]):
            doc = sample_audit_doc(with_snapshot=True)
            a = _serialize_audit(doc, owner_name="", include_snapshot=False)
            b = _serialize_audit(doc, owner_name="", include_snapshot=True)
            assert "template_snapshot" not in a
            assert "template_snapshot" in b
            assert b["template_snapshot"]["template_code"] == "isg_v1_default"