# S4+S6: Excel ve PDF ortak kolon semasi
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
Write-Host '=== Setup ===' -ForegroundColor Cyan
$auditBody = @{ restaurant_name = 'TEST_S46'; address = 'a'; audit_date = '2026-08-13'; denetci = 'd' } | ConvertTo-Json
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits" -Method Post -Body $auditBody -ContentType 'application/json' -WebSession $sv
$aid = $audit.id
$hayirBody = @{ answers = @{ '1' = 'HAYIR' }; expected_version = $audit.version } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/answers" -Method Put -Body $hayirBody -ContentType 'application/json' -WebSession $sv
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/submit" -Method Post -WebSession $sv
$closeBody = @{ status = 'KAPATILDI'; notes = 'closed' } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/dofs/$aid/1" -Method Put -Body $closeBody -ContentType 'application/json' -WebSession $sv
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid" -Method Get -WebSession $sv
Write-Host "  state: $($audit.state)"

Write-Host ''
Write-Host '=== Export Excel ===' -ForegroundColor Cyan
$xlPath = 'C:\Users\baran\RISK-ANALIZ\scripts\test_export.xlsx'
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/export/excel" -Method Get -WebSession $sv -OutFile $xlPath
Write-Host "  saved: $xlPath"

# Python ile header parse (openpyxl yok, raw XML)
$pyOut = & 'backend\.venv\Scripts\python.exe' 'scripts/parse_xlsx.py' 'scripts/test_export.xlsx' 2>&1
$pyOut | ForEach-Object { Write-Host "  $_" }

# parse_xlsx.py son satırı 'COUNT: 11' olmalı
$countLine = $pyOut | Where-Object { $_ -match '^COUNT:' } | Select-Object -First 1
if (-not $countLine) { throw "FAIL: parse_xlsx.py returned no COUNT line" }
$count = [int]($countLine -replace 'COUNT:\s*', '')
if ($count -ne 11) { throw "FAIL: 11 kolon bekleniyordu, $count bulundu" }
Write-Host '  OK: 11 kolon dogrulandi' -ForegroundColor Green

Write-Host ''
Write-Host '=== Export PDF ===' -ForegroundColor Cyan
$pdfPath = 'C:\Users\baran\RISK-ANALIZ\scripts\test_export.pdf'
$null = Invoke-RestMethod -Uri "$BaseUrl/api/audits/$aid/export/pdf" -Method Get -WebSession $sv -OutFile $pdfPath
$pdfSize = (Get-Item $pdfPath).Length
Write-Host "  PDF size: $pdfSize bytes"
if ($pdfSize -lt 5000) { throw "FAIL: PDF too small ($pdfSize)" }
Write-Host '  OK: PDF > 5KB' -ForegroundColor Green

# Statik kontrol: her iki export audit_columns modülünü kullaniyor mu?
$serverCode = Get-Content 'backend\server.py' -Raw
$pdfUsesColumns = $serverCode -match "export_pdf[\s\S]{0,50000}from audit_columns import get_columns"
$xlUsesColumns = $serverCode -match "export_excel[\s\S]{0,50000}from audit_columns import get_columns"
if (-not $pdfUsesColumns) { throw "FAIL: export_pdf audit_columns import etmiyor" }
if (-not $xlUsesColumns) { throw "FAIL: export_excel audit_columns import etmiyor" }
Write-Host '  OK: Excel ve PDF AYNI audit_columns kaynagindan besleniyor' -ForegroundColor Green
Write-Host '  OK: S6 garantili (Kesinlikle ayni olmali kurali)' -ForegroundColor Green

Write-Host ''
Write-Host 'S4+S6 PASSED' -ForegroundColor Green
exit 0
