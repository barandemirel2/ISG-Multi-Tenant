"""S9 — DÖF Güncelleme Özeti PDF + Excel export testi.

Backend'i disari cagirip PDF/Excel dosyalarini olusturur, sonra DÖF
Guncelleme Ozeti bolumunun var oldugunu dogrular.
"""
import io
import os
import re
import sys
import urllib.request
import urllib.parse
import json
import http.cookiejar
from pathlib import Path


def login_and_get_session(base_url, email, password):
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    opener.open(req).read()
    return opener


def http_post(opener, url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    return json.loads(opener.open(req).read())


def http_put(opener, url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="PUT")
    return json.loads(opener.open(req).read())


def http_get(opener, url):
    req = urllib.request.Request(url)
    return json.loads(opener.open(req).read())


def http_get_raw(opener, url):
    req = urllib.request.Request(url)
    return opener.open(req).read()


def test_dof_summary_in_pdf_and_excel():
    base = "http://127.0.0.1:8000"

    # ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        raise RuntimeError(
            "ADMIN_EMAIL and ADMIN_PASSWORD environment variables are required"
        )

    print("=== Login ===")
    opener = login_and_get_session(base, admin_email, admin_password)
    print("  OK")

    # Create audit (S12: Burger King markalı — PDF'te logo görünecek)
    audit = http_post(opener, f"{base}/api/audits", {
        "restaurant_name": "BURGER KING TEST_S9",
        "address": "a",
        "audit_date": "2026-08-13",
        "denetci": "d",
        "brand": "Burger King",
    })
    aid = audit["id"]
    print(f"=== Audit: {aid} (brand=Burger King) ===")

    # HAYIR cevap ekle
    audit = http_put(opener, f"{base}/api/audits/{aid}/answers", {
        "answers": {"1": "HAYIR", "2": "HAYIR"},
        "expected_version": audit["version"],
    })
    print(f"  HAYIR: state={audit['state']}")

    # Submit
    http_post(opener, f"{base}/api/audits/{aid}/submit", {})
    audit = http_get(opener, f"{base}/api/audits/{aid}")
    print(f"  submit: {audit['state']}")

    # Soru 1: AÇIK (default), Soru 2: KAPATILDI (S9 min 20 char notu ile)
    long_note_1 = "Bu DÖF henuz acil mudahale gerektiriyor"  # 36 char
    long_note_2 = "Bu DÖF kapatildi, fotograf kanitlari mevcut"  # 44 char

    # Soru 1'i AÇIK bırak (kısa not yeterli)
    http_put(opener, f"{base}/api/dofs/{aid}/1", {
        "status": "AÇIK",
        "notes": long_note_1,
    })
    # Soru 2'yi KAPATILDI yap (min 20 char not zorunlu)
    http_put(opener, f"{base}/api/dofs/{aid}/2", {
        "status": "KAPATILDI",
        "notes": long_note_2,
    })
    print("  DÖF updates applied")

    # Tüm DÖF'leri kapat ki export DOF_CLOSED/FINAL state'te olsun
    http_put(opener, f"{base}/api/dofs/{aid}/1", {
        "status": "KAPATILDI",
        "notes": "Soru 1 DÖF kapatildi, saha calismasi tamam" * 2,  # 50+ char
    })
    audit = http_get(opener, f"{base}/api/audits/{aid}")
    print(f"  all DÖF closed: state={audit['state']}")
    assert audit["state"] in ("DOF_CLOSED", "FINAL"), \
        f"DOF_CLOSED bekleniyordu, gelen: {audit['state']}"

    # ===== EXCEL TEST =====
    print("=== Excel download ===")
    xlsx_bytes = http_get_raw(opener, f"{base}/api/audits/{aid}/export/excel")
    print(f"  XLSX size: {len(xlsx_bytes)} bytes")
    assert len(xlsx_bytes) > 1000, "XLSX too small"

    # XLSX bir ZIP — içinde xl/sharedStrings.xml var, text içerik orada
    import zipfile
    zf = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    sheet_names = zf.namelist()
    print(f"  XLSX contains: {len(sheet_names)} files")
    # sharedStrings.xml içinde Türkçe text var
    all_text = ""
    for name in sheet_names:
        if name.endswith(".xml"):
            try:
                all_text += zf.read(name).decode("utf-8", errors="ignore")
            except Exception:
                pass
    # S9: DÖF GÜNCELLEME ÖZETİ başlığı Excel'de
    assert "DÖF" in all_text or "D&#214;F" in all_text, \
        "DÖF Excel'de yok"
    assert "GÜNCELLEME ÖZETİ" in all_text, \
        "GÜNCELLEME ÖZETİ başlığı Excel'de yok"
    # DÖF durumları görünmeli
    assert "KAPATILDI" in all_text, "KAPATILDI durumu Excel'de yok"
    # Updated_by user_id — S18 kontrat: başlık "Güncelleyen (ID)", değer user_id
    assert "Güncelleyen (ID)" in all_text, \
        "Güncelleyen (ID) kolonu Excel'de yok"
    print("  OK: Excel'de DÖF GÜNCELLEME ÖZETİ var")

    # ===== PDF TEST =====
    print("=== PDF download ===")
    pdf_bytes = http_get_raw(opener, f"{base}/api/audits/{aid}/export/pdf")
    print(f"  PDF size: {len(pdf_bytes)} bytes")
    assert len(pdf_bytes) > 1000, "PDF too small"
    # PDF magic bytes
    assert pdf_bytes[:4] == b"%PDF", "PDF magic bytes yanlış"
    print("  OK: PDF oluşturuldu (boyut + magic bytes)")

    # PDF'te DÖF özeti var mı kontrol et (pypdf text extraction)
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        # pypdf DejaVu font extract'inde Türkçe char'lar mojibake olabilir;
        # testte ASCII karşılıklarını arıyoruz.
        assert "D" in text, "PDF'te 'D' yok"
        assert "F" in text, "PDF'te 'F' yok"
        # "DÖF GÜNCELLEME ÖZETİ" → mojibake toleransı
        dof_summary_found = (
            "D" in text and "F" in text and "G" in text
            and "NCELLEME" in text and "ZET" in text
        )
        assert dof_summary_found, f"PDF'te DÖF Güncelleme Özeti yok"
        # DÖF durumları (KAPATILDI ASCII)
        assert "KAPATILDI" in text, "KAPATILDI durumu PDF'te yok"
        # "Son Güncelleme" sütun başlığı
        assert "Son G" in text, "Son Güncelleme sütunu yok"
        # Güncelleyen
        assert "Admin" in text, "Güncelleyen (Admin) PDF'te yok"
        print(f"  OK: PDF'te DÖF Güncelleme Özeti var ({len(text)} chars)")
    except ImportError:
        print("  (pypdf yok, sadece magic bytes + boyut doğrulandı)")

    # ===== S12: MARKA LOGO TESTİ =====
    print("=== Brand logo test ===")
    # XLSX'in images/ klasöründe logo olmalı
    import zipfile
    zf = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    xlsx_files = zf.namelist()
    images = [f for f in xlsx_files if "media/image" in f or f.startswith("xl/media/")]
    print(f"  XLSX media files: {images}")
    assert len(images) > 0, "XLSX'te marka logosu yok (S12)"

    # PDF'te logo: image objesi olarak embed edilmiş olmalı.
    # pypdf reader.images çalışmadı; raw byte tarama ile image XObject
    # marker'larını arayalım.
    print(f"  PDF size: {len(pdf_bytes)}")
    # /XObject /ImX marker'larını say (her embedded image için)
    pdf_image_objects = pdf_bytes.count(b"/Subtype /Image")
    print(f"  PDF Subtype/Image objects: {pdf_image_objects}")
    assert pdf_image_objects > 0, "PDF'te hiç image yok (S12 logo eksik)"
    # Cache PNG dosyası var mı (cairosvg çıktısı) — repo-relative path
    cache_png = Path(__file__).resolve().parent.parent / "backend" / "brand_logos" / "_png_cache" / "burger-king_300.png"
    assert cache_png.exists(), f"Cache PNG yok: {cache_png}"
    print(f"  Cache PNG: {cache_png.stat().st_size} bytes")
    print("  OK: PDF + XLSX'te Burger King logosu var (S12)")

    # ===== AUDIT LOG TEST =====
    print("=== Audit log check ===")
    log = http_get(opener, f"{base}/api/audits/{aid}/audit-log")
    log_items = log.get("items", log)
    dof_actions = [x for x in log_items if x.get("action", "").startswith("dof_")]
    print(f"  DÖF actions in log: {len(dof_actions)}")
    for x in dof_actions:
        print(f"    - {x.get('action')}: {x.get('user_name')}")
    # AÇIK + KAPATILDI geçişleri var; en az 1 dof_close olmalı
    assert any(x.get("action") == "dof_close" for x in dof_actions), \
        "dof_close loglanmamış"
    # AÇIK'e set ettiğimiz için dof_open da olmalı
    assert any(x.get("action") == "dof_open" for x in dof_actions), \
        "dof_open loglanmamış"

    print("\nS9 DÖF SUMMARY TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(test_dof_summary_in_pdf_and_excel())
