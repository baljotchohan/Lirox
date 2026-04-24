#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ========================================="
echo "  Lirox Installer for macOS"
echo " ========================================="
echo ""

# ── Detect python3 ─────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "[ERROR] Python 3.9+ is required but was not found."
    exit 1
fi

# ── Handle Uninstall ──────────────────────────────────────────────────────────
if [[ "${1:-}" == "--uninstall" ]]; then
    echo "[INFO] Starting Lirox Deep Uninstall..."
    # We use python -m lirox logic or direct config call
    $PYTHON -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from lirox.config import delete_all_data; delete_all_data()"
    exit 0
fi

PY_VER=$($PYTHON --version 2>&1)
echo "[INFO] Found $PY_VER"

# ── Check version >= 3.9 ───────────────────────────────────────────────────────
$PYTHON - <<'EOF'
import sys
if sys.version_info < (3, 9):
    print(f"[ERROR] Python 3.9+ required. You have {sys.version}")
    sys.exit(1)
EOF

# ── Ensure pip is available ────────────────────────────────────────────────────
if ! $PYTHON -m pip --version &>/dev/null; then
    echo "[INFO] pip not found. Installing via ensurepip..."
    $PYTHON -m ensurepip --upgrade || {
        echo "[ERROR] Could not install pip."
        echo " Try: brew install python  (which includes pip)"
        exit 1
    }
fi

# ── Upgrade pip ────────────────────────────────────────────────────────────────
echo "[INFO] Upgrading pip..."
$PYTHON -m pip install --upgrade pip --quiet

# ── Install Lirox ──────────────────────────────────────────────────────────────
echo "[INFO] Installing Lirox and all dependencies..."
$PYTHON -m pip install -e . || {
    echo ""
    echo "[WARN] Standard install failed. Trying with --break-system-packages flag..."
    $PYTHON -m pip install --break-system-packages -e . || {
        echo ""
        echo "[ERROR] Installation failed."
        echo " Try using a virtual environment:"
        echo "   python3 -m venv lirox-env"
        echo "   source lirox-env/bin/activate"
        echo "   pip install -e ."
        exit 1
    }
}

# ── Verify lirox command ───────────────────────────────────────────────────────
if command -v lirox &>/dev/null; then
    echo ""
    echo " ========================================="
    echo "  Lirox installed successfully!"
    echo " ========================================="
    echo ""
    echo " Run:   lirox"
    echo " Setup: lirox --setup"
    echo ""
else
    echo ""
    echo "[WARN] 'lirox' command not found in PATH."
    echo " Run the following to find your Python version and add it to PATH:"
    echo "   python3 --version   # e.g. Python 3.11.9  →  use 3.11 below"
    echo "   echo 'export PATH=\"\$HOME/Library/Python/3.11/bin:\$PATH\"' >> ~/.zshrc"
    echo "   source ~/.zshrc"
    echo ""
    echo " Or run directly with:"
    echo "   $PYTHON -m lirox"
    echo ""
fi
