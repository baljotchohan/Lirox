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
        context = ""
        for msg in self.history:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role_name}: {msg['content']}\n"
        return context

    def clear(self):
        self.history = []
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
