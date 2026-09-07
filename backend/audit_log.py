"""Audit Log (Phase 2B — S20).

İş birimi kuralı (UAT S20 — 2026-08-13):
    "Nihai raporların resmi argileşme veya saklama süresiyle ilgili bir
    kural var mıdır? — Kanunen 6 yıl saklanmalı ve istendiğinde imzalı
    olarak ibraz edilebilmeli. ..yoksa suç"

Bu modül:
    1. ``audit_log`` koleksiyonuna her mutation'da append-only kayıt yazar
       (kim, ne zaman, ne yaptı, öncesi/sonrası, IP).
    2. ``retention_until`` alanını audit oluşturulduğunda +6 yıl olarak set eder.
    3. ``is_archived`` flag'i 6 yılı dolmuş audit'leri işaretler (soft-archive).

Koleksiyon yapısı (``audit_log``):
    {
      _id: ObjectId,
      audit_id: str,
      user_id: str,
      user_name: str,
      action: str,          # "create", "submit", "answer_update", "dof_close", "export_pdf", ...
      before: dict | None,  # değişiklik öncesi snapshot (seçici alanlar)
      after: dict | None,   # değişiklik sonrası snapshot
      timestamp: ISO str,
      ip: str | None,
      user_agent: str | None,
    }

Endpoint kullanımı:
    from audit_log import log_action, set_retention, get_audit_log, archive_expired

    await log_action(
        db, audit_id="...", user=current_user, action="submit",
        before={"state": "DRAFT"}, after={"state": "DOF_OPEN"},
    )
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence

# B8 — calendar-year arithmetic: 6 takvim yılı = ``relativedelta(years=6)``.
# ``timedelta(days=365 * 6)`` artık yılları saymıyor; 29 Şubat doğumlu audit
#'leri takvim-altı bir gün kaydırıyordu. ``python-dateutil`` zaten projede
# transitively mevcut (requirements.txt içinde).
from dateutil.relativedelta import relativedelta

# İş birimi kuralı: 6 yıl. KVKK ve Türk mevzuatı da uyumlu.
RETENTION_YEARS = 6

_log = logging.getLogger("audit_log")


def compute_retention_until(created_at_iso: Optional[str] = None) -> str:
    """Audit'in retention bitiş tarihini hesapla (created_at + 6 takvim yılı).

    ``created_at_iso`` ISO 8601 string olmalı; parse edilemezse now()+6y döner.

    B8: ``relativedelta(years=6)`` kullanır — artık yıllar doğru sayılır
    (29 Şubat → 28 Şubat/29 Şubat) ve saat dilimi UTC'de korunur.
    """
    if created_at_iso:
        try:
            dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return (dt + relativedelta(years=RETENTION_YEARS)).isoformat()


def is_retention_expired(retention_until_iso: str | None, now: Optional[datetime] = None) -> bool:
    """Retention süresi dolmuş mu?"""
    if not retention_until_iso:
        return False
    try:
        ru = datetime.fromisoformat(retention_until_iso.replace("Z", "+00:00"))
    except Exception:
        return False
    return ru <= (now or datetime.now(timezone.utc))


async def log_action(
    db,
    *,
    audit_id: str,
    user: dict,
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    timestamp: Optional[str] = None,
    mandatory: bool = False,
) -> None:
    """``audit_log`` koleksiyonuna append-only kayıt yaz.

    B6 — Log Dayanıklılık:

    * ``mandatory=True`` → yazma hatası exception olarak yükseltilir. Bu,
      iş birimi kuralı veya compliance invariantı gerektiren kritik
      mutasyonlar (state transition, finalize, DÖF update, photo
      upload/delete, vb.) için seçilir. Yanlışlıkla yutulursa "audit
      fully audited" yalanı raporlanır.
    * ``mandatory=False`` (varsayılan, geriye uyumlu) → yazma hatası
      ``logging.warning`` ile loglanır, ana işlem etkilenmez. Operasyonel
      telemetri (login/logout/export counter) için uygundur.
    """
    entry = {
        "audit_id": audit_id,
        "user_id": user.get("id") or user.get("_id") or "",
        "user_name": user.get("name") or user.get("email") or "unknown",
        "action": action,
        "before": before,
        "after": after,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "ip": ip,
        "user_agent": user_agent,
    }
    try:
        await db.audit_log.insert_one(entry)
    except Exception as exc:
        if mandatory:
            # Compliance invariant kırıldı — mutasyon "fully audited" değil.
            # Caller'ı zorla fail et ki hata UI'a/surface'e çıksın.
            raise RuntimeError(
                f"[audit_log] MANDATORY audit log write failed for action "
                f"'{action}' on audit {audit_id}: {exc}"
            ) from exc
        # Best-effort operasyonel telemetri: hatayı yutma, logla.
        _log.warning(
            "[audit_log] best-effort log write failed for action '%s' "
            "on audit %s: %s",
            action,
            audit_id,
            exc,
        )


async def get_audit_log(
    db,
    audit_id: str,
    *,
    limit: int = 100,
    skip: int = 0,
) -> List[Dict[str, Any]]:
    """Bir audit'in log geçmişini getir (en yeni önce)."""
    cursor = (
        db.audit_log.find({"audit_id": audit_id})
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )
    items = []
    async for doc in cursor:
        # ObjectId serializable değil; str'ye çevir
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    return items


async def archive_expired_audits(db, *, now: Optional[datetime] = None, batch_size: int = 100) -> int:
    """Retention süresi dolmuş audit'leri ``is_archived=true`` olarak işaretle.

    İş birimi kuralı S20: "Kanunen 6 yıl saklanmalı" → 6 yılı dolan audit'ler
    arşivlenir; silinmez. ``is_archived=True`` set edilir, listede
    default olarak görünmez; ``?include_archived=true`` query ile getirilir.

    Returns:
        Arşivlenen audit sayısı.
    """
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    archived_count = 0
    cursor = db.audits.find(
        {
            "retention_until": {"$lte": now_iso, "$ne": None},
            "is_archived": {"$ne": True},
        },
        {"_id": 1, "retention_until": 1},
    )
    async for doc in cursor:
        await db.audits.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "is_archived": True,
                    "archived_at": now_iso,
                }
            },
        )
        # Log the archival as a system event (no user)
        await db.audit_log.insert_one(
            {
                "audit_id": str(doc["_id"]),
                "user_id": "system",
                "user_name": "system",
                "action": "archive",
                "before": {"is_archived": False},
                "after": {"is_archived": True, "archived_at": now_iso},
                "timestamp": now_iso,
                "ip": None,
                "user_agent": None,
            }
        )
        archived_count += 1
        if archived_count >= batch_size:
            break
    return archived_count


# Eylem adları (tutarlılık için enum benzeri sabitler). Yeni eylem eklerken
# buraya da ekleyin; böylece log_action çağrılarında typo önlenir.
class Action:
    CREATE = "create"
    SUBMIT = "submit"
    ANSWER_UPDATE = "answer_update"
    META_UPDATE = "meta_update"
    DECLARATION_UPDATE = "declaration_update"
    DOF_UPDATE = "dof_update"
    DOF_OPEN = "dof_open"
    DOF_CLOSE = "dof_close"
    PHOTO_UPLOAD = "photo_upload"
    PHOTO_DELETE = "photo_delete"
    EXPORT_PDF = "export_pdf"
    EXPORT_EXCEL = "export_excel"
    EXPORT_IBRAZ = "export_ibraz"  # S20: mahkeme-format ibraz belgesi
    EXPORT_FINALIZE = "export_finalize"  # DOF_CLOSED → FINAL geçişi
    DELETE = "delete"
    SOFT_DELETE = "soft_delete"
    RESTORE = "restore"
    ARCHIVE = "archive"
    LOGIN = "login"
    LOGOUT = "logout"
    WORKPLACE_APPROVAL_SIGNED = "workplace_approval_signed"  # İşveren vekili onay imzası (S7.2)
