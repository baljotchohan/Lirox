import unittest
from unittest.mock import patch, MagicMock
import os

from lirox.utils.llm import aimlapi_call, generate_response
from lirox.llm.providers import LLMRouter, LLMRequest

class TestAIMLAPIIntegration(unittest.TestCase):

    @patch("lirox.utils.secure_keys.get_api_key")
    @patch("requests.post")
    def test_aimlapi_call_success(self, mock_post, mock_get_key):
        # Setup mocks
        mock_get_key.return_value = "02384ee17f798a4c71d160ecd37b17df"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Hello from AIMLAPI!"
                }
            }]
        }
        mock_post.return_value = mock_response

        # Execute
        result = aimlapi_call("Say hi", system_prompt="System instructions", model="deepseek-chat")

        # Assertions
        self.assertEqual(result, "Hello from AIMLAPI!")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.aimlapi.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer 02384ee17f798a4c71d160ecd37b17df")
        self.assertEqual(kwargs["json"]["model"], "deepseek-chat")
        self.assertEqual(kwargs["json"]["messages"][0]["content"], "System instructions")
        self.assertEqual(kwargs["json"]["messages"][1]["content"], "Say hi")

    @patch("lirox.utils.secure_keys.get_api_key")
    @patch("lirox.utils.llm.available_providers")
    def test_router_recommends_aimlapi_first(self, mock_available, mock_get_key):
        # If aimlapi key is configured, task priority recommends it first
        mock_get_key.return_value = "02384ee17f798a4c71d160ecd37b17df"
        mock_available.return_value = ["groq", "aimlapi"]

        router = LLMRouter()
        
        recommended = router.recommend(task_type="coding")
        self.assertEqual(recommended, "aimlapi")
        
        recommended_reasoning = router.recommend(task_type="reasoning")
        self.assertEqual(recommended_reasoning, "aimlapi")

    @patch("lirox.utils.llm.provider_has_key")
    @patch("lirox.utils.llm.available_providers")
    def test_router_health_includes_aimlapi(self, mock_available, mock_has_key):
        mock_available.return_value = ["aimlapi"]
        mock_has_key.side_effect = lambda p: p == "aimlapi"

        router = LLMRouter()
        health = router.health()

        self.assertIn("aimlapi", health)
        self.assertTrue(health["aimlapi"]["ok"])
        self.assertTrue(health["aimlapi"]["available"])
