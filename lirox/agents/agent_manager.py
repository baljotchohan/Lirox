import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from lirox.security.identity_system import AgentIdentity

_logger = logging.getLogger("lirox.agents.manager")

class AgentManager:
    """
    Manages agent registry, identities, and secure key storage.
    Enforces strict POSIX permissions (0o600) on private keys.
    """
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or os.path.expanduser("~/.lirox/agents"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Ensure root agent dir is secure
        try:
            os.chmod(self.base_dir, 0o700)
        except Exception as e:
            _logger.warning("Could not set strict permissions on %s: %s", self.base_dir, e)
            
    def _get_agent_dir(self, name: str) -> Path:
        agent_dir = self.base_dir / name
        agent_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(agent_dir, 0o700)
        except Exception:
            pass
        return agent_dir
        
    def create_or_load_identity(self, name: str) -> AgentIdentity:
        """Loads an existing identity or generates a new one securely."""
        identity_path = self._get_agent_dir(name) / "identity.json"
        
        if identity_path.exists():
            try:
                with open(identity_path, "r") as f:
                    data = json.load(f)
                return AgentIdentity.load(data)
            except Exception as e:
                _logger.error("Failed to load identity for %s: %s", name, e)
                
        # Generate new
        _logger.info("Generating new cryptographic identity for agent: %s", name)
        identity = AgentIdentity.generate(name)
        
        # Save securely
        with open(identity_path, "w") as f:
            json.dump(identity.export(), f, indent=2)
            
        try:
            # Absolute critical security requirement: only owner can read private keys
            os.chmod(identity_path, 0o600)
        except Exception as e:
            _logger.warning("Could not set 0o600 on identity file %s: %s", identity_path, e)
            
        return identity
        
    def list_agents(self) -> List[str]:
        """List all registered agents."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def kill_agent(self, name: str):
        """Prepare for Kill-Switch functionality (Week 2)."""
        _logger.critical("KILL SWITCH INITIATED for agent: %s", name)
        # This will be fully implemented in Week 2
        pass
