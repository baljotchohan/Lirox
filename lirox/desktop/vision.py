"""
Lirox v1.0.0 — Desktop Vision
Screen capture and visual analysis for the desktop control loop.
"""
from __future__ import annotations

import base64
import os
from typing import Tuple


class DesktopVision:
    """
    Captures the current screen and produces a textual description
    suitable for use in an LLM prompt.

    Two strategies are tried in order:
    1. PIL screenshot + OCR via pytesseract (preferred — gives exact text)
    2. PIL screenshot with base64 encoding for multimodal LLMs

    If neither dependency is available, a placeholder is returned so the
    rest of the pipeline keeps working (graceful degradation).
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def capture_and_describe(self) -> Tuple[str, str]:
        """
        Take a screenshot and return ``(base64_png, text_description)``.

        Returns
        -------
        base64_png:
            Base64-encoded PNG string (empty string if capture fails).
        text_description:
            Human-readable description of screen contents.
        """
        screenshot_b64 = ""
        description    = "Screen capture unavailable."

        try:
            import PIL.ImageGrab as _grab    # type: ignore
            img = _grab.grab()
        except Exception:
            try:
                import pyautogui as _pag    # type: ignore
                img = _pag.screenshot()
            except Exception:
                return screenshot_b64, description

        # OCR path
        try:
            import pytesseract as _tess    # type: ignore
            text = _tess.image_to_string(img).strip()
            description = f"Screen text (OCR):\n{text[:2000]}" if text else "Empty screen"
        except Exception:
            description = "Screen captured (OCR unavailable)"

        # Base64 encode for multimodal use
        try:
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            screenshot_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass

        return screenshot_b64, description

    def save_screenshot(self, path: str) -> bool:
        """
        Save the current screen to *path* as a PNG.

        Returns *True* on success.
        """
        try:
            import pyautogui as _pag    # type: ignore
            _pag.screenshot(path)
            return True
        except Exception:
            try:
                import PIL.ImageGrab as _grab    # type: ignore
                _grab.grab().save(path)
                return True
            except Exception:
                return False
