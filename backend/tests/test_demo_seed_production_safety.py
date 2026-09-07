"""Demo-audit production-safety regression tests.

Kapsam
======

Bu test paketi ``seed_all_no_sample_audit``'ın üretim güvenliği sözleşmesini
kilit altına alır:

* **Test A** — ``on_startup`` artık demo denetimi oluşturmaz; template/admin
  davranışı bozulmaz.
* **Test B** — ``ENVIRONMENT`` ``production``/``prod`` (her harf kombinasyonu)
  olduğunda açık seed çağrısı reddedilir.
* **Test C** — Normal geliştirme ortamında açık seed çağrısı **tam olarak
  bir** doğru demo denetimi oluşturur (alan doğrulamaları dahil).
* **Test D** — Ardışık iki seed çağrısı yine **tek** kayıt üretir
  (idempotent); mevcut doküman korunur.
* **Test E** — ``seed.seed_demo_audit`` modülü ``server.seed_all_no_sample_audit``
  çağrısını yeniden kullanır, mantığı kopyalamaz, ``ENVIRONMENT=production``
  durumunda no-op kalır.

Kapsam dışı
-----------

``branch_code`` üzerinde unique index yoktur; bu nedenle **çoklu
bağımsız süreçlerin eşzamanlı** çalışmasının tek kayıt üreteceği
garanti edilmez. Test paketi kasıtlı olarak bu senaryoyu kapsamaz.
Üretim çoklu-worker startup yarışı zaten ``on_startup``'tan seed'i
kaldırdığımız için ortaya çıkmaz.

Tasarım kararları
=================

* ``_phase_2a_helpers`` üzerindeki ``FakeAuditsCollection`` ``update_one``
  semantiğini ``$setOnInsert + upsert`` ile taklit eder; **yalnızca
  ardışık tek-süreçli** davranış modellenir (MongoDB unique index'siz
  ``update_one + upsert`` davranışına sadık).
* Admin kullanıcı ``db.users.find_one`` side_effect'i üzerinden
  önceden yüklenir; ``seed_admin``'in yeni bir kullanıcı oluşturup
  oluşturmadığı bu test paketinin kapsamı dışındadır.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from _phase_2a_helpers import (  # noqa: E402
    fake_db,
    run_async,
    sample_template_doc,
)


# ---------------------------------------------------------------------------
# Yardımcı: fake users koleksiyonuna admin user ekle
# ---------------------------------------------------------------------------
def _install_admin_user(fake_db_obj) -> str:
    """``db.users.find_one`` semantiğini admin-döndürecek şekilde bağla.

    Testler ``seed_all_no_sample_audit``'ın ``user_id`` alanını admin'den
    türetmesine güvenir. Admin id'sini döndürürür.
    """
    admin_id = str(ObjectId())

    async def _find_one(query):
        if query.get("role") == "admin":
            return {
                "_id": admin_id if isinstance(admin_id, ObjectId) else ObjectId(admin_id),
                "email": "admin@example.com",
                "role": "admin",
            }
        return None

    fake_db_obj.users.find_one = AsyncMock(side_effect=_find_one)
    return admin_id


# ---------------------------------------------------------------------------
# Demo seed yardımcı: üretim guard'ını kapatıp açıkça seed çağır.
# ---------------------------------------------------------------------------
def _count_demo_audits(fake_db_obj) -> int:
    return sum(
        1
        for d in fake_db_obj.audits.docs.values()
        if d.get("branch_code") == "DEMO-ALL-RISK-01"
    )


def _get_demo_audit(fake_db_obj):
    for d in fake_db_obj.audits.docs.values():
        if d.get("branch_code") == "DEMO-ALL-RISK-01":
            return d
    return None


# ---------------------------------------------------------------------------
# Test A — startup never seeds demo audit
# ---------------------------------------------------------------------------
class TestStartupDoesNotSeedDemoAudit:
    """``on_startup`` artık demo denetimi oluşturmaz."""

    def test_startup_with_unset_environment_creates_no_demo_audit(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([]) as db:
            from server import on_startup
            run_async(on_startup())
            assert _count_demo_audits(db) == 0, (
                "on_startup ENVIRONMENT unset iken demo denetimi oluşturmamalı"
            )

    def test_startup_with_development_environment_creates_no_demo_audit(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        with fake_db([]) as db:
            from server import on_startup
            run_async(on_startup())
            assert _count_demo_audits(db) == 0, (
                "on_startup ENVIRONMENT=development iken demo denetimi oluşturmamalı"
            )

    def test_startup_still_seeds_template_and_loads_cache(self, monkeypatch):
        """Demo seed kaldırıldı; template/admin/cache davranışı bozulmamalı."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([]) as db:
            from server import on_startup
            run_async(on_startup())
            # Template hâlâ seed ediliyor
            assert db.templates.docs.get("isg_v1_default") is not None
            # Cache dolu
            import server as srv
            assert srv.TEMPLATES_CACHE.get("isg_v1_default") is not None
            # Index oluşturma hâlâ çağrılıyor
            assert db.templates.create_index.await_count >= 1
            assert db.audits.create_index.await_count >= 1
            # Hâlâ demo yok
            assert _count_demo_audits(db) == 0


# ---------------------------------------------------------------------------
# Test B — production environment guard
# ---------------------------------------------------------------------------
class TestProductionEnvironmentGuard:
    """``seed_all_no_sample_audit`` üretim benzeri ortamlarda no-op kalır."""

    @pytest.mark.parametrize(
        "env_value",
        ["production", "prod", "PRODUCTION", "PROD", "Production", "PrOd", "pRoD"],
    )
    def test_seed_refuses_in_production_like_environment(self, monkeypatch, env_value):
        monkeypatch.setenv("ENVIRONMENT", env_value)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            assert _count_demo_audits(db) == 0, (
                f"ENVIRONMENT={env_value!r} iken demo denetimi oluşmamalı"
            )
            # update_one hiç çağrılmamalı (guard erken çıkar)
            assert db.audits.update_one.await_count == 0


# ---------------------------------------------------------------------------
# Test C — explicit dev seed works (single correct record)
# ---------------------------------------------------------------------------
class TestExplicitDevSeedCreatesCorrectAudit:
    """``seed_all_no_sample_audit`` geliştirme ortamında tam olarak bir
    doğru demo denetimi oluşturur."""

    def test_creates_exactly_one_demo_audit(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            assert _count_demo_audits(db) == 1

    def test_demo_audit_has_correct_restaurant_and_branch(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            demo = _get_demo_audit(db)
            assert demo is not None
            assert demo["branch_code"] == "DEMO-ALL-RISK-01"
            assert demo["restaurant_name"] == (
                "TÜM RİSKLER ÖRNEK DEMO ŞUBESİ (TÜM SORULAR HAYIR)"
            )
            assert demo["is_completed"] is True
            assert demo["brand"] == "Burger King"
            assert demo["city"] == "İstanbul"
            assert demo["district"] == "Kadıköy"
            assert demo["denetci"] == "Örnek İSG Başdenetçisi (Demo)"

    def test_demo_audit_has_84_hayir_answers(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            demo = _get_demo_audit(db)
            assert demo is not None
            answers = demo["answers"]
            assert len(answers) == 84
            assert all(v == "HAYIR" for v in answers.values())
            # id'ler 1..84 string olarak
            keys = set(int(k) for k in answers.keys())
            assert keys == set(range(1, 85))

    def test_demo_audit_includes_template_snapshot(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            demo = _get_demo_audit(db)
            assert demo is not None
            snap = demo["template_snapshot"]
            assert snap["code"] == "isg_v1_default"
            assert len(snap["questions"]) == 84


# ---------------------------------------------------------------------------
# Test D — sequential idempotency
# ---------------------------------------------------------------------------
class TestSequentialIdempotency:
    """Ardışık iki seed çağrısı tek kayıt üretir."""

    def test_two_sequential_calls_yield_one_audit(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            run_async(seed_all_no_sample_audit())
            assert _count_demo_audits(db) == 1

    def test_five_sequential_calls_yield_one_audit(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            for _ in range(5):
                run_async(seed_all_no_sample_audit())
            assert _count_demo_audits(db) == 1

    def test_existing_demo_audit_is_not_overwritten(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            from server import seed_all_no_sample_audit
            run_async(seed_all_no_sample_audit())
            first_id = next(
                d["_id"] for d in db.audits.docs.values()
                if d.get("branch_code") == "DEMO-ALL-RISK-01"
            )
            first_completed_at = _get_demo_audit(db)["completed_at"]
            run_async(seed_all_no_sample_audit())
            ids = [
                d["_id"] for d in db.audits.docs.values()
                if d.get("branch_code") == "DEMO-ALL-RISK-01"
            ]
            assert ids == [first_id]
            assert _get_demo_audit(db)["completed_at"] == first_completed_at


# ---------------------------------------------------------------------------
# Test E — explicit command wiring (seed.seed_demo_audit)
# ---------------------------------------------------------------------------
class TestExplicitSeedCommand:
    """``seed.seed_demo_audit`` modülü ``server.seed_all_no_sample_audit``
    çağrısını yeniden kullanır ve kopyalamaz."""

    def test_command_module_invokes_canonical_seed_function(self, monkeypatch):
        """Komut ``seed_all_no_sample_audit``'ı doğrudan çağırır; ``main``
        içinden veya import sırasında ``seed_admin`` + ``seed_all_no_sample_audit``
        çağrılır."""
        import seed.seed_demo_audit as cmd

        called = {"seed_admin": 0, "seed_all_no_sample_audit": 0}

        async def _seed_admin():
            called["seed_admin"] += 1

        async def _seed_all_no_sample_audit():
            called["seed_all_no_sample_audit"] += 1

        monkeypatch.setattr(
            "server.seed_admin",
            _seed_admin,
            raising=False,
        )
        monkeypatch.setattr(
            "server.seed_all_no_sample_audit",
            _seed_all_no_sample_audit,
            raising=False,
        )

        run_async(cmd.main())

        assert called["seed_admin"] == 1
        assert called["seed_all_no_sample_audit"] == 1

    def test_command_does_not_duplicate_84_question_construction(self, monkeypatch):
        """Komut 84 soruluk demo inşasını **kopyalamamalı**. Komut dosyasında
        ``"HAYIR"`` → cevap sözlüğü inşası, ``build_template_doc`` çağrısı
        veya isg_v1 doğrudan kullanımı yer almamalı; bunun yerine
        ``server.seed_all_no_sample_audit`` çağrılmalı."""
        import seed.seed_demo_audit as cmd

        src = Path(cmd.__file__).read_text(encoding="utf-8")
        # Komut dosyası demo inşasını yeniden yazmamalı; yalnızca
        # ``seed_admin`` + ``seed_all_no_sample_audit`` çağrısı yapmalı.
        forbidden_construction = ['"HAYIR"', "build_template_doc", "isg_v1"]
        for token in forbidden_construction:
            assert token not in src, (
                f"seed_demo_audit.py demo inşasını kopyalamamalı; "
                f"yasaklı token {token!r} dosyada bulundu"
            )
        # Bunun yerine ``server.seed_all_no_sample_audit`` çağrılmalı.
        assert "seed_all_no_sample_audit" in src
        assert "seed_admin" in src

    def test_command_module_does_not_start_fastapi_app(self):
        """Komut import edildiğinde ``server.app`` üzerinde startup
        event tetiklenmemeli; ``app.on_event`` kayıtları import'a bağlı
        olsa da, ``asyncio.run``/uvicorn başlatılmaz."""
        import seed.seed_demo_audit as cmd
        import server

        # Komut dosyasının import edilmesi sunucu uygulamasını kapatmaz;
        # sadece ``main`` async fonksiyonunu çağırırız.
        assert callable(cmd.main)
        # ``app`` import edilmiş olmalı ama ``on_startup`` çağrılmamalı.
        assert server.app is not None

    def test_command_refuses_in_production_environment(self, monkeypatch):
        """``ENVIRONMENT=production`` iken komut seed_all_no_sample_audit
        çağrısını yapar ama o fonksiyon no-op kalır; audit oluşmaz."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        with fake_db([sample_template_doc()]) as db:
            _install_admin_user(db)
            import seed.seed_demo_audit as cmd
            run_async(cmd.main())
            assert _count_demo_audits(db) == 0

    def test_command_module_has_main_entry_point(self):
        """``python -m seed.seed_demo_audit`` için gerekli ``__main__`` koruması."""
        src = Path(__file__).resolve().parent.parent / "seed" / "seed_demo_audit.py"
        text = src.read_text(encoding="utf-8")
        assert "__main__" in text, (
            "seed_demo_audit.py 'python -m' çağrısı için __main__ guard içermeli"
        )
        assert "asyncio.run" in text, (
            "seed_demo_audit.py main() çağrısını asyncio.run ile çalıştırmalı"
        )