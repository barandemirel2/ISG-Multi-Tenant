# encoding: utf-8
# E2E: S19 Tutarl?? Onay Mekanizmas?? ??? DELETE ?reason= query param
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

Write-Host '=== Login ===' -ForegroundColor Cyan
$loginBody = @{ email = $env:ADMIN_EMAIL; password = $env:ADMIN_PASSWORD } | ConvertTo-Json -Compress
$loginBytes = [System.Text.Encoding]::UTF8.GetBytes($loginBody)
$null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -Body $loginBytes -ContentType 'application/json; charset=utf-8' -SessionVariable sv
Write-Host '  OK'

Write-Host ''
Write-Host '=== Setup: DRAFT audit (hard delete) ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_DEL_REASON'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -Sv $sv
$aid = $audit.id
Write-Host "  audit: $aid (state=$($audit.state))"

Write-Host ''
Write-Host '=== Test 1: Hard delete WITH reason ===' -ForegroundColor Cyan
$reasonText = 'Test silme sebebi ??? yanlislikla olusturulmus'
$encodedReason = [System.Web.HttpUtility]::UrlEncode($reasonText)
$resp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid`?reason=$encodedReason" -Method Delete -WebSession $sv
Write-Host "  ok: $($resp.ok), soft: $($resp.soft)"
if (-not $resp.ok) { throw "FAIL: ok=true bekleniyordu" }
Write-Host '  OK: hard delete basarili' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 2: DRAFT audit, reason OLMADAN ===' -ForegroundColor Cyan
$audit2 = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -Sv $sv
$aid2 = $audit2.id
$resp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid2" -Method Delete -WebSession $sv
if (-not $resp.ok) { throw "FAIL: ok=true bekleniyordu" }
Write-Host '  OK: hard delete reasonsiz da calisiyor' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 3: SUBMITTED+ audit (soft delete) with reason ===' -ForegroundColor Cyan
$audit3 = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -Sv $sv
$aid3 = $audit3.id
# HAYIR + submit
$answersBody = @{ answers = @{ '1' = 'HAYIR' }; expected_version = $audit3.version } | ConvertTo-Json
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid3/answers" -Method Put -Body $answersBody -Sv $sv
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid3/submit" -Method Post -Body '{}' -Sv $sv
$reasonText2 = 'Soft delete sebebi ??? saha denetimi iptal'
$encodedReason2 = [System.Web.HttpUtility]::UrlEncode($reasonText2)
$resp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid3`?reason=$encodedReason2" -Method Delete -WebSession $sv
Write-Host "  ok: $($resp.ok), soft: $($resp.soft)"
if (-not $resp.soft) { throw "FAIL: soft=true bekleniyordu" }
if ($resp.deleted_at) { Write-Host "  deleted_at: $($resp.deleted_at)" }
Write-Host '  OK: soft delete with reason basarili' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 4: Reason > 2000 char ??? 422 ===' -ForegroundColor Cyan
$audit4 = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -Sv $sv
$aid4 = $audit4.id
$longReason = 'x' * 2500
$encodedLong = [System.Web.HttpUtility]::UrlEncode($longReason)
try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid4`?reason=$encodedLong" -Method Delete -WebSession $sv
    throw "FAIL: 2000+ char reason reddedilmesi gerekirdi"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -ne 422) {
        throw "FAIL: 422 bekleniyordu, gelen: $code"
    }
    Write-Host '  OK: 2000+ char reason reddedildi (422)' -ForegroundColor Green
}

Write-Host ''
Write-Host 'DELETE REASON E2E PASSED' -ForegroundColor Green
