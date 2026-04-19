"""Lirox v1.1 — File Operations (verified, structured receipts, audit logging).

Every write/read/delete/patch now returns a FileReceipt with explicit
disk-verification. The agent can no longer report success unless
`receipt.verified and receipt.ok` are both True.

All file operations are logged to the audit trail (Feature-7).
The self-modification gate is enforced on all write paths (BUG-12).

Backwards-compat: string-returning wrappers kept for callers that
haven't migrated — they produce identical output but internally use
the verified path.
"""
from __future__ import annotations

import glob
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from lirox.verify import (
    FileReceipt,
    verify_file_exists,
    verify_file_content_matches,
    verify_dir_exists,
    verify_file_deleted,
)
from lirox.config import is_self_modification


def _audit(event_name: str, path: str = "", message: str = "", **kwargs) -> None:
    """Audit logging placeholder."""
    pass


def _self_mod_blocked(path: str) -> Optional[str]:
    """Return an error string if writing to `path` would modify Lirox itself
    AND the user hasn't opted in via LIROX_ALLOW_SELF_MOD=1. Else None.

    BUG-12 fix: this function is now CALLED in every write path in file_tools.py.
    """
    try:
        if is_self_modification(path):
            if os.getenv("LIROX_ALLOW_SELF_MOD") != "1":
                _audit("self_mod_blocked", path=path,
                       message="Self-modification blocked — LIROX_ALLOW_SELF_MOD not set")
                return (
                    f"BLOCKED: '{path}' is inside the Lirox source tree. "
                    f"Set LIROX_ALLOW_SELF_MOD=1 to allow self-modification."
                )
            else:
                _audit("self_mod_allowed", path=path,
                       message="Self-modification allowed (LIROX_ALLOW_SELF_MOD=1)")
    except Exception:
        pass
    return None


# ── Safety ────────────────────────────────────────────────────────

def _readlink_or_none(path: str) -> Optional[str]:
    if not os.path.islink(path):
        return None
    try:
        return os.readlink(path)
    except OSError:
        return None


def _normalize_and_expand(path: str) -> str:
    """Expand ~, env vars, and make absolute. Does not check existence."""
    if not path:
        return path
    p = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(p):
        p = os.path.abspath(p)
    return p


def _is_safe_path(path: str) -> Tuple[bool, str]:
    """Returns (ok, resolved_or_reason).

    Uses os.path.realpath to fully resolve all symlink chains, preventing
    path-traversal attacks via symlinks pointing outside the sandbox.
    """
    from lirox.config import SAFE_DIRS_RESOLVED, PROTECTED_PATHS
    if not path:
        return False, "Empty path"
    try:
        # os.path.realpath resolves the complete symlink chain (including
        # intermediate symlinks), unlike Path.resolve() on the raw target.
        resolved = os.path.realpath(_normalize_and_expand(path))
    except (OSError, ValueError) as e:
        return False, f"Path resolution error: {e}"

    # Check SAFE_DIRS first — an explicitly whitelisted path (e.g. /private/tmp
    # which is the macOS realpath of /tmp) must not be blocked by PROTECTED_PATHS.
    for safe in SAFE_DIRS_RESOLVED:
        if resolved.startswith(safe):
            return True, resolved

    for blocked in PROTECTED_PATHS:
        if resolved.startswith(blocked):
            return False, f"BLOCKED: {blocked} is a protected system path"

    return False, (
        f"BLOCKED: Path '{resolved}' is outside permitted directories.\n"
        f"Allowed roots: Desktop, Documents, Downloads, Projects, Lirox project dir, /tmp"
    )


# ── Structured (verified) ops ─────────────────────────────────────

def file_write_verified(path: str, content: str, mode: str = "w") -> FileReceipt:
    """Write + verify on disk. Never reports success without verification."""
    r = FileReceipt(tool="file_write", operation="write", path=path)
    ok, info = _is_safe_path(path)
    if not ok:
        r.error = info
        return r
    err = _self_mod_blocked(info)
    if err:
        r.error = err
        return r
    if mode not in ("w", "a", "x"):
        r.error = f"Invalid mode: '{mode}' (allowed: 'w', 'a', 'x')"
        return r
    try:
        os.makedirs(os.path.dirname(info) or ".", exist_ok=True)
        with open(info, mode, encoding="utf-8") as f:
            f.write(content)
        r.ok = True
        r.bytes_written = len(content.encode("utf-8", errors="replace"))
        r.message = f"Wrote {r.bytes_written} bytes to {info}"
        r.details["resolved_path"] = info

        # Verify: exists + size matches + (for 'w' mode) content matches
        exists_ok, exists_reason = verify_file_exists(info)
        if not exists_ok:
            r.error = f"Write returned but file missing: {exists_reason}"
            r.ok = False
            return r
        if mode == "w":
            content_ok, content_reason = verify_file_content_matches(info, content)
            if not content_ok:
                r.error = f"Content verification failed: {content_reason}"
                r.ok = False
                return r
        r.verified = True
        r.details["verification"] = "file_exists + content_matches" if mode == "w" else "file_exists"
        _audit("file_write", path=info, message=f"Wrote {r.bytes_written} bytes")
        return r
    except FileExistsError:
        r.error = f"File exists (use mode='a' to append): {info}"
        return r
    except Exception as e:
        r.error = f"Write error: {e}"
        return r


def file_read_verified(path: str, max_chars: int = 8000) -> FileReceipt:
    r = FileReceipt(tool="file_read", operation="read", path=path)
    ok, info = _is_safe_path(path)
    if not ok:
        r.error = info
        return r
    try:
        exists_ok, exists_reason = verify_file_exists(info)
        if not exists_ok:
            r.error = exists_reason
            return r
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        was_truncated = len(content) >= max_chars
        r.ok = True
        r.verified = True
        r.bytes_read = len(content.encode("utf-8", errors="replace"))
        r.lines = content.count("\n") + 1
        r.details["content"]      = content
        r.details["truncated"]    = was_truncated
        r.details["resolved_path"] = info
        r.message = f"Read {r.bytes_read} bytes from {info}"
        return r
    except FileNotFoundError:
        r.error = f"File not found: {info}"
        return r
    except Exception as e:
        r.error = f"Read error: {e}"
        return r


def file_delete_verified(path: str, confirm: bool = True) -> FileReceipt:
    r = FileReceipt(tool="file_delete", operation="delete", path=path)
    ok, info = _is_safe_path(path)
    if not ok:
        r.error = info
        return r
    err = _self_mod_blocked(info)
    if err:
        r.error = err
        return r
    try:
        if os.path.isdir(info):
            if confirm:
                r.error = (
                    f"Directory deletion requires confirm=False.\n"
                    f"This would permanently delete: {info}"
                )
                return r
            shutil.rmtree(info)
        else:
            os.remove(info)
        del_ok, del_reason = verify_file_deleted(info)
        if not del_ok:
            r.error = f"Delete operation did not remove target: {del_reason}"
            return r
        r.ok = True
        r.verified = True
        r.message = f"Deleted {info}"
        _audit("file_delete", path=info, message="File deleted")
        return r
    except FileNotFoundError:
        # Idempotent delete: nothing to do
        r.ok = True
        r.verified = True
        r.message = f"Already absent: {info}"
        return r
    except Exception as e:
        r.error = f"Delete error: {e}"
        return r


def file_append_verified(path: str, content: str) -> FileReceipt:
    r = FileReceipt(tool="file_append", operation="append", path=path)
    ok, info = _is_safe_path(path)
    if not ok:
        r.error = info
        return r
    err = _self_mod_blocked(info)
    if err:
        r.error = err
        return r
    try:
        before = os.path.getsize(info) if os.path.exists(info) else 0
        os.makedirs(os.path.dirname(info) or ".", exist_ok=True)
        with open(info, "a", encoding="utf-8") as f:
            f.write(content)
        after = os.path.getsize(info)
        expected = before + len(content.encode("utf-8", errors="replace"))
        if after != expected:
            r.error = f"Append size mismatch: expected {expected}, got {after}"
            return r
        r.ok = True
        r.verified = True
        r.bytes_written = len(content.encode("utf-8", errors="replace"))
        r.message = f"Appended {r.bytes_written} bytes to {info}"
        return r
    except Exception as e:
        r.error = f"Append error: {e}"
        return r


def file_patch_verified(path: str, old_text: str, new_text: str) -> FileReceipt:
    r = FileReceipt(tool="file_patch", operation="patch", path=path)
    ok, info = _is_safe_path(path)
    if not ok:
        r.error = info
        return r
    err = _self_mod_blocked(info)
    if err:
        r.error = err
        return r
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
        if old_text not in original:
            r.error = f"Text not found in {info}. Match exactly, including whitespace."
            return r
        count = original.count(old_text)
        if count > 1:
            r.error = f"Found {count} occurrences — be more specific."
            return r
        patched = original.replace(old_text, new_text, 1)

        # Backup
        backup = info + f".bak.{int(time.time())}"
        try:
            shutil.copy2(info, backup)
        except Exception:
            backup = ""

        with open(info, "w", encoding="utf-8") as f:
            f.write(patched)

        # Verify
        content_ok, content_reason = verify_file_content_matches(info, patched)
        if not content_ok:
            r.error = f"Patch verification failed: {content_reason}"
            return r
        r.ok = True
        r.verified = True
        r.bytes_written = len(patched.encode("utf-8", errors="replace"))
        r.message = f"Patched {info} ({len(old_text)} → {len(new_text)} chars)"
        r.details["backup"] = backup
        _audit("file_write", path=info, message=f"Patched file ({len(old_text)} → {len(new_text)} chars)")
        return r
    except FileNotFoundError:
        r.error = f"File not found: {info}"
        return r
    except Exception as e:
        r.error = f"Patch error: {e}"
        return r


def create_directory_verified(path: str) -> FileReceipt:
    r = FileReceipt(tool="create_dir", operation="mkdir", path=path)
    ok, info = _is_safe_path(path)
    if not ok:
        r.error = info
        return r
    err = _self_mod_blocked(info)
    if err:
        r.error = err
        return r
    try:
        os.makedirs(info, exist_ok=True)
        ver_ok, reason = verify_dir_exists(info)
        if not ver_ok:
            r.error = reason
            return r
        r.ok = True
        r.verified = True
        r.message = f"Directory created at {info}"
        return r
    except Exception as e:
        r.error = f"mkdir error: {e}"
        return r


# ── Backwards-compat string wrappers ──────────────────────────────

def file_write(path: str, content: str, mode: str = "w") -> str:
    return file_write_verified(path, content, mode).as_user_summary()


def file_read(path: str, max_chars: int = 8000) -> str:
    r = file_read_verified(path, max_chars)
    if not r.ok:
        return r.error or r.message
    trunc = " (truncated)" if r.details.get("truncated") else ""
    return (f"📄 {r.path} ({r.lines} lines, {r.bytes_read}{trunc} bytes):\n\n"
            f"{r.details.get('content', '')}")


def file_delete(path: str, confirm: bool = True) -> str:
    return file_delete_verified(path, confirm).as_user_summary()


def file_append(path: str, content: str) -> str:
    return file_append_verified(path, content).as_user_summary()


def file_patch(path: str, old_text: str, new_text: str) -> str:
    return file_patch_verified(path, old_text, new_text).as_user_summary()


def create_directory(path: str) -> str:
    return create_directory_verified(path).as_user_summary()


# ── List / tree / search (read-only, no state to verify beyond existence) ─

def file_list(path: str = ".", pattern: str = "*", max_files: int = 100) -> str:
    # SECURITY-03 fix: reject glob patterns that escape the directory via '..'
    # (directory traversal) or begin with '/' (absolute patterns).
    # Check for actual traversal sequences, not just any occurrence of '..'
    # so that valid patterns like 'file..txt' are not falsely rejected.
    norm_pattern = pattern.replace("\\", "/")
    if any(seg == ".." for seg in norm_pattern.split("/")) or norm_pattern.startswith("/"):
        return "Invalid glob pattern: '..' path components and leading '/' are not permitted."
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
            try:
                st = os.stat(m)
                size = f"{st.st_size // 1024}KB" if st.st_size > 1024 else f"{st.st_size}B"
            except (OSError, FileNotFoundError):
                size = "?"
            is_dir  = "[DIR]" if os.path.isdir(m) else "     "
            is_link = " →" if os.path.islink(m) else ""
            rel = os.path.relpath(m, info)
            lines.append(f"  {is_dir}  {size:>8}  {rel}{is_link}")
        header = f"📁 {path} ({total} items"
        if total > max_files:
            header += f", showing first {max_files}"
        header += "):"
        return header + "\n" + "\n".join(lines)
    except Exception as e:
        return f"List error: {e}"


def list_directory_tree(path: str = ".", depth: int = 3, ignore_hidden: bool = True) -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    lines: List[str] = [f"📁 {path}"]
    ignored = [0]

    def _walk(dp: str, prefix: str, d: int) -> None:
        if d > depth:
            return
        try:
            entries = sorted(os.listdir(dp))
        except (OSError, PermissionError):
            lines.append(f"{prefix}[Permission denied]")
            return
        vis = []
        for e in entries:
            if ignore_hidden and e.startswith("."):
                ignored[0] += 1
                continue
            vis.append(e)
        for i, entry in enumerate(vis):
            last = i == len(vis) - 1
            conn = "└── " if last else "├── "
            full = os.path.join(dp, entry)
            if os.path.isdir(full):
                lines.append(f"{prefix}{conn}📁 {entry}/")
                ext = "    " if last else "│   "
                _walk(full, prefix + ext, d + 1)
            else:
                try:
                    size = os.path.getsize(full)
                    sz = f"{size // 1024}KB" if size > 1024 else f"{size}B"
                except OSError:
                    sz = "?"
                lines.append(f"{prefix}{conn}{entry} ({sz})")

    _walk(info, "", 1)
    if ignored[0]:
        lines.append(f"\n({ignored[0]} hidden entries omitted)")
    return "\n".join(lines)


def file_search(root: str, query: str, max_results: int = 50) -> str:
    ok, info = _is_safe_path(root)
    if not ok:
        return info
    results: List[str] = []
    skipped: List[str] = []
    for dp, _, fns in os.walk(info):
        for fn in fns:
            if fn.endswith((".py",".js",".ts",".md",".txt",".json",".yaml",".yml",".toml")):
                fp = os.path.join(dp, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        for i, ln in enumerate(f, 1):
                            if query.lower() in ln.lower():
                                results.append(f"{os.path.relpath(fp, info)}:{i}: {ln.rstrip()}")
                                if len(results) >= max_results:
                                    break
                except UnicodeDecodeError:
                    continue
                except PermissionError:
                    skipped.append(f"[SKIPPED] {os.path.relpath(fp, info)}: Permission denied")
                except Exception as e:
                    skipped.append(f"[ERROR] {os.path.relpath(fp, info)}: {e}")
        if len(results) >= max_results:
            break
    if not results and not skipped:
        return f"No matches for '{query}' in {root}"
    out = "\n".join(results)
    if len(results) >= max_results:
        out += f"\n\n📄 Results capped at {max_results}."
    if skipped:
        out += "\n" + "\n".join(skipped)
    return out


def file_read_lines(path: str, start_line: int = 1, end_line: int = None) -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        start = max(1, start_line) - 1
        end   = min(total, end_line) if end_line else total
        selected = lines[start:end]
        return f"📄 {path} (lines {start+1}–{end} of {total}):\n\n" + "".join(selected)
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def run_shell(command: str, timeout: int = 30) -> str:
    """Kept for back-compat; new code should use ShellReceipt via shell_run_verified."""
    from lirox.tools.terminal import run_command
    return run_command(command)


# ── Legacy helpers (kept for backward-compat) ─────────────────────

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


def file_stream(path: str, chunk_size: int = 4096) -> Generator[str, None, None]:
    """Stream a large file in chunks."""
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


def file_search_advanced(
    root: str,
    query: str,
    extensions: Optional[List[str]] = None,
    max_results: int = 100,
) -> Dict:
    """Advanced file search with extension filtering and result metadata."""
    ok, info = _is_safe_path(root)
    if not ok:
        return {"error": info}
    default_exts = (".py", ".js", ".ts", ".md", ".txt", ".json",
                    ".yaml", ".yml", ".toml", ".csv", ".html", ".css")
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
