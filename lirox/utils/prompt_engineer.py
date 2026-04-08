"""
Advanced prompt engineering with:
- User context injection
- Dynamic system prompts
- Learning history integration
- Communication style adaptation
- Provider-specific optimization
"""

from __future__ import annotations


class AdvancedPromptEngineer:
    """Build intelligent, context-aware prompts"""

    _TASK_GUIDELINES: dict = {
        "code": (
            "- Write production-quality code\n"
            "- Include error handling\n"
            "- Add type hints\n"
            "- Include docstrings\n"
            "- Follow PEP 8"
        ),
        "research": (
            "- Cite credible sources\n"
            "- Present multiple perspectives\n"
            "- Acknowledge limitations\n"
            "- Separate facts from opinions"
        ),
        "analysis": (
            "- Provide pros and cons\n"
            "- Include trade-offs\n"
            "- Suggest alternatives\n"
            "- Explain reasoning"
        ),
        "writing": (
            "- Clear and engaging\n"
            "- Well-structured\n"
            "- Proper grammar\n"
            "- Appropriate tone"
        ),
        "planning": (
            "- Break into actionable steps\n"
            "- Include time estimates\n"
            "- List dependencies\n"
            "- Identify risks"
        ),
        "general": (
            "- Balance brevity with completeness\n"
            "- Use clear sections for organization\n"
            "- Include key details and reasoning\n"
            "- Adapt length to question complexity"
        ),
    }

    def build_system_prompt(
        self,
        profile: dict,
        learnings: dict,
        task_type: str = "general",
    ) -> str:
        """Build advanced system prompt with full context"""

        prompt = (
            f"You are {profile.get('agent_name', 'Lirox')}, "
            "an advanced autonomous AI agent.\n\n"
            "## Identity & Role\n"
            f"- Operator: {profile.get('user_name', 'Operator')}\n"
            f"- Specialization: {profile.get('niche', 'General tasks')}\n"
            f"- Profession: {profile.get('profession', 'Professional')}\n\n"
            "## Communication Style\n"
            f"- Tone: {profile.get('tone', 'professional')}\n"
            f"- Format: {profile.get('format_preference', 'balanced')}\n"
            f"- Response length: {profile.get('response_length', 'medium')}\n"
        )

        # Add learned communication preferences
        if learnings.get("communication_style"):
            prompt += "\n## Your Learned Communication Rules\n"
            for key, value in learnings["communication_style"].items():
                prompt += f"- {key}: {value}\n"

        # Add response format guidelines
        prompt += "\n## Response Format Requirements\n"
        fmt = profile.get("format_preference", "balanced")
        if fmt == "concise":
            prompt += (
                "- Keep responses SHORT and direct\n"
                "- One paragraph maximum unless asked otherwise\n"
                "- Use bullet points for lists (max 5 items)\n"
                "- No unnecessary elaboration\n"
                "- Get to the point immediately\n"
            )
        elif fmt == "detailed":
            prompt += (
                "- Provide comprehensive explanations\n"
                "- Include reasoning, trade-offs, and alternatives\n"
                "- Use multiple paragraphs with clear structure\n"
                "- Include examples where helpful\n"
                "- Explain the \"why\" not just the \"how\"\n"
            )
        else:
            prompt += (
                "- Balance brevity with completeness\n"
                "- Use clear sections for organization\n"
                "- Include key details and reasoning\n"
                "- Adapt length to question complexity\n"
            )

        # Task-specific context
        prompt += "\n## Task-Specific Guidelines\n"
        prompt += self._TASK_GUIDELINES.get(task_type, self._TASK_GUIDELINES["general"])

        # Add known facts about user
        if learnings.get("user_facts"):
            prompt += "\n## Facts You've Learned About the User\n"
            for fact in learnings["user_facts"][:8]:
                if isinstance(fact, dict):
                    prompt += f"- {fact.get('fact', fact)}\n"
                else:
                    prompt += f"- {fact}\n"

        # Add recent work context
        if learnings.get("topics"):
            prompt += "\n## Recent Work Areas\n"
            topics = learnings["topics"]
            for topic, info in list(topics.items())[:5]:
                count = info.get("count", 0) if isinstance(info, dict) else 0
                if count > 0:
                    prompt += f"- {topic} ({count}x recently)\n"

        # Add goals
        if profile.get("goals"):
            prompt += "\n## User's Goals\n"
            for goal in profile.get("goals", [])[:5]:
                prompt += f"- {goal}\n"

        return prompt

    def inject_context(
        self,
        prompt: str,
        memory_context: str = "",
        recent_interactions: list = None,
    ) -> str:
        """Inject contextual information into prompt"""

        enhanced = prompt

        if memory_context:
            enhanced += f"\n## Relevant Context\n{memory_context}\n"

        if recent_interactions:
            enhanced += "\n## Similar Past Interactions\n"
            for interaction in recent_interactions[:3]:
                if isinstance(interaction, dict):
                    enhanced += f"- Q: {interaction.get('query', '')}\n"
                    enhanced += f"  A: {interaction.get('answer', '')[:200]}...\n"

        return enhanced

    def optimize_for_provider(self, prompt: str, provider: str) -> str:
        """Optimize prompt for specific LLM provider"""

        optimizations = {
            "anthropic": lambda p: p.replace(
                "Provide an answer",
                "Think step-by-step, then provide your answer",
            ),
            "openai": lambda p: p + "\n\nFormat with clear sections and bullet points.",
            "groq": lambda p: p + "\n\nBe concise and efficient.",
            "gemini": lambda p: p + "\n\nFeel free to show detailed reasoning.",
        }

        if provider in optimizations:
            return optimizations[provider](prompt)

        return prompt
