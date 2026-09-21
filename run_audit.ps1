$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$ReportDir = Join-Path $Root "report"
$Log = Join-Path $ReportDir "audit.log"
$env:NO_COLOR = "1"
$env:FORCE_COLOR = "0"
$env:TERM = "dumb"
$env:CI = "1"
$Total = 2

Write-Host ""
Write-Host "============ AUDIT ============"
Write-Host ""

if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir | Out-Null
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$requirements = Join-Path $Root "requirements.txt"

if (-not (Test-Path $venvPython)) {
    Write-Host "[BLAD] Brak .venv - uruchom najpierw start_app.ps1 albo: py -3 -m venv .venv"
    exit 1
}

if (-not (Test-Path $requirements)) {
    Write-Host "[BLAD] Brak pliku requirements.txt"
    exit 1
}

Write-Host "Aktualizacja pip i instalacja pip-audit..."
& $venvPython -m pip install --quiet --upgrade pip pip-audit
if ($LASTEXITCODE -ne 0) {
    Write-Host "[BLAD] Nie udalo sie zainstalowac pip-audit"
    exit 1
}

Set-Content -LiteralPath $Log -Encoding UTF8 -Value @(
    "========================================",
    " AUDIT - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "========================================",
    ""
)

function Invoke-AuditStep {
    param(
        [int]$StepNo,
        [string]$Title,
        [string[]]$ArgumentList
    )

    Write-Host "[Krok $StepNo/$Total] $Title..."

    Add-Content -LiteralPath $Log -Encoding UTF8 -Value @(
        "--- Krok $StepNo/${Total}: $Title ---",
        (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
        ""
    )

    $stdout = Join-Path $env:TEMP "audit_stdout_$PID.log"
    $stderr = Join-Path $env:TEMP "audit_stderr_$PID.log"

    $process = Start-Process `
        -FilePath $venvPython `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $Root `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr

    $esc = [char]27
    $csi = [regex]::new("$([regex]::Escape($esc.ToString()))\[[0-?]*[ -/]*[@-~]")

    $lines = @()
    foreach ($path in @($stdout, $stderr)) {
        if (Test-Path -LiteralPath $path) {
            $lines += Get-Content -LiteralPath $path -Encoding UTF8 -ErrorAction SilentlyContinue
        }
    }

    $lines | ForEach-Object {
        $text = [string]$_
        $text = $csi.Replace($text, "")
        $text = $text -replace [string][char]0xFFFD, ""
        $text
    } | Where-Object {
        $_ -and
        $_ -notmatch '^System\.Management\.Automation\.RemoteException$'
    } | Add-Content -LiteralPath $Log -Encoding UTF8

    Add-Content -LiteralPath $Log -Encoding UTF8 -Value @("", "========================================", "")
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    return $process.ExitCode
}

$results = @(
    (Invoke-AuditStep 1 "pip-audit requirements.txt" @(
        "-m", "pip_audit", "-r", "requirements.txt", "--desc", "on", "--progress-spinner", "off"
    ))
    (Invoke-AuditStep 2 "pip-audit zainstalowane pakiety (.venv)" @(
        "-m", "pip_audit", "--local", "--desc", "on", "--progress-spinner", "off"
    ))
)

Write-Host ""
Write-Host "============ PODSUMOWANIE ============"
Write-Host ""

$anyFail = $false
for ($i = 0; $i -lt $Total; $i++) {
    $stepNo = $i + 1
    if ($results[$i] -eq 0) {
        Write-Host "  [$stepNo] PASS"
    } else {
        Write-Host "  [$stepNo] FAIL"
        $anyFail = $true
    }
}

Write-Host ""
Write-Host "  Log: $Log"
Write-Host ""

Add-Content -LiteralPath $Log -Encoding UTF8 -Value @(
    "",
    "========================================",
    " PODSUMOWANIE",
    "========================================",
    ""
)
for ($i = 0; $i -lt $Total; $i++) {
    $stepNo = $i + 1
    if ($results[$i] -eq 0) {
        Add-Content -LiteralPath $Log -Encoding UTF8 -Value "  [$stepNo] PASS"
    } else {
        Add-Content -LiteralPath $Log -Encoding UTF8 -Value "  [$stepNo] FAIL"
    }
}
Add-Content -LiteralPath $Log -Encoding UTF8 -Value ""

if ($anyFail) {
    Write-Host "[BLAD] Wykryto podatnosci albo blad audytu - sprawdz log."
    exit 1
}

Write-Host "[OK] Brak znanych podatnosci w zaleznosciach."
exit 0
