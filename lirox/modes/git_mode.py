"""Lirox — Smart Git Mode
AI-powered git automation: semantic commits, PR drafts, conflict resolution,
diff reviews, and intelligent log summaries.

Commands:
    /git commit         — AI writes the commit message from staged diff
    /git review         — Review staged changes before committing
    /git pr             — Draft a pull request description from branch diff
    /git explain [n]    — Explain last N commits in plain English
    /git fix-conflict   — AI resolves current merge conflicts
    /git log-ai [n]     — Beautiful AI-summarized git log
    /git status         — Smart git status with AI context
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.rule import Rule
from rich.markdown import Markdown


def _run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def _git_root():
    out, _, code = _run(["git", "rev-parse", "--show-toplevel"])
    return out if code == 0 else None

def _branch_name():
    out, _, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return out or "main"

def _staged_diff():
    out, _, _ = _run(["git", "diff", "--staged"])
    return out

def _unstaged_diff():
    out, _, _ = _run(["git", "diff"])
    return out

def _ticket_from_branch(branch):
    m = re.search(r"([A-Z]+-\d+)", branch)
    return m.group(1) if m else ""

def _parse_conventional_type(branch):
    for prefix in ["feat", "fix", "chore", "docs", "refactor", "test", "style", "perf", "ci"]:
        if branch.lower().startswith(prefix):
            return prefix
    return "feat"

def _llm(prompt):
    from lirox.utils.llm import generate_response
    return generate_response(prompt, provider="auto").strip()

def _strip_fences(text):
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    return text.strip()


# ──────────────────────────────────────────────────────────────
# /git commit
# ──────────────────────────────────────────────────────────────
def git_commit(console, parts):
    root = _git_root()
    if not root:
        console.print("[bold red]✗[/] Not inside a git repository."); return
    diff = _staged_diff()
    if not diff:
        unstaged = _unstaged_diff()
        if unstaged:
            console.print("[bold #FFC107]⚠[/] No staged changes. Run [bold]git add[/] first.")
        else:
            console.print("[dim]Nothing to commit — working tree clean.[/]")
        return

    branch = _branch_name()
    ticket = _ticket_from_branch(branch)
    diff_preview = diff[:6000]

    prompt = (
        f"You are a senior engineer writing a git commit message.\n"
        f"Branch: {branch}\n"
        f"{'Ticket: ' + ticket if ticket else ''}\n\n"
        f"Staged diff:\n```diff\n{diff_preview}\n```\n\n"
        "Write ONE conventional commit message:\n"
        "<type>(<scope>): <short imperative description>\n\n"
        "[optional body]\n[optional footer]\n\n"
        "Rules: type = feat|fix|chore|docs|refactor|test|style|perf|ci\n"
        "subject ≤72 chars, imperative mood, no period.\n"
        f"{'Add Refs: ' + ticket + ' in footer.' if ticket else ''}\n"
        "Output ONLY the commit message."
    )

    console.print("[dim #a78bfa]Analyzing diff…[/]")
    message = _strip_fences(_llm(prompt))

    console.print()
    console.print(Rule("[bold #FFC107]Suggested Commit Message[/]", style="#FFC107 dim"))
    console.print(Panel(message, border_style="#a78bfa", padding=(1, 2)))
    console.print()

    auto = "--yes" in parts or "-y" in parts
    if auto:
        do_commit = True
    else:
        answer = console.input("  [bold #FFC107]Commit? (y/e/n): [/]").strip().lower()
        do_commit = answer in ("y", "yes")
        if answer in ("e", "edit"):
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(message); tmp = f.name
            os.system(f"${{EDITOR:-nano}} {tmp}")
            with open(tmp) as f: message = f.read().strip()
            os.unlink(tmp); do_commit = True

    if do_commit:
        _, err, code = _run(["git", "commit", "-m", message], cwd=root)
        if code == 0: console.print("  [bold #10b981]✓ Committed![/]")
        else: console.print(f"  [bold red]✗ Commit failed:[/] {err}")
    else:
        console.print("  [dim]Cancelled.[/]")


# ──────────────────────────────────────────────────────────────
# /git review
# ──────────────────────────────────────────────────────────────
def git_review(console):
    root = _git_root()
    if not root:
        console.print("[bold red]✗[/] Not inside a git repository."); return
    diff = _staged_diff()
    if not diff:
        console.print("[dim]No staged changes to review.[/]"); return

    prompt = (
        "You are a senior code reviewer. Review this staged git diff.\n\n"
        f"```diff\n{diff[:8000]}\n```\n\n"
        "Structure your review:\n"
        "## Summary\nWhat does this change do?\n\n"
        "## Issues\nBugs, security risks, logic errors (or 'None found')\n\n"
        "## Improvements\nStyle, performance, readability suggestions\n\n"
        "## Verdict\nLGTM ✓ / Needs changes ⚠ / Critical issues ✗\n\n"
        "Be direct, concise, use markdown."
    )
    console.print("[dim #a78bfa]Reviewing staged changes…[/]")
    review = _llm(prompt)
    console.print()
    console.print(Rule("[bold #FFC107]Code Review[/]", style="#FFC107 dim"))
    console.print(Markdown(review))
    console.print()


# ──────────────────────────────────────────────────────────────
# /git pr
# ──────────────────────────────────────────────────────────────
def git_pr(console):
    root = _git_root()
    if not root:
        console.print("[bold red]✗[/] Not inside a git repository."); return
    branch = _branch_name()
    if branch in ("main", "master", "develop"):
        console.print(f"[bold #FFC107]⚠[/] On [bold]{branch}[/] — switch to a feature branch first."); return

    diff_out, _, code = _run(["git", "diff", f"main...{branch}"], cwd=root)
    if code != 0 or not diff_out:
        diff_out, _, _ = _run(["git", "diff", f"master...{branch}"], cwd=root)
    log_out, _, _ = _run(["git", "log", f"main..{branch}", "--oneline"], cwd=root)
    if not log_out:
        log_out, _, _ = _run(["git", "log", f"master..{branch}", "--oneline"], cwd=root)

    if not diff_out and not log_out:
        console.print("[dim]No changes versus main.[/]"); return

    ticket = _ticket_from_branch(branch)
    prompt = (
        f"Write a GitHub pull request for this branch.\n"
        f"Branch: {branch}\n{'Ticket: ' + ticket if ticket else ''}\n\n"
        f"Commits:\n{log_out}\n\nDiff:\n```diff\n{diff_out[:5000]}\n```\n\n"
        "Sections:\n## Title\n## Summary\n## Changes\n## Testing\n## Notes\n\n"
        "Output only the PR in markdown."
    )
    console.print("[dim #a78bfa]Drafting PR description…[/]")
    pr_text = _llm(prompt)
    console.print()
    console.print(Rule("[bold #FFC107]Pull Request Draft[/]", style="#FFC107 dim"))
    console.print(Markdown(pr_text))
    console.print()
    try:
        import subprocess as sp
        sp.run(["pbcopy"], input=pr_text.encode(), check=True, capture_output=True)
        console.print("  [dim #10b981]✓ Copied to clipboard[/]")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# /git explain
# ──────────────────────────────────────────────────────────────
def git_explain(console, parts):
    root = _git_root()
    if not root:
        console.print("[bold red]✗[/] Not a git repo."); return
    n = next((int(p) for p in parts if p.isdigit()), 5)
    log_out, _, code = _run(["git", "log", f"-{n}", "--pretty=format:%h|%s|%an|%ar", "--name-only"], cwd=root)
    if code != 0 or not log_out:
        console.print("[dim]No commits found.[/]"); return
    prompt = (
        f"Explain these {n} git commits in plain English:\n```\n{log_out}\n```\n\n"
        "Per commit: one sentence on what changed and why. Flag risky changes with ⚠. Use markdown."
    )
    console.print(f"[dim #a78bfa]Explaining last {n} commits…[/]")
    console.print()
    console.print(Rule(f"[bold #FFC107]Last {n} Commits[/]", style="#FFC107 dim"))
    console.print(Markdown(_llm(prompt)))
    console.print()


# ──────────────────────────────────────────────────────────────
# /git fix-conflict
# ──────────────────────────────────────────────────────────────
def git_fix_conflict(console):
    root = _git_root()
    if not root:
        console.print("[bold red]✗[/] Not a git repo."); return
    status_out, _, _ = _run(["git", "status", "--porcelain"], cwd=root)
    conflicted = [
        l[3:].strip() for l in status_out.splitlines()
        if l[:2] in ("UU", "AA", "DD", "AU", "UA")
    ]
    if not conflicted:
        console.print("[dim]No merge conflicts detected.[/]"); return

    console.print(f"  [bold #FFC107]Found {len(conflicted)} conflicted file(s)[/]")
    for f in conflicted: console.print(f"  [dim]  • {f}[/]")
    console.print()

    for filepath in conflicted[:5]:
        full_path = Path(root) / filepath
        try: content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            console.print(f"  [red]Cannot read {filepath}: {e}[/]"); continue
        if "<<<<<<" not in content: continue

        prompt = (
            f"Resolve the git merge conflict in `{filepath}`.\n\n"
            f"Conflicted file:\n```\n{content[:6000]}\n```\n\n"
            "Output ONLY the resolved file — remove all conflict markers. "
            "Preserve both intentions. Preserve all imports and indentation."
        )
        console.print(f"  [dim #a78bfa]Resolving {filepath}…[/]")
        resolved = _strip_fences(_llm(prompt))
        preview = resolved[:200] + "…" if len(resolved) > 200 else resolved
        console.print(Panel(f"[bold]{filepath}[/]\n\n[dim]{preview}[/]", title="[bold #10b981]Resolution[/]", border_style="#10b981"))
        answer = console.input("  [bold #FFC107]Apply? (y/n): [/]").strip().lower()
        if answer in ("y", "yes"):
            full_path.write_text(resolved, encoding="utf-8")
            _run(["git", "add", filepath], cwd=root)
            console.print(f"  [bold #10b981]✓ {filepath} resolved & staged[/]")
        else:
            console.print(f"  [dim]Skipped {filepath}[/]")


# ──────────────────────────────────────────────────────────────
# /git log-ai, /git status
# ──────────────────────────────────────────────────────────────
def git_log_ai(console, parts):
    root = _git_root()
    if not root: console.print("[bold red]✗[/] Not a git repo."); return
    n = next((int(p) for p in parts if p.isdigit()), 10)
    log_out, _, _ = _run(["git", "log", f"-{n}", "--pretty=format:%h  %ar  %an  %s"], cwd=root)
    if not log_out: console.print("[dim]No commits.[/]"); return
    console.print()
    console.print(Rule("[bold #FFC107]Git Log[/]", style="#FFC107 dim"))
    console.print(Syntax(log_out, "text", theme="monokai", word_wrap=True))
    console.print()

def git_status_ai(console):
    root = _git_root()
    if not root: console.print("[bold red]✗[/] Not a git repo."); return
    status_out, _, _ = _run(["git", "status", "--short"], cwd=root)
    branch = _branch_name()
    if not status_out:
        console.print(f"  [bold #10b981]✓[/] [dim]Clean · branch:[/] [bold]{branch}[/]"); return
    staged = [l for l in status_out.splitlines() if l and l[0] not in (" ", "?")]
    unstaged = [l for l in status_out.splitlines() if l and l[1] in "MADRCU?"]
    console.print(f"\n  [bold #FFC107]Branch:[/] {branch}")
    console.print(f"  [bold #10b981]Staged:[/] {len(staged)}  [bold #a78bfa]Unstaged:[/] {len(unstaged)}\n")
    console.print(Syntax(status_out, "text", theme="monokai", word_wrap=True))
    if staged:
        console.print("\n  [dim]Run [bold]/git commit[/] or [bold]/git review[/][/]")
    elif unstaged:
        console.print("\n  [dim]Run [bold]git add <file>[/] then [bold]/git commit[/][/]")


# ──────────────────────────────────────────────────────────────
# DISPATCHER
# ──────────────────────────────────────────────────────────────
def handle_git_command(cmd, console):
    parts = cmd.strip().split()
    sub = parts[1].lower() if len(parts) > 1 else "status"
    rest = parts[2:]
    dispatch = {
        "commit": lambda: git_commit(console, rest),
        "review": lambda: git_review(console),
        "pr":     lambda: git_pr(console),
        "explain": lambda: git_explain(console, rest),
        "why":    lambda: git_explain(console, rest),
        "fix-conflict": lambda: git_fix_conflict(console),
        "fix":    lambda: git_fix_conflict(console),
        "conflict": lambda: git_fix_conflict(console),
        "log-ai": lambda: git_log_ai(console, rest),
        "log":    lambda: git_log_ai(console, rest),
        "status": lambda: git_status_ai(console),
    }
    fn = dispatch.get(sub)
    if fn:
        fn()
    else:
        console.print(f"  [bold red]Unknown:[/] /git {sub}")
        console.print("  [dim]Subcommands: commit · review · pr · explain · fix-conflict · log-ai · status[/]")
