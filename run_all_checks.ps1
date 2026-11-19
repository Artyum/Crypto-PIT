param(
    [Parameter(Position = 0)]
    [string]$TestTarget,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
Set-Location $Root

try {
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    $OutputEncoding = [Text.Encoding]::UTF8
} catch {}

$lintScript = Join-Path $Root "run_lint_check.ps1"
$testsScript = Join-Path $Root "run_tests.ps1"
$auditScript = Join-Path $Root "run_audit.ps1"

foreach ($path in @($lintScript, $testsScript, $auditScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "[BLAD] Brak skryptu: $path" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "  LINT + TESTY + AUDYT"
Write-Host "========================================"
Write-Host ""

$lintExit = 0
$testExit = 0
$auditExit = 0

Write-Host ">>> Lint check"
Write-Host ""
& $lintScript
$lintExit = $LASTEXITCODE

Write-Host ""
Write-Host ">>> Testy"
Write-Host ""
if ($TestTarget) {
    & $testsScript $TestTarget @PytestArgs
} else {
    & $testsScript @PytestArgs
}
$testExit = $LASTEXITCODE

Write-Host ""
Write-Host ">>> Audit"
Write-Host ""
& $auditScript
$auditExit = $LASTEXITCODE

Write-Host ""
Write-Host "========================================"
Write-Host "  PODSUMOWANIE"
Write-Host "========================================"
Write-Host ""

function Show-StepResult([string]$Label, [int]$ExitCode) {
    if ($ExitCode -eq 0) {
        Write-Host "  $Label : PASS" -ForegroundColor Green
    } else {
        Write-Host "  $Label : FAIL (kod $ExitCode)" -ForegroundColor Red
    }
}

Show-StepResult "Lint" $lintExit
Show-StepResult "Testy" $testExit
Show-StepResult "Audit" $auditExit

Write-Host ""
Write-Host "  Logi: report\lint_check.log, report\audit.log"
Write-Host ""

$overall = $lintExit -bor $testExit -bor $auditExit
if ($overall -ne 0) {
    Write-Host "[BLAD] Co najmniej jeden etap zakonczyl sie bledem." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Wszystkie etapy zakonczone pomyslnie." -ForegroundColor Green
exit 0