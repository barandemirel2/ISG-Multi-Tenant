"""Question-number backward-compatibility contract for DÖF responses.

PR2 review concern: ``question_no`` previously held the **string**
``"1.3"`` after the category-based numbering refactor. That silently
breaks the existing API contract — legacy consumers pin ``question_no``
to a numeric ``int`` and would crash or sort incorrectly.

This suite pins the **dual-field** contract:

* ``question_no`` (legacy, must remain): ``int``
* ``category_question_no`` (new, opt-in): ``str`` of shape ``"<cat>.<idx>"``

And the helper-level invariants:

* ``_get_category_question_no`` produces well-formed ``"<cat>.<idx>"``
  output for first/last question and across multiple categories.
* The DÖF builder round-trips a HAYIR answer into a single item that
  carries BOTH fields with the right types.
* Legacy / sparse question data (no ``no`` field) does NOT crash the
  endpoint and still surfaces ``category_question_no``.
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Minimum env so server.py can be imported (PR2 pattern).
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_qn_contract_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "qn-contract-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")

import server


# ---------------------------------------------------------------------------
# A. _get_category_question_no — pure helper, no DB.
# ---------------------------------------------------------------------------
class TestGetCategoryQuestionNo:
    def test_first_question_first_category_returns_1_1(self):
        q = {"id": 1, "no": 1, "category": "C1"}
        questions = [
            {"id": 1, "no": 1, "category": "C1"},
            {"id": 2, "no": 2, "category": "C1"},
        ]
        result = server._get_category_question_no(q, questions)
        assert result == "1.1"
        assert isinstance(result, str)

    def test_third_question_first_category_returns_1_3(self):
        q = {"id": 3, "no": 3, "category": "C1"}
        questions = [
            {"id": 1, "no": 1, "category": "C1"},
            {"id": 2, "no": 2, "category": "C1"},
            {"id": 3, "no": 3, "category": "C1"},
        ]
        assert server._get_category_question_no(q, questions) == "1.3"

    def test_first_question_of_second_category_returns_2_1(self):
        q = {"id": 4, "no": 4, "category": "C2"}
        questions = [
            {"id": 1, "no": 1, "category": "C1"},
            {"id": 2, "no": 2, "category": "C1"},
            {"id": 3, "no": 3, "category": "C1"},
            {"id": 4, "no": 4, "category": "C2"},
        ]
        assert server._get_category_question_no(q, questions) == "2.1"

    def test_handles_kategori_tr_al_field(self):
        # Turkish ``kategori`` alias must also drive the result.
        q = {"id": 5, "no": 5, "kategori": "Hijyen"}
        questions = [
            {"id": 4, "no": 4, "kategori": "Hijyen"},
            {"id": 5, "no": 5, "kategori": "Hijyen"},
        ]
        assert server._get_category_question_no(q, questions) == "1.2"

    def test_missing_category_falls_back_to_index_1(self):
        # Question declares a category that isn't in the list — safe
        # fallback to ``1.<idx>``.
        q = {"id": 1, "no": 1, "category": "Ghost"}
        questions = [{"id": 1, "no": 1, "category": "Ghost"}]
        assert server._get_category_question_no(q, questions) == "1.1"

    def test_returns_string_with_dot_separator(self):
        q = {"id": 1, "no": 1, "category": "C1"}
        questions = [{"id": 1, "no": 1, "category": "C1"}]
        result = server._get_category_question_no(q, questions)
        assert "." in result
        head, tail = result.split(".", 1)
        assert head.isdigit()
        assert tail.isdigit()

    def test_match_by_id_not_index(self):
        # Out-of-order listing: the index within the category list
        # is by ``id`` match, not by list position.
        q = {"id": 7, "no": 7, "category": "C1"}
        questions = [
            {"id": 9, "no": 9, "category": "C1"},  # not the target
            {"id": 7, "no": 7, "category": "C1"},  # target: in-cat idx 2
        ]
        assert server._get_category_question_no(q, questions) == "1.2"


# ---------------------------------------------------------------------------
# B. End-to-end /api/dofs — ensure the dual-field contract holds in the
#    real response builder (covers the wiring, not just the helper).
# ---------------------------------------------------------------------------
import asyncio
import copy
from typing import Any, Dict, List, Optional

import pytest
from bson import ObjectId
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock
from pymongo.errors import OperationFailure


class FakeAuditCollection_QN:
    """Stateful dotted-key Mongo double for the question_no contract."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _get_dotted(doc, key):
        cur = doc
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def matches(self, doc, query):
        for key, expected in query.items():
            if key == "$and":
                if not all(self.matches(doc, b) for b in expected):
                    return False
            elif key == "$or":
                if not any(self.matches(doc, b) for b in expected):
                    return False
            elif isinstance(expected, dict) and any(k.startswith("$") for k in expected):
                actual = self._get_dotted(doc, key)
                if "$exists" in expected:
                    if (actual is not None) != expected["$exists"]:
                        return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            else:
                actual = self._get_dotted(doc, key)
                if actual != expected:
                    return False
        return True

    async def find_one(self, query, projection=None):
        for doc in self.docs.values():
            if self.matches(doc, query):
                return copy.deepcopy(doc)
        return None

    async def find_one_and_update(self, query, update, return_document=None):
        for oid, doc in self.docs.items():
            if self.matches(doc, query):
                # No-op for read-only contract tests.
                return copy.deepcopy(doc)
        return None

    def find(self, query):
        items = [
            copy.deepcopy(doc)
            for doc in self.docs.values()
            if self.matches(doc, query)
        ]
        items.sort(key=lambda d: d.get("created_at", ""), reverse=True)

        class _Cursor:
            def __init__(self, items):
                self._items = items

            def sort(self, *a, **k):
                return self

            def __aiter__(self):
                async def gen():
                    for it in self._items:
                        yield it
                return gen()

        return _Cursor(items)


class FakeDB_QN:
    def __init__(self, audits):
        self.audits = audits
        self.users = MagicMock()
        self.users.find_one = AsyncMock(return_value=None)
        self.audit_log = MagicMock()
        self.audit_log.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="x")
        )
        self.audit_ibraz = MagicMock()
        self.audit_ibraz.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="x")
        )


USER_QN = {"id": "u-qn", "name": "User QN", "role": "user"}


def _audit_qn(user_id, answers, template):
    return {
        "_id": ObjectId(),
        "user_id": user_id,
        "restaurant_name": "Restoran QN",
        "audit_date": "2026-08-15",
        "denetci": "Denetçi QN",
        "answers": answers,
        "risk_overrides": {},
        "version": 0,
        "created_at": "2026-08-15T00:00:00+00:00",
        "updated_at": "2026-08-15T00:00:00+00:00",
        "template_snapshot": {
            "template_code": template["code"],
            "template_name": template["name"],
            "template_version": template["version"],
            "snapshot_at": "2026-08-15T00:00:00+00:00",
            "questions": list(template["questions"]),
        },
    }


@pytest.fixture
def api_client_qn(monkeypatch):
    collection = FakeAuditCollection_QN()
    monkeypatch.setattr(server, "db", FakeDB_QN(collection))
    app = FastAPI()
    app.include_router(server.api_router)
    app.dependency_overrides[server.get_current_user] = lambda: USER_QN
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client, collection


class TestQuestionNumberContract:
    def test_dof_item_legacy_question_no_is_int(self, api_client_qn):
        """Legacy ``question_no`` MUST be a numeric ``int``."""
        from tests._phase_2a_helpers import sample_template_doc

        client, collection = api_client_qn
        template = sample_template_doc()  # 84 questions, 9 categories
        # q id=3 is HAYIR — we'll pin both question_no and category_question_no
        audit = _audit_qn(USER_QN["id"], {"3": "HAYIR"}, template)
        collection.docs[audit["_id"]] = audit

        response = client.get("/api/dofs")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        item = items[0]
        assert isinstance(item["question_no"], int), (
            f"question_no must be int (legacy); got {type(item['question_no']).__name__}"
        )
        assert item["question_no"] == 3

    def test_dof_item_exposes_category_question_no_as_string(self, api_client_qn):
        """``category_question_no`` MUST be a string of shape ``"<n>.<m>"``."""
        from tests._phase_2a_helpers import sample_questions, sample_template_doc

        client, collection = api_client_qn
        template = sample_template_doc()
        # q id=1 is HAYIR — first question of the first category → "1.1".
        audit = _audit_qn(USER_QN["id"], {"1": "HAYIR"}, template)
        collection.docs[audit["_id"]] = audit

        response = client.get("/api/dofs")
        items = response.json()
        item = items[0]
        assert "category_question_no" in item
        assert isinstance(item["category_question_no"], str)
        # First question of Cat1 → "1.1".
        assert item["category_question_no"] == "1.1"

    def test_both_fields_present_in_same_item(self, api_client_qn):
        """Both fields must coexist on the same item — opt-in vs legacy."""
        from tests._phase_2a_helpers import sample_template_doc

        client, collection = api_client_qn
        template = sample_template_doc()
        audit = _audit_qn(USER_QN["id"], {"1": "HAYIR"}, template)
        collection.docs[audit["_id"]] = audit

        response = client.get("/api/dofs")
        item = response.json()[0]
        # Required subset
        assert "question_no" in item
        assert "category_question_no" in item
        # Types pinned
        assert isinstance(item["question_no"], int)
        assert isinstance(item["category_question_no"], str)
        # Distinct fields (proves opt-in, not a rename)
        assert item["question_no"] != item["category_question_no"]

    def test_multiple_hayir_answers_each_carry_both_fields(self, api_client_qn):
        """Two HAYIR answers → two items, each with both fields."""
        from tests._phase_2a_helpers import sample_template_doc

        client, collection = api_client_qn
        template = sample_template_doc()
        # q1 is in Cat1 (index 1.1) and q3 is in Cat3 (index 3.1). This
        # gives us two items across different categories to confirm
        # ``category_question_no`` rolls over per-category correctly.
        audit = _audit_qn(
            USER_QN["id"], {"1": "HAYIR", "3": "HAYIR"}, template
        )
        collection.docs[audit["_id"]] = audit

        response = client.get("/api/dofs")
        items = response.json()
        by_qid = {it["question_id"]: it for it in items}
        assert set(by_qid.keys()) == {1, 3}

        for qid, item in by_qid.items():
            assert isinstance(item["question_no"], int)
            assert isinstance(item["category_question_no"], str)
            assert "." in item["category_question_no"]

        # Distinct category_question_no values across categories.
        assert by_qid[1]["category_question_no"] != by_qid[3]["category_question_no"]
        # q1 (Cat1 first) → "1.1".
        assert by_qid[1]["category_question_no"] == "1.1"
        # q3 (Cat3 first) → "3.1".
        assert by_qid[3]["category_question_no"] == "3.1"

    def test_legacy_question_without_no_field_does_not_crash_endpoint(
        self, api_client_qn
    ):
        """Sparse / legacy question data must not crash ``_build_dof_items``.

        Production guards: ``q.get("no") or q.get("id") or 0`` →
        ``int(...)``. If ``no`` is missing, falls back to ``id``.
        """
        client, collection = api_client_qn
        template = {
            "code": "isg_v1_default",
            "name": "ABCD Tech Solutions İSG Denetim ve Risk Analizi",
            "version": 1,
            "is_default": True,
            "questions": [
                {
                    "id": 7,
                    # intentionally NO ``no`` field → legacy fallback path
                    "category": "Legacy Cat",
                    "area": "Legacy",
                    "question": "Legacy question",
                    "responsible": "r1",
                    "default_probability": 1,
                    "default_severity": 1,
                    "default_risk_score": 1,
                    "default_risk_level": "Kabul Edilebilir",
                    "document_risk_level": "Kabul Edilebilir",
                    "deadline": "3 Ay",
                    "legal_basis": [],
                    "corrective_action": "",
                }
            ],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        audit = _audit_qn(USER_QN["id"], {"7": "HAYIR"}, template)
        collection.docs[audit["_id"]] = audit

        response = client.get("/api/dofs")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        item = items[0]
        # Falls back to ``id`` and remains int.
        assert isinstance(item["question_no"], int)
        assert item["question_no"] == 7
        # ``category_question_no`` is still produced.
        assert isinstance(item["category_question_no"], str)
        assert "." in item["category_question_no"]

    def test_legacy_question_with_only_id_field(self, api_client_qn):
        """When only ``id`` exists, ``question_no`` reflects it."""
        client, collection = api_client_qn
        template = {
            "code": "isg_v1_default",
            "name": "ABCD Tech Solutions İSG Denetim ve Risk Analizi",
            "version": 1,
            "is_default": True,
            "questions": [
                {
                    "id": 42,
                    "category": "Only Id Cat",
                    "area": "Only Id Area",
                    "question": "Id-only question",
                    "responsible": "r1",
                    "default_probability": 1,
                    "default_severity": 1,
                    "default_risk_score": 1,
                    "default_risk_level": "Kabul Edilebilir",
                    "document_risk_level": "Kabul Edilebilir",
                    "deadline": "3 Ay",
                    "legal_basis": [],
                    "corrective_action": "",
                }
            ],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        audit = _audit_qn(USER_QN["id"], {"42": "HAYIR"}, template)
        collection.docs[audit["_id"]] = audit

        response = client.get("/api/dofs")
        items = response.json()
        item = items[0]
        assert item["question_no"] == 42
        assert isinstance(item["question_no"], int)
