# ABCD Tech Solutions — Risk Analiz Sistemi

İSG denetim checklist'ini (84 evet/hayır sorusu, 9 kategori) dijital çok kullanıcılı sisteme dönüştürür. FastAPI + MongoDB backend, React 19 + Tailwind + Shadcn/UI frontend.

Bir **denetçi** siteye girer, restoran seçer, **yeni denetim** açar; sistem o an aktif olan **template'in snapshot'unu** alır, 84 soruyu 9 kategori altında yükler. Denetçi EVET/HAYIR/N/A ile ilerler, HAYIR cevaplarında **risk override** ederek (olasılık/şiddet) **Kabul Edilebilir → Dikkate Değer → Kabul Edilemez** sınıflamasını canlı günceller; sonuç **PDF/Excel** olarak dışa aktarılır.

---

## 1. Proje Özeti

- **Ne yapıyor:** ABCD Tech Solutions'nın İSG denetim soru listesini (DOCX) dijital forma taşır, çok kullanıcılı bir denetim/analiz/skorlama sistemine dönüştürür.
- **Kim kullanıyor:**
  - **Admin** — tüm auditleri görür, default template'i yönetir.
  - **Denetçi** (regular user) — kendi auditlerini oluşturur/düzenler.
- **Genel akış:**
  1. Kullanıcı giriş yapar (JWT + HttpOnly cookie).
  2. Admin veya denetçi yeni audit oluşturur → aktif default template'in snapshot'ı alınır.
  3. 84 soru 9 kategori altında cevaplanır.
  4. HAYIR cevaplarında olasılık/şiddet override edilir; canlı risk skoru ve sınıfı hesaplanır.
  5. Audit tamamlandığında PDF ve Excel export edilir.

---

## 2. Teknoloji

| Katman      | Tercih                                                                       |
|-------------|------------------------------------------------------------------------------|
| Backend     | FastAPI (Python 3.11), MongoDB (motor), Pydantic v2, JWT (PyJWT), bcrypt     |
| Frontend    | React 19 + Vite (build zamanı CRA/CRACO miras), Tailwind + Shadcn/UI         |
| Database    | MongoDB 7 (`templates`, `audits`, `users`)                                   |
| Docker      | Dev: `docker-compose.yml` (mongo + backend `--reload` + frontend dev server) |
|             | Prod: `docker-compose.prod.yml` (mongo + backend `--workers 2` + nginx)      |
| Export      | `openpyxl` (Excel), `reportlab` (PDF)                                        |
| Auth        | Bcrypt parola hash, JWT access (kısa ömürlü) + refresh (HttpOnly cookie)    |

---

## 3. Risk Analizi Akışı

```
┌───────────────┐    ┌──────────────┐    ┌────────────────┐    ┌──────────────┐
│  DOCX Şablon  │ →  │  Seed JSON   │ →  │ Mongo Template │ →  │ Yeni Audit   │
│ (84 soru)     │    │ (84/9 kat.)  │    │ (is_default=1) │    │ POST /audits │
└───────────────┘    └──────────────┘    └────────────────┘    └──────┬───────┘
                                                                     │
                                                                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ PDF / Excel  │ ← │Canlı Risk    │ ← │  Override     │ ← │  Snapshot    │
│ GET /export  │    │ Hesabı       │    │ (HAYIR'da)    │    │ embed        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

- **DOCX → Seed JSON:** `seed/isg_v1.py` `load_seed_questions()` ile 84 soruyu 1..84 numaralı, 9 benzersiz kategorili biçimde döner.
- **Seed → Template:** Backend startup'ta default template yoksa seed'i içeri alır (`is_default=true`).
- **Template → Audit:** Yeni audit oluşturulurken template'in tam kopyası audit'e gömülür (snapshot).
- **Snapshot → Cevaplama:** Frontend snapshot'ı okur, override'ı state'te tutar, canlı hesap yapar.
- **Override → Canlı Risk:** `P×S` skoru ve sınıfı anlık güncellenir.
- **Canlı Risk → Export:** PDF/Excel snapshot + cevap + override + özet kullanır.

---

## 4. Template Sistemi

- **Template nedir?** Soru havuzudur. Bir template = `{code, version, name, questions[84]}` (ve opsiyonel `categories`). İlk aktif template `isg_v1_default`.
- **Neden snapshot?** Bir audit oluşturulduğunda template'in **o anki** hâli `template_snapshot` olarak audit dokümanına yazılır. Böylece:
  - Audit zamanında hangi soru hangi kategorideydi, kim ne cevapladı bilinir.
  - Sonradan template değişse de eski audit'in görünümü bozulmaz.
  - Template yeni sürüme geçse de eski audit yeni soruları **görmez**.
- **Eski audit neden bozulmaz?** Çünkü yeni template değişikliği yalnızca `templates` koleksiyonunu etkiler; `audits.template_snapshot` zaten audit'e gömülüdür. Bu yüzden her audit kendi zamanının sorularıyla yaşar (legacy auditler `is_legacy=true` olarak işaretlenir).

---

## 5. Risk Hesabı

**Risk Skoru = Olasılık × Şiddet** (`probability * severity`, her ikisi 1..5).

| Skor Aralığı | Sınıf           |
|--------------|-----------------|
| **1 – 4**    | Kabul Edilebilir|
| **5 – 12**   | Dikkate Değer   |
| **13 – 25**  | Kabul Edilemez  |

- Her sorunun başlangıç değeri template'de kayıtlıdır: `default_probability`, `default_severity`, `default_risk_score`, `default_risk_level`.
- **Kullanıcı override yaptığında:**
  - Effective değerler `risk_overrides[qid] = {probability, severity}` üzerinden hesaplanır.
  - UI anında yeni skor + sınıfı gösterir; özet kabul edilebilirlik sayısı değişir.
- **Varsayılana dönünce:**
  - `risk_overrides[qid]` silinir; effective hesap yine `default_*` alanlarına düşer.
  - Override default'a eşitse veya override yoksa, audit `risk_overrides` set'i boş kalır (aşağıdaki **collapse**).

---

## 6. Override Sistemi

- **Ne zaman açılır?** Soruya **HAYIR** cevabı verildiğinde; soru satırı "Override Editor" panelini açar.
- **Nasıl çalışır?**
  - Denetçi olasılık (1–5) ve şiddet (1–5) sliders/radial bileşenleriyle ayarlar.
  - Not alanı opsiyoneldir.
  - Her değişiklikte frontend `compute_effective_risk` anında yeniden hesaplar.
- **Ne DB'ye yazılır?**
  - `audits.risk_overrides` Map'i: `{ "<question_id>": {"probability": int, "severity": int, "note"?: str} }`.
  - Audit update PUT'unda `version` artar (optimistic concurrency).
- **Ne zaman collapse edilir?** DB'ye yazmadan veya autosave sırasında `risk_overrides` içindeki kayıtlar default değerlerle karşılaştırılır; default'a eşit olanlar kaldırılır → sadece gerçek farklılaştırılmış override'lar DB'de kalır. Bu, audit'in temiz temsilini garanti eder.

---

## 7. Mongo Yapısı

| Koleksiyon      | Görev                                                                     |
|-----------------|---------------------------------------------------------------------------|
| `users`         | Hesaplar; bcrypt parola, JWT subject, rol (`admin`/`user`)                |
| `templates`     | Soru şablonları; `code`, `version`, `name`, `questions`, `is_default`     |
| `audits`        | Denetim; `template_snapshot`, `answers`, `risk_overrides`, `version`, …   |

### `audits` alanları (özet)

```
{
  _id, user_id, restaurant_name, address, audit_date, denetci,
  template_snapshot: { questions: [...84], snapshot_at, template_code, ... },
  answers:           { "<qid>": "EVET" | "HAYIR" | "N/A" },
  risk_overrides:    { "<qid>": { probability, severity, note? } },
  version:           int  // optimistic concurrency
}
```

`template_snapshot.categories` taşınmaz (snapshot şu an `questions + snapshot_at + template_code + template_name + template_version` saklar); kategori listesi frontend tarafında `questions[*].category`'lerden **türetilir**. Aynı audit içindeki soruların `category`'leri snapshot zamanından gelir, sonradan değişmez.

---

## 8. API Akışı

**Yeni audit** — `POST /api/audits` → aktif default template'in snapshot'ını audit'e gömer, `version=1` set eder. Response: `template_code`, `template_name`, `template_version`, `is_legacy=false`.

**Audit açma** — `GET /api/audits/{id}` → detay response şunları taşır: `answers`, `risk_overrides`, `template_snapshot` (yalnız detay), `summary` (kabul edilebilirlik özeti), `is_legacy`.

**Cevap kaydetme** — `PUT /api/audits/{id}` body `answers` ve (opsiyonel) `risk_overrides` Map'i. Body'de beklenen `version` ile optimistic concurrency uygulanır.

**Override kaydetme** — Aynı PUT body'sinde `risk_overrides` Map'i; effective risk hem backend'de (`compute_effective_risk`) hem frontend'de (`lib/risk.js`) aynı formülle hesaplanır.

**Export** — `GET /api/audits/{id}/export.xlsx` (openpyxl) ve `GET /api/audits/{id}/export.pdf` (reportlab). Legacy audit export'ları `template_snapshot` yerine modül düzeyinde `QUESTIONS` listesine düşer.

> Tüm mutation endpoint'leri `version` (optimistic concurrency) taşır.

---

## 9. Çalıştırma

### Önkoşul
- `.env` zorunludur; `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` set edilmeden servisler ayağa kalkmaz (fail-fast).

```bash
cp .env.example .env
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"   # → .env'e yapıştır
# ADMIN_EMAIL=<e-posta>
# ADMIN_PASSWORD=<güçlü parola>
```

### Geliştirme (hot reload)

```bash
docker compose up -d --build
# Backend:  http://localhost:8000/docs   (Swagger)
# Frontend: http://localhost:3000
```

Backend kaynak değişikliklerinde uvicorn reload; frontend HMR. Veri `mongo_data` named volume'unda (lokal geliştirme veritabanı), frontend `node_modules` `frontend_node_modules` volume'unda.

### Production Build (tek port)

```bash
docker compose -f docker-compose.prod.yml up -d --build
# Tek port: http://localhost  (nginx → /api proxy backend:8000)
```

Multi-arch manifest; Apple Silicon ve Intel host'larda aynı imajlar çalışır. Zorla amd64 için `--platform linux/amd64`. Backend `--workers 2`.

### Sıkça kullanılan komutlar

```bash
# Backend testleri (mongomock + httpx)
cd backend && pytest

# Frontend birim testleri
cd frontend && npm test

# Sadece backend'i lokal çalıştırmak için
cd backend
uvicorn server:app --reload --port 8000

# Stack'i sıfırlama (volume'lar dahil)
docker compose down -v
docker compose up --build
```

### Bağımlılık volume refresh (güvenli)

Frontend bağımlılıkları değiştiğinde yalnız `frontend_node_modules` volume'unu
silmek güvenlidir. Bu volume `com.docker.compose.volume=frontend_node_modules`
label'ı ile işaretlidir; silmek için:

```bash
docker volume rm $(docker volume ls -q -f name=frontend_node_modules)
```

`mongo_data` volume'u **lokal geliştirme veritabanı**dır — bağımlılık refresh
için ASLA silinmez. Geniş kapsamlı prune komutları `mongo_data`'yı da
sileceğinden güvenli refresh için kullanılmaz.

### Çerez politika seçimi (PR4)

`COOKIE_SECURE` ve `COOKIE_SAMESITE` ortam değişkenleriyle:

- **HTTP demo (lokal):** `COOKIE_SECURE=false`, `COOKIE_SAMESITE=lax`
- **HTTPS üretim:** `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax`

`SameSite=None` yalnızca gerçek cross-site gereksiniminde seçilir ve `COOKIE_SECURE=true` zorlar.

---

## 10. Phase 2B Sonunda Tamamlanan Özellikler

- DOCX → seed JSON (`seed/isg_v1.py`) ile 84 soru / 9 kategori standardizasyonu.
- `templates` koleksiyonu: default template yönetimi, `is_default` flag.
- `create_audit()` snapshot'ı template'den audit'e gömer (`template_snapshot`).
- Audit detayı kendi snapshot'ını kullanır; `/questions` global endpoint'i yalnız yeni-akış şablonu için okunur.
- Legacy auditler `is_legacy=true` ile işaretlenir ve export fonksiyonları modül-düzeyi `QUESTIONS` fallback'i ile çalışır.
- HAYIR cevaplarında risk override akışı: `risk_overrides` Map'i + canlı effective hesabı.
- Override collapse: default'a eşit override'lar DB'ye yazılmaz, audit özeti temiz kalır.
- Optimistic concurrency: `version` field ile conflict detection (`409`).
- Çerez politika profili (HTTP demo / HTTPS) operatörden okunur, request sinyallerinden değil.
- PDF & Excel export snapshot + cevap + override + özeti taşır.

---

## 11. Bilinen Kısıtlar

- Frontend hâlâ **CRACO/CRA** üzerinde; **Vite migration** yapılmadı (build zamanı `@craco/craco` devDependency tutularak süreklilik sağlandı).
- Database **PostgreSQL'e taşınmadı**; MongoDB ile devam ediliyor.
- Audit **silme** ve **arşivleme** yok; silinen auditler için yumuşak-silme (soft-delete) desteği eklenmedi.
- **Çoklu tenant** routing/izolasyon **yok** (Faz 1+ yol haritasında); şu an tek kiracı (ABCD Tech Solutions).
- **Çoklu template** seçimi yok; her zaman aktif default `gida_v1` template kullanılır (template loader altyapısı `backend/scripts/template_loader.py`'de hazır).
- **Rapor şablonları** sabit; PDF/Excel biçimi henüz tema/şablon-değişkeni almıyor.
- **E-posta bildirim** veya **kullanıcı davet** akışı yok.
- **Audit kilitleme** yok; iki kullanıcı aynı anda aynı audit'i açarsa son yazan kazanır (snapshot conflict detection var ama edit kilidi yok).
- **Test çıktıları** `test_reports/` altında birikmiş durumda; CI/CD runner'ı bu depoya henüz bağlanmadı.

---

## 12. Sonraki Yol Haritası

### Faz 1 — Multi-Tenant Temel Altyapı (sonraki sprint)

- **Tenant veri modeli:** `tenants` koleksiyonu + mevcut collection'lara `tenant_id` alanı
- **Backend middleware:** her sorguya `tenant_id` filtresi enjekte eden resolver
- **Tenant resolver:** subdomain (`firma-a.isg-multi-tenant.com`) → tenant_id
- **Branding:** her tenant için logo, renk paleti, marka adı
- **Onboarding UI:** admin → yeni müşteri formu

### Faz 2 — Sektörel Şablonlar

- `tekstil_v1.json` (60-80 soru)
- `insaat_v1.json` (100+ soru, yüksek riskli işler)
- `maden_v1.json` (120+ soru, çok yüksek riskli)
- `genel_v1.json` (sektör-bağımsız temel 40 soru)

### Faz 3 — Mevzuat Motoru

- PerQuestionReviewer → admin UI
- WebSearcher (mevzuat.gov.tr scraper)
- Otomatik KB güncelleme + cron self

### Faz 4 — Teknik Borç

- **Vite'a geçiş** + build/cache iyileştirmesi.
- **Edit kilidi** (audit optimistic lock UI tarafında görünür hale gelsin).
- **PostgreSQL migration** araştırması (ilişkisel sorgu ihtiyacı netleşince).
- **Bildirim/abonelik** kanalı (e-posta veya webhook).
- **Tema/şablon** ile PDF/Excel raporlarını özelleştirme.
- **Soft-delete + audit log** ile geri alma ve denetim izi.

Detaylı mimari: `docs/ARCHITECTURE.md`.
