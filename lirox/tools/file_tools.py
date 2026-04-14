"""
Lirox v1.0.0 — File Operations and Shell Execution Tools

Safe, sandboxed file operations and shell execution.
"""
from __future__ import annotations

import glob
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple


def _readlink_or_none(path: str) -> Optional[str]:
    """Return the symlink target for *path*, or None if not a symlink or on read error."""
    if not os.path.islink(path):
        return None
    try:
        return os.readlink(path)
    except OSError:
        return None


# ── File Safety ───────────────────────────────────────────────────────────────

def _is_safe_path(path: str) -> Tuple[bool, str]:
    """
    Returns (True, resolved_path) if safe, (False, reason) if blocked.
    Agent can only touch SAFE_DIRS; PROTECTED_PATHS are always blocked.
    Handles symlinks safely by resolving and checking the target.
    """
    from lirox.config import SAFE_DIRS_RESOLVED, PROTECTED_PATHS
    try:
        # BUG-C1 FIX: Use pathlib.Path.resolve() which correctly handles paths
        # with special characters like () and + on Windows (os.path.realpath()
        # can mangle such characters on Windows, causing [Errno 22] errors).
        if os.path.islink(path):
            target = _readlink_or_none(path)
            if target is None:
                return False, f"Symlink resolution error: unreadable link at {path}"
            try:
                resolved = str(Path(target).resolve())
            except (OSError, ValueError) as e:
                return False, f"Symlink resolution error: {e}"
        else:
            resolved = str(Path(path).resolve())
    except (OSError, ValueError) as e:
        return False, f"Path resolution error: {e}"

    for blocked in PROTECTED_PATHS:
        if resolved.startswith(blocked):
            return False, f"BLOCKED: {blocked} is a protected system path"

    for safe in SAFE_DIRS_RESOLVED:
        if resolved.startswith(safe):
            return True, resolved

    return False, (
        f"BLOCKED: Path '{resolved}' is outside permitted directories.\n"
        f"Allowed: Desktop, Documents, Downloads, Projects, Lirox project dir"
    )


# ── File Operations ───────────────────────────────────────────────────────────

def file_read(path: str, max_chars: int = 8000) -> str:
    """Read a file, returning its contents with metadata. Truncation is indicated."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        lines = content.count("\n") + 1
        # Bug #1: Indicate when content was truncated
        was_truncated = len(content) >= max_chars
        indicator = " (truncated)" if was_truncated else ""
        return f"📄 {path} ({lines} lines, {len(content)}{indicator} chars):\n\n{content}"
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def file_write(path: str, content: str, mode: str = "w") -> str:
    """Write content to a file. Mode must be 'w' (overwrite), 'a' (append), or 'x' (exclusive)."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    # Bug #10: Validate mode — only allow safe text modes
    if mode not in ("w", "a", "x"):
        return f"Invalid mode: '{mode}' (allowed: 'w' to overwrite, 'a' to append, 'x' for new file only)"
    try:
        os.makedirs(os.path.dirname(info) or ".", exist_ok=True)
        with open(info, mode, encoding="utf-8") as f:
            f.write(content)
        return f"✅ File saved to {info} ({len(content)} chars)"
    except FileExistsError:
        return f"File already exists (use mode='a' to append or mode='w' to overwrite): {info}"
    except Exception as e:
        return f"Write error: {e}"


def file_list(path: str = ".", pattern: str = "*", max_files: int = 100) -> str:
    """List files in a directory matching a glob pattern."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        matches = glob.glob(os.path.join(info, pattern), recursive=True)
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        lines = []
        total = len(matches)
        for m in sorted(matches)[:max_files]:
            # Bug #18: Catch stat errors on broken symlinks
            try:
                stat = os.stat(m)
                size_str = f"{stat.st_size // 1024}KB" if stat.st_size > 1024 else f"{stat.st_size}B"
            except (OSError, FileNotFoundError):
                # Broken symlink or inaccessible file — use '?' to distinguish from truly empty files
                size_str = "?"
            # Bug #11: Use a cleaner format that handles long paths without breaking
            is_dir = "[DIR]" if os.path.isdir(m) else "     "
            is_link = " →" if os.path.islink(m) else ""
            rel_path = os.path.relpath(m, info)
            lines.append(f"  {is_dir}  {size_str:>8}  {rel_path}{is_link}")
        header = f"📁 {path} ({total} items"
        if total > max_files:
            header += f", showing first {max_files}"
        header += "):"
        return header + "\n" + "\n".join(lines)
    except Exception as e:
        return f"List error: {e}"


def file_delete(path: str, confirm: bool = True) -> str:
    """Delete a file or directory. Requires confirm=False to delete directories."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        # Bug #3: Require explicit confirmation before deleting directories
        if os.path.isdir(info):
            if confirm:
                return (
                    f"⚠️  Directory deletion requires confirmation.\n"
                    f"Call file_delete('{path}', confirm=False) to proceed.\n"
                    f"This will permanently delete: {info}"
                )
            import shutil
            shutil.rmtree(info)
            return f"🗑️  Deleted directory: {info}"
        else:
            os.remove(info)
            return f"🗑️  Deleted: {info}"
    except Exception as e:
        return f"Delete error: {e}"


def file_search(root: str, query: str, max_results: int = 50) -> str:
    """Search file contents recursively for a string."""
    ok, info = _is_safe_path(root)
    if not ok:
        return info
    results: List[str] = []
    skipped: List[str] = []
    for dirpath, _, filenames in os.walk(info):
        for fn in filenames:
            if fn.endswith((".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml", ".toml")):
                fp = os.path.join(dirpath, fn)
                # Bug #5: Distinguish between encoding errors, permission errors, and other errors
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{os.path.relpath(fp, info)}:{i}: {line.rstrip()}")
                                if len(results) >= max_results:
                                    break
                except UnicodeDecodeError:
                    # Skip binary files silently
                    continue
                except PermissionError:
                    skipped.append(f"[SKIPPED] {os.path.relpath(fp, info)}: Permission denied")
                except Exception as e:
                    skipped.append(f"[ERROR] {os.path.relpath(fp, info)}: {e}")
        if len(results) >= max_results:
            break
    if not results and not skipped:
        return f"No matches for '{query}' in {root}"
    # Bug #4: Indicate when results are capped so user knows to narrow search
    output = "\n".join(results)
    if len(results) >= max_results:
        output += f"\n\n📄 Results capped at {max_results}. Use max_results param or narrow your search."
    if skipped:
        output += "\n" + "\n".join(skipped)
    return output


# ── Shell Execution ───────────────────────────────────────────────────────────

def run_shell(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command with security validation.
    Delegates to the hardened terminal tool (shell=False, shlex-parsed).
    Only commands in ALLOWED_COMMANDS are permitted.
    BLOCK_PATTERNS are always rejected.
    """
    from lirox.tools.terminal import run_command
    # run_command already does allowlist + injection checking + shell=False
    return run_command(command)


# ── Advanced File Operations ──────────────────────────────────────────────────

def file_stream(path: str, chunk_size: int = 4096) -> Generator[str, None, None]:
    """Stream a large file in chunks without loading it all into memory."""
    ok, info = _is_safe_path(path)
    if not ok:
        yield f"Error: {info}"
        return
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except FileNotFoundError:
        yield f"File not found: {path}"
    except Exception as e:
        yield f"Stream error: {e}"


def get_file_metadata(path: str) -> Dict:
    """Extract file metadata (size, timestamps, permissions, type) without reading content."""
    ok, info = _is_safe_path(path)
    if not ok:
        return {"error": info}
    try:
        stat = os.stat(info)
        import mimetypes
        mime_type, _ = mimetypes.guess_type(info)
        return {
            "path": info,
            "size_bytes": stat.st_size,
            "size_human": f"{stat.st_size // 1024}KB" if stat.st_size > 1024 else f"{stat.st_size}B",
            "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime)),
            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            "accessed": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_atime)),
            "permissions": oct(stat.st_mode)[-3:],
            "is_dir": os.path.isdir(info),
            "is_symlink": os.path.islink(info),
            "symlink_target": _readlink_or_none(info),
            "mime_type": mime_type or "unknown",
        }
    except (OSError, FileNotFoundError) as e:
        return {"error": f"Metadata error: {e}"}


def list_directory_tree(path: str = ".", depth: int = 3, ignore_hidden: bool = True) -> str:
    """Generate a visual directory tree up to the given depth."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info

    lines: List[str] = [f"📁 {path}"]
    ignored_count = [0]

    def _walk(dir_path: str, prefix: str, current_depth: int) -> None:
        if current_depth > depth:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except (OSError, PermissionError):
            lines.append(f"{prefix}[Permission denied]")
            return

        visible = []
        for e in entries:
            if ignore_hidden and e.startswith("."):
                ignored_count[0] += 1
                continue
            visible.append(e)

        for i, entry in enumerate(visible):
            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            full = os.path.join(dir_path, entry)
            if os.path.isdir(full):
                lines.append(f"{prefix}{connector}📁 {entry}/")
                extension = "    " if is_last else "│   "
                _walk(full, prefix + extension, current_depth + 1)
            else:
                try:
                    size = os.path.getsize(full)
                    size_str = f"{size // 1024}KB" if size > 1024 else f"{size}B"
                except OSError:
                    size_str = "?"
                lines.append(f"{prefix}{connector}{entry} ({size_str})")

    _walk(info, "", 1)
    if ignored_count[0]:
        lines.append(f"\n({ignored_count[0]} hidden entries omitted)")
    return "\n".join(lines)


# ── Patch Tool (surgical file edits) ─────────────────────────────────────────

def file_patch(path: str, old_text: str, new_text: str) -> str:
    """
    Surgically replace EXACT text in a file. Much safer than full file_write
    for making small targeted changes without corrupting the rest of the file.

    Returns success message or error. Shows context around the change.
    """
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()

        if old_text not in original:
            lines = original.splitlines()
            preview = "\n".join(lines[:10])
            return (
                f"❌ Text not found in {path}.\n"
                f"File starts with:\n{preview}\n\n"
                f"Make sure the old_text matches exactly (spaces, indentation, newlines)."
            )

        count = original.count(old_text)
        if count > 1:
            return (
                f"❌ Found {count} occurrences of that text in {path}. "
                f"Be more specific — include more surrounding context."
            )

        patched = original.replace(old_text, new_text, 1)

        # Backup before writing
        import shutil
        backup = info + f".bak.{int(time.time())}"
        try:
            shutil.copy2(info, backup)
        except Exception:
            pass  # backup failure is non-fatal

        with open(info, "w", encoding="utf-8") as f:
            f.write(patched)

        return f"✅ Patched {path} — replaced {len(old_text)} chars with {len(new_text)} chars"

    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Patch error: {e}"


def file_read_lines(path: str, start_line: int = 1, end_line: int = None) -> str:
    """
    Read specific line ranges from a file. Useful for large files.
    Lines are 1-indexed. end_line=None reads to end of file.
    """
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        start = max(1, start_line) - 1  # convert to 0-indexed
        end   = min(total, end_line) if end_line else total

        selected = lines[start:end]
        result = "".join(selected)

        return (
            f"📄 {path} (lines {start+1}–{end} of {total}):\n\n"
            f"{result}"
        )
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def create_directory(path: str) -> str:
    """Create a directory and all parent directories."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        os.makedirs(info, exist_ok=True)
        return f"✅ Directory created: {info}"
    except Exception as e:
        return f"Directory creation error: {e}"


def file_append(path: str, content: str) -> str:
    """Append content to a file. Creates the file if it doesn't exist."""
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        os.makedirs(os.path.dirname(info) or ".", exist_ok=True)
        with open(info, "a", encoding="utf-8") as f:
            f.write(content)
        return f"✅ Appended {len(content)} chars to {info}"
    except Exception as e:
        return f"Append error: {e}"


def file_search_advanced(
    root: str,
    query: str,
    extensions: Optional[List[str]] = None,
    max_results: int = 100,
) -> Dict:
    """
    Advanced file search with extension filtering and result metadata.

    Returns a dict with 'results', 'total', 'skipped', and 'truncated' keys.
    """
    ok, info = _is_safe_path(root)
    if not ok:
        return {"error": info}

    default_exts = (".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".html", ".css")
    search_exts = tuple(extensions) if extensions else default_exts

    results: List[Dict] = []
    skipped: List[str] = []

    for dirpath, _, filenames in os.walk(info):
        for fn in filenames:
            if not fn.endswith(search_exts):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            results.append({
                                "file": os.path.relpath(fp, info),
                                "line": lineno,
                                "text": line.rstrip(),
                            })
                            if len(results) >= max_results:
                                break
            except PermissionError:
                skipped.append(f"{os.path.relpath(fp, info)}: Permission denied")
            except UnicodeDecodeError:
                continue
            except Exception as e:
                skipped.append(f"{os.path.relpath(fp, info)}: {e}")
        if len(results) >= max_results:
            break

    return {
        "query": query,
        "root": root,
        "results": results,
        "total": len(results),
        "truncated": len(results) >= max_results,
        "skipped": skipped,
    }
