"""
Lirox v0.5 — User Profile System (CLI-First)

Storage anchored to PROJECT_ROOT (not CWD).
v0.5 Pivot: Professional CLI-only hardened prompt system.
"""

import json
import os
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
        self.data = self._load()

    def _load(self):
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
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.storage_file, "w") as f:
            json.dump(self.data, f, indent=4)

    def update(self, key: str, value):
        self.data[key] = value
        self.save()

    def add_learned_fact(self, fact: str):
        if fact not in self.data["learned_facts"]:
            self.data["learned_facts"].append(fact)
            if len(self.data["learned_facts"]) > 50:
                self.data["learned_facts"] = self.data["learned_facts"][-50:]
            self.save()

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

TOOLS YOU CAN USE (HOST RUNS THEM)
- terminal: run a shell command (high risk)
- file_io: read/write/list files (medium risk)
- browser: search/fetch public web pages (low/medium risk)
- llm: reasoning/writing only (no side effects)

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
