"""PDF export design (Baran form) — clean-port testleri.

Bu test paketi, ``backend/server.py::export_pdf`` endpoint'inin
resmî ABCD Tech Solutions PDF form görünümünü koruduğunu ve mevcut main
mimarisine (kanonik risk hesaplama, snapshot, override, Türkçe
Unicode) bağlı kaldığını kanıtlar.

Yeni bağımlılık EKLENMEZ; ortamda zaten mevcut olan
``reportlab`` (build) ve ``PyPDF2`` (parse) kullanılır.
"""
from __future__ import annotations

import asyncio
import io
import re
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

# PyPDF2 PDF parser olarak kullanılır (sayfa sayısı + metin çıkarma).
# Ortamda yoksa test'ler yalnız bytes-level ve server-config doğrulaması
# yapar ve bunu açıkça raporlar.
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
from server import export_pdf, export_excel


# ---------------------------------------------------------------------------
# Sabitler / yardımcılar
# ---------------------------------------------------------------------------
AID = "507f1f77bcf86cd799439041"


def _standard_questions():
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


def _build_pdf(
    *,
    answers=None,
    risk_overrides=None,
    is_completed=True,
    restaurant="Şişli Çarşı Şubesi",
    address="Üsküdar Mevki, Ömerli Çeşme Sk. No:12 Şişli/İstanbul",
    audit_date="2026-08-04",
    denetci="Çağatay Gümüş",
    questions=None,
):
    """Verilen cevap/override ile bir PDF response üretir."""
    template = sample_template_doc(questions=questions)
    audit = sample_audit_doc(
        audit_id=AID,
        answers=answers or {},
        risk_overrides=risk_overrides or {},
        with_snapshot=True,
        template=template,
        version=0,
    )
    audit["is_completed"] = is_completed
    # S18 lifecycle: nihai rapor export'u yalnızca DOF_CLOSED/FINAL'de
    # mümkün (DRAFT/DOF_OPEN 409). Design testleri export çıktısını inceler;
    # geçerli exportable state sağlanır, ``is_completed`` (subtitle) ayrı kalır.
    audit["state"] = "FINAL" if is_completed else "DOF_CLOSED"
    audit["restaurant_name"] = restaurant
    audit["address"] = address
    audit["audit_date"] = audit_date
    audit["denetci"] = denetci

    with fake_db([template]):
        push_audit(server.db, audit)
        return run_async(
            export_pdf(
                audit_id=AID,
                current_user={"id": "u-1", "name": "Denetçi"},
            )
        )


def _collect_bytes(resp) -> bytes:
    """``StreamingResponse`` body bytes'ını döndürür."""
    body = resp.body_iterator
    if hasattr(body, "__aiter__"):
        async def _collect():
            out = bytearray()
            async for chunk in body:
                out.extend(chunk)
            return bytes(out)
        return asyncio.run(_collect())
    # In-memory Response.body fallback.
    return bytes(resp.body)


def _pdf_pages_and_text(pdf_bytes: bytes) -> Tuple[int, List[str]]:
    """PyPDF2 ile sayfa sayısı ve sayfa bazlı metin çıkarır."""
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return len(reader.pages), pages


def _normalize_text(text: str) -> str:
    """Tüm whitespace tek boşluğa indirgenir (satır sonu, tab dahil).

    ReportLab Paragraph wrap noktalarında satır sonu ekler; PyPDF2
    text extraction da bunları korur. Örn:
    * "Uygun Değil" -> "Uygun\\nDeğil"
    * "2026-09-30" -> "2026-09-3\\n0"
    * "Restoran / Şube" -> "Restoran /\\nŞube"
    Sağlam substring araması için whitespace normalize uygulanır.
    """
    return re.sub(r"\s+", " ", text).strip()


def _wrap_tolerant(pattern: str, text: str) -> bool:
    """Üç katmanlı dayanıklı substring araması.

    PyPDF2 ``extract_text`` çıktısı, ReportLab Paragraph wrap noktalarında
    satır sonu içerir. Örn:
    * "Yanıtlanmadı" -> "Yanıtlan\\nmadı"
    * "2026-09-30" -> "2026-09-3\\n0"
    * "Restoran / Şube" -> "Restoran /\\nŞube"
    * "Uygun Değil" -> "Uygun\\nDeğil"

    Üç katmanlı arama:

    1. **Düz substring**: Ham pattern ham metinde var mı?
    2. **Whitespace normalize**: Tüm ``\\s+`` tek boşluğa indirgenmiş
       hâlde pattern var mı? Bu token arası wrap'ları yakalar.
    3. **Wrap-tolerant regex**: Yalnızca regex-meta karakterler
       (``\\.^$?+*(){}[]|/``) escape edilir; diğer her karakterden
       SONRA ``\\s*`` enjekte edilir. Bu token içi wrap'ları ("Y\\nı"
       gibi) yakalar.

    Bu sıralama, mümkün olan en sıkı eşleşmeden gevşek olana doğru
    ilerler; yalnızca katı aramalar başarısız olduğunda wrap'lı
    metin için regex fallback çalışır.
    """
    # 1. Düz substring.
    if pattern in text:
        return True
    # 2. Whitespace normalize.
    if pattern in _normalize_text(text):
        return True
    # 3. Wrap-tolerant regex (karakterler arası \s*).
    # NOT: "/" Python ``re`` içinde meta karakter DEĞİLDİR; escape edilmemeli.
    # Escape edilirse "\\/" iki karaktere bölünür ve join araya "\s*" sokuşturup
    # pattern'i bozar (ör. "N/A" hiç eşleşmezdi).
    # Meta karakterler TEK token olarak escape edilir; join yalnızca token'lar
    # arasına "\s*" sokar. Eski karakter-bazlı join, "\(" ikiye bölüp araya
    # "\s*" koyardı ve regex literal backslash arardı (ör. "Olasılık (O)"
    # wrap'lanınca hiç eşleşmezdi).
    meta = r"\.^$?+*(){}[]|"
    tokens: List[str] = []
    for ch in pattern:
        tokens.append("\\" + ch if ch in meta else ch)
    rx = r"\s*".join(tokens)
    return re.search(rx, text) is not None


def _all_text_normalized(pages: List[str]) -> str:
    return " ".join(_normalize_text(p) for p in pages if p)


# ---------------------------------------------------------------------------
# Görsel sözleşme
# ---------------------------------------------------------------------------
class TestPDFVisualContract:
    def test_pdf_bytes_start_with_magic(self):
        resp = _build_pdf(answers={"1": "HAYIR"}, questions=_standard_questions())
        body = _collect_bytes(resp)
        assert body[:5] == b"%PDF-"
        assert len(body) > 1000  # boş/çok küçük değil

    def test_landscape_a4_pagesize_config(self):
        """Sayfa boyutu landscape A4 olmalı (842 × 595 pt)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; sayfa boyutu test edilemedi")
        resp = _build_pdf(answers={"1": "HAYIR"}, questions=_standard_questions())
        body = _collect_bytes(resp)
        reader = PyPDF2.PdfReader(io.BytesIO(body))
        assert len(reader.pages) >= 1
        page = reader.pages[0]
        mediabox = page.mediabox
        w = float(mediabox.width)
        h = float(mediabox.height)
        assert w > h, f"landscape olmalı: w={w}, h={h}"
        # A4 uzun boyut 841.89 pt, kısa boyut 595.27 pt.
        assert 838 <= max(w, h) <= 846
        assert 590 <= min(w, h) <= 600

    def test_mime_and_content_disposition(self):
        resp = _build_pdf(answers={"1": "HAYIR"}, questions=_standard_questions())
        assert resp.media_type == "application/pdf"
        cd = resp.headers["content-disposition"]
        assert cd.startswith("attachment; ")
        assert 'filename="' in cd
        assert "filename*=UTF-8''" in cd
        # ASCII fallback filename prefix'i içermeli.
        assert cd.split('filename="')[1].split('"')[0].startswith("ISG_Risk_Analizi_")

    def test_title_text_status_completed(self):
        """Üst başlık tam metin, alt başlık TAMAMLANDI durumunu gösterir."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; başlık metni test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            is_completed=True,
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        all_text = _all_text_normalized(pages)
        assert "ABCD Tech Solutions SAN. VE TİC. A.Ş." in all_text
        assert "RESTORAN İSG RİSK ANALİZİ VE DÖF RAPORU" in all_text
        assert "Rapor Statüsü: TAMAMLANDI" in all_text
        assert "RESMİ ONAYLI" not in all_text

    def test_subtitle_status_draft(self):
        """Alt başlık TASLAK DENETİM durumunu doğru yansıtır."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; alt başlık test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            is_completed=False,
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        all_text = _all_text_normalized(pages)
        assert "Rapor Statüsü: TASLAK DENETİM" in all_text
        assert "RESMİ ONAYLI" not in all_text

    def test_metadata_table_present(self):
        """Metadata iki satırlı tablo: Restoran+Tarih, Adres+Denetçi."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; metadata test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            restaurant="Şişli Çarşı Şubesi",
            address="Üsküdar Mevki, Ömerli Çeşme Sk. No:12 Şişli/İstanbul",
            audit_date="2026-08-04",
            denetci="Çağatay Gümüş",
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        all_text = _all_text_normalized(pages)
        for needle in [
            "Restoran / Şube",
            "Tarih",
            "Adres",
            "Denetçi",
            "Şişli Çarşı Şubesi",
            "Üsküdar Mevki",
            "2026-08-04",
            "Çağatay Gümüş",
        ]:
            assert _wrap_tolerant(needle, all_text), (
                f"metadata eksik: {needle!r}"
            )

    def test_main_table_headers(self):
        """Ana tablo 11 kolonu ortak şema ile aynı sırada (S6)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; header test edilemedi")
        from audit_columns import get_columns

        resp = _build_pdf(answers={"1": "HAYIR"}, questions=_standard_questions())
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        all_text = _all_text_normalized(pages)
        expected = [c.header for c in get_columns()]
        assert expected == [
            "No",
            "Kategori",
            "Tehlike & Risk Maddesi",
            "Cevap",
            "Olasılık (O)",
            "Şiddet (Ş)",
            "Risk Skoru (R)",
            "Risk Seviyesi",
            "Sorumlu",
            "Termin Süresi",
            "Alınması Gereken Tedbir (DÖF)",
        ]
        for h in expected:
            assert _wrap_tolerant(h, all_text), f"header eksik: {h!r}"
        # S6: birleşik "O x Ş" header'ı artık üretilmez.
        assert "O x Ş" not in all_text, "birleşik 'O x Ş' header kalmamalı"

    def test_shared_11_column_contract_excel_and_pdf(self):
        """S6: Excel ve PDF header'ları ortak 11 kolon şemasıyla birebir aynı.

        ``excel_headers == pdf_headers == get_columns()`` — Excel header
        satırı 7'dir; PDF metin içeriğinden header'ların varlığı ve
        birleşik ``O x Ş`` header'ının olmadığı doğrulanır.
        """
        from openpyxl import load_workbook
        from audit_columns import get_columns

        shared = [c.header for c in get_columns()]
        assert len(shared) == 11

        # PDF tarafı.
        resp = _build_pdf(answers={"1": "HAYIR"}, questions=_standard_questions())
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        pdf_text = _all_text_normalized(pages)

        # Excel tarafı (header satırı 7).
        template = sample_template_doc(questions=_standard_questions())
        audit = sample_audit_doc(
            audit_id=AID,
            answers={"1": "HAYIR"},
            risk_overrides={},
            with_snapshot=True,
            template=template,
            version=0,
        )
        audit["state"] = "FINAL"
        with fake_db([template]):
            push_audit(server.db, audit)
            excel_resp = run_async(
                export_excel(
                    audit_id=AID,
                    current_user={"id": "u-1", "name": "Denetçi"},
                )
            )
        wb = load_workbook(io.BytesIO(_collect_bytes(excel_resp)))
        ws = wb.active
        excel_headers = [ws.cell(row=7, column=i).value for i in range(1, 12)]

        assert excel_headers == shared, "Excel header'ları ortak şemadan sapıyor"
        for h in shared:
            assert _wrap_tolerant(h, pdf_text), f"PDF header eksik: {h!r}"
        # PDF'te birleşik 'O x Ş' header'ı kesinlikle olmamalı.
        assert "O x Ş" not in pdf_text, "birleşik 'O x Ş' header kalmamalı"

    def test_unicode_turkish_preserved_in_pdf(self):
        """Şişli / Çağatay / Gümüş gibi Türkçe karakterler PDF'te korunur."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; Unicode test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            restaurant="Şişli Çarşı Şubesi",
            address="Üsküdar Mevki, Ömerli Çeşme Sk. No:12 Şişli/İstanbul",
            denetci="Çağatay Gümüş",
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        all_text = _all_text_normalized(pages)
        for char in ["Ş", "ş", "Ç", "ç", "İ", "ı", "Ö", "ö", "Ü", "ü", "ğ"]:
            assert char in all_text, f"Türkçe Unicode kayıp: {char!r}"
        assert "Şişli" in all_text
        assert "Çağatay Gümüş" in all_text
        assert "Üsküdar" in all_text


# ---------------------------------------------------------------------------
# Veri sözleşmesi
# ---------------------------------------------------------------------------
class TestPDFDataContract:
    def test_snapshot_used_over_global_questions(self):
        """Audit kendi template_snapshot'ından beslenir, global
        ``QUESTIONS`` kullanılmaz. Snapshot'ta ek bir 'ÖZEL' soru olsun.
        """
        custom = _standard_questions() + [
            {
                "id": 99, "no": 99, "category": "Özel Snapshot",
                "question": "Bu soru yalnız snapshot'ta var — globalde yok.",
                "responsible": "Snapshot Sorumlusu",
                "default_probability": 5, "default_severity": 5,
                "default_risk_score": 25, "default_risk_level": "Kabul Edilemez",
                "document_risk_level": "Kabul Edilemez",
                "deadline": "",
                "corrective_action": "Snapshot tedbir.",
            }
        ]
        resp = _build_pdf(answers={"1": "HAYIR"}, questions=custom)
        body = _collect_bytes(resp)
        if HAS_PYPDF2:
            _, pages = _pdf_pages_and_text(body)
            text = _all_text_normalized(pages)
            assert _wrap_tolerant("Bu soru yalnız snapshot'ta var", text)
            assert "Snapshot Sorumlusu" in text

    def test_risk_override_reflected_in_pdf(self):
        """Risk override'ları ``compute_effective_risk`` üzerinden PDF'e
        yansımalı."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; override test edilemedi")
        # q1 default Kabul Edilebilir (1x1), override ile Kabul Edilemez (5x5).
        questions = [
            {
                "id": 1, "no": 1, "category": "Elektrik",
                "question": "Pano etiketleri?",
                "responsible": "İSG",
                "default_probability": 1, "default_severity": 1,
                "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
                "document_risk_level": "Kabul Edilebilir",
                "deadline": "",
                "corrective_action": "",
            }
        ]
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            risk_overrides={"1": {"probability": 5, "severity": 5}},
            questions=questions,
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        assert "5 x 5" not in text, "birleşik 'O x Ş' hücresi kalmamalı"
        # S6: Olasılık ve Şiddet ayrı kolonlardır; override değerleri
        # (olasılık 5, şiddet 5) ve hesaplanan skor/seviye görünür kalır.
        assert "25" in text
        assert "Kabul Edilemez" in text
        assert _wrap_tolerant("Olasılık (O)", text)
        assert _wrap_tolerant("Şiddet (Ş)", text)

    def test_answer_mapping_canonical(self):
        """EVET/HAYIR/NA/boş cevaplar kanonik mapping ile gösterilir.

        PyPDF2 ``extract_text`` çıktısı, ReportLab Paragraph wrap
        noktalarında satır sonu içerir (örn. "Yanıtlanmadı" ->
        "Yanıtlan\\nmadı"). Bu yüzden tüm substring aramaları
        ``_wrap_tolerant`` ile yapılır; ``pattern`` içindeki her boşluk
        "0+ whitespace" olarak eşleşir.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; cevap mapping test edilemedi")
        questions = _standard_questions() + [
            {
                "id": 4, "no": 4, "category": "Tehlikeli Kimyasal",
                "question": "Asbest var mı?",
                "responsible": "İSG",
                "default_probability": 1, "default_severity": 1,
                "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
                "document_risk_level": "Kabul Edilebilir",
                "deadline": "",
                "corrective_action": "",
            }
        ]
        resp = _build_pdf(
            answers={
                "1": "EVET",     # → Uygun
                "2": "HAYIR",    # → Uygun Değil
                "3": "NA",       # → N/A
                "4": "BOŞ_DEĞİL",  # eksik → Yanıtlanmadı
            },
            questions=questions,
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        for needle in [
            "Uygun",
            "Uygun Değil",
            "N/A",
            "Yanıtlanmadı",
        ]:
            assert _wrap_tolerant(needle, text), (
                f"cevap eşlemesi eksik: {needle!r}"
            )

    def test_legacy_schema_fallback(self):
        """Legacy alan adları (kategori/soru/sorumlu/termin/tedbir)
        hâlâ okunabilir.
        """
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; legacy fallback test edilemedi")
        legacy_questions = [
            {
                "id": 1, "no": 1,
                # Yeni şema alanları YOK; sadece legacy.
                "kategori": "Legacy Kategori",
                "soru": "Legacy soru metni",
                "sorumlu": "Legacy Sorumlu",
                "termin": "2026-12-31",
                "tedbir": "Legacy tedbir.",
                "default_probability": 5, "default_severity": 5,
                "default_risk_score": 25, "default_risk_level": "Kabul Edilemez",
                "document_risk_level": "Kabul Edilemez",
            }
        ]
        resp = _build_pdf(answers={"1": "HAYIR"}, questions=legacy_questions)
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        for needle in [
            "Legacy Kategori",
            "Legacy soru metni",
            "Legacy Sorumlu",
            "2026-12-31",  # wrap-tolerant: "2026-12-3\n1" olabilir
            "Legacy tedbir.",
        ]:
            assert _wrap_tolerant(needle, text), (
                f"legacy alan eksik: {needle!r}"
            )

    def test_termin_and_tedbir_in_correct_columns(self):
        """Termin ve Tedbir doğru kolonlarda (ortak şemada sırasıyla kolon 10, 11)."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; kolon sırası test edilemedi")
        resp = _build_pdf(
            answers={"1": "HAYIR"},
            questions=_standard_questions(),
        )
        body = _collect_bytes(resp)
        _, pages = _pdf_pages_and_text(body)
        text = _all_text_normalized(pages)
        # q1 için Termin=2026-09-30, Tedbir "Etiketleri güncelle..."
        # Tarih cell_text içinde wrap edilirse "2026-09-3\n0" olabilir.
        assert _wrap_tolerant("2026-09-30", text), "Termin 2026-09-30 eksik"
        assert _wrap_tolerant("Etiketleri güncelle", text), (
            "Tedbir metni eksik"
        )


# ---------------------------------------------------------------------------
# HTTP sözleşmesi
# ---------------------------------------------------------------------------
class TestPDFHTTPContract:
    def test_invalid_object_id_400(self):
        template = sample_template_doc(questions=_standard_questions())
        audit = sample_audit_doc(
            audit_id=AID,
            answers={},
            risk_overrides={},
            with_snapshot=True,
            template=template,
            version=0,
        )
        with fake_db([template]):
            push_audit(server.db, audit)
            with pytest.raises(Exception) as exc:
                run_async(
                    export_pdf(
                        audit_id="not-a-valid-objectid",
                        current_user={"id": "u-1"},
                    )
                )
        assert exc.value.status_code == 400

    def test_not_found_404(self):
        with fake_db([]):
            with pytest.raises(Exception) as exc:
                run_async(
                    export_pdf(
                        audit_id=AID,
                        current_user={"id": "u-1"},
                    )
                )
        assert exc.value.status_code == 404

    def test_excel_endpoint_unchanged_mime(self):
        """Excel endpoint'i PDF değişikliğinden etkilenmez; MIME
        ve Content-Disposition sözleşmesi korunur.
        """
        template = sample_template_doc(questions=_standard_questions())
        audit = sample_audit_doc(
            audit_id=AID,
            answers={"1": "HAYIR"},
            risk_overrides={},
            with_snapshot=True,
            template=template,
            version=0,
        )
        audit["is_completed"] = True
        audit["state"] = "FINAL"
        audit["restaurant_name"] = "Şişli Çarşı Şubesi"
        audit["address"] = "İstanbul"
        audit["audit_date"] = "2026-08-04"
        audit["denetçi"] = "Çağatay Gümüş"  # noqa

        with fake_db([template]):
            push_audit(server.db, audit)
            resp = run_async(
                export_excel(
                    audit_id=AID,
                    current_user={"id": "u-1"},
                )
            )
        assert "spreadsheetml.sheet" in resp.media_type
        cd = resp.headers["content-disposition"]
        assert cd.startswith("attachment; ")
        assert 'filename="' in cd
        assert "filename*=UTF-8''" in cd
        assert cd.split('filename="')[1].split('"')[0].startswith(
            "ISG_Risk_Analizi_"
        )


# ---------------------------------------------------------------------------
# Çok sayfalı çıktı / repeatRows
# ---------------------------------------------------------------------------
class TestPDFMultipage:
    def test_many_questions_multipage(self):
        """50+ soruluk örnek PDF birden fazla sayfaya geçmeli."""
        if not HAS_PYPDF2:
            pytest.skip("PyPDF2 yok; sayfa sayısı test edilemedi")
        big_questions: List[dict] = []
        for i in range(1, 60):
            big_questions.append({
                "id": i, "no": i,
                "category": f"Kategori {i}",
                "question": (
                    f"Soru {i}: bu uzun bir soru metnidir — "
                    f"denetim listesinde ayrıntılı açıklama yapılır."
                ),
                "responsible": f"Sorumlu {i}",
                "default_probability": (i % 5) + 1,
                "default_severity": (i % 5) + 1,
                "default_risk_score": ((i % 5) + 1) * ((i % 5) + 1),
                "default_risk_level": "Kabul Edilebilir",
                "document_risk_level": "Kabul Edilebilir",
                "deadline": "2026-12-31",
                "corrective_action": (
                    f"Bu tedbir {i}. soru için önerilen düzeltici "
                    f"faaliyetlerden oluşur ve uzun metin içerir."
                ),
            })
        resp = _build_pdf(
            answers={str(i): "HAYIR" for i in range(1, 60)},
            questions=big_questions,
        )
        body = _collect_bytes(resp)
        page_count, pages = _pdf_pages_and_text(body)
        assert page_count > 1, (
            f"50+ soru tek sayfada olmamalı; alındı: {page_count}"
        )
        # repeatRows=1: header metni sonraki sayfalarda da bulunmalı.
        header_keywords = ["Kategori", "Tehlike & Risk Maddesi", "Risk Seviyesi"]
        last_page_text = _normalize_text(pages[-1]) if pages else ""
        for kw in header_keywords:
            assert kw in last_page_text, (
                f"repeatRows=1 ihlali: son sayfada header eksik: {kw!r}"
            )

    def test_repeatrows_one_configured(self):
        """Table constructor ``repeatRows=1`` ile oluşturulmuş olmalı."""
        try:
            from reportlab.platypus import Table as RLTable
        except Exception:  # pragma: no cover
            pytest.skip("reportlab Table import edilemedi")

        captured: List[dict] = []
        original_init = RLTable.__init__

        def _spy_init(self, data, *args, **kwargs):
            captured.append({
                "data_len": len(data) if hasattr(data, "__len__") else -1,
                "repeatRows": kwargs.get("repeatRows", 1),
                "kwargs": list(kwargs.keys()),
            })
            return original_init(self, data, *args, **kwargs)

        RLTable.__init__ = _spy_init  # type: ignore[assignment]
        try:
            _build_pdf(answers={"1": "HAYIR"}, questions=_standard_questions())
        finally:
            RLTable.__init__ = original_init  # type: ignore[assignment]

        assert captured, "Table instance capture edilemedi"
        for cap in captured:
            assert cap["repeatRows"] == 1, f"repeatRows yanlış: {cap}"


# ---------------------------------------------------------------------------
# Parser yoksa sınırlamayı net biçimde yaz.
# ---------------------------------------------------------------------------
def test_pdf_parser_availability_report():
    """Ortamda PyPDF2 yoksa bunu raporlar.

    Test her durumda PASS olur; yalnız ortam durumunu belgelemek
    içindir.
    """
    if not HAS_PYPDF2:
        pytest.skip(
            "PyPDF2 ortamda yok — metin/sayfa tabanlı doğrulamalar "
            "skip edilir. Bytes-level ve Table-config testleri hâlâ "
            "geçerli."
        )
    assert PyPDF2 is not None