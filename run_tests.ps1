param(
    [Parameter(Position = 0)]
    [string]$TestTarget,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

function Write-Step([string]$Message, [string]$Color = 'Cyan') {
    Write-Host $Message -ForegroundColor $Color
}

function Fail([string]$Message) {
    Write-Host "[BLAD] $Message" -ForegroundColor Red
    exit 1
}

function Resolve-TestFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TestArg,
        [Parameter(Mandatory = $true)]
        [string]$TestRoot
    )

    $normalized = $TestArg -replace '/', '\'
    if (Test-Path -LiteralPath $normalized) {
        return (Resolve-Path -LiteralPath $normalized).Path
    }

    $underRoot = Join-Path $TestRoot $normalized
    if (Test-Path -LiteralPath $underRoot) {
        return (Resolve-Path -LiteralPath $underRoot).Path
    }

    if ([System.IO.Path]::GetExtension($TestArg) -ieq '.py') {
        $filter = [System.IO.Path]::GetFileName($TestArg)
    } else {
        $filter = "$normalized.py"
        if ($filter -match '[\\/]') {
            $filter = [System.IO.Path]::GetFileName($filter)
        }
    }

    $found = Get-ChildItem -Path $TestRoot -Recurse -Filter $filter -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) {
        return $found.FullName
    }
    return $null
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Pip = Join-Path $Root '.venv\Scripts\pip.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    Fail "Nie znaleziono .venv (oczekiwano: $Python)`n       Utworz: python -m venv .venv"
}

Write-Step '[VENV] Uzywam .venv\Scripts\python.exe'
Write-Step 'Instalowanie zaleznosci...' 'Yellow'
& $Pip install -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$env:PY_COLORS = '1'
$env:FORCE_COLOR = '1'
$TestRoot = Join-Path $Root 'tests'
$runCoverage = $true

Write-Host ''
if ($TestTarget) {
    $testFile = Resolve-TestFile -TestArg $TestTarget -TestRoot $TestRoot
    if (-not $testFile) {
        Fail "Nie znaleziono pliku testow: $TestTarget`n       Szukano w: $TestRoot"
    }
    if (-not (Test-Path -LiteralPath $testFile)) {
        Fail "Plik testow nie istnieje: $testFile"
    }
    Write-Step "===== Uruchamianie: $testFile =====" 'Magenta'
    $runCoverage = $false
    & $Python -m pytest $testFile -v --tb=line --color=yes @PytestArgs
} else {
    Write-Step '===== Uruchamianie wszystkich testow =====' 'Magenta'
    & $Python -m pytest tests/ -v --tb=line --color=yes --cov=crypto_pit --cov-report=term-missing @PytestArgs
}

$pytestExit = $LASTEXITCODE

Write-Host ''
if ($runCoverage) {
    Write-Step '[SPRZATANIE] Usuwanie pliku .coverage...' 'Yellow'
    $coverageFile = Join-Path $Root '.coverage'
    if (Test-Path -LiteralPath $coverageFile) {
        Remove-Item -LiteralPath $coverageFile -Force
        Write-Step '[OK] .coverage usuniety.' 'Green'
    } else {
        Write-Step '[INFO] .coverage nie istnieje - pomijam.' 'DarkGray'
    }
}

exit $pytestExit
