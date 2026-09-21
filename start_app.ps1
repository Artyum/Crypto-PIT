param(
    [switch]$InBackground,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = "Stop"

# Przy starcie z Eksploratora: przejdz na ukryty proces PowerShell,
# zeby nie zostawalo okno CMD/konsoli pod aplikacja.
if (-not $InBackground) {
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -InBackground"
    if ($AppArgs) {
        foreach ($a in $AppArgs) {
            $argList += " `"$a`""
        }
    }
    Start-Process -FilePath "powershell.exe" -ArgumentList $argList -WindowStyle Hidden
    exit 0
}

Set-Location -Path $PSScriptRoot

function Show-Error([string]$Message) {
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show(
        $Message,
        "Crypto-PIT",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
    exit 1
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvPythonw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
$requirements = Join-Path $PSScriptRoot "requirements.txt"

if (-not (Test-Path $venvPython)) {
    $created = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
        $created = $true
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
        $created = $true
    }

    if (-not $created) {
        Show-Error "Nie znaleziono Pythona. Zainstaluj Python 3 lub upewnij sie, ze 'py' / 'python' jest w PATH."
    }
    if (-not (Test-Path $venvPython)) {
        Show-Error "Nie udalo sie utworzyc .venv (brak $venvPython)."
    }
}

if (-not (Test-Path $venvPythonw)) {
    Show-Error "Brak pythonw.exe w .venv - wymagany do uruchomienia bez okna konsoli."
}

if (-not (Test-Path $requirements)) {
    Show-Error "Brak pliku requirements.txt w $PSScriptRoot."
}

& $venvPython -m pip install --quiet -r $requirements
if ($LASTEXITCODE -ne 0) {
    Show-Error "pip install -r requirements.txt zakonczylo sie bledem."
}

# pythonw = GUI bez okna konsoli
$pyArgs = @("-m", "crypto_pit")
if ($AppArgs) {
    $pyArgs += $AppArgs
}
Start-Process -FilePath $venvPythonw -ArgumentList $pyArgs -WorkingDirectory $PSScriptRoot
