"""Advanced Desktop Control with Live Screen Rendering"""
import os
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

try:
    import pyautogui
    import pyperclip
    from PIL import Image, ImageDraw, ImageFont
    HAS_DESKTOP = True
except ImportError:
    HAS_DESKTOP = False

from lirox.config import DESKTOP_ENABLED, PROJECT_ROOT
from lirox.utils.structured_logger import get_logger

logger = get_logger("lirox.tools.desktop_v2")


class AdvancedDesktopController:
    """Live desktop control with screen streaming & visual feedback."""
    
    def __init__(self):
        self.enabled = HAS_DESKTOP and DESKTOP_ENABLED
        self.screenshot_dir = Path(PROJECT_ROOT) / "outputs" / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.task_active = False
        self.screen_stream_buffer = None
        self.last_screenshot = None
        
    def get_screen_size(self) -> Tuple[int, int]:
        """Get current screen resolution."""
        if not self.enabled:
            return (1920, 1080)
        try:
            return pyautogui.size()
        except Exception as e:
            logger.warning(f"Could not get screen size: {e}")
            return (1920, 1080)
    
    def take_screenshot(self, annotate: bool = False) -> Optional[Image.Image]:
        """
        Take screenshot with optional annotation (crosshair, status).
        
        Args:
            annotate: Add glowing border + task status
            
        Returns:
            PIL Image object
        """
        if not self.enabled:
            return None
        
        try:
            # Capture screen
            screenshot = pyautogui.screenshot()
            
            # Add visual feedback if task active
            if annotate and self.task_active:
                self._add_glowing_border(screenshot)
                self._add_status_indicator(screenshot)
            
            self.last_screenshot = screenshot
            return screenshot
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
    
    def _add_glowing_border(self, img: Image.Image) -> None:
        """Add glowing cyan border effect."""
        draw = ImageDraw.Draw(img, 'RGBA')
        w, h = img.size
        border_width = 4
        glow_color = (0, 255, 255, 255)  # Cyan
        
        # Draw glowing border
        for i in range(border_width):
            opacity = int(255 * (1 - i / border_width))
            color = (0, 255, 255, opacity)
            draw.rectangle([i, i, w-i-1, h-i-1], outline=color, width=2)
    
    def _add_status_indicator(self, img: Image.Image) -> None:
        """Add status text + timestamp."""
        draw = ImageDraw.Draw(img, 'RGBA')
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status_text = f"⚡ Lirox Active  |  {timestamp}"
        
        # Draw semi-transparent background
        draw.rectangle([10, 10, 400, 50], fill=(0, 0, 0, 180))
        draw.text((20, 20), status_text, fill=(0, 255, 255, 255))
    
    def save_screenshot(self, name: str = None) -> Optional[Path]:
        """Save screenshot to outputs directory."""
        if not self.last_screenshot:
            return None
        
        if not name:
            name = f"screenshot_{int(time.time())}.png"
        
        filepath = self.screenshot_dir / name
        try:
            self.last_screenshot.save(str(filepath))
            logger.info(f"Screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Could not save screenshot: {e}")
            return None
    
    def find_element(self, image: Image.Image, threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        """
        Find element on screen using template matching.
        
        Args:
            image: Template image to find
            threshold: Match confidence (0-1)
            
        Returns:
            (x, y) coordinates or None
        """
        try:
            # Use pyautogui's locateOnScreen
            pos = pyautogui.locateOnScreen(image, confidence=threshold)
            if pos:
                # Return center of found region
                x, y, w, h = pos
                return (x + w // 2, y + h // 2)
        except Exception as e:
            logger.warning(f"Element not found: {e}")
        return None
    
    def click(self, x: int, y: int, double: bool = False) -> bool:
        """Click at coordinates."""
        if not self.enabled:
            return False
        
        try:
            if double:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y)
            time.sleep(0.5)  # Wait for UI response
            return True
        except Exception as e:
            logger.error(f"Click failed at ({x}, {y}): {e}")
            return False
    
    def type_text(self, text: str, delay: float = 0.05) -> bool:
        """Type text with character delay."""
        if not self.enabled:
            return False
        
        try:
            pyautogui.typewrite(text, interval=delay)
            return True
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press keyboard key (tab, enter, etc.)."""
        if not self.enabled:
            return False
        
        try:
            pyautogui.press(key)
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False
    
    def open_app(self, app_name: str) -> bool:
        """
        Open application by name.
        
        Works on:
        - macOS: via 'open' command
        - Linux: via 'xdg-open' or direct command
        - Windows: via 'start' command
        """
        if not self.enabled:
            return False
        
        import subprocess
        import sys
        
        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", "-a", app_name])
            elif sys.platform == "linux":
                subprocess.Popen(["xdg-open", app_name])
            elif sys.platform == "win32":  # Windows
                subprocess.Popen(["start", app_name], shell=True)
            
            time.sleep(2)  # Wait for app to launch
            return True
        except Exception as e:
            logger.error(f"Could not open app '{app_name}': {e}")
            return False
    
    def navigate_to_url(self, url: str) -> bool:
        """Open URL in default browser."""
        if not self.enabled:
            return False
        
        import subprocess
        import sys
        
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", url])
            else:
                import webbrowser
                webbrowser.open(url)
            
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Could not navigate to {url}: {e}")
            return False
    
    def _start_recording(self, task_name: str):
        """Start continuous screen recording to MP4 in a background thread."""
        try:
            import cv2
            import numpy as np
            
            w, h = self.get_screen_size()
            
            # Using mp4v codec for MP4
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            filename = self.screenshot_dir / f"{task_name}_{int(time.time())}.mp4"
            self.video_writer = cv2.VideoWriter(str(filename), fourcc, 5.0, (w, h))
            
            def record_loop():
                while self.task_active:
                    try:
                        screenshot = self.take_screenshot(annotate=True)
                        if screenshot:
                            frame = np.array(screenshot)
                            # Convert RGB to BGR for OpenCV
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                            self.video_writer.write(frame)
                    except Exception as e:
                        logger.error(f"Recording frame error: {e}")
                    time.sleep(0.1) # approx 5-10 fps
                    
                self.video_writer.release()
                logger.info(f"Full screen recording saved: {filename}")

            self.record_thread = threading.Thread(target=record_loop, daemon=True)
            self.record_thread.start()
            logger.info("Screen recording started.")
        except ImportError:
            logger.warning("cv2 or numpy missing. Full screen recording disabled. (pip install opencv-python numpy)")
    
    def start_task(self, task_description: str) -> Dict[str, Any]:
        """Start a new desktop task with live feedback."""
        self.task_active = True
        logger.info(f"Starting desktop task: {task_description}")
        
        # Start continuous screen recording
        self._start_recording("lirox_session")
        
        # Take initial screenshot
        screenshot = self.take_screenshot(annotate=True)
        if screenshot:
            self.save_screenshot(f"task_start_{int(time.time())}.png")
        
        return {
            "status": "active",
            "task": task_description,
            "screen_size": self.get_screen_size(),
            "timestamp": time.time(),
        }
    
    def end_task(self, success: bool = True) -> Dict[str, Any]:
        """End desktop task."""
        self.task_active = False
        
        if hasattr(self, 'record_thread') and self.record_thread.is_alive():
            self.record_thread.join(timeout=2.0)
            
        screenshot = self.take_screenshot(annotate=False)
        if screenshot:
            self.save_screenshot(f"task_end_{int(time.time())}.png")
        
        return {
            "status": "complete",
            "success": success,
            "timestamp": time.time(),
        }


# Global instance
_desktop = None

def get_desktop_controller() -> AdvancedDesktopController:
    """Get or create desktop controller."""
    global _desktop
    if _desktop is None:
        _desktop = AdvancedDesktopController()
    return _desktop
