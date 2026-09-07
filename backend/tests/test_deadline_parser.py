"""parse_deadline_to_days unit testleri (UAT S1 kapsamı).

Test scope'ları AGENTS.md §6'ya göre ayrı raporlanır:
- Hedefli test (bu dosya): parse_deadline_to_days helper'ı
- Full backend suite: ``cd backend && pytest`` (84+ test)
- Frontend: değişmedi
- Production build: değişmedi
- E2E: S1 sonrası mevcut 11 script hâlâ yeşil olmalı
"""
from __future__ import annotations

from deadline_parser import parse_deadline_to_days


class TestParseDeadlineContinuous:
    """Sürekli termin → None (anında müdahale, deadline yok)."""

    def test_surekli_capitalized(self):
        assert parse_deadline_to_days("Sürekli") is None

    def test_surekli_lowercase(self):
        assert parse_deadline_to_days("sürekli") is None

    def test_surekli_ascii_fallback(self):
        """ASCII fallback encoding hatalarına karşı koruma."""
        assert parse_deadline_to_days("surekli") is None

    def test_surekli_with_whitespace(self):
        assert parse_deadline_to_days("  Sürekli  ") is None


class TestParseDeadlineAcil:
    """Acil → 1 gün."""

    def test_acil_lowercase(self):
        assert parse_deadline_to_days("acil") == 1

    def test_acil_capitalized(self):
        assert parse_deadline_to_days("Acil") == 1


class TestParseDeadlineGun:
    """X gün → X (doğrudan sayı)."""

    def test_1_gun(self):
        assert parse_deadline_to_days("1 gün") == 1

    def test_5_gun(self):
        """ESKİ BUG: '5 gün' → 90 (else branch) idi, YENİ: 5."""
        assert parse_deadline_to_days("5 gün") == 5

    def test_10_gun(self):
        """ESKİ BUG: '10 gün' → 30 ('1' in '10' → 30) idi, YENİ: 10."""
        assert parse_deadline_to_days("10 gün") == 10

    def test_30_gun(self):
        assert parse_deadline_to_days("30 gün") == 30

    def test_90_gun(self):
        assert parse_deadline_to_days("90 gün") == 90


class TestParseDeadlineAy:
    """X ay → X * 30."""

    def test_1_ay_capitalized(self):
        """questions.json'da gerçek değer: '1 Ay'."""
        assert parse_deadline_to_days("1 Ay") == 30

    def test_1_ay_lowercase(self):
        assert parse_deadline_to_days("1 ay") == 30

    def test_2_ay(self):
        assert parse_deadline_to_days("2 ay") == 60

    def test_3_ay(self):
        """ESKİ BUG: '3 ay' → 90 (else branch) doğru, YENİ: 90 (aynı, doğru)."""
        assert parse_deadline_to_days("3 ay") == 90

    def test_6_ay(self):
        assert parse_deadline_to_days("6 ay") == 180


class TestParseDeadlineHafta:
    """X hafta → X * 7."""

    def test_1_hafta(self):
        assert parse_deadline_to_days("1 hafta") == 7

    def test_2_hafta(self):
        """ESKİ BUG: '2 hafta' → 60 ('2' var diye) idi, YENİ: 14."""
        assert parse_deadline_to_days("2 hafta") == 14

    def test_4_hafta(self):
        assert parse_deadline_to_days("4 hafta") == 28


class TestParseDeadlineYil:
    """X yıl → X * 365."""

    def test_1_yil(self):
        """ESKİ BUG: '1 yıl' → 30 ('1' var diye) idi, YENİ: 365."""
        assert parse_deadline_to_days("1 yıl") == 365

    def test_2_yil(self):
        assert parse_deadline_to_days("2 yıl") == 730

    def test_yil_ascii(self):
        assert parse_deadline_to_days("1 yil") == 365


class TestParseDeadlineEdgeCases:
    """Boş/None/garbage → None + log warning. Strict parse: fazladan karakter yok."""

    def test_empty_string(self):
        assert parse_deadline_to_days("") is None

    def test_none(self):
        assert parse_deadline_to_days(None) is None

    def test_whitespace_only(self):
        assert parse_deadline_to_days("   ") is None

    def test_garbage_string(self):
        assert parse_deadline_to_days("asdf") is None

    def test_number_only(self):
        """Sayı var ama birim yok → parse edilemez."""
        assert parse_deadline_to_days("30") is None

    def test_unit_only(self):
        """Birim var ama sayı yok → parse edilemez."""
        assert parse_deadline_to_days("gün") is None

    def test_invalid_format_with_extra_words(self):
        """Strict: 'yaklaşık 1 ay' → None (fazladan kelime, S1 alan adı ile aynı anlam değil)."""
        assert parse_deadline_to_days("yaklaşık 1 ay") is None

    def test_invalid_format_with_trailing_dot(self):
        """Strict: '5 gün.' → None (trailing punctuation)."""
        assert parse_deadline_to_days("5 gün.") is None

    def test_invalid_format_with_preposition(self):
        """Strict: 'en fazla 1 ay' → None (fazladan kelime)."""
        assert parse_deadline_to_days("en fazla 1 ay") is None

    def test_acil_with_extra_words(self):
        """Strict: 'çok acil' → None (acil exact match olmalı)."""
        assert parse_deadline_to_days("çok acil") is None

    def test_surekli_with_extra_words(self):
        """Strict: 'sürekli denetim' → None (sürekli exact match olmalı)."""
        assert parse_deadline_to_days("sürekli denetim") is None


class TestParseDeadlineNoWhitespace:
    r"""Boşluksuz formatlar da desteklenmeli (regex \s* whitespace tolerant)."""

    def test_5gun_no_space(self):
        assert parse_deadline_to_days("5gun") == 5

    def test_30gun_no_space(self):
        assert parse_deadline_to_days("30gun") == 30

    def test_2ay_no_space(self):
        assert parse_deadline_to_days("2ay") == 60


class TestParseDeadlineSaat:
    """X saat → 1 gün (acil muadili, saha tespit anında müdahale)."""

    def test_1_saat(self):
        assert parse_deadline_to_days("1 saat") == 1

    def test_3_saat(self):
        assert parse_deadline_to_days("3 saat") == 1

    def test_24_saat(self):
        """Büyük saat değerleri de 1 gün (acil muadili — saat dilimi
        birimi gün-katına taşınmaz, semantic olarak 'acil' kategorisinde).
        """
        assert parse_deadline_to_days("24 saat") == 1

    def test_saat_no_space(self):
        assert parse_deadline_to_days("3saat") == 1
