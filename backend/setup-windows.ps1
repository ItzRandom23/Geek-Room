$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    # The pinned ML/data-science dependencies are tested with Python 3.11.
    # Calling the launcher with an explicit version avoids accidentally creating
    # a Python 3.14 environment, for which several pinned packages have no wheels.
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11)" 2>$null
    $pythonCheckExitCode = $LASTEXITCODE
    $ErrorActionPreference = $savedErrorActionPreference
    if ($pythonCheckExitCode -ne 0) {
        Write-Host "Python 3.11 is required but was not found." -ForegroundColor Red
        Write-Host "Install it with: winget install --id Python.Python.3.11 -e"
        Write-Host "Then close this terminal, open a new one, and run this script again."
        exit 1
    }

    Write-Host "Creating the Python 3.11 virtual environment..."
    & py -3.11 -m venv .venv311
}

& $venvPython -c "import sys; assert sys.version_info[:2] == (3, 11)"
if ($LASTEXITCODE -ne 0) {
    Write-Host ".venv311 is not a Python 3.11 environment. Remove it and rerun this script." -ForegroundColor Red
    exit 1
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created backend\.env from .env.example."
}

Write-Host "Backend setup complete." -ForegroundColor Green
Write-Host "Activate it with: .\.venv311\Scripts\Activate.ps1"
