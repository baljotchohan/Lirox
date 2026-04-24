#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ========================================="
echo "  Lirox Installer for Linux"
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
    echo "[INFO] pip not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-pip
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python-pip
    else
        $PYTHON -m ensurepip --upgrade || {
            echo "[ERROR] Could not install pip. Install it manually and re-run."
            exit 1
        }
    fi
fi

# ── Upgrade pip ────────────────────────────────────────────────────────────────
echo "[INFO] Upgrading pip..."
$PYTHON -m pip install --upgrade pip --quiet

# ── Install Lirox ──────────────────────────────────────────────────────────────
echo "[INFO] Installing Lirox and all dependencies..."
$PYTHON -m pip install -e . || {
    echo ""
    echo "[ERROR] Installation with '-e .' failed. Trying requirements.txt fallback..."
    $PYTHON -m pip install -r requirements.txt && $PYTHON -m pip install -e . || {
        echo ""
        echo "[ERROR] Installation failed."
        echo " Try manually:"
        echo "   $PYTHON -m pip install -r requirements.txt"
        echo "   $PYTHON -m pip install -e ."
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
    echo " Try adding ~/.local/bin to your PATH:"
    echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
    echo ""
    echo " Or run directly with:"
    echo "   $PYTHON -m lirox"
    echo ""
fi
