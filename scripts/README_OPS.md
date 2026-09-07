# Operasyonel Scriptler (Backup + Archive)

S20 — Kanunen 6 yıl retention + off-site backup. Bu klasördeki
scriptler production'da host makinede (veya ayrı bir sidecar
container'da) çalıştırılacak operasyonel araçlardır.

## 📦 `backup_mongo.sh`

MongoDB'nin periyodik yedeğini alır. Hem yerel diske yazar hem
opsiyonel olarak S3'e (veya S3-uyumlu storage: MinIO, Wasabi vb.)
yükler.

### Kullanım

```bash
# Manuel çalıştırma
bash scripts/backup_mongo.sh

# Custom konfigürasyon
BACKUP_DIR=/mnt/backups BACKUP_KEEP_DAYS=30 \
  S3_BUCKET=my-backups S3_ENDPOINT=https://s3.amazonaws.com \
  AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy \
  bash scripts/backup_mongo.sh
```

### Çıktı formatı

```
/var/backups/mongo/
├── risk_analiz_20260814_030000.tar.gz
├── risk_analiz_20260813_030000.tar.gz
├── ...
```

Her dosya `mongodump --gzip --archive` ile oluşturulur; gzip'li
single-file archive formatındadır.

### Restore

```bash
# Yedeği bir klasöre aç
mkdir restore && cd restore
tar xzf /var/backups/mongo/risk_analiz_20260814_030000.tar.gz
# veya doğrudan mongorestore ile:
docker exec -i risk-analiz-mongo-1 \
  mongorestore --archive --gzip < /var/backups/mongo/risk_analiz_20260814_030000.tar.gz
```

### Crontab (host'ta)

```cron
# Her gece 03:00 — günlük tam yedek
0 3 * * * /opt/risk-analiz/scripts/backup_mongo.sh >> /var/log/mongo_backup.log 2>&1
```

### Çevre değişkenleri

| Değişken                  | Default                | Açıklama                                |
|---------------------------|------------------------|-----------------------------------------|
| `BACKUP_DIR`              | `/var/backups/mongo`   | Yedek kök dizini                        |
| `BACKUP_DOCKER_EXEC`      | `true`                 | `true` → container içinde çalıştır      |
| `BACKUP_MONGO_CONTAINER`  | `risk-analiz-mongo-1`  | Docker container adı                    |
| `BACKUP_DB`               | `risk_analiz`          | Veritabanı adı                          |
| `BACKUP_KEEP_DAYS`        | `7`                    | Yerel retention (gün)                    |
| `S3_BUCKET`               | _(yok)_                | S3 bucket (varsa off-site upload aktif)  |
| `S3_ENDPOINT`             | _(yok)_                | S3 endpoint (MinIO gibi custom)          |
| `AWS_ACCESS_KEY_ID`       | _(yok)_                | AWS credentials                          |
| `AWS_SECRET_ACCESS_KEY`   | _(yok)_                | AWS credentials                          |

---

## 🗄️ `archive_expired.sh`

6 yıl retention süresi dolmuş audit'leri `is_archived=true` olarak
işaretler (veriyi SİLMEZ, sadece default listelerde gizler). Manuel
veya cron ile tetiklenir.

### Kullanım

```bash
# Admin credentials env'den
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=secret \
  bash scripts/archive_expired.sh

# veya .env dosyasından (cron job'unda source edilebilir)
source /opt/risk-analiz/.env.production
bash scripts/archive_expired.sh
```

### Akış

1. Admin login → JWT al
2. `POST /api/admin/archive-expired` → retention'ı dolmuş audit'leri arşivle
3. `GET /api/admin/retention-status` → anlık retention durumunu logla

### Crontab (host'ta)

```cron
# Her gece 02:00 — günlük archive
0 2 * * * /opt/risk-analiz/scripts/archive_expired.sh >> /var/log/archive_expired.log 2>&1
```

---

## 🔧 Admin Endpoints

`/api/admin/*` endpoint'leri yalnız `role=admin` kullanıcılar tarafından
erişilebilir. Uygulama üzerinden admin dashboard'unda da tetiklenebilir.

| Endpoint                              | Method | Amaç                                |
|---------------------------------------|--------|--------------------------------------|
| `/api/admin/archive-expired`          | POST   | Retention'ı dolmuş audit'leri arşivle |
| `/api/admin/retention-status`         | GET    | Anlık retention durumu özeti          |
| `/api/admin/backup`                   | POST   | Manuel backup tetikleyici (log-only)  |

---

## 🔐 E2E Test Credential Setup

`scripts/e2e_*.ps1` ve `scripts/e2e_*.py` scriptleri hardcoded credentials
içermez. Admin credential environment variable'lardan okunur
(`scripts/archive_expired.sh` ile aynı pattern).

### bash / zsh

```bash
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="$(vault kv get -field=password secret/risk-analiz/admin)"
pwsh scripts/e2e_columns_test.ps1
```

### PowerShell

```powershell
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_PASSWORD = (Get-Secret -Name RISK-ANALIZ-ADMIN-PASSWORD -AsPlainText)
pwsh scripts/e2e_columns_test.ps1
```

### Python

```bash
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="$(op read 'op://Prod/Risk-Analiz/admin/password')"
python scripts/e2e_dof_summary_test.py
```

### Fail-fast davranışı

Credential env-var eksikse script başlamaz ve açık hata verir:

```
ADMIN_EMAIL environment variable is required
ADMIN_PASSWORD environment variable is required
```

Hiçbir hardcoded fallback, placeholder veya örnek şifre yoktur.

### Güvenlik notu

- Credential değerleri **asla** repository'ye commit edilmez.
- Credential içeren tüm dosyalar `.gitignore` ve branch-level
  secret-scanning ile korunur (`backend/.env`, `scripts/login_body.json`).
- Eğer bir credential leaked ise (committed/pushed/printed):
  1. Hemen rotasyon yap (production admin account'u değiştir)
  2. Yeni credential'ı sadece secret store'a yaz
  3. Eski credential'ı invalidate et
  4. `git log -S` ile leak edilen SHA'ları bulup audit trail tut

---

## 🛡️ Production Deployment Kontrol Listesi

1. **Backup stratejisi**:
   - [ ] `BACKUP_DIR` ayrı disk/volüme mount edildi (veri kaybı koruması)
   - [ ] `S3_BUCKET` (veya MinIO endpoint) off-site storage yapılandırıldı
   - [ ] Crontab kuruldu ve günlük log rotation yapılandırıldı
   - [ ] İlk backup alındı ve restore test edildi (en az 1 kere!)

2. **Archive stratejisi**:
   - [ ] `archive_expired.sh` için admin credentials env'de tanımlı
   - [ ] Crontab kuruldu (her gece 02:00 önerilen)
   - [ ] UI'da `/admin` sayfası varsa oradan da tetiklenebilir (TODO)

3. **Monitoring**:
   - [ ] Backup/Archive cron failure alerting (opsiyonel: Slack/email webhook)
   - [ ] Disk space monitoring (`/var/backups/mongo` <80% dolu)
   - [ ] Audit log endpoint'inden son 24h'de `archive` action var mı kontrol
