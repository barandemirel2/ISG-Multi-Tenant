# E2E test: login -> create audit -> check state=DRAFT -> submit -> check state=SUBMITTED -> try update_answers (should fail) -> delete (should soft) -> check deleted_at
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'
$CookieFile = "C:\Users\baran\RISK-ANALIZ\scripts\test_cookies.txt"

Remove-Item $CookieFile -ErrorAction SilentlyContinue

# ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
if (-not $env:ADMIN_EMAIL) {
    throw "ADMIN_EMAIL environment variable is required"
}
if (-not $env:ADMIN_PASSWORD) {
    throw "ADMIN_PASSWORD environment variable is required"
}

Write-Host '=== 1. Login ===' -ForegroundColor Cyan
$body = @{ email = $env:ADMIN_EMAIL; password = $env:ADMIN_PASSWORD } | ConvertTo-Json -Compress
$loginResp = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -Body $body -ContentType 'application/json' -SessionVariable sv
Write-Host "  user_id: $($loginResp.id), role: $($loginResp.role)"

Write-Host ''
Write-Host '=== 2. Create audit ===' -ForegroundColor Cyan
$auditBody = @{
    restaurant_name = 'TEST_DENEME_SUBMIT'
    address = 'Test Adres Cankaya Ankara'
    audit_date = '2026-08-13'
    denetci = 'Test Denetci'
    brand = 'Burger King'
    city = 'Ankara'
    district = 'Cankaya'
} | ConvertTo-Json
$auditResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -ContentType 'application/json' -WebSession $sv
$auditId = $auditResp.id
Write-Host "  audit_id: $auditId"
Write-Host "  state: $($auditResp.state)"
Write-Host "  is_completed: $($auditResp.is_completed)"
Write-Host "  state_history length: $($auditResp.state_history.Count)"
if ($auditResp.state -ne 'DRAFT') { throw "FAIL: expected DRAFT, got $($auditResp.state)" }
Write-Host '  OK: state=DRAFT' -ForegroundColor Green

Write-Host ''
Write-Host '=== 3. Submit audit (no HAYIR -> should go to SUBMITTED) ===' -ForegroundColor Cyan
$submitResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$auditId/submit" -Method Post -WebSession $sv
Write-Host "  state: $($submitResp.state)"
Write-Host "  is_completed: $($submitResp.is_completed)"
Write-Host "  state_history length: $($submitResp.state_history.Count)"
Write-Host "  last transition: $($submitResp.state_history[-1] | ConvertTo-Json -Compress)"
if ($submitResp.state -ne 'SUBMITTED') { throw "FAIL: expected SUBMITTED, got $($submitResp.state)" }
Write-Host '  OK: state=SUBMITTED' -ForegroundColor Green

Write-Host ''
Write-Host '=== 4. Try update_answers (should fail 409) ===' -ForegroundColor Cyan
try {
    $ansBody = @{ answers = @{ '1' = 'EVET' }; expected_version = $submitResp.version } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl/api/audits/$auditId/answers" -Method Put -Body $ansBody -ContentType 'application/json' -WebSession $sv
    Write-Host '  FAIL: update_answers should have been rejected' -ForegroundColor Red
} catch {
    $errResp = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    Write-Host "  expected error: $($errResp.detail)"
    if ($_.Exception.Response.StatusCode.value__ -ne 409) { throw "FAIL: expected 409" }
    Write-Host '  OK: state guard rejected' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== 5. Try update_audit_meta (should fail 409) ===' -ForegroundColor Cyan
try {
    $metaBody = @{
        restaurant_name = 'TEST_DENEME_SUBMIT'
        address = 'Yeni Adres'
        expected_version = $submitResp.version
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl/api/audits/$auditId" -Method Patch -Body $metaBody -ContentType 'application/json' -WebSession $sv
    Write-Host '  FAIL: update_audit_meta should have been rejected' -ForegroundColor Red
} catch {
    $errResp = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "  expected error: $code - $($errResp.detail)"
    if ($code -ne 409) { throw "FAIL: expected 409, got $code" }
    Write-Host '  OK: state guard rejected' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== 6. Try update_audit_declarations (should SUCCEED in SUBMITTED) ===' -ForegroundColor Cyan
$decBody = @{ declarations = @{ '1' = @{ isyeri_beyani = 'test' } } } | ConvertTo-Json
$decResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$auditId/declarations" -Method Patch -Body $decBody -ContentType 'application/json' -WebSession $sv
Write-Host "  state: $($decResp.state)"
if ($decResp.state -ne 'SUBMITTED') { throw "FAIL: state changed unexpectedly" }
Write-Host '  OK: declarations editable in SUBMITTED' -ForegroundColor Green

Write-Host ''
Write-Host '=== 7. Try export_pdf (should fail - no final yet) ===' -ForegroundColor Cyan
try {
    $null = Invoke-WebRequest -Uri "$BaseUrl/api/audits/$auditId/export/pdf" -Method Get -WebSession $sv -TimeoutSec 5 -ErrorAction Stop
    Write-Host '  WARN: export succeeded' -ForegroundColor Yellow
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "  status: $code (export guard not yet implemented - TODO S18 next step)"
}

Write-Host ''
Write-Host '=== 8. Try delete (should SOFT-DELETE in SUBMITTED) ===' -ForegroundColor Cyan
$delResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$auditId" -Method Delete -WebSession $sv
Write-Host "  response: $($delResp | ConvertTo-Json -Compress)"
if (-not $delResp.soft) { throw "FAIL: expected soft delete" }
Write-Host '  OK: soft-deleted' -ForegroundColor Green

Write-Host ''
Write-Host '=== 9. Try update_answers on soft-deleted (should fail 410) ===' -ForegroundColor Cyan
try {
    $ansBody = @{ answers = @{ '2' = 'HAYIR' }; expected_version = $decResp.version } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl/api/audits/$auditId/answers" -Method Put -Body $ansBody -ContentType 'application/json' -WebSession $sv
    Write-Host '  FAIL: should be rejected' -ForegroundColor Red
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    $errResp = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    Write-Host "  expected error: $code - $($errResp.detail)"
    if ($code -ne 410) { throw "FAIL: expected 410" }
    Write-Host '  OK: 410 Gone for soft-deleted' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== 10. Create + DRAFT delete (should HARD-DELETE) ===' -ForegroundColor Cyan
$audit2Body = @{
    restaurant_name = 'TEST_DENEME_DRAFT_DELETE'
    address = 'Test Adres 2'
    audit_date = '2026-08-13'
    denetci = 'Test Denetci 2'
} | ConvertTo-Json
$audit2 = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $audit2Body -ContentType 'application/json' -WebSession $sv
Write-Host "  created audit_id: $($audit2.id), state: $($audit2.state)"

$del2 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($audit2.id)" -Method Delete -WebSession $sv
Write-Host "  delete response: $($del2 | ConvertTo-Json -Compress)"
if ($del2.soft) { throw "FAIL: DRAFT should be hard delete" }
Write-Host '  OK: hard-deleted DRAFT' -ForegroundColor Green

Write-Host ''
Write-Host '=== 11. Create + HAYIR + Submit (should go to DOF_OPEN) ===' -ForegroundColor Cyan
$audit3Body = @{
    restaurant_name = 'TEST_HAYIR_DOF'
    address = 'Test Adres 3'
    audit_date = '2026-08-13'
    denetci = 'Test Denetci 3'
} | ConvertTo-Json
$audit3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $audit3Body -ContentType 'application/json' -WebSession $sv
Write-Host "  created audit_id: $($audit3.id), state: $($audit3.state)"

# HAYIR cevap ekle
$hayirBody = @{ answers = @{ '1' = 'HAYIR'; '5' = 'HAYIR' }; expected_version = $audit3.version } | ConvertTo-Json
$audit3After = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($audit3.id)/answers" -Method Put -Body $hayirBody -ContentType 'application/json' -WebSession $sv
Write-Host "  set HAYIR -> state: $($audit3After.state) (should be DRAFT)"

# Şimdi submit et
$sub3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$($audit3.id)/submit" -Method Post -WebSession $sv
Write-Host "  after submit -> state: $($sub3.state) (should be DOF_OPEN due to HAYIR)"
if ($sub3.state -ne 'DOF_OPEN') { throw "FAIL: expected DOF_OPEN, got $($sub3.state)" }
Write-Host '  OK: state=DOF_OPEN' -ForegroundColor Green
Write-Host "  state_history:"
$sub3.state_history | ForEach-Object { Write-Host "    $($_.from) -> $($_.to): $($_.reason)" }

Write-Host ''
Write-Host 'ALL TESTS PASSED' -ForegroundColor Green
