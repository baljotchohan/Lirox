"""Lirox V1 — Home Screen Integration.

Creates and manages the ~/Lirox/ workspace folder so users can easily access
all their agent data, memory, skills, and backups from their home directory.

Platform-specific shortcut/bookmark creation:
  - macOS  : Finder sidebar alias (via AppleScript)
  - Windows : Desktop shortcut (.lnk)
  - Linux  : XDG bookmarks (~/.config/gtk-3.0/bookmarks) + .desktop file
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Optional


# ── Paths ────────────────────────────────────────────────────────────────────

HOME_LIROX_DIR = Path.home() / "Lirox"

_STRUCTURE = {
    "data/memory":   "Conversation memory and daily logs",
    "data/sessions": "Chat session history",
    "data/mind":     "Skills, agents, and learnings",
    "data/backups":  "Automatic backups",
    "quick-access":  "Shortcuts and summaries",
    "audit":         "Audit logs for all operations",
}

_README_CONTENT = """\
# 🦁 Lirox Workspace

Your personal AI agent workspace. All your data lives here.

## Structure

```
~/Lirox/
├── data/
│   ├── memory/      # Conversation history
│   ├── sessions/    # Chat sessions
│   ├── mind/        # Skills, agents, learnings
│   └── backups/     # Automatic backups
├── quick-access/    # Summaries and shortcuts
├── audit/           # Audit logs
├── README.md
└── .lirox-config
```

## Commands

- `/recall`          — See everything the agent knows about you
- `/learnings`       — View all learned knowledge
- `/backup`          — Create a manual backup
- `/export-memory`   — Export your full profile as a portable file
- `/import-memory`   — Import from ChatGPT / Claude / Gemini / Lirox export

## Privacy

All data is stored **locally** on your machine. Nothing is sent to external
servers except the queries you send to your configured LLM provider.
"""

_CONFIG_TEMPLATE = {
    "version":       "1.0.0",
    "created_at":    "",
    "home_dir":      str(HOME_LIROX_DIR),
    "shortcut_created": False,
    "platform":      sys.platform,
}


# ── Public API ───────────────────────────────────────────────────────────────

def setup_home_folder(ask: bool = True) -> dict:
    """Create the ~/Lirox/ workspace folder and return a status dict.

    Args:
        ask: if True, the caller is responsible for asking the user first;
             this function only handles creation.

    Returns:
        {
          "created": bool,
          "path": str,
          "shortcut": bool,   # whether a platform shortcut was made
          "error": str | None
        }
    """
    result = {"created": False, "path": str(HOME_LIROX_DIR),
              "shortcut": False, "error": None}

    try:
        _create_folder_structure()
        result["created"] = True
    except Exception as e:
        result["error"] = str(e)
        return result

    try:
        shortcut_ok = _create_platform_shortcut()
        result["shortcut"] = shortcut_ok
    except Exception:
        pass  # shortcut failure is non-fatal

    _write_config(shortcut_created=result["shortcut"])
    return result


def is_home_folder_setup() -> bool:
    """Return True if the ~/Lirox/ folder already exists and has a config."""
    return (HOME_LIROX_DIR / ".lirox-config").exists()


def get_home_folder_path() -> Path:
    """Return the home folder path (may not exist yet)."""
    return HOME_LIROX_DIR


def link_data_dir(source_data_dir: str) -> bool:
    """Create symlinks from ~/Lirox/data/* → <source_data_dir>/*.

    Falls back to copying a README pointer file if symlinks are unsupported.
    """
    src = Path(source_data_dir)
    dst = HOME_LIROX_DIR / "data"
    if not src.exists():
        return False
    try:
        dst.mkdir(parents=True, exist_ok=True)
        for sub in ("memory", "sessions", "mind", "backups"):
            sub_src = src / sub
            sub_dst = dst / sub
            if sub_src.exists() and not sub_dst.exists():
                try:
                    sub_dst.symlink_to(sub_src)
                except (OSError, NotImplementedError):
                    # Fallback: write a pointer file so the user can navigate there
                    pointer = sub_dst.with_suffix(".location")
                    pointer.write_text(f"Data location: {sub_src}\n", encoding="utf-8")
        return True
    except Exception:
        return False


# ── Internal helpers ─────────────────────────────────────────────────────────

def _create_folder_structure() -> None:
    """Create ~/Lirox/ and all sub-directories with safe permissions."""
    HOME_LIROX_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

    for rel_path in _STRUCTURE:
        d = HOME_LIROX_DIR / rel_path
        d.mkdir(mode=0o700, parents=True, exist_ok=True)

    # README.md
    readme = HOME_LIROX_DIR / "README.md"
    if not readme.exists():
        readme.write_text(_README_CONTENT, encoding="utf-8")

    # quick-access stubs
    for fname in ("recent-files.md", "favorite-agents.md", "skills.md"):
        p = HOME_LIROX_DIR / "quick-access" / fname
        if not p.exists():
            p.write_text(f"# {fname.replace('-', ' ').replace('.md', '').title()}\n\n"
                         "_Populated automatically as you use Lirox._\n",
                         encoding="utf-8")


def _write_config(shortcut_created: bool = False) -> None:
    from datetime import datetime
    config = dict(_CONFIG_TEMPLATE)
    config["created_at"]       = datetime.now().isoformat()
    config["shortcut_created"] = shortcut_created
    cfg_path = HOME_LIROX_DIR / ".lirox-config"
    try:
        cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except Exception:
        pass  # non-fatal


def _create_platform_shortcut() -> bool:
    """Attempt to create a platform-specific shortcut. Return True on success."""
    if sys.platform == "darwin":
        return _shortcut_macos()
    elif sys.platform == "win32":
        return _shortcut_windows()
    else:
        return _shortcut_linux()


def _shortcut_macos() -> bool:
    """Add ~/Lirox to Finder sidebar via AppleScript (best-effort)."""
    try:
        import subprocess
        script = (
            f'tell application "Finder"\n'
            f'  set liroxFolder to POSIX file "{HOME_LIROX_DIR}" as alias\n'
            f'  if not (liroxFolder is in (every item of sidebar items)) then\n'
            f'    add liroxFolder to sidebar items\n'
            f'  end if\n'
            f'end tell'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _shortcut_windows() -> bool:
    """Create a Desktop shortcut on Windows (best-effort)."""
    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            return False
        shortcut_path = desktop / "Lirox.lnk"
        if shortcut_path.exists():
            return True  # already exists

        # Use win32com if available, otherwise create a plain .url file
        try:
            import win32com.client  # type: ignore
            shell = win32com.client.Dispatch("WScript.Shell")
            sc = shell.CreateShortCut(str(shortcut_path))
            sc.Targetpath  = str(HOME_LIROX_DIR)
            sc.Description = "Lirox AI Agent workspace"
            sc.save()
            return True
        except ImportError:
            pass

        # Fallback: create a .url file pointing to the folder
        url_path = desktop / "Lirox.url"
        url_path.write_text(
            f"[InternetShortcut]\nURL=file:///{HOME_LIROX_DIR}\n",
            encoding="utf-8"
        )
        return True
    except Exception:
        return False


def _shortcut_linux() -> bool:
    """Add ~/Lirox to XDG file-manager bookmarks (best-effort)."""
    try:
        bookmarks_path = Path.home() / ".config" / "gtk-3.0" / "bookmarks"
        bookmarks_path.parent.mkdir(parents=True, exist_ok=True)

        entry = f"file://{HOME_LIROX_DIR} Lirox\n"
        existing = bookmarks_path.read_text(encoding="utf-8") if bookmarks_path.exists() else ""
        if str(HOME_LIROX_DIR) not in existing:
            with open(bookmarks_path, "a", encoding="utf-8") as f:
                f.write(entry)

        # Also create a .desktop file in the home dir for visibility
        desktop_file = HOME_LIROX_DIR / "Lirox.desktop"
        if not desktop_file.exists():
            desktop_file.write_text(
                "[Desktop Entry]\n"
                "Type=Directory\n"
                f"Name=Lirox\n"
                f"Comment=Lirox AI Agent workspace\n"
                f"Path={HOME_LIROX_DIR}\n"
                "Icon=folder\n",
                encoding="utf-8"
            )
        return True
    except Exception:
        return False
