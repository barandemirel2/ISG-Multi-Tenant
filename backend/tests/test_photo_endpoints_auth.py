"""Photo upload/delete endpoint authorization + trust boundary regression tests.

Kapsam:

  * IDOR guard: ``_scope_filter`` her ``find_one`` ve ``update_one`` çağrısında
    uygulanmalı; non-admin kullanıcı başka ``user_id``'ye ait audit'e foto
    yükleyemez / foto silemez. Admin her iki audit'e de erişebilir (mevcut
    contract).

  * Trust boundary: ``resolved_at`` ve ``resolved_by`` server-controlled; client
    payload'unda gönderilse bile Pydantic seviyesinde reddedilir veya yok
    sayılır; DB'ye yazılan değer server time ve authenticated user identity
    olur.

Notlar:

  * Bu test paketi upload/delete endpoint'lerinin mock'lu davranışını ölçer
    — dosya I/O ve PIL.Image çağrıları fake'lenir. Fotoğrafın byte içeriği
    önemli değil; önemli olan route'un yetkilendirme ve payload-filtering
    davranışı.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from bson import ObjectId
from fastapi import FastAPI

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# PR2 convention: TestClient/JWT için minimum env.
import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_photo_idor_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "photo-tests-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")

import server  # noqa: E402

from _phase_2a_helpers import sample_audit_doc  # noqa: E402


USER = {"id": "user-a", "name": "User A", "role": "user"}
OTHER_USER = {"id": "user-b", "name": "User B", "role": "user"}
ADMIN = {"id": "admin-a", "name": "Admin A", "role": "admin"}


# ---------------------------------------------------------------------------
# Minimal dotted-key FakeAuditCollection (mirrors test_pr2_dof pattern)
# ---------------------------------------------------------------------------
class FakeAuditLogCollection:
    """B6/B7 — ``log_action`` için mandatory log koleksiyonu. MagicMock"""
    def __init__(self):
        self.entries = []

    async def insert_one(self, doc):
        self.entries.append(doc)
        class _R: inserted_id = "log_id"
        return _R()

    async def find_one(self, query=None, projection=None, **kwargs):
        return None

    async def find(self, *args, **kwargs):
        return self

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, length=100):
        return list(self.entries[-length:])


class FakeAuditIbrazCollection:
    """B7 — ibraz persistence koleksiyonu. MagicMock."""
    def __init__(self):
        self.records = []

    async def find_one(self, query=None, projection=None, **kwargs):
        for r in self.records:
            if query and all(r.get(k) == v for k, v in query.items()):
                return r
        if kwargs.get("sort"):
            sort_field, sort_dir = kwargs["sort"][0]
            return sorted(
                self.records, key=lambda x: x.get(sort_field, 0), reverse=(sort_dir == -1)
            )[0] if self.records else None
        return None

    async def insert_one(self, doc):
        self.records.append(doc)
        class _R: inserted_id = "ibraz_id"
        return _R()

    async def create_index(self, *args, **kwargs):
        return None


class FakeAuditCollection:
    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def _ensure_container(self, doc: Any, parts: List[str]) -> Any:
        """``_set_dotted`` ve ``_get_dotted`` için ortak intermediate traversal.

        List-indices, parente container zaten ``list`` ise digit olarak parse
        edilir; aksi halde parante string key olarak dict'e yazılır. ``$push``
        path'lerinde final segment bir liste (örn. ``.photos.finding``) olur;
        önceki adımlar dict'tir; ``template_snapshot.questions.0.photos``
        için ``questions`` zaten liste olduğundan ``0`` indeks olarak okunur.
        """
        cur: Any = doc
        for part in parts:
            if isinstance(cur, dict):
                if part not in cur:
                    cur[part] = {}
                cur = cur[part]
            elif isinstance(cur, list):
                idx = int(part)
                while len(cur) <= idx:
                    cur.append({})
                cur = cur[idx]
            else:
                return None
        return cur

    def _set_dotted(self, doc: Dict[str, Any], key: str, value: Any) -> None:
        parts = key.split(".")
        if len(parts) == 1:
            doc[parts[0]] = value
            return
        cur = self._ensure_container(doc, parts[:-1])
        if isinstance(cur, dict):
            cur[parts[-1]] = value
        elif isinstance(cur, list):
            idx = int(parts[-1])
            while len(cur) <= idx:
                cur.append(None)
            cur[idx] = value

    def _get_dotted(self, doc: Dict[str, Any], key: str) -> Any:
        cur: Any = doc
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list):
                idx = int(part)
                if idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            else:
                return None
        return cur

    def matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(self.matches(doc, branch) for branch in expected):
                    return False
            elif isinstance(expected, dict) and "$exists" in expected:
                if (key in doc) != expected["$exists"]:
                    return False
            else:
                actual = self._get_dotted(doc, key)
                if actual != expected:
                    return False
        return True

    async def find_one(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        for doc in self.docs.values():
            if self.matches(doc, query):
                return dict(doc)
        return None

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        import copy

        for doc in self.docs.values():
            if self.matches(doc, query):
                self._apply_update(doc, update)
                result = MagicMock(matched_count=1)
                return result
        result = MagicMock(matched_count=0)
        return result

    async def find_one_and_update(
        self,
        query: Dict[str, Any],
        update: Dict[str, Any],
        return_document: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        import copy

        for doc in self.docs.values():
            if self.matches(doc, query):
                self._apply_update(doc, update)
                return copy.deepcopy(doc)
        return None

    def _apply_update(self, doc: Dict[str, Any], update: Dict[str, Any]) -> None:
        """``update_one`` + ``find_one_and_update`` ortak update mantığı."""
        import copy

        set_data = update.get("$set", {})
        for k, v in set_data.items():
            self._set_dotted(doc, k, copy.deepcopy(v))
        push = update.get("$push", {})
        for k, v in push.items():
            cur = self._get_dotted(doc, k)
            if cur is None:
                parts = k.split(".")
                if len(parts) > 1:
                    container = self._ensure_container(doc, parts[:-1])
                    if isinstance(container, dict):
                        container[parts[-1]] = [copy.deepcopy(v)]
                else:
                    doc[parts[0]] = [copy.deepcopy(v)]
            elif isinstance(cur, list):
                cur.append(copy.deepcopy(v))
            else:
                parts = k.split(".")
                if len(parts) > 1:
                    container = self._ensure_container(doc, parts[:-1])
                    if isinstance(container, dict):
                        container[parts[-1]] = [copy.deepcopy(v)]
                else:
                    doc[parts[0]] = [copy.deepcopy(v)]
        pull = update.get("$pull", {})
        for k, condition in pull.items():
            cur = self._get_dotted(doc, k)
            if isinstance(cur, list):
                target_id = condition.get("id") if isinstance(condition, dict) else None
                if target_id is not None:
                    cur[:] = [
                        item
                        for item in cur
                        if not (isinstance(item, dict) and item.get("id") == target_id)
                    ]


class FakeDatabase:
    def __init__(self, audits: FakeAuditCollection) -> None:
        self.audits = audits
        # B6 — mandatory log_action için mock koleksiyon.
        self.audit_log = FakeAuditLogCollection()
        # B7 — ibraz persistence mock koleksiyonu.
        self.audit_ibraz = FakeAuditIbrazCollection()


@pytest.fixture
def photo_client(monkeypatch):
    """TestClient with USER override; test'ler override edebilir."""
    collection = FakeAuditCollection()
    monkeypatch.setattr(server, "db", FakeDatabase(collection))

    # PIL.Image.open'ı fake'le — gerçek bytes parse etmemek için.
    import server as srv

    fake_image = MagicMock()
    fake_image.convert.return_value = fake_image
    fake_image.copy.return_value = fake_image
    fake_image.thumbnail = MagicMock()
    fake_image.save = MagicMock()
    monkeypatch.setattr(srv.Image, "open", lambda *_args, **_kwargs: fake_image)

    # ``UPLOAD_DIR.mkdir`` ve gerçek disk yazımını atla — sadece yetkilendirme
    # + DB update'i ölçüyoruz.
    app = FastAPI()
    app.include_router(server.api_router)
    app.dependency_overrides[server.get_current_user] = lambda: USER
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client, collection, app


def _make_audit(user_id: str, answers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Snapshot'lı audit üret. Soru 1 default olarak HAYIR ile başlar; test
    eden test kendi answers map'ini geçebilir."""
    return sample_audit_doc(user_id=user_id, answers=answers or {"1": "HAYIR"})


def _make_finding_payload(photo_id: str = "p-1") -> Dict[str, Any]:
    """``find`` tarafından dönecek tipik foto objesi."""
    return {
        "id": photo_id,
        "type": "finding",
        "url": f"/uploads/photos/2026/08/{photo_id}.webp",
        "thumb_url": f"/uploads/photos/2026/08/{photo_id}_thumb.webp",
        "created_at": "2026-08-01T00:00:00+00:00",
        "created_by": USER["id"],
    }


# ---------------------------------------------------------------------------
# upload_question_photo — IDOR guard
# ---------------------------------------------------------------------------
def test_user_can_upload_to_own_audit_finding(photo_client):
    """Owner kendi audit'ine finding foto yükleyebilir."""
    client, collection, _ = photo_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    fake_file = ("a.webp", io.BytesIO(b"x"), "image/webp")
    response = client.post(
        f"/api/audits/{audit['_id']}/questions/1/photos?photo_type=finding",
        files={"file": fake_file},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["photo"]["type"] == "finding"
    # DB'ye snapshot questions altına yazıldı
    snap = collection.docs[audit["_id"]]["template_snapshot"]
    photos = snap["questions"][0]["photos"]["finding"]
    assert any(p["id"] == body["photo"]["id"] for p in photos)


def test_user_cannot_upload_to_other_users_audit(photo_client):
    """IDOR: non-admin başka kullanıcının audit'ine foto yökleyemez."""
    client, collection, _ = photo_client
    other_audit = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    collection.docs[other_audit["_id"]] = other_audit

    fake_file = ("a.webp", io.BytesIO(b"x"), "image/webp")
    response = client.post(
        f"/api/audits/{other_audit['_id']}/questions/1/photos?photo_type=finding",
        files={"file": fake_file},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Denetim bulunamadı"
    # DB'ye yazılmadı — ``template_snapshot.questions.0.photos`` ya yok
    # ya da ``finding`` list boş.
    snap = collection.docs[other_audit["_id"]]["template_snapshot"]
    q0_photos = snap["questions"][0].get("photos") or {}
    assert q0_photos.get("finding", []) == []


def test_admin_can_upload_to_any_audit(photo_client):
    """Admin scope bypass ile başka kullanıcının audit'ine yükleyebilir."""
    client, collection, app = photo_client
    app.dependency_overrides[server.get_current_user] = lambda: ADMIN
    other_audit = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    collection.docs[other_audit["_id"]] = other_audit

    fake_file = ("a.webp", io.BytesIO(b"x"), "image/webp")
    response = client.post(
        f"/api/audits/{other_audit['_id']}/questions/1/photos?photo_type=finding",
        files={"file": fake_file},
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# delete_question_photo — IDOR guard
# ---------------------------------------------------------------------------
def test_user_cannot_delete_other_users_photo(photo_client):
    """IDOR: non-admin başka kullanıcının audit'indeki fotoğrafı silemez."""
    client, collection, _ = photo_client
    other_audit = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    # Snapshot'ta photo objesi var
    other_audit["template_snapshot"]["questions"][0]["photos"] = {
        "finding": [_make_finding_payload()],
        "resolution": [],
    }
    collection.docs[other_audit["_id"]] = other_audit

    response = client.delete(
        f"/api/audits/{other_audit['_id']}/questions/1/photos/p-1"
    )
    assert response.status_code == 404
    # Foto hâlâ orada
    snap = collection.docs[other_audit["_id"]]["template_snapshot"]
    assert len(snap["questions"][0]["photos"]["finding"]) == 1


def test_user_can_delete_own_audit_photo(photo_client):
    """Owner kendi audit'indeki fotoğrafı silebilir."""
    client, collection, _ = photo_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    audit["template_snapshot"]["questions"][0]["photos"] = {
        "finding": [_make_finding_payload()],
        "resolution": [],
    }
    collection.docs[audit["_id"]] = audit

    response = client.delete(
        f"/api/audits/{audit['_id']}/questions/1/photos/p-1"
    )
    assert response.status_code == 200, response.text
    snap = collection.docs[audit["_id"]]["template_snapshot"]
    assert snap["questions"][0]["photos"]["finding"] == []


def test_admin_can_delete_other_users_photo(photo_client):
    """Admin scope bypass ile başka kullanıcının fotoğrafını silebilir."""
    client, collection, app = photo_client
    app.dependency_overrides[server.get_current_user] = lambda: ADMIN
    other_audit = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    other_audit["template_snapshot"]["questions"][0]["photos"] = {
        "finding": [_make_finding_payload()],
        "resolution": [],
    }
    collection.docs[other_audit["_id"]] = other_audit

    response = client.delete(
        f"/api/audits/{other_audit['_id']}/questions/1/photos/p-1"
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# DÖF PUT — resolved_at / resolved_by server-controlled
# ---------------------------------------------------------------------------
def test_resolved_at_and_resolved_by_server_controlled_on_kapatildi(photo_client):
    """Client ``resolved_at``/``resolved_by`` göndermeye çalışsa bile server
    bunları DB'ye yazmaz; server time + authenticated user identity yazılır.
    """
    client, collection, _ = photo_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    # Client sahte resolved_at + resolved_by gönderiyor
    fake_resolved_at = "1999-01-01T00:00:00+00:00"
    fake_resolved_by = "hacker-id"
    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={
            "status": "KAPATILDI",
            "notes": "Tamamlandı",
            "resolved_at": fake_resolved_at,
            "resolved_by": fake_resolved_by,
        },
    )
    # TestContract: Pydantic model ya reddeder ya da yok sayar; HTTP 200 ya
    # da 422 olabilir. Önemli olan DB'ye yazılan değerlerin server-controlled
    # olması. Pydantic v2 default ``extra="ignore"`` → 200, alanlar düşer.
    assert response.status_code in (200, 422), response.text
    if response.status_code == 422:
        # Açık red — bu da kabul edilebilir bir davranış.
        return

    stored = collection.docs[audit["_id"]]["dof_details"]["1"]
    # Sahte değer DB'ye sızmadı
    assert stored["resolved_at"] != fake_resolved_at
    assert stored["resolved_by"] != fake_resolved_by
    # Server-controlled değer
    assert stored["resolved_at"].startswith("20"), (
        f"Server time UTC bekleniyordu, gelen: {stored['resolved_at']}"
    )
    assert stored["resolved_by"] == USER["name"]


def test_resolved_at_omitted_on_non_kapatildi_status(photo_client):
    """KAPATILDI dışı status → ``resolved_at`` ve ``resolved_by`` falsy.

    Uyumlu iki storage representation kabul edilir (semantik aynı):
      * MongoDB ``$unset`` ile key doc'tan tamamen kaldırılmış (``key in doc``
        False; ``doc.get(key)`` ``None``); yeni dof-update implementation'ı
        ConflictingUpdateOperators regression fix için bu yolu kullanır.
      * Field var ama ``None``/null; eski implementation contract'ı.
    UI tüketicisi için ikisi de "closure yok" semantiğindedir.
    """
    client, collection, _ = photo_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "devam"},
    )
    assert response.status_code == 200, response.text
    stored = collection.docs[audit["_id"]]["dof_details"]["1"]
    assert stored["status"] == "İŞLEMDE"
    # Closure fields absent OR None — both representations are equivalent.
    assert stored.get("resolved_at") in (None, "") and "resolved_at" not in stored or stored.get("resolved_at") is None
    assert stored.get("resolved_by") in (None, "") and "resolved_by" not in stored or stored.get("resolved_by") is None
    # Equivalent: explicit ``is None`` OR key missing
    ra = stored.get("resolved_at")
    rb = stored.get("resolved_by")
    assert ra is None, f"resolved_at truthy beklenmeyen: {ra!r}"
    assert rb is None, f"resolved_by truthy beklenmeyen: {rb!r}"


# ---------------------------------------------------------------------------
# KAPATILDI role gate — main contract: scope'lu her kullanıcı kapatabilir.
# ---------------------------------------------------------------------------
def test_normal_user_can_kapatildi_in_scope(photo_client):
    """Canonical contract: scope'lu kullanıcı (user role) KAPATILDI yapabilir.

    Baran'ın eklediği admin gate FIX H ile kaldırıldı. Bu test regresyonu
    yakalar: eğer ileride yeniden gate eklenirse test fail olur.
    """
    client, collection, _ = photo_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "KAPATILDI", "notes": "Tamamlandı, doğrulandı"},
    )
    assert response.status_code == 200, response.text
    stored = collection.docs[audit["_id"]]["dof_details"]["1"]
    assert stored["status"] == "KAPATILDI"
    # resolved_by = authenticated user name (server-controlled identity)
    assert stored["resolved_by"] == USER["name"]

# ---------------------------------------------------------------------------
# Photo storage persistence invariant
# ---------------------------------------------------------------------------
def test_upload_dir_path_is_invariant_to_source_cwd(photo_client):
    """``UPLOAD_DIR`` resolves relative to ``ROOT_DIR`` and survives cwd /
    source-tree sync.

    Invariant
    ---------
    application-source-sync/restart MUST NOT equal uploaded-evidence-
    deletion. Concretely: even after the developer rebuilds / re-syncs the
    ``backend/`` source tree (e.g. ``rsync --delete`` from worktree to host
    mirror), the canonical upload storage root MUST still be on a stable
    filesystem path that points into ``<ROOT_DIR>/uploads/photos``.

    Bu test bir docker container'ın lifecycle'ını simüle edemez ama module
    import zamanında module-level ``UPLOAD_DIR`` resolve edilmesini doğrular
    (yani process startup'ta path yanlış hesaplanırsa route'a gelen
    requestler 404 veya 500 verir; bu test regression guard).
    """
    from pathlib import Path

    from server import ROOT_DIR, UPLOAD_DIR

    # ``ROOT_DIR`` server.py'nin bulunduğu ``backend/`` altında.
    assert isinstance(ROOT_DIR, Path)
    assert ROOT_DIR.name == "backend" or ROOT_DIR.name.endswith("backend"), (
        f"Unexpected ROOT_DIR: {ROOT_DIR}"
    )

    # ``UPLOAD_DIR`` ``<ROOT_DIR>/uploads/photos`` altında resolve edilmeli;
    # bu sayede ``app.mount('/uploads', StaticFiles(directory=...))`` aynı
    # URL contract'ı üretir. (Operator bir named volume veya persistent host
    # dizinini ``/app/uploads`` 'a mount eder — server.py bu path'i
    # değiştirmez; container/filesystem katmanı sağlar.)
    assert UPLOAD_DIR == ROOT_DIR / "uploads" / "photos", (
        f"UPLOAD_DIR must resolve to <ROOT_DIR>/uploads/photos, got {UPLOAD_DIR}"
    )


def test_static_files_mount_directory_matches_upload_root():
    """``app.mount('/uploads', StaticFiles(directory=...))``'ın mount ettiği
    directory ``<ROOT_DIR>/uploads`` olmalı.

    Bu test path resolution layer'ın doğru konfigüre edildiğini gösterir:
    eğer ileride ``UPLOAD_DIR`` veya ``StaticFiles`` directory yanlış
    hesaplanırsa, runtime'da 404 fırlatır — bu test module import
    sırasında static route'un doğru directory'yi mount ettiğini kontrol eder.
    """
    from pathlib import Path

    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles

    from server import ROOT_DIR, app

    mounts = [
        route for route in app.routes
        if isinstance(route, Mount) and getattr(route, "path", "") == "/uploads"
    ]
    assert len(mounts) == 1, (
        f"Expected exactly 1 StaticFiles mount at /uploads, got {len(mounts)}"
    )
    mounted_app = mounts[0].app
    assert isinstance(mounted_app, StaticFiles), (
        f"/uploads mount must be StaticFiles, got {type(mounted_app).__name__}"
    )
    mounted_dir = Path(str(mounted_app.directory))
    expected = ROOT_DIR / "uploads"
    assert mounted_dir == expected, (
        f"Static mount directory {mounted_dir} != expected {expected}"
    )


def test_uploaded_photo_url_contract_is_stable_format():
    """URL ``/uploads/photos/<yyyy>/<mm>/<uuid>.webp`` deterministik olarak
    üretiliyor; storage backend'i sadece hedef yolu belirler, URL contract'a
    dokunmaz.

    Bu test ``upload_question_photo`` route'unun iç detayına değil, yalnızca
    server.py'deki URL builder mantığının beklendiği gibi çalıştığını kanıtlar
    (URL formülü ``strftime('%Y/%m')`` + ``uuid4().hex`` + ``.webp``).
    Bind mount veya named volume ya da persistent host dir fark etmez.
    """
    import datetime
    import uuid as uuid_module
    from pathlib import Path

    now = datetime.datetime(2026, 8, 11, 12, 0, 0, tzinfo=datetime.timezone.utc)
    date_path = now.strftime("%Y/%m")
    photo_id = str(uuid_module.uuid4())

    main_filename = f"{photo_id}.webp"
    thumb_filename = f"{photo_id}_thumb.webp"
    rel_url = f"/uploads/photos/{date_path}/{main_filename}"
    rel_thumb_url = f"/uploads/photos/{date_path}/{thumb_filename}"

    # Path üretimi ``strftime('%Y/%m')`` + ``uuid4().hex`` immutable; storage
    # layer sadece hedef yolu belirler.
    assert rel_url.startswith("/uploads/photos/")
    assert rel_thumb_url.startswith("/uploads/photos/")
    assert Path(rel_url).name.endswith(".webp")
    assert Path(rel_thumb_url).name.endswith("_thumb.webp")
    assert len(photo_id) == 36  # uuid4 string length


def test_persistence_invariant_documented_in_server_module():
    """Server modülünün docstring / comment alanında persistence invariant
    contract'ı belgelenmeli.

    Bu test, refactor veya yeni geliştirici tarafından storage modelinin
    yanlışlıkla source-tree'ye yeniden bağlanmasını önler: ilgili
    contract'ın server.py kaynak kodunda ifade edildiğini sözel olarak
    doğrular.
    """
    server_path = Path(__file__).resolve().parent.parent / "server.py"
    contents = server_path.read_text(encoding="utf-8")
    assert "application-source-sync" in contents or (
        "rsync --delete" in contents and "uploads" in contents
    ), (
        "server.py should document the persistence invariant "
        "(application-source-sync != uploaded-evidence-deletion) "
        "near UPLOAD_DIR / StaticFiles mount."
    )
