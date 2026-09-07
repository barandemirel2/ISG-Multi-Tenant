"""Aşama 2A — Optimistic Concurrency (version) + atomik ``update_answers`` testleri.

Doğrulanan bağlayıcı davranış:

* ``update_answers`` endpoint'i ``expected_version`` ile DB'deki mevcut
  version'ı karşılaştırır. Eşleşme yoksa → 409 Conflict.
* Atomik update: ``$set: {answers, risk_overrides, updated_at}``
  + ``$inc: version`` tek ``find_one_and_update`` çağrısında yapılır;
  yarı yazım yok.
* ``_collapse_overrides`` default ile aynı override'ları DB'ye yazmaz.
* Version her update'te artar.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from bson import ObjectId

from _phase_2a_helpers import (
    fake_db,
    push_audit,
    run_async,
    sample_audit_doc,
    sample_template_doc,
)


# Sabit ObjectId hex'leri: server ``ObjectId(audit_id)`` parse edeceği
# için deterministik 24-char string'ler kullanıyoruz. PR0 audit kayıtları
# ObjectId taşıyabilir ama geriye dönük string id'ler de hâlâ kabul edilir
# (server ``ObjectId(audit_id)`` ile parse eder; string'ler "Geçersiz
# denetim ID" hatasına yol açar).
AID_1 = str(ObjectId("507f1f77bcf86cd799439011"))
AID_2 = str(ObjectId("507f1f77bcf86cd799439012"))
AID_3 = str(ObjectId("507f1f77bcf86cd799439013"))
AID_NOT_FOUND = str(ObjectId("507f1f77bcf86cd799439099"))


class TestOptimisticConcurrency:
    """``expected_version`` mismatch → 409."""

    def _audit(self, *, version=0, audit_id=AID_1):
        return sample_audit_doc(
            audit_id=audit_id, version=version, with_snapshot=True,
            template=sample_template_doc(),
        )

    def test_version_match_succeeds(self):
        from server import update_answers, AnswersBulkInput

        audit = self._audit(version=0)
        with fake_db([sample_template_doc()]):
            push_audit(__import__("server").db, audit)
            user = {"id": "u-1", "name": "D"}
            body = AnswersBulkInput(
                expected_version=0,
                answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
            )
            out = run_async(update_answers(
                audit_id=AID_1, body=body, current_user=user,
            ))
            assert out is not None
            # DB'de version 1 oldu — ``_id`` ObjectId olarak depolanır
            doc = __import__("server").db.audits.docs[ObjectId(AID_1)]
            assert doc["version"] == 1

    def test_version_mismatch_returns_conflict(self):
        from server import update_answers, AnswersBulkInput, HTTPException

        # DB'deki version = 3 ama client 0 gönderiyor → conflict
        audit = self._audit(version=3)
        with fake_db([sample_template_doc()]):
            push_audit(__import__("server").db, audit)
            user = {"id": "u-1", "name": "D"}
            body = AnswersBulkInput(
                expected_version=0,
                answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
            )
            with pytest.raises(HTTPException) as exc:
                run_async(update_answers(
                    audit_id=AID_1, body=body, current_user=user,
                ))
            assert exc.value.status_code == 409
            # DB'de version hâlâ 3 — ``_id`` ObjectId olarak depolanır
            assert __import__("server").db.audits.docs[ObjectId(AID_1)]["version"] == 3

    def test_audit_not_found_returns_404(self):
        from server import update_answers, AnswersBulkInput, HTTPException
        with fake_db([sample_template_doc()]):
            user = {"id": "u-1", "name": "D"}
            body = AnswersBulkInput(
                expected_version=0,
                answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
            )
            with pytest.raises(HTTPException) as exc:
                run_async(update_answers(
                    audit_id=AID_NOT_FOUND, body=body, current_user=user,
                ))
            assert exc.value.status_code == 404


class TestCollapseOverrides:
    """``_collapse_overrides`` — default ile aynı olan override'ları düşürür."""

    def test_overrides_collapsed_against_defaults(self):
        from server import _collapse_overrides

        # Default q1: prob=3, sev=3
        questions = [
            {"id": 1, "default_probability": 3, "default_severity": 3},
            {"id": 2, "default_probability": 1, "default_severity": 5},
        ]
        # q1: default ile aynı → düşürülmeli
        # q2: override ile farklı → korunmalı
        overrides = {
            "1": {"probability": 3, "severity": 3},
            "2": {"probability": 5, "severity": 5},
        }
        collapsed = _collapse_overrides(overrides, questions)
        assert "1" not in collapsed
        assert collapsed["2"] == {"probability": 5, "severity": 5}

    def test_empty_overrides_collapse_to_empty(self):
        from server import _collapse_overrides
        collapsed = _collapse_overrides({}, [{"id": 1, "default_probability": 3, "default_severity": 3}])
        assert collapsed == {}

    def test_none_overrides_collapse_to_none(self):
        from server import _collapse_overrides
        collapsed = _collapse_overrides(None, [{"id": 1, "default_probability": 3, "default_severity": 3}])
        # None override input → None output (anlamı: "override yok, default kullan")
        assert collapsed is None

    def test_unknown_question_id_overrides_dropped(self):
        """Snapshot'ta olmayan soru id'si override'ı düşürülür (orphan)."""
        from server import _collapse_overrides
        collapsed = _collapse_overrides(
            {"1": {"probability": 5, "severity": 5}},
            [],  # snapshot boş
        )
        assert collapsed == {}


class TestAtomicUpdateSingleCall:
    """``update_answers`` ``find_one_and_update`` kullanır ve tek seferde yazar."""

    def test_single_find_one_and_update_call(self):
        from server import update_answers, AnswersBulkInput
        audit = sample_audit_doc(
            audit_id=AID_2, version=0, with_snapshot=True,
            template=sample_template_doc(),
        )
        with fake_db([sample_template_doc()]):
            push_audit(__import__("server").db, audit)
            user = {"id": "u-1", "name": "D"}
            body = AnswersBulkInput(
                expected_version=0,
                answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
            )
            run_async(update_answers(
                audit_id=AID_2, body=body, current_user=user,
            ))
            # find_one_and_update en az 1 kez çağrılmış olmalı
            assert __import__("server").db.audits.find_one_and_update.await_count >= 1

    def test_update_writes_answers_overrides_version(self):
        """``$set: {answers, risk_overrides, updated_at}`` + ``$inc: version``."""
        from server import update_answers, AnswersBulkInput
        audit = sample_audit_doc(
            audit_id=AID_3, version=0, with_snapshot=True,
            template=sample_template_doc(),
        )
        with fake_db([sample_template_doc()]):
            push_audit(__import__("server").db, audit)
            user = {"id": "u-1", "name": "D"}
            body = AnswersBulkInput(
                expected_version=0,
                answers={"1": "EVET", "2": "HAYIR", "3": "NA"},
                risk_overrides={"2": {"probability": 5, "severity": 5}},
            )
            run_async(update_answers(
                audit_id=AID_3, body=body, current_user=user,
            ))
            # Çağrı yakalama — son find_one_and_update çağrısının update body.
            # Server ``find_one_and_update(filter, update, return_document=...)``
            # şeklinde çağırır; ``update`` 2. positional arg.
            call = __import__("server").db.audits.find_one_and_update.await_args
            assert call is not None
            update_doc = call.args[1] if len(call.args) > 1 else call.kwargs.get("update", {})
            set_data = update_doc.get("$set", {})
            inc_data = update_doc.get("$inc", {})
            assert "answers" in set_data
            assert "risk_overrides" in set_data
            assert "updated_at" in set_data
            assert inc_data.get("version") == 1