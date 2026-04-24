"""Lirox v1.1 — Backup System

Creates complete backups of all Lirox data for the /backup command.
Produces a timestamped zip archive on the user's Desktop.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from lirox.config import DATA_DIR, OUTPUTS_DIR, MIND_DIR, APP_VERSION


def create_backup() -> str:
    """
    Create a complete backup of Lirox data.

    Returns:
        Path to the created backup zip file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"lirox_backup_{timestamp}"
    backup_dir = Path.home() / "Desktop" / backup_name

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup data directory (sessions, memory, mind)
    data_path = Path(DATA_DIR)
    if data_path.exists():
        shutil.copytree(data_path, backup_dir / "data", dirs_exist_ok=True)

    # Backup outputs directory
    outputs_path = Path(OUTPUTS_DIR)
    if outputs_path.exists():
        shutil.copytree(outputs_path, backup_dir / "outputs", dirs_exist_ok=True)

    # Create manifest
    manifest = {
        "backup_date": datetime.now().isoformat(),
        "lirox_version": APP_VERSION,
        "contents": {
            "data_dir": data_path.exists(),
            "outputs_dir": outputs_path.exists(),
        },
    }

    with open(backup_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Create zip archive
    backup_zip = shutil.make_archive(
        str(backup_dir), "zip", backup_dir.parent, backup_dir.name
    )

    # Clean up unzipped directory
    shutil.rmtree(backup_dir)

    return backup_zip
