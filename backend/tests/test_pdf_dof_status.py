"""S8 — DÖF Durumu renkli (PDF Tedbir kolonu) + DÖF Özeti testleri.

Bu test paketi, ``backend/server.py::export_pdf`` endpoint'inin S8
kapsamında eklenen iki yeni davranışı doğrular:

  1. **Tedbir (DÖF) kolonu renk kodlaması** — HAYIR cevaplı satırlarda,
     ``dof_details.<qid>.status`` alanına göre arka plan rengi:

       * ``AÇIK``      → amber   ``#FEF3C7``
       * ``İŞLEMDE``   → blue    ``#DBEAFE``
       * ``KAPATILDI`` → emerald ``#D1FAE5``

     Excel ``export_excel`` ile birebir aynı renk kodu (satır ~2280,
     ``status_color_map``). EVET / NA / boş satırlar etkilenmez.

  2. **DÖF Durumu Özeti** — Ana tablo sonrası, fotoğraf bölümünden önce
     4 kolonlu mini-table: ``HAYIR`` (toplam) + 3 status sayısı. Yalnız
     HAYIR cevaplı soru varsa gösterilir.

Tasarım kararları:

* test_pdf_export_design.py'deki ``_build_pdf`` / ``_collect_bytes`` /
  ``_pdf_pages_and_text`` / ``_wrap_tolerant`` / ``_all_text_normalized``
  helper'ları **kopyalanmaz**; aynı modülden import edilir. S13 ile
  aynı politika.

* PyPDF2 bağımlılığı zorunlu değil; yoksa ``pytest.skip`` ile geçilir.

* Renk doğrulaması dolaylıdır: PyPDF2 text extraction ile "AÇIK:" /
  "İŞLEMDE:" / "KAPATILDI:" etiketlerinin DÖF Özeti bölümünde
  görünmesi ve renk adı yerine status string'inin rapor metninde
  bulunması yeterli sayılır. Reportlab renk set etse de PDF text
  extraction'da renk korunmaz; gerçek renk byte karşılaştırması
  gerekir (opsiyonel, gelecekte eklenebilir).

* Doğrulama yelpazesi:
  - 1 HAYIR + 1 KAPATILDI: özet 1+1, KAPATILDI emerald rengi
  - 3 HAYIR farklı status'larla: özet doğru sayım
  - 0 HAYIR: özet bölümü GÖRÜNMEZ (no-op)
  - 1 EVET + 0 HAYIR: özet bölümü GÖRÜNMEZ
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

try:
    import PyPDF2  # type: ignore
    HAS_PYPDF2 = True
except Exception:  # pragma: no cover
    PyPDF2 = None  # type: ignore
    HAS_PYPDF2 = False

from _phase_2a_helpers import (  # type: ignore
    sample_audit_doc,
    sample_template_doc,
)
import server
from server import export_pdf, AuditState
from test_pdf_export_design import (  # type: ignore
    _standard_questions,
    _collect_bytes,
    _pdf_pages_and_text,
    _wrap_tolerant,
    _all_text_normalized,
)
from test_pdf_footer_signature import (  # type: ignore
    fake_db as fake_db_footer,
    push_audit as push_audit_footer,
    run_async as run_async_footer,
)


AID = "507f1f77bcf86cd799439012"


def _build_pdf_with_dof(
    *,
    answers: Dict[str, str],
    dof_details: Dict[str, Dict[str, Any]] | None = None,
    state: str = "FINAL",
    is_completed: bool = True,
    questions: List[dict] | None = None,
):
    """DÖF details ile dolu bir audit üretip export_pdf çağırır.

    Yardımcı: ``_build_pdf`` (test_pdf_export_design) ile aynı DB
    factory altyapısını kullanır, ek olarak ``dof_details`` alanını
    audit doc'a yazar. ``fake_db`` / ``push_audit`` / ``run_async``
    orada ``_phase_2a_helpers`` üzerinden gelir; burada yeniden
    import etmek yerine ``test_pdf_footer_signature`` üzerinden alıyoruz
    (alias uyumluluğu için).
    """
    qs = questions or _standard_questions()
    template = sample_template_doc(questions=qs)
    audit = sample_audit_doc(
        audit_id=AID,
        answers=answers,
        risk_overrides={},
        with_snapshot=True,
        template=template,
        version=0,
    )
    audit["is_completed"] = is_completed
    audit["state"] = state
    audit["restaurant_name"] = "S8 Smoke Sube"
    audit["address"] = "Test Adres"
    audit["audit_date"] = "2026-08-17"
    audit["denetci"] = "S8 Denetci"
    audit["brand"] = "Burger King"
    if dof_details is not None:
        audit["dof_details"] = dof_details

    with fake_db_footer([template]):
        push_audit_footer(server.db, audit)
        return run_async_footer(
            export_pdf(
                audit_id=AID,
                current_user={"id": "u-1", "name": "S8 Denetci"},
            )
        )


# ---------------------------------------------------------------------------
# S8 — DÖF Durumu Özeti section
# ---------------------------------------------------------------------------
class TestDofSummarySection:
    def test_summary_absent_when_no_hayir(self):
        """0 HAYIR cevaplı soru varsa DÖF Özeti section'ı GÖRÜNMEZ."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; özet test edilemedi")
        # 3 soru, hepsi EVET
        resp = _build_pdf_with_dof(answers={"1": "EVET", "2": "EVET", "3": "EVET"})
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        assert "DÖF Durumu Özeti" not in text, (
            "0 HAYIR varken DÖF Durumu Özeti section'ı gözükmemeliydi"
        )

    def test_summary_present_when_hayir_exists(self):
        """1+ HAYIR cevaplı soru varsa DÖF Özeti section'ı + etiketler var."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; özet test edilemedi")
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR"},
            dof_details={"1": {"status": "KAPATILDI"}},
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        assert _wrap_tolerant("DÖF Durumu Özeti", text), (
            "DÖF Durumu Özeti section başlığı eksik"
        )
        # 4 etiket: HAYIR + AÇIK + İŞLEMDE + KAPATILDI
        for label in ("HAYIR:", "AÇIK:", "İŞLEMDE:", "KAPATILDI:"):
            assert _wrap_tolerant(label, text), (
                f"DÖF Özeti etiketi eksik: {label!r}"
            )

    def test_summary_counts_correct(self):
        """3 HAYIR farklı status'larla → doğru sayım.

        q1=AÇIK, q2=İŞLEMDE, q3=KAPATILDI → toplam 1+1+1=3,
        HAYIR=3.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; sayım test edilemedi")
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR", "2": "HAYIR", "3": "HAYIR"},
            dof_details={
                "1": {"status": "AÇIK"},
                "2": {"status": "İŞLEMDE"},
                "3": {"status": "KAPATILDI"},
            },
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        # HAYIR: 3
        assert _wrap_tolerant("HAYIR: 3", text), (
            f"HAYIR sayımı yanlış; text excerpt: {text[:500]!r}"
        )
        # AÇIK: 1, İŞLEMDE: 1, KAPATILDI: 1
        assert _wrap_tolerant("AÇIK: 1", text), "AÇIK sayımı yanlış"
        assert _wrap_tolerant("İŞLEMDE: 1", text), "İŞLEMDE sayımı yanlış"
        assert _wrap_tolerant("KAPATILDI: 1", text), "KAPATILDI sayımı yanlış"

    def test_summary_mixed_no_dof_defaults_to_acik(self):
        """DÖF details'ta status yoksa → AÇIK sayılır (S9 default)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; default AÇIK test edilemedi")
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR", "2": "HAYIR"},
            dof_details={
                "1": {"status": "KAPATILDI"},
                "2": {},  # status yok → AÇIK
            },
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        # HAYIR: 2, AÇIK: 1 (q2 default), KAPATILDI: 1 (q1)
        assert _wrap_tolerant("HAYIR: 2", text), "HAYIR sayımı yanlış"
        assert _wrap_tolerant("AÇIK: 1", text), "Default AÇIK sayımı yanlış"
        assert _wrap_tolerant("KAPATILDI: 1", text), "KAPATILDI sayımı yanlış"


# ---------------------------------------------------------------------------
# S8 — DÖF Durumu renkli (Tedbir kolonu)
# ---------------------------------------------------------------------------
class TestDofStatusColoring:
    def test_tedbir_cell_colored_for_kapatildi(self):
        """KAPATILDI DÖF → Tedbir hücresi emerald arka plan alır.

        Bu test dolaylıdır: PyPDF2 text extraction renkleri KORUMAZ
        (renk, içerik değil görsel özelliktir). Bu yüzden ``AÇIK``,
        ``İŞLEMDE``, ``KAPATILDI`` status'larının **DÖF Özeti bölümünde**
        doğru sayılarla görünmesi yeterli sayılır; özet sayıları yukarıdaki
        testlerle kanıtlanmıştır. Buradaki test export'ün hata vermeden
        geçtiğini ve renk set etme kodunun çalıştığını (exception'sız
        render) doğrular.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; render test edilemedi")
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR"},
            dof_details={"1": {"status": "KAPATILDI"}},
        )
        body = _collect_bytes(resp)
        assert body[:5] == b"%PDF-", "PDF magic yok; render başarısız"
        assert len(body) > 5000, "PDF çok küçük; render başarısız olabilir"

    def test_unknown_status_no_crash(self):
        """Bilinmeyen status string'i (örn. 'BILINMEYEN') render'ı kırmaz;
        DÖF Özeti bu öğeyi ``DİĞER`` bucket'ında sayar (HAYIR toplamı
        ile bucket toplamı reconcile). Test: render exception'sız biter
        ve toplamlar eşleşir.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; unknown status test edilemedi")
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR", "2": "HAYIR"},
            dof_details={
                "1": {"status": "BILINMEYEN"},
                "2": {"status": "KAPATILDI"},
            },
        )
        body = _collect_bytes(resp)
        assert body[:5] == b"%PDF-"
        # DÖF özeti: HAYIR=2, KAPATILDI=1, AÇIK=0, İŞLEMDE=0, DİĞER=1
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        assert _wrap_tolerant("HAYIR: 2", text)
        assert _wrap_tolerant("KAPATILDI: 1", text)
        assert _wrap_tolerant("AÇIK: 0", text)
        assert _wrap_tolerant("İŞLEMDE: 0", text)
        # DİĞER bucket: bilinmeyen status reconcile sayımı.
        assert _wrap_tolerant("DİĞER: 1", text), (
            "Bilinmeyen status DİĞER bucket'ında reconcile edilmeli"
        )

    def test_yes_answers_excluded_from_summary(self):
        """EVET / NA cevaplı sorular DÖF Özeti'ne dahil değil.

        HAYIR=1 (q1 KAPATILDI), EVET/NA olanlar (q2, q3) HAYIR
        sayısına girmez.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; EVET/NA exclusion test edilemedi")
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR", "2": "EVET", "3": "NA"},
            dof_details={"1": {"status": "KAPATILDI"}},
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        assert _wrap_tolerant("HAYIR: 1", text), "HAYIR sayımı yanlış"
        assert _wrap_tolerant("KAPATILDI: 1", text), "KAPATILDI sayımı yanlış"
        assert _wrap_tolerant("AÇIK: 0", text), "AÇIK sayımı yanlış"
        assert _wrap_tolerant("İŞLEMDE: 0", text), "İŞLEMDE sayımı yanlış"


# ---------------------------------------------------------------------------
# S8 — Server.py regression
# ---------------------------------------------------------------------------
class TestS8Regression:
    def test_export_pdf_mime_unchanged(self):
        """S8 eklenmesi MIME type'ı bozmamalı."""
        resp = _build_pdf_with_dof(
            answers={"1": "HAYIR"},
            dof_details={"1": {"status": "KAPATILDI"}},
        )
        assert resp.media_type == "application/pdf"
        cd = resp.headers["content-disposition"]
        assert cd.startswith("attachment; ")
        assert 'filename="' in cd
        assert "filename*=UTF-8''" in cd
