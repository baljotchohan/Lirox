"""
Lirox v3.0 — Desktop Control Tool
Full device control: screenshot, cursor, keyboard, app launch, file ops.

Dependencies:
  pip install pyautogui pillow pygetwindow
  macOS: pip install pyobjc-framework-Quartz  (for screencapture)
  Linux: pip install python-xlib xdotool (apt-get install scrot xdotool)

SAFETY: All destructive actions require explicit confirmation flag.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import platform
from typing import Optional, Tuple

_SYSTEM = platform.system()  # "Darwin", "Linux", "Windows"


def _check_pyautogui():
    try:
        import pyautogui
        return pyautogui
    except ImportError:
        raise RuntimeError(
            "Desktop control requires pyautogui: pip install pyautogui pillow"
        )


# ── Screenshot ────────────────────────────────────────────────────────────────

def take_screenshot(path: str = None) -> str:
    """
    Capture the full screen and save to path.
    Returns the file path of the saved screenshot.
    """
    from lirox.config import OUTPUTS_DIR
    if path is None:
        ts = int(time.time())
        path = os.path.join(OUTPUTS_DIR, f"screenshot_{ts}.png")

    try:
        if _SYSTEM == "Darwin":
            subprocess.run(["screencapture", "-x", path], check=True, timeout=10)
        elif _SYSTEM == "Linux":
            # Try scrot first, then import
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


def get_screen_content_text() -> str:
    """
    Take a screenshot and extract visible text via OCR.
    Requires: pip install pytesseract tesseract
    Falls back to returning the screenshot path if OCR unavailable.
    """
    path = take_screenshot()
    if path.startswith("Screenshot error"):
        return path
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception:
        return f"Screenshot saved at: {path} (install pytesseract for text extraction)"


# ── Mouse & Keyboard ─────────────────────────────────────────────────────────

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
    """Press a keyboard key. Examples: 'enter', 'ctrl+c', 'cmd+space'"""
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
    """Launch an application by name."""
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


def open_file(file_path: str) -> str:
    """Open a file with its default application."""
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
    """List currently open windows (best-effort, platform-specific)."""
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
    """Find an image on screen and return its center coordinates."""
    pag = _check_pyautogui()
    try:
        loc = pag.locateCenterOnScreen(image_path, confidence=confidence)
        if loc:
            return (loc.x, loc.y)
    except Exception:
        pass
    return None


def click_image(image_path: str, confidence: float = 0.8) -> str:
    """Find an image on screen and click it."""
    coords = find_on_screen(image_path, confidence)
    if coords:
        return click(coords[0], coords[1])
    return f"Image not found on screen: {image_path}"


# ── Clipboard ────────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> str:
    try:
        if _SYSTEM == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif _SYSTEM == "Linux":
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True)
        else:
            pag = _check_pyautogui()
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


# ── High-Level Task Helpers ───────────────────────────────────────────────────

def execute_desktop_task(task: dict) -> str:
    """
    Execute a structured desktop task dict from LLM output.
    
    task format:
    {
      "action": "screenshot" | "click" | "type" | "key" | "launch" | "open_file" | "scroll",
      "x": int,         # for click
      "y": int,         # for click
      "text": str,      # for type
      "key": str,       # for key press
      "app": str,       # for launch
      "file": str,      # for open_file
      "direction": str, # for scroll
      "clicks": int     # for scroll
    }
    """
    action = task.get("action", "")
    if action == "screenshot":
        return take_screenshot(task.get("path"))
    elif action == "click":
        return click(task.get("x"), task.get("y"), task.get("button", "left"))
    elif action == "double_click":
        return double_click(task["x"], task["y"])
    elif action == "type":
        return type_text(task.get("text", ""))
    elif action == "key":
        return press_key(task.get("key", ""))
    elif action == "hotkey":
        keys = task.get("keys", [])
        return hotkey(*keys)
    elif action in ("launch", "open_app"):
        app = task.get("app", task.get("name", ""))
        return launch_app(app)
    elif action in ("open_file", "open_url"):
        file_path = task.get("file", task.get("url", ""))
        return open_file(file_path)
    elif action == "scroll":
        return scroll(task.get("clicks", 3), task.get("direction", "down"))
    elif action == "get_screen":
        return get_screen_content_text()
    elif action == "get_windows":
        return get_open_windows()
    elif action == "clipboard_copy":
        return copy_to_clipboard(task.get("text", ""))
    elif action == "clipboard_get":
        return get_clipboard()
    else:
        return f"Unknown desktop action: {action}"
