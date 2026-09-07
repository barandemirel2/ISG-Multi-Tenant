"""Aşama 2A — ``AnswersBulkInput.risk_overrides`` Pydantic validation testleri.

Bu testler **saf Pydantic validation**: DB'ye dokunmazlar.

Doğrulanan kurallar:

* ``risk_overrides`` opsiyonel (``None`` veya yokluk → geçer)
* Empty dict → geçer
* ``probability`` ve ``severity`` strict int 1-5 arası → geçer
* Yanlış tip, aralık dışı, bool → ``ValidationError``
* ``risk_score`` / ``risk_level`` alanları client tarafından gönderilemez
* Geçersiz question_id (snapshot'ta yoksa) endpoints seviyesinde → 400
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from pydantic import ValidationError

from server import AnswersBulkInput


class TestRiskOverridesValidation:
    """``AnswersBulkInput`` ``risk_overrides`` alanı."""

    def _make(self, **overrides):
        defaults = dict(
            expected_version=0,
            answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
        )
        defaults.update(overrides)
        return defaults

    # ---- Geçerli durumlar ----

    def test_none_is_accepted(self):
        body = AnswersBulkInput(**self._make(risk_overrides=None))
        assert body.risk_overrides is None

    def test_missing_field_is_accepted(self):
        # risk_overrides opsiyonel — yok da geçerli
        kwargs = self._make()
        kwargs.pop("risk_overrides", None)
        body = AnswersBulkInput(**kwargs)
        assert body.risk_overrides is None

    def test_empty_dict_is_accepted(self):
        body = AnswersBulkInput(**self._make(risk_overrides={}))
        assert body.risk_overrides == {}

    def test_valid_pair(self):
        body = AnswersBulkInput(**self._make(
            risk_overrides={"1": {"probability": 3, "severity": 4}}
        ))
        assert body.risk_overrides == {"1": {"probability": 3, "severity": 4}}

    def test_valid_min_max_boundaries(self):
        body = AnswersBulkInput(**self._make(
            risk_overrides={
                "1": {"probability": 1, "severity": 1},
                "84": {"probability": 5, "severity": 5},
            }
        ))
        assert body.risk_overrides["1"]["probability"] == 1
        assert body.risk_overrides["84"]["severity"] == 5

    # ---- Tip hataları ----

    @pytest.mark.parametrize("bad", [
        "3", 3.0, [3], {"p": 3},
    ])
    def test_probability_strict_int_rejected(self, bad):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(risk_overrides={"1": {"probability": bad, "severity": 3}}))

    def test_bool_rejected_as_probability(self):
        """bool strict int sayılmaz; ``True`` (==1) reddedilir."""
        for bad in (True, False):
            with pytest.raises(ValidationError):
                AnswersBulkInput(**self._make(
                    risk_overrides={"1": {"probability": bad, "severity": 3}}
                ))

    def test_string_severity_rejected(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"probability": 3, "severity": "4"}}
            ))

    # ---- Aralık hataları ----

    @pytest.mark.parametrize("bad_prob", [0, 6, 100, -1])
    def test_probability_out_of_range_rejected(self, bad_prob):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"probability": bad_prob, "severity": 3}}
            ))

    @pytest.mark.parametrize("bad_sev", [0, 6, 100, -1])
    def test_severity_out_of_range_rejected(self, bad_sev):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"probability": 3, "severity": bad_sev}}
            ))

    # ---- Yasaklı alanlar (score / level) ----

    def test_risk_score_field_rejected(self):
        with pytest.raises(ValidationError) as exc:
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"probability": 3, "severity": 3, "risk_score": 9}}
            ))
        assert "risk_score" in str(exc.value).lower() or "client" in str(exc.value).lower()

    def test_risk_level_field_rejected(self):
        with pytest.raises(ValidationError) as exc:
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"probability": 3, "severity": 3, "risk_level": "Kabul Edilebilir"}}
            ))

    # ---- Yapı hataları ----

    def test_override_must_be_dict(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(risk_overrides=["not", "a", "dict"]))

    def test_override_pair_must_be_dict(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(risk_overrides={"1": "not-a-dict"}))

    def test_override_pair_missing_severity(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"probability": 3}}
            ))

    def test_override_pair_missing_probability(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(
                risk_overrides={"1": {"severity": 3}}
            ))

    def test_override_pair_none_value_rejected_by_pydantic(self):
        """``{qid: None}`` Pydantic tarafından reddedilir (Dict[str, Dict] şeması).

        Yani override temizleme istemcide ``None`` yerine boş dict
        gönderilerek yapılmalıdır; Pydantic seviyesinde None kabul edilmez.
        Endpoint bu rejection'ı 400 olarak yayar.
        """
        with pytest.raises(ValidationError):
            AnswersBulkInput(**self._make(risk_overrides={"1": None}))


class TestAnswersExistingValidation:
    """``AnswersBulkInput`` temel ``answers`` validasyonu değişmedi (regression guard)."""

    def test_empty_answers_rejected(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(expected_version=0, answers={})

    def test_invalid_answer_value_rejected(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(expected_version=0, answers={"1": "BELKI"})

    def test_invalid_question_id_rejected(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(expected_version=0, answers={"abc": "EVET"})

    def test_negative_version_rejected(self):
        with pytest.raises(ValidationError):
            AnswersBulkInput(expected_version=-1, answers={"1": "EVET"})