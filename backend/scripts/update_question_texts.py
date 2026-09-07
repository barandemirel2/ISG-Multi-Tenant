"""Update question texts for remediated questions in Mongo template and audits (Batch 1 & Batch 2).

Source of truth: backend/seed/isg_v1_default_questions.json and backend/questions.json

9 remediated questions:
  9  : "Tüm personelin Hijyen Eğitimi Belgesi mevcut mudur?"
  15 : "Acil çıkış yolları ve merdivenleri malzeme depolanmasından arındırılmış, geçişe açık mıdır?"
  26 : "Tüm kablolar yalıtımlı, sağlam ve kapalı mıdır (ek, aşınma, soyulma, açıkta iletken tel yok)?"
  27 : "Seyyar uzatma kabloları ve çoklu prizler yalnızca geçici kullanım için mi kullanılmaktadır?"
  29 : "Aydınlatma armatürleri sağlam ve güvenli midir?"
  30 : "Tüm elektrik arıza ve bakım işlemleri Yetkili Elektrik Personeli tarafından mı yapılmaktadır?"
  58 : "Çalışanlar iş sırasında ziynet eşyası, yüzük, saat vb. aksesuarları çıkarmış mıdır?"
  61 : "Zeminler düzgün ve güvenli midir?"
  68 : "Mutfak ve depo tavanları nem, küf, sıva döküntüsü ve su sızıntısından arındırılmış mıdır?"

Compatibility Strategy:
  - db.templates: Idempotently update questions in isg_v1_default.
  - FINAL historical audits: Untouched (immutable historical evidence).
  - Unanswered DRAFT/DOF_OPEN questions: Safely update snapshot question text.
  - Answered legacy questions: DO NOT mutate text (avoids semantic inversion / DÖF corruption).
    Skip and report for manual review.
  - Idempotent and supports dry-run mode (--dry-run).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Set default env vars BEFORE importing server.py
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-with-at-least-32-chars-for-entropy-ok")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from server import db  # noqa: E402


QUESTION_UPDATES: Dict[int, str] = {
    9: "Tüm personelin Hijyen Eğitimi Belgesi mevcut mudur?",
    15: "Acil çıkış yolları ve merdivenleri malzeme depolanmasından arındırılmış, geçişe açık mıdır?",
    26: "Tüm kablolar yalıtımlı, sağlam ve kapalı mıdır (ek, aşınma, soyulma, açıkta iletken tel yok)?",
    27: "Seyyar uzatma kabloları ve çoklu prizler yalnızca geçici kullanım için mi kullanılmaktadır?",
    29: "Aydınlatma armatürleri sağlam ve güvenli midir?",
    30: "Tüm elektrik arıza ve bakım işlemleri Yetkili Elektrik Personeli tarafından mı yapılmaktadır?",
    58: "Çalışanlar iş sırasında ziynet eşyası, yüzük, saat vb. aksesuarları çıkarmış mıdır?",
    61: "Zeminler düzgün ve güvenli midir?",
    68: "Mutfak ve depo tavanları nem, küf, sıva döküntüsü ve su sızıntısından arındırılmış mıdır?",
}


def _is_answered(
    qid: int,
    answers: Optional[Dict[str, Any]],
    dof_details: Optional[Dict[str, Any]],
    risk_overrides: Optional[Dict[str, Any]],
) -> bool:
    """Check if question has an existing recorded answer or derived DÖF/override state."""
    qid_str = str(qid)
    if isinstance(answers, dict) and qid_str in answers:
        val = answers[qid_str]
        if val is not None and str(val).strip() != "" and str(val).strip() != "unanswered":
            return True

    if isinstance(dof_details, dict) and qid_str in dof_details:
        d = dof_details[qid_str]
        if isinstance(d, dict) and any(bool(v) for v in d.values()):
            return True

    if isinstance(risk_overrides, dict) and qid_str in risk_overrides:
        return True

    return False


async def run_migration(database: Any, dry_run: bool = False) -> Dict[str, Any]:
    """Execute question texts migration with strict safety and classification.

    Returns a summary dict containing counts and manual review details.
    """
    stats: Dict[str, Any] = {
        "dry_run": dry_run,
        "template_updated": 0,
        "unanswered_audit_questions_updated": 0,
        "already_correct_records": 0,
        "answered_legacy_detected": 0,
        "audits_skipped_manual_review": 0,
        "finalized_untouched": 0,
        "manual_review_audits": [],
    }

    # 1. Update template collection
    template = await database.templates.find_one({"code": "isg_v1_default"})
    if template:
        if not isinstance(template.get("questions"), list):
            raise ValueError(f"Invalid template format: 'questions' is not a list in isg_v1_default")

        template_questions = template["questions"]
        template_changed = False
        for q in template_questions:
            if not isinstance(q, dict):
                raise ValueError(f"Invalid template question format: {q}")
            qid = q.get("id")
            if qid in QUESTION_UPDATES:
                target_text = QUESTION_UPDATES[qid]
                if q.get("question") != target_text:
                    q["question"] = target_text
                    template_changed = True

        if template_changed:
            stats["template_updated"] = 1
            if not dry_run:
                await database.templates.update_one(
                    {"code": "isg_v1_default"},
                    {
                        "$set": {
                            "questions": template_questions,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
    else:
        print("UYARI: 'isg_v1_default' template db.templates koleksiyonunda bulunamadı.")

    # 2. Inspect and migrate audits
    cursor = database.audits.find({})
    async for doc in cursor:
        if not isinstance(doc, dict) or "_id" not in doc:
            raise ValueError(f"Invalid audit document shape in database: {doc}")

        audit_id_str = str(doc["_id"])
        state = doc.get("state", "DRAFT")

        # Invariant: FINAL audits are immutable and intentionally untouched
        if state == "FINAL":
            stats["finalized_untouched"] += 1
            continue

        snap = doc.get("template_snapshot")
        if snap is None:
            # Legacy audit without template_snapshot
            answers = doc.get("answers")
            if answers is not None and not isinstance(answers, dict):
                raise ValueError(f"Audit {audit_id_str} 'answers' field is not a dict")

            dof_details = doc.get("dof_details")
            risk_overrides = doc.get("risk_overrides")

            legacy_answered = [
                qid
                for qid in QUESTION_UPDATES
                if _is_answered(qid, answers, dof_details, risk_overrides)
            ]
            if legacy_answered:
                stats["answered_legacy_detected"] += len(legacy_answered)
                stats["audits_skipped_manual_review"] += 1
                stats["manual_review_audits"].append(
                    {
                        "audit_id": audit_id_str,
                        "restaurant_name": doc.get("restaurant_name", ""),
                        "state": state,
                        "reason": "Legacy audit without template_snapshot containing answered affected questions",
                        "answered_questions": legacy_answered,
                    }
                )
            else:
                stats["already_correct_records"] += 1
            continue

        if not isinstance(snap, dict):
            raise ValueError(f"Audit {audit_id_str} has non-dict 'template_snapshot': {type(snap)}")

        questions = snap.get("questions")
        if not isinstance(questions, list):
            raise ValueError(f"Audit {audit_id_str} has non-list 'template_snapshot.questions'")

        # Identify affected questions with old text
        old_text_qids: List[int] = []
        for q in questions:
            if not isinstance(q, dict):
                raise ValueError(f"Audit {audit_id_str} contains non-dict question in snapshot: {q}")
            qid = q.get("id")
            if qid in QUESTION_UPDATES:
                if q.get("question") != QUESTION_UPDATES[qid]:
                    old_text_qids.append(qid)

        if not old_text_qids:
            stats["already_correct_records"] += 1
            continue

        answers = doc.get("answers")
        if answers is not None and not isinstance(answers, dict):
            raise ValueError(f"Audit {audit_id_str} 'answers' field is not a dict")

        dof_details = doc.get("dof_details")
        if dof_details is not None and not isinstance(dof_details, dict):
            raise ValueError(f"Audit {audit_id_str} 'dof_details' field is not a dict")

        risk_overrides = doc.get("risk_overrides")
        if risk_overrides is not None and not isinstance(risk_overrides, dict):
            raise ValueError(f"Audit {audit_id_str} 'risk_overrides' field is not a dict")

        # Check which of the old-text questions are answered
        answered_qids = [
            qid
            for qid in old_text_qids
            if _is_answered(qid, answers, dof_details, risk_overrides)
        ]
        unanswered_qids = [qid for qid in old_text_qids if qid not in answered_qids]

        if answered_qids:
            # Unfinished audit has answered legacy questions.
            # Do NOT mutate! Skip and report for manual review.
            stats["answered_legacy_detected"] += len(answered_qids)
            stats["audits_skipped_manual_review"] += 1
            stats["manual_review_audits"].append(
                {
                    "audit_id": audit_id_str,
                    "restaurant_name": doc.get("restaurant_name", ""),
                    "state": state,
                    "reason": "Unfinished audit with answered legacy question(s)",
                    "answered_questions": answered_qids,
                    "unanswered_questions": unanswered_qids,
                    "answers": {str(qid): answers.get(str(qid)) for qid in answered_qids} if isinstance(answers, dict) else {},
                }
            )
            continue

        # All affected old questions in this audit are unanswered -> safe to update snapshot!
        for q in questions:
            qid = q.get("id")
            if qid in unanswered_qids:
                q["question"] = QUESTION_UPDATES[qid]

        stats["unanswered_audit_questions_updated"] += len(unanswered_qids)
        if not dry_run:
            now_iso = datetime.now(timezone.utc).isoformat()
            await database.audits.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "template_snapshot.questions": questions,
                        "updated_at": now_iso,
                    }
                },
            )

    return stats


def print_report(stats: Dict[str, Any]) -> None:
    """Print structured migration summary report."""
    mode_str = "DRY-RUN (NO DB WRITES)" if stats["dry_run"] else "LIVE (CHANGES APPLIED)"
    print("=" * 68)
    print(f"ABCD Tech Solutions İSG — Question Texts Migration Report (U2)")
    print(f"Execution Mode: {mode_str}")
    print("=" * 68)
    print("Summary Counts:")
    print(f"  * Template updated                         : {stats['template_updated']}")
    print(f"  * Unanswered audit questions updated       : {stats['unanswered_audit_questions_updated']}")
    print(f"  * Already-correct records                  : {stats['already_correct_records']}")
    print(f"  * Answered legacy questions detected       : {stats['answered_legacy_detected']}")
    print(f"  * Audits skipped for manual review         : {stats['audits_skipped_manual_review']}")
    print(f"  * Finalized audits intentionally untouched : {stats['finalized_untouched']}")
    print("=" * 68)

    manual_reviews = stats.get("manual_review_audits", [])
    if manual_reviews:
        print(f"Audits Requiring Manual Review ({len(manual_reviews)} total):")
        for item in manual_reviews:
            print(f"  - Audit ID   : {item['audit_id']}")
            print(f"    Restaurant : {item.get('restaurant_name', 'N/A')}")
            print(f"    State      : {item.get('state', 'N/A')}")
            print(f"    Answered Qs: {item.get('answered_questions', [])}")
            if item.get("answers"):
                print(f"    Answers    : {item['answers']}")
            print(f"    Reason     : {item.get('reason', '')}")
            print()
    else:
        print("No audits require manual review.")
    print("=" * 68)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate 4 question texts in Mongo templates and safe audits."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without modifying any documents in MongoDB.",
    )
    parser.add_argument(
        "--mongo-url",
        type=str,
        default=None,
        help="MongoDB connection URL (defaults to MONGO_URL env or mongodb://localhost:27017).",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=None,
        help="MongoDB database name (defaults to DB_NAME env or risk_analiz).",
    )
    args = parser.parse_args()

    if args.mongo_url:
        os.environ["MONGO_URL"] = args.mongo_url
    if args.db_name:
        os.environ["DB_NAME"] = args.db_name

    stats = await run_migration(db, dry_run=args.dry_run)
    print_report(stats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
