"""
Lirox v1.0.0 — Desktop Actions
Mouse, keyboard, and application control primitives.
"""
from __future__ import annotations

import time
from typing import Optional


class DesktopActions:
    """
    Low-level desktop action primitives.

    All methods are safe to call even when the underlying libraries
    (pyautogui, subprocess) are unavailable — they return an error
    string rather than raising.

    Parameters
    ----------
    action_delay:
        Seconds to pause after each action to allow the UI to settle.
    """

    def __init__(self, action_delay: float = 0.6) -> None:
        self.action_delay = action_delay

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def click(self, target: str, button: str = "left") -> str:
        """
        Click on a screen element described by *target*.

        The target can be:
        - ``"x,y"`` — absolute pixel coordinates
        - A descriptive string like ``"OK button"`` (best-effort OCR locate)
        """
        try:
            import pyautogui as _pag    # type: ignore
            if "," in target and all(p.strip().lstrip("-").isdigit() for p in target.split(",", 1)):
                x, y = (int(v.strip()) for v in target.split(",", 1))
                _pag.click(x, y, button=button)
            else:
                loc = _pag.locateCenterOnScreen(target, confidence=0.8)
                if loc:
                    _pag.click(loc, button=button)
                else:
                    return f"Could not locate '{target}' on screen"
            time.sleep(self.action_delay)
            return f"Clicked {target}"
        except Exception as e:
            return f"Click error: {e}"

    def double_click(self, target: str) -> str:
        """Double-click on *target*."""
        try:
            import pyautogui as _pag    # type: ignore
            if "," in target:
                x, y = (int(v.strip()) for v in target.split(",", 1))
                _pag.doubleClick(x, y)
            else:
                loc = _pag.locateCenterOnScreen(target, confidence=0.8)
                if loc:
                    _pag.doubleClick(loc)
                else:
                    return f"Could not locate '{target}' on screen"
            time.sleep(self.action_delay)
            return f"Double-clicked {target}"
        except Exception as e:
            return f"Double-click error: {e}"

    def scroll(self, target: str, direction: str = "down", clicks: int = 3) -> str:
        """Scroll at *target* in *direction*."""
        try:
            import pyautogui as _pag    # type: ignore
            amount = -clicks if direction == "down" else clicks
            if "," in target:
                x, y = (int(v.strip()) for v in target.split(",", 1))
                _pag.scroll(amount, x=x, y=y)
            else:
                _pag.scroll(amount)
            time.sleep(self.action_delay)
            return f"Scrolled {direction} at {target}"
        except Exception as e:
            return f"Scroll error: {e}"

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.03) -> str:
        """Type *text* at the current cursor position."""
        try:
            import pyautogui as _pag    # type: ignore
            _pag.write(text, interval=interval)
            time.sleep(self.action_delay)
            return f"Typed: {text[:60]}{'...' if len(text) > 60 else ''}"
        except Exception as e:
            return f"Type error: {e}"

    def press_key(self, key: str) -> str:
        """
        Press a keyboard key or hotkey combination.

        Examples: ``"enter"``, ``"ctrl+c"``, ``"alt+tab"``.
        """
        try:
            import pyautogui as _pag    # type: ignore
            if "+" in key:
                parts = [k.strip() for k in key.split("+")]
                _pag.hotkey(*parts)
            else:
                _pag.press(key)
            time.sleep(self.action_delay)
            return f"Pressed: {key}"
        except Exception as e:
            return f"Key error: {e}"

    # ── Applications ──────────────────────────────────────────────────────────

    def open_app(self, app: str) -> str:
        """
        Open an application or URL.

        On macOS uses ``open``; on Linux uses ``xdg-open``; on Windows
        uses ``start``.
        """
        import subprocess
        import sys

        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", app])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", app])
            else:
                subprocess.Popen(["cmd", "/c", "start", "", app])
            time.sleep(1.5)
            return f"Opened: {app}"
        except Exception as e:
            return f"Open error: {e}"

    def get_clipboard(self) -> str:
        """Return the current clipboard text."""
        try:
            import pyperclip as _pc    # type: ignore
            return _pc.paste()
        except Exception:
            try:
                import subprocess
                result = subprocess.run(
                    ["pbpaste"], capture_output=True, text=True
                )
                return result.stdout
            except Exception as e:
                return f"Clipboard error: {e}"

    def set_clipboard(self, text: str) -> str:
        """Set the clipboard to *text*."""
        try:
            import pyperclip as _pc    # type: ignore
            _pc.copy(text)
            return f"Clipboard set ({len(text)} chars)"
        except Exception as e:
            return f"Clipboard error: {e}"
