"""Aşama 2A — Legacy audit'ler için kontrollü QUESTIONS fallback testleri.

Doğrulanan bağlayıcı davranış:

* Snapshot'ı olmayan audit (legacy) → ``_get_audit_questions`` modül
  seviyesindeki ``QUESTIONS`` listesine **kontrollü fallback** yapar.
* Snapshot'lı yeni audit → snapshot questions'ı kullanır; QUESTIONS'a
  düşmez.
* ``_serialize_audit`` legacy audit için ``is_legacy=True`` koyar.
* ``is_legacy=True`` olan audit export (PDF/Excel) fonksiyonları çalışır
  (başlangıçta QUESTIONS kullanır, sonra effective risk ile summary
  oluşturur).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from _phase_2a_helpers import (
    fake_db,
    sample_audit_doc,
    sample_template_doc,
)


class TestGetAuditQuestions:
    """``_get_audit_questions`` snapshot ve legacy."""

    def test_snapshot_audit_uses_snapshot(self):
        tpl = sample_template_doc()
        audit = sample_audit_doc(
            with_snapshot=True, template=tpl,
            answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
        )
        with fake_db([]):  # template cache boş; snapshot zaten audit'te
            from server import _get_audit_questions
            qs = _get_audit_questions(audit)
            assert len(qs) == 84
            assert qs[0]["question"] == "question-1"

    def test_legacy_audit_falls_back_to_QUESTIONS(self):
        from server import QUESTIONS
        assert len(QUESTIONS) >= 1, "QUESTIONS modül seviyesinde boş olmamalı"
        audit = sample_audit_doc(with_snapshot=False)
        with fake_db([]):
            from server import _get_audit_questions
            qs = _get_audit_questions(audit)
            assert qs is QUESTIONS  # identity check: aynı liste

    def test_legacy_audit_prefers_template_cache_when_present(self):
        """Legacy ama cache dolu ise → cache'den alır mı?

        Kural: legacy audit snapshot yoksa cache'ten de almaz; doğrudan
        QUESTIONS'a gider (orphan kontrolü). Bu ``template değişse bile
        eski audit etkilenmez`` ilkesine uygun.
        """
        tpl = sample_template_doc()
        audit = sample_audit_doc(with_snapshot=False)
        with fake_db([tpl]):
            from server import _get_audit_questions, QUESTIONS
            qs = _get_audit_questions(audit)
            # Template cache dolu ama audit snapshot'sız; fallback = QUESTIONS
            assert qs is QUESTIONS


class TestSerializeLegacyAudit:
    """Legacy audit → ``is_legacy=True``."""

    def test_legacy_audit_serialized(self):
        with fake_db([]):
            from server import _serialize_audit
            audit = sample_audit_doc(with_snapshot=False)
            out = _serialize_audit(audit, owner_name="Legacy Owner")
            assert out["is_legacy"] is True
            assert "template_code" not in out
            assert "template_version" not in out
            assert out["risk_overrides"] == {}

    def test_modern_audit_serialized(self):
        tpl = sample_template_doc()
        with fake_db([tpl]):
            from server import _serialize_audit
            audit = sample_audit_doc(with_snapshot=True, template=tpl)
            out = _serialize_audit(audit, owner_name="")
            assert out["is_legacy"] is False
            assert out["template_code"] == "isg_v1_default"
            assert out["template_version"] == 1


class TestSummarizeLegacyAudit:
    """Legacy audit summary effective risk kullanır (default değerler)."""

    def test_legacy_summary_uses_QUESTIONS_defaults(self):
        from server import QUESTIONS
        # HAYIR cevapları modül seviyesindeki QUESTIONS'tan ilk 3'e isabet etsin
        answers = {}
        for q in QUESTIONS[:3]:
            answers[str(q["id"])] = "HAYIR"

        audit = sample_audit_doc(answers=answers, with_snapshot=False)
        with fake_db([]):
            from server import _summarize
            s = _summarize(audit)
            assert s["counts"]["HAYIR"] == 3
            # QUESTIONS[0] üzerinden score (canonical şema: default_probability /
            # default_severity; legacy şema olasilik/siddet). Implementation
            # ``compute_effective_risk`` her iki şemayı fallback ile okur; bu
            # test de aynı fallback ile beklenen değeri hesaplar — yani veri
            # dosyası tek bir şema taşıyorsa test yine geçer.
            q1 = QUESTIONS[0]
            expected_prob = q1.get("default_probability", q1.get("olasilik"))
            expected_sev = q1.get("default_severity", q1.get("siddet"))
            expected = expected_prob * expected_sev
            assert s["hayir_questions"][0]["risk_score"] == expected