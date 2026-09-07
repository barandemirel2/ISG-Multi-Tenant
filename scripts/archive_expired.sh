#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Archive Expired Audits — ABCD Tech Solutions İSG Risk Analiz Sistemi (S20)
# 6 yıl retention süresi dolmuş audit'leri arşivler (silmez, is_archived=true).
#
# Bu shell wrapper backend'in POST /api/admin/archive-expired endpoint'ini
# çağırır. Endpoint admin user + JWT token gerektirir.
#
# Crontab (her gün 02:00):
#   0 2 * * * /opt/risk-analiz/scripts/archive_expired.sh >> /var/log/archive_expired.log 2>&1
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────
BASE_URL="${BACKEND_URL:-http://localhost:8000}"
LOG_PREFIX="[archive_expired $(date '+%Y-%m-%d %H:%M:%S')]"

# ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
: "${ADMIN_EMAIL:?ADMIN_EMAIL is required}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD is required}"

log() { echo "$LOG_PREFIX $*"; }

# ─── Login (JWT al) ─────────────────────────────────────────────────────
# JSON payload güvenli oluşturma: shell interpolation ile değil,
# python -c ile JSON encode edilir (credential içinde özel karakter
# olsa bile geçerli JSON üretilir; injection yüzeyi yok).
LOGIN_BODY=$(ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    python3 -c 'import os, json, sys; print(json.dumps({"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}))')

TOKEN=$(curl -sS -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "$LOGIN_BODY" \
    | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token') or '')" 2>/dev/null || true)

if [ -z "$TOKEN" ]; then
    log "✗ Login başarısız (token alınamadı)"
    exit 1
fi
log "✓ Token alındı"

# ─── Archive tetikle ────────────────────────────────────────────────────
log "POST $BASE_URL/api/admin/archive-expired"
RESP=$(curl -sS -X POST "$BASE_URL/api/admin/archive-expired" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{}")

ARCHIVED=$(echo "$RESP" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('archived_count', '?'))" 2>/dev/null || echo "?")
log "✓ Arşivlenen audit sayısı: $ARCHIVED"

# ─── Retention status log ───────────────────────────────────────────────
log "GET $BASE_URL/api/admin/retention-status"
STATUS=$(curl -sS "$BASE_URL/api/admin/retention-status" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null || true)
if [ -n "$STATUS" ]; then
    echo "$STATUS" | python3 -m json.tool 2>/dev/null | sed "s/^/$LOG_PREFIX /" || true
fi

log "Tamamlandı."
exit 0
