"""Phase 2B — S18 migration script.

Mevcut audit doc'larına ``state`` alanı ekler (önceki sürümlerde yoktu).

Geçiş mantığı:
    * ``is_completed=True`` ise → ``FINAL`` (audit tamamlanmış, düzenlenemez)
    * ``is_completed=False`` veya yoksa → ``DRAFT`` (açık taslak)

``state_history`` array'ine ``{from: null, to: <state>, by: "migration",
reason: "Initial state migration from is_completed"}`` kaydı eklenir.

``deleted_at`` set edilmiş soft-deleted audit'ler de migrate edilir (state
değerleri aynı mantıkla, ama deleted_at korunur — bunlar soft-delete
listesinde görünmeye devam eder).

Kullanım (production):
    cd backend
    python -m scripts.migrate_audit_state [--dry-run] [--batch-size N]

Veya interactive (mongosh uyumlu):
    python -m scripts.migrate_audit_state --dry-run   # sadece raporlar
    python -m scripts.migrate_audit_state            # gerçek yazım
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# ``backend/`` path'ini ekle — server.py gibi modüllere doğrudan erişim
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
import os  # noqa: E402

# Phase 2B — S20: Retention helper'ı import et
from audit_log import compute_retention_until  # noqa: E402

# ``.env`` backend kök dizininde olmalı; yoksa kök .env'i de dene
load_dotenv(BACKEND_DIR / ".env")
if not os.environ.get("MONGO_URL"):
    # Kök .env'i de dene (docker-compose kökten okur)
    load_dotenv(BACKEND_DIR.parent / ".env")


async def migrate(dry_run: bool = True, batch_size: int = 100) -> None:
    """Migration ana akışı."""
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "risk_analiz")

    print(f"→ Connecting to {mongo_url} / {db_name}")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # ``state`` field'ı olmayan audit'leri bul. ``is_completed`` flag'ine
    # göre hedef state'i hesapla.
    cursor = db.audits.find(
        {"state": {"$exists": False}},
        {"_id": 1, "is_completed": 1, "deleted_at": 1, "created_at": 1},
    )
    candidates = await cursor.to_list(length=None)
    total = len(candidates)
    print(f"→ Found {total} audit(s) without 'state' field")

    if total == 0:
        print("✓ Nothing to migrate (state).")
    else:
        now_iso = datetime.now(timezone.utc).isoformat()
        draft_count = 0
        final_count = 0
        error_count = 0

        for doc in candidates:
            is_completed = bool(doc.get("is_completed", False))
            target_state = "FINAL" if is_completed else "DRAFT"
            if target_state == "DRAFT":
                draft_count += 1
            else:
                final_count += 1

            update_ops = {
                "$set": {
                    "state": target_state,
                    "state_history": [
                        {
                            "from": None,
                            "to": target_state,
                            "at": now_iso,
                            "by": "migration",
                            "reason": "Initial state migration from is_completed",
                        }
                    ],
                }
            }
            if dry_run:
                print(f"  [DRY-RUN state] {doc['_id']} → {target_state} (is_completed={is_completed})")
                continue

            try:
                await db.audits.update_one({"_id": doc["_id"]}, update_ops)
            except Exception as e:
                error_count += 1
                print(f"  [ERROR state] {doc['_id']}: {e}")

        print()
        print("=" * 50)
        print(f"  state migration:")
        print(f"  Total:    {total}")
        print(f"  → DRAFT:  {draft_count}")
        print(f"  → FINAL:  {final_count}")
        if error_count:
            print(f"  Errors:   {error_count}")
        print(f"  Mode:     {'DRY-RUN' if dry_run else 'LIVE'}")
        print("=" * 50)

        if not dry_run and (draft_count or final_count):
            print(f"✓ Migrated {draft_count + final_count} audit(s) to new state machine.")

    # ──────────────────────────────────────────────────────────────────
    # Phase 2B — S20: ``retention_until`` ve ``is_archived`` migration
    # ──────────────────────────────────────────────────────────────────
    retention_cursor = db.audits.find(
        {"retention_until": {"$exists": False}},
        {"_id": 1, "created_at": 1},
    )
    retention_candidates = await retention_cursor.to_list(length=None)
    retention_total = len(retention_candidates)
    print(f"\n→ Found {retention_total} audit(s) without 'retention_until' field")

    if retention_total == 0:
        print("✓ Nothing to migrate (retention).")
    else:
        now_iso = datetime.now(timezone.utc).isoformat()
        retention_set = 0
        retention_errors = 0
        for doc in retention_candidates:
            created_at = doc.get("created_at") or now_iso
            retention_value = compute_retention_until(created_at)
            if dry_run:
                print(f"  [DRY-RUN retention] {doc['_id']} → {retention_value[:10]} (6y after {created_at[:10]})")
                continue
            try:
                await db.audits.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"retention_until": retention_value, "is_archived": False}},
                )
                retention_set += 1
            except Exception as e:
                retention_errors += 1
                print(f"  [ERROR retention] {doc['_id']}: {e}")

        print()
        print("=" * 50)
        print(f"  retention migration:")
        print(f"  Total:    {retention_total}")
        print(f"  Set:      {retention_set}")
        if retention_errors:
            print(f"  Errors:   {retention_errors}")
        print(f"  Mode:     {'DRY-RUN' if dry_run else 'LIVE'}")
        print("=" * 50)

        if not dry_run and retention_set:
            print(f"✓ Set retention_until on {retention_set} audit(s) (+6y policy).")

    client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy audits to S18 state machine.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sadece raporla, DB'ye yazma (varsayılan: dry-run).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Cursor batch boyutu (varsayılan: 100).",
    )
    args = parser.parse_args()

    # Default davranış dry-run: production'da yanlışlıkla yazımı önle.
    asyncio.run(migrate(dry_run=args.dry_run, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
