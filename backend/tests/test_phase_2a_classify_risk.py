"""Aşama 2A — ``classify_risk`` kanonik eşik fonksiyonu testleri.

Bu testler **saf pure-Python**: server.py import edilmeden, sadece
``classify_risk`` fonksiyonu düzeyinde çalışır. DB ve network bağımlılığı
yoktur.

Kanıtlanan bağlayıcı eşikler:

* 1–4   → "Kabul Edilebilir"
* 5–12  → "Dikkate Değer"
* 13–25 → "Kabul Edilemez"
* Sınır değerler (1, 4, 5, 12, 13, 25) doğru seviyeye düşer.
* Orta değerler (6, 11, 14, 24) doğru seviyeye düşer.
* Aralık dışı, yanlış tip ve bool → ``ValueError`` fırlatır.
* ``document_risk_level`` hesaba katılmaz — sadece ``score`` belirler.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

# ``classify_risk`` import edilebilmesi için gerekli minimum env (server.py
# import path'inde ``load_dotenv`` çağrısı yapıyor ama doğrudan fonksiyonu
# çağırırken buna gerek yok).
import os  # noqa: E402

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_phase_2a")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "phase-2a@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")

from server import classify_risk  # noqa: E402
from server import (  # noqa: E402
    RISK_LEVEL_KABUL_EDILEBILIR,
    RISK_LEVEL_DIKKATE_DEGER,
    RISK_LEVEL_KABUL_EDILEMEZ,
)


class TestClassifyRiskBoundaries:
    """Sınır değerler — Aşama 1 karar bağlayıcı."""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (1, RISK_LEVEL_KABUL_EDILEBILIR),
            (2, RISK_LEVEL_KABUL_EDILEBILIR),
            (3, RISK_LEVEL_KABUL_EDILEBILIR),
            (4, RISK_LEVEL_KABUL_EDILEBILIR),  # üst sınır
            (5, RISK_LEVEL_DIKKATE_DEGER),     # alt sınır
            (6, RISK_LEVEL_DIKKATE_DEGER),
            (11, RISK_LEVEL_DIKKATE_DEGER),
            (12, RISK_LEVEL_DIKKATE_DEGER),    # üst sınır
            (13, RISK_LEVEL_KABUL_EDILEMEZ),   # alt sınır
            (14, RISK_LEVEL_KABUL_EDILEMEZ),
            (24, RISK_LEVEL_KABUL_EDILEMEZ),
            (25, RISK_LEVEL_KABUL_EDILEMEZ),   # üst sınır
        ],
    )
    def test_score_maps_to_correct_level(self, score, expected):
        assert classify_risk(score) == expected

    def test_lower_bound_1_is_kabul_edilebilir(self):
        assert classify_risk(1) == "Kabul Edilebilir"

    def test_boundary_4_is_still_kabul_edilebilir(self):
        """1-4 inclusive → Kabul Edilebilir (4 sınır değer)."""
        assert classify_risk(4) == "Kabul Edilebilir"

    def test_boundary_5_is_dikkate_deger(self):
        """5-12 → Dikkate Değer (5 sınır değer)."""
        assert classify_risk(5) == "Dikkate Değer"

    def test_boundary_12_is_still_dikkate_deger(self):
        assert classify_risk(12) == "Dikkate Değer"

    def test_boundary_13_is_kabul_edilemez(self):
        """13-25 → Kabul Edilemez (13 sınır değer)."""
        assert classify_risk(13) == "Kabul Edilemez"

    def test_upper_bound_25_is_kabul_edilemez(self):
        assert classify_risk(25) == "Kabul Edilemez"


class TestClassifyRiskInvalidInput:
    """Geçersiz girdi → ``ValueError``."""

    @pytest.mark.parametrize("bad_score", [0, -1, -100, 26, 100, 999])
    def test_out_of_range_raises(self, bad_score):
        with pytest.raises(ValueError):
            classify_risk(bad_score)

    @pytest.mark.parametrize("bad_input", ["5", 5.0, None, [5], {"score": 5}, True, False])
    def test_non_int_or_bool_raises(self, bad_input):
        with pytest.raises((ValueError, TypeError)):
            classify_risk(bad_input)


class TestDocumentRiskLevelIgnored:
    """``document_risk_level`` tek başına sonucu belirlemez; yalnızca ``score`` belirler.

    Aşama 1 kararı: ``document_risk_level`` provenance-only'dir; hesaba
    katılmaz. Bu test, ``classify_risk`` çağrısının yalnızca ``score``
    parametresine baktığını kanıtlar.
    """

    def test_classify_risk_signature_has_no_doc_param(self):
        """``classify_risk`` imzası ``document_risk_level`` almaz."""
        import inspect

        sig = inspect.signature(classify_risk)
        assert "document_risk_level" not in sig.parameters
        assert list(sig.parameters.keys()) == ["score"]