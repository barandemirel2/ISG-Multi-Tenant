"""Aşama 2A — backend kanonik hesap testleri.

Hedef: ``compute_effective_risk`` ve ``_summarize`` (HAYIR cevapları için
effective risk kullanan) birlikte aşağıdaki bağlayıcı davranışı garanti
eder:

* ``score = probability * severity``
* ``level = classify_risk(score)``
* Document risk_level alanı **hesaba katılmaz** (override yoksa da, varsa da).
* EVET / NA cevapları risk sayımına girmez (mevcut davranış korunur).
* Default ile aynı override collapse edilir (DB yazımı seviyesinde kontrol).

DB-mock: ``fake_db`` helper'ı kullanır.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from _phase_2a_helpers import fake_db, sample_audit_doc, sample_template_doc
from server import (
    RISK_LEVEL_KABUL_EDILEBILIR,
    RISK_LEVEL_DIKKATE_DEGER,
    RISK_LEVEL_KABUL_EDILEMEZ,
    classify_risk,
    compute_effective_risk,
)


class TestComputeEffectiveRisk:
    """``compute_effective_risk(question, override)`` kanonik hesap."""

    def test_default_path_uses_question_defaults(self):
        q = {
            "default_probability": 3, "default_severity": 4,
            "default_risk_score": 12, "default_risk_level": "Dikkate Değer",
            "document_risk_level": "Kabul Edilebilir",  # sahte provenance
            "id": 1,
        }
        result = compute_effective_risk(q)
        assert result == {
            "probability": 3, "severity": 4,
            "risk_score": 12, "risk_level": "Dikkate Değer",
        }

    def test_override_path_uses_override_values(self):
        q = {
            "default_probability": 1, "default_severity": 1,
            "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
            "document_risk_level": "Kabul Edilemez",  # sahte provenance
            "id": 2,
        }
        result = compute_effective_risk(q, override={"probability": 5, "severity": 5})
        assert result == {
            "probability": 5, "severity": 5,
            "risk_score": 25, "risk_level": "Kabul Edilemez",
        }

    def test_document_risk_level_ignored(self):
        """``document_risk_level`` hesaba katılmaz — ne default ne override durumda."""
        # Eğer document_risk_level dikkate alınsaydı burada "Kabul Edilemez" dönerdi.
        q = {
            "default_probability": 1, "default_severity": 1,
            "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
            "document_risk_level": "Kabul Edilemez",
            "id": 3,
        }
        result = compute_effective_risk(q)
        assert result["risk_level"] == "Kabul Edilebilir"

    @pytest.mark.parametrize("prob,sev,score,level", [
        (1, 1, 1, "Kabul Edilebilir"),
        (2, 2, 4, "Kabul Edilebilir"),
        (3, 2, 6, "Dikkate Değer"),
        (3, 4, 12, "Dikkate Değer"),
        (5, 3, 15, "Kabul Edilemez"),
        (5, 5, 25, "Kabul Edilemez"),
    ])
    def test_matrix_end_to_end(self, prob, sev, score, level):
        q = {
            "default_probability": prob, "default_severity": sev,
            "default_risk_score": score, "default_risk_level": level,
            "document_risk_level": "Kabul Edilebilir",  # sahte
            "id": 1,
        }
        r = compute_effective_risk(q)
        assert r["risk_score"] == prob * sev
        assert r["risk_level"] == classify_risk(score)
        assert r["risk_level"] == level

    def test_invalid_probability_raises(self):
        q = {"default_probability": 0, "default_severity": 1, "id": 1}
        with pytest.raises(ValueError):
            compute_effective_risk(q)

    def test_invalid_severity_raises(self):
        q = {"default_probability": 1, "default_severity": 6, "id": 1}
        with pytest.raises(ValueError):
            compute_effective_risk(q)

    def test_bool_rejected_as_probability(self):
        q = {"default_probability": True, "default_severity": 1, "id": 1}
        with pytest.raises(ValueError):
            compute_effective_risk(q)


class TestSummarizeUsesEffectiveRisk:
    """``_summarize`` HAYIR cevapları için ``compute_effective_risk`` çağırır."""

    def test_hayir_counts_risk_by_effective_level(self):
        """HAYIR cevapları effective level'a göre risk_counts içine girer."""
        tpl = sample_template_doc()
        audit = sample_audit_doc(
            answers={"1": "HAYIR", "2": "HAYIR", "3": "HAYIR"},
            with_snapshot=True, template=tpl,
        )
        with fake_db([tpl]):
            from server import _summarize
            s = _summarize(audit)
            assert s["counts"]["HAYIR"] == 3
            assert s["counts"]["EVET"] == 0
            assert s["total_risk_score"] > 0
            assert len(s["hayir_questions"]) == 3

    def test_evet_and_na_no_risk(self):
        """EVET/NA → risk sayımına girmez; total_risk_score=0 olur (tüm HAYIR yoksa)."""
        audit = sample_audit_doc(
            answers={"1": "EVET", "2": "NA"}, with_snapshot=False,
        )
        with fake_db([]):
            from server import _summarize
            s = _summarize(audit)
            assert s["total_risk_score"] == 0
            assert sum(s["risk_counts"].values()) == 0
            assert s["hayir_questions"] == []

    def test_score_equals_prob_times_severity_in_summary(self):
        """Her HAYIR için ``risk_score = probability * severity`` olmalı."""
        tpl = sample_template_doc()
        audit = sample_audit_doc(
            answers={"1": "HAYIR"}, with_snapshot=True, template=tpl,
        )
        with fake_db([tpl]):
            from server import _summarize
            s = _summarize(audit)
            q1 = tpl["questions"][0]
            exp_score = q1["default_probability"] * q1["default_severity"]
            assert s["hayir_questions"][0]["risk_score"] == exp_score

    def test_override_changes_risk_score_in_summary(self):
        """Override uygulanırsa ``_summarize`` yeni değerleri kullanır."""
        tpl = sample_template_doc()
        audit = sample_audit_doc(
            answers={"1": "HAYIR"},
            risk_overrides={"1": {"probability": 5, "severity": 5}},
            with_snapshot=True, template=tpl,
        )
        with fake_db([tpl]):
            from server import _summarize
            s = _summarize(audit)
            assert s["hayir_questions"][0]["risk_score"] == 25
            assert s["hayir_questions"][0]["risk_level"] == "Kabul Edilemez"

    def test_canary_constants(self):
        """Seviye sabitleri tam metin ile eşleşir (frontend adapter için)."""
        assert RISK_LEVEL_KABUL_EDILEBILIR == "Kabul Edilebilir"
        assert RISK_LEVEL_DIKKATE_DEGER == "Dikkate Değer"
        assert RISK_LEVEL_KABUL_EDILEMEZ == "Kabul Edilemez"