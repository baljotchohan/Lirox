"""
Lirox v3.0 — Desktop Control Engine
Full OS control: screenshot, mouse, keyboard, apps, files, clipboard.
Yellow glowing border overlay when agent is in control.
Vision loop: see → plan → act → verify → repeat.

Requirements:
  pip install pyautogui pillow pytesseract
  macOS: System Settings → Privacy → Accessibility → grant Terminal
  Linux: sudo apt install scrot xdotool tesseract-ocr
  Windows: pip install pygetwindow
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import platform
import threading
from typing import Optional, Tuple, Generator, Dict, Any

_SYSTEM = platform.system()  # "Darwin" | "Linux" | "Windows"

# ── Global agent state flags ──────────────────────────────────────────────────
_overlay_stop    = threading.Event()
_agent_lock      = threading.Event()   # set = agent owns desktop, block user input
_pause_requested = threading.Event()   # user hit /pause mid-task


def is_agent_locked() -> bool:
    """True while agent controls the desktop."""
    return _agent_lock.is_set()


def request_pause():
    """Signal the running agent to pause after the current step."""
    _pause_requested.set()


def clear_pause():
    """Clear a previous pause request (used by /resume)."""
    _pause_requested.clear()


def is_paused() -> bool:
    return _pause_requested.is_set()


# ── Dependency check ──────────────────────────────────────────────────────────

def _check_pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True   # move mouse to corner to abort
        pyautogui.PAUSE    = 0.05
        return pyautogui
    except ImportError:
        raise RuntimeError(
            "Desktop control requires: pip install pyautogui pillow\n"
            "macOS: grant Accessibility in System Settings → Privacy"
        )


# ── Yellow Glow Border Overlay ────────────────────────────────────────────────

def activate_desktop_mode() -> threading.Thread:
    """
    Show a pulsing yellow border around the entire screen (tkinter overlay).
    Skipped on macOS (NSWindow main-thread restriction) — terminal status
    provides the same signal there.
    Returns the overlay thread.
    """
    _overlay_stop.clear()

    def _run_overlay():
        if _SYSTEM == "Darwin":
            _overlay_stop.wait()
            return

        try:
            import tkinter as tk
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.0)

            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")

            canvas = tk.Canvas(root, bg="black", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            root.configure(bg="black")
            try:
                root.attributes("-transparentcolor", "black")
            except Exception:
                pass

            bw = 8
            gold = "#FFD700"
            canvas.create_rectangle(0, 0, sw, bw, fill=gold, outline="")
            canvas.create_rectangle(0, sh - bw, sw, sh, fill=gold, outline="")
            canvas.create_rectangle(0, 0, bw, sh, fill=gold, outline="")
            canvas.create_rectangle(sw - bw, 0, sw, sh, fill=gold, outline="")

            state = {"alpha": 0.1, "dir": 1}

            def pulse():
                if _overlay_stop.is_set():
                    root.destroy()
                    return
                state["alpha"] += 0.04 * state["dir"]
                if state["alpha"] >= 0.9:
                    state["dir"] = -1
                elif state["alpha"] <= 0.1:
                    state["dir"] = 1
                root.attributes("-alpha", max(0.0, min(1.0, state["alpha"])))
                root.after(40, pulse)

            pulse()
            root.mainloop()
        except Exception:
            pass  # overlay is cosmetic; agent continues without it

    t = threading.Thread(target=_run_overlay, daemon=True)
    t.start()
    return t


def deactivate_desktop_mode(overlay_thread: threading.Thread = None):
    """Stop the yellow border overlay."""
    _overlay_stop.set()


# ── Screenshot & OCR ──────────────────────────────────────────────────────────

def take_screenshot(path: str = None) -> str:
    """
    Capture the screen. Returns the saved file path.
    Falls back gracefully across macOS/Linux/Windows.
    """
    from lirox.config import OUTPUTS_DIR
    if path is None:
        ts   = int(time.time() * 1000)
        path = os.path.join(OUTPUTS_DIR, f"screen_{ts}.png")

    try:
        if _SYSTEM == "Darwin":
            subprocess.run(["screencapture", "-x", path], check=True, timeout=10)
        elif _SYSTEM == "Linux":
            try:
                subprocess.run(["scrot", path], check=True, timeout=10)
            except (subprocess.CalledProcessError, FileNotFoundError):
                pag = _check_pyautogui()
                pag.screenshot().save(path)
        else:
            pag = _check_pyautogui()
            pag.screenshot().save(path)
        return path
    except Exception as e:
        return f"screenshot_error:{e}"


def ocr_screen(path: str = None) -> str:
    """
    Take a screenshot and extract all visible text using tesseract OCR.
    Returns raw text string.
    """
    if path is None:
        path = take_screenshot()
    if path.startswith("screenshot_error"):
        return f"Could not capture screen: {path}"
    try:
        from PIL import Image
        import pytesseract
        return pytesseract.image_to_string(Image.open(path)).strip()
    except ImportError:
        return f"[OCR unavailable — install: pip install pytesseract pillow]\nScreenshot: {path}"
    except Exception as e:
        return f"[OCR error: {e}]\nScreenshot at: {path}"


# ── Mouse ─────────────────────────────────────────────────────────────────────

def move_mouse(x: int, y: int) -> str:
    pag = _check_pyautogui()
    pag.moveTo(x, y, duration=0.25)
    return f"Mouse → ({x}, {y})"


def click(x: int = None, y: int = None, button: str = "left") -> str:
    pag = _check_pyautogui()
    if x is not None and y is not None:
        pag.click(x, y, button=button)
        return f"Clicked {button} at ({x}, {y})"
    pag.click(button=button)
    return f"Clicked {button} at cursor"


def double_click(x: int, y: int) -> str:
    pag = _check_pyautogui()
    pag.doubleClick(x, y)
    return f"Double-clicked ({x}, {y})"


def right_click(x: int, y: int) -> str:
    pag = _check_pyautogui()
    pag.rightClick(x, y)
    return f"Right-clicked ({x}, {y})"


def drag(x1: int, y1: int, x2: int, y2: int) -> str:
    pag = _check_pyautogui()
    pag.dragTo(x2, y2, duration=0.4)
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def scroll(clicks: int = 3, direction: str = "down", x: int = None, y: int = None) -> str:
    pag = _check_pyautogui()
    amount = -clicks if direction == "down" else clicks
    if x and y:
        pag.scroll(amount, x=x, y=y)
    else:
        pag.scroll(amount)
    return f"Scrolled {direction} {abs(clicks)} ticks"


# ── Keyboard ──────────────────────────────────────────────────────────────────

def type_text(text: str, interval: float = 0.03) -> str:
    pag = _check_pyautogui()
    pag.write(text, interval=interval)
    preview = text[:60] + ("…" if len(text) > 60 else "")
    return f"Typed: {preview}"


def press_key(key: str) -> str:
    """
    Press a single key or hotkey combo.
    Supports: 'enter', 'tab', 'escape', 'ctrl+c', 'cmd+space', etc.
    """
    pag = _check_pyautogui()
    if "+" in key:
        parts = [p.strip() for p in key.split("+")]
        # normalize cmd → command on macOS
        parts = ["command" if p == "cmd" else p for p in parts]
        pag.hotkey(*parts)
    else:
        pag.press(key)
    return f"Key: {key}"


def hotkey(*keys: str) -> str:
    pag = _check_pyautogui()
    pag.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


# ── App & File Launch ─────────────────────────────────────────────────────────

def launch_app(app_name: str) -> str:
    """Open an application by name (cross-platform)."""
    try:
        if _SYSTEM == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        elif _SYSTEM == "Linux":
            subprocess.Popen([app_name.lower()])
        else:
            subprocess.Popen(["start", app_name], shell=True)
        return f"Launched: {app_name}"
    except Exception as e:
        return f"Launch failed ({app_name}): {e}"


def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    try:
        if _SYSTEM == "Darwin":
            subprocess.Popen(["open", url])
        elif _SYSTEM == "Linux":
            subprocess.Popen(["xdg-open", url])
        else:
            subprocess.Popen(["start", url], shell=True)
        return f"Opened: {url}"
    except Exception as e:
        return f"Open URL failed: {e}"


def open_file(file_path: str) -> str:
    """Open a file with its default application."""
    try:
        if _SYSTEM == "Darwin":
            subprocess.Popen(["open", file_path])
        elif _SYSTEM == "Linux":
            subprocess.Popen(["xdg-open", file_path])
        else:
            os.startfile(file_path)
        return f"Opened file: {file_path}"
    except Exception as e:
        return f"Open file failed: {e}"


# ── Window Inspection ─────────────────────────────────────────────────────────

def get_open_windows() -> str:
    """List all currently open application windows."""
    try:
        if _SYSTEM == "Darwin":
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process '
                 'whose background only is false'],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip()
        elif _SYSTEM == "Linux":
            r = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=5)
            return r.stdout.strip()
        else:
            try:
                import pygetwindow as gw
                return "\n".join(t for t in gw.getAllTitles() if t)
            except ImportError:
                return "Install pygetwindow: pip install pygetwindow"
    except Exception as e:
        return f"Window list error: {e}"


def find_on_screen(image_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
    """Find a template image on screen. Returns (x, y) center or None."""
    pag = _check_pyautogui()
    try:
        loc = pag.locateCenterOnScreen(image_path, confidence=confidence)
        return (loc.x, loc.y) if loc else None
    except Exception:
        return None


# ── Clipboard ─────────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> str:
    try:
        if _SYSTEM == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif _SYSTEM == "Linux":
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True)
        else:
            import pyperclip
            pyperclip.copy(text)
        return f"Clipboard: {text[:60]}"
    except Exception as e:
        return f"Clipboard write error: {e}"


def get_clipboard() -> str:
    try:
        if _SYSTEM == "Darwin":
            return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
        elif _SYSTEM == "Linux":
            return subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True
            ).stdout
        else:
            import pyperclip
            return pyperclip.paste()
    except Exception as e:
        return f"Clipboard read error: {e}"


# ── AppleScript / xdotool click-by-name ─────────────────────────────────────

def _find_and_click(target: str) -> str:
    """
    Click a UI element by its visible label (button name, window title, etc.)
    Uses AppleScript on macOS, xdotool on Linux, pyautogui image search on Windows.
    """
    try:
        if _SYSTEM == "Darwin":
            script = (
                f'tell application "System Events"\n'
                f'  set frontApp to name of first application process '
                f'whose frontmost is true\n'
                f'  tell process frontApp\n'
                f'    click (first button whose name is "{target}")\n'
                f'  end tell\n'
                f'end tell'
            )
            r = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                return f"Clicked: {target}"
            # Try UI element search fallback
            script2 = (
                f'tell application "System Events"\n'
                f'  set frontApp to name of first application process '
                f'whose frontmost is true\n'
                f'  tell process frontApp\n'
                f'    click (first UI element whose name contains "{target}")\n'
                f'  end tell\n'
                f'end tell'
            )
            r2 = subprocess.run(
                ["osascript", "-e", script2],
                capture_output=True, text=True, timeout=5
            )
            return f"Clicked: {target}" if r2.returncode == 0 else f"Not found: {target}"

        elif _SYSTEM == "Linux":
            r = subprocess.run(
                ["xdotool", "search", "--name", target, "click"],
                timeout=5, capture_output=True
            )
            return f"Clicked window: {target}"
        else:
            pag = _check_pyautogui()
            pos = pag.locateOnScreen(target, confidence=0.8)
            if pos:
                pag.click(pos)
                return f"Clicked at {pos}"
    except Exception as e:
        return f"Click '{target}' failed: {e}"
    return f"Element not found: {target}"


# ── DesktopController — The Vision-Action Loop ────────────────────────────────

class DesktopController:
    """
    Autonomous desktop controller with full vision feedback.
    
    Lifecycle:
        ctrl = DesktopController()
        ctrl.start()                        # activates yellow border, locks input
        for event in ctrl.run_task(task):   # vision → plan → act → verify loop
            yield event
        ctrl.stop()                         # removes border, unlocks input
    """

    def __init__(self):
        self._active         = False
        self._overlay_thread = None
        self._screen_state: Dict[str, Any] = {}
        self._step_history: list = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Activate desktop control: yellow border + lock user input."""
        self._active         = True
        self._step_history   = []
        _agent_lock.set()
        _pause_requested.clear()
        self._overlay_thread = activate_desktop_mode()

    def stop(self):
        """Deactivate: remove border, unlock user input."""
        self._active = False
        _agent_lock.clear()
        _pause_requested.clear()
        deactivate_desktop_mode(self._overlay_thread)

    # ── Screen ────────────────────────────────────────────────────────────────

    def refresh_screen(self) -> Dict[str, Any]:
        """Take a screenshot and extract screen text."""
        path = take_screenshot()
        text = ocr_screen(path) if not path.startswith("screenshot_error") else ""
        self._screen_state = {
            "path":      path,
            "text":      text,
            "timestamp": time.time(),
        }
        return self._screen_state

    def get_screen(self) -> Dict[str, Any]:
        return self._screen_state

    # ── Main Task Execution Loop ───────────────────────────────────────────────

    def run_task(
        self, task: str, max_steps: int = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Execute a natural-language desktop task using the vision-action loop.
        
        Yields event dicts:
          {"type": "tool_call",      "message": "..."}  — before action
          {"type": "tool_result",    "message": "..."}  — after action
          {"type": "agent_progress", "message": "..."}  — step reasoning
          {"type": "done",           "message": "..."}  — task complete
          {"type": "paused",         "message": "..."}  — user paused
          {"type": "error",          "message": "..."}  — unrecoverable error
        """
        from lirox.config import DESKTOP_MAX_STEPS, DESKTOP_ACTION_DELAY
        from lirox.utils.llm import generate_response

        if max_steps is None:
            max_steps = DESKTOP_MAX_STEPS

        # Initial screen capture
        yield {"type": "tool_call", "message": "👁️  Capturing initial screen state…"}
        state = self.refresh_screen()
        yield {"type": "tool_result",
               "message": f"📸 Screen captured — {len(state.get('text',''))} chars visible"}

        consecutive_failures = 0

        for step in range(1, max_steps + 1):
            if not self._active:
                break

            # ── Check for pause ───────────────────────────────────────────────
            if is_paused():
                yield {"type": "paused",
                       "message": "⏸  Agent paused. Type /resume to continue."}
                # Wait until resumed or stopped
                while is_paused() and self._active:
                    time.sleep(0.3)
                if not self._active:
                    break
                yield {"type": "agent_progress", "message": "▶  Resuming task…"}
                state = self.refresh_screen()

            screen_text = state.get("text", "Screen not readable")

            # ── Build step history context (last 6 steps) ─────────────────────
            history_ctx = ""
            if self._step_history:
                recent = self._step_history[-6:]
                history_ctx = "\nPrevious steps:\n" + "\n".join(
                    f"  {i+1}. {s}" for i, s in enumerate(recent)
                )

            # ── Ask LLM: what single action to take next ──────────────────────
            yield {"type": "tool_call",
                   "message": f"🧠 Step {step}/{max_steps} — reasoning…"}

            prompt = (
                f"TASK: {task}\n"
                f"STEP: {step} of {max_steps}\n"
                f"CURRENT SCREEN (OCR):\n{screen_text[:3000]}\n"
                f"{history_ctx}\n\n"
                f"What SINGLE action should I take next to progress toward completing this task?\n"
                f"If the task is fully complete, output action=done.\n"
                f"If stuck or need user input, output action=ask.\n\n"
                f"Output ONLY valid JSON, no explanation:\n"
                f'{{"action": "click|type|key|scroll|launch|open_url|open_file|'
                f'move_mouse|double_click|right_click|drag|'
                f'screenshot|read_screen|get_windows|clipboard_copy|clipboard_paste|done|ask", '
                f'"target": "element label or text to find (for click)", '
                f'"x": null_or_int, "y": null_or_int, '
                f'"value": "text to type / key to press / url / app / text to copy", '
                f'"reason": "brief explanation of why"}}'
            )

            action_raw = generate_response(
                prompt,
                provider="auto",
                system_prompt=(
                    "You are a desktop automation agent with vision. "
                    "Analyze the screen text and output ONLY a single valid JSON action object. "
                    "No markdown, no explanation, just the JSON."
                ),
            )

            # ── Parse JSON action ─────────────────────────────────────────────
            try:
                m = re.search(r"\{[^{}]*\}", action_raw, re.DOTALL)
                if not m:
                    raise ValueError("No JSON found in LLM response")
                action = json.loads(m.group())
            except Exception as e:
                consecutive_failures += 1
                yield {"type": "tool_result",
                       "message": f"⚠️  Parse error (attempt {consecutive_failures}): {e}"}
                if consecutive_failures >= 3:
                    yield {"type": "error",
                           "message": "❌ Failed to parse 3 consecutive actions. Stopping."}
                    break
                time.sleep(1)
                continue

            consecutive_failures = 0

            act    = action.get("action", "")
            target = action.get("target", "")
            value  = action.get("value", "")
            ax     = action.get("x")
            ay     = action.get("y")
            reason = action.get("reason", act)

            yield {"type": "agent_progress",
                   "message": f"🖥️  {reason}"}
            self._step_history.append(f"{act}: {target or value or reason}")

            # ── Execute action ────────────────────────────────────────────────
            result = self._execute_action(act, target, value, ax, ay)
            yield {"type": "tool_result", "message": result}

            if act == "done":
                yield {"type": "done",
                       "message": f"✅ Task complete in {step} steps: {value or reason}"}
                return

            if act == "ask":
                yield {"type": "done",
                       "message": f"❓ Agent needs input: {value or reason}"}
                return

            # ── Wait for screen to update then re-capture ─────────────────────
            time.sleep(DESKTOP_ACTION_DELAY)
            state = self.refresh_screen()

        yield {"type": "done",
               "message": f"⏹  Reached step limit ({max_steps}). Task may be incomplete."}

    # ── Action Dispatch ───────────────────────────────────────────────────────

    def _execute_action(
        self, act: str, target: str, value: str,
        x: Optional[int], y: Optional[int]
    ) -> str:
        """Map action name → tool function and execute."""
        try:
            if act == "click":
                if x is not None and y is not None:
                    return click(x, y)
                if target:
                    return _find_and_click(target)
                return "click requires x,y or target"

            elif act == "double_click":
                if x is not None and y is not None:
                    return double_click(x, y)
                return "double_click requires x,y"

            elif act == "right_click":
                if x is not None and y is not None:
                    return right_click(x, y)
                return "right_click requires x,y"

            elif act == "move_mouse":
                if x is not None and y is not None:
                    return move_mouse(x, y)
                return "move_mouse requires x,y"

            elif act == "drag":
                # value format: "x1,y1,x2,y2"
                try:
                    parts = [int(v.strip()) for v in value.split(",")]
                    return drag(*parts)
                except Exception:
                    return f"drag parse error: {value}"

            elif act == "scroll":
                direction = "down" if "down" in (value or "").lower() else "up"
                tries = 3
                try:
                    tries = int(value) if value and value.isdigit() else 3
                except Exception:
                    pass
                return scroll(tries, direction, x, y)

            elif act == "type":
                text = value or target
                return type_text(text) if text else "type requires value"

            elif act == "key":
                key = value or target or "return"
                return press_key(key)

            elif act == "launch":
                return launch_app(target or value)

            elif act == "open_url":
                return open_url(target or value)

            elif act == "open_file":
                return open_file(target or value)

            elif act == "screenshot":
                path = take_screenshot()
                state = self.refresh_screen()
                return f"📸 Screenshot: {path}"

            elif act == "read_screen":
                state = self.refresh_screen()
                text = state.get("text", "")
                return f"Screen text ({len(text)} chars): {text[:300]}…"

            elif act == "get_windows":
                return get_open_windows()

            elif act == "clipboard_copy":
                return copy_to_clipboard(value or target)

            elif act == "clipboard_paste":
                content = get_clipboard()
                return f"Clipboard: {content[:100]}"

            elif act in ("done", "ask"):
                return value or target or "done"

            else:
                return f"Unknown action: {act}"

        except Exception as e:
            return f"Action '{act}' error: {e}"


# ── File Operations (with safety checks) ─────────────────────────────────────

def _is_safe_path(path: str) -> Tuple[bool, str]:
    """
    Returns (True, resolved_path) if safe, (False, reason) if blocked.
    Agent can only touch SAFE_DIRS; PROTECTED_PATHS are always blocked.
    """
    from lirox.config import SAFE_DIRS_RESOLVED, PROTECTED_PATHS
    try:
        resolved = os.path.realpath(os.path.abspath(path))
    except Exception as e:
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


def file_read(path: str, max_chars: int = 8000) -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        with open(info, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        lines = content.count("\n") + 1
        return f"📄 {path} ({lines} lines, {len(content)} chars):\n\n{content}"
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Read error: {e}"


def file_write(path: str, content: str, mode: str = "w") -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        os.makedirs(os.path.dirname(info) or ".", exist_ok=True)
        with open(info, mode, encoding="utf-8") as f:
            f.write(content)
        return f"✅ Written {len(content)} chars → {path}"
    except Exception as e:
        return f"Write error: {e}"


def file_list(path: str = ".", pattern: str = "*") -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        import glob
        matches = glob.glob(os.path.join(info, pattern), recursive=True)
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        lines = []
        for m in sorted(matches)[:100]:
            stat = os.stat(m)
            size = stat.st_size
            size_str = f"{size//1024}KB" if size > 1024 else f"{size}B"
            lines.append(f"  {'[DIR]' if os.path.isdir(m) else '':>5}  {size_str:>8}  {os.path.relpath(m, info)}")
        return f"📁 {path}:\n" + "\n".join(lines)
    except Exception as e:
        return f"List error: {e}"


def file_delete(path: str) -> str:
    ok, info = _is_safe_path(path)
    if not ok:
        return info
    try:
        if os.path.isdir(info):
            import shutil
            shutil.rmtree(info)
            return f"🗑️  Deleted directory: {path}"
        else:
            os.remove(info)
            return f"🗑️  Deleted: {path}"
    except Exception as e:
        return f"Delete error: {e}"


def file_search(root: str, query: str) -> str:
    """Search file contents recursively for a string."""
    ok, info = _is_safe_path(root)
    if not ok:
        return info
    results = []
    for dirpath, _, filenames in os.walk(info):
        for fn in filenames:
            if fn.endswith((".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml", ".toml")):
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{os.path.relpath(fp, info)}:{i}: {line.rstrip()}")
                                if len(results) >= 50:
                                    break
                except Exception:
                    pass
        if len(results) >= 50:
            break
    if not results:
        return f"No matches for '{query}' in {root}"
    return "\n".join(results[:50]) + (f"\n… ({len(results)} total)" if len(results) == 50 else "")


# ── Shell Execution ───────────────────────────────────────────────────────────

def run_shell(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command with security validation.
    Only commands in ALLOWED_COMMANDS are permitted.
    BLOCK_PATTERNS are always rejected.
    """
    from lirox.config import ALLOWED_COMMANDS, BLOCK_PATTERNS

    # Block dangerous patterns
    for pattern in BLOCK_PATTERNS:
        if pattern.lower() in command.lower():
            return f"❌ BLOCKED: '{pattern}' is a forbidden command pattern"

    # Check first token is in allowed list
    first_token = command.strip().split()[0].lower() if command.strip() else ""
    base_cmd = os.path.basename(first_token)
    if base_cmd not in ALLOWED_COMMANDS:
        return (
            f"❌ Command '{base_cmd}' is not in the allowed list.\n"
            f"Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        if not output.strip():
            return f"✅ Command ran (no output)"
        return output.strip()[:4000]
    except subprocess.TimeoutExpired:
        return f"❌ Command timed out after {timeout}s"
    except Exception as e:
        return f"❌ Shell error: {e}"


# ── Backward-compat high-level dispatcher ────────────────────────────────────

def execute_desktop_task(task: dict) -> str:
    """Legacy dict-based task dispatcher (kept for backward compat)."""
    action = task.get("action", "")
    if action == "screenshot":        return take_screenshot(task.get("path"))
    if action == "click":             return click(task.get("x"), task.get("y"), task.get("button", "left"))
    if action == "double_click":      return double_click(task["x"], task["y"])
    if action == "type":              return type_text(task.get("text", ""))
    if action in ("key", "press"):    return press_key(task.get("key", task.get("value", "")))
    if action == "hotkey":            return hotkey(*task.get("keys", []))
    if action in ("launch", "open_app"): return launch_app(task.get("app", task.get("target", "")))
    if action == "open_url":          return open_url(task.get("url", task.get("target", "")))
    if action == "open_file":         return open_file(task.get("file", task.get("target", "")))
    if action == "scroll":            return scroll(task.get("clicks", 3), task.get("direction", "down"))
    if action == "get_screen":        return ocr_screen()
    if action == "get_windows":       return get_open_windows()
    if action == "read_file":         return file_read(task.get("path", ""))
    if action == "write_file":        return file_write(task.get("path", ""), task.get("content", ""))
    if action == "list_files":        return file_list(task.get("path", "."))
    if action == "run_command":       return run_shell(task.get("command", ""))
    return f"Unknown desktop action: {action}"
