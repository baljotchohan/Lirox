"""Lirox v1.1 — Pixel Art Mascot

Handles rendering of the Lirox terminal mascot using rich-pixels.
Generates the pixel art dynamically using Pillow (PIL) so no external
image assets are required. Degrades gracefully to emoji if dependencies fail.
"""
import io
import logging
from typing import Optional

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

_logger = logging.getLogger("lirox.ui.mascot")

# Color palette for the mascot
_BG = (20, 20, 25)           # Dark slate background
_MAIN = (255, 193, 7)        # Lirox Gold (#FFC107)
_ACCENT = (16, 185, 129)     # Emerald Green (#10b981)
_ERR = (239, 68, 68)         # Red
_THINK = (167, 139, 250)     # Purple

class MascotRenderer:
    def __init__(self):
        self._enabled = True
        self._frames = {}
        try:
            import PIL.Image
            import PIL.ImageDraw
            from rich_pixels import Pixels
            self._available = True
        except ImportError:
            self._available = False
            _logger.warning("rich-pixels or pillow not installed. Mascot gracefully degraded to emojis.")
            
        if self._available:
            self._generate_frames()

    def _generate_frames(self):
        """Generates pixel art frames purely in memory."""
        import PIL.Image
        import PIL.ImageDraw
        from rich_pixels import Pixels

        def create_face(eye_color, eye_char="normal", mouth="neutral", bg_color=_BG) -> Pixels:
            # 16x16 pixel art base
            size = 16
            img = PIL.Image.new("RGB", (size, size), bg_color)
            pixels = img.load()
            
            # Helper to draw a rect
            def draw_rect(x1, y1, w, h, color):
                for y in range(y1, y1 + h):
                    for x in range(x1, x1 + w):
                        if 0 <= x < size and 0 <= y < size:
                            pixels[x, y] = color

            # Draw outer robot shell
            draw_rect(2, 2, 12, 12, (50, 50, 60))  # casing
            draw_rect(3, 3, 10, 10, (30, 30, 40))  # screen
            
            # Eyes
            if eye_char == "normal":
                draw_rect(4, 5, 2, 2, eye_color)
                draw_rect(10, 5, 2, 2, eye_color)
            elif eye_char == "closed":
                draw_rect(4, 6, 2, 1, eye_color)
                draw_rect(10, 6, 2, 1, eye_color)
            elif eye_char == "wide":
                draw_rect(4, 4, 2, 3, eye_color)
                draw_rect(10, 4, 2, 3, eye_color)
            elif eye_char == "error":
                # X X
                pixels[4,4] = eye_color; pixels[5,5] = eye_color; pixels[4,5] = eye_color
                pixels[10,4] = eye_color; pixels[11,5] = eye_color; pixels[10,5] = eye_color
            
            # Mouth
            if mouth == "neutral":
                draw_rect(6, 10, 4, 1, eye_color)
            elif mouth == "smile":
                draw_rect(5, 9, 1, 1, eye_color)
                draw_rect(6, 10, 4, 1, eye_color)
                draw_rect(10, 9, 1, 1, eye_color)
            elif mouth == "sad":
                draw_rect(5, 10, 1, 1, eye_color)
                draw_rect(6, 9, 4, 1, eye_color)
                draw_rect(10, 10, 1, 1, eye_color)
            elif mouth == "processing":
                draw_rect(6, 10, 1, 1, eye_color)
                draw_rect(9, 10, 1, 1, eye_color)
                
            return Pixels.from_image(img)

        # Generate the state dictionary
        self._frames = {
            "idle": create_face(_MAIN, "normal", "smile"),
            "thinking": create_face(_THINK, "closed", "processing"),
            "computing": create_face(_ACCENT, "wide", "neutral"),
            "error": create_face(_ERR, "error", "sad"),
        }

    def render(self, state: str = "idle", message: str = "") -> RenderableType:
        """Returns a renderable panel containing the mascot and an optional speech bubble."""
        if not self._available or not self._enabled:
            return self._render_emoji_fallback(state, message)
            
        frame = self._frames.get(state, self._frames["idle"])
        
        # Determine border color based on state
        border_colors = {
            "idle": "#FFC107",
            "thinking": "#a78bfa",
            "computing": "#10b981",
            "error": "#ef4444"
        }
        bcolor = border_colors.get(state, "#FFC107")
        
        if message:
            # Combine mascot and text in a layout
            from rich.table import Table
            grid = Table.grid(padding=(0, 2))
            grid.add_row(frame, Text(message, style=f"bold {bcolor}"))
            return Panel(grid, border_style=bcolor, padding=(0, 1))
        
        return Panel(Align.center(frame), border_style=bcolor, padding=(0, 1), width=20)

    def _render_emoji_fallback(self, state: str, message: str) -> RenderableType:
        emojis = {
            "idle": "🤖",
            "thinking": "🤔",
            "computing": "⚡",
            "error": "❌",
        }
        emoji = emojis.get(state, "🤖")
        bcolor = "#FFC107"
        if state == "thinking": bcolor = "#a78bfa"
        elif state == "computing": bcolor = "#10b981"
        elif state == "error": bcolor = "#ef4444"
        
        content = f"{emoji}  {message}" if message else emoji
        return Panel(Text(content, style=bcolor), border_style=bcolor)

# Singleton instance
mascot = MascotRenderer()
