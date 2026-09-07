"""U2 Question Audit Remediation Comprehensive Regression Tests.

Tests cover:
  1. Post-fix invariant for 4 questions (9, 29, 30, 61): positive wording, EVET=compliant, HAYIR=non-compliant.
  2. Question file integrity (84 questions identical between questions.json and seed/isg_v1_default_questions.json).
  3. New audits receive positive wording from default template snapshot.
  4. Unanswered DRAFT audits receive safe snapshot text updates.
  5. Answered legacy EVET questions are NOT silently reinterpreted (skipped for manual review).
  6. Answered legacy HAYIR questions (with or without DÖF) are NOT silently reinterpreted (skipped for manual review).
  7. Existing DÖF / user notes / details are strictly preserved.
  8. FINAL historical audits remain completely untouched.
  9. Migration script is idempotent.
  10. Dry-run mode produces zero database writes while computing accurate statistics.
  11. Migration script handles optional fields and raises on corrupt document shapes.
  12. Documentation (TAB_GIDA_ISG_Denetim_Risk_Analizi_Soruları.md) aligns with canonical questions.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-with-at-least-32-chars-for-entropy-ok")

import server
from scripts.update_question_texts import QUESTION_UPDATES, run_migration, _is_answered
from tests._phase_2a_helpers import FakeCursor


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------
OLD_TEXTS = {
    9: "Hijyen Eğitimi Belgesi bulunmayan personel çalıştırılmakta mıdır?",
    15: "Acil çıkış yolları ve merdivenlerinde malzeme depolaması yapılmakta mıdır?",
    26: "Kablolarda ek, aşınma, soyulma veya açıkta iletken tel bulunmakta mıdır?",
    27: "Seyyar uzatma kabloları ve çoklu prizler kalıcı tesisat gibi kullanılmakta mıdır?",
    29: "Aydınlatma armatürlerinin etrafında kırık veya sarkma var mıdır?",
    30: "Elektrik arıza ve bakım işlemleri Yetkili Elektrik Personeli dışında kişilerce yapılıyor mu?",
    58: "Çalışanlar ziynet eşyası, yüzük, saat vb. aksesuarlarla çalışmakta mıdır?",
    61: "Mutfak ve servis zeminlerinde kırık karo, çukur veya takılma riski oluşturan deformasyon var mıdır?",
    68: "Mutfak ve depo tavanlarında nem, küf, sıva döküntüsü veya su sızıntısı var mıdır?",
}


def load_canonical_questions() -> List[Dict[str, Any]]:
    with open(BACKEND_DIR / "questions.json", "r", encoding="utf-8") as f:
        return json.load(f)


def build_legacy_questions() -> List[Dict[str, Any]]:
    qs = copy.deepcopy(load_canonical_questions())
    for q in qs:
        qid = q["id"]
        if qid in OLD_TEXTS:
            q["question"] = OLD_TEXTS[qid]
    return qs


class MockDB:
    """Stateful mock for db.templates and db.audits."""

    def __init__(
        self,
        templates: Optional[List[Dict[str, Any]]] = None,
        audits: Optional[List[Dict[str, Any]]] = None,
    ):
        self.templates_data: Dict[str, Dict[str, Any]] = {
            t.get("code", str(t.get("_id", i))): copy.deepcopy(t)
            for i, t in enumerate(templates or [])
        }
        self.audits_data: Dict[str, Dict[str, Any]] = {
            str(a["_id"]): copy.deepcopy(a)
            for a in (audits or [])
        }

        # Collection mocks
        self.templates = MagicMock()
        self.templates.find_one = AsyncMock(side_effect=self._template_find_one)
        self.templates.update_one = AsyncMock(side_effect=self._template_update_one)

        self.audits = MagicMock()
        self.audits.find = MagicMock(side_effect=self._audit_find)
        self.audits.find_one = AsyncMock(side_effect=self._audit_find_one)
        self.audits.update_one = AsyncMock(side_effect=self._audit_update_one)
        self.audits.insert_one = AsyncMock(side_effect=self._audit_insert_one)

    async def _template_find_one(self, filter_dict: Dict[str, Any], *args, **kwargs):
        code = filter_dict.get("code")
        if code in self.templates_data:
            return copy.deepcopy(self.templates_data[code])
        return None

    async def _template_update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], *args, **kwargs):
        code = filter_dict.get("code")
        if code in self.templates_data:
            if "$set" in update_dict:
                for k, v in update_dict["$set"].items():
                    self.templates_data[code][k] = copy.deepcopy(v)
            return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)

    def _audit_find(self, filter_dict: Optional[Dict[str, Any]] = None, *args, **kwargs):
        items = [copy.deepcopy(doc) for doc in self.audits_data.values()]
        return FakeCursor(items)

    async def _audit_find_one(self, filter_dict: Dict[str, Any], *args, **kwargs):
        oid = filter_dict.get("_id")
        key = str(oid)
        if key in self.audits_data:
            return copy.deepcopy(self.audits_data[key])
        return None

    async def _audit_update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], *args, **kwargs):
        oid = filter_dict.get("_id")
        key = str(oid)
        if key in self.audits_data:
            if "$set" in update_dict:
                for k, v in update_dict["$set"].items():
                    # Handle nested paths like "template_snapshot.questions"
                    if "." in k:
                        parts = k.split(".")
                        target = self.audits_data[key]
                        for p in parts[:-1]:
                            target = target.setdefault(p, {})
                        target[parts[-1]] = copy.deepcopy(v)
                    else:
                        self.audits_data[key][k] = copy.deepcopy(v)
            return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)

    async def _audit_insert_one(self, doc: Dict[str, Any], *args, **kwargs):
        doc_copy = copy.deepcopy(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = ObjectId()
        self.audits_data[str(doc_copy["_id"])] = doc_copy
        return MagicMock(inserted_id=doc_copy["_id"])


# ---------------------------------------------------------------------------
# 1. Post-fix Canonical Questions Invariant & Alignment Tests
# ---------------------------------------------------------------------------
class TestQuestionFileIntegrity:
    """Verify questions.json and seed/isg_v1_default_questions.json integrity."""

    def test_canonical_and_seed_are_byte_identical(self):
        q_path = BACKEND_DIR / "questions.json"
        seed_path = BACKEND_DIR / "seed" / "isg_v1_default_questions.json"

        assert q_path.exists(), "backend/questions.json missing"
        assert seed_path.exists(), "backend/seed/isg_v1_default_questions.json missing"

        with open(q_path, "r", encoding="utf-8") as f1, open(seed_path, "r", encoding="utf-8") as f2:
            q_data = json.load(f1)
            seed_data = json.load(f2)

        assert q_data == seed_data, "questions.json and seed file must be identical"

    def test_all_84_questions_ordered_and_numbered(self):
        questions = load_canonical_questions()
        assert len(questions) == 84

        for idx, q in enumerate(questions, start=1):
            assert q["id"] == idx, f"Question id {q['id']} != {idx}"
            assert q["no"] == idx, f"Question no {q['no']} != {idx}"
            assert "category" in q and q["category"]
            assert "question" in q and q["question"]
            assert "responsible" in q and q["responsible"]
            assert "legal_basis" in q and isinstance(q["legal_basis"], list)
            assert "corrective_action" in q and q["corrective_action"]
            assert q["default_probability"] in [1, 2, 3, 4, 5]
            assert q["default_severity"] in [1, 2, 3, 4, 5]
            assert q["default_risk_score"] == q["default_probability"] * q["default_severity"]

    def test_remediated_questions_have_positive_wording(self):
        questions_by_id = {q["id"]: q for q in load_canonical_questions()}

        for qid, expected_text in QUESTION_UPDATES.items():
            assert questions_by_id[qid]["question"] == expected_text, (
                f"Question {qid} does not have expected positive wording: {questions_by_id[qid]['question']}"
            )

    def test_u2_baseline_questions_strictly_preserved(self):
        """Non-negotiable rule: Q9, Q29, Q30, Q61 must remain exact current-main wording."""
        questions_by_id = {q["id"]: q for q in load_canonical_questions()}
        assert questions_by_id[9]["question"] == "Tüm personelin Hijyen Eğitimi Belgesi mevcut mudur?"
        assert questions_by_id[29]["question"] == "Aydınlatma armatürleri sağlam ve güvenli midir?"
        assert questions_by_id[30]["question"] == "Tüm elektrik arıza ve bakım işlemleri Yetkili Elektrik Personeli tarafından mı yapılmaktadır?"
        assert questions_by_id[61]["question"] == "Zeminler düzgün ve güvenli midir?"

    def test_batch_2_remediated_questions_positive_semantics(self):
        """Batch 2 remediated questions must have positive compliant semantics."""
        questions_by_id = {q["id"]: q for q in load_canonical_questions()}
        assert questions_by_id[15]["question"] == "Acil çıkış yolları ve merdivenleri malzeme depolanmasından arındırılmış, geçişe açık mıdır?"
        assert questions_by_id[26]["question"] == "Tüm kablolar yalıtımlı, sağlam ve kapalı mıdır (ek, aşınma, soyulma, açıkta iletken tel yok)?"
        assert questions_by_id[27]["question"] == "Seyyar uzatma kabloları ve çoklu prizler yalnızca geçici kullanım için mi kullanılmaktadır?"
        assert questions_by_id[58]["question"] == "Çalışanlar iş sırasında ziynet eşyası, yüzük, saat vb. aksesuarları çıkarmış mıdır?"
        assert questions_by_id[68]["question"] == "Mutfak ve depo tavanları nem, küf, sıva döküntüsü ve su sızıntısından arındırılmış mıdır?"


# ---------------------------------------------------------------------------
# 2. Markdown Documentation Alignment
# ---------------------------------------------------------------------------
class TestMarkdownDocAlignment:
    """Verify TAB_GIDA_ISG_Denetim_Risk_Analizi_Soruları.md matches canonical questions."""

    def test_markdown_contains_positive_wording(self):
        doc_path = BACKEND_DIR.parent / "TAB_GIDA_ISG_Denetim_Risk_Analizi_Soruları.md"
        assert doc_path.exists(), "TAB_GIDA_ISG_Denetim_Risk_Analizi_Soruları.md not found"

        content = doc_path.read_text(encoding="utf-8")

        for qid, text in QUESTION_UPDATES.items():
            assert text in content, f"Question {qid} positive text not found in markdown doc: {text}"

        for qid, old_text in OLD_TEXTS.items():
            assert old_text not in content, f"Old negative text for question {qid} still found in markdown: {old_text}"


# ---------------------------------------------------------------------------
# 3. New Audit Semantics Test
# ---------------------------------------------------------------------------
class TestNewAuditSemantics:
    """Verify new audits created from default template use positive wording and canonical semantics."""

    def test_new_audit_creation_gets_positive_wording(self):
        questions = load_canonical_questions()
        template_doc = {
            "code": "isg_v1_default",
            "name": "ABCD Tech Solutions İSG Risk Analiz Formu v1",
            "version": 1,
            "questions": questions,
        }
        mock_db = MockDB(templates=[template_doc])

        # Verify template questions in db
        tpl_q_by_id = {q["id"]: q for q in template_doc["questions"]}
        for qid, expected_text in QUESTION_UPDATES.items():
            assert tpl_q_by_id[qid]["question"] == expected_text

    def test_evet_is_compliant_and_hayir_generates_risk_in_summary(self):
        """Verify EVET has no risk, while HAYIR calculates risk."""
        questions = load_canonical_questions()
        audit_doc = {
            "_id": ObjectId(),
            "state": "DRAFT",
            "answers": {"9": "EVET", "29": "HAYIR"},
            "template_snapshot": {
                "template_code": "isg_v1_default",
                "questions": questions,
            },
        }

        # Calculate summary via server helper
        summary = server._summarize(audit_doc)
        assert summary["counts"]["EVET"] == 1
        assert summary["counts"]["HAYIR"] == 1
        assert summary["counts"]["unanswered"] == 82
        # Question 29 is HAYIR (O=2, S=3 -> R=6 -> Dikkate Değer)
        assert summary["risk_counts"]["Dikkate Değer"] >= 1
        # Question 9 is EVET -> No risk score contributed
        assert len(summary["hayir_questions"]) == 1
        assert summary["hayir_questions"][0]["soru_no"] == 29


# ---------------------------------------------------------------------------
# 4. Migration: Unanswered DRAFT Audits Safe Update
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestUnansweredDraftMigration:
    """Unanswered questions in DRAFT audits must receive safe wording correction."""

    async def test_unanswered_draft_updated_to_positive_wording(self):
        legacy_questions = build_legacy_questions()
        tpl_doc = {
            "code": "isg_v1_default",
            "questions": build_legacy_questions(),
        }
        draft_doc = {
            "_id": ObjectId(),
            "restaurant_name": "Test Burger King",
            "state": "DRAFT",
            "answers": {},  # Completely unanswered
            "template_snapshot": {
                "template_code": "isg_v1_default",
                "questions": copy.deepcopy(legacy_questions),
            },
        }

        mock_db = MockDB(templates=[tpl_doc], audits=[draft_doc])

        stats = await run_migration(mock_db, dry_run=False)

        assert stats["template_updated"] == 1
        assert stats["unanswered_audit_questions_updated"] == len(QUESTION_UPDATES)
        assert stats["answered_legacy_detected"] == 0
        assert stats["audits_skipped_manual_review"] == 0
        assert stats["already_correct_records"] == 0

        # Verify DB updated
        updated_audit = mock_db.audits_data[str(draft_doc["_id"])]
        q_map = {q["id"]: q["question"] for q in updated_audit["template_snapshot"]["questions"]}
        for qid, expected in QUESTION_UPDATES.items():
            assert q_map[qid] == expected


# ---------------------------------------------------------------------------
# 5. Migration: Answered Legacy Questions Safety Guard
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAnsweredLegacyAuditSafety:
    """Already-answered legacy questions must NOT be silently mutated and must be flagged for manual review."""

    async def test_answered_legacy_evet_is_not_mutated(self):
        legacy_questions = build_legacy_questions()
        tpl_doc = {
            "code": "isg_v1_default",
            "questions": load_canonical_questions(),
        }
        draft_doc = {
            "_id": ObjectId(),
            "restaurant_name": "Legacy Restoran EVET",
            "state": "DRAFT",
            "answers": {"9": "EVET"},  # Q9 answered under old negative wording
            "template_snapshot": {
                "template_code": "isg_v1_default",
                "questions": copy.deepcopy(legacy_questions),
            },
        }

        mock_db = MockDB(templates=[tpl_doc], audits=[draft_doc])

        stats = await run_migration(mock_db, dry_run=False)

        assert stats["answered_legacy_detected"] == 1
        assert stats["audits_skipped_manual_review"] == 1
        assert stats["unanswered_audit_questions_updated"] == 0
        assert len(stats["manual_review_audits"]) == 1
        assert stats["manual_review_audits"][0]["audit_id"] == str(draft_doc["_id"])

        # Audit snapshot must NOT have been changed in DB
        current_audit = mock_db.audits_data[str(draft_doc["_id"])]
        q9 = next(q for q in current_audit["template_snapshot"]["questions"] if q["id"] == 9)
        assert q9["question"] == OLD_TEXTS[9]
        assert current_audit["answers"]["9"] == "EVET"

    async def test_answered_legacy_hayir_with_dof_is_preserved(self):
        legacy_questions = build_legacy_questions()
        tpl_doc = {
            "code": "isg_v1_default",
            "questions": load_canonical_questions(),
        }
        draft_doc = {
            "_id": ObjectId(),
            "restaurant_name": "Legacy Restoran HAYIR DÖF",
            "state": "DOF_OPEN",
            "answers": {"29": "HAYIR"},
            "dof_details": {
                "29": {
                    "action_plan": "Armatür koruma glopları takılacak",
                    "status": "ACIK",
                    "active": True,
                    "target_date": "2026-09-01",
                }
            },
            "template_snapshot": {
                "template_code": "isg_v1_default",
                "questions": copy.deepcopy(legacy_questions),
            },
        }

        mock_db = MockDB(templates=[tpl_doc], audits=[draft_doc])

        stats = await run_migration(mock_db, dry_run=False)

        assert stats["answered_legacy_detected"] == 1
        assert stats["audits_skipped_manual_review"] == 1
        assert stats["unanswered_audit_questions_updated"] == 0

        # Preserved untouched
        current_audit = mock_db.audits_data[str(draft_doc["_id"])]
        assert current_audit["dof_details"]["29"]["action_plan"] == "Armatür koruma glopları takılacak"
        assert current_audit["answers"]["29"] == "HAYIR"


# ---------------------------------------------------------------------------
# 6. Migration: FINAL Historical Audits Immutability
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestFinalAuditImmutability:
    """FINAL audits must remain byte/semantically untouched."""

    async def test_final_audit_is_never_mutated(self):
        legacy_questions = build_legacy_questions()
        final_doc = {
            "_id": ObjectId(),
            "restaurant_name": "Historical FINAL Restaurant",
            "state": "FINAL",
            "answers": {"9": "EVET", "61": "HAYIR"},
            "template_snapshot": {
                "template_code": "isg_v1_default",
                "questions": copy.deepcopy(legacy_questions),
            },
        }

        mock_db = MockDB(templates=[], audits=[final_doc])

        stats = await run_migration(mock_db, dry_run=False)

        assert stats["finalized_untouched"] == 1
        assert stats["unanswered_audit_questions_updated"] == 0
        assert stats["audits_skipped_manual_review"] == 0

        # Verify audit remained unmodified
        audit_in_db = mock_db.audits_data[str(final_doc["_id"])]
        assert audit_in_db == final_doc


# ---------------------------------------------------------------------------
# 7. Migration: Idempotency & Dry-Run
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestMigrationIdempotencyAndDryRun:
    """Test idempotency and dry-run guarantees."""

    async def test_dry_run_performs_zero_writes(self):
        tpl_doc = {"code": "isg_v1_default", "questions": build_legacy_questions()}
        draft_doc = {
            "_id": ObjectId(),
            "state": "DRAFT",
            "answers": {},
            "template_snapshot": {"questions": build_legacy_questions()},
        }

        mock_db = MockDB(templates=[tpl_doc], audits=[draft_doc])

        stats = await run_migration(mock_db, dry_run=True)

        assert stats["dry_run"] is True
        assert stats["template_updated"] == 1
        assert stats["unanswered_audit_questions_updated"] == len(QUESTION_UPDATES)

        # DB must have ZERO writes
        assert mock_db.templates_data["isg_v1_default"]["questions"][8]["question"] == OLD_TEXTS[9]
        assert mock_db.audits_data[str(draft_doc["_id"])]["template_snapshot"]["questions"][8]["question"] == OLD_TEXTS[9]

    async def test_idempotency_second_run_is_noop(self):
        tpl_doc = {"code": "isg_v1_default", "questions": build_legacy_questions()}
        draft_doc = {
            "_id": ObjectId(),
            "state": "DRAFT",
            "answers": {},
            "template_snapshot": {"questions": build_legacy_questions()},
        }

        mock_db = MockDB(templates=[tpl_doc], audits=[draft_doc])

        # Run 1: Applies updates
        stats1 = await run_migration(mock_db, dry_run=False)
        assert stats1["template_updated"] == 1
        assert stats1["unanswered_audit_questions_updated"] == len(QUESTION_UPDATES)

        # Run 2: Exact same state, 0 updates, 1 already correct
        stats2 = await run_migration(mock_db, dry_run=False)
        assert stats2["template_updated"] == 0
        assert stats2["unanswered_audit_questions_updated"] == 0
        assert stats2["already_correct_records"] == 1
        assert stats2["audits_skipped_manual_review"] == 0


# ---------------------------------------------------------------------------
# 8. Document Shape Error Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestDocumentShapeDefensiveness:
    """Migration script must fail loudly on corrupted or invalid document shapes."""

    async def test_invalid_template_questions_shape_raises(self):
        tpl_doc = {"code": "isg_v1_default", "questions": "invalid_string_not_list"}
        mock_db = MockDB(templates=[tpl_doc], audits=[])

        with pytest.raises(ValueError, match="Invalid template format"):
            await run_migration(mock_db, dry_run=False)

    async def test_invalid_audit_document_shape_raises(self):
        mock_db = MockDB(templates=[], audits=[])
        # Add invalid doc without _id
        mock_db.audits_data["invalid"] = {"state": "DRAFT"}

        with pytest.raises(ValueError, match="Invalid audit document shape"):
            await run_migration(mock_db, dry_run=False)

    async def test_missing_optional_fields_handled_gracefully(self):
        """Audits with missing optional fields (e.g. declarations, dof_details) do not crash."""
        tpl_doc = {"code": "isg_v1_default", "questions": build_legacy_questions()}
        draft_doc = {
            "_id": ObjectId(),
            "restaurant_name": "Minimal Audit",
            "state": "DRAFT",
            "answers": None,
            "dof_details": None,
            "risk_overrides": None,
            "template_snapshot": {"questions": build_legacy_questions()},
        }
        mock_db = MockDB(templates=[tpl_doc], audits=[draft_doc])

        stats = await run_migration(mock_db, dry_run=False)
        assert stats["unanswered_audit_questions_updated"] == len(QUESTION_UPDATES)
        assert stats["audits_skipped_manual_review"] == 0


# ---------------------------------------------------------------------------
# 9. Standalone Script & CLI Execution
# ---------------------------------------------------------------------------
class TestStandaloneScriptExecution:
    """Verify script starts cleanly and parses CLI arguments."""

    def test_script_help_flag_succeeds(self):
        import subprocess

        script_path = BACKEND_DIR / "scripts" / "update_question_texts.py"
        # Run in clean environment without pre-exported MONGO_URL/DB_NAME
        clean_env = {k: v for k, v in os.environ.items() if k not in ("MONGO_URL", "DB_NAME")}
        res = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert res.returncode == 0
        assert "--dry-run" in res.stdout
        assert "--mongo-url" in res.stdout
        assert "--db-name" in res.stdout

    def test_is_answered_helper_logic(self):
        assert not _is_answered(9, None, None, None)
        assert not _is_answered(9, {}, {}, {})
        assert not _is_answered(9, {"9": ""}, {}, {})
        assert not _is_answered(9, {"9": "unanswered"}, {}, {})
        assert _is_answered(9, {"9": "EVET"}, {}, {})
        assert _is_answered(9, {"9": "HAYIR"}, {}, {})
        assert _is_answered(9, {"9": "NA"}, {}, {})
        assert _is_answered(9, {}, {"9": {"status": "ACIK"}}, {})
        assert _is_answered(9, {}, {}, {"9": {"probability": 4, "severity": 4}})
