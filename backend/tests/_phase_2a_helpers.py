"""Aşama 2A test ortak helper'ları.

Bu modül pytest tarafından ``_`` prefix'i nedeniyle **toplanmaz** (yalnız
helper). Diğer ``test_phase_2a_*`` modülleri buradan DB-mock factory'lerini
ve ortak ``AuditDoc`` üretici fonksiyonları import eder.

Tasarım kararları:

* ``AsyncMock`` / ``MagicMock`` üzerinde explicit olarak ``db.audits`` /
  ``db.templates`` collection attribute'ları tanımlanır; ``MagicMock``'ın
  "her attribute mock olur" semantiği burada yeterli ama açıkça
  tanımlamak test sözleşmesini netleştirir ve hatalı kullanımı önler.

* Cursor simülasyonu (``async for``) için ``aiter`` helper'ı kullanılır;
  test fixture'larında tüm template'leri / audit'leri iterable döner.

* Tüm helper'lar **stateful** bir ``FakeDB`` döner — test sırasında
  ``db.audits.docs`` sözlüğüne eklemek/silmek mümkün olur, böylece update
  senaryolarını sonradan ``find_one`` ile doğrulayabiliriz.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# server.py import edilebilmesi için minimum env (PR0 pattern'i). Bazı
# helper'lar ``server.db``'ye dokunmadan sadece saf pure-Python
# fonksiyonları test eder; ama ``AnswersBulkInput`` gibi sınıflar
# server.py'nin yüklenmesini gerektirir.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "risk_analiz_phase_2a_tests")
os.environ.setdefault("JWT_SECRET", "x" * 48)
os.environ.setdefault("ADMIN_EMAIL", "phase-2a-tests@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "placeholder-for-tests-not-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")


# ---------------------------------------------------------------------------
# Seed data factory
# ---------------------------------------------------------------------------
def sample_questions(minimal: bool = False) -> List[Dict[str, Any]]:
    """Testlerde kullanılacak 84 soruluk seed (server.py seed'inden bağımsız).

    ``minimal=True`` → yalnız 3 soru (hız testleri için).
    ``minimal=False`` → 84 soru (default Phase 2A test davranışı).
    """
    if minimal:
        return [
            {
                "id": 1, "no": 1, "category": "C1", "area": "A1",
                "question": "q1", "responsible": "r1",
                "default_probability": 1, "default_severity": 1,
                "default_risk_score": 1, "default_risk_level": "Kabul Edilebilir",
                "document_risk_level": "Kabul Edilebilir",
                "deadline": "d1", "legal_basis": ["l1"], "corrective_action": "c1",
            },
            {
                "id": 2, "no": 2, "category": "C1", "area": "A1",
                "question": "q2", "responsible": "r1",
                "default_probability": 3, "default_severity": 4,
                "default_risk_score": 12, "default_risk_level": "Dikkate Değer",
                "document_risk_level": "Dikkate Değer",
                "deadline": "d2", "legal_basis": ["l2"], "corrective_action": "c2",
            },
            {
                "id": 3, "no": 3, "category": "C2", "area": "A2",
                "question": "q3", "responsible": "r2",
                "default_probability": 5, "default_severity": 5,
                "default_risk_score": 25, "default_risk_level": "Kabul Edilemez",
                "document_risk_level": "Kabul Edilemez",
                "deadline": "d3", "legal_basis": ["l3"], "corrective_action": "c3",
            },
        ]
    # Tam 84 soru üret — Phase 2A snapshot davranışı için
    out: List[Dict[str, Any]] = []
    categories = [f"Cat{i}" for i in range(1, 10)]  # 9 kategori
    for i in range(1, 85):
        cat = categories[(i - 1) % 9]
        prob = (i % 5) + 1
        sev = ((i * 3) % 5) + 1
        score = prob * sev
        if score <= 4:
            level = "Kabul Edilebilir"
        elif score <= 12:
            level = "Dikkate Değer"
        else:
            level = "Kabul Edilemez"
        out.append({
            "id": i, "no": i, "category": cat, "area": f"A{cat}",
            "question": f"question-{i}", "responsible": f"resp-{cat}",
            "default_probability": prob, "default_severity": sev,
            "default_risk_score": score, "default_risk_level": level,
            "document_risk_level": level,
            "deadline": "2026-12-31", "legal_basis": [f"law-{i}"],
            "corrective_action": f"action-{i}",
        })
    return out


def sample_template_doc(questions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """``db.templates`` üzerinde dönecek tipik bir template dökümanı."""
    qs = questions if questions is not None else sample_questions()
    return {
        "code": "isg_v1_default",
        "name": "ABCD Tech Solutions İSG Denetim ve Risk Analizi",
        "version": 1,
        "is_default": True,
        "questions": qs,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def snapshot_for(template: Dict[str, Any]) -> Dict[str, Any]:
    """Bir audit'in ``template_snapshot`` alanını üret (deep-copy yerine referans)."""
    return {
        "template_code": template["code"],
        "template_name": template["name"],
        "template_version": template["version"],
        "snapshot_at": "2026-01-01T00:00:00+00:00",
        "questions": list(template["questions"]),  # basit kopya
    }


def sample_audit_doc(
    user_id: str = "u-1",
    answers: Optional[Dict[str, str]] = None,
    risk_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    with_snapshot: bool = True,
    template: Optional[Dict[str, Any]] = None,
    version: int = 0,
    audit_id: Optional[str] = None,
    created_at: str = "2026-01-01T00:00:00+00:00",
    updated_at: str = "2026-01-01T00:00:00+00:00",
) -> Dict[str, Any]:
    """``db.audits`` üzerinde dönecek tipik audit dökümanı.

    ``user_id`` default ``"u-1"`` ile ``current_user["id"] = "u-1"`` test
    kullanımına hizalanır; aksi takdirde ``_scope_filter`` ile ``find_one``
    eşleşmeyerek 404 döner.

    ``audit_id`` default olarak **valid 24-char ObjectId hex** üretir;
    server.py ``ObjectId(audit_id)`` parse edeceği için normal string'ler
    "Geçersiz denetim ID" 400 hatasına yol açar.
    """
    tpl = template or sample_template_doc()
    doc: Dict[str, Any] = {
        # Mongo'da ``_id`` ObjectId tipindedir; server
        # ``ObjectId(audit_id)`` parse ederek ``find_one`` filtresi
        # yapar. String depolamak sahte eşleşmeye yol açar (test'te
        # 404 döner). Bu yüzden ``_id`` her zaman ``ObjectId``.
        "_id": ObjectId(audit_id) if audit_id else ObjectId(),
        "user_id": user_id,
        "restaurant_name": "Restoran Test",
        "address": "Adres Test",
        "audit_date": "2026-01-15",
        "denetci": "Test Denetçi",
        "answers": answers or {},
        "risk_overrides": risk_overrides if risk_overrides is not None else {},
        "version": version,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    if with_snapshot:
        doc["template_snapshot"] = snapshot_for(tpl)
    return doc


# ---------------------------------------------------------------------------
# FakeDB — stateful mock
# ---------------------------------------------------------------------------
class FakeCursor:
    """``db.templates.find({})`` için async iterable mock."""

    def __init__(self, items: List[Dict[str, Any]]):
        self._items = list(items)

    def sort(self, *_args, **_kwargs):
        # Sort zinciri için no-op (motor: db.templates.find().sort())
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        async def gen():
            for item in self._items:
                yield item
        return gen()


class FakeAuditsCollection:
    """``db.audits`` için stateful + AsyncMock-friendly collection.

    ``find_one`` ve ``find_one_and_update`` çağrılarında önce ``by_id``
    sözlüğüne bakar; yoksa AsyncMock fallback döner. Bu sayede testler
    hem "başarılı" hem "yok" senaryolarını temiz yazabilir.

    ``update_one`` demo-seed ``$setOnInsert + upsert`` senaryosunu
    **ardışık tek-süreçli** çağrılar için taklit eder: filter eşleşirse
    ``$setOnInsert`` uygulanmaz (dokunulmaz), eşleşmezse yeni doküman
    ``$setOnInsert`` + filter alanları + (varsa) ``$set`` ile birlikte
    eklenir. Bu, ``find_one + insert_one`` yarış koşulunu ortadan
    kaldırır — ancak **yalnızca ardışık tek-süreçli** çağrılar için.
    Çoklu bağımsız süreçlerin eşzamanlı çalışması bu fake DB'nin
    kapsamı dışındadır; unique index olmadan MongoDB de bunu garanti
    etmez.
    """

    def __init__(self):
        self.create_index = AsyncMock(return_value=None)
        self.docs: Dict[str, Dict[str, Any]] = {}
        # update_one / insert_one AsyncMock; test'ler bunlar üzerinden
        # side-effect tetikleyebilir
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.update_one = AsyncMock(side_effect=self._update_one)
        self.find_one_and_update = AsyncMock(side_effect=self._find_one_and_update)
        self.find_one = AsyncMock(side_effect=self._find_one)

    def _insert_one(self, doc: Dict[str, Any]):
        doc["_id"] = doc.get("_id") or f"new-{len(self.docs) + 1}"
        self.docs[doc["_id"]] = dict(doc)
        return MagicMock(inserted_id=doc["_id"])

    async def _update_one(
        self,
        filter_: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
        *args,
        **kwargs,
    ):
        """MongoDB ``update_one(filter, update, upsert)`` minimal semantiği.

        Desteklenen operatörler:

        * ``$set`` — eşleşen dokümana uygulanır (insert sırasında da).
        * ``$setOnInsert`` — yalnızca upsert insert durumunda uygulanır.

        Yalnızca **ardışık tek-süreçli** davranış modellenir. Yarış
        penceresi yoktur; birden fazla eşzamanlı çağrı aynı anda
        ``no match`` görüp ikisi de insert edebilir. Bu, MongoDB'nin
        ``update_one + upsert`` davranışına (unique index olmadan) sadık
        bir modeldir.
        """
        matched = self._find_matching(filter_)
        if matched is not None:
            if "$set" in update:
                for k, v in update["$set"].items():
                    matched[k] = v
                self.docs[matched["_id"]] = matched
            # ``$setOnInsert`` yalnızca insert sırasında uygulanır.
            return MagicMock(matched_count=1, modified_count=1, upserted_id=None)

        if not upsert:
            return MagicMock(matched_count=0, modified_count=0, upserted_id=None)

        from bson import ObjectId
        new_doc: Dict[str, Any] = {}
        # Filter alanları varsayılan baseline olarak eklenir
        # (MongoDB upsert davranışı).
        for k, v in filter_.items():
            if k.startswith("$"):
                continue
            new_doc[k] = v
        # ``$setOnInsert`` insert'e özel alanlar.
        if "$setOnInsert" in update:
            for k, v in update["$setOnInsert"].items():
                new_doc[k] = v
        # ``$set`` her zaman yazar (insert sırasında da).
        if "$set" in update:
            for k, v in update["$set"].items():
                new_doc[k] = v
        if "_id" not in new_doc:
            new_doc["_id"] = ObjectId()
        self.docs[str(new_doc["_id"])] = new_doc
        return MagicMock(
            matched_count=0, modified_count=0, upserted_id=new_doc["_id"]
        )

    def _find_matching(self, filter_: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter'a uyan ilk dokümanı döner (yoksa ``None``)."""
        for doc in self.docs.values():
            ok = True
            for k, v in filter_.items():
                if k.startswith("$"):
                    continue  # operatörler _find_one üzerinden
                if doc.get(k) != v:
                    ok = False
                    break
            if ok:
                return doc
        return None

    def _find_one(self, query: Dict[str, Any], *args, **kwargs):
        """Sadece ``{"_id": id, ...}`` ve sınırlı Mongo operatörleri.

        Desteklenen operatörler (Phase 2A kapsamı):

        * ``$or`` — bir branch eşleşirse true
        * ``$exists: bool`` (operatör-value) — key'in var/yok eşleşmesi

        Diğer operatörler (örn. ``$gt``) yoksayılır — Mongo'nun tam
        alt kümesini yeniden uygulamak yerine test kapsamını sınırlı
        tutarız.

        ``_id`` içermeyen sorgular için en az bir eşleşen alan eşitliği
        olan doküman aranır (örn. ``{"branch_code": "DEMO-ALL-RISK-01"}``).
        """
        if "_id" in query:
            doc = self.docs.get(query["_id"])
            if doc is None:
                return None
            for k, v in query.items():
                if k == "_id":
                    continue
                if k.startswith("$"):
                    if k == "$or":
                        if not any(
                            self._doc_matches_branch(doc, b) for b in v
                        ):
                            return None
                    # Diğer operatörler ($gt vs.) yoksay
                    continue
                if doc.get(k) != v:
                    return None
            return dict(doc)
        # Generic top-level equality match
        for doc in self.docs.values():
            if self._doc_matches_branch(doc, query):
                return dict(doc)
        return None

    def _doc_matches_branch(self, doc: Dict[str, Any], branch: Dict[str, Any]) -> bool:
        """``$or`` branch'i için basit match — sadece ``$exists`` desteklenir."""
        for k, v in branch.items():
            if isinstance(v, dict) and v and all(
                vk.startswith("$") for vk in v
            ):
                if "$exists" in v:
                    if bool(v["$exists"]) != (k in doc):
                        return False
                # Diğer operatör dict'leri yoksay
                continue
            if doc.get(k) != v:
                return False
        return True

    def _find_one_and_update(
        self, filter_, update, *args, return_document=None, **kwargs
    ):
        doc = self._find_one(filter_)
        if doc is None:
            return None
        # $set / $inc uygula
        set_data = update.get("$set", {})
        for k, v in set_data.items():
            doc[k] = v
        inc = update.get("$inc", {})
        for k, v in inc.items():
            doc[k] = doc.get(k, 0) + v
        # Mutate in-place
        self.docs[doc["_id"]] = doc
        return dict(doc)


class FakeTemplatesCollection:
    """``db.templates`` için stateful collection mock."""

    def __init__(self, initial: Optional[List[Dict[str, Any]]] = None):
        self.create_index = AsyncMock(return_value=None)
        self.docs: Dict[str, Dict[str, Any]] = {}
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.find = MagicMock(side_effect=self._find)
        self.insert_one = AsyncMock(side_effect=self._insert_one)

        if initial:
            for doc in initial:
                # ``code`` unique index anchor
                self.docs[doc["code"]] = doc

    def _find_one(self, query: Dict[str, Any], *args, **kwargs):
        if "code" in query:
            doc = self.docs.get(query["code"])
            return dict(doc) if doc else None
        return None

    def _find(self, query: Dict[str, Any], *args, **kwargs):
        if query == {}:
            items = [dict(d) for d in self.docs.values()]
        else:
            items = []
            for d in self.docs.values():
                if all(d.get(k) == v for k, v in query.items()):
                    items.append(dict(d))
        return FakeCursor(items)

    def _insert_one(self, doc: Dict[str, Any]):
        # Duplicate insert exception sim
        from pymongo.errors import DuplicateKeyError
        if doc.get("code") in self.docs:
            raise DuplicateKeyError("duplicate code")
        self.docs[doc["code"]] = dict(doc)
        return MagicMock(inserted_id=doc.get("code"))


class FakeDB:
    """``server.db`` için complete double — tüm collection'ları içerir."""

    def __init__(self, templates: Optional[List[Dict[str, Any]]] = None):
        self.audits = FakeAuditsCollection()
        self.templates = FakeTemplatesCollection(templates or [])
        # users koleksiyonu MagicMock ise içindeki ``create_index`` de
        # MagicMock olur; ``await`` edilemez. Tüm indeks oluşturma
        # çağrılarını AsyncMock ile sarmalıyoruz.
        self.users = MagicMock()
        self.users.create_index = AsyncMock(return_value=None)
        # ``seed_admin`` ve kimlik doğrulama yolu ``await db.users.update_one``
        # çağırır; MagicMock olarak kalırsa await edilemez.
        self.users.update_one = AsyncMock(return_value=None)
        self.users.find_one = AsyncMock(return_value=None)
        self.users.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        # JWT secret başka testlerde mock'landığı için users-specific
        # davranışı test etmiyoruz.
        # B6/B7 — audit_log ve audit_ibraz koleksiyonları. ``log_action``
        # ve ``_persist_ibraz_record`` mandatory=True olduğunda bu
        # koleksiyonlara yazar; yoksa testlerde ``RuntimeError`` raise
        # eder. MagicMock yeterli — yazma işlemleri await'lenebilir.
        self.audit_log = MagicMock()
        self.audit_log.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        self.audit_log.find_one = AsyncMock(return_value=None)
        self.audit_log.create_index = AsyncMock(return_value=None)
        self.audit_ibraz = MagicMock()
        self.audit_ibraz.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
        self.audit_ibraz.find_one = AsyncMock(return_value=None)
        self.audit_ibraz.create_index = AsyncMock(return_value=None)

    def attach_to_server(self) -> Any:
        """Modül-level ``server.db``'yi bu fake ile değiştir.

        Test sonunda eski haline restore etmek için ``detach`` ile
        birlikte kullanılır (``with`` context'iyle).
        """
        from unittest.mock import patch
        return patch("server.db", self)


@asynccontextmanager
async def fake_db_context(
    templates: Optional[List[Dict[str, Any]]] = None,
):
    """Async context manager — ``server.db`` mock'la, tüm test boyunca aktif.

    Kullanım::

        @pytest.mark.asyncio  # gerekmiyor async testler için
        async def test_x():
            async with fake_db_context([sample_template_doc()]) as db:
                ...
    """
    from unittest.mock import patch
    fake = FakeDB(templates)
    p = patch("server.db", fake)
    p.start()
    try:
        # TEMPLATES_CACHE'i de doldur
        import server
        server.TEMPLATES_CACHE.clear()
        for tpl in (templates or []):
            server.TEMPLATES_CACHE[tpl["code"]] = tpl
        yield fake
    finally:
        p.stop()
        import server
        server.TEMPLATES_CACHE.clear()


# ---------------------------------------------------------------------------
# Non-async sync wrapper (pytest async fixture olmadan)
# ---------------------------------------------------------------------------
from contextlib import contextmanager


def run_async(coro):
    """Sync test içinden async coroutine çalıştır.

    Phase 2A test'leri ``pytest-asyncio`` yerine bu helper'ı kullanır:
    pytest-asyncio image'a ekstra dependency eklemek yerine, asyncio.run
    ile sync köprü kurar. Bu helper yalnızca test ortamı içindir.
    """
    import asyncio
    return asyncio.run(coro)


@contextmanager
def fake_db(
    templates: Optional[List[Dict[str, Any]]] = None,
):
    """Senkron testler için — ``server.db`` mock'lanır.

    Testler bunu ``with`` ile kullanır; ``fake_db_context`` async
    versiyonu. Sync testlerde FastAPI endpoint'leri DB'ye dokunmaz
    (sadece saf pure-Python fonksiyonlar test edilir) veya
    ``find_one_and_update`` vb. doğrudan fake'e çağrılır.
    """
    from unittest.mock import patch
    fake = FakeDB(templates)
    with patch("server.db", fake):
        import server
        server.TEMPLATES_CACHE.clear()
        for tpl in (templates or []):
            server.TEMPLATES_CACHE[tpl["code"]] = tpl
        yield fake
        server.TEMPLATES_CACHE.clear()


def push_audit(db: FakeDB, audit_doc: Dict[str, Any]) -> None:
    """Bir audit'i fake'e koy (stateful doğrulama için)."""
    db.audits.docs[audit_doc["_id"]] = audit_doc
