# 🧠 Lirox Mastery: Prompt Engineering Guide

This document provides high-fidelity prompt structures to help you (the Operator) get exact and professional outputs from LLMs when extending or fixing the Lirox Kernel.

---

## 🔬 The "Professional Tester" Persona
Use this prompt when you want a deep audit of a new feature.

**Prompt Template:**
```markdown
Act as a Senior Cybersecurity Researcher and QA Engineer. 
Audit the following Lirox code snippet for:
1. Command Injection (especially via shell pipes/logical operators).
2. Path Traversal (escaping the /outputs/ or /data/ directories).
3. Thread Safety (race conditions in the Executor).
4. UX Friction (non-obvious CLI error messages).

Format your output as:
- [CRITICAL]: High-risk vulnerabilities.
- [SUB-OPTIMAL]: Logic errors or performance bottlenecks.
- [REASONING]: Step-by-step logic of your findings.
- [CODE FIX]: Complete, drop-in replacement code.

Code to Audit:
<PASTE_CODE_HERE>
```

---

## 🛠️ The "Component Architect" Persona
Use this prompt when adding a new tool to `lirox/tools/`.

**Prompt Template:**
```markdown
Act as the Lead Architect of Lirox (v2.0). 
Design a new tool component for [FEATURE_NAME].
Constraints:
- It must follow the `lirox/tools/` pattern (functional, stateless if possible).
- It must catch all exceptions and return a `ToolExecutionError`.
- It must include docstrings matching the existing v2.0 style.
- Ensure dependency checks are handled at the top.

Goal: [DESCRIBE_WHAT_TOOL_DOES]
```

---

## 🛡️ The "Security Policy" Persona
Use this prompt to update the `policy.py` engine.

**Prompt Template:**
```markdown
Analyze the current Lirox Execution Policy.
Current Goal: [USER_QUERY]
Current Plan: [PLAN_JSON]

Evaluate if this plan violates the 'Zero Trust Terminal' protocol. 
Check for:
- Writing to system directories (~/, /etc, /usr).
- Deletion of non-temporary files.
- Excessive network exfiltration patterns.

Output a revised JSON risk score:
{
  "risk": 0-10,
  "action": "AUTO_EXECUTE | REQUIRE_CONFIRM | BLOCK",
  "reason": "Detailed justification"
}
```

---

## 📈 Tips for Exact Outputs
1. **Context Anchoring**: Always mention "Lirox v2.0" and "CLI-first architecture" to avoid the AI suggesting web-based solutions.
2. **Path Constraints**: Remind the AI that all paths must be relative to the `PROJECT_ROOT` found in `lirox.config`.
3. **UI Constraints**: Explicitly ask for `rich.console` or `lirox.ui.display` components for any user-facing output.

---
*Created by Antigravity for the Lirox Kernel.*
