# E2E test: export guards
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'

Write-Host '=== Login ===' -ForegroundColor Cyan

# ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
if (-not $env:ADMIN_EMAIL) {
    throw "ADMIN_EMAIL environment variable is required"
}
if (-not $env:ADMIN_PASSWORD) {
    throw "ADMIN_PASSWORD environment variable is required"
}

$body = @{ email = $env:ADMIN_EMAIL; password = $env:ADMIN_PASSWORD } | ConvertTo-Json -Compress
$login = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -Body $body -ContentType 'application/json' -SessionVariable sv
Write-Host "  OK"

Write-Host ''
Write-Host '=== Test A: DRAFT audit -> export should fail 409 ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_EXPORT_DRAFT'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$draftAudit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -ContentType 'application/json' -WebSession $sv
Write-Host "  audit: $($draftAudit.id), state: $($draftAudit.state)"

try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$($draftAudit.id)/export/excel" -Method Get -WebSession $sv -TimeoutSec 5 -ErrorAction Stop | Out-Null
    Write-Host '  FAIL: should be rejected' -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "  $code (expected 409)"
    if ($code -ne 409) { throw "FAIL: expected 409" }
}

Write-Host ''
Write-Host '=== Test B: SUBMITTED audit -> export should fail 409 ===' -ForegroundColor Cyan
$sub = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($draftAudit.id)/submit" -Method Post -WebSession $sv
Write-Host "  after submit: state: $($sub.state)"

try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$($draftAudit.id)/export/pdf" -Method Get -WebSession $sv -TimeoutSec 5 -ErrorAction Stop | Out-Null
    Write-Host '  FAIL: should be rejected' -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "  $code (expected 409)"
    if ($code -ne 409) { throw "FAIL: expected 409" }
}

Write-Host ''
Write-Host '=== Test C: DOF_OPEN audit -> export should fail 409 (with DOF_OPEN-specific message) ===' -ForegroundColor Cyan
$auditBody2 = @{ restaurant_name = 'TEST_EXPORT_DOF'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$dofAudit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody2 -ContentType 'application/json' -WebSession $sv

$hayirBody = @{ answers = @{ '1' = 'HAYIR' }; expected_version = $dofAudit.version } | ConvertTo-Json
$dofAudit2 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($dofAudit.id)/answers" -Method Put -Body $hayirBody -ContentType 'application/json' -WebSession $sv
$dofSubmit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($dofAudit.id)/submit" -Method Post -WebSession $sv
Write-Host "  audit state: $($dofSubmit.state) (should be DOF_OPEN)"

try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$($dofAudit.id)/export/excel" -Method Get -WebSession $sv -TimeoutSec 5 -ErrorAction Stop | Out-Null
    Write-Host '  FAIL: should be rejected' -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    $errResp = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    Write-Host "  $code - $($errResp.detail)"
    if ($code -ne 409) { throw "FAIL: expected 409" }
    if ($errResp.detail -notmatch 'a\u00e7\u0131k D\u00d6F') { throw "FAIL: expected DOF_OPEN message" }
    Write-Host '  OK: DOF_OPEN-specific error' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== Test D: Soft-deleted audit -> 404 (find_one filters out) ===' -ForegroundColor Cyan
$auditBody3 = @{ restaurant_name = 'TEST_EXPORT_DELETED'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$delAudit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody3 -ContentType 'application/json' -WebSession $sv
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($delAudit.id)" -Method Delete -WebSession $sv
Write-Host "  audit: $($delAudit.id), soft-deleted"

try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$($delAudit.id)/export/pdf" -Method Get -WebSession $sv -TimeoutSec 5 -ErrorAction Stop | Out-Null
    Write-Host '  FAIL: should be rejected' -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    $errResp = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    Write-Host "  $code - $($errResp.detail) (expected 404 - soft-deleted hidden from query)"
    if ($code -ne 404) { throw "FAIL: expected 404" }
}

Write-Host ''
Write-Host 'ALL EXPORT GUARD TESTS PASSED' -ForegroundColor Green
