"""Per-Agent Memory with Unified Access"""
import json
import time
from pathlib import Path
from typing import Dict, List, Any

from lirox.config import MEMORY_DIR


class AgentMemory:
    """Individual agent memory with conversation history."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.memory_file = Path(MEMORY_DIR) / f"{agent_name}_memory.json"
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load memory from disk."""
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text())
            except Exception:
                pass
        
        return {
            "agent": self.agent_name,
            "created_at": time.time(),
            "conversations": [],
            "facts": [],
            "preferences": {},
        }
    
    def save(self) -> None:
        """Save memory to disk."""
        self.memory_file.write_text(json.dumps(self.data, indent=2))
    
    def add_conversation(self, role: str, content: str) -> None:
        """Add message to conversation history."""
        self.data["conversations"].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        self.save()
    
    def add_fact(self, fact: str, category: str = "general") -> None:
        """Store learned facts."""
        self.data["facts"].append({
            "fact": fact,
            "category": category,
            "timestamp": time.time(),
        })
        self.save()
    
    def get_context(self, limit: int = 10) -> str:
        """Get recent conversation context."""
        recent = self.data["conversations"][-limit:]
        return "\n".join([f"{m['role']}: {m['content']}" for m in recent])


class UnifiedMemory:
    """Master memory — access to all agent memories."""
    
    def __init__(self):
        self.agent_memories: Dict[str, AgentMemory] = {}
    
    def get_agent_memory(self, agent_name: str) -> AgentMemory:
        """Get or create agent memory."""
        if agent_name not in self.agent_memories:
            self.agent_memories[agent_name] = AgentMemory(agent_name)
        return self.agent_memories[agent_name]
    
    def query_all_agents(self, query: str) -> Dict[str, Any]:
        """Query what all agents have done."""
        result = {}
        
        for agent_name, memory in self.agent_memories.items():
            # Find relevant conversations
            relevant = [
                msg for msg in memory.data["conversations"]
                if query.lower() in msg["content"].lower()
            ]
            
            result[agent_name] = {
                "recent_work": memory.get_context(5),
                "matching_history": [m["content"] for m in relevant[:3]],
            }
        
        return result
    
    def get_full_history(self) -> str:
        """Export full conversation history."""
        output = "# Full Lirox History\n\n"
        
        for agent_name, memory in self.agent_memories.items():
            output += f"\n## {agent_name.upper()} Agent\n"
            for msg in memory.data["conversations"]:
                output += f"**{msg['role']}**: {msg['content'][:200]}\n"
        
        return output
