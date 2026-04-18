"""Niche-specific follow-up questions for the setup wizard.

The generic niche label ("Developer", "Founder") is too shallow to
personalize the first interaction. These follow-ups capture the
concrete details the agent needs to be useful from message #1.

Each entry returns a list of (key, prompt, default) triples.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# (storage_key, question_text, optional_default_or_empty)
_Q = Tuple[str, str, str]

NICHE_QUESTIONS: Dict[str, List[_Q]] = {
    "Developer": [
        ("primary_language", "Main language you ship in?", ""),
        ("stack",            "Current stack (frontend/backend/mobile/infra)?", ""),
        ("scale",            "Solo project · Small team · Large codebase?", ""),
        ("biggest_blocker",  "What's slowing you down most right now?", ""),
    ],
    "Founder / CEO": [
        ("company_stage",    "Pre-seed · Seed · Series A+ · Bootstrapped?", ""),
        ("product_type",     "B2B SaaS · B2C · Marketplace · Infra · Other?", ""),
        ("team_size",        "How many people on the team?", ""),
        ("top_priority",     "What's the #1 thing occupying you this week?", ""),
    ],
    "Content Creator": [
        ("primary_platform", "Main platform (YouTube, X, TikTok, Newsletter…)?", ""),
        ("content_format",   "Long-form · Short-form · Written · Mixed?", ""),
        ("audience_size",    "Rough audience size?", ""),
        ("biggest_blocker",  "Where do you struggle most — ideation, writing, editing, distribution?", ""),
    ],
    "Researcher": [
        ("field",            "Field of research?", ""),
        ("stage",            "PhD · Postdoc · Industry · Independent?", ""),
        ("current_paper",    "Working paper or topic you're on now?", ""),
        ("tools",            "Main tools (Python, R, Stata, LaTeX, Jupyter…)?", ""),
    ],
    "Student": [
        ("level",            "Undergrad · Masters · PhD · Self-taught?", ""),
        ("subject",          "Main subject / major?", ""),
        ("current_focus",    "What are you studying or working on right now?", ""),
        ("goal",             "Short-term goal (exam, project, paper)?", ""),
    ],
    "Data Scientist": [
        ("domain",           "Industry or domain?", ""),
        ("stack",            "Stack (pandas, polars, spark, SQL, dbt…)?", ""),
        ("ml_focus",         "ML focus (classical, DL, LLM, analytics)?", ""),
        ("biggest_blocker",  "Biggest blocker right now?", ""),
    ],
    "Designer": [
        ("design_type",      "Product · Brand · Web · Motion · Other?", ""),
        ("tools",            "Main tools (Figma, Illustrator, After Effects…)?", ""),
        ("client_model",     "In-house · Freelance · Agency?", ""),
        ("current_project",  "What are you designing right now?", ""),
    ],
    "Trader / Finance": [
        ("market",           "Markets (equities, crypto, FX, derivatives)?", ""),
        ("style",            "Intraday · Swing · Position · Quant?", ""),
        ("capital_scope",    "Retail · Prop · Fund?", ""),
        ("focus_now",        "What're you watching this week?", ""),
    ],
    "Writer": [
        ("writing_type",     "Fiction · Non-fiction · Technical · Copywriting?", ""),
        ("venue",            "Venue (book, newsletter, blog, clients)?", ""),
        ("current_piece",    "What are you writing right now?", ""),
        ("biggest_blocker",  "Biggest blocker — ideas, drafting, editing, shipping?", ""),
    ],
    "Other": [
        ("role_description", "Describe your work in a sentence.", ""),
        ("current_focus",    "What are you focused on this week?", ""),
        ("tools",            "Main tools / software you use?", ""),
        ("biggest_blocker",  "Biggest blocker you'd want help with?", ""),
    ],
}


def all_niche_labels() -> List[str]:
    return list(NICHE_QUESTIONS.keys())


def get_niche_followups(niche: str) -> List[_Q]:
    return NICHE_QUESTIONS.get(niche, NICHE_QUESTIONS["Other"])
