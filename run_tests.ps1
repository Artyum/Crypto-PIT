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

$env:NO_COLOR = '1'
$env:FORCE_COLOR = '0'
$env:TERM = 'dumb'
$env:CI = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$ReportDir = Join-Path $Root 'report'
$Log = Join-Path $ReportDir 'tests.log'
if (-not (Test-Path -LiteralPath $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir | Out-Null
}

$TestRoot = Join-Path $Root 'tests'
$runCoverage = -not [bool]$TestTarget
$pytestTarget = 'tests/'
$stepTitle = 'pytest tests/'

Write-Host ''
if ($TestTarget) {
    $testFile = Resolve-TestFile -TestArg $TestTarget -TestRoot $TestRoot
    if (-not $testFile) {
        Fail "Nie znaleziono pliku testow: $TestTarget`n       Szukano w: $TestRoot"
    }
    if (-not (Test-Path -LiteralPath $testFile)) {
        Fail "Plik testow nie istnieje: $testFile"
    }
    $pytestTarget = $testFile
    if ($testFile.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        $pytestTarget = $testFile.Substring($Root.Length).TrimStart('\', '/')
    }
    $stepTitle = "pytest $pytestTarget"
}

Set-Content -LiteralPath $Log -Encoding UTF8 -Value @(
    '========================================',
    " TESTY - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    '========================================',
    ''
)

function Invoke-TestStep {
    param(
        [int]$StepNo,
        [string]$Title,
        [string[]]$ArgumentList
    )

    Write-Host "[Krok $StepNo/1] $Title..."

    Add-Content -LiteralPath $Log -Encoding UTF8 -Value @(
        "--- Krok ${StepNo}/1: $Title ---",
        (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
        ''
    )

    $stdout = Join-Path $env:TEMP "tests_stdout_$PID.log"
    $stderr = Join-Path $env:TEMP "tests_stderr_$PID.log"
    $commandLine = ($ArgumentList | ForEach-Object {
        if ($_ -match '[\s"]') { '"{0}"' -f ($_ -replace '"', '\"') } else { $_ }
    }) -join ' '

    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList $commandLine `
        -WorkingDirectory $Root `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr
    $exitCode = $process.ExitCode

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
        $text = $csi.Replace($text, '')
        $text = $osc.Replace($text, '')
        $text = $oscOrphan.Replace($text, '${1}')
        $text = $text -replace [string][char]0xFFFD, ''
        $text
    } | Where-Object {
        $_ -and
        $_ -notmatch '^System\.Management\.Automation\.RemoteException$'
    } | Add-Content -LiteralPath $Log -Encoding UTF8

    Add-Content -LiteralPath $Log -Encoding UTF8 -Value @('', '========================================', '')
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    return $exitCode
}

$launchArgs = @(
    '-m', 'pytest', $pytestTarget,
    '-v', '--tb=line', '--color=no'
)
if ($runCoverage) {
    $launchArgs += @('--cov=crypto_pit', '--cov-report=term-missing')
}
if ($PytestArgs) {
    $launchArgs += $PytestArgs
}

if ($TestTarget) {
    Write-Step "===== Uruchamianie: $pytestTarget =====" 'Magenta'
} else {
    Write-Step '===== Uruchamianie wszystkich testow =====' 'Magenta'
}

$pytestExit = Invoke-TestStep 1 $stepTitle $launchArgs

Add-Content -LiteralPath $Log -Encoding UTF8 -Value @(
    '',
    '========================================',
    ' PODSUMOWANIE',
    '========================================',
    ''
)
if ($pytestExit -eq 0) {
    Add-Content -LiteralPath $Log -Encoding UTF8 -Value '  [1] PASS'
} else {
    Add-Content -LiteralPath $Log -Encoding UTF8 -Value '  [1] FAIL'
}
Add-Content -LiteralPath $Log -Encoding UTF8 -Value ''

Write-Host ''
Write-Host '============ PODSUMOWANIE ============'
Write-Host ''
if ($pytestExit -eq 0) {
    Write-Host '  [1] PASS'
} else {
    Write-Host '  [1] FAIL'
}
Write-Host ''
Write-Host "  Log: $Log"
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
