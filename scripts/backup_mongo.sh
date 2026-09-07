#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# MongoDB Backup Script — ABCD Tech Solutions İSG Risk Analiz Sistemi (S20)
# UAT kuralı: "Kanunen 6 yıl saklanmalı" → 6 yıl boyunca geri alınabilir
# olmalı. Bu script, audit_log + audits koleksiyonlarının periyodik
# yedeğini alır (yerel + opsiyonel S3 off-site).
#
# Kullanım:
#   bash scripts/backup_mongo.sh                    # varsayılan: docker exec
#   BACKUP_DOCKER_EXEC=false bash backup_mongo.sh   # yerel mongodump
#   BACKUP_KEEP_DAYS=30 bash backup_mongo.sh        # 30 gün tut
#
# Ortam değişkenleri:
#   BACKUP_DIR            Yedek kök dizini (default: /var/backups/mongo)
#   BACKUP_DOCKER_EXEC    true → container içinde çalıştır (default: true)
#   BACKUP_MONGO_CONTAINER Docker container adı (default: risk-analiz-mongo-1)
#   BACKUP_DB             Veritabanı adı (default: risk_analiz)
#   BACKUP_KEEP_DAYS      Yerel saklama süresi (default: 7)
#   S3_BUCKET             S3 bucket adı (varsa off-site upload)
#   S3_ENDPOINT           S3 endpoint (MinIO vb. için)
#   AWS_ACCESS_KEY_ID     AWS credentials
#   AWS_SECRET_ACCESS_KEY
#
# Crontab (host'ta):
#   0 3 * * * /opt/risk-analiz/scripts/backup_mongo.sh >> /var/log/mongo_backup.log 2>&1
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Defaults ─────────────────────────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-/var/backups/mongo}"
BACKUP_DOCKER_EXEC="${BACKUP_DOCKER_EXEC:-true}"
BACKUP_MONGO_CONTAINER="${BACKUP_MONGO_CONTAINER:-risk-analiz-mongo-1}"
BACKUP_DB="${BACKUP_DB:-risk_analiz}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="${BACKUP_DB}_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
ARCHIVE_PATH="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# ─── Logging ──────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

mkdir -p "$BACKUP_DIR"

log "═══════════════════════════════════════════════════════════════"
log "MongoDB Backup başlatıldı: $BACKUP_NAME"
log "  DB:                $BACKUP_DB"
log "  Mode:              $([ "$BACKUP_DOCKER_EXEC" = "true" ] && echo "docker exec ($BACKUP_MONGO_CONTAINER)" || echo "local mongodump")"
log "  Target:            $BACKUP_PATH"
log "  Keep days:         $BACKUP_KEEP_DAYS"
log "  S3 off-site:       $([ -n "${S3_BUCKET:-}" ] && echo "enabled (s3://$S3_BUCKET)" || echo "disabled")"

# ─── mongodump ───────────────────────────────────────────────────────────
if [ "$BACKUP_DOCKER_EXEC" = "true" ]; then
    # docker CLI host'ta mevcut mu kontrol et. Container içinde çalıştırılıyorsa
    # ``docker`` komutu bulunmaz, otomatik local mod'a düş.
    if ! command -v docker >/dev/null 2>&1; then
        log "  ⚠ BACKUP_DOCKER_EXEC=true ama docker CLI bulunamadı; local moda geçiliyor"
        BACKUP_DOCKER_EXEC=false
    fi
fi

if [ "$BACKUP_DOCKER_EXEC" = "true" ]; then
    # Container içinde çalıştır, output'u host'a kopyala
    TMP_TAR="/tmp/${BACKUP_NAME}.tar"
    docker exec "$BACKUP_MONGO_CONTAINER" \
        sh -c "mongodump --db=$BACKUP_DB --archive=$TMP_TAR --gzip"
    docker cp "${BACKUP_MONGO_CONTAINER}:${TMP_TAR}" "${BACKUP_DIR}/${BACKUP_NAME}.tar"
    docker exec "$BACKUP_MONGO_CONTAINER" rm -f "$TMP_TAR"
    ARCHIVE_PATH="${BACKUP_DIR}/${BACKUP_NAME}.tar"
    COMPRESSED_SIZE=$(stat -c%s "$ARCHIVE_PATH" 2>/dev/null || stat -f%z "$ARCHIVE_PATH")
else
    # Yerel mongodump (single-file archive mode)
    mongodump --db="$BACKUP_DB" --archive="$ARCHIVE_PATH" --gzip
    COMPRESSED_SIZE=$(stat -c%s "$ARCHIVE_PATH" 2>/dev/null || stat -f%z "$ARCHIVE_PATH")
fi

log "  Backup tamamlandı: $ARCHIVE_PATH ($COMPRESSED_SIZE bytes)"

# ─── S3 off-site upload (opsiyonel) ──────────────────────────────────────
if [ -n "${S3_BUCKET:-}" ]; then
    S3_KEY="${S3_BUCKET}/${BACKUP_DB}/${BACKUP_NAME}.tar.gz"
    log "  S3 upload başlıyor: s3://${S3_KEY}"
    if command -v s5cmd >/dev/null 2>&1; then
        s5cmd cp "$ARCHIVE_PATH" "s3://${S3_KEY}"
    elif command -v aws >/dev/null 2>&1; then
        aws s3 cp "$ARCHIVE_PATH" "s3://${S3_KEY}"
    else
        log "  ⚠ s5cmd/aws CLI bulunamadı, S3 upload atlandı (BACKUP_DOSYASI yerelde kaldı)"
    fi
fi

# ─── Eski yedekleri temizle ──────────────────────────────────────────────
DELETED=$(find "$BACKUP_DIR" -maxdepth 1 -name "${BACKUP_DB}_*.tar*" -mtime "+${BACKUP_KEEP_DAYS}" -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
    log "  Eski yedek temizlendi: $DELETED dosya (>${BACKUP_KEEP_DAYS} gün)"
fi

# ─── Özet ────────────────────────────────────────────────────────────────
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -maxdepth 1 -name "${BACKUP_DB}_*.tar*" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "?")
log "  Mevcut yedek sayısı: $TOTAL_BACKUPS, toplam boyut: $TOTAL_SIZE"
log "═══════════════════════════════════════════════════════════════"

# ─── Audit log entry (opsiyonel) ─────────────────────────────────────────
# Yedekleme olayını audit_log'a yazmak için backend'in /api/admin/backup
# endpoint'i kullanılabilir. Şimdilik sadece sistem log'una yazıyoruz.
log "Backup başarıyla tamamlandı."
exit 0
