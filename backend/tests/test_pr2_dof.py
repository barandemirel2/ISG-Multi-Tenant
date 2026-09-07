"""PR2 DÖF backend contract testleri.

GET /api/dofs + PUT /api/dofs/{audit_id}/{question_id} davranış sözleşmesi.

Karar matrisi (approved):
    OK-1  HAYIR olmayan soru PUT → 409 ``dof_answer_not_hayir``
    OK-2  DÖF PUT ana audit ``version`` ve ``updated_at`` alanlarına dokunmaz
    OK-3  Yalnız canonical İngilizce alanlar (legacy alias YOK)
    OK-4  Mevcut test convention'a uygun (pr2_concurrency.py + _phase_2a_helpers.py)
    OK-5  Yalnız backend/server.py + bu test dosyası değişir

Teknik düzeltmeler — 7 zorunlu:
    1. Storage key = ``question_id`` (stabil int), ``question_no`` ASLA storage key değil
    2. ``question_id: int`` path param → FastAPI doğal 422; snapshot'ta valid
       int yoksa 404
    3. HAYIR koşulu atomik update filtresinde; başarısız atomic update
       sonrası ikinci scoped read ile 404 vs 409 ayrımı
    4. Yeni DÖF response builder (``_build_dof_items``) — ``_summarize``
       yerine snapshot + ``compute_effective_risk`` reuse
    5. ``updated_by`` = ``current_user["id"]``; ``owner_name`` unique
       user_id cache'i ile (N+1 yok)
    6. KAPATILDI + trim-sonrası boş notes → 422 (model_validator); trim DB
       write öncesi uygulanır; max 2000
    7. Auth, JWT, audit answers, expected_version, _version_filter,
       PATCH /audits/{id}, questions.json, frontend DOKUNULMAZ
"""
import asyncio
import copy
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from bson import ObjectId
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock
from pymongo.errors import OperationFailure

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# PR2 convention: TestClient/JWT için minimum env.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_pr2_dof_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "pr2-dof-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")

import server

from _phase_2a_helpers import sample_audit_doc  # noqa: E402


USER = {"id": "user-a", "name": "User A", "role": "user"}
OTHER_USER = {"id": "user-b", "name": "User B", "role": "user"}
ADMIN = {"id": "admin-a", "name": "Admin A", "role": "admin"}


# ---------------------------------------------------------------------------
# Minimal FakeAuditCollection (dotted-key Mongo semantics)
# ---------------------------------------------------------------------------
class FakeAuditCollection:
    """``db.audits`` için stateful + dotted-key destekli mock.

    Neden ayrı? ``_phase_2a_helpers.FakeAuditsCollection`` ``$set`` içinde
    sadece düz ``doc[k] = v`` uygular; DÖF write ise ``dof_details.1``
    gibi dotted Mongo path'leri nested dict olarak yazmayı bekler.
    """

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    @staticmethod
    def _get_dotted(doc: Dict[str, Any], key: str) -> Any:
        cur: Any = doc
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    @staticmethod
    def _set_dotted(doc: Dict[str, Any], key: str, value: Any) -> None:
        parts = key.split(".")
        cur: Dict[str, Any] = doc
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = value

    def matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$and":
                if not all(self.matches(doc, branch) for branch in expected):
                    return False
            elif key == "$or":
                if not any(self.matches(doc, branch) for branch in expected):
                    return False
            elif isinstance(expected, dict) and any(k.startswith("$") for k in expected):
                actual = self._get_dotted(doc, key)
                if "$exists" in expected:
                    # ``$exists`` alanın varlığına bakar (değerinden bağımsız).
                    if (actual is not None) != expected["$exists"]:
                        return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$gte" in expected and not (
                    actual is not None and actual >= expected["$gte"]
                ):
                    return False
                if "$lte" in expected and not (
                    actual is not None and actual <= expected["$lte"]
                ):
                    return False
                if "$eq" in expected and actual != expected["$eq"]:
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
                return copy.deepcopy(doc)
        return None

    async def find_one_and_update(
        self,
        query: Dict[str, Any],
        update: Dict[str, Any],
        return_document: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        async with self.lock:
            for oid, doc in self.docs.items():
                if self.matches(doc, query):
                    self._apply_update(doc, update)
                    return copy.deepcopy(doc)
        return None

    def _apply_update(self, doc: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Mongo update operator semantiği.

        Desteklenen operatorler: ``$set``, ``$unset``, ``$inc``, ``$push``.

        MongoDB uyumluluğu: aynı atomik update içinde ``$set`` bir parent
        path'e (örn. ``a.b``) ve başka bir operator (``$push``, ``$set``,
        ``$unset``) o parent'ın çocuğuna (örn. ``a.b.c``) dokunuyorsa
        ``pymongo.errors.OperationFailure(code=40)`` fırlatır. Bu, gerçek
        MongoDB'nin ``ConflictingUpdateOperators`` davranışıdır — bug
        kanıt testinin (DÖF kapatma 500) sahte geçmesini engeller.
        """
        # 1) Conflict guard: parent-path ihlallerini tespit et.
        set_paths = set((update.get("$set") or {}).keys())
        unset_paths = set((update.get("$unset") or {}).keys())
        inc_paths = set((update.get("$inc") or {}).keys())
        push_paths = set((update.get("$push") or {}).keys())
        all_modified = set_paths | unset_paths | inc_paths | push_paths

        def _is_parent_of(parent: str, child: str) -> bool:
            return child != parent and (
                child.startswith(parent + ".") or child == parent
            )

        # Sadece ``var olan`` parent path'lere dokunan $set/$unset parent'i
        # yok etmek / değiştirmek anlamına gelir; child path'te başka bir
        # operator varsa conflict olur. Mevcut ``doc`` referansı.
        for path in set_paths | unset_paths:
            existing = self._get_dotted(doc, path)
            parent_is_existing_object = isinstance(existing, dict)
            for other in all_modified - {path}:
                if _is_parent_of(path, other) and parent_is_existing_object:
                    raise OperationFailure(
                        f"Updating the path '{other}' would create a conflict at '{path}'",
                        code=40,
                        details={
                            "errmsg": f"Updating the path '{other}' would create a conflict at '{path}'",
                            "code": 40,
                            "codeName": "ConflictingUpdateOperators",
                        },
                    )

        # 2) Operasyonları gerçekleştir.
        for key, value in (update.get("$set") or {}).items():
            self._set_dotted(doc, key, copy.deepcopy(value))
        for key, value in (update.get("$inc") or {}).items():
            cur = self._get_dotted(doc, key) or 0
            self._set_dotted(doc, key, cur + value)
        for key, value in (update.get("$unset") or {}).items():
            self._unset_dotted(doc, key)
        for key, value in (update.get("$push") or {}).items():
            cur = self._get_dotted(doc, key)
            if not isinstance(cur, list):
                self._set_dotted(doc, key, [copy.deepcopy(value)])
            else:
                cur.append(copy.deepcopy(value))

    @staticmethod
    def _unset_dotted(doc: Dict[str, Any], key: str) -> None:
        """``$unset`` ile dotted path sil — parent'tan anahtarı kaldır.

        MongoDB'ye uygun olarak: ``"a.b.c"`` için ``a.b.c`` varsa siler,
        yoksa no-op. Ara dict boşalırsa onu da silmez (Mongo da bırakır).
        """
        parts = key.split(".")
        cur: Any = doc
        for part in parts[:-1]:
            if not isinstance(cur, dict) or part not in cur:
                return
            cur = cur[part]
        if isinstance(cur, dict):
            cur.pop(parts[-1], None)

    def find(self, query: Dict[str, Any]):
        items = [
            copy.deepcopy(doc)
            for doc in self.docs.values()
            if self.matches(doc, query)
        ]
        items.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return FakeCursor(items)


class FakeUsersCollection:
    """``db.users`` için no-op double (owner_name test kapsamında değil)."""

    async def find_one(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        return None


class FakeDatabase:
    def __init__(self, audits: FakeAuditCollection) -> None:
        self.audits = audits
        self.users = FakeUsersCollection()
        # B6/B7 — log_action mandatory + ibraz persistence için mock.
        self.audit_log = MagicMock()
        self.audit_log.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        self.audit_log.find_one = AsyncMock(return_value=None)
        self.audit_ibraz = MagicMock()
        self.audit_ibraz.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        self.audit_ibraz.find_one = AsyncMock(return_value=None)


class FakeCursor:
    """``db.audits.find(...)`` için async iterable destekli cursor."""

    def __init__(self, items: List[Dict[str, Any]]) -> None:
        self._items = items

    def sort(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        async def gen():
            for item in self._items:
                yield item

        return gen()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def api_client(monkeypatch):
    """Default: USER olarak auth. Test override eder."""
    collection = FakeAuditCollection()
    monkeypatch.setattr(server, "db", FakeDatabase(collection))
    app = FastAPI()
    app.include_router(server.api_router)
    app.dependency_overrides[server.get_current_user] = lambda: USER
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client, collection, app


def _make_audit(
    user_id: str = USER["id"],
    answers: Optional[Dict[str, str]] = None,
    version: int = 0,
    updated_at: str = "2026-07-01T00:00:00+00:00",
) -> Dict[str, Any]:
    """Snapshot'lı audit üret (HAYIR/EVET/NA answers ile)."""
    return sample_audit_doc(
        user_id=user_id,
        answers=answers or {},
        version=version,
        updated_at=updated_at,
    )


# ---------------------------------------------------------------------------
# Auth kontratı
# ---------------------------------------------------------------------------
def test_unauthenticated_get_returns_401():
    """Kimlik doğrulama yoksa GET /dofs → 401."""
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(server.api_router)
    # dependency_overrides YOK
    with TestClient(app) as client:
        response = client.get("/api/dofs")
    assert response.status_code == 401


def test_unauthenticated_put_returns_401():
    """Kimlik doğrulama yoksa PUT /dofs/{id}/{qid} → 401."""
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(server.api_router)
    with TestClient(app) as client:
        response = client.put(
            "/api/dofs/65b0a7b5b5b5b5b5b5b5b5b5/1",
            json={"status": "AÇIK", "notes": ""},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/dofs — scope + default + filtre
# ---------------------------------------------------------------------------
def test_normal_user_sees_only_own_dofs(api_client):
    client, collection, _ = api_client
    audit_a = _make_audit(user_id=USER["id"], answers={"1": "HAYIR", "2": "EVET"})
    audit_b = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit_a["_id"]] = audit_a
    collection.docs[audit_b["_id"]] = audit_b

    response = client.get("/api/dofs")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["audit_id"] == str(audit_a["_id"])
    assert items[0]["question_id"] == 1
    assert items[0]["audit_user_id"] == USER["id"]


def test_admin_sees_all_dofs(api_client):
    client, collection, app = api_client
    app.dependency_overrides[server.get_current_user] = lambda: ADMIN
    audit_a = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    audit_b = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit_a["_id"]] = audit_a
    collection.docs[audit_b["_id"]] = audit_b

    response = client.get("/api/dofs")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    user_ids = {item["audit_user_id"] for item in items}
    assert user_ids == {USER["id"], OTHER_USER["id"]}


def test_default_status_is_acik_with_empty_notes(api_client):
    """DÖF state yok → default AÇIK + boş notes + null updated_at/by."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.get("/api/dofs")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert item["status"] == "AÇIK"
    assert item["notes"] == ""
    assert item["updated_at"] is None
    assert item["updated_by"] is None


def test_evet_cevapli_soru_does_not_appear(api_client):
    """EVET cevaplı sorular DÖF listesinde yer almaz."""
    client, collection, _ = api_client
    audit = _make_audit(
        user_id=USER["id"], answers={"1": "EVET", "2": "HAYIR"}
    )
    collection.docs[audit["_id"]] = audit

    response = client.get("/api/dofs")
    items = response.json()
    assert len(items) == 1
    assert items[0]["question_id"] == 2


def test_na_cevapli_soru_does_not_appear(api_client):
    """NA cevaplı sorular DÖF listesinde yer almaz."""
    client, collection, _ = api_client
    audit = _make_audit(
        user_id=USER["id"], answers={"1": "NA", "2": "HAYIR"}
    )
    collection.docs[audit["_id"]] = audit

    response = client.get("/api/dofs")
    items = response.json()
    assert len(items) == 1
    assert items[0]["question_id"] == 2


def test_get_dof_response_uses_canonical_english_keys(api_client):
    """OK-3: Legacy Turkish anahtarlar YOK; canonical İngilizce keys.

    Invariant: response tüm zorunlu canonical İngilizce alanları içermeli ve
    legacy Turkish alias'lar içermemelidir. Response, Baran branch'inin
    eklediği ek canonical alanları (resolution_note, resolved_at, resolved_by,
    photos, in_progress_at, due_date, created_at, photo_modify_count,
    timeline_logs) da içerebilir — bunlar product surface alanıdır.
    Strict equality contract front-end feature'ları kısıtladığı için subset
    kontrolü tercih edildi.
    """
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    # dof_details dolu (status, notes, updated_at, updated_by)
    audit["dof_details"] = {
        "1": {
            "status": "İŞLEMDE",
            "notes": "test",
            "updated_at": "2026-07-15T10:00:00+00:00",
            "updated_by": USER["id"],
        }
    }
    collection.docs[audit["_id"]] = audit

    response = client.get("/api/dofs")
    item = response.json()[0]
    required_canonical_keys = {
        "audit_id",
        "audit_user_id",
        "owner_name",
        "restaurant_name",
        "audit_date",
        "question_id",
        "question_no",
        "category",
        "question",
        "responsible",
        "probability",
        "severity",
        "risk_score",
        "risk_level",
        "document_risk_level",
        "deadline",
        "legal_basis",
        "corrective_action",
        "status",
        "notes",
        "updated_at",
        "updated_by",
    }
    # Canonical İngilizce keys response içinde bulunmalı (subset check).
    # Yeni canonical alanlar response'a eklenebilir; bunlar product surface
    # alanıdır (resolution_note, resolved_at, resolved_by, photos,
    # in_progress_at, due_date, created_at, photo_modify_count, timeline_logs).
    assert required_canonical_keys.issubset(item.keys())
    # Legacy Turkish alias'lar response'ta OLMAMALI.
    for legacy in ("soru_no", "soru", "denetim_id", "kullanici_adi"):
        assert legacy not in item


# ---------------------------------------------------------------------------
# PUT /api/dofs/{audit_id}/{question_id} — scope + HAYIR gate
# ---------------------------------------------------------------------------
def test_other_users_dof_cannot_be_updated_returns_404(api_client):
    client, collection, _ = api_client
    audit_b = _make_audit(user_id=OTHER_USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit_b["_id"]] = audit_b

    response = client.put(
        f"/api/dofs/{audit_b['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "test"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Denetim bulunamadı"
    # No mutation on DB
    assert "dof_details" not in collection.docs[audit_b["_id"]]


def test_valid_status_and_notes_persist(api_client):
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "Tedarikçi değişimi başlatıldı"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["dof"]["status"] == "İŞLEMDE"
    assert payload["dof"]["notes"] == "Tedarikçi değişimi başlatıldı"
    assert payload["dof"]["question_id"] == 1
    assert payload["dof"]["audit_id"] == str(audit["_id"])

    # DB'ye nested yazıldı
    stored = collection.docs[audit["_id"]]
    assert stored["dof_details"]["1"]["status"] == "İŞLEMDE"
    assert stored["dof_details"]["1"]["notes"] == "Tedarikçi değişimi başlatıldı"

    # GET ile okundu
    response = client.get("/api/dofs")
    item = response.json()[0]
    assert item["status"] == "İŞLEMDE"
    assert item["notes"] == "Tedarikçi değişimi başlatıldı"


def test_put_on_non_hayir_returns_409(api_client):
    """OK-1: HAYIR olmayan soru PUT → 409 dof_answer_not_hayir."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "EVET"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "AÇIK", "notes": "test"},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "dof_answer_not_hayir"
    assert "HAYIR" in detail["message"]
    # No mutation
    assert "dof_details" not in collection.docs[audit["_id"]]


def test_put_with_unknown_question_id_returns_404(api_client):
    """Snapshot'ta var olmayan question_id → 404 (snapshot_id güncel değil)."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/999",
        json={"status": "AÇIK", "notes": ""},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Soru audit snapshot'ında bulunamadı"


def test_put_with_invalid_audit_objectid_returns_400(api_client):
    """Geçersiz ObjectId → 400 ``Geçersiz denetim ID`` (FastAPI değil, biz)."""
    client, _, _ = api_client
    response = client.put(
        "/api/dofs/not-a-valid-objectid/1",
        json={"status": "AÇIK", "notes": ""},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Geçersiz denetim ID"


def test_put_with_non_integer_question_id_returns_422(api_client):
    """``question_id`` int değilse FastAPI doğal 422 döner."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/abc",
        json={"status": "AÇIK", "notes": ""},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Pydantic input validation
# ---------------------------------------------------------------------------
def test_invalid_status_returns_422(api_client):
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "BİTTİ", "notes": ""},
    )
    assert response.status_code == 422


def test_notes_over_2000_chars_returns_422(api_client):
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "AÇIK", "notes": "x" * 2001},
    )
    assert response.status_code == 422


def test_kapatildi_with_empty_notes_returns_422(api_client):
    """KAPATILDI + trim-sonrası boş notes → 422 (model_validator)."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "KAPATILDI", "notes": "   "},
    )
    assert response.status_code == 422


def test_notes_are_trimmed_before_persist(api_client):
    """Notes trim uygulanır, DB'ye trim'li yazılır."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "  içerik  "},
    )
    assert response.status_code == 200
    stored = collection.docs[audit["_id"]]
    assert stored["dof_details"]["1"]["notes"] == "içerik"


def test_kapatildi_with_non_empty_notes_succeeds(api_client):
    """KAPATILDI + not dolu → 200."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "KAPATILDI", "notes": "Tamamlandı, doğrulandı"},
    )
    assert response.status_code == 200
    payload = response.json()["dof"]
    assert payload["status"] == "KAPATILDI"
    assert payload["notes"] == "Tamamlandı, doğrulandı"


# ---------------------------------------------------------------------------
# Audit bütünlüğü (OK-2)
# ---------------------------------------------------------------------------
def test_updated_at_and_updated_by_persisted(api_client):
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "Test"},
    )
    assert response.status_code == 200
    payload = response.json()["dof"]
    assert payload["updated_at"] is not None
    assert payload["updated_at"] != ""
    assert payload["updated_by"] == USER["id"]

    stored = collection.docs[audit["_id"]]
    assert stored["dof_details"]["1"]["updated_at"] == payload["updated_at"]
    assert stored["dof_details"]["1"]["updated_by"] == USER["id"]


def test_dof_update_does_not_increment_audit_version(api_client):
    """OK-2: Audit version sabit kalır."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"}, version=2)
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "Test"},
    )
    assert response.status_code == 200
    stored = collection.docs[audit["_id"]]
    assert stored["version"] == 2


def test_dof_write_does_not_touch_audit_updated_at(api_client):
    """OK-2: DÖF PUT audit ``updated_at`` alanına dokunmaz."""
    client, collection, _ = api_client
    audit = _make_audit(
        user_id=USER["id"],
        answers={"1": "HAYIR"},
        updated_at="2026-07-01T00:00:00+00:00",
    )
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "Test"},
    )
    assert response.status_code == 200
    stored = collection.docs[audit["_id"]]
    assert stored["updated_at"] == "2026-07-01T00:00:00+00:00"


def test_dof_write_does_not_touch_audit_created_at(api_client):
    """OK-2: DÖF PUT audit ``created_at`` alanına dokunmaz (ekstra koruma)."""
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit
    initial_created_at = audit["created_at"]

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "Test"},
    )
    assert response.status_code == 200
    stored = collection.docs[audit["_id"]]
    assert stored["created_at"] == initial_created_at


# ---------------------------------------------------------------------------
# BUG: DÖF kapatma 500 (ConflictingUpdateOperators)
# ---------------------------------------------------------------------------
def test_kapatildi_after_previous_update_does_not_500(api_client):
    """BUG: DÖF daha önce İŞLEMDE'ye alındıktan sonra KAPATILDI yapılırken
    server 500 dönüyordu.

    Kök neden: ``backend.server.update_dof`` atomic update'inde
    ``$set: {"dof_details.<qid>": <whole_subdoc>}`` + ``$push:
    {"dof_details.<qid>.timeline_logs": <entry>}`` aynı parent path'i
    hedefliyordu. ``dof_details.<qid>`` doc'ta zaten varsa (önceki PUT'tan)
    MongoDB ``ConflictingUpdateOperators`` (code 40) → ``pymongo.errors.
    OperationFailure`` → FastAPI 500 fırlatıyordu.

    Bu test: önce İŞLEMDE PUT başarılı (200), sonra KAPATILDI PUT başarılı
    (200), sonra dof_details.3 altında status/resolved_at/resolved_by/
    timeline_logs doğru persist edilmiş.
    """
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    # Önce İŞLEMDE'ye al (Bu PUT, dof_details.1 sub-doc'unu oluşturur +
    # timeline_logs listesi başlatır).
    r1 = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "Çözüm başlatıldı"},
    )
    assert r1.status_code == 200

    # Şimdi aynı DÖF'ü KAPATILDI'ya geçir. ESKİ KOD ile bu 500 dönerdi.
    r2 = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={
            "status": "KAPATILDI",
            "notes": "Saha düzeltme kanıt fotoğrafı ve fiziksel önlemler yerinde incelendi.",
            "resolution_note": "Saha düzeltme kanıt fotoğrafı ve fiziksel önlemler yerinde incelendi.",
        },
    )
    assert r2.status_code == 200, f"Beklenen 200, gelen {r2.status_code}: {r2.text}"

    payload = r2.json()["dof"]
    assert payload["status"] == "KAPATILDI"
    assert payload["notes"].startswith("Saha düzeltme kanıt fotoğrafı")
    assert payload["updated_by"] == USER["id"]

    stored = collection.docs[audit["_id"]]["dof_details"]["1"]

    # Server-controlled closure fields
    assert stored["status"] == "KAPATILDI"
    assert stored["resolved_at"] is not None
    assert stored["resolved_at"] != ""
    assert stored["resolved_by"] == USER["name"], (
        "resolved_by server-controlled must be authenticated user identity, "
        f"got {stored['resolved_by']!r}"
    )

    # resolution_note, persisted
    assert stored["resolution_note"].startswith("Saha düzeltme kanıt fotoğrafı")

    # Timeline: önce İŞLEMDE, sonra KAPATILDI → en az 2 log
    logs = stored["timeline_logs"]
    assert isinstance(logs, list)
    assert len(logs) >= 2, f"timeline_logs 2+ entry beklenir, got {len(logs)}"

    # İlk log İŞLEMDE ile başladı, son log KAPATILDI ile başladı
    assert ("İŞLEMDE" in logs[0]["action"]) or ("Düzeltme" in logs[0]["action"])
    assert "KAPATILDI" in logs[-1]["action"] or "Onay" in logs[-1]["action"]


def test_kapatildi_persists_server_timestamp_not_client(api_client):
    """Server-controlled ``resolved_at`` invariant: client hiçbir payload
    alanında ``resolved_at`` gönderemez; Pydantic ``DofUpdateInput`` reddi
    gereksiz (``extra`` default ignore zaten düşürür). Bu test: ``resolved_at``
    response + DB'de server'ın oluşturduğu ISO timestamp'tir; client
    göndermiş olsa bile client value değil server value yazılmıştır.
    """
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    response = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "KAPATILDI", "notes": "Saha kontrolü tamamlandı ve doğrulandı"},
    )
    assert response.status_code == 200

    stored = collection.docs[audit["_id"]]["dof_details"]["1"]
    resolved_at = stored["resolved_at"]
    assert resolved_at is not None

    # ``datetime.now(timezone.utc).isoformat()`` ISO 8601 UTC üretir;
    # server timestamp ``YYYY-MM-DDTHH:MM:SS...`` şeklinde olmalı.
    # (Client herhangi bir formatta göndermiş olsa bile döndürülen
    # server-controlled alan; client değeri Pydantic ignore nedeniyle
    # sessizce düşerdi.)
    from datetime import datetime as _dt, timezone as _tz

    parsed = _dt.fromisoformat(resolved_at)
    # Tarih saat delta'sı çok küçük olmalı (saniyeler içinde)
    now = _dt.now(_tz.utc)
    delta = abs((now - parsed).total_seconds())
    assert delta < 60, f"resolved_at sunucudan değilmiş gibi (>60s delta): {delta}s"


def test_reopen_dof_unsets_resolved_at(api_client):
    """Reopen invariant: KAPATILDI'dan AÇIK'a dönünce ``resolved_at`` ve
    ``resolved_by`` ``$unset`` ile temizlenir. Aksi halde eski kapanış
    bilgisi UI'da görünürdü.
    """
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    # Önce KAPATILDI
    r_close = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "KAPATILDI", "notes": "İlk kapanış: önlemler yerinde doğrulandı"},
    )
    assert r_close.status_code == 200
    closed = collection.docs[audit["_id"]]["dof_details"]["1"]
    assert closed.get("resolved_at") is not None
    assert closed.get("resolved_by") is not None

    # Şimdi AÇIK'a geri aç
    r_open = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "AÇIK", "notes": "Yeniden açıldı"},
    )
    assert r_open.status_code == 200
    reopened = collection.docs[audit["_id"]]["dof_details"]["1"]
    assert reopened["status"] == "AÇIK"
    assert "resolved_at" not in reopened or reopened.get("resolved_at") in (None, "")
    assert "resolved_by" not in reopened or reopened.get("resolved_by") in (None, "")


def test_islemde_to_kapatildi_does_not_create_mongo_conflict(api_client):
    """Ana bug test: İŞLEMDE → KAPATILDI geçişinde MongoDB
    ConflictingUpdateOperators guard'i tetiklenmemeli.

    ``FakeAuditCollection._apply_update`` MongoDB'ye uygun olarak
    ``$set`` parent path + aynı parent'ın çocuğuna başka operator →
    ``OperationFailure(code=40)`` raise eder. Server yeni kodu
    leaf-seviye ``$set`` + ``$push`` kullandığı için parent'ı
    değiştirmez; çocuğu ``$push`` yapar — conflict yok.
    """
    client, collection, _ = api_client
    audit = _make_audit(user_id=USER["id"], answers={"1": "HAYIR"})
    collection.docs[audit["_id"]] = audit

    # İlk PUT → İŞLEMDE
    r1 = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "İŞLEMDE", "notes": "başla"},
    )
    assert r1.status_code == 200

    # İkinci PUT → KAPATILDI; eski kod OperationFailure kaldırırdı,
    # yeni kod başarıyla persist eder.
    r2 = client.put(
        f"/api/dofs/{audit['_id']}/1",
        json={"status": "KAPATILDI", "notes": "Saha düzeltmesi doğrulandı ve kapatıldı"},
    )
    assert r2.status_code == 200
