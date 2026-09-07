# encoding: utf-8
# E2E: Audit log coverage — her mutation log'a yaziyor mu?
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'

# ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
if (-not $env:ADMIN_EMAIL) {
    throw "ADMIN_EMAIL environment variable is required"
}
if (-not $env:ADMIN_PASSWORD) {
    throw "ADMIN_PASSWORD environment variable is required"
}

$KAPATILDI = 'KAPATILDI'

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
Write-Host '=== Setup: Yeni audit + HAYIR ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_AUDIT_LOG'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -Sv $sv
$aid = $audit.id
Write-Host "  audit: $aid"

# HAYIR
$answersBody = @{ answers = @{ '1' = 'HAYIR' }; expected_version = $audit.version } | ConvertTo-Json
$audit = Send-Json -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $answersBody -Sv $sv
Write-Host "  HAYIR eklendi: state=$($audit.state)"

Write-Host ''
Write-Host '=== Test 1: update_answers log ===' -ForegroundColor Cyan
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$answerUpdate = $log | Where-Object { $_.action -eq 'answer_update' }
if (-not $answerUpdate) {
    Write-Host "  Actions in log:" -ForegroundColor Yellow
    $log | ForEach-Object { Write-Host "    $($_.action)" }
    throw "FAIL: answer_update loglanmadi"
}
Write-Host "  OK: answer_update bulundu" -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 2: update_audit_meta log ===' -ForegroundColor Cyan
# AuditMetaUpdate AuditCreate'i inherit ediyor, tüm alanlar required
# (model_fields_set ile sadece gercekten degisenler log'a yazilir)
$metaBody = @{
    restaurant_name = 'TEST_AUDIT_LOG'
    address = 'a'
    audit_date = '2026-08-13'
    denetci = 'Yeni Denetci'
    expected_version = $audit.version
} | ConvertTo-Json
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid" -Method Patch -Body $metaBody -Sv $sv
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$metaUpdate = $log | Where-Object { $_.action -eq 'meta_update' }
if (-not $metaUpdate) { throw "FAIL: meta_update loglanmadi" }
Write-Host "  OK: meta_update bulundu, before.denetci=$($metaUpdate.before.denetci), after.denetci=$($metaUpdate.after.denetci)" -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 3: update_audit_declarations log ===' -ForegroundColor Cyan
$decBody = @{ declarations = @{ '1' = @{ decision = 'APPROVED'; commitment = 'X' } } } | ConvertTo-Json
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid/declarations" -Method Patch -Body $decBody -Sv $sv
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$decUpdate = $log | Where-Object { $_.action -eq 'declaration_update' }
if (-not $decUpdate) { throw "FAIL: declaration_update loglanmadi" }
Write-Host "  OK: declaration_update bulundu" -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 4: update_dof log (KAPATILDI) ===' -ForegroundColor Cyan
# Once audit'i submit edip DOF_OPEN'a dusurmeliyiz
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid/submit" -Method Post -Body '{}' -Sv $sv
$dofBody = @{ status = $KAPATILDI; notes = 'kanit yuklendi' } | ConvertTo-Json
$null = Send-Json -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $dofBody -Sv $sv
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$dofClose = $log | Where-Object { $_.action -eq 'dof_close' }
if (-not $dofClose) {
    Write-Host "  dof-related actions in log:" -ForegroundColor Yellow
    $log | Where-Object { $_.action -like 'dof*' } | ForEach-Object { Write-Host "    $($_.action)" }
    throw "FAIL: dof_close loglanmadi"
}
Write-Host "  OK: dof_close bulundu" -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 5: export_excel log ===' -ForegroundColor Cyan
# Excel export icin audit DOF_CLOSED veya FINAL olmali (S18 guard)
# Simdi zaten DOF_CLOSED olmali
$outFile = "$env:TEMP\audit_log_test.xlsx"
try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$aid/export/excel" -Method Get -WebSession $sv -OutFile $outFile -ErrorAction Stop
} catch {
    Write-Host "  (excel export hatasi, muhtemelen state guard: $_)" -ForegroundColor Yellow
}
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$excelExport = $log | Where-Object { $_.action -eq 'export_excel' }
if (-not $excelExport) {
    Write-Host "  export actions in log:" -ForegroundColor Yellow
    $log | Where-Object { $_.action -like 'export*' } | ForEach-Object { Write-Host "    $($_.action)" }
    throw "FAIL: export_excel loglanmadi"
}
Write-Host "  OK: export_excel bulundu" -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 6: export_pdf log ===' -ForegroundColor Cyan
$outFile2 = "$env:TEMP\audit_log_test.pdf"
try {
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$aid/export/pdf" -Method Get -WebSession $sv -OutFile $outFile2 -ErrorAction Stop
} catch {
    Write-Host "  (pdf export hatasi: $_)" -ForegroundColor Yellow
}
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$pdfExport = $log | Where-Object { $_.action -eq 'export_pdf' }
if (-not $pdfExport) { throw "FAIL: export_pdf loglanmadi" }
Write-Host "  OK: export_pdf bulundu" -ForegroundColor Green

# Cleanup
Remove-Item $outFile, $outFile2 -ErrorAction SilentlyContinue

Write-Host ''
Write-Host 'AUDIT LOG COVERAGE E2E PASSED' -ForegroundColor Green
exit 0
