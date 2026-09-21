$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$ReportDir = Join-Path $Root "report"
$Log = Join-Path $ReportDir "lint_check.log"
$env:NO_COLOR = "1"
$env:FORCE_COLOR = "0"
$env:TERM = "dumb"
$env:CI = "1"
$Total = 4

Write-Host ""
Write-Host "============ LINT CHECK ============"
Write-Host ""

if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir | Out-Null
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
$venvScripts = Join-Path $Root ".venv\Scripts"
$requirementsDev = Join-Path $Root "requirements.txt"

if (-not (Test-Path $venvPython)) {
    Write-Host "[BLAD] Brak .venv - uruchom najpierw start_app.ps1 albo: py -3 -m venv .venv"
    exit 1
}

# Narzedzia lint w .venv (ruff, basedpyright)
& $venvPython -m pip install --quiet -r $requirementsDev
if ($LASTEXITCODE -ne 0) {
    Write-Host "[BLAD] Nie udalo sie zainstalowac requirements.txt"
    exit 1
}

$ruff = Join-Path $venvScripts "ruff.exe"
$basedpyright = Join-Path $venvScripts "basedpyright.exe"

Set-Content -LiteralPath $Log -Encoding UTF8 -Value @(
    "========================================",
    " LINT CHECK - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "========================================",
    ""
)

function Invoke-LintStep {
    param(
        [int]$StepNo,
        [string]$Title,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    Write-Host "[Krok $StepNo/$Total] $Title..."

    Add-Content -LiteralPath $Log -Encoding UTF8 -Value @(
        "--- Krok $StepNo/${Total}: $Title ---",
        (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
        ""
    )

    $stdout = Join-Path $env:TEMP "lint_stdout_$PID.log"
    $stderr = Join-Path $env:TEMP "lint_stderr_$PID.log"

    $startParams = @{
        FilePath               = $FilePath
        WorkingDirectory       = $Root
        NoNewWindow            = $true
        Wait                   = $true
        PassThru               = $true
        RedirectStandardOutput = $stdout
        RedirectStandardError  = $stderr
    }
    if ($ArgumentList -and $ArgumentList.Count -gt 0) {
        $startParams.ArgumentList = $ArgumentList
    }
    $process = Start-Process @startParams

    $esc = [char]27
    $csi = [regex]::new("$([regex]::Escape($esc.ToString()))\[[0-?]*[ -/]*[@-~]")
    $osc = [regex]::new("$([regex]::Escape($esc.ToString()))\][^\x07$([regex]::Escape($esc.ToString()))]*(?:\x07|$([regex]::Escape($esc.ToString()))\\)")
    $oscOrphan = [regex]::new('\]8;[^\s]*?\\([^\\]+?)\\]8;;\\')

    $lines = @()
    foreach ($path in @($stdout, $stderr)) {
        if (Test-Path -LiteralPath $path) {
            $lines += Get-Content -LiteralPath $path -Encoding UTF8 -ErrorAction SilentlyContinue
        }
    }

    $lines | ForEach-Object {
        $text = [string]$_
        $text = $csi.Replace($text, "")
        $text = $osc.Replace($text, "")
        $text = $oscOrphan.Replace($text, '${1}')
        $text = $text -replace [string][char]0xFFFD, ""
        $text
    } | Where-Object {
        $_ -and
        $_ -notmatch '^System\.Management\.Automation\.RemoteException$' -and
        $_ -notmatch '^Reformatting \d+/\d+ files'
    } | Add-Content -LiteralPath $Log -Encoding UTF8

    Add-Content -LiteralPath $Log -Encoding UTF8 -Value @("", "========================================", "")
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    return $process.ExitCode
}

$results = @(
    (Invoke-LintStep 1 "ruff format" $ruff @("format", ".", "--color=never"))
    (Invoke-LintStep 2 "ruff check --fix-only --show-fixes" $ruff @("check", ".", "--fix-only", "--show-fixes", "--color=never"))
    (Invoke-LintStep 3 "ruff check --output-format=concise" $ruff @("check", ".", "--output-format=concise", "--color=never"))
    (Invoke-LintStep 4 "basedpyright" $basedpyright @())
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
    Write-Host "[BLAD] Niektore kroki zakonczone bledem - sprawdz log."
    exit 1
}

Write-Host "[OK] Wszystkie kroki zakonczone pomyslnie."
exit 0
