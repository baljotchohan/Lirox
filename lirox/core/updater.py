"""
Update logic for Lirox - handles git pulls and dependency refreshing.
"""
import subprocess
import os
import sys
import logging
from pathlib import Path
from lirox.ui.display import console, success_message, error_panel, info_panel

_logger = logging.getLogger("lirox.core.updater")

def run_update():
    """Checks for and applies updates via git."""
    from lirox.config import LIROX_SOURCE_DIR
    
    root_dir = Path(LIROX_SOURCE_DIR).parent
    
    # Ensure we are in a git repo
    if not (root_dir / ".git").exists():
        error_panel("NOT A GIT REPO", f"Update failed: {root_dir} is not a git repository.")
        return False

    try:
        console.print("  [cyan]➜[/] Fetching latest changes from GitHub...")
        
        # 1. git fetch
        subprocess.run(["git", "fetch"], cwd=root_dir, check=True, capture_output=True)
        
        # 2. Check if we are behind
        status = subprocess.run(
            ["git", "status", "-uno"], 
            cwd=root_dir, check=True, capture_output=True, text=True
        ).stdout
        
        if "Your branch is up to date" in status:
            success_message("Lirox is already up to date! 🚀")
            return True
            
        if "Your branch is behind" in status:
            console.print("  [yellow]![/] New updates found. Pulling...")
            
            # 3. git pull
            pull_res = subprocess.run(
                ["git", "pull"], 
                cwd=root_dir, check=True, capture_output=True, text=True
            ).stdout
            
            success_message("Successfully updated Lirox!")
            
            # 4. Refresh dependencies if requirements.txt changed
            if "requirements.txt" in pull_res or "pyproject.toml" in pull_res:
                console.print("  [cyan]➜[/] Dependencies changed. Updating environment...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=root_dir, check=True)
                success_message("Environment refreshed.")

            info_panel("Please run [bold cyan]/restart[/] to apply the update.")
            return True
        
        else:
            # Maybe local changes or diverted
            info_panel("Local branch has diverged or has uncommitted changes.\nUpdate skipped to prevent data loss.")
            return False

    except subprocess.CalledProcessError as e:
        _logger.error(f"Update failed: {e.stderr}")
        error_panel("UPDATE FAILED", f"Error during git operation:\n{e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        _logger.error(f"Update error: {e}")
        error_panel("ERROR", f"Unexpected error: {e}")
        return False
