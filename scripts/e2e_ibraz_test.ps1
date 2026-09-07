# encoding: utf-8
# E2E: Ibraz belgesi (S20) — mahkeme format PDF + QR + hash + 4 imza kutusu
# PS 5.1 workaround: -Body bytes + 'application/json; charset=utf-8' zorunlu
# (yoksa PS ISO-8859-1 gönderiyor, Turkce karakterler bozuluyor)
$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:8000'

# ─── Credential (env-var; hardcoded fallback YOK) ───────────────────────
if (-not $env:ADMIN_EMAIL) {
    throw "ADMIN_EMAIL environment variable is required"
}
if (-not $env:ADMIN_PASSWORD) {
    throw "ADMIN_PASSWORD environment variable is required"
}

# UTF-8 byte olarak gonder helper
function Send-Json {
    param([string]$Uri, [string]$Method, [string]$Body, $Sv)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
    return Invoke-RestMethod -Uri $Uri -Method $Method -Body $bytes -ContentType 'application/json; charset=utf-8' -WebSession $Sv
}

$KAPATILDI = 'KAPATILDI'
$CAP = ([int][char]'C') + 0xC7 - 0x43
$ACIK = [char[]]@(0x41, $CAP, 0x49, 0x4B) -join ''

# Turkce karakter iceren audit alanlari (kaynak dosya encoding'inden bagimsiz)
$CANKAYA = [char[]]@(0xC7, 0x61, 0x6E, 0x6B, 0x61, 0x79, 0x61) -join ''
$ATATURK = [char[]]@(0x41, 0x74, 0x61, 0x74, 0xFC, 0x72, 0x6B) -join ''  # ü = U+00FC

Write-Host '=== Login ===' -ForegroundColor Cyan
$loginBody = @{ email = $env:ADMIN_EMAIL; password = $env:ADMIN_PASSWORD } | ConvertTo-Json -Compress
$loginBytes = [System.Text.Encoding]::UTF8.GetBytes($loginBody)
$null = Invoke-RestMethod -Uri "$BaseUrl/api/auth/login" -Method Post -Body $loginBytes -ContentType 'application/json; charset=utf-8' -SessionVariable sv
Write-Host '  OK'

Write-Host ''
Write-Host '=== Setup: HAYIR + Submit + KAPATILDI + Sign ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_IBRAZ'; address = "$ATATURK Cad. 25"; city = 'Ankara'; district = $CANKAYA; brand = 'TAB Burger'; audit_date = '2026-08-13'; denetci = 'Mehmet Uzman' } | ConvertTo-Json
$audit = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -Sv $sv
$aid = $audit.id
Write-Host "  audit: $aid"

# HAYIR
$answersBody = @{ answers = @{ '1' = 'HAYIR'; '2' = 'HAYIR' }; expected_version = $audit.version } | ConvertTo-Json
$audit = Send-Json -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $answersBody -Sv $sv
Write-Host "  HAYIR eklendi: state=$($audit.state)"

# Submit
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid/submit" -Method Post -Body '{}' -Sv $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  submit sonrasi: $($audit.state)"

# Tum DOF'leri kapat
$dof1 = @{ status = $KAPATILDI; notes = 'Fotograf kanit yuklendi'; resolution_note = 'gorsel kanit mevcut' } | ConvertTo-Json
$null = Send-Json -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $dof1 -Sv $sv
$dof2 = @{ status = $KAPATILDI; notes = 'Egitim verildi'; resolution_note = 'katilimci listesi eklendi' } | ConvertTo-Json
$null = Send-Json -Uri "$BaseUrl/api/dofs/$aid/2" -Method Put -Body $dof2 -Sv $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  tum DOF'ler kapali sonrasi: $($audit.state)"
if ($audit.state -ne 'DOF_CLOSED') { throw "FAIL: DOF_CLOSED bekleniyordu" }

# Sign
$signBody = @{
    decisions = @{
        '1' = @{ decision = 'APPROVED'; commitment = '15 gun icinde giderilecek' }
        '2' = @{ decision = 'DISPUTED'; reason = 'Bu bulgu 2 ay onceki denetimde yoktu, kosullar degisti' }
    }
    rep_name = 'Hasan Bey'
    rep_title = 'Restoran Muduru'
    declaration_date = '2026-08-13'
} | ConvertTo-Json -Depth 5
$null = Send-Json -Uri "$BaseUrl/api/audits/$aid/workplace-approval/sign" -Method Post -Body $signBody -Sv $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  imza sonrasi: state=$($audit.state), signed=$($audit.declarations_meta.signed_at)"

Write-Host ''
Write-Host '=== Test 1: DRAFT audit icin ibraz reddedilir ===' -ForegroundColor Cyan
$audit2Body = @{ restaurant_name = 'TEST_IBRAZ_DRAFT'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit2 = Send-Json -Uri "$BaseUrl/api/audits" -Method Post -Body $audit2Body -Sv $sv
$aid2 = $audit2.id
try {
    $null = Invoke-WebRequest -Uri "$BaseUrl/api/audits/$aid2/ibraz" -Method Get -WebSession $sv -ErrorAction Stop
    throw "FAIL: DRAFT ibraz kabul edilmemeliydi"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -ne 409) {
        throw "FAIL: 409 bekleniyordu, gelen: $code"
    }
    Write-Host '  OK: DRAFT ibraz reddedildi (409)' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== Test 2: Signed audit icin PDF uret ===' -ForegroundColor Cyan
$outFile = "$env:TEMP\ibraz_test.pdf"
try {
    # Invoke-WebRequest binary data ile PassThru sorun cikarabilir;
    # sadece -OutFile ile indir, sonra dosyayi kontrol et
    Invoke-WebRequest -Uri "$BaseUrl/api/audits/$aid/ibraz" -Method Get -WebSession $sv -OutFile $outFile -ErrorAction Stop

    if ((Test-Path $outFile) -eq $false) {
        throw "FAIL: PDF dosyasi olusturulamadi"
    }
    $fileInfo = Get-Item $outFile
    if ($fileInfo.Length -lt 1000) {
        throw "FAIL: PDF dosyasi cok kucuk ($($fileInfo.Length) bytes)"
    }
    Write-Host "  PDF boyut: $($fileInfo.Length) bytes"
    Write-Host '  OK: PDF uretildi' -ForegroundColor Green
} catch {
    throw "FAIL: ibraz istegi basarisiz: $_"
}

Write-Host ''
Write-Host '=== Test 3: PDF magic bytes ===' -ForegroundColor Cyan
$firstBytes = Get-Content $outFile -Encoding Byte -TotalCount 8
$hex = ($firstBytes | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
Write-Host "  Ilk 8 byte hex: $hex"
if ($firstBytes[0] -ne 0x25 -or $firstBytes[1] -ne 0x50 -or $firstBytes[2] -ne 0x44 -or $firstBytes[3] -ne 0x46) {
    throw "FAIL: PDF magic bytes yanlis (25 50 44 46 bekleniyordu)"
}
Write-Host '  OK: PDF magic bytes gecerli' -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 4: PDF sanity (trailer + object count) ===' -ForegroundColor Cyan
# reportlab compressed stream'ler kullaniyor; raw byte'da metin aramak
# saglikli degil. Bunun yerine PDF yapisal sanity check: %%EOF trailer
# ve en az 1 object tanimi olmali.
$raw = [System.IO.File]::ReadAllBytes($outFile)
$eof = $raw | Select-Object -Last 1024
$eofStr = [System.Text.Encoding]::ASCII.GetString($eof)
if (-not $eofStr.Contains('%%EOF')) {
    throw "FAIL: PDF %%EOF trailer yok"
}
Write-Host "  + %%EOF trailer bulundu" -ForegroundColor Green
$objCount = ([regex]::Matches([System.Text.Encoding]::ASCII.GetString($raw), '\d+ \d+ obj')).Count
Write-Host "  + Object sayisi: $objCount"
if ($objCount -lt 5) {
    throw "FAIL: PDF cok az object iceriyor ($objCount)"
}
Write-Host "  OK: PDF yapisal olarak gecerli" -ForegroundColor Green

Write-Host ''
Write-Host '=== Test 5: Audit log export_ibraz ===' -ForegroundColor Cyan
$logResp = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/audit-log" -Method Get -WebSession $sv
$log = if ($logResp.items) { $logResp.items } else { $logResp }
$ibrazLog = $log | Where-Object { $_.action -eq 'export_ibraz' }
if (-not $ibrazLog) {
    throw "FAIL: export_ibraz loglanmadi"
}
Write-Host "  log.user_name: $($ibrazLog.user_name)"
Write-Host "  log.after.ibraz_hash: $($ibrazLog.after.ibraz_hash)"
Write-Host "  log.ip: $($ibrazLog.ip)"
Write-Host '  OK: audit log dogru' -ForegroundColor Green

# Cleanup
Remove-Item $outFile -ErrorAction SilentlyContinue

Write-Host ''
Write-Host 'IBRAZ E2E PASSED' -ForegroundColor Green
exit 0
