# ISG Multi-Tenant — Mimari Doküman

Bu doküman `isg-multi-tenant` reposunun şu anki ve planlanan mimarisini açıklar.

---

## 1. Vizyon

**ABCD Tech Solutions İSG Denetim ve Risk Analiz Sistemi**, çok kiracılı (multi-tenant) bir SaaS
platformudur. Her kiracı (tenant) bir firmadır; her firma kendi:

- **Markasını** (logo, renk, favicon) taşır
- **Sektörel soru şablonunu** (gıda, tekstil, inşaat, ...) kullanır
- **Restoran/işletme kataloğunu** (lokasyon, personel, departman) yönetir
- **Kullanıcılarını** (admin, denetçi, gözlemci) barındırır

Hedef: bir İSG denetimini firma-spesifik yapılandırmayla, standart İSG mevzuatına (6331, 4857, 6098, 5237, 5510, 5996, ...) tam uyumlu şekilde dijitalleştirmek.

---

## 2. Mevcut Durum (Faz 0 — Temel)

### 2.1 Şu an: Tek kiracı (single-tenant)

- **Marka:** ABCD Tech Solutions
- **Sektör:** Gıda (restoran/üretim/paketleme)
- **Soru şablonu:** `gida_v1` — 84 soru, 9 ana kategori
- **Veritabanı:** MongoDB `risk_analiz` (single database)
- **Deployment:** Docker Compose, localhost geliştirme

### 2.2 Repository Yapısı

```
isg-multi-tenant/
├── AGENTS.md                    # Repo operasyonel anayasa (git preflight, secret, vs.)
├── ARRODES.md                   # Mimari kararlar ve alan kuralları
├── README.md                    # Proje özeti, kurulum, çalıştırma
├── docker-compose.yml           # Mongo + Backend + Frontend
├── .env.example                 # Güvenli env placeholder'ları
│
├── backend/
│   ├── server.py                # FastAPI app
│   ├── questions.json           # 84 soru (legacy — şablon'dan türetilir)
│   ├── questions_orig.json      # Orijinal yedek
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── data/
│   │   └── legal_knowledge_base.json   # PerQuestionReviewer KB (kanun + yönetmelik)
│   ├── scripts/
│   │   ├── question_regulatory_map.py  # 84 soru için mevzuat + yaptırım haritası
│   │   ├── template_loader.py          # Çoklu şablon yükleyici (FAZ 1)
│   │   ├── migrate_audit_state.py      # Audit state migration
│   │   └── update_question_texts.py    # Soru metni güncelleme
│   ├── seed/
│   │   ├── isg_v1.py                   # Seed script (varsayılan: gida_v1)
│   │   └── isg_v1_questions.json       # Seed soru listesi
│   └── tests/                          # Backend testleri
│
├── frontend/
│   ├── package.json
│   ├── Dockerfile.dev
│   ├── public/                         # Statik dosyalar (logo, docs)
│   └── src/
│       ├── pages/                      # Sayfa bileşenleri
│       ├── components/                 # Yeniden kullanılabilir bileşenler
│       ├── constants/
│       │   └── restaurantCatalog.json  # Restoran/lokasyon kataloğu
│       └── styles/                     # Tasarım token'ları
│
├── docs/
│   ├── ARCHITECTURE.md        # Bu dosya
│   └── RAILWAY_UAT.md         # Railway deployment notları
│
├── scripts/                            # Kök düzey scriptler
└── tests/                              # Kök düzey test runner
```

### 2.3 Template Sistemi (Faz 1 — Şu an faal)

Sektörel soru şablonları `backend/templates/` klasöründe tutulur. Şu an tek şablon var:

- `gida_v1.json` — 84 soru + regulatory map + metadata

**`template_loader.py` API:**

```python
from backend.scripts.template_loader import (
    list_templates,      # → [{"template_id": "gida_v1", ...}]
    load_template,       # → tam dict
    get_questions,       # → sadece soru listesi
    get_regulatory_map,  # → soru_id → {legal_basis, yaptirim, ceza}
    export_questions_json,  # JSON array olarak dışa aktar
)
```

**CLI:**

```bash
# Şablonları listele
python -m backend.scripts.template_loader --list

# Şablon özetini gör
python -m backend.scripts.template_loader --template gida_v1 --summary

# Soruları JSON'a dışa aktar
python -m backend.scripts.template_loader --template gida_v1 --output backend/questions.json
```

**İleride eklenecek şablonlar** (Faz 2+):

- `tekstil_v1.json` — Tekstil sektörü (60-80 soru)
- `insaat_v1.json` — İnşaat sektörü (yüksek riskli işler, 100+ soru)
- `maden_v1.json` — Maden sektörü (çok yüksek riskli, 120+ soru)
- `genel_v1.json` — Sektör-bağımsız temel İSG (40 soru)

---

## 3. Planlanan Mimari (Faz 1+ — Multi-Tenant)

### 3.1 Tenant Kavramı

**Tenant** = bir firma/müşteri. Her tenant:

- Benzersiz `tenant_id`'ye sahip
- Kendi alt domain'i: `{tenant}.isg-multi-tenant.com` (örn. `firma-a.isg-multi-tenant.com`)
- Kendi MongoDB verisini paylaşımlı DB'de `tenant_id` alanıyla izole eder
- Kendi markası, soru şablonu, kullanıcı grubu olur

### 3.2 Veri İzolasyon Stratejisi

**Seçenek A: Shared database, shared schema, `tenant_id` column** (Faz 1+ için planlanan)

- Tüm collection'larda `tenant_id` alanı
- Backend middleware her query'ye `tenant_id` filtresi enjekte eder
- Düşük maliyetli, basit deployment
- Dezavantaj: gürültülü komşu (noisy neighbor) riski

**Seçenek B: Database-per-tenant** (Faz 3+, premium tenant'lar için)

- Her tenant'ın kendi MongoDB veritabanı
- Güçlü izolasyon, kolay backup
- Yüksek maliyet

İlk aşamada **A**, premium tier için **B**.

### 3.3 Tenant Çözümleme (Resolver)

Tenant tespiti için 3 mekanizma planlanıyor:

1. **Subdomain** (tercih edilen): `firma-a.isg-multi-tenant.com` → tenant_id
2. **Header** (API/programatic): `X-Tenant-ID: firma-a`
3. **Path prefix** (test için): `isg-multi-tenant.com/t/firma-a/...`

### 3.4 Branding / White-Label (Faz 2)

Her tenant'ın:

- **Logo** (header + favicon)
- **Renk paleti** (primary, accent, semantic colors)
- **Font** (opsiyonel)
- **Marka adı** (UI text'lerde)

Tasarım token'ları (`frontend/src/styles/tokens.css`) tenant bazlı override edilebilir olacak.

### 3.5 Onboarding Flow (Faz 2)

Yeni tenant ekleme:

1. Admin → "Yeni Müşteri" → form
2. Tenant metadata: isim, subdomain, sektör, iletişim
3. Şablon seçimi (gida, tekstil, ...) veya custom
4. İlk admin kullanıcı oluşturma
5. Demo data factory (opsiyonel, pilot için)
6. Subdomain DNS kaydı + TLS

---

## 4. Mevzuat Motoru (PerQuestionReviewer)

`backend/scripts/question_regulatory_map.py` — 84 soru için:

- `legal_basis` — ilgili kanun/yönetmelik maddeleri
- `yaptirim` — idari/cezai/tazminat tipi
- `ceza` — miktar aralığı (2026 IPC güncel)
- `severity` — high/medium/low

`backend/data/legal_knowledge_base.json` — KB:

- 7 ana kanun (6331, 4857, 6098, 5237, 5510, 5996, BYKHY)
- 13 yönetmelik (İSG Risk Değerlendirmesi, Yangın, KKD, Gıda Hijyeni, vb.)

İleride: WebSearcher (mevzuat.gov.tr scraper) + otomatik KB güncelleme.

---

## 5. Geliştirme Workflow

### 5.1 Branch Stratejisi

- `main` — her zaman production-ready
- `feature/<isim>` — yeni özellik dalları
- `fix/<isim>` — bug fix dalları
- `chore/<isim>` — bakım, refactor, cleanup

### 5.2 Commit Konvansiyonu

`<type>(<scope>): <konu>`

- `feat(backend): tenant_id middleware`
- `fix(frontend): CascadingRestaurantSelect null check`
- `chore(legal): KB güncelleme — 5510 md. 102`
- `docs(readme): multi-tenant vizyon eklendi`

### 5.3 PR Review

- 1 onaylayıcı (maintainer) yeterli
- Tüm targeted testler PASS olmalı (full-suite henüz yok)
- AGENTS.md §6: targeted ≠ full-suite — raporlamada ayrı tut

---

## 6. Bilinen Sınırlamalar (Known Limitations)

- **Multi-tenant routing henüz yok** (Faz 0'da single-tenant, Faz 1+'da gelecek)
- **WebSearcher mevzuat.gov.tr scraper** henüz yazılmadı (KB güncellemesi manuel)
- **Per-işletme tehlike sınıfına göre dinamik IPC hesabı** yok (sabit 2026 tarifesi)
- **PDF export'a yasal dayanak eklenmedi** (Excel'de var)
- **Frontend severity field backend'den gelmiyor** (export script hardcoded)
- **Çoklu dil desteği** yok (sadece Türkçe)

---

## 7. Yol Haritası (Özet)

| Faz | Kapsam | Durum |
|-----|--------|-------|
| Faz 0 | Temel sistem (84 soru, gıda) | ✅ Tamamlandı |
| Faz 1 | Template loader altyapısı | ✅ Tamamlandı |
| Faz 2 | Multi-tenant (tenant_id, resolver, branding) | 📋 Planlandı |
| Faz 3 | Database-per-tenant (premium) | 📋 İleri tarih |
| Faz 4 | PerQuestionReviewer cron + admin UI | 📋 Planlandı |
| Faz 5 | Sektörel şablonlar (tekstil, inşaat, maden) | 📋 Gelecek |

---

## 8. Referanslar

- **AGENTS.md** — Repo operasyonel anayasa
- **ARRODES.md** — Mimari kararlar ve alan kuralları
- **docs/RAILWAY_UAT.md** — Railway deployment notları
- **README.md** — Kurulum ve çalıştırma

