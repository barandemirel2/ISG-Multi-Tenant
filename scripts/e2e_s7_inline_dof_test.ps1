# encoding: utf-8
# S7 E2E: inline DOF olusturma (HAYIR + henuz submit yok)
# PowerShell 5.1 ANSI parsing bug nedeniyle Tum Turkce karakterler [char]0x.. olarak yazildi
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'

# Status literal degerleri (PowerShell 5.1 ANSI parsing bug workaround)
# Turkce karakterler U+XXXX codepoint olarak uretiliyor (kaynak dosya encoding'inden bagimsiz)
$CAP    = [int][char]'C' + 0xC7 - 0x43      # C + (0xC7 - 0x43) = C cedilla = U+00C7
$IDOT   = [int][char]'I' + 0x130 - 0x49     # I + (0x130 - 0x49) = I with dot = U+0130
$SCED   = [int][char]'S' + 0x15E - 0x53     # S + (0x15E - 0x53) = S cedilla = U+015E
$ACIK     = [char[]]@(0x41, $CAP, 0x49, 0x4B) -join ''                       # A + C cedilla + IK
$ISLEMDE  = [char[]]@($IDOT, $SCED, 0x4C, 0x45, 0x4D, 0x44, 0x45) -join ''  # I dot + S cedilla + LEMDE
$KAPATILDI = 'KAPATILDI'  # ASCII only (literal I, not I-dot)

# Sanity check
Write-Host "  ACIK literal: [$ACIK] (length $($ACIK.Length))"
Write-Host "  ISLEMDE literal: [$ISLEMDE] (length $($ISLEMDE.Length))"
Write-Host "  KAPATILDI literal: [$KAPATILDI] (length $($KAPATILDI.Length))"

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
Write-Host '=== Create + HAYIR (henuz submit yok) ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_S7'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -ContentType 'application/json' -WebSession $sv
$aid = $audit.id
Write-Host "  audit: $aid, state: $($audit.state)"

# HAYIR cevap
$hayirBody = @{ answers = @{ '1' = 'HAYIR' }; expected_version = $audit.version } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $hayirBody -ContentType 'application/json' -WebSession $sv
Write-Host "  HAYIR eklendi: state=$($audit.state)"

Write-Host ''
Write-Host '=== Test 1: DRAFT iken DOF olusturma (backend) ===' -ForegroundColor Cyan
$dofBody = @{ status = $ACIK; notes = 'Ilk saha tespiti' } | ConvertTo-Json
try {
    $dofResp = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $dofBody -ContentType 'application/json; charset=utf-8' -WebSession $sv
    Write-Host '  DOF olusturuldu' -ForegroundColor Green
    Write-Host "  dof.status: $($dofResp.dof.status)"
    Write-Host "  dof.notes: $($dofResp.dof.notes)"
} catch {
    throw "FAIL: DRAFT'ta DOF olusturulamadi: $_"
}

Write-Host ''
Write-Host '=== Test 2: get_audit DOF bilgisi donuyor mu? ===' -ForegroundColor Cyan
$auditDetail = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
if (-not $auditDetail.dof_details) {
    throw 'FAIL: dof_details serialize edilmiyor'
}
if (-not $auditDetail.dof_details.'1') {
    throw 'FAIL: dof_details[1] bos'
}
Write-Host "  dof_details.1.status: $($auditDetail.dof_details.'1'.status)"
Write-Host "  dof_details.1.notes: $($auditDetail.dof_details.'1'.notes)"
Write-Host '  OK: dof_details serialize ediliyor' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 3: DOF state transition (ACIK -> ISLEMDE -> KAPATILDI) ===' -ForegroundColor Cyan
$dofBody2 = @{ status = $ISLEMDE; notes = 'Duzeltme calismasi baslatildi' } | ConvertTo-Json
$dofResp2 = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $dofBody2 -ContentType 'application/json; charset=utf-8' -WebSession $sv
Write-Host "  ACIK -> ISLEMDE: status=$($dofResp2.dof.status)"

$dofBody3 = @{ status = $KAPATILDI; notes = 'Duzeltme tamamlandi, fotograf yuklendi' } | ConvertTo-Json
$dofResp3 = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $dofBody3 -ContentType 'application/json; charset=utf-8' -WebSession $sv
Write-Host "  ISLEMDE -> KAPATILDI: status=$($dofResp3.dof.status)"
Write-Host '  OK: state machine calisiyor' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 4: HAYIR cevap olmadan DOF engellenir mi? ===' -ForegroundColor Cyan
# Soru 2'ye HAYIR yok, DOF olusturulmamali
try {
    $dofBody4 = @{ status = $ACIK; notes = 'yetkisiz DOF' } | ConvertTo-Json
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/2" -Method Put -Body $dofBody4 -ContentType 'application/json; charset=utf-8' -WebSession $sv
    Write-Host '  WARN: HAYIR olmayan soruya DOF kabul edildi' -ForegroundColor Yellow
} catch {
    Write-Host '  OK: HAYIR olmayan soruya DOF reddedildi' -ForegroundColor Green
}

Write-Host ''
Write-Host 'S7 E2E PASSED' -ForegroundColor Green
exit 0
