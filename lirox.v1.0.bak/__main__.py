"""
lirox/__main__.py — enables `python -m lirox`

Usage:
    python -m lirox
    lirox              (after pip install -e .)
"""

from lirox.main import fix_windows_path, main

fix_windows_path()   # auto-fix Windows PATH before anything else

if __name__ == "__main__":
    main()
