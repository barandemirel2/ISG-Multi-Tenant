# encoding: utf-8
# E2E: Admin endpoint'ler (S20 backup + archive)
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'

# ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
if (-not $env:ADMIN_EMAIL) {
    throw "ADMIN_EMAIL environment variable is required"
}
if (-not $env:ADMIN_PASSWORD) {
    throw "ADMIN_PASSWORD environment variable is required"
}

function Send-Json {
    param([string]$Uri, [string]$Method, [string]$Body, $Sv)
    if (-not $Body) { $Body = '{}' }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
    return Invoke-RestMethod -Uri $Uri -Method $Method -Body $bytes -ContentType 'application/json; charset=utf-8' -WebSession $Sv
}

Write-Host '=== Login (admin) ===' -ForegroundColor Cyan
$loginBody = @{ email = $env:ADMIN_EMAIL; password = $env:ADMIN_PASSWORD } | ConvertTo-Json -Compress
$loginBytes = [System.Text.Encoding]::UTF8.GetBytes($loginBody)
$null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -Body $loginBytes -ContentType 'application/json; charset=utf-8' -SessionVariable sv
Write-Host '  OK'

Write-Host ''
Write-Host '=== Test 1: retention-status (admin) ===' -ForegroundColor Cyan
$resp = Invoke-RestMethod -Uri "$BaseUrl/api/admin/retention-status" -Method Get -WebSession $sv
Write-Host "  total: $($resp.total_audits), archived: $($resp.archived_audits), active: $($resp.active_audits)"
Write-Host "  expired_pending: $($resp.expired_pending_archive)"
Write-Host "  retention_years: $($resp.retention_years)"
if ($resp.retention_years -ne 6) { throw "FAIL: 6 yil bekleniyordu" }
Write-Host '  OK' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 2: archive-expired (admin) ===' -ForegroundColor Cyan
$resp = Send-Json -Uri "$BaseUrl/api/admin/archive-expired" -Method Post -Body '{}' -Sv $sv
Write-Host "  ok: $($resp.ok), archived_count: $($resp.archived_count)"
if (-not $resp.ok) { throw "FAIL: ok true bekleniyordu" }
Write-Host '  OK' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 3: backup trigger (admin, log-only) ===' -ForegroundColor Cyan
$resp = Send-Json -Uri "$BaseUrl/api/admin/backup" -Method Post -Body '{}' -Sv $sv
Write-Host "  ok: $($resp.ok), note: $($resp.note)"
if (-not $resp.ok) { throw "FAIL: ok true bekleniyordu" }
Write-Host '  OK' -ForegroundColor Green

Write-Host ''
Write-Host 'ADMIN OPS E2E PASSED' -ForegroundColor Green
exit 0
