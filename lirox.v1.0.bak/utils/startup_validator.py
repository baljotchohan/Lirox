"""
Lirox v2.0 — Startup Validation

Validates system state before agent starts.
Checks: directories, API keys, Python version, dependencies.
"""

import os
import sys
from typing import Dict, List, Tuple
from pathlib import Path
from lirox.utils.dependency_bootstrap import required_package_map


class StartupValidator:
    """Validates Lirox can start properly."""
    
    @staticmethod
    def validate_all() -> Tuple[bool, List[str]]:
        """
        Run all startup checks.
        Returns: (all_ok, list_of_warnings)
        """
        warnings = []
        
        # 1. Check directories are writable
        try:
            from lirox.config import DATA_DIR, OUTPUTS_DIR, PROJECT_ROOT
        except ImportError:
            return False, ["Cannot import lirox.config"]
        
        for dir_path in [DATA_DIR, OUTPUTS_DIR, PROJECT_ROOT]:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    return False, [f"Cannot create {dir_path}: {e}"]
            
            if not os.access(dir_path, os.W_OK):
                return False, [f"Directory not writable: {dir_path}"]
        
        # 2. Check .env exists
        env_path = Path(PROJECT_ROOT) / ".env"
        if not env_path.exists():
            warnings.append("⚠️ .env not found. Run /setup to configure API keys.")
        
        # 3. Check at least one API key configured
        api_keys = [
            os.getenv(f"{p}_API_KEY")
            for p in ["OPENAI", "GEMINI", "GROQ", "ANTHROPIC"]
        ]
        if not any(api_keys):
            # Non-fatal: new users haven't done onboarding yet
            warnings.append("No LLM API keys found. Run /add-api or use /setup to configure.")
        
        # 4. Check Python version
        if sys.version_info < (3, 8):
            return False, ["Python 3.8+ required"]
        
        # 5. Check critical dependencies
        required_modules = list(required_package_map().values())
        missing = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        
        if missing:
            return False, [
                f"Missing: {', '.join(missing)}. "
                "Run Lirox once to auto-install, or run: python -m pip install -r requirements.txt"
            ]
        
        return True, warnings
