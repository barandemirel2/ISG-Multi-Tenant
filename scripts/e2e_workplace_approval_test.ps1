# encoding: utf-8
# E2E: Isveren Vekili Onay imzalama (S7.2)
# PS 5.1 ANSI workaround: Turkce karakterler U+XXXX codepoint ile uretiliyor
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'

# Unicode codepoint helper (kaynak dosya encoding'inden bagimsiz)
$CAP    = [int][char]'C' + 0xC7 - 0x43      # U+00C7 C-cedilla
$IDOT   = [int][char]'I' + 0x130 - 0x49     # U+0130 I-dot
$SCED   = [int][char]'S' + 0x15E - 0x53     # U+015E S-cedilla
$ACIK     = [char[]]@(0x41, $CAP, 0x49, 0x4B) -join ''
$ISLEMDE  = [char[]]@($IDOT, $SCED, 0x4C, 0x45, 0x4D, 0x44, 0x45) -join ''
$KAPATILDI = 'KAPATILDI'

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
Write-Host '=== Create + HAYIR + Submit (DOF_OPEN) ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_WA'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -ContentType 'application/json' -WebSession $sv
$aid = $audit.id
Write-Host "  audit: $aid"

# Soru 1 ve 2'ye HAYIR
$answersBody = @{ answers = @{ '1' = 'HAYIR'; '2' = 'HAYIR' }; expected_version = $audit.version } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $answersBody -ContentType 'application/json' -WebSession $sv
Write-Host "  HAYIR eklendi: state=$($audit.state)"

# Submit
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/submit" -Method Post -Body '{}' -ContentType 'application/json' -WebSession $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  submit sonrasi state: $($audit.state)"
if ($audit.state -ne 'DOF_OPEN') {
    throw "FAIL: submit sonrasi DOF_OPEN bekleniyordu, gelen: $($audit.state)"
}

Write-Host ''
Write-Host '=== Test 1: DRAFT/SUBMITTED state imzalanamaz ===' -ForegroundColor Cyan
# Yeni draft audit olustur, imzayi DRAFT'ta dene
$audit2Body = @{ restaurant_name = 'TEST_WA_DRAFT'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit2 = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $audit2Body -ContentType 'application/json' -WebSession $sv
$aid2 = $audit2.id
try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid2/workplace-approval/sign" -Method Post -Body '{"rep_name":"Test"}' -ContentType 'application/json' -WebSession $sv
    throw "FAIL: DRAFT imzalanmamaliydi"
} catch {
    if ($_.Exception.Response.StatusCode -ne 409) {
        throw "FAIL: 409 bekleniyordu, gelen: $($_.Exception.Response.StatusCode)"
    }
    Write-Host '  OK: DRAFT imza reddedildi (409)' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== Test 2: rep_name zorunlu ===' -ForegroundColor Cyan
try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/workplace-approval/sign" -Method Post -Body '{"rep_name":""}' -ContentType 'application/json' -WebSession $sv
    throw "FAIL: bos rep_name kabul edilmemeliydi"
} catch {
    if ($_.Exception.Response.StatusCode -ne 422 -and $_.Exception.Response.StatusCode -ne 400) {
        throw "FAIL: 422/400 bekleniyordu, gelen: $($_.Exception.Response.StatusCode)"
    }
    Write-Host '  OK: bos rep_name reddedildi' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== Test 3: Basarili imzalama ===' -ForegroundColor Cyan
$signBody = @{
    decisions = @{
        '1' = @{ decision = 'APPROVED'; commitment = '15 gun icinde giderilecek' }
        '2' = @{ decision = 'DISPUTED'; reason = 'Bu bulgu 2 ay onceki denetimde yoktu, kosullar degisti' }
    }
    rep_name = 'Ahmet Yilmaz'
    rep_title = 'Restoran Muduru'
    declaration_date = '2026-08-13'
} | ConvertTo-Json -Depth 5
$signResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/workplace-approval/sign" -Method Post -Body $signBody -ContentType 'application/json; charset=utf-8' -WebSession $sv
Write-Host "  signed_at: $($signResp.declarations_meta.signed_at)"
Write-Host "  signed_by_rep_name: $($signResp.declarations_meta.signed_by_rep_name)"
Write-Host "  state sonrasi: $($signResp.state)"

if (-not $signResp.declarations_meta.signed_at) {
    throw "FAIL: signed_at serialize edilmedi"
}
if ($signResp.declarations_meta.signed_by_rep_name -ne 'Ahmet Yilmaz') {
    throw "FAIL: signed_by_rep_name yanlis"
}
Write-Host '  OK: imza kaydedildi' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 4: Idempotency (zaten imzali) ===' -ForegroundColor Cyan
try {
    $null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/workplace-approval/sign" -Method Post -Body $signBody -ContentType 'application/json; charset=utf-8' -WebSession $sv
    throw "FAIL: 2. imza kabul edilmemeliydi"
} catch {
    if ($_.Exception.Response.StatusCode -ne 409) {
        throw "FAIL: 409 bekleniyordu, gelen: $($_.Exception.Response.StatusCode)"
    }
    Write-Host '  OK: 2. imza reddedildi (idempotent)' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== Test 5: Audit log workplace_approval_signed ===' -ForegroundColor Cyan
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
Write-Host "  log count: $($log.Count)"
$signed = $log | Where-Object { $_.action -eq 'workplace_approval_signed' }
if (-not $signed) {
    Write-Host "  Actions in log:" -ForegroundColor Yellow
    $log | ForEach-Object { Write-Host "    $($_.action)" }
    throw "FAIL: workplace_approval_signed loglanmadi"
}
Write-Host "  log.user_name: $($signed.user_name)"
Write-Host "  log.action: $($signed.action)"
Write-Host "  log.after.state_after: $($signed.after.state_after)"
Write-Host '  OK: audit log dogru' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 6: Tum DOF kapaninca sign DOF_CLOSED transition yapar ===' -ForegroundColor Cyan
# Yeni audit: HAYIR + submit + KAPATILDI + imzala → DOF_CLOSED
$audit3Body = @{ restaurant_name = 'TEST_WA_TRANS'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $audit3Body -ContentType 'application/json' -WebSession $sv
$aid3 = $audit3.id
$answersBody3 = @{ answers = @{ '1' = 'HAYIR' }; expected_version = $audit3.version } | ConvertTo-Json
$audit3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid3/answers" -Method Put -Body $answersBody3 -ContentType 'application/json' -WebSession $sv
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid3/submit" -Method Post -Body '{}' -ContentType 'application/json' -WebSession $sv
$audit3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid3" -Method Get -WebSession $sv
Write-Host "  submit sonrasi: $($audit3.state)"

# Tum DOF'leri kapat (soru 1)
$dofBody = @{ status = $KAPATILDI; notes = 'Duzeltme tamamlandi'; resolution_note = 'kanit yuklendi' } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid3/1" -Method Put -Body $dofBody -ContentType 'application/json; charset=utf-8' -WebSession $sv
Write-Host '  DOF KAPATILDI'

# Audit'i tekrar cek, DOF_CLOSED olmali
$audit3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid3" -Method Get -WebSession $sv
Write-Host "  KAPATILDI sonrasi state: $($audit3.state)"

# Imzala
$signBody3 = @{
    decisions = @{ '1' = @{ decision = 'APPROVED' } }
    rep_name = 'Mehmet Demir'
    rep_title = 'Mudur'
} | ConvertTo-Json -Depth 4
$signResp3 = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid3/workplace-approval/sign" -Method Post -Body $signBody3 -ContentType 'application/json; charset=utf-8' -WebSession $sv
Write-Host "  sign sonrasi state: $($signResp3.state)"

if ($signResp3.state -ne 'DOF_CLOSED') {
    throw "FAIL: tum DOF kapali + sign sonrasi DOF_CLOSED bekleniyordu, gelen: $($signResp3.state)"
}
Write-Host '  OK: auto-transition DOF_OPEN -> DOF_CLOSED calisti' -ForegroundColor Green

Write-Host ''
Write-Host 'S7.2 E2E PASSED' -ForegroundColor Green
exit 0
