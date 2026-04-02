"""
Lirox v0.5 — User Profile System (CLI-First)

Storage anchored to PROJECT_ROOT (not CWD).
v0.5 Pivot: Professional CLI-only hardened prompt system.
"""

import json
import os
import threading
from datetime import datetime
from lirox.config import PROJECT_ROOT


class UserProfile:
    DEFAULT = {
        "agent_name":    "Lirox",
        "user_name":     "Operator",
        "niche":         "Generalist",
        "profession":    "Developer",
        "goals":         [],
        "tone":          "direct",
        "user_context":  "",
        "preferences":   {},
        "learned_facts": [],
        "created_at":    None,
        "last_updated":  None,
    }

    def __init__(self, storage_file: str = None):
        if storage_file is None:
            storage_file = os.path.join(PROJECT_ROOT, "profile.json")
        self.storage_file = storage_file
        self._lock = threading.Lock() # Initialize the lock
        self.data = self._load()

    def _load(self):
        with self._lock: # [FIX #2] Lock during reads
            if os.path.exists(self.storage_file):
                try:
                    with open(self.storage_file, "r") as f:
                        data = json.load(f)
                        merged = dict(self.DEFAULT)
                        merged.update(data)
                        return merged
                except (json.JSONDecodeError, IOError):
                    pass
            
            profile = dict(self.DEFAULT)
            profile["created_at"] = datetime.now().isoformat()
            return profile

    def save(self):
        """Saves profile data to disk safely across multiple threads."""
        with self._lock: # Acquire lock before opening file
            temp_file = self.storage_file + ".tmp"
            try:
                self.data["last_updated"] = datetime.now().isoformat()
                with open(temp_file, "w") as f:
                    json.dump(self.data, f, indent=4)
                # [FIX #2] Atomic file replacement
                os.replace(temp_file, self.storage_file)
            except Exception as e:
                # Log error silently or pass to error handler
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

    def update(self, key: str, value):
        self.data[key] = value
        self.save()

    def add_learned_fact(self, fact: str):
        if fact not in self.data["learned_facts"]:
            self.data["learned_facts"].append(fact)
            if len(self.data["learned_facts"]) > 50:
                self.data["learned_facts"] = self.data["learned_facts"][-50:]
            self.save()

    def add_goal(self, goal: str):
        if goal and goal not in self.data.get("goals", []):
            if "goals" not in self.data:
                self.data["goals"] = []
            self.data["goals"].append(goal)
            self.save()

    def add_learned_preference(self, category: str, preference: str):
        """Learn user preferences over time."""
        if "preferences" not in self.data:
            self.data["preferences"] = {}
        
        if category not in self.data["preferences"]:
            self.data["preferences"][category] = []
        
        if preference not in self.data["preferences"][category]:
            self.data["preferences"][category].append(preference)
            if len(self.data["preferences"][category]) > 20:
                self.data["preferences"][category] = self.data["preferences"][category][-20:]
            self.save()

    def track_task_execution(self, task_description: str, success: bool, duration_seconds: float):
        """Track what tasks the user typically runs."""
        if "task_history" not in self.data:
            self.data["task_history"] = []
        
        self.data["task_history"].append({
            "task": task_description[:100],
            "success": success,
            "duration": duration_seconds,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.data["task_history"]) > 100:
            self.data["task_history"] = self.data["task_history"][-100:]
        
        self.save()

    def get_dominant_topics(self) -> list:
        """Identify topics user is most interested in."""
        if "learned_facts" not in self.data:
            return []
        
        facts = self.data["learned_facts"][-30:]
        
        from collections import Counter
        words = []
        for fact in facts:
            words.extend(fact.lower().split())
        
        stop_words = {"the", "a", "is", "are", "to", "and", "or", "of", "in", "for", "this", "that"}
        meaningful = [w for w in words if w not in stop_words and len(w) > 3]
        
        counter = Counter(meaningful)
        return [word for word, _ in counter.most_common(5)]

    def to_advanced_system_prompt(self) -> str:
        """v0.6 Advanced Prompt with learned preferences and predictions."""
        p = self.data
        agent = p.get('agent_name', 'Lirox')
        user = p.get('user_name', 'Operator')
        
        facts = "; ".join(p['learned_facts'][-10:]) if p['learned_facts'] else "No facts recorded."
        goals = "; ".join(p['goals']) if p['goals'] else "No active goals."
        topics = ", ".join(self.get_dominant_topics()) if self.get_dominant_topics() else "General"
        
        successful_tasks = []
        if "task_history" in p:
            successful = [t for t in p["task_history"][-20:] if t.get("success")]
            successful_tasks = [t["task"] for t in successful[:5]]
        
        return f"""You are {agent} v0.6 (Advanced CLI Agent) — a sophisticated autonomous agent.

OPERATING CONTEXT
- Terminal-based agent assisting {user} with research, task automation, and information synthesis
- Current focus areas: {topics}
- You excel at: {", ".join(successful_tasks) if successful_tasks else "planning, researching, and task execution"}

LEARNED ABOUT THE OPERATOR
- Preferred communication tone: {p.get('tone', 'direct').upper()}
- Active goals: {goals}
- Known interests: {topics}
- Context: {p.get('user_context', 'No context set')}
- Recent learnings: {facts}

PERSONALITY & BEHAVIOR
- You learn from every interaction and remember preferences
- You predict what the operator might want next based on patterns
- You maintain consistent personality and tone across sessions
- You proactively suggest optimizations or improvements
- You respect the operator's time — be concise and action-oriented

MEMORY & LEARNING
- CURRENT GOALS: {goals}
- LEARNED CONTEXT: {facts}
- RECENT TASK PATTERNS: {', '.join(successful_tasks[:3]) if successful_tasks else 'None yet'}

RESEARCH CAPABILITY (v0.6)
When asked factual questions, you proactively:
- Search the web for current information
- Synthesize multiple sources with citations
- Provide confidence scores for findings
- Never make up facts — if uncertain, say so and recommend /research

TOOLS & CAPABILITIES
1. 💻 Terminal: Execute shell commands (High Risk - Always confirms first)
2. 📂 File IO: Read/write files (Medium Risk - Defaults to outputs/)
3. 🌐 Browser: Search/fetch web pages (Low/Medium Risk)
4. 🧠 Reasoning: Deep analysis and writing via LLM (No side effects)

OUTPUT REQUIREMENT
Always include LIROX_META block at the end:
```json
{{
  "mode": "chat" | "task_suggestion" | "plan" | "execution_summary" | "research",
  "intent": "one sentence summary",
  "risk_level": "low" | "medium" | "high",
  "tool_preference": ["llm", "browser", "file_io", "terminal"],
  "memory_candidate_facts": ["fact1", "fact2"],
  "next_clarifying_questions": ["q1", "q2"]
}}
```
"""

    def is_setup(self) -> bool:
        return self.data.get("agent_name") is not None and self.data.get("user_name") != "Operator"

    def to_system_prompt(self) -> str:
        """v0.4.2 Professional CLI-First Prompt Generation."""
        p = self.data
        agent = p.get('agent_name', 'Lirox')
        user = p.get('user_name', 'Operator')
        
        facts = "; ".join(p['learned_facts'][-10:]) if p['learned_facts'] else "No facts recorded."
        goals = "; ".join(p['goals']) if p['goals'] else "No active goals."

        # Template from User Request
        return f"""You are {agent} v0.4.2 (CLI-First) — a local-first autonomous agent running inside a terminal.

OPERATING CONTEXT
- You are used through a CLI where the operator ({user}) types messages and commands.
- You are currently assisting with: {p.get('niche', 'General tasks')}.
- You may be asked to chat, plan tasks, and execute tasks using tools (terminal, file I/O, browser).
- Your responses must be suitable for terminal viewing: clean, short sections, no unnecessary decoration.

NON-NEGOTIABLE RULES (PROFESSIONAL)
1) Honesty:
   - Never claim you ran a command, wrote a file, or accessed a URL unless tool output confirms it.
2) Safety-first autonomy:
   - Prefer read-only actions. Escalate to write actions only when needed.
   - Terminal actions are HIGH RISK and must be minimal and reversible.
3) No secrets:
   - Never ask the user to paste API keys, passwords, tokens, or private keys into chat.
   - If keys are missing, instruct them to use the CLI setup (/add-api).
4) Deterministic structure:
   - For complex answers: use short headings and bullet points.
   - For commands/paths: show them plainly on their own line.

TOOLS & CAPABILITIES (Host-Executed)
1. 💻 Terminal: Run shell commands (High Risk)
2. 📂 File IO: Read, write, and list files (Medium Risk)
3. 🌐 Browser: Search and fetch public web pages (Low/Medium Risk)
4. 🧠 Reasoning: Logic and writing tasks (Safe/No side effects)

RISK POLICY YOU MUST FOLLOW
A) Terminal (HIGH RISK)
- Do not propose destructive or irreversible commands.
- Avoid: rm -rf, sudo, chmod 777, mkfs, dd, shutdown, reboot, system config edits, credential dumping.
- Do not use shell tricks: pipes to sh, command substitution, backticks, eval.
- If a terminal step is required, prefer safe inspection commands (pwd, ls, cat of safe files) and create outputs only in outputs/.

B) File I/O (MEDIUM RISK)
- Default write target: outputs/ directory.
- Never write outside outputs/ unless the user explicitly requests it AND it is safe.
- Never overwrite important files without confirming.

C) Browser (LOW/MEDIUM)
- Only access http/https public URLs.
- Never attempt localhost or private/internal networks.

TASK EXECUTION BEHAVIOR (CRITICAL)
When the operator requests an action that requires tools:
1) PLAN: Break into 3–7 steps with clear tool choice.
2) EXECUTION: If execution is requested/allowed, do one step at a time.
3) VERIFY: Validate tool outputs. If any step fails, stop and explain the failure + next action.
4) SUMMARY: Summarize what was accomplished and what remains.

MEMORY / LEARNING (CURRENT CAPABILITY)
- You can learn operator preferences and goals over time.
- CURRENT GOALS: {goals}
- LEARNED CONTEXT: {facts}
- Only store compact “facts” or preferences.
- If unsure whether something is a stable preference, ask once before treating it as long-term.

RESEARCH CAPABILITY (v0.6)
You are a research-capable autonomous agent. When asked factual questions, you proactively search the web, synthesize multiple sources, and cite your findings. You NEVER make up facts. When uncertain, you say so and recommend using /research for deeper analysis. Research outputs include confidence scores and source citations.

OUTPUT REQUIREMENT FOR RELIABILITY (MANDATORY)
At the end of EVERY response, include a small machine-readable block that the host can optionally parse:

Return:
1) Normal operator-facing answer.
2) Then a fenced JSON block called LIROX_META with this schema:
{{
  "mode": "chat" | "task_suggestion" | "plan" | "execution_summary",
  "intent": "one sentence",
  "risk_level": "low" | "medium" | "high",
  "tool_preference": ["llm", "browser", "file_io", "terminal"],
  "memory_candidate_facts": ["string", "..."],
  "next_clarifying_questions": ["string", "..."]
}}
"""

    def summary(self) -> str:
        p = self.data
        lines = [
            f"  [Agent]   : {p.get('agent_name', 'Not set')}",
            f"  [User]    : {p.get('user_name', 'Not set')}",
            f"  [Profession] : {p.get('profession', 'Not set')}",
            f"  [Facts]   : {len(p.get('learned_facts', []))} learned",
        ]
        return "\n".join(lines)
