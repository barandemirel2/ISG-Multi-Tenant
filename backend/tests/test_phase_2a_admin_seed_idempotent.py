"""Aşama 2A — Admin startup seed: idempotent + unique index + cache load.

Doğrulanan bağlayıcı davranış:

* ``on_startup`` çağrıldığında ``db.templates.create_index("code", unique=True)``
  tetiklenir (PR0 ile aynı kalır; Phase 2A bunu değiştirmez).
* ``on_startup`` ``seed_default_template()`` çağırır; ilk çalıştırmada
  insert eder, ikinci çalıştırmada idempotent (existing=True döner).
* ``on_startup`` sonunda ``TEMPLATES_CACHE`` dolu olur.
* Eğer templates koleksiyonu zaten doluysa, ``seed_default_template``
  insert etmez; ama cache yine de doldurulur.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from _phase_2a_helpers import (
    fake_db,
    run_async,
    sample_template_doc,
)


class TestSeedDefaultTemplate:
    """``seed_default_template`` idempotent."""

    def test_first_call_inserts(self):
        tpl = sample_template_doc()
        with fake_db([]):  # boş başla
            from server import seed_default_template
            inserted = run_async(seed_default_template())
            assert inserted is True
            assert __import__("server").db.templates.docs.get("isg_v1_default") is not None

    def test_second_call_is_noop(self):
        """Template zaten DB'de → ikinci çağrı False döner."""
        with fake_db([sample_template_doc()]):
            from server import seed_default_template
            inserted = run_async(seed_default_template())
            assert inserted is False
            # Hâlâ tek template var
            assert len(__import__("server").db.templates.docs) == 1

    def test_idempotent_across_three_calls(self):
        with fake_db([]):
            from server import seed_default_template
            r1 = run_async(seed_default_template())
            r2 = run_async(seed_default_template())
            r3 = run_async(seed_default_template())
            assert (r1, r2, r3) == (True, False, False)
            assert len(__import__("server").db.templates.docs) == 1


class TestOnStartupLoadsCache:
    """``on_startup`` cache'i doldurur ve index oluşturur."""

    def test_startup_creates_unique_code_index(self):
        tpl = sample_template_doc()
        with fake_db([]):
            from server import on_startup
            run_async(on_startup())
            # create_index çağrıldı
            assert __import__("server").db.templates.create_index.await_count >= 1

    def test_startup_seeds_if_missing(self):
        with fake_db([]):
            from server import on_startup
            run_async(on_startup())
            assert __import__("server").db.templates.docs.get("isg_v1_default") is not None

    def test_startup_preserves_existing_template(self):
        existing = sample_template_doc()
        with fake_db([existing]):
            from server import on_startup
            run_async(on_startup())
            # Değişmedi
            assert __import__("server").db.templates.docs["isg_v1_default"]["version"] == existing["version"]

    def test_startup_loads_cache(self):
        with fake_db([]):
            from server import on_startup
            run_async(on_startup())
            assert __import__("server").TEMPLATES_CACHE.get("isg_v1_default") is not None

    def test_cache_rebuilt_on_repeated_startup(self):
        """İki kez çağrılsa bile cache tutarlı."""
        with fake_db([]):
            from server import on_startup
            run_async(on_startup())
            v1 = __import__("server").TEMPLATES_CACHE.get("isg_v1_default", {}).get("version")
            run_async(on_startup())
            v2 = __import__("server").TEMPLATES_CACHE.get("isg_v1_default", {}).get("version")
            assert v1 == v2


class TestTemplateCodeConstant:
    """Template code unique index anchor olarak doğru sabittir."""

    def test_template_code_matches_seed(self):
        from seed import isg_v1
        assert isg_v1.TEMPLATE_CODE == "isg_v1_default"

    def test_built_doc_uses_stable_code(self):
        from seed import isg_v1
        doc = isg_v1.build_template_doc()
        assert doc["code"] == "isg_v1_default"