"""Aşama 2A — Template Isolation: snapshot bağımsız, audit etkilenmez.

Doğrulanan bağlayıcı davranış:

* Audit oluşturulduktan sonra template cache'te / db.templates'te
  değişiklik yapılırsa audit'in snapshot soru listesi **değişmez**.

  * Soru dict'i replace edilse bile snapshot bağımsız kalmalı.
  * Soru silinse bile snapshot'ta kalmalı.
  * Soru eklenirse audit snapshot'ına eklenmemeli (mevcut audit'i
    bozmamalı).

* Audit'in effective risk hesabı template cache'i değil snapshot'ı
  okuduğu için, template değişse bile audit summary tutarlı.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from _phase_2a_helpers import (
    fake_db,
    run_async,
    sample_audit_doc,
    sample_template_doc,
)


class TestTemplateIsolation:
    """Audit snapshot, template cache ve DB mutation'larından bağımsız."""

    def _create_audit(self, tpl):
        """Helper: tek bir audit oluştur."""
        from server import create_audit
        from types import SimpleNamespace

        user = {"id": "u-1", "name": "D"}
        body = SimpleNamespace(
            restaurant_name="R", address="A", audit_date="2026-01-15", denetci="",
        )
        with fake_db([tpl]):
            run_async(create_audit(body=body, current_user=user))
            return list(__import__("server").db.audits.docs.values())[0]

    def test_template_replace_does_not_affect_audit_snapshot(self):
        """Template cache tamamen değişse bile snapshot eski şablondan kalır."""
        tpl_v1 = sample_template_doc()
        audit = self._create_audit(tpl_v1)
        snapshot_first_q = audit["template_snapshot"]["questions"][0]["question"]

        with fake_db([tpl_v1]):
            # Template cache'i tamamen değiştir
            new_tpl = sample_template_doc()
            new_tpl["questions"][0]["question"] = "NEW-Q1"
            new_tpl["version"] = 99
            __import__("server").TEMPLATES_CACHE.clear()
            __import__("server").TEMPLATES_CACHE[new_tpl["code"]] = new_tpl

            # Audit dokümanı hâlâ snapshot_first_q'yı tutuyor olmalı
            assert audit["template_snapshot"]["questions"][0]["question"] == snapshot_first_q
            assert audit["template_snapshot"]["template_version"] == 1

    def test_question_remove_does_not_affect_audit(self):
        """Template'ten soru silinse bile audit snapshot'ında kalır."""
        tpl = sample_template_doc()
        audit = self._create_audit(tpl)
        original_count = len(audit["template_snapshot"]["questions"])

        with fake_db([tpl]):
            # Template'ten bir soru sil
            tpl["questions"].pop()
            # Snapshot değişmemeli
            assert len(audit["template_snapshot"]["questions"]) == original_count

    def test_question_add_does_not_propagate_to_audit(self):
        """Template'e yeni soru eklenirse audit snapshot'ına yansımaz."""
        tpl = sample_template_doc()
        audit = self._create_audit(tpl)
        original_count = len(audit["template_snapshot"]["questions"])

        with fake_db([tpl]):
            # Template'e yeni soru ekle
            tpl["questions"].append({
                "id": 999, "no": 999, "category": "Z", "area": "Z",
                "question": "extra", "responsible": "x",
                "default_probability": 1, "default_severity": 1,
                "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
                "document_risk_level": "Kabul Edilebilir",
                "deadline": "2026-12-31", "legal_basis": ["l"], "corrective_action": "c",
            })
            assert len(audit["template_snapshot"]["questions"]) == original_count

    def test_summary_uses_snapshot_not_current_template(self):
        """Özet hesabı snapshot'tan; template değişse bile summary sabit."""
        from server import _summarize
        tpl = sample_template_doc()
        audit = self._create_audit(tpl)
        # Snapshot'taki ilk sorunun p*s değerini sabitle
        snap_q = audit["template_snapshot"]["questions"][0]
        original_score = snap_q["default_probability"] * snap_q["default_severity"]

        with fake_db([tpl]):
            # Template cache'i çarp — yine de snapshot sabit
            for q in tpl["questions"]:
                q["default_probability"] = 5
                q["default_severity"] = 5
            # Snapshot'a dokunmuyoruz (deep copy oluşturulmuştu zaten)
            assert audit["template_snapshot"]["questions"][0]["default_probability"] == snap_q["default_probability"]
            # Summary hesabı — HAYIR olarak audit et
            audit["answers"] = {str(snap_q["id"]): "HAYIR"}
            s = _summarize(audit)
            assert s["hayir_questions"][0]["risk_score"] == original_score