@echo off
setlocal EnableDelayedExpansion

echo.
echo  =========================================
echo   Lirox Installer for Windows
echo  =========================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python is not installed or not in PATH.
        echo.
        echo  Please install Python 3.9+ from https://www.python.org/downloads/
        echo  Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

:: ── Check Python version ──────────────────────────────────────────────────────
for /f "tokens=2 delims= " %%v in ('%PYTHON% --version 2^>^&1') do set PY_VER=%%v
echo [INFO] Found Python %PY_VER%

:: ── Upgrade pip ───────────────────────────────────────────────────────────────
echo [INFO] Upgrading pip...
%PYTHON% -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo [WARN] Could not upgrade pip. Continuing...
)

:: ── Install Lirox ─────────────────────────────────────────────────────────────
echo [INFO] Installing Lirox and all dependencies...
%PYTHON% -m pip install -e .
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Installation failed.
    echo.
    echo  Fallback: try installing dependencies manually:
    echo    %PYTHON% -m pip install -r requirements.txt
    echo    %PYTHON% -m pip install -e .
    echo.
    echo  If you see "file:///C:/Users/... does not appear to be a Python project":
    echo    Make sure you are running this script from the Lirox project folder.
    echo    cd path\to\Lirox
    echo    install_windows.bat
    echo.
    pause
    exit /b 1
)

:: ── Verify lirox command ──────────────────────────────────────────────────────
lirox --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARN] 'lirox' command not found in PATH yet.
    echo  This usually means Python's Scripts directory is not in your PATH.
    echo.
    echo  Find the correct Scripts path by running:
    echo    python -c "import sys; print(sys.executable)"
    echo  Then add the Scripts folder in that directory to your PATH.
    echo  Example: C:\Users\YourName\AppData\Local\Programs\Python\Python311\Scripts
    echo.
    echo  Alternatively, run Lirox with:
    echo    %PYTHON% -m lirox
    echo.
) else (
    echo.
    echo  =========================================
    echo   Lirox installed successfully!
    echo  =========================================
    echo.
    echo  Run: lirox
    echo  Setup: lirox --setup
    echo.
)

pause
endlocal
