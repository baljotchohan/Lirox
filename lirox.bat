@echo off
setlocal

:: Find Python
set PYTHON=python
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not in PATH.
        echo Please install Python 3.9+ from https://www.python.org/downloads/
        exit /b 1
    )
    set PYTHON=py
)

:: Check if Lirox is importable, otherwise install automatically
%PYTHON% -c "import lirox" >nul 2>&1
if errorlevel 1 (
    echo [Lirox] Initializing environment and installing dependencies automatically...
    %PYTHON% -m pip install --upgrade pip --quiet
    %PYTHON% -m pip install -e . --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Try running install_windows.bat instead.
        exit /b 1
    )
)

:: Run the application
%PYTHON% -m lirox.main %*
endlocal
