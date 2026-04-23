import os
import json
import logging
from typing import Dict, Any
import subprocess
import sys

_logger = logging.getLogger("lirox.security")

def _ensure_cryptography():
    try:
        import cryptography
    except ImportError:
        _logger.info("Installing missing dependency: cryptography")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "cryptography", "--quiet", "--disable-pip-version-check"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        import importlib
        importlib.invalidate_caches()

class AgentIdentity:
    """
    Cryptographic identity for a Lirox Agent.
    Uses ED25519 for high-performance, secure digital signatures.
    """
    def __init__(self, agent_id: str, private_key_pem: bytes, public_key_pem: bytes, permissions: Dict[str, Any] = None):
        self.agent_id = agent_id
        self.private_key_pem = private_key_pem
        self.public_key_pem = public_key_pem
        self.permissions = permissions or {"capabilities": ["read", "execute"]}
        
    @classmethod
    def generate(cls, name: str) -> "AgentIdentity":
        _ensure_cryptography()
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        import uuid
        
        # UUID-based ID with agent prefix
        agent_id = f"ag_{uuid.uuid4().hex[:16]}"
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return cls(agent_id=agent_id, private_key_pem=priv_pem, public_key_pem=pub_pem)
        
    def sign_action(self, action_data: str) -> str:
        """Sign an action payload with the agent's private key."""
        _ensure_cryptography()
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        import base64
        
        private_key = serialization.load_pem_private_key(self.private_key_pem, password=None)
        signature = private_key.sign(action_data.encode('utf-8'))
        return base64.b64encode(signature).decode('utf-8')
        
    def verify_action(self, signature_b64: str, action_data: str) -> bool:
        """Verify an action was genuinely performed by this agent."""
        _ensure_cryptography()
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature
        import base64
        
        public_key = serialization.load_pem_public_key(self.public_key_pem)
        try:
            signature = base64.b64decode(signature_b64)
            public_key.verify(signature, action_data.encode('utf-8'))
            return True
        except (InvalidSignature, Exception) as e:
            _logger.warning("Signature verification failed for agent %s: %s", self.agent_id, e)
            return False

    def export(self) -> Dict[str, Any]:
        """Export identity for secure storage."""
        return {
            "agent_id": self.agent_id,
            "private_key": self.private_key_pem.decode('utf-8'),
            "public_key": self.public_key_pem.decode('utf-8'),
            "permissions": self.permissions
        }

    @classmethod
    def load(cls, data: Dict[str, Any]) -> "AgentIdentity":
        """Load identity from secure storage."""
        return cls(
            agent_id=data["agent_id"],
            private_key_pem=data["private_key"].encode('utf-8'),
            public_key_pem=data["public_key"].encode('utf-8'),
            permissions=data.get("permissions", {"capabilities": ["read", "execute"]})
        )
