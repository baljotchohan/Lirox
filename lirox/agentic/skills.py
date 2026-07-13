"""Skill library — portable Markdown skills + a closed self-improvement loop.

Ported from two real 2026 open-source agents researched for this upgrade:

  * OpenClaw (github.com/openclaw/openclaw) — local-first memory/skills stored
    as plain Markdown files on disk, human-readable and community-shareable
    ("a portable skill format").
  * Hermes Agent (github.com/nousresearch/hermes-agent) — a "closed learning
    loop": after finishing a complex task, the agent writes itself a reusable
    skill, so it gets more capable the longer it runs, and that memory
    persists across restarts (not just within one session).

This module gives Lirox the same mechanic: skills are plain ``.md`` files with
a small YAML-like frontmatter header, stored at ``~/.lirox/skills/*.md`` —
inspectable, hand-editable, and shareable by just copying a file. No YAML
dependency: the frontmatter schema is small and controlled, so a minimal
parser keeps this dependency-free like the rest of lirox.agentic.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("lirox.agentic.skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def skills_dir() -> Path:
    override = os.getenv("LIROX_SKILLS_DIR")
    p = Path(override).expanduser() if override else Path.home() / ".lirox" / "skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "skill"


@dataclass
class Skill:
    slug: str
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    uses: int = 1
    created_at: str = ""
    source_task: str = ""
    procedure: str = ""  # the markdown body — steps, notes, gotchas
    path: Optional[Path] = None

    def to_markdown(self) -> str:
        kw = ", ".join(self.keywords)
        lines = [
            "---",
            f"name: {self.name}",
            f"description: {self.description}",
            f"keywords: [{kw}]",
            f"uses: {self.uses}",
            f"created_at: {self.created_at}",
            f"source_task: {self.source_task!r}",
            "---",
            "",
            self.procedure.strip(),
            "",
        ]
        return "\n".join(lines)

    def score(self, query_terms: List[str]) -> float:
        """Cheap keyword-overlap relevance score against a query — no
        embeddings, consistent with the rest of Lirox's retrieval code."""
        hay = " ".join([self.name, self.description, " ".join(self.keywords)]).lower()
        if not hay.strip():
            return 0.0
        hits = sum(1 for t in query_terms if t and t in hay)
        return hits / max(1, len(query_terms))


def _parse_list(value: str) -> List[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [v.strip().strip("'\"") for v in value.split(",") if v.strip()]


def _parse_frontmatter(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip()
    return out


def load_skill(path: Path) -> Optional[Skill]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return None
    fm = _parse_frontmatter(m.group(1))
    body = m.group(2)
    try:
        return Skill(
            slug=path.stem,
            name=fm.get("name", path.stem),
            description=fm.get("description", ""),
            keywords=_parse_list(fm.get("keywords", "[]")),
            uses=int(fm.get("uses", "1") or 1),
            created_at=fm.get("created_at", ""),
            source_task=fm.get("source_task", "").strip("'\""),
            procedure=body.strip(),
            path=path,
        )
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Skipping malformed skill %s: %s", path, exc)
        return None


class SkillLibrary:
    """Reads/writes the local, portable Markdown skill collection."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.dir = directory or skills_dir()

    def all(self) -> List[Skill]:
        out = []
        for p in sorted(self.dir.glob("*.md")):
            s = load_skill(p)
            if s:
                out.append(s)
        return out

    def search(self, query: str, k: int = 3, min_score: float = 0.2) -> List[Skill]:
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        if not terms:
            return []
        scored = [(s.score(terms), s) for s in self.all()]
        scored = [(sc, s) for sc, s in scored if sc >= min_score]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:k]]

    def get(self, slug: str) -> Optional[Skill]:
        p = self.dir / f"{slug}.md"
        return load_skill(p) if p.exists() else None

    def save(self, skill: Skill) -> Path:
        import datetime
        skill.slug = _slugify(skill.name)
        path = self.dir / f"{skill.slug}.md"
        if not skill.created_at:
            skill.created_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        path.write_text(skill.to_markdown(), encoding="utf-8")
        skill.path = path
        return path

    def bump_uses(self, slug: str) -> None:
        s = self.get(slug)
        if s:
            s.uses += 1
            self.save(s)

    @staticmethod
    def render_for_prompt(matches: List[Skill]) -> str:
        if not matches:
            return ""
        blocks = ["LEARNED SKILLS (from past sessions — reuse if relevant, adapt if not):"]
        for s in matches:
            blocks.append(f"\n### Skill: {s.name}\n{s.description}\n{s.procedure}")
        return "\n".join(blocks)


# ══════════════════════════════════════════════════════════════════════════
# Closed self-improvement loop (Hermes-style): after a verified-complete,
# non-trivial run, distill the transcript into a new reusable skill.
# ══════════════════════════════════════════════════════════════════════════

_DISTILL_SYSTEM = (
    "You turn a completed autonomous agent run into a reusable SKILL for future "
    "similar tasks. Read the TASK and TRANSCRIPT, then output ONLY a JSON object "
    "with exactly these string-typed fields (procedure MUST be a single string "
    "with embedded \\n line breaks, NEVER a JSON array): "
    '{"name": "short-kebab-case-skill-name", "description": "one sentence, when to use this", '
    '"keywords": ["3-6 short lowercase keywords"], '
    '"procedure": "1. step one\\n2. step two\\n... a numbered list of GENERAL steps '
    '(not the specific file names/values from this run) that would solve similar future '
    'tasks, plus any gotchas hit along the way, as ONE string"}. '
    "Generalize — strip task-specific literals (exact filenames, numbers) into placeholders."
)

# Regex fallback for when the model emits a malformed pseudo-JSON "procedure"
# array (bare unquoted lines instead of a string) — a real failure mode
# observed live, same family of issue as diff-apply brittleness elsewhere in
# this codebase. Extract fields independently rather than discarding the
# whole (often still useful) distillation.
_FIELD_RE = {
    "name": re.compile(r'"name"\s*:\s*"([^"]*)"'),
    "description": re.compile(r'"description"\s*:\s*"([^"]*)"'),
    "keywords": re.compile(r'"keywords"\s*:\s*\[(.*?)\]', re.DOTALL),
    "procedure": re.compile(r'"procedure"\s*:\s*(.*?)\s*\}\s*$', re.DOTALL),
}


def _lenient_parse_skill(text: str) -> Optional[Dict[str, Any]]:
    import json as _json

    for cand in (text,):
        try:
            return _json.loads(cand)
        except Exception:  # noqa: BLE001
            pass
        repaired = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            return _json.loads(repaired)
        except Exception:  # noqa: BLE001
            pass

    name_m = _FIELD_RE["name"].search(text)
    desc_m = _FIELD_RE["description"].search(text)
    kw_m = _FIELD_RE["keywords"].search(text)
    proc_m = _FIELD_RE["procedure"].search(text)
    if not (name_m and proc_m):
        return None

    keywords = []
    if kw_m:
        keywords = [k.strip().strip("'\"") for k in kw_m.group(1).split(",") if k.strip()]

    procedure = proc_m.group(1).strip()
    # Strip a wrapping array/quote left over from a malformed pseudo-array or
    # quoted string, then unescape literal "\n" sequences into real newlines.
    procedure = procedure.strip("[]").strip().strip('"').strip()
    procedure = procedure.replace("\\n", "\n")

    return {
        "name": name_m.group(1),
        "description": desc_m.group(1) if desc_m else "",
        "keywords": keywords,
        "procedure": procedure,
    }


def distill_skill(task: str, transcript_text: str, provider: str = "auto") -> Optional[Skill]:
    """LLM-distill a finished run into a new Skill object (unsaved)."""
    from lirox.utils.llm import generate_response
    from lirox.agentic.loop import _largest_json_span

    prompt = f"TASK:\n{task}\n\nTRANSCRIPT:\n{transcript_text[:8000]}"
    try:
        reply = generate_response(prompt, provider=provider,
                                  system_prompt=_DISTILL_SYSTEM + "\nOutput ONLY JSON.")
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Skill distillation LLM call failed: %s", exc)
        return None

    for cand in (reply, _largest_json_span(reply)):
        if not cand:
            continue
        data = _lenient_parse_skill(cand)
        if data is None:
            continue
        name = str(data.get("name", "")).strip()
        procedure = str(data.get("procedure", "")).strip()
        if not name or not procedure:
            continue
        return Skill(
            slug=_slugify(name),
            name=name,
            description=str(data.get("description", "")).strip(),
            keywords=[str(k).lower() for k in data.get("keywords", [])][:8],
            source_task=task[:200],
            procedure=procedure,
        )
    return None


def learn_from_run(
    task: str,
    transcript: List[str],
    *,
    min_steps: int = 3,
    similarity_threshold: float = 0.6,
    provider: str = "auto",
    library: Optional[SkillLibrary] = None,
) -> Optional[Skill]:
    """The closed learning-loop entry point. Call after a run finishes AND is
    critic-verified complete. Skips trivial runs (too few steps) and skips
    saving a near-duplicate of an existing skill (dedup by keyword overlap
    against the new skill's own keywords).

    Returns the newly-saved :class:`Skill`, or ``None`` if nothing new was
    written (trivial run, distillation failed, or an existing skill was
    reinforced instead — callers can use ``None`` to mean "no new skill to
    announce")."""
    if len(transcript) < min_steps:
        return None

    lib = library or SkillLibrary()
    skill = distill_skill(task, "\n".join(transcript), provider=provider)
    if skill is None:
        return None

    existing = lib.search(f"{skill.name} {skill.description} {' '.join(skill.keywords)}", k=1)
    if existing and existing[0].score([w for w in re.findall(r"[a-z0-9]+", skill.name.lower())]) >= similarity_threshold:
        lib.bump_uses(existing[0].slug)
        return None  # reinforced an existing skill — not a new one to announce

    lib.save(skill)
    _logger.info("Learned new skill: %s", skill.name)
    return skill
