import json
import os
from lirox.config import MEMORY_LIMIT

class Memory:
    def __init__(self, storage_file="memory.json"):
        self.storage_file = storage_file
        self.history = self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_memory(self, role, content):
        self.history.append({"role": role, "content": content})
        # Keep only the last N messages (limit * 2 for user/ai pairs)
        if len(self.history) > MEMORY_LIMIT * 2:
            self.history = self.history[-(MEMORY_LIMIT * 2):]
        
        with open(self.storage_file, 'w') as f:
            json.dump(self.history, f, indent=4)

    def get_context(self):
        """Returns formatted conversation history for injection into prompts."""
        if not self.history:
            return ""
            
        lines = ["--- Recent conversation ---"]
        for msg in self.history:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_name}: {msg['content']}")
        lines.append("--- End of history ---\n")
        return "\n".join(lines)

    def get_messages_for_api(self):
        """Returns history in OpenAI message format for providers that support it."""
        return [{"role": m["role"], "content": m["content"]} for m in self.history]

    def clear(self):
        self.history = []
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
        print("[*] Conversation memory cleared.")
