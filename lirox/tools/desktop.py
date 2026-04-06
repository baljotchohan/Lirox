"""
Lirox — Desktop Control Tool
Full device control: screenshot, cursor, keyboard, app launch.
Yellow glowing border overlay when desktop control is active.
Vision loop: see screen → think → act → verify.

Dependencies:
  pip install pyautogui pillow pytesseract
  macOS: grant Accessibility in System Settings → Privacy & Security → Accessibility
  Linux: apt-get install scrot xdotool tesseract-ocr
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import platform
import threading
from typing import Optional, Tuple, Generator

_SYSTEM = platform.system()  # "Darwin", "Linux", "Windows"

# Global overlay stop flag
_overlay_stop = threading.Event()


def _check_pyautogui():
    try:
        import pyautogui
        return pyautogui
    except ImportError:
        raise RuntimeError(
            "Desktop control requires pyautogui: pip install pyautogui pillow"
        )


# ── Yellow Glow Border Overlay ────────────────────────────────────────────────

def activate_desktop_mode() -> threading.Thread:
    """
    Show a yellow glowing pulsing border around the entire screen.
    Uses tkinter transparent always-on-top overlay.
    Returns the overlay thread.
    """
    _overlay_stop.clear()

    def _run_overlay():
        try:
            import tkinter as tk
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes('-topmost', True)
            root.attributes('-alpha', 0.0)

            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")

            canvas = tk.Canvas(root, bg='black', highlightthickness=0)
            canvas.pack(fill='both', expand=True)
            root.configure(bg='black')

            # Make black transparent (OS-level compositing)
            try:
                root.attributes('-transparentcolor', 'black')
            except Exception:
                pass  # Not all platforms support this

            border_w  = 6
            glow_color = "#FFD700"  # Gold yellow
            canvas.create_rectangle(0, 0, sw, border_w, fill=glow_color, outline="")
            canvas.create_rectangle(0, sh - border_w, sw, sh, fill=glow_color, outline="")
            canvas.create_rectangle(0, 0, border_w, sh, fill=glow_color, outline="")
            canvas.create_rectangle(sw - border_w, 0, sw, sh, fill=glow_color, outline="")

            # Pulse animation using mutable state
            state = {"alpha": 0.0, "direction": 1}

            def pulse():
                if _overlay_stop.is_set():
                    root.destroy()
                    return
                state["alpha"] += 0.05 * state["direction"]
                if state["alpha"] >= 0.85:
                    state["direction"] = -1
                elif state["alpha"] <= 0.1:
                    state["direction"] = 1
                state["alpha"] = max(0.0, min(1.0, state["alpha"]))
                root.attributes('-alpha', state["alpha"])
                root.after(50, pulse)

            pulse()
            root.mainloop()
        except Exception:
            pass  # tkinter unavailable — desktop mode still works without overlay

    t = threading.Thread(target=_run_overlay, daemon=True)
    t.start()
    return t


def deactivate_desktop_mode(overlay_thread: threading.Thread = None):
    """Remove the yellow border overlay."""
    _overlay_stop.set()


# ── Screenshot & OCR ──────────────────────────────────────────────────────────

def take_screenshot(path: str = None) -> str:
    from lirox.config import OUTPUTS_DIR
    if path is None:
        ts   = int(time.time())
        path = os.path.join(OUTPUTS_DIR, f"screenshot_{ts}.png")

    try:
        if _SYSTEM == "Darwin":
            subprocess.run(["screencapture", "-x", path], check=True, timeout=10)
        elif _SYSTEM == "Linux":
            try:
                subprocess.run(["scrot", path], check=True, timeout=10)
            except (subprocess.CalledProcessError, FileNotFoundError):
                pag = _check_pyautogui()
                img = pag.screenshot()
                img.save(path)
        else:
            pag = _check_pyautogui()
            img = pag.screenshot()
            img.save(path)
        return path
    except Exception as e:
        return f"Screenshot error: {e}"


def get_screen_content_text(path: str = None) -> str:
    """
    Take a screenshot and extract visible text via OCR.
    Requires: pip install pytesseract tesseract
    """
    if path is None:
        path = take_screenshot()
    if path.startswith("Screenshot error"):
        return path
    try:
        from PIL import Image
        import pytesseract
        img  = Image.open(path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception:
        return f"Screenshot saved at: {path} (install pytesseract for text extraction)"


# ── Mouse & Keyboard ──────────────────────────────────────────────────────────

def move_mouse(x: int, y: int) -> str:
    pag = _check_pyautogui()
    pag.moveTo(x, y, duration=0.3)
    return f"Mouse moved to ({x}, {y})"


def click(x: int = None, y: int = None, button: str = "left") -> str:
    pag = _check_pyautogui()
    if x is not None and y is not None:
        pag.click(x, y, button=button)
        return f"Clicked {button} at ({x}, {y})"
    else:
        pag.click(button=button)
        return f"Clicked {button} at current position"


def double_click(x: int, y: int) -> str:
    pag = _check_pyautogui()
    pag.doubleClick(x, y)
    return f"Double-clicked at ({x}, {y})"


def type_text(text: str, interval: float = 0.02) -> str:
    pag = _check_pyautogui()
    pag.write(text, interval=interval)
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


def press_key(key: str) -> str:
    pag = _check_pyautogui()
    if '+' in key:
        parts = key.split('+')
        pag.hotkey(*parts)
    else:
        pag.press(key)
    return f"Pressed: {key}"


def hotkey(*keys: str) -> str:
    pag = _check_pyautogui()
    pag.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def scroll(clicks: int = 3, direction: str = "down") -> str:
    pag = _check_pyautogui()
    amount = -clicks if direction == "down" else clicks
    pag.scroll(amount)
    return f"Scrolled {direction} {abs(clicks)} clicks"


# ── App Control ───────────────────────────────────────────────────────────────

def launch_app(app_name: str) -> str:
    try:
        if _SYSTEM == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
            return f"Launched: {app_name}"
        elif _SYSTEM == "Linux":
            subprocess.Popen([app_name.lower()])
            return f"Launched: {app_name}"
        else:
            subprocess.Popen(["start", app_name], shell=True)
            return f"Launched: {app_name}"
    except Exception as e:
        return f"Launch error: {e}"


def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    try:
        if _SYSTEM == "Darwin":
            subprocess.Popen(["open", url])
        elif _SYSTEM == "Linux":
            subprocess.Popen(["xdg-open", url])
        else:
            subprocess.Popen(["start", url], shell=True)
        return f"Opened URL: {url}"
    except Exception as e:
        return f"Open URL error: {e}"


def open_file(file_path: str) -> str:
    try:
        if _SYSTEM == "Darwin":
            subprocess.Popen(["open", file_path])
        elif _SYSTEM == "Linux":
            subprocess.Popen(["xdg-open", file_path])
        else:
            os.startfile(file_path)
        return f"Opened: {file_path}"
    except Exception as e:
        return f"Open error: {e}"


def get_open_windows() -> str:
    try:
        if _SYSTEM == "Darwin":
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process whose background only is false'],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        elif _SYSTEM == "Linux":
            result = subprocess.run(
                ["wmctrl", "-l"], capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        else:
            try:
                import pygetwindow as gw
                windows = gw.getAllTitles()
                return "\n".join(w for w in windows if w)
            except ImportError:
                return "Install pygetwindow: pip install pygetwindow"
    except Exception as e:
        return f"Window list error: {e}"


def find_on_screen(image_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
    pag = _check_pyautogui()
    try:
        loc = pag.locateCenterOnScreen(image_path, confidence=confidence)
        if loc:
            return (loc.x, loc.y)
    except Exception:
        pass
    return None


# ── DesktopController — Vision Loop ──────────────────────────────────────────

class DesktopController:
    """
    Autonomous desktop control with continuous screen understanding.
    Uses screenshot + OCR/vision to understand screen state.
    Shows yellow glowing border when active.
    """

    def __init__(self):
        self._active        = False
        self._screen_state  = {}
        self._overlay_thread = None
        self._monitor_thread = None
        self._stop_monitor  = threading.Event()

    def start(self):
        """Activate desktop control: yellow border + begin screen monitoring."""
        self._active = True
        self._overlay_thread = activate_desktop_mode()
        self._start_screen_monitor()

    def stop(self):
        """Deactivate and remove border."""
        self._active = False
        self._stop_monitor.set()
        deactivate_desktop_mode(self._overlay_thread)

    def _start_screen_monitor(self):
        """Background thread: screenshot every 2s, extract text."""
        self._stop_monitor.clear()

        def _monitor():
            while self._active and not self._stop_monitor.is_set():
                try:
                    path = take_screenshot()
                    text = get_screen_content_text(path)
                    self._screen_state = {
                        "screenshot": path,
                        "text":       text,
                        "timestamp":  time.time(),
                    }
                except Exception:
                    pass
                time.sleep(2)

        self._monitor_thread = threading.Thread(target=_monitor, daemon=True)
        self._monitor_thread.start()

    def get_screen_state(self) -> dict:
        """Get current screen text + screenshot path."""
        return self._screen_state

    def execute_task(self, task_description: str) -> Generator:
        """
        Execute a high-level task on the desktop.
        Vision loop: see → think → act → verify.
        """
        from lirox.utils.llm import generate_response
        import json as _json, re as _re

        max_steps = 20
        for step in range(max_steps):
            if not self._active:
                break

            # 1. See current screen
            state       = self.get_screen_state()
            screen_text = state.get("text", "Screen content not yet available.")

            yield {"type": "tool_call", "message": f"👁️  Reading screen (step {step + 1}/{max_steps})..."}

            # 2. Think: what action to take next
            action_json = generate_response(
                f"Task: {task_description}\n"
                f"Step: {step + 1}\n"
                f"Current screen content (OCR):\n{screen_text[:2000]}\n\n"
                f"What single action should I take next to complete this task? "
                f"If the task is complete, output action=done.\n"
                f'Output ONLY JSON: {{"action": "click|type|press|launch|open_url|screenshot|done", '
                f'"target": "...", "value": "...", "reason": "..."}}',
                provider="auto",
                system_prompt="You are a desktop automation agent. Output ONLY valid JSON. No explanation.",
            )

            # 3. Parse action
            try:
                m = _re.search(r'\{.*\}', action_json, _re.DOTALL)
                if not m:
                    yield {"type": "tool_result", "message": "⚠️ Could not parse action JSON"}
                    break
                action = _json.loads(m.group())
            except Exception as e:
                yield {"type": "tool_result", "message": f"⚠️ Parse error: {e}"}
                break

            yield {"type": "agent_progress",
                   "message": f"🖥️  Step {step + 1}: {action.get('reason', action.get('action', ''))}"}

            # 4. Execute action
            act    = action.get("action", "")
            target = action.get("target", "")
            value  = action.get("value", "")

            if act == "done":
                yield {"type": "tool_result", "message": "✅ Task completed"}
                break
            elif act == "click":
                result = self._find_and_click(target)
                yield {"type": "tool_result", "message": result}
            elif act == "type":
                result = type_text(value or target)
                yield {"type": "tool_result", "message": result}
            elif act == "press":
                result = press_key(value or target or "return")
                yield {"type": "tool_result", "message": result}
            elif act == "launch":
                result = launch_app(target)
                yield {"type": "tool_result", "message": result}
            elif act == "open_url":
                result = open_url(target or value)
                yield {"type": "tool_result", "message": result}
            elif act == "screenshot":
                path = take_screenshot()
                self._screen_state = {
                    "screenshot": path,
                    "text":       get_screen_content_text(path),
                    "timestamp":  time.time(),
                }
                yield {"type": "tool_result", "message": f"📸 Screenshot: {path}"}
            else:
                yield {"type": "tool_result", "message": f"⚠️ Unknown action: {act}"}

            time.sleep(0.8)  # wait for screen to update after action

    def _find_and_click(self, target: str) -> str:
        """Find a UI element by text and click it."""
        try:
            if _SYSTEM == "Darwin":
                # Try AppleScript first (most reliable on macOS)
                script = (
                    f'tell application "System Events"\n'
                    f'  click (first button of (first window of (first application process '
                    f'whose frontmost is true)) whose name is "{target}")\n'
                    f'end tell'
                )
                result = subprocess.run(
                    ["osascript", "-e", script], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return f"Clicked: {target}"
            elif _SYSTEM == "Linux":
                subprocess.run(["xdotool", "search", "--name", target, "click"],
                                timeout=5, capture_output=True)
                return f"Clicked window: {target}"
            else:
                # Windows: pyautogui image match
                pag = _check_pyautogui()
                pos = pag.locateOnScreen(target, confidence=0.8)
                if pos:
                    pag.click(pos)
                    return f"Clicked at {pos}"
        except Exception as e:
            return f"Click failed: {e}"
        return f"Could not find: {target}"


# ── High-Level Task Helper (backward compat) ───────────────────────────────────

def execute_desktop_task(task: dict) -> str:
    """Execute a structured desktop task dict."""
    action = task.get("action", "")
    if action == "screenshot":
        return take_screenshot(task.get("path"))
    elif action == "click":
        return click(task.get("x"), task.get("y"), task.get("button", "left"))
    elif action == "double_click":
        return double_click(task["x"], task["y"])
    elif action == "type":
        return type_text(task.get("text", ""))
    elif action in ("key", "press"):
        return press_key(task.get("key", task.get("value", "")))
    elif action == "hotkey":
        keys = task.get("keys", [])
        return hotkey(*keys)
    elif action in ("launch", "open_app"):
        app = task.get("app", task.get("name", task.get("target", "")))
        return launch_app(app)
    elif action in ("open_file", "open_url"):
        target = task.get("file", task.get("url", task.get("target", "")))
        if target.startswith("http"):
            return open_url(target)
        return open_file(target)
    elif action == "scroll":
        return scroll(task.get("clicks", 3), task.get("direction", "down"))
    elif action == "get_screen":
        return get_screen_content_text()
    elif action == "get_windows":
        return get_open_windows()
    else:
        return f"Unknown desktop action: {action}"


# ── Clipboard ────────────────────────────────────────────────────────────────

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
        return f"Copied to clipboard: {text[:50]}"
    except Exception as e:
        return f"Clipboard error: {e}"


def get_clipboard() -> str:
    try:
        if _SYSTEM == "Darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True)
            return result.stdout
        elif _SYSTEM == "Linux":
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True
            )
            return result.stdout
        else:
            import pyperclip
            return pyperclip.paste()
    except Exception as e:
        return f"Clipboard error: {e}"
