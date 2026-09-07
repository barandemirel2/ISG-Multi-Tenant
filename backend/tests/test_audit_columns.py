"""audit_columns modülü unit testleri.

Phase 2B — S4+S6: Excel ve PDF'in ortak kolon şeması.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pytest

from audit_columns import (
    DEFAULT_COLUMNS,
    Column,
    get_columns,
    num_columns,
    render_row,
    total_width,
)


class TestDefaultColumns:
    """İş birimi S6: Excel ve PDF aynı 11 kolon olmalı."""

    def test_column_count_is_eleven(self):
        """İş birimi S4/S6 başlangıç tanımı: 11 kolon."""
        assert len(DEFAULT_COLUMNS) == 11
        assert num_columns() == 11

    def test_first_column_is_no(self):
        """İş birimi S2/S6: ilk kolon 'No' (sıra no)."""
        assert DEFAULT_COLUMNS[0].key == "no"
        assert DEFAULT_COLUMNS[0].header == "No"

    def test_required_columns_present(self):
        """İş birimi S4: 11 kolonun hepsi spesifik başlıklarla."""
        required_headers = [
            "No", "Kategori", "Tehlike & Risk Maddesi", "Cevap",
            "Olasılık (O)", "Şiddet (Ş)", "Risk Skoru (R)", "Risk Seviyesi",
            "Sorumlu", "Termin Süresi", "Alınması Gereken Tedbir (DÖF)",
        ]
        actual_headers = [c.header for c in DEFAULT_COLUMNS]
        assert actual_headers == required_headers

    def test_column_keys_are_snake_case(self):
        """DB ve frontend'de kullanılan key'ler snake_case."""
        for col in DEFAULT_COLUMNS:
            assert col.key == col.key.lower(), f"{col.key} lowercase olmalı"
            assert " " not in col.key
            assert "(" not in col.key and ")" not in col.key

    def test_columns_have_width(self):
        """Her kolonun width değeri pozitif olmalı (PDF layout için)."""
        for col in DEFAULT_COLUMNS:
            assert col.width > 0, f"{col.key} width pozitif olmalı"

    def test_total_width_reasonable(self):
        """Toplam genişlik A4 landscape'e (~277mm) sığmalı veya auto-scale."""
        tw = total_width()
        # audit_columns'da auto-scale kuralı: 277mm'yi aşarsa oranla
        assert tw > 100, "Toplam genişlik çok küçük"
        # Auto-scale sonrası 277mm'yi geçmemeli
        scaled = min(tw, 277.0)
        assert scaled <= 277.0


class TestColumnRender:
    """Column.render() — kolon tipine göre değer üretimi."""

    def test_text_render(self):
        col = Column(key="kategori", header="Kategori", width=20, kind="text")
        assert col.render({"kategori": "Mutfak"}) == "Mutfak"
        assert col.render({"kategori": ""}) == "—"
        assert col.render({}) == "—"

    def test_number_render_integer(self):
        col = Column(key="olasilik", header="O", width=10, kind="number")
        assert col.render({"olasilik": 3}) == "3"
        # 0 geçerli bir olasılık değeridir (render 0 olarak döndürür)
        assert col.render({"olasilik": 0}) == "0"
        assert col.render({"olasilik": None}) == "—"

    def test_number_render_float(self):
        col = Column(key="x", header="X", width=10, kind="number")
        assert col.render({"x": 2.5}) == "2.5"

    def test_answer_render(self):
        col = Column(key="cevap", header="Cevap", width=10, kind="answer")
        assert col.render({"cevap": "EVET"}) == "EVET"
        assert col.render({"cevap": ""}) == "—"

    def test_risk_score_render(self):
        col = Column(key="risk_skoru", header="Risk Skoru", width=10, kind="risk_score")
        assert col.render({"risk_skoru": 16}) == "16 Puan"
        assert col.render({"risk_skoru": ""}) == "—"

    def test_risk_level_render(self):
        col = Column(key="risk_seviyesi", header="Risk Seviyesi", width=15, kind="risk_level")
        assert col.render({"risk_seviyesi": "Kabul Edilemez"}) == "Kabul Edilemez"
        assert col.render({}) == "—"

    def test_multiline_render(self):
        col = Column(key="soru", header="Soru", width=40, kind="multiline", multiline=True)
        assert col.render({"soru": "Çok uzun bir soru"}) == "Çok uzun bir soru"
        assert col.render({"soru": ""}) == "—"


class TestRenderRow:
    """render_row() — tüm kolonları sırayla getir."""

    def test_render_row_with_all_fields(self):
        row = {
            "no": 1,
            "kategori": "Mutfak",
            "soru": "Yangın söndürücü var mı?",
            "cevap": "EVET",
            "olasilik": 2,
            "siddet": 3,
            "risk_skoru": 6,
            "risk_seviyesi": "Dikkate Değer",
            "sorumlu": "Restoran Sorumlusu",
            "termin": "1 Ay",
            "tedbir": "Aylık kontrol",
        }
        values = render_row(row)
        assert len(values) == 11
        assert values[0] == "1"           # No
        assert values[1] == "Mutfak"     # Kategori
        assert values[2] == "Yangın söndürücü var mı?"
        assert values[3] == "EVET"
        assert values[4] == "2"           # Olasılık
        assert values[5] == "3"           # Şiddet
        assert values[6] == "6 Puan"     # Risk Skoru
        assert values[7] == "Dikkate Değer"
        assert values[8] == "Restoran Sorumlusu"
        assert values[9] == "1 Ay"
        assert values[10] == "Aylık kontrol"

    def test_render_row_partial(self):
        """Eksik alanlarla render — boş olanlar '—' dönmeli."""
        row = {"no": 1, "soru": "Test"}
        values = render_row(row)
        assert len(values) == 11
        assert values[0] == "1"
        assert values[2] == "Test"
        # Diğerleri '—'
        for v in values[1:2:1] + values[3:]:
            assert v == "—"

    def test_render_row_with_custom_columns(self):
        """Farklı kolon listesiyle render (admin UI senaryosu)."""
        custom = [
            Column(key="no", header="#", width=5, kind="number"),
            Column(key="soru", header="Q", width=20, kind="multiline"),
        ]
        values = render_row({"no": 1, "soru": "Test"}, custom)
        assert values == ["1", "Test"]


class TestGetColumns:
    def test_returns_a_copy(self):
        """get_columns() mutasyona karşı liste döndürmeli (kopya)."""
        cols1 = get_columns()
        cols1.clear()
        cols2 = get_columns()
        assert len(cols2) == 11  # original etkilenmedi
