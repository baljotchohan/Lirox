import json
import os
from datetime import datetime

class UserProfile:
    DEFAULT = {
        "agent_name": None,          # Name the user gives their agent (e.g. "Atlas")
        "user_name": None,           # The actual user's name
        "niche": None,               # What they do (e.g. "YouTube content creator")
        "profession": None,          # User's profession
        "goals": [],                 # e.g. ["reach 1M subscribers", "daily upload schedule"]
        "tone": "direct",            # How the agent talks: "formal", "casual", "direct", "friendly"
        "user_context": "",          # Background context provided by user
        "preferences": {},           # Any key/value preferences learned over time
        "learned_facts": [],         # Passive learning storage
        "created_at": None,
        "last_updated": None
    }

    def __init__(self, storage_file="profile.json"):
        self.storage_file = storage_file
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default empty profile
        profile = dict(self.DEFAULT)
        profile["created_at"] = datetime.now().isoformat()
        return profile

    def save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.storage_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def update(self, key, value):
        self.data[key] = value
        self.save()

    def add_goal(self, goal):
        if goal not in self.data["goals"]:
            self.data["goals"].append(goal)
            self.save()

    def add_learned_fact(self, fact):
        """Adds a fact to the profile silently."""
        if fact not in self.data["learned_facts"]:
            self.data["learned_facts"].append(fact)
            # Max 50 facts, trim oldest
            if len(self.data["learned_facts"]) > 50:
                self.data["learned_facts"] = self.data["learned_facts"][-50:]
            self.save()

    def is_setup(self):
        return self.data.get("agent_name") is not None

    def to_system_prompt(self):
        """Generates a rich, personalized system prompt from user data."""
        p = self.data
        agent = p.get("agent_name") or "Lirox"
        lines = [
            f"You are {agent}, a personal AI operating system — not a generic chatbot.",
            f"You are autonomous, proactive, and deeply personalized. You work exclusively for {p.get('user_name', 'your user')}."
        ]

        if p.get("user_name"):
            lines.append(f"The user's name is {p['user_name']}.")
        
        profession = p.get("profession") or p.get("niche")
        if profession:
            lines.append(f"Their profession/focus: {profession}.")

        if p.get("goals"):
            goals_str = "; ".join(p["goals"])
            lines.append(f"Their current goals: {goals_str}.")

        if p.get("user_context"):
            lines.append(f"Context they've shared: {p['user_context']}")

        if p.get("learned_facts"):
            facts_str = "; ".join(p["learned_facts"][-10:])
            lines.append(f"Recent facts learned about them: {facts_str}")

        tone_instructions = {
            "formal": "Speak formally and professionally at all times.",
            "casual": "Be casual, warm and conversational. Use everyday language.",
            "direct": "Be extremely direct. No filler. Get to the point fast.",
            "friendly": "Be warm, encouraging and supportive.",
        }
        lines.append(tone_instructions.get(p.get("tone", "direct"), "Be direct and helpful."))

        lines.append(
            "You remember past conversations. You do NOT ask for information you already know. "
            "Reference their name and goals when relevant. You are their personal AI — act like one."
        )

        # Response formatting rules — enforced on every interaction
        lines.append(
            "Response formatting rules: "
            "Never use asterisks (*) or markdown bold/italic formatting in your responses. "
            "Never use excessive bullet points or dashes for lists. "
            "Write in clean, plain sentences and short paragraphs. "
            "Use numbered lists only when listing concrete steps or options. "
            "Keep answers structured but natural — like a knowledgeable colleague, not a formatted document. "
            "Be concise. No filler phrases like 'Certainly!' or 'Great question!'. Get to the substance immediately."
        )

        return " ".join(lines)

    def summary(self):
        """Returns a human-readable profile summary for display."""
        p = self.data
        lines = [
            f"  [Agent]   : {p.get('agent_name', 'Not set')}",
            f"  [User]    : {p.get('user_name', 'Not set')}",
            f"  [Niche]   : {p.get('niche', 'Not set')}",
            f"  [Goals]   : {', '.join(p['goals']) if p['goals'] else 'None set'}",
            f"  [Tone]    : {p.get('tone', 'direct')}",
            f"  [Facts]   : {len(p.get('learned_facts', []))} learned",
        ]
        return "\n".join(lines)
