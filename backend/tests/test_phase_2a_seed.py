"""Aşama 2A — ``isg_v1`` seed yükleme + fail-fast doğrulama testleri.

Bu testler **saf pure-Python**: DB ve network bağımlılığı yoktur; sadece
``isg_v1`` modülü düzeyinde çalışır.

Kanıtlanan bağlayıcı doğrulamalar:

* 84 kayıt yüklenir.
* 9 benzersiz kategori vardır.
* ``id`` ve ``no`` alanları 1..84, benzersiz, ardışık ve eşittir.
* ``default_probability`` ve ``default_severity`` 1-5 aralığındadır.
* ``default_risk_score == default_probability * default_severity``.
* ``document_risk_level`` provenance-only; hesaba katılmaz (bu testin
  kapsamı seed modülü; ``classify_risk`` testi ayrıdır).
* ``build_template_doc`` Mongo'ya insert edilecek doğru yapıyı üretir.
* ``code`` unique seed-key olarak doğru sabittir.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import json  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from seed import isg_v1  # noqa: E402


class TestSeedLoading:
    """Seed dosyası başarıyla yüklenir + içerik doğrulamaları."""

    def test_84_questions_loaded(self):
        qs = isg_v1.load_seed_questions()
        assert len(qs) == 84

    def test_9_unique_categories(self):
        qs = isg_v1.load_seed_questions()
        cats = {q["category"] for q in qs}
        assert len(cats) == 9
        # Kategori adları boş olmamalı
        assert all(c.strip() for c in cats)

    def test_id_range_1_to_84_unique_consecutive(self):
        qs = isg_v1.load_seed_questions()
        ids = [q["id"] for q in qs]
        assert ids == list(range(1, 85))
        assert len(set(ids)) == 84

    def test_no_range_1_to_84_unique_consecutive(self):
        qs = isg_v1.load_seed_questions()
        nos = [q["no"] for q in qs]
        assert nos == list(range(1, 85))
        assert len(set(nos)) == 84

    def test_id_and_no_are_equal(self):
        qs = isg_v1.load_seed_questions()
        for q in qs:
            assert q["id"] == q["no"], f"soru {q['id']}: id != no"

    def test_required_fields_present(self):
        qs = isg_v1.load_seed_questions()
        required = (
            "id", "no", "category", "area", "question", "responsible",
            "default_probability", "default_severity", "default_risk_score",
            "default_risk_level", "document_risk_level",
            "deadline", "legal_basis", "corrective_action",
        )
        for q in qs:
            for key in required:
                assert key in q, f"soru {q.get('id')}: {key} eksik"
                assert q[key] is not None, f"soru {q.get('id')}: {key} None"

    def test_default_probability_and_severity_in_range(self):
        qs = isg_v1.load_seed_questions()
        for q in qs:
            assert 1 <= q["default_probability"] <= 5
            assert 1 <= q["default_severity"] <= 5

    def test_default_risk_score_equals_prob_times_sev(self):
        qs = isg_v1.load_seed_questions()
        for q in qs:
            assert (
                q["default_risk_score"]
                == q["default_probability"] * q["default_severity"]
            ), f"soru {q['id']}: score != p*s"

    def test_legal_basis_not_empty(self):
        qs = isg_v1.load_seed_questions()
        for q in qs:
            assert q["legal_basis"], f"soru {q['id']}: legal_basis boş"

    def test_corrective_action_not_empty(self):
        qs = isg_v1.load_seed_questions()
        for q in qs:
            assert q["corrective_action"], f"soru {q['id']}: corrective_action boş"

    def test_no_duplicate_question_ids(self):
        qs = isg_v1.load_seed_questions()
        ids = [q["id"] for q in qs]
        assert len(ids) == len(set(ids)), "duplicate question id"


class TestTemplateDocBuilder:
    """``build_template_doc`` Mongo dokümanı doğru üretir."""

    def test_template_code_is_stable(self):
        """Şablon kodu bağlayıcı sabittir (unique index anchor)."""
        assert isg_v1.TEMPLATE_CODE == "isg_v1_default"

    def test_build_template_doc_has_required_fields(self):
        doc = isg_v1.build_template_doc()
        assert doc["code"] == isg_v1.TEMPLATE_CODE
        assert doc["is_default"] is True
        assert doc["version"] == 1
        assert isinstance(doc["questions"], list)
        assert len(doc["questions"]) == 84
        assert isinstance(doc["name"], str) and doc["name"]


class TestSeedValidationFailure:
    """Seed dosyası bozuksa → ``SeedValidationError`` (fail-fast)."""

    def test_missing_file_raises(self):
        with patch.object(isg_v1, "_SEED_FILE", Path("/nonexistent/seed.json")):
            with pytest.raises(isg_v1.SeedValidationError):
                isg_v1.load_seed_questions()

    def test_invalid_json_raises(self, tmp_path):
        bogus = tmp_path / "bogus.json"
        bogus.write_text("{not valid json", encoding="utf-8")
        with patch.object(isg_v1, "_SEED_FILE", bogus):
            with pytest.raises(isg_v1.SeedValidationError):
                isg_v1.load_seed_questions()

    def test_wrong_count_raises(self, tmp_path):
        bogus = tmp_path / "short.json"
        bogus.write_text(json.dumps([{"id": 1, "no": 1}]), encoding="utf-8")
        with patch.object(isg_v1, "_SEED_FILE", bogus):
            with pytest.raises(isg_v1.SeedValidationError):
                isg_v1.load_seed_questions()