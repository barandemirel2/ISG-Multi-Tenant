"""Explicit developer entry point for seeding the demo audit.

Kullanım
========

    cd backend && python3 -m seed.seed_demo_audit

Bu komut ``on_startup``'tan **bağımsız** olarak demo denetimini DB'ye
ekler. Geliştirici/UAT amaçlıdır; production ortamında
``seed_all_no_sample_audit`` environment guard'ı nedeniyle erken çıkar.

Tasarım kararları
=================

* ``server.seed_admin`` + ``server.seed_all_no_sample_audit`` çağrılarını
  yeniden kullanır — 84 soruluk demo inşası burada kopyalanmaz.
* FastAPI ``app`` başlatılmaz; ``@app.on_event("startup")`` tetiklenmez.
* DB bağlantısı ``server.py`` modülünün import edilmesiyle kurulur
  (``AsyncIOMotorClient`` motor lazy-connect semantiği kullanır).
* Ortam değişkenleri ``server.py`` importundan önce mevcut olmalıdır;
  aksi halde ``MONGO_URL``/``DB_NAME`` modül yüklemesinde ``KeyError``
  verir. Bu kasıtlı: demo seed komutu, canlı ``backend/.env`` veya
  geliştirici kabuğunun env'ıyla çalışır.
* ``seed_admin`` zaten ``ADMIN_EMAIL``/``ADMIN_PASSWORD`` doğrulamasını
  (uzunluk dahil) yapar; eksik/geçersiz ise ``RuntimeError`` fırlatır —
  fail-fast.
* ``seed_all_no_sample_audit`` kendi ``ENVIRONMENT`` guard'ını uygular;
  ``production``/``prod`` durumunda hiçbir şey yazmaz ve exit code 0
  ile çıkar (güvenli no-op).
* Tek-süreçli provisioning komutu olarak tasarlandı: ``branch_code``
  üzerinde unique index yoktur; birden fazla bağımsız sürecin aynı
  anda çalıştırılması bu komut kapsamında garanti edilmez. Çoklu-worker
  uygulama başlangıcı artık seed'i çağırmadığı için bu yarış üretimde
  ortaya çıkmaz.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


async def main() -> None:
    import server

    # Admin yoksa oluştur (demo denetimin ``user_id`` ataması için).
    await server.seed_admin()
    # Demo denetim kaydını atomik upsert ile seed et.
    await server.seed_all_no_sample_audit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        # ``seed_admin`` ``ADMIN_EMAIL``/``ADMIN_PASSWORD`` doğrulamasında
        # ``RuntimeError`` fırlatır; burada okunabilir bir mesajla exit.
        print(f"demo seed hata: {exc}", file=sys.stderr)
        sys.exit(1)