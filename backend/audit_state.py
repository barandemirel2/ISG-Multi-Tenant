"""Audit State Machine (Phase 2B — S18).

İş birimi kuralı (UAT S18 — 2026-08-13):
    "Tamamlanan denetim sonradan düzenlenebilir mi? — Hayır, olumsuz ara döf
    açılacak, döf protokolü tamamlanınca nihai rapor düzenlenebilecek,
    akıldöfü olana nihai rapor verilmeyecek."

Bu modül audit'in yaşam döngüsünü temsil eden 5 state + izin matrisini tanımlar.
Tüm mutation endpoint'leri (``update_answers``, ``update_audit_meta``,
``update_audit_declarations``, ``delete_audit``, ``export_*`` ve DÖF
endpoint'leri) bu tablodan geçiş yaparak audit'i kilitler/açar.

Tasarım notları:
    * ``state`` string alanı audit doc'unda yaşar; ``state_history`` array her
      geçiş için bir append-only kayıt tutar (S20 audit_log için temel).
    * ``is_completed`` geriye uyumluluk için korunur; bu modüldeki
      ``derive_is_completed()`` ile türetilir, yeni kod ``state`` kullanır.
    * Geçişler **açık** yapılır — hiçbir endpoint sessizce state değiştirmez.
      ``transition_audit()`` çağrıldığında yeni state, sebep ve işlem yapan
      kullanıcı ile birlikte ``state_history``'ye yazılır.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Literal, Optional, Set


class AuditState(str, Enum):
    """Audit yaşam döngüsü durumları.

    Geçiş kuralları için :data:`TRANSITIONS` ve davranış matrisleri için
    ``can_*`` yardımcılarına bak.
    """

    DRAFT = "DRAFT"            # Yeni oluşturuldu; denetçi cevapları dolduruyor
    SUBMITTED = "SUBMITTED"    # Denetçi "Denetimi Tamamla" dedi; kilitli (ama DÖF açılabilir)
    DOF_OPEN = "DOF_OPEN"      # En az 1 DÖF açık; audit düzenlenemez
    DOF_CLOSED = "DOF_CLOSED"  # Tüm DÖF'ler kapandı; nihai rapor export edilebilir
    FINAL = "FINAL"            # Nihai rapor verildi; ASLA düzenlenemez

    # Geçmiş/lint uyumluluğu için alias.
    @classmethod
    def _missing_(cls, value):  # type: ignore[override]
        if isinstance(value, str) and value.upper() == "DOF":
            return cls.DOF_OPEN
        return None


# İzin verilen geçişler: ``from -> {to, ...}``.
# ``FINAL`` terminal durumdur (geri dönüş yok). ``DOF_CLOSED`` da
# normalde tek yönlüdür (FINAL'a), ama DÖF yeniden açılırsa (ör. yeni
# soruya cevap verilirse) DOF_OPEN'a geri dönülebilir — bu kenar durum
# manuel operasyon gerektirir, bu yüzden yorumda bırakılmıştır.
#
# DRAFT -> DOF_OPEN'a **doğrudan** izin verilir: submit edilen audit'te
# HAYIR cevaplı soru varsa, sistem tek atomik submit işlemiyle audit'i
# DRAFT'tan DOF_OPEN'a alır. ``SUBMITTED`` arada görünmez. İş birimi
# kuralı S18: "submit edilen denetimde DÖF varsa, o denetim DOF_OPEN olur".
TRANSITIONS: Dict[AuditState, Set[AuditState]] = {
    # DRAFT'tan: DÖF yoksa doğrudan DOF_CLOSED'a; DÖF varsa DOF_OPEN'a;
    # SUBMITTED yalnızca bütçe/geçiş uyumluluğu için listede tutulur
    # (henüz hiçbir endpoint SUBMITTED'a DRAFT'tan geçiş yapmıyor —
    # ``compute_submit_target_state`` B1 gereği DOF_CLOSED/DOF_OPEN'a atlar).
    AuditState.DRAFT: {AuditState.SUBMITTED, AuditState.DOF_OPEN, AuditState.DOF_CLOSED},
    AuditState.SUBMITTED: {AuditState.DOF_OPEN, AuditState.DOF_CLOSED, AuditState.FINAL},
    AuditState.DOF_OPEN: {AuditState.DOF_CLOSED},
    AuditState.DOF_CLOSED: {AuditState.FINAL},
    AuditState.FINAL: set(),
}


# Davranış matrisi — her endpoint sınıfı için state'e göre izin.
# Yeni bir mutasyon eklerken burada bir satır daha ekle.

_EDIT_BEHAVIOR = {
    # state: (can_edit_answers, can_edit_meta, can_edit_declarations, can_open_dof, can_close_dof)
    AuditState.DRAFT:       (True,  True,  True,  True,  True),
    AuditState.SUBMITTED:   (False, False, True,  True,  False),
    AuditState.DOF_OPEN:    (False, False, True,  True,  True),
    AuditState.DOF_CLOSED:  (False, False, True,  False, False),  # Tüm DÖF'ler zaten kapalı
    AuditState.FINAL:       (False, False, False, False, False),
}


def can_edit_answers(state: AuditState | str) -> bool:
    s = _coerce(state)
    return _EDIT_BEHAVIOR[s][0]


def can_edit_meta(state: AuditState | str) -> bool:
    s = _coerce(state)
    return _EDIT_BEHAVIOR[s][1]


def can_edit_declarations(state: AuditState | str) -> bool:
    s = _coerce(state)
    return _EDIT_BEHAVIOR[s][2]


def can_open_dof(state: AuditState | str) -> bool:
    s = _coerce(state)
    return _EDIT_BEHAVIOR[s][3]


def can_close_dof(state: AuditState | str) -> bool:
    s = _coerce(state)
    return _EDIT_BEHAVIOR[s][4]


# Silme davranışı: "hard" (gerçekten sil), "soft" (deleted_at set), "deny" (404/403).
DeleteBehavior = Literal["hard", "soft", "deny"]


def delete_behavior(state: AuditState | str) -> DeleteBehavior:
    s = _coerce(state)
    if s == AuditState.DRAFT:
        return "hard"   # Taslak hiç var olmamış gibi silinebilir
    if s in (AuditState.SUBMITTED, AuditState.DOF_OPEN, AuditState.DOF_CLOSED, AuditState.FINAL):
        return "soft"   # Yasal/operasyonel kayıt — soft-delete flag
    return "deny"


def can_export_final(state: AuditState | str) -> bool:
    """Nihai (imzalı) rapor export edilebilir mi?

    Sadece DOF_CLOSED ve FINAL'de ``True``. SUBMITTED'da bile DÖF açılabileceği
    için nihai rapor verilmez (iş birimi kuralı: "akıldöfü olana nihai rapor
    verilmeyecek"). DRAFT'ta da verilmez çünkü henüz denetim tamamlanmadı.
    """
    s = _coerce(state)
    return s in (AuditState.DOF_CLOSED, AuditState.FINAL)


def can_export_draft(state: AuditState | str) -> bool:
    """Taslak rapor (henüz tamamlanmamış) export edilebilir mi?

    Sadece DRAFT ve SUBMITTED. DOF_OPEN/DOF_CLOSED'ta nihai rapor gerekir.
    """
    s = _coerce(state)
    return s in (AuditState.DRAFT, AuditState.SUBMITTED)


def can_submit(state: AuditState | str) -> bool:
    """``POST /api/audits/{id}/submit`` çağrılabilir mi?

    Sadece DRAFT'tan SUBMITTED'a geçiş mümkün. Diğer tüm durumlar zaten
    submit edilmiş kabul edilir.
    """
    s = _coerce(state)
    return s == AuditState.DRAFT


def can_transition(from_state: AuditState | str, to_state: AuditState | str) -> bool:
    f = _coerce(from_state)
    t = _coerce(to_state)
    return t in TRANSITIONS.get(f, set())


def transition_audit(
    audit_doc: dict,
    new_state: AuditState | str,
    *,
    actor_id: str,
    reason: str = "",
    now_iso: Optional[str] = None,
) -> dict:
    """Audit doc'unu ``new_state``'e geçirir; ``state_history``'ye append yapar.

    Geçiş yasaksa :class:`ValueError` fırlatır. Mevcut state yoksa (``None``)
    ``DRAFT`` kabul edilir (yeni oluşturulmuş audit'ler için).

    Döndürülen dict ``$set`` olarak MongoDB'ye yazılmak üzere hazırdır:
        {
            "state": <new>,
            "is_completed": <derived>,
            "updated_at": <now>,
            "state_history": [<append>],
        }
    """
    target = _coerce(new_state)
    current = _coerce(audit_doc.get("state")) if audit_doc.get("state") else AuditState.DRAFT

    if current == target:
        # Geçiş yok, idempotent — sadece updated_at yenilenir.
        return {
            "updated_at": now_iso or _now_iso(),
        }

    if not can_transition(current, target):
        raise ValueError(
            f"Geçersiz state geçişi: {current.value} -> {target.value}. "
            f"İzin verilen: {sorted(s.value for s in TRANSITIONS.get(current, set()))}"
        )

    now = now_iso or _now_iso()
    history_entry = {
        "from": current.value,
        "to": target.value,
        "at": now,
        "by": actor_id,
        "reason": reason or _default_reason(current, target),
    }

    history = list(audit_doc.get("state_history") or [])
    history.append(history_entry)

    return {
        "state": target.value,
        "is_completed": derive_is_completed(target),
        "updated_at": now,
        "state_history": history,
    }


def derive_is_completed(state: AuditState | str) -> bool:
    """Geriye uyumluluk: ``is_completed`` türevi.

    Dışa aktarılan rapor başlığında ``TAMAMLANDI / TASLAK DENETİM`` etiketi
    için kullanılır. ``is_completed == True`` audit'in artık düzenlenemeyeceği
    anlamına gelir; bu DOF_CLOSED ve FINAL'i kapsar.
    """
    s = _coerce(state)
    return s in (AuditState.DOF_CLOSED, AuditState.FINAL)


def compute_submit_target_state(
    audit_doc: dict,
    has_open_dof: bool,
) -> AuditState:
    """Denetim submit edildiğinde varış state'ini hesapla.

    İş birimi kuralı (B1 — No-DÖF deterministik path):
        * DÖF varsa → DOF_OPEN (tüm DÖF'ler kapandığında ``transition_audit``
          otomatik DOF_CLOSED'a alır).
        * DÖF yoksa → **DOF_CLOSED** (henüz FINAL değil; ilk geçerli nihai
          export beklentisiyle). SUBMITTED artık kullanılmıyor; daha önce
          burada bırakmak audit'i ``can_export_final=False`` durumunda
          kilitliyordu (bütçede SUBMITTED export edilemiyor).

    Geçiş tablosu (``TRANSITIONS[DRAFT]``) bu hedefleri kapsar; bu işlev
    state makinesinin tek doğruluk kaynağıdır — endpoint'lerde ad-hoc
    state ataması yapma (B1 invariant).
    """
    return AuditState.DOF_OPEN if has_open_dof else AuditState.DOF_CLOSED


def compute_dof_resolution_target_state(
    audit_state: AuditState | str,
    remaining_open_dofs: int,
) -> AuditState:
    """Bir DÖF kapatıldıktan sonra audit'in state'i ne olmalı?

    * Eğer audit DOF_OPEN'ta DEĞİLSE → state değişmez (çağıran dikkate almalı).
    * Eğer tüm DÖF'ler kapandıysa (remaining_open_dofs == 0) → DOF_CLOSED.
    * Aksi → DOF_OPEN (değişiklik yok).
    """
    s = _coerce(audit_state)
    if s != AuditState.DOF_OPEN:
        return s
    if remaining_open_dofs <= 0:
        return AuditState.DOF_CLOSED
    return s


# ----- Internal helpers -----


def _coerce(value: AuditState | str) -> AuditState:
    if isinstance(value, AuditState):
        return value
    if isinstance(value, str):
        # Enum value ile eşleş (büyük/küçük harf duyarsız).
        try:
            return AuditState(value.upper())
        except ValueError:
            pass
        # Enum._missing_ fallback (örn. "DOF" -> DOF_OPEN).
        coerced = AuditState._missing_(value)
        if coerced is not None:
            return coerced
    raise ValueError(f"Geçersiz audit state: {value!r}")


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _default_reason(from_state: AuditState, to_state: AuditState) -> str:
    default_reasons = {
        (AuditState.DRAFT, AuditState.SUBMITTED): "Denetim tamamlandı, denetçi tarafından gönderildi.",
        (AuditState.SUBMITTED, AuditState.DOF_OPEN): "DÖF açıldı, takip başladı.",
        (AuditState.SUBMITTED, AuditState.DOF_CLOSED): "DÖF yok, doğrudan nihai rapor için hazır.",
        (AuditState.SUBMITTED, AuditState.FINAL): "Nihai rapor verildi.",
        (AuditState.DOF_OPEN, AuditState.DOF_CLOSED): "Tüm DÖF'ler kapatıldı.",
        (AuditState.DOF_CLOSED, AuditState.FINAL): "Nihai rapor verildi.",
    }
    return default_reasons.get((from_state, to_state), f"{from_state.value} -> {to_state.value}")
