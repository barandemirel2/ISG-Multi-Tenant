"""audit_log modülü unit testleri.

Phase 2B — S20: 6 yıl retention, append-only activity log, arşivleme.

Çalıştırma: ``pytest backend/tests/test_audit_log.py -v``
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pytest

from audit_log import (
    Action,
    RETENTION_YEARS,
    compute_retention_until,
    is_retention_expired,
)
from dateutil.relativedelta import relativedelta


# ============ compute_retention_until ============

class TestComputeRetentionUntil:
    def test_retention_is_six_years(self):
        """İş birimi kuralı: kanunen 6 yıl saklama."""
        created = "2026-01-01T00:00:00+00:00"
        result = compute_retention_until(created)
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        created_dt = datetime.fromisoformat(created)
        # 6 yıl = ~2191 gün (artık yıllar dahil)
        delta_days = (result_dt - created_dt).days
        assert 2190 <= delta_days <= 2192, f"Expected ~6 years, got {delta_days} days"

    def test_retention_constant_is_six(self):
        """RETENTION_YEARS = 6 — mevzuat gereği."""
        assert RETENTION_YEARS == 6

    def test_retention_with_no_input_uses_now(self):
        """``created_at_iso=None`` → now() + 6y."""
        result = compute_retention_until(None)
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_days = (result_dt - now).days
        # 6 yıl = 2190 gün. ``now`` test'inde fonksiyonun kendi ``now``'ından
        # sonra çağrıldığı için delta 1 gün aşağı yuvarlanabilir (pytest-xdist
        # altında timing gap büyüyor). Kabul aralığı 2189-2191.
        assert 2189 <= delta_days <= 2191

    def test_retention_with_garbage_string_falls_back(self):
        """Geçersiz ISO string → now() + 6y (parser'ı yıkmaz)."""
        result = compute_retention_until("not-a-date")
        result_dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_days = (result_dt - now).days
        # Test sırasında ``now`` fonksiyondan sonra çağrıldığı için delta
        # 1 gün aşağı yuvarlanabilir (pytest-xdist altında timing gap büyüyor).
        assert 2189 <= delta_days <= 2191

    def test_retention_z_suffix(self):
        """``Z`` suffix'i de parse edilmeli (UTC indicator)."""
        from datetime import datetime as _dt
        result = compute_retention_until("2026-01-01T00:00:00Z")
        result_dt = _dt.fromisoformat(result.replace("Z", "+00:00"))
        # 2026'dan 6 yıl sonra 2031 veya 2032 (artık yıl hesabı, 1 gün oynayabilir)
        assert result_dt.year in (2031, 2032), f"Beklenen 2031 veya 2032, got {result_dt.year}"
        # Toplam süre 2190-2192 gün arası (artık yıllar dahil)
        created_dt = _dt(2026, 1, 1, tzinfo=_dt.now(timezone.utc).tzinfo)
        delta_days = (result_dt - created_dt).days
        assert 2190 <= delta_days <= 2192

    # --- B8: exact calendar-year arithmetic ---

    def test_ordinary_date_exact_calendar_years(self):
        """Sıradan tarih: tam 6 takvim yılı, gün/ay değişmez (365*6 kayması yok)."""
        result = compute_retention_until("2026-01-15T00:00:00+00:00")
        assert result == "2032-01-15T00:00:00+00:00", result

    def test_leap_day_feb29_clamps_to_feb28(self):
        """29 Şubat (artık gün) + 6 yıl → hedef yıl artık değilse 28 Şubat.

        ``relativedelta`` takvim aritmetiği 29 Şubat'ı hedef yılda yoksa ayın
        son gününe (28 Şubat) kilitler; ``365*6`` ise 1 gün kaydırırdı.
        """
        # 2024 artık yıl; 2030 artık DEĞİL.
        result = compute_retention_until("2024-02-29T00:00:00+00:00")
        assert result == "2030-02-28T00:00:00+00:00", result

    def test_leap_day_feb29_to_leap_year_keeps_feb29(self):
        """29 Şubat + 4 yıl (artık → artık): gün korunur (29 Şubat kalır)."""
        # Bu test retention'dan bağımsız olarak takvim aritmetiğini doğrular:
        # 2028 artık yıl, 2024 + 4y = 2028 artık → 29 Şubat korunur.
        dt = datetime(2024, 2, 29, tzinfo=timezone.utc)
        assert (dt + relativedelta(years=4)).isoformat() == "2028-02-29T00:00:00+00:00"

    def test_leap_year_crossing_exact_days(self):
        """Artık yıl geçişi: 2024→2030 tam 2192 gün (2 artık gün), 2190 değil."""
        result = compute_retention_until("2024-01-15T00:00:00+00:00")
        result_dt = datetime.fromisoformat(result)
        created_dt = datetime.fromisoformat("2024-01-15T00:00:00+00:00")
        # 2024 (29 Şub) + 2028 (29 Şub) → 6*365 + 2 = 2192 gün.
        assert (result_dt - created_dt).days == 2192, (result_dt - created_dt).days
        # Ve gün/ay aynı kalır.
        assert (result_dt.month, result_dt.day) == (1, 15)

    def test_timezone_aware_input_preserves_offset(self):
        """Timezone-aware input: UTC offset korunur (UTC'ye çevrilmez/atılmaz)."""
        result = compute_retention_until("2026-06-15T00:00:00+03:00")
        # 6 takvim yılı sonrası, aynı +03:00 offset korunmalı.
        assert result == "2032-06-15T00:00:00+03:00", result

    def test_naive_input_does_not_claim_timezone(self):
        """Naive (tz'siz) input: tz bilgisi uydurulmamalı (naive kalır)."""
        result = compute_retention_until("2026-06-15T10:30:00")
        assert result == "2032-06-15T10:30:00", result


# ============ is_retention_expired ============

class TestIsRetentionExpired:
    def test_future_not_expired(self):
        """Gelecekteki retention → expired değil."""
        future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        assert is_retention_expired(future) is False

    def test_past_expired(self):
        """Geçmiş tarihli retention → expired."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        assert is_retention_expired(past) is True

    def test_now_equals_expired(self):
        """Şu an ile eşit → expired (boundary)."""
        now = datetime.now(timezone.utc)
        assert is_retention_expired(now.isoformat()) is True

    def test_none_not_expired(self):
        """``retention_until=None`` → expired değil (veri yok, kontrol atlanır)."""
        assert is_retention_expired(None) is False

    def test_empty_string_not_expired(self):
        """Boş string → expired değil."""
        assert is_retention_expired("") is False

    def test_invalid_string_not_expired(self):
        """Parse edilemeyen string → expired değil (güvenli default)."""
        assert is_retention_expired("garbage") is False

    def test_just_created_6_years_future(self):
        """Tam 6 yıl sonrası expired olmamalı (sınırda 1 gün tolerans)."""
        # created_at'tan tam 6 yıl = expired değil
        future = (datetime.now(timezone.utc) + timedelta(days=365 * 6)).isoformat()
        # Bu tam sınırda; ``<=`` kontrolü expired sayar. Bir gün sonrası test edelim.
        future_plus = (datetime.now(timezone.utc) + timedelta(days=365 * 6 + 1)).isoformat()
        assert is_retention_expired(future_plus) is False


# ============ Action enum ============

class TestActionEnum:
    def test_action_values_are_snake_case(self):
        """Action değerleri snake_case string olmalı (DB'de tutulur)."""
        for attr in dir(Action):
            if attr.startswith("_"):
                continue
            value = getattr(Action, attr)
            if isinstance(value, str):
                assert value == value.lower(), f"{attr} = {value} lowercase olmalı"
                assert " " not in value, f"{attr} boşluk içermemeli"

    def test_required_actions_exist(self):
        """İş akışı için gerekli action'lar tanımlı olmalı."""
        required = [
            "create", "submit", "answer_update", "meta_update",
            "declaration_update", "dof_update", "dof_close",
            "export_pdf", "export_excel", "export_finalize",
            "delete", "soft_delete", "archive", "login", "logout",
        ]
        for action in required:
            assert hasattr(Action, action.upper()), f"Action.{action.upper()} tanımsız"
            assert getattr(Action, action.upper()) == action, f"Action.{action.upper()} yanlış değer"


# Not: ``log_action`` async DB çağrısı yapar; unit test yerine
# integration test (``test_phase_2a_*``) ve E2E test ile doğrulanır.
# Burada sadece pure logic testleri var; mock'lu async testler
# pytest-asyncio mode'a bağlı olduğu için çıkarıldı.
