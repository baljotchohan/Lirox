import os
import tempfile
import unittest
import base64
from pathlib import Path
from lirox.security.identity_system import AgentIdentity
from lirox.agents.agent_manager import AgentManager

class TestAgentIdentity(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = AgentManager(base_dir=self.temp_dir.name)
        
    def tearDown(self):
        self.temp_dir.cleanup()
        
    def test_identity_generation(self):
        # Generate new identity
        identity = self.manager.create_or_load_identity("test_agent")
        self.assertTrue(identity.agent_id.startswith("ag_"))
        self.assertIsNotNone(identity.private_key_pem)
        self.assertIsNotNone(identity.public_key_pem)
        self.assertIn("capabilities", identity.permissions)
        
    def test_signature_verification(self):
        identity = AgentIdentity.generate("signer_agent")
        payload = '{"action": "create_file", "path": "/test/path"}'
        
        # Sign it
        signature = identity.sign_action(payload)
        
        # Verify it
        self.assertTrue(identity.verify_action(signature, payload))
        
        # Verify with wrong payload fails
        wrong_payload = '{"action": "delete_file", "path": "/test/path"}'
        self.assertFalse(identity.verify_action(signature, wrong_payload))
        
        # Verify with corrupted signature fails
        bad_sig = base64.b64encode(b"corrupted_data_not_real_signature").decode('utf-8')
        self.assertFalse(identity.verify_action(bad_sig, payload))
        
    def test_persistence(self):
        # Create identity and save
        identity1 = self.manager.create_or_load_identity("persist_agent")
        
        # Reload identity
        identity2 = self.manager.create_or_load_identity("persist_agent")
        
        # Should be exactly the same
        self.assertEqual(identity1.agent_id, identity2.agent_id)
        self.assertEqual(identity1.public_key_pem, identity2.public_key_pem)
        self.assertEqual(identity1.private_key_pem, identity2.private_key_pem)

if __name__ == "__main__":
    unittest.main()
