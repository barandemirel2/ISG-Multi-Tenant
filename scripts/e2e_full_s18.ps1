# Full S18 E2E: state machine + D\u00d6F transition + export finalize
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
$null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -Body $body -ContentType 'application/json' -SessionVariable sv
Write-Host '  OK'

Write-Host ''
Write-Host '=== Test: HAYIR + Submit -> DOF_OPEN, close all D\u00d6Fs -> DOF_CLOSED, export -> FINAL ===' -ForegroundColor Cyan

# 1. Create
$auditBody = @{ restaurant_name = 'TEST_S18_FULL'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -ContentType 'application/json' -WebSession $sv
$aid = $audit.id
Write-Host "  [1] Created audit: $aid, state=$($audit.state)"

# 2. Set 3 HAYIR answers
$hayirBody = @{ answers = @{ '1' = 'HAYIR'; '5' = 'HAYIR'; '10' = 'HAYIR' }; expected_version = $audit.version } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $hayirBody -ContentType 'application/json' -WebSession $sv
Write-Host "  [2] 3 HAYIR answers set"

# 3. Submit -> DOF_OPEN
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/submit" -Method Post -WebSession $sv
Write-Host "  [3] Submit -> state: $($audit.state) (expect DOF_OPEN)"
if ($audit.state -ne 'DOF_OPEN') { throw "FAIL: expected DOF_OPEN" }

# 4. Try export -> 409
try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$aid/export/excel" -Method Get -WebSession $sv -TimeoutSec 5 -ErrorAction Stop | Out-Null
    throw 'FAIL: export should fail'
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 409) { throw "FAIL: expected 409" }
    Write-Host '  [4] Export blocked (409) - DOF_OPEN, OK' -ForegroundColor Green
}

# 5. Close first D\u00d6F
$closeBody1 = @{ status = 'KAPATILDI'; notes = 'Duzeltildi, 1. madde' } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $closeBody1 -ContentType 'application/json' -WebSession $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  [5.1] DOF #1 closed -> audit state: $($audit.state) (expect DOF_OPEN - 2 remain)"
if ($audit.state -ne 'DOF_OPEN') { throw "FAIL: expected DOF_OPEN" }

# 6. Close second D\u00d6F
$closeBody2 = @{ status = 'KAPATILDI'; notes = 'Duzeltildi, 2. madde' } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/5" -Method Put -Body $closeBody2 -ContentType 'application/json' -WebSession $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  [5.2] DOF #5 closed -> audit state: $($audit.state) (expect DOF_OPEN - 1 remain)"
if ($audit.state -ne 'DOF_OPEN') { throw "FAIL: expected DOF_OPEN" }

# 7. Close last D\u00d6F
$closeBody3 = @{ status = 'KAPATILDI'; notes = 'Duzeltildi, 3. madde' } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/10" -Method Put -Body $closeBody3 -ContentType 'application/json' -WebSession $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  [5.3] DOF #10 closed -> audit state: $($audit.state) (expect DOF_CLOSED)"
if ($audit.state -ne 'DOF_CLOSED') { throw "FAIL: expected DOF_CLOSED, got $($audit.state)" }
Write-Host "         is_completed: $($audit.is_completed) (expect True)"
if (-not $audit.is_completed) { throw "FAIL: expected is_completed=True" }

# 8. Export -> should succeed AND transition to FINAL
$resp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/export/excel" -Method Get -WebSession $sv -TimeoutSec 10
Write-Host "  [6] Export excel -> 200, size: $($resp.Length) bytes"

# Verify FINAL after export
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "         post-export state: $($audit.state) (expect FINAL)"
if ($audit.state -ne 'FINAL') { throw "FAIL: expected FINAL, got $($audit.state)" }

# 9. Try edit in FINAL -> 409
try {
    $editBody = @{ answers = @{ '20' = 'EVET' }; expected_version = $audit.version } | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $editBody -ContentType 'application/json' -WebSession $sv
    throw 'FAIL: edit should fail'
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 409) { throw "FAIL: expected 409" }
    Write-Host '  [7] Edit blocked in FINAL (409) - OK' -ForegroundColor Green
}

# 10. Re-export in FINAL -> still 200 (idempotent)
$resp2 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/export/pdf" -Method Get -WebSession $sv -TimeoutSec 10
Write-Host "  [8] Re-export pdf in FINAL -> 200, size: $($resp2.Length) bytes"
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "         state still: $($audit.state) (FINAL, expect stable)"

Write-Host ''
Write-Host 'state_history:'
$audit.state_history | ForEach-Object { Write-Host "  $($_.from) -> $($_.to): $($_.reason)" }

Write-Host ''
Write-Host 'ALL FULL S18 TESTS PASSED' -ForegroundColor Green
