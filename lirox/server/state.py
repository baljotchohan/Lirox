"""
[WEB-1] Server-level shared state.

Single instances of Orchestrator, Profile, etc. shared across requests.
Thread-safe: the orchestrator already uses locks internally.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lirox.orchestrator.master import MasterOrchestrator
    from lirox.agents.profile import UserProfile

_logger = logging.getLogger("lirox.server.state")

# ── Singleton instances ──────────────────────────────────────────────────────
orchestrator: Optional[MasterOrchestrator] = None
profile: Optional[UserProfile] = None
_initialized: bool = False


def init() -> None:
    """Bootstrap the Lirox backend — mirrors what main() does in the terminal REPL.

    1. check_dependencies()
    2. ensure_directories()
    3. Load UserProfile
    4. Create MasterOrchestrator(profile_data=profile.data)
    5. Restore pinned LLM provider from profile
    """
    global orchestrator, profile, _initialized

    if _initialized:
        return

    # 1. Dependencies
    from lirox.main import check_dependencies
    check_dependencies()

    # 2. Logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 3. Directories
    from lirox.config import ensure_directories
    ensure_directories()

    # 4. Profile
    from lirox.agents.profile import UserProfile
    profile = UserProfile()

    # 5. Orchestrator
    from lirox.orchestrator.master import MasterOrchestrator
    orchestrator = MasterOrchestrator(profile_data=profile.data)

    # 6. Restore pinned LLM provider
    saved_provider = profile.data.get("llm_provider", "")
    if saved_provider and saved_provider != "auto":
        os.environ["_LIROX_PINNED_MODEL"] = saved_provider

    _initialized = True
    _logger.info("Lirox server state initialized.")


def is_initialized() -> bool:
    return _initialized
