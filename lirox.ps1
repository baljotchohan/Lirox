$ErrorActionPreference = "Stop"

$PythonCmd = "python"
if (!(Get-Command $PythonCmd -ErrorAction SilentlyContinue)) {
    $PythonCmd = "py"
    if (!(Get-Command $PythonCmd -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
        Write-Host "Please install Python 3.9+ from https://www.python.org/downloads/"
        exit 1
    }
}

try {
    & $PythonCmd -c "import lirox" *>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Lirox] Initializing environment and installing dependencies automatically..." -ForegroundColor Cyan
        & $PythonCmd -m pip install --upgrade pip --quiet
        & $PythonCmd -m pip install -e . --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to install dependencies. Try running install_windows.bat instead." -ForegroundColor Red
            exit 1
        }
    }
} catch {
    # Ignore check errors
}

# Forward execution to the main module
$argsList = @("-m", "lirox.main") + $args
& $PythonCmd @argsList
