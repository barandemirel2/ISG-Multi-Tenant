"""audit_state modülü unit testleri.

Phase 2B — S18: 5-state machine, transition kuralları, davranış matrisi.

Bu testler pure-Python'dır — MongoDB mock'lamaz, sadece ``audit_state`` modülünün
saf logic'ini test eder. DB'ye bağımlı entegrasyon testleri (endpoint guard'lar,
submit, export finalize) ``test_phase_2a_*`` ve yeni ``test_s18_*`` testleri
içinde zaten var/eklenecek.

Çalıştırma: ``pytest backend/tests/test_audit_state_machine.py -v``
"""
import sys
from pathlib import Path

# ``audit_state`` modülü ``backend/`` kök dizininde; sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from audit_state import (
    AuditState,
    TRANSITIONS,
    can_close_dof,
    can_edit_answers,
    can_edit_declarations,
    can_edit_meta,
    can_export_draft,
    can_export_final,
    can_open_dof,
    can_submit,
    can_transition,
    compute_dof_resolution_target_state,
    compute_submit_target_state,
    delete_behavior,
    derive_is_completed,
    transition_audit,
)


# ============ Enum ve TRANSITIONS ============

class TestAuditState:
    """AuditState enum değerlerinin ve transition kurallarının bütünlüğü."""

    def test_state_values_are_uppercase(self):
        """State string'leri DB'de tutulur; uppercase tutarlılığı kritik."""
        for s in AuditState:
            assert s.value == s.value.upper(), f"{s.name} değeri uppercase olmalı"

    def test_all_states_listed_in_transitions(self):
        """Tüm state'ler TRANSITIONS dict'inde geçmeli (explicit empty set dahil)."""
        for s in AuditState:
            assert s in TRANSITIONS, f"{s.value} TRANSITIONS'da yok"

    def test_final_is_terminal(self):
        """FINAL tek yönlü — geri dönüş yok (yasal/operasyonel kayıt)."""
        assert TRANSITIONS[AuditState.FINAL] == set(), "FINAL'dan geri dönülemez"

    def test_draft_only_goes_forward(self):
        """DRAFT'tan SUBMITTED/DOF_OPEN/DOF_CLOSED'a gidilebilir.

        B1: DÖF yoksa doğrudan DOF_CLOSED'a; DÖF varsa DOF_OPEN'a.
        SUBMITTED, eski uyumluluk için listede kalır (``compute_submit_target_state``
        onu kullanmasa da başka araçlar/migration'lar için teorik izin).
        """
        assert TRANSITIONS[AuditState.DRAFT] == {
            AuditState.SUBMITTED,
            AuditState.DOF_OPEN,
            AuditState.DOF_CLOSED,
        }

    def test_dof_open_can_only_close(self):
        """DOF_OPEN'dan DOF_CLOSED'a geçilebilir; SUBMITTED/FINAL'a dönülemez."""
        assert TRANSITIONS[AuditState.DOF_OPEN] == {AuditState.DOF_CLOSED}

    def test_dof_closed_to_final_only(self):
        """DOF_CLOSED'dan sadece FINAL'e gidilir."""
        assert TRANSITIONS[AuditState.DOF_CLOSED] == {AuditState.FINAL}

    def test_submitted_can_branch(self):
        """SUBMITTED'tan DÖF varsa DOF_OPEN, yoksa direkt DOF_CLOSED/FINAL."""
        assert TRANSITIONS[AuditState.SUBMITTED] == {
            AuditState.DOF_OPEN,
            AuditState.DOF_CLOSED,
            AuditState.FINAL,
        }


# ============ Davranış Matrisi ============

class TestBehaviorMatrix:
    """Her state için can_* helper'larının doğru değer döndürmesi."""

    @pytest.mark.parametrize("state,expected", [
        (AuditState.DRAFT,      (True,  True,  True,  True,  True)),
        (AuditState.SUBMITTED,  (False, False, True,  True,  False)),
        (AuditState.DOF_OPEN,   (False, False, True,  True,  True)),
        (AuditState.DOF_CLOSED, (False, False, True,  False, False)),
        (AuditState.FINAL,      (False, False, False, False, False)),
    ])
    def test_davranis_matrisi(self, state, expected):
        """Tüm 5 state için can_edit_answers, can_edit_meta, can_edit_declarations,
        can_open_dof, can_close_dof değerleri sabit."""
        e_ans, e_meta, e_decl, e_open, e_close = expected
        assert can_edit_answers(state) is e_ans, f"{state.value}: edit_answers"
        assert can_edit_meta(state) is e_meta, f"{state.value}: edit_meta"
        assert can_edit_declarations(state) is e_decl, f"{state.value}: edit_decl"
        assert can_open_dof(state) is e_open, f"{state.value}: open_dof"
        assert can_close_dof(state) is e_close, f"{state.value}: close_dof"

    def test_can_submit_only_draft(self):
        assert can_submit(AuditState.DRAFT) is True
        for s in (AuditState.SUBMITTED, AuditState.DOF_OPEN, AuditState.DOF_CLOSED, AuditState.FINAL):
            assert can_submit(s) is False, f"{s.value}: submit edilemez"

    def test_can_export_final_only_dof_closed_and_final(self):
        """İş birimi kuralı: 'Aktif DÖF varsa nihai rapor verilmez'."""
        assert can_export_final(AuditState.DRAFT) is False
        assert can_export_final(AuditState.SUBMITTED) is False
        assert can_export_final(AuditState.DOF_OPEN) is False
        assert can_export_final(AuditState.DOF_CLOSED) is True
        assert can_export_final(AuditState.FINAL) is True

    def test_can_export_draft_only_draft_and_submitted(self):
        """Taslak rapor: DRAFT ve SUBMITTED'ta mümkün."""
        assert can_export_draft(AuditState.DRAFT) is True
        assert can_export_draft(AuditState.SUBMITTED) is True
        for s in (AuditState.DOF_OPEN, AuditState.DOF_CLOSED, AuditState.FINAL):
            assert can_export_draft(s) is False, f"{s.value}: taslak rapor verilemez"

    def test_derive_is_completed(self):
        """Geriye uyumluluk: is_completed = (state in {DOF_CLOSED, FINAL})."""
        assert derive_is_completed(AuditState.DRAFT) is False
        assert derive_is_completed(AuditState.SUBMITTED) is False
        assert derive_is_completed(AuditState.DOF_OPEN) is False
        assert derive_is_completed(AuditState.DOF_CLOSED) is True
        assert derive_is_completed(AuditState.FINAL) is True

    def test_delete_behavior(self):
        """DRAFT=hard (gerçekten sil), diğer=soft (deleted_at), invalid=deny."""
        assert delete_behavior(AuditState.DRAFT) == "hard"
        for s in (AuditState.SUBMITTED, AuditState.DOF_OPEN, AuditState.DOF_CLOSED, AuditState.FINAL):
            assert delete_behavior(s) == "soft", f"{s.value}: soft-delete"


# ============ can_transition ============

class TestCanTransition:
    def test_valid_transitions(self):
        assert can_transition(AuditState.DRAFT, AuditState.SUBMITTED) is True
        assert can_transition(AuditState.DRAFT, AuditState.DOF_OPEN) is True
        assert can_transition(AuditState.SUBMITTED, AuditState.DOF_OPEN) is True
        assert can_transition(AuditState.SUBMITTED, AuditState.FINAL) is True
        assert can_transition(AuditState.DOF_OPEN, AuditState.DOF_CLOSED) is True
        assert can_transition(AuditState.DOF_CLOSED, AuditState.FINAL) is True

    def test_invalid_transitions(self):
        # Geriye dönüş yok
        assert can_transition(AuditState.SUBMITTED, AuditState.DRAFT) is False
        assert can_transition(AuditState.FINAL, AuditState.DRAFT) is False
        assert can_transition(AuditState.FINAL, AuditState.SUBMITTED) is False
        # Atlanan state'ler
        assert can_transition(AuditState.DRAFT, AuditState.FINAL) is False
        # B1 — DRAFT → DOF_CLOSED artık GEÇERLİ (DÖF yoksa direkt).
        assert can_transition(AuditState.DRAFT, AuditState.DOF_CLOSED) is True
        assert can_transition(AuditState.SUBMITTED, AuditState.DOF_CLOSED) is True  # DÖF yoksa direkt
        # FINAL'dan hiçbir yere
        for to_state in AuditState:
            assert can_transition(AuditState.FINAL, to_state) is False


# ============ compute_submit_target_state ============

class TestComputeSubmitTargetState:
    def test_no_dof_goes_to_dof_closed(self):
        """B1: HAYIR yok → DOF_CLOSED (exportable intermediate state).

        İlk geçerli nihai export sonrası ``transition_audit`` ile FINAL'a
        geçecek; bu fonksiyon sadece ``DRAFT`` kaynaklı submit hedefini hesaplar.
        Geçmişte ``SUBMITTED`` dönülürdü — bu, audit'i ``can_export_final=False``
        durumunda bırakıp nihai rapor döngüsünü kırıyordu (audit ``SUBMITTED``
        export edilemezdi). B1 düzeltmesi doğrudan DOF_CLOSED'a hedefler.
        """
        audit = {"state": "DRAFT"}
        assert compute_submit_target_state(audit, has_open_dof=False) == AuditState.DOF_CLOSED

    def test_with_dof_goes_to_dof_open(self):
        """HAYIR var → DOF_OPEN (direkt atlar)."""
        audit = {"state": "DRAFT"}
        assert compute_submit_target_state(audit, has_open_dof=True) == AuditState.DOF_OPEN

    def test_existing_dof_count_triggers_skip_to_dof_open(self):
        """``has_open_dof=True`` flag'i, HAYIR ya da daha önce açılan DÖF
        gerekçesiyle DOF_OPEN'a düşürür.

        (Önceden bu test ``has_open_dof=False`` ile SUBMITTED dönüyordu — bu
        hem yanlıştı hem B1 invariantıyla çelişiyordu. B1 düzeltmesiyle burada
        DOF_OPEN doğrulanır.)
        """
        audit = {"state": "DRAFT"}
        assert compute_submit_target_state(audit, has_open_dof=True) == AuditState.DOF_OPEN


# ============ compute_dof_resolution_target_state ============

class TestComputeDofResolutionTargetState:
    def test_dof_open_zero_remaining_goes_to_dof_closed(self):
        assert compute_dof_resolution_target_state(AuditState.DOF_OPEN, 0) == AuditState.DOF_CLOSED

    def test_dof_open_with_remaining_stays(self):
        assert compute_dof_resolution_target_state(AuditState.DOF_OPEN, 1) == AuditState.DOF_OPEN
        assert compute_dof_resolution_target_state(AuditState.DOF_OPEN, 3) == AuditState.DOF_OPEN

    def test_other_states_unchanged(self):
        """DOF_OPEN dışındaki state'lerde çağrı no-op."""
        for s in (AuditState.DRAFT, AuditState.SUBMITTED, AuditState.DOF_CLOSED, AuditState.FINAL):
            result = compute_dof_resolution_target_state(s, 0)
            assert result == s, f"{s.value} değişmemeliydi"

    def test_string_input_accepted(self):
        """State string olarak da kabul edilir (DB'den gelir)."""
        assert compute_dof_resolution_target_state("DOF_OPEN", 0) == AuditState.DOF_CLOSED


# ============ transition_audit ============

class TestTransitionAudit:
    def _now(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def test_idempotent_same_state(self):
        """Aynı state'e geçiş → sadece updated_at yenilenir, state_history büyümez."""
        doc = {"state": "DRAFT", "state_history": []}
        result = transition_audit(doc, AuditState.DRAFT, actor_id="u1", now_iso=self._now())
        assert "state" not in result  # değişmedi
        assert "is_completed" not in result
        assert "updated_at" in result
        assert "state_history" not in result  # append yok

    def test_draft_to_submitted(self):
        doc = {"state": "DRAFT", "state_history": []}
        result = transition_audit(
            doc, AuditState.SUBMITTED, actor_id="u1", reason="test", now_iso=self._now()
        )
        assert result["state"] == "SUBMITTED"
        assert result["is_completed"] is False
        assert len(result["state_history"]) == 1
        entry = result["state_history"][-1]
        assert entry["from"] == "DRAFT"
        assert entry["to"] == "SUBMITTED"
        assert entry["by"] == "u1"
        assert entry["reason"] == "test"

    def test_draft_to_dof_open_directly(self):
        """Submit edilen ve HAYIR olan audit direkt DOF_OPEN'a düşer."""
        doc = {"state": "DRAFT", "state_history": []}
        result = transition_audit(
            doc, AuditState.DOF_OPEN, actor_id="u1", reason="submit with DOF", now_iso=self._now()
        )
        assert result["state"] == "DOF_OPEN"

    def test_full_happy_path(self):
        """DRAFT → SUBMITTED → DOF_OPEN → DOF_CLOSED → FINAL."""
        doc = {"state": None, "state_history": []}

        # None → DRAFT (idempotent setup; create_audit'te state DRAFT set edilir)
        r = transition_audit(doc, AuditState.DRAFT, actor_id="u1", now_iso=self._now())
        doc.update(r)

        # DRAFT → SUBMITTED
        r = transition_audit(doc, AuditState.SUBMITTED, actor_id="u1", now_iso=self._now())
        doc.update(r)
        assert doc["state"] == "SUBMITTED"

        # SUBMITTED → DOF_OPEN
        r = transition_audit(doc, AuditState.DOF_OPEN, actor_id="u2", now_iso=self._now())
        doc.update(r)
        assert doc["state"] == "DOF_OPEN"

        # DOF_OPEN → DOF_CLOSED
        r = transition_audit(doc, AuditState.DOF_CLOSED, actor_id="u2", now_iso=self._now())
        doc.update(r)
        assert doc["state"] == "DOF_CLOSED"
        assert doc["is_completed"] is True

        # DOF_CLOSED → FINAL
        r = transition_audit(doc, AuditState.FINAL, actor_id="u1", now_iso=self._now())
        doc.update(r)
        assert doc["state"] == "FINAL"
        assert doc["is_completed"] is True

        # state_history 4 giriş içermeli (DRAFT init + 3 geçiş)
        # aslında DRAFT init idempotent olduğu için 3 giriş
        # ama senaryoda DRAFT'a geçiş yapılmadı (None zaten kabul edildi)
        assert len(doc["state_history"]) >= 3

    def test_invalid_transition_raises(self):
        """Geçersiz geçiş ValueError fırlatır."""
        doc = {"state": "FINAL", "state_history": []}
        with pytest.raises(ValueError, match="Geçersiz state geçişi"):
            transition_audit(doc, AuditState.DRAFT, actor_id="u1", now_iso=self._now())

    def test_state_history_appends_in_order(self):
        """Her geçiş append-only; sıra korunur."""
        doc = {"state": "DRAFT", "state_history": []}
        for target in (AuditState.SUBMITTED, AuditState.DOF_OPEN, AuditState.DOF_CLOSED, AuditState.FINAL):
            r = transition_audit(doc, target, actor_id=f"u{target.value}", now_iso=self._now())
            doc.update(r)
        history = doc["state_history"]
        assert len(history) == 4
        assert [h["to"] for h in history] == ["SUBMITTED", "DOF_OPEN", "DOF_CLOSED", "FINAL"]

    def test_string_state_input_accepted(self):
        """Doc'taki state string olabilir (DB'den okunduğu gibi)."""
        doc = {"state": "DRAFT", "state_history": []}
        r = transition_audit(doc, AuditState.SUBMITTED, actor_id="u1", now_iso=self._now())
        assert r["state"] == "SUBMITTED"


# ============ _coerce edge cases ============

class TestCoerceEdgeCases:
    def test_lowercase_string_normalized(self):
        from audit_state import _coerce
        assert _coerce("draft") == AuditState.DRAFT
        assert _coerce("submitted") == AuditState.SUBMITTED

    def test_mixed_case_string_normalized(self):
        from audit_state import _coerce
        assert _coerce("Dof_Open") == AuditState.DOF_OPEN
        assert _coerce("DoF_ClOsEd") == AuditState.DOF_CLOSED

    def test_dof_alias_resolves_to_dof_open(self):
        """Backward-compat: "DOF" → DOF_OPEN (eski data migration için)."""
        from audit_state import _coerce
        assert _coerce("DOF") == AuditState.DOF_OPEN

    def test_invalid_string_raises(self):
        from audit_state import _coerce
        with pytest.raises(ValueError, match="Geçersiz audit state"):
            _coerce("UNKNOWN_STATE")

    def test_non_string_raises(self):
        from audit_state import _coerce
        with pytest.raises(ValueError):
            _coerce(123)
        with pytest.raises(ValueError):
            _coerce(None)
