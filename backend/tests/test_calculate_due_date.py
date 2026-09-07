"""_calculate_due_date bütünleşik testleri (UAT S1 + current-main uyumluluğu).

Bu paket, ``backend/server.py::_calculate_due_date`` fonksiyonunun
PR #13 sonrası entegrasyon davranışını belgeler:

* Strict parser başarılıysa ``parse_deadline_to_days`` çıktısını kullanır.
* "Sürekli" termin → ``None`` (kasıtlı S1 değişikliği; anında müdahale).
* Parse edilemeyen değer (boş/None/garbage/eksik format) → **90 gün**
  fallback (PR #13 öncesi main davranışı, geriye uyumluluk).
* Geçerli tarih parse edilemezse ``datetime.now(timezone.utc)`` kullanılır.

Hedefli test, full backend suite'in parçası olarak çalışır.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import server
from server import _calculate_due_date


CREATED_ISO = "2026-01-15T12:00:00+00:00"
BASE = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _td(days: int):
    return timedelta(days=days)


class TestCalculateDueDateSurekli:
    """'Sürekli' / 'surekli' → None (S1 kasıtlı değişiklik)."""

    def test_surekli_capitalized(self):
        assert _calculate_due_date(CREATED_ISO, "Sürekli") is None

    def test_surekli_lowercase(self):
        assert _calculate_due_date(CREATED_ISO, "sürekli") is None

    def test_surekli_ascii_fallback(self):
        assert _calculate_due_date(CREATED_ISO, "surekli") is None

    def test_surekli_with_whitespace(self):
        assert _calculate_due_date(CREATED_ISO, "  Sürekli  ") is None

    def test_surekli_in_phrase(self):
        """Substring match: 'sürekli denetim' içeren termin de None."""
        assert _calculate_due_date(CREATED_ISO, "sürekli denetim") is None


class TestCalculateDueDateValid:
    """Parser'ın strict parse başarısı → beklenen gün sayısı."""

    def test_acil_returns_one_day(self):
        out = _calculate_due_date(CREATED_ISO, "acil")
        assert out is not None
        assert out == (BASE + _td(1)).isoformat()

    def test_5_gun(self):
        out = _calculate_due_date(CREATED_ISO, "5 gün")
        assert out == (BASE + _td(5)).isoformat()

    def test_30_gun(self):
        out = _calculate_due_date(CREATED_ISO, "30 gün")
        assert out == (BASE + _td(30)).isoformat()

    def test_2_ay(self):
        out = _calculate_due_date(CREATED_ISO, "2 ay")
        assert out == (BASE + _td(60)).isoformat()

    def test_2_hafta(self):
        out = _calculate_due_date(CREATED_ISO, "2 hafta")
        assert out == (BASE + _td(14)).isoformat()

    def test_1_yil(self):
        out = _calculate_due_date(CREATED_ISO, "1 yıl")
        assert out == (BASE + _td(365)).isoformat()

    def test_3_saat(self):
        """saat → 1 gün (acil muadili)."""
        out = _calculate_due_date(CREATED_ISO, "3 saat")
        assert out == (BASE + _td(1)).isoformat()

    def test_zulu_iso_normalized(self):
        """'Z' soneki ISO parse'ında +00:00 olarak normalize olur."""
        out = _calculate_due_date("2026-06-01T00:00:00Z", "5 gün")
        assert out is not None
        assert out.startswith("2026-06-06")


class TestCalculateDueDateFallback:
    """Parser None döndürürse → current-main 90 gün fallback (geriye uyumluluk).

    Bu davranış PR #13 öncesi main davranışıdır (else → 90).
    S1 strict parser boş/garbage/eksik format için None döndürür;
    main'deki eski 90 gün default'u bu integration'da korunmuştur.
    """

    def test_empty_string_returns_90_days(self):
        out = _calculate_due_date(CREATED_ISO, "")
        assert out == (BASE + _td(90)).isoformat()

    def test_whitespace_only_returns_90_days(self):
        out = _calculate_due_date(CREATED_ISO, "   ")
        assert out == (BASE + _td(90)).isoformat()

    def test_none_input_returns_90_days(self):
        out = _calculate_due_date(CREATED_ISO, None)
        assert out == (BASE + _td(90)).isoformat()

    def test_garbage_returns_90_days(self):
        out = _calculate_due_date(CREATED_ISO, "asdf")
        assert out == (BASE + _td(90)).isoformat()

    def test_number_only_returns_90_days(self):
        """'30' → birim yok → parse None → 90 fallback."""
        out = _calculate_due_date(CREATED_ISO, "30")
        assert out == (BASE + _td(90)).isoformat()

    def test_unit_only_returns_90_days(self):
        out = _calculate_due_date(CREATED_ISO, "gün")
        assert out == (BASE + _td(90)).isoformat()

    def test_extra_word_strict_reject_returns_90_days(self):
        """Strict: 'yaklaşık 1 ay' → None → 90 fallback."""
        out = _calculate_due_date(CREATED_ISO, "yaklaşık 1 ay")
        assert out == (BASE + _td(90)).isoformat()

    def test_trailing_dot_returns_90_days(self):
        out = _calculate_due_date(CREATED_ISO, "5 gün.")
        assert out == (BASE + _td(90)).isoformat()


class TestCalculateDueDateDateParsing:
    """``created_at_iso`` geçersizse ``datetime.now(tz=utc)`` kullanılır."""

    def test_invalid_created_iso_uses_now(self):
        """Geçersiz ISO → now fallback; sonuç hâlâ parse edilebilir ISO."""
        out = _calculate_due_date("not-a-date", "5 gün")
        assert out is not None
        parsed = datetime.fromisoformat(out)
        assert parsed.tzinfo is not None
        # Bugün + 5 gün civarı olmalı (toleransla).
        delta = (parsed - datetime.now(timezone.utc)).total_seconds()
        assert abs(delta - 5 * 86400) < 60


class TestCalculateDueDateIntegrationShape:
    """Sunucu tarafındaki gerçek kullanım: ``DofUpdateInput`` akışıyla uyum."""

    def test_helper_callable(self):
        """_calculate_due_date server modülünden erişilebilir."""
        assert callable(server._calculate_due_date)

    def test_real_call_does_not_raise_on_edge_inputs(self):
        """Tüm edge-case input kombinasyonları hata vermez."""
        for value in ("", "  ", None, "asdf", "Sürekli", "5 gün", "acil",
                      "30", "gün", "yaklaşık 1 ay", "3 saat"):
            out = _calculate_due_date(CREATED_ISO, value)
            # Sürekli → None; diğerleri ISO string veya None (Sürekli).
            assert (out is None) or isinstance(out, str), (
                f"value={value!r} returned {out!r}"
            )
