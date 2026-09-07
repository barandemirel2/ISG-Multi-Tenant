"""S13 — PDF Footer + İmza Alanı testleri.

Bu test paketi, ``backend/server.py::export_pdf`` endpoint'inin S13
kapsamında eklenen iki yeni davranışı doğrular:

  1. **Footer callback** (``_draw_export_pdf_footer``) — her sayfada
     alt kenarda üç parçalı içerik:

       * Sol  : ``Denetçi: <ad>``
       * Orta : ``<restoran_adı> — <state>``
       * Sağ  : ``Sayfa X``

     Reportlab callback olduğu için ``onFirstPage`` ve ``onLaterPages``
     aynı callback'i paylaşır; bu nedenle footer'ın **her sayfada**
     görünmesi garanti edilir (single-page ve multi-page PDF'lerde
     ayrı ayrı doğrulanır).

  2. **İmza Alanları tablosu** (4 imza kutusu) — son sayfada, S20 İbraz
     belgesiyle birebir aynı şema: ``Denetçi / Restoran Müdürü /
     İşveren Vekili / İSG Uzmanı``. Landscape A4 içinde 4 × 44 mm
     sütun genişliğinde Table + TableStyle.

Tasarım kararları:

* Test_pdf_export_design.py'deki ``_build_pdf`` / ``_pdf_pages_and_text``
  / ``_wrap_tolerant`` / ``_all_text_normalized`` helper'ları
  **kopyalanmaz**; aynı modülden import edilir. Tekrar yok, tutarlılık
  var (PdfSigLabel gibi yeni stiller test edilirken aynı metin
  normalizasyonu kullanılır).

* PyPDF2 bağımlılığı zorunlu değil; yoksa ``pytest.skip`` ile geçilir
  (mevcut design testleriyle aynı politika).

* Çok sayfalı davranış için ``_many_questions()`` (60 soru) üretilir;
  main 11-kolon tablosu + repeatRows=1 nedeniyle PDF 2+ sayfa olur.
  Footer'ın her sayfada olduğu sayfa-bazlı aramayla kanıtlanır.

* Footer metin normalizasyonu: ``Denetçi:`` ve ``Sayfa`` token'ları
  PyPDF2 extract_text'in wrap noktalarıyla bozulabilir; ``_wrap_tolerant``
  bu nedenle zorunludur.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

try:
    import PyPDF2  # type: ignore
    HAS_PYPDF2 = True
except Exception:  # pragma: no cover
    PyPDF2 = None  # type: ignore
    HAS_PYPDF2 = False

from _phase_2a_helpers import (
    fake_db,
    push_audit,
    run_async,
    sample_audit_doc,
    sample_template_doc,
)
import server
from server import export_pdf

# test_pdf_export_design.py ile aynı helper'lar (kolon sırası, metin
# normalizasyonu vb. tutarlılığı için).
from test_pdf_export_design import (  # type: ignore
    _build_pdf,
    _collect_bytes,
    _pdf_pages_and_text,
    _wrap_tolerant,
    _all_text_normalized,
)


AID = "507f1f77bcf86cd799439011"


def _standard_questions():
    """test_pdf_export_design.py ile aynı 3-soru seed'i."""
    return [
        {
            "id": 1, "no": 1, "category": "Elektrik Güvenliği",
            "area": "Elektrik & Pano",
            "question": "Şişli şubesinde elektrik panosu etiketleri güncel mi?",
            "responsible": "İSG Uzmanı — Çağatay Gümüş",
            "default_probability": 5, "default_severity": 5,
            "default_risk_score": 25, "default_risk_level": "Kabul Edilemez",
            "document_risk_level": "Kabul Edilemez",
            "deadline": "2026-09-30",
            "legal_basis": ["İş Sağlığı ve Güvenliği Kanunu md.10"],
            "corrective_action": "Etiketleri güncelle; topraklama ölçümü yap.",
        },
        {
            "id": 2, "no": 2, "category": "Yangın Güvenliği",
            "area": "Yangın Söndürme",
            "question": "Tüp doluluk oranı kontrol ediliyor mu?",
            "responsible": "İşveren Vekili",
            "default_probability": 3, "default_severity": 4,
            "default_risk_score": 12, "default_risk_level": "Dikkate Değer",
            "document_risk_level": "Dikkate Değer",
            "deadline": "2026-10-15",
            "corrective_action": "Aylık doluluk kontrolü planla.",
        },
        {
            "id": 3, "no": 3, "category": "Acil Çıkış",
            "area": "Acil Çıkış & Yönlendirme",
            "question": "Acil çıkış levhaları görünür durumda mı?",
            "responsible": "Bölüm Sorumlusu",
            "default_probability": 1, "default_severity": 1,
            "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
            "document_risk_level": "Kabul Edilebilir",
            "deadline": "2026-12-31",
            "corrective_action": "Yıllık kontrol planı.",
        },
    ]


def _many_questions(n: int = 60) -> List[dict]:
    """Çok sayfalı PDF üretmek için n soruluk seed (repeatRows tetikler)."""
    out: List[dict] = []
    for i in range(1, n + 1):
        out.append({
            "id": i, "no": i,
            "category": f"Kategori {i}",
            "area": f"Alan {i}",
            "question": (
                f"Soru {i}: Bu denetim maddesi için saha gözlemi ve "
                f"tehlike analizi yapıldı mı? Madde {i} gereği tüm "
                f"sorumlular bilgilendirildi mi?"
            ),
            "responsible": f"Sorumlu {i}",
            "default_probability": (i % 5) + 1,
            "default_severity": ((i + 2) % 5) + 1,
            "default_risk_score": ((i % 5) + 1) * (((i + 2) % 5) + 1),
            "default_risk_level": "Kabul Edilemez",
            "document_risk_level": "Kabul Edilemez",
            "deadline": "2026-12-31",
            "corrective_action": f"Madde {i} tedbir metni uygulanmalı.",
        })
    return out


# ---------------------------------------------------------------------------
# S13 — Footer callback
# ---------------------------------------------------------------------------
class TestPDFFooter:
    def test_footer_present_single_page(self):
        """Tek sayfalık PDF'te footer metni görünür (3 bölüm: denetçi, restoran+state, sayfa)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; footer test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
            restaurant="Şişli Çarşı Şubesi",
            denetci="Çağatay Gümüş",
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        # Sol: denetçi
        assert _wrap_tolerant("Denetçi:", text), "Footer sol: 'Denetçi:' eksik"
        assert _wrap_tolerant("Çağatay Gümüş", text), "Footer sol: denetçi adı eksik"
        # Orta: restoran + state (state=FINAL is_completed=True olduğu için)
        assert _wrap_tolerant("Şişli Çarşı Şubesi", text), (
            "Footer orta: restoran adı eksik"
        )
        assert _wrap_tolerant("FINAL", text), "Footer orta: state eksik"
        # Sağ: sayfa
        assert _wrap_tolerant("Sayfa", text), "Footer sağ: 'Sayfa' prefix eksik"

    def test_footer_present_multipage_every_page(self):
        """Multi-page PDF'te footer **her sayfada** görünür (60+ soru)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; multi-page footer test edilemedi")
        resp = _build_pdf(
            answers={str(i): "HAYIR" for i in range(1, 31)},
            questions=_many_questions(60),
            restaurant="Kadıköy Şubesi",
            denetci="Denetçi Bey",
        )
        body = _collect_bytes(resp)
        reader = PyPDF2.PdfReader(io.BytesIO(body))
        n_pages = len(reader.pages)
        assert n_pages >= 2, f"Multi-page bekleniyordu; {n_pages} sayfa bulundu"
        for idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            normalized = re.sub(r"\s+", " ", page_text).strip()
            # Her sayfada 3 footer parçası da var mı?
            assert _wrap_tolerant("Denetçi:", normalized), (
                f"Sayfa {idx}: 'Denetçi:' eksik"
            )
            assert _wrap_tolerant("Sayfa", normalized), (
                f"Sayfa {idx}: 'Sayfa' prefix eksik"
            )
            assert _wrap_tolerant("Kadıköy Şubesi", normalized), (
                f"Sayfa {idx}: restoran adı eksik"
            )
            # Sayfa numarası: 1..n_pages; her sayfada kendi numarası olmalı.
            assert _wrap_tolerant(f"Sayfa {idx}", normalized), (
                f"Sayfa {idx}: kendi sayfa numarası eksik"
            )

    def test_footer_no_electronic_signature_claim(self):
        """Footer'da 'elektronik imza' / 'e-imza' ibaresi YOK (S20:

        ibraz SHA-256 doğrulama, elektronik imza DEĞİL). Bu test S13
        footer'ın 'imza' kelimesini yanlış bağlamda kullanmadığını
        garanti eder.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; footer text test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages).lower()
        # "elektronik imza" yanlış bağlam olur; "e-imza" da.
        assert "elektronik imza" not in text, (
            "Footer 'elektronik imza' içeriyor; SHA-256 doğrulama "
            "elektronik imza DEĞİLDİR (ARRODES.md §8)"
        )
        assert "e-imza" not in text, (
            "Footer 'e-imza' içeriyor; SHA-256 doğrulama e-imza DEĞİLDİR"
        )


# ---------------------------------------------------------------------------
# S13 — İmza Alanları tablosu (4 imza kutusu)
# ---------------------------------------------------------------------------
class TestPDFSignatureBlock:
    def test_signature_section_header_present(self):
        """'İmza Alanları' section başlığı son sayfada var."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; imza section test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        assert _wrap_tolerant("İmza Alanları", text), (
            "İmza Alanları section başlığı eksik"
        )

    def test_signature_box_labels_all_four(self):
        """4 imza kutusu etiketi de PDF'te var: Denetçi, Restoran Müdürü,
        İşveren Vekili, İSG Uzmanı. S20 İbraz ile aynı şema.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; imza etiketleri test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        for label in ("Denetçi", "Restoran Müdürü", "İşveren Vekili", "İSG Uzmanı"):
            assert _wrap_tolerant(label, text), (
                f"İmza kutusu etiketi eksik: '{label}'"
            )

    def test_signature_block_appears_on_last_page(self):
        """İmza tablosu son sayfada olmalı (multi-page PDF'lerde)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; imza location test edilemedi")
        resp = _build_pdf(
            answers={str(i): "HAYIR" for i in range(1, 31)},
            questions=_many_questions(60),
        )
        body = _collect_bytes(resp)
        reader = PyPDF2.PdfReader(io.BytesIO(body))
        n_pages = len(reader.pages)
        assert n_pages >= 2, "Multi-page PDF bekleniyor"
        # Son sayfada 4 imza kutusu var, ilk sayfada YOK.
        try:
            first_text = reader.pages[0].extract_text() or ""
        except Exception:
            first_text = ""
        first_norm = re.sub(r"\s+", " ", first_text).strip()
        try:
            last_text = reader.pages[-1].extract_text() or ""
        except Exception:
            last_text = ""
        last_norm = re.sub(r"\s+", " ", last_text).strip()
        # Son sayfada 4 etiket de var.
        for label in ("Denetçi", "Restoran Müdürü", "İşveren Vekili", "İSG Uzmanı"):
            assert _wrap_tolerant(label, last_norm), (
                f"Son sayfada '{label}' eksik"
            )
        # İlk sayfada "İmza Alanları" başlığı OLMAMALI (son flowable).
        # Ancak "Denetçi" kelimesi metadata tablosunda ve 11-kolon
        # tablosunda da geçebilir; "İmza Alanları" başlığı ise
        # section başlığı olarak yalnızca son sayfada var.
        assert not _wrap_tolerant("İmza Alanları", first_norm), (
            "İmza Alanları başlığı ilk sayfada görünüyor; son flowable olmalı"
        )

    def test_signature_block_landscape_a4_dimensions(self):
        """İmza tablosu landscape A4 içinde 4 × 44 mm = 176 mm sütun

        genişliğinde olmalı. Bu test dolaylıdır: PDF'in landscape
        olduğunu zaten test_pdf_export_design doğrular; burada
        imza tablosunun **render edilebildiğini** (exception'sız
        üretildiğini) garanti ederiz.
        """
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
        )
        # Response StreamingResponse; bytes toplanabilmeli (exception
        # yoksa render başarılı).
        body = _collect_bytes(resp)
        assert body[:5] == b"%PDF-", "PDF magic yok; render başarısız"
        assert len(body) > 5000, "PDF çok küçük; imza tablosu render edilmemiş olabilir"


# ---------------------------------------------------------------------------
# Server.py regression — export_pdf build hattı değişmedi
# ---------------------------------------------------------------------------
class TestExportPdfRegression:
    def test_export_pdf_mime_unchanged(self):
        """Footer + imza eklenmesi MIME type'ı bozmamalı."""
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
        )
        assert resp.media_type == "application/pdf"
        cd = resp.headers["content-disposition"]
        assert cd.startswith("attachment; ")
        assert 'filename="' in cd
        assert "filename*=UTF-8''" in cd

    def test_callback_name_unique(self):
        """S13 callback adı export_ibraz'dan ayrı olmalı (collision YOK).

        ``server._draw_export_pdf_footer`` mevcut; export_ibraz'ın
        kendi iç callback'i ``_on_page``'dir ve farklı scope'ta.

        Server modülünde ``_on_page`` module-level olarak TANIMLI
        OLMAMALI. ``export_ibraz`` içindeki ``_on_page`` local closure
        scope'undadır; module'e sızarsa yanlışlıkla iki export'un
        callback'i aynı isimle çakışır.
        """
        assert hasattr(server, "export_pdf"), "export_pdf export kaldırıldı!"
        assert not hasattr(server, "_on_page"), (
            "server._on_page module-level sızıntı; export_ibraz callback'i "
            "local scope'ta kalmalı."
        )
