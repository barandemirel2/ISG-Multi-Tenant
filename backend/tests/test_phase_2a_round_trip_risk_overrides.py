"""Aşama 2A — ``risk_overrides`` round-trip testleri.

Doğrulanan bağlayıcı davranış:

* Snapshot'lı yeni audit oluşturma → response içinde ``risk_overrides``
  alanı ``{}`` ile başlar.
* ``PUT /audits/{id}/answers`` çağrısı snapshot varsa cevapların + override'ların
  tek atomik update ile yazılması:

  - default olmayan override DB'ye yazılır;
  - default'a eşit olan override **collapse** edilir (DB'de bulunmaz);
  - ``risk_overrides`` alanı request'te yoksa (None) → mevcut override'lar
    **korunur**;
  - ``risk_overrides={}`` gönderilirse → mevcut override'lar bilinçli olarak
    **temizlenir**.

* ``PUT`` response'unda döndürülen ``risk_overrides`` ve ``summary`` ile
  takip eden ``GET /audits/{id}`` response'u **bire bir aynı** olmalı.
* Her PUT sonrası ``version`` tam +1 artar (iki ardışık PUT → +2).
* Effective risk score / level, ``HAYIR`` cevabı olan soru için
  ``override`` değerleri kullanılarak kanonik eşiklere göre hesaplanır.

Bu testler **deterministik 3 soruluk minimal template** kullanır (q1, q2, q3)
böylece override math'ı insan tarafından doğrulanabilir:

    q1: default prob=1 sev=1 → skor 1  → "Kabul Edilebilir"
    q2: default prob=3 sev=4 → skor 12 → "Dikkate Değer"
    q3: default prob=5 sev=5 → skor 25 → "Kabul Edilemez"
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
    sample_questions,
    sample_template_doc,
)


# Deterministik ObjectId — server ``ObjectId(audit_id)`` parse eder.
AID = str(ObjectId("507f1f77bcf86cd799439040"))


def _minimal_template():
    """3 soruluk deterministik template — q1=(1,1), q2=(3,4), q3=(5,5)."""
    return sample_template_doc(questions=sample_questions(minimal=True))


def _audit_doc(version=0):
    return sample_audit_doc(
        audit_id=AID, version=version, with_snapshot=True,
        template=_minimal_template(),
    )


def _user():
    return {"id": "u-1", "name": "Denetçi 1"}


def _hayir_summary(out, qid):
    """HAYIR cevaplanan bir sorunun summary satırını döndürür."""
    return next(h for h in out["summary"]["hayir_questions"] if h["soru_no"] == qid)


# ---------------------------------------------------------------------------
# A) Round-trip başarı senaryosu
# ---------------------------------------------------------------------------


class TestOverrideRoundTrip:
    """``PUT → GET`` aynı override çiftini döndürür; version yalnız +1."""

    def test_put_then_get_returns_identical_overrides(self):
        from server import update_answers, get_audit, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # 1) PUT — q2 (default 3/4 → skor 12 → "Dikkate Değer") HAYIR +
            #    override (5,5) → skor 25 → "Kabul Edilemez".
            put_body = AnswersBulkInput(
                expected_version=0,
                answers={"2": "HAYIR"},
                risk_overrides={"2": {"probability": 5, "severity": 5}},
            )
            put_out = run_async(update_answers(
                audit_id=AID, body=put_body, current_user=user,
            ))
            assert put_out is not None

            # 1a) PUT response içinde override doğru dönmeli.
            assert put_out["risk_overrides"] == {"2": {"probability": 5, "severity": 5}}
            assert put_out["answers"] == {"2": "HAYIR"}
            assert put_out["version"] == 1

            # 1b) Effective risk summary override ile yeniden hesaplanmalı.
            q2_summary = _hayir_summary(put_out, 2)
            assert q2_summary["probability"] == 5
            assert q2_summary["severity"] == 5
            assert q2_summary["risk_score"] == 25
            assert q2_summary["risk_level"] == "Kabul Edilemez"
            # Kabul Edilemez sayımı artmalı.
            assert put_out["summary"]["risk_counts"]["Kabul Edilemez"] == 1

            # 2) GET — server'dan tekrar oku; aynı payload gelmeli.
            get_out = run_async(get_audit(audit_id=AID, current_user=user))
            assert get_out is not None
            assert get_out["risk_overrides"] == {"2": {"probability": 5, "severity": 5}}
            assert get_out["answers"] == {"2": "HAYIR"}
            assert get_out["version"] == 1

            # 2a) GET snapshot da döner; audit kendi snapshot'ından beslenir.
            assert get_out.get("is_legacy") is False
            assert "template_snapshot" in get_out

            # 2b) GET summary de aynı effective değerleri göstermeli.
            q2_get = _hayir_summary(get_out, 2)
            assert q2_get["risk_score"] == 25
            assert q2_get["risk_level"] == "Kabul Edilemez"


# ---------------------------------------------------------------------------
# B) Default'a eşit override → collapse
# ---------------------------------------------------------------------------


class TestOverrideCollapseAgainstDefaults:
    """Default'a eşit override DB'ye yazılmaz; GET sonrası görünmez."""

    def test_default_equal_override_is_collapsed(self):
        from server import update_answers, get_audit, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # q2 default = (3, 4). Override default'la birebir aynı → yazılmaz.
            put_body = AnswersBulkInput(
                expected_version=0,
                answers={"2": "HAYIR"},
                risk_overrides={"2": {"probability": 3, "severity": 4}},
            )
            put_out = run_async(update_answers(
                audit_id=AID, body=put_body, current_user=user,
            ))
            # Response'da collapse edilmiş halde dönmeli.
            assert put_out["risk_overrides"] == {}

            # DB dokümanında risk_overrides alanı boş olmalı (yok veya {}).
            doc = __import__("server").db.audits.docs[ObjectId(AID)]
            assert doc.get("risk_overrides", {}) == {}

            # GET — aynı şekilde boş kalmalı.
            get_out = run_async(get_audit(audit_id=AID, current_user=user))
            assert get_out["risk_overrides"] == {}

            # Effective skor default üzerinden hesaplanmalı (3×4=12 → "Dikkate Değer").
            q2_get = _hayir_summary(get_out, 2)
            assert q2_get["risk_score"] == 12
            assert q2_get["risk_level"] == "Dikkate Değer"

    def test_mixed_overrides_partial_collapse(self):
        """Karışık override'larda yalnız default'tan farklı olanlar kalır."""
        from server import update_answers, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # q1 default (1,1) → eşit gönderilir → collapse.
            # q2 default (3,4) → override (5,5) → kalır.
            # q3 default (5,5) → override (2,2) → kalır (default'tan farklı).
            put_body = AnswersBulkInput(
                expected_version=0,
                answers={"1": "HAYIR", "2": "HAYIR", "3": "HAYIR"},
                risk_overrides={
                    "1": {"probability": 1, "severity": 1},  # default → collapse
                    "2": {"probability": 5, "severity": 5},
                    "3": {"probability": 2, "severity": 2},
                },
            )
            put_out = run_async(update_answers(
                audit_id=AID, body=put_body, current_user=user,
            ))
            assert put_out["risk_overrides"] == {
                "2": {"probability": 5, "severity": 5},
                "3": {"probability": 2, "severity": 2},
            }


# ---------------------------------------------------------------------------
# C) risk_overrides gönderilmezse → mevcut korunur
# ---------------------------------------------------------------------------


class TestRiskOverridesPreserveWhenOmitted:
    """``risk_overrides`` alanı request'te yok → DB'deki değerler korunur."""

    def test_omitted_field_preserves_existing_overrides(self):
        from server import update_answers, get_audit, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # 1) İlk PUT — override yaz.
            run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 5, "severity": 5}},
                ),
                current_user=user,
            ))
            assert __import__("server").db.audits.docs[ObjectId(AID)]["version"] == 1

            # 2) İkinci PUT — yalnız answers değişir; risk_overrides alanı
            #    gönderilmez (None). Override korunmalı.
            put_body = AnswersBulkInput(
                expected_version=1,
                answers={"2": "HAYIR", "3": "HAYIR"},
                # risk_overrides alanı request'te hiç yok → None semantiği
            )
            put_out = run_async(update_answers(
                audit_id=AID, body=put_body, current_user=user,
            ))
            # Response'ta mevcut override kalmalı.
            assert put_out["risk_overrides"] == {"2": {"probability": 5, "severity": 5}}
            assert put_out["version"] == 2

            # GET ile doğrula.
            get_out = run_async(get_audit(audit_id=AID, current_user=user))
            assert get_out["risk_overrides"] == {"2": {"probability": 5, "severity": 5}}
            assert get_out["version"] == 2


# ---------------------------------------------------------------------------
# D) risk_overrides={} → bilinçli temizleme
# ---------------------------------------------------------------------------


class TestRiskOverridesExplicitClear:
    """``risk_overrides={}`` → mevcut override'lar silinir."""

    def test_empty_dict_clears_overrides(self):
        from server import update_answers, get_audit, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # 1) Önce override yaz.
            run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 5, "severity": 5}},
                ),
                current_user=user,
            ))

            # 2) Şimdi bilinçli olarak boş gönder → temizle.
            put_body = AnswersBulkInput(
                expected_version=1,
                answers={"2": "HAYIR"},
                risk_overrides={},
            )
            put_out = run_async(update_answers(
                audit_id=AID, body=put_body, current_user=user,
            ))
            assert put_out["risk_overrides"] == {}
            assert put_out["version"] == 2

            get_out = run_async(get_audit(audit_id=AID, current_user=user))
            assert get_out["risk_overrides"] == {}

            # Effective skor artık default'a (3,4 → 12) dönmüş olmalı.
            q2_get = _hayir_summary(get_out, 2)
            assert q2_get["risk_score"] == 12
            assert q2_get["risk_level"] == "Dikkate Değer"


# ---------------------------------------------------------------------------
# E) Version invariant'ı — yalnız +1
# ---------------------------------------------------------------------------


class TestVersionInvariant:
    """Her başarılı PUT version'ı tam +1 artırır; collapse/preserve bunu değiştirmez."""

    def test_two_puts_increment_version_by_two(self):
        from server import update_answers, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 5, "severity": 5}},
                ),
                current_user=user,
            ))
            assert __import__("server").db.audits.docs[ObjectId(AID)]["version"] == 1

            # İkinci PUT — yalnız answers değişir, override gönderilmez.
            run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=1,
                    answers={"2": "HAYIR", "3": "NA"},
                ),
                current_user=user,
            ))
            assert __import__("server").db.audits.docs[ObjectId(AID)]["version"] == 2

    def test_collapse_still_increments_version(self):
        """Default'a eşit override gönderildiğinde de version artar."""
        from server import update_answers, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 3, "severity": 4}},  # default
                ),
                current_user=user,
            ))
            doc = __import__("server").db.audits.docs[ObjectId(AID)]
            assert doc["version"] == 1
            # Collapse sonrası override yazılmamış olmalı.
            assert doc.get("risk_overrides", {}) == {}


# ---------------------------------------------------------------------------
# F) Kanonik eşik doğrulaması — override farklı seviyelere taşıyabilir
# ---------------------------------------------------------------------------


class TestCanonicalThresholdsEffectiveRisk:
    """Override'lar effective skor/level'i kanonik eşiklere göre taşır.

    Aşama 1 eşikleri:

    * 1–4   → "Kabul Edilebilir"
    * 5–12  → "Dikkate Değer"
    * 13–25 → "Kabul Edilemez"
    """

    def test_override_low_score_stays_low(self):
        from server import update_answers, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # q2 default (3,4) → override (1,2) → skor 2 → "Kabul Edilebilir".
            out = run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 1, "severity": 2}},
                ),
                current_user=user,
            ))
            q2 = _hayir_summary(out, 2)
            assert q2["risk_score"] == 2
            assert q2["risk_level"] == "Kabul Edilebilir"

    def test_override_medium_score_stays_medium(self):
        from server import update_answers, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # q2 default (3,4) → override (2,3) → skor 6 → "Dikkate Değer".
            out = run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 2, "severity": 3}},
                ),
                current_user=user,
            ))
            q2 = _hayir_summary(out, 2)
            assert q2["risk_score"] == 6
            assert q2["risk_level"] == "Dikkate Değer"

    def test_override_high_score_promotes_to_high(self):
        from server import update_answers, AnswersBulkInput

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # q2 default (3,4) → override (4,4) → skor 16 → "Kabul Edilemez".
            out = run_async(update_answers(
                audit_id=AID,
                body=AnswersBulkInput(
                    expected_version=0,
                    answers={"2": "HAYIR"},
                    risk_overrides={"2": {"probability": 4, "severity": 4}},
                ),
                current_user=user,
            ))
            q2 = _hayir_summary(out, 2)
            assert q2["risk_score"] == 16
            assert q2["risk_level"] == "Kabul Edilemez"
            assert out["summary"]["risk_counts"]["Kabul Edilemez"] == 1
            assert out["summary"]["risk_counts"]["Dikkate Değer"] == 0


# ---------------------------------------------------------------------------
# G) Snapshot kaynak kullanımı — kendi snapshot'ından validate eder
# ---------------------------------------------------------------------------


class TestSnapshotSourceUsage:
    """Override validation audit'in kendi snapshot'ından gelir; global QUESTIONS'a değil."""

    def test_override_for_unknown_question_id_rejected(self):
        from server import update_answers, AnswersBulkInput, HTTPException

        audit = _audit_doc(version=0)
        with fake_db([_minimal_template()]):
            push_audit(__import__("server").db, audit)
            user = _user()

            # Snapshot'ta 999 yok → 400.
            with pytest.raises(HTTPException) as exc:
                run_async(update_answers(
                    audit_id=AID,
                    body=AnswersBulkInput(
                        expected_version=0,
                        answers={"1": "EVET"},
                        risk_overrides={"999": {"probability": 5, "severity": 5}},
                    ),
                    current_user=user,
                ))
            assert exc.value.status_code == 400