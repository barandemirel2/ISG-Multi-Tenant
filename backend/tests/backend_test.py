"""Backend API integration tests for ABCD Tech Solutions Risk Analiz Sistemi.

Bunlar EXTERNAL INTEGRATION testleridir: **çalışan bir backend** ve geçerli
bir admin hesabı gerektirir. Deterministik unit suite'ten (mongomock/httpx,
canlı sunucu yok) bilinçli olarak AYRILIR.

Çalıştırmak için::

    BACKEND_INTEGRATION_URL=http://localhost:8001 \\
    ADMIN_EMAIL=... ADMIN_PASSWORD=... \\
    pytest tests/backend_test.py

Environment:
  * ``BACKEND_INTEGRATION_URL`` (veya ``REACT_APP_BACKEND_URL``) — canlı
    backend base URL'i (örn. ``http://localhost:8001``).
  * ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD`` — seed edilmiş admin kimlik bilgileri.
    Hardcoded fallback YOKTUR; biri eksikse modül atlanır (skip).
"""
import os
import io
import pytest
import requests

BASE_URL = (
    os.environ.get("BACKEND_INTEGRATION_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or ""
).rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Explicit environment requirement — canlı hedef olmadan bu testler çalıştırılamaz.
# (Bu, "green number elde etmek için" kör bir skip DEĞİL; testler ayrıca canlı
# backend'e karşı çalıştırılıp sonuçları ayrı raporlanır.)
if not BASE_URL:
    pytest.skip(
        "BACKEND_INTEGRATION_URL/REACT_APP_BACKEND_URL set edilmedi; "
        "external integration tests canlı bir backend gerektirir",
        allow_module_level=True,
    )
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    pytest.skip(
        "ADMIN_EMAIL/ADMIN_PASSWORD set edilmedi (hardcoded kimlik bilgisi yok)",
        allow_module_level=True,
    )

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def new_user_session():
    import uuid
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "TestPass123", "name": "Test User"})
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    return s, email


# ---------- Health ----------
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------- Auth ----------
def test_register_and_autologin(new_user_session):
    s, email = new_user_session
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email
    assert data["role"] == "user"


def test_register_duplicate(new_user_session):
    s, email = new_user_session
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "TestPass123", "name": "Dup"})
    assert r.status_code == 400


def test_login_admin(admin_session):
    r = admin_session.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL


def test_login_bad_credentials():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_me_unauthenticated():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


# ---------- Questions ----------
def test_questions_count(admin_session):
    r = admin_session.get(f"{API}/questions")
    assert r.status_code == 200
    data = r.json()
    assert len(data["categories"]) == 9
    assert len(data["questions"]) == 84
    # Expected categories (Phase 2B numaralı kategori şeması)
    expected = {
        "1. Genel İş Sağlığı ve Güvenliği Organizasyonu & Belgeleme": 10,
        "2. Yangın Güvenliği, Acil Durum ve Tahliye Sistemleri": 10,
        "3. Elektrik ve Tesisat Güvenliği": 10,
        "4. Mutfak, Pişirme, Kızartma ve Isıl İşlem Ekipmanları": 10,
        "5. Soğuk Hava Depoları, Depolama ve Ergonomi": 10,
        "6. Kişisel Koruyucu Donanımlar (KKD) ve Hijyen": 10,
        "7. Bina, Yapı, Zemin, Kayma-Düşme Riskleri ve Merdivenler": 10,
        "8. Atık Yönetimi, Kimyasal Güvenlik ve Havalandırma": 8,
        "9. İşveren Vekili Denetimi, İlk Yardım ve Müşteri Alanları Güvenliği": 6,
    }
    counts = {}
    for q in data["questions"]:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    for cat, cnt in expected.items():
        assert counts.get(cat) == cnt, f"{cat}: expected {cnt}, got {counts.get(cat)}"


def test_questions_unauth():
    r = requests.get(f"{API}/questions")
    assert r.status_code == 401


# ---------- Audits CRUD ----------
@pytest.fixture(scope="module")
def audit_id(admin_session):
    r = admin_session.post(f"{API}/audits", json={
        "restaurant_name": "TEST_Popeyes Kadıköy",
        "address": "Kadıköy, İstanbul",
        "audit_date": "2026-01-15",
        "denetci": "Test Denetçi",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["restaurant_name"] == "TEST_Popeyes Kadıköy"
    assert d["version"] == 0
    assert d["summary"]["total_questions"] == 84
    return d["id"]


def test_get_audit(admin_session, audit_id):
    r = admin_session.get(f"{API}/audits/{audit_id}")
    assert r.status_code == 200
    assert r.json()["id"] == audit_id


def test_list_audits(admin_session, audit_id):
    r = admin_session.get(f"{API}/audits")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert audit_id in ids


def test_update_answers_and_summary(admin_session, audit_id):
    # Answer HAYIR on question id 1, EVET on 2, NA on 3
    answers = {"1": "HAYIR", "2": "EVET", "3": "NA"}
    r = admin_session.put(f"{API}/audits/{audit_id}/answers", json={"expected_version": 0, "answers": answers})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["answers"]["1"] == "HAYIR"
    assert d["summary"]["counts"]["EVET"] == 1
    assert d["summary"]["counts"]["HAYIR"] == 1
    assert d["summary"]["counts"]["NA"] == 1
    assert d["summary"]["answered"] == 3

    # Verify persistence with GET
    r2 = admin_session.get(f"{API}/audits/{audit_id}")
    assert r2.json()["answers"]["1"] == "HAYIR"


def test_export_excel(admin_session, audit_id):
    # S18 lifecycle: nihai rapor export'u yalnızca DOF_CLOSED/FINAL.
    # DRAFT → submit → DOF_OPEN (soru 1 HAYIR) → DÖF KAPATILDI → DOF_CLOSED.
    r_submit = admin_session.post(f"{API}/audits/{audit_id}/submit")
    assert r_submit.status_code == 200, r_submit.text
    r_close = admin_session.put(
        f"{API}/dofs/{audit_id}/1",
        json={"status": "KAPATILDI", "notes": "Saha düzeltmesi tamamlandı ve doğrulandı"},
    )
    assert r_close.status_code == 200, r_close.text
    r = admin_session.get(f"{API}/audits/{audit_id}/export/excel")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("content-type", "")
    # Sanity check xlsx magic bytes (PK zip)
    assert r.content[:2] == b"PK"
    assert len(r.content) > 2000


def test_export_pdf(admin_session, audit_id):
    r = admin_session.get(f"{API}/audits/{audit_id}/export/pdf")
    assert r.status_code == 200
    assert "pdf" in r.headers.get("content-type", "")
    assert r.content[:4] == b"%PDF"


def test_isolation_between_users(new_user_session, audit_id):
    s, _ = new_user_session
    r = s.get(f"{API}/audits/{audit_id}")
    assert r.status_code == 404


def test_delete_audit(admin_session, audit_id):
    r = admin_session.delete(f"{API}/audits/{audit_id}")
    assert r.status_code == 200
    r2 = admin_session.get(f"{API}/audits/{audit_id}")
    assert r2.status_code == 404


def test_logout(admin_session):
    r = admin_session.post(f"{API}/auth/logout")
    assert r.status_code == 200
    r2 = admin_session.get(f"{API}/auth/me")
    assert r2.status_code == 401
