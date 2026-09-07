import asyncio
import copy
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_pr2_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "pr2-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")

import server


USER = {"id": "user-a", "name": "User A", "role": "user"}
OTHER_USER = {"id": "user-b", "name": "User B", "role": "user"}


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, field, direction):
        self.docs.sort(key=lambda doc: doc.get(field, ""), reverse=direction < 0)
        return self

    def __aiter__(self):
        async def iterate():
            for doc in self.docs:
                yield copy.deepcopy(doc)
        return iterate()


class FakeAuditCollection:
    def __init__(self, docs=None):
        self.docs = {doc["_id"]: copy.deepcopy(doc) for doc in docs or []}
        self.lock = asyncio.Lock()

    @staticmethod
    def matches(doc, query):
        for key, expected in query.items():
            if key == "$and":
                if not all(FakeAuditCollection.matches(doc, branch) for branch in expected):
                    return False
            elif key == "$or":
                if not any(FakeAuditCollection.matches(doc, branch) for branch in expected):
                    return False
            elif isinstance(expected, dict) and any(k.startswith("$") for k in expected):
                actual = doc.get(key)
                if "$exists" in expected and (actual is not None) != expected["$exists"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$gte" in expected and not (actual is not None and actual >= expected["$gte"]):
                    return False
                if "$lte" in expected and not (actual is not None and actual <= expected["$lte"]):
                    return False
            elif doc.get(key) != expected:
                return False
        return True

    async def insert_one(self, doc):
        oid = ObjectId()
        stored = copy.deepcopy(doc)
        stored["_id"] = oid
        self.docs[oid] = stored
        return SimpleNamespace(inserted_id=oid)

    def find(self, query):
        return FakeCursor([
            copy.deepcopy(doc) for doc in self.docs.values() if self.matches(doc, query)
        ])

    async def find_one(self, query, projection=None):
        for doc in self.docs.values():
            if self.matches(doc, query):
                if projection:
                    return {key: copy.deepcopy(doc[key]) for key, enabled in projection.items() if enabled and key in doc}
                return copy.deepcopy(doc)
        return None

    async def find_one_and_update(self, query, update, return_document=None):
        async with self.lock:
            for oid, doc in self.docs.items():
                if self.matches(doc, query):
                    for key, value in update.get("$set", {}).items():
                        doc[key] = copy.deepcopy(value)
                    for key, value in update.get("$inc", {}).items():
                        doc[key] = doc.get(key, 0) + value
                    self.docs[oid] = doc
                    await asyncio.sleep(0)
                    return copy.deepcopy(doc)
        return None

    async def update_one(self, query, update, upsert=False, array_filters=None):
        """B4 — ``update_answers`` invalidation path FakeAuditCollection
        üzerinde ``update_one`` kullanıyor (DÖF'ü ``active=False`` yap).
        Mongo semantics: matched_count (modified_count) döndür."""
        matched = 0
        async with self.lock:
            for doc in self.docs.values():
                if self.matches(doc, query):
                    for key, value in update.get("$set", {}).items():
                        doc[key] = copy.deepcopy(value)
                    for key, value in update.get("$inc", {}).items():
                        doc[key] = doc.get(key, 0) + value
                    matched = 1
                    break
        return SimpleNamespace(matched_count=matched, modified_count=matched)


class FakeUsersCollection:
    async def find_one(self, query, projection=None):
        return None


class FakeDatabase:
    def __init__(self, audits):
        self.audits = audits
        self.users = FakeUsersCollection()
        # B6/B7 — log_action mandatory ve _persist_ibraz için mock.
        self.audit_log = MagicMock()
        self.audit_log.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        self.audit_log.find_one = AsyncMock(return_value=None)
        self.audit_ibraz = MagicMock()
        self.audit_ibraz.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        self.audit_ibraz.find_one = AsyncMock(return_value=None)


def audit_doc(version=0, answers=None, user_id=USER["id"], include_version=True):
    doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "restaurant_name": "Test Restoran",
        "address": "Adres",
        "audit_date": "2026-07-23",
        "denetci": "User A",
        "answers": answers or {},
        "created_at": "2026-07-23T10:00:00+00:00",
        "updated_at": "2026-07-23T10:00:00+00:00",
    }
    if include_version:
        doc["version"] = version
    return doc


@pytest.fixture
def api_client(monkeypatch):
    collection = FakeAuditCollection()
    monkeypatch.setattr(server, "db", FakeDatabase(collection))
    # S18 — create_audit default template ister (TEMPLATES_CACHE'ten).
    # Test ortamında minimal bir default template sağla.
    monkeypatch.setattr(server, "TEMPLATES_CACHE", {
        "default": {
            "code": "default",
            "name": "Default Template",
            "version": 1,
            "is_default": True,
            "questions": [],
        }
    })
    app = FastAPI()
    app.include_router(server.api_router)
    app.dependency_overrides[server.get_current_user] = lambda: USER
    with TestClient(app) as client:
        yield client, collection, app


def test_new_audit_returns_version_zero(api_client):
    client, collection, app = api_client
    response = client.post("/api/audits", json={"restaurant_name": "Yeni"})
    assert response.status_code == 200
    assert response.json()["version"] == 0
    assert next(iter(collection.docs.values()))["version"] == 0


def test_legacy_audit_read_and_list_expose_version_zero(api_client):
    client, collection, app = api_client
    doc = audit_doc(include_version=False)
    collection.docs[doc["_id"]] = doc
    get_response = client.get(f"/api/audits/{doc['_id']}")
    list_response = client.get("/api/audits")
    assert get_response.json()["version"] == 0
    assert list_response.json()[0]["version"] == 0


def test_valid_updates_increment_versions(api_client):
    client, collection, app = api_client
    doc = audit_doc()
    collection.docs[doc["_id"]] = doc
    first = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 0, "answers": {"1": "EVET"}})
    second = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 1, "answers": {"1": "HAYIR"}})
    assert first.status_code == 200
    assert first.json()["version"] == 1
    assert second.status_code == 200
    assert second.json()["version"] == 2
    assert second.json()["summary"]["counts"]["HAYIR"] == 1


def test_stale_request_returns_409_without_mutation(api_client):
    client, collection, app = api_client
    doc = audit_doc(version=1, answers={"1": "EVET"})
    collection.docs[doc["_id"]] = doc
    before = copy.deepcopy(doc)
    response = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 0, "answers": {"1": "HAYIR"}})
    after = collection.docs[doc["_id"]]
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "audit_version_conflict"
    assert after["answers"] == before["answers"]
    assert after["version"] == before["version"]
    assert after["updated_at"] == before["updated_at"]


@pytest.mark.parametrize("payload", [
    {"expected_version": 0, "answers": {"1": "evet"}},
    {"expected_version": 0, "answers": {"1": "EVET", "bad": "HAYIR"}},
    {"expected_version": -1, "answers": {"1": "EVET"}},
    {"expected_version": 0, "answers": {}},
])
def test_invalid_payloads_return_422_atomically(api_client, payload):
    client, collection, app = api_client
    doc = audit_doc(answers={"2": "NA"})
    collection.docs[doc["_id"]] = doc
    before = copy.deepcopy(doc)
    response = client.put(f"/api/audits/{doc['_id']}/answers", json=payload)
    assert response.status_code == 422
    assert collection.docs[doc["_id"]] == before


def test_unknown_question_id_rejected_atomically_400(api_client):
    """Snapshotta var olmayan soru id'si 400 döner (Pydantic 422 DEĞİL).

    ``AnswersBulkInput`` yalnız format/tip/cevap-değeri validation'ı yapar
    (422); soru id'sinin audit'in snapshot'ında bulunması endpoint içinde
    context-aware kontrol edilir ve 400 döner. Bu, ``risk_overrides`` bilinmeyen
    anahtar davranışıyla tutarlıdır. Atomiklik yine de korunur.
    """
    client, collection, app = api_client
    doc = audit_doc(answers={"2": "NA"})
    collection.docs[doc["_id"]] = doc
    before = copy.deepcopy(doc)
    response = client.put(
        f"/api/audits/{doc['_id']}/answers",
        json={"expected_version": 0, "answers": {"999999": "EVET"}},
    )
    assert response.status_code == 400
    assert collection.docs[doc["_id"]] == before


def test_mixed_valid_and_invalid_values_are_rejected(api_client):
    client, collection, app = api_client
    doc = audit_doc(answers={"3": "NA"})
    collection.docs[doc["_id"]] = doc
    response = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 0, "answers": {"1": "EVET", "2": "INVALID"}})
    assert response.status_code == 422
    assert collection.docs[doc["_id"]]["answers"] == {"3": "NA"}
    assert collection.docs[doc["_id"]]["version"] == 0


@pytest.mark.parametrize("expected_version", [1.0, True, "1", None])
def test_non_integer_expected_version_returns_422(api_client, expected_version):
    client, collection, app = api_client
    doc = audit_doc(answers={"2": "NA"})
    collection.docs[doc["_id"]] = doc
    before = copy.deepcopy(doc)
    response = client.put(
        f"/api/audits/{doc['_id']}/answers",
        json={"expected_version": expected_version, "answers": {"1": "EVET"}},
    )
    assert response.status_code == 422
    assert collection.docs[doc["_id"]] == before


def test_metadata_update_uses_version_contract(api_client):
    client, collection, app = api_client
    doc = audit_doc()
    collection.docs[doc["_id"]] = doc
    payload = {"expected_version": 0, "restaurant_name": "Güncel", "address": "A", "audit_date": "2026-07-24", "denetci": "D"}
    success = client.patch(f"/api/audits/{doc['_id']}", json=payload)
    stale = client.patch(f"/api/audits/{doc['_id']}", json=payload)
    assert success.status_code == 200
    assert success.json()["version"] == 1
    assert stale.status_code == 409
    assert collection.docs[doc["_id"]]["version"] == 1


def test_user_isolation_is_preserved(api_client):
    client, collection, app = api_client
    doc = audit_doc(user_id=OTHER_USER["id"])
    collection.docs[doc["_id"]] = doc
    response = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 0, "answers": {"1": "EVET"}})
    assert response.status_code == 404
    assert collection.docs[doc["_id"]]["answers"] == {}
    assert collection.docs[doc["_id"]]["version"] == 0


def test_legacy_missing_version_can_be_atomically_updated_once(api_client):
    client, collection, app = api_client
    doc = audit_doc(include_version=False)
    collection.docs[doc["_id"]] = doc
    first = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 0, "answers": {"1": "EVET"}})
    second = client.put(f"/api/audits/{doc['_id']}/answers", json={"expected_version": 0, "answers": {"1": "HAYIR"}})
    assert first.status_code == 200
    assert first.json()["version"] == 1
    assert second.status_code == 409
    assert collection.docs[doc["_id"]]["answers"] == {"1": "EVET"}
    assert collection.docs[doc["_id"]]["version"] == 1


def test_two_concurrent_updates_same_version_have_one_winner(monkeypatch):
    doc = audit_doc()
    collection = FakeAuditCollection([doc])
    monkeypatch.setattr(server, "db", FakeDatabase(collection))

    async def run_update(answer):
        try:
            result = await server.update_answers(
                str(doc["_id"]),
                server.AnswersBulkInput(expected_version=0, answers={"1": answer}),
                USER,
            )
            return 200, result
        except HTTPException as exc:
            return exc.status_code, exc.detail

    async def run_both():
        return await asyncio.gather(run_update("EVET"), run_update("HAYIR"))

    first, second = asyncio.run(run_both())
    statuses = sorted([first[0], second[0]])
    assert statuses == [200, 409]
    winner = first[1] if first[0] == 200 else second[1]
    stored = collection.docs[doc["_id"]]
    assert stored["answers"] == winner["answers"]
    assert stored["version"] == 1
