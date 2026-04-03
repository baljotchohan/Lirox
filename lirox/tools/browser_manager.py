"""
Lirox v0.7.1 — Browser Session Manager (Hardened)

Manages Lightpanda browser instance lifecycle, session pooling,
and provides sync wrappers for the async CDP bridge.

Improvements over v0.7:
- AsyncBridge class: prevents deadlocks with strict timeouts + task cleanup
- Atomic session pool: thread-safe acquire/release with dead-session pruning
- Session health tracking with configurable error thresholds
"""

import asyncio
import logging
import time
import json
import os
import threading
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

from lirox.tools.browser_bridge import LightpandaBridge, BrowserLauncher
from lirox.tools.browser_security import BrowserSecurityValidator

logger = logging.getLogger("lirox.browser.manager")


# ─── AsyncBridge ──────────────────────────────────────────────────────────────
import concurrent.futures

class AsyncBridge:
    """
    Safely bridge async coroutines to synchronous code.
    
    Uses a SINGLE persistent dedicated background thread and event loop.
    This guarantees that all asyncio objects (like websockets or CDP sessions)
    are bound to the SAME loop, avoiding 'future attached to different loop' errors,
    even when calls originate from multiple different synchronous threads.
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self._loop = None
        self._thread = None
        self._lock = threading.Lock()
        self._ensure_running()

    def _ensure_running(self):
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro, timeout: int = None):
        self._ensure_running()
        effective_timeout = timeout or self.timeout

        async def _wrapper():
            return await asyncio.wait_for(coro, timeout=effective_timeout)

        future = asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)
        
        try:
            return future.result(timeout=effective_timeout + 5)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"Async operation timed out after {effective_timeout}s")
        except Exception as e:
            raise e


# Backward-compatible wrapper
_async_bridge = AsyncBridge(timeout=60)


def _run_async(coro, timeout: int = None):
    """Run an async coroutine from synchronous context (compatibility shim)."""
    return _async_bridge.run(coro, timeout=timeout)


# ─── Session Metrics ─────────────────────────────────────────────────────────

@dataclass
class SessionMetrics:
    """Track per-session usage and health."""
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    usage_count: int = 0
    error_count: int = 0
    total_nav_time: float = 0.0
    last_url: str = ""


# ─── Browser Session ─────────────────────────────────────────────────────────

class BrowserSession:
    """
    Manages a single Lightpanda browser instance.
    Provides synchronous methods wrapping the async CDP bridge.
    """

    def __init__(self, session_id: str, bridge: LightpandaBridge,
                 security: BrowserSecurityValidator,
                 async_bridge: AsyncBridge = None):
        self.session_id = session_id
        self.bridge = bridge
        self.security = security
        self._async = async_bridge or _async_bridge
        self.metrics = SessionMetrics()
        self._is_active = True

    @property
    def is_active(self) -> bool:
        return self._is_active and self.bridge.is_connected

    def navigate(self, url: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Navigate to URL with security validation.

        Returns:
            {"url": str, "status": int, "title": str}
        """
        # Validate URL
        is_safe, reason = self.security.validate_url(url)
        if not is_safe:
            raise ValueError(f"Unsafe URL rejected: {reason}")

        start = time.time()
        result = self._async.run(self.bridge.navigate_to_url(url, timeout=timeout))
        nav_time = time.time() - start

        self.metrics.last_used = time.time()
        self.metrics.usage_count += 1
        self.metrics.total_nav_time += nav_time
        self.metrics.last_url = url

        return result

    def get_markdown(self, selector: Optional[str] = None) -> str:
        """
        Get page content as semantic markdown.

        Args:
            selector: Optional CSS selector to scope extraction
        """
        if selector:
            is_safe, reason = self.security.validate_selector(selector)
            if not is_safe:
                raise ValueError(f"Unsafe selector: {reason}")
            # Get inner HTML of selected element, convert to markdown
            html = self._async.run(self.bridge.get_element_text(selector))
            return html

        return self._async.run(self.bridge.get_page_markdown())

    def get_html(self) -> str:
        """Get full page HTML."""
        return self._async.run(self.bridge.get_page_html())

    def extract_links(self) -> List[Dict[str, str]]:
        """Extract all links from page."""
        return self._async.run(self.bridge.extract_links())

    def extract_tables(self) -> List[List[Dict]]:
        """Extract all tables from page."""
        return self._async.run(self.bridge.extract_tables())

    def extract_images(self) -> List[Dict[str, str]]:
        """Extract all images from page."""
        return self._async.run(self.bridge.extract_images())

    def click(self, selector: str) -> bool:
        """Click element matching CSS selector."""
        is_safe, reason = self.security.validate_selector(selector)
        if not is_safe:
            raise ValueError(f"Unsafe selector: {reason}")
        return self._async.run(self.bridge.click_element(selector))

    def type_text(self, selector: str, text: str) -> bool:
        """Type text into input element."""
        is_safe, reason = self.security.validate_selector(selector)
        if not is_safe:
            raise ValueError(f"Unsafe selector: {reason}")
        return self._async.run(self.bridge.type_in_element(selector, text))

    def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for selector to appear in DOM."""
        is_safe, reason = self.security.validate_selector(selector)
        if not is_safe:
            raise ValueError(f"Unsafe selector: {reason}")
        return self._async.run(self.bridge.wait_for_selector(selector, timeout))

    def evaluate_js(self, script: str) -> Any:
        """Execute JavaScript in page context with security validation."""
        is_safe, reason = self.security.validate_javascript(script)
        if not is_safe:
            raise ValueError(f"Unsafe JavaScript: {reason}")
        return self._async.run(self.bridge.evaluate_script(script))

    def take_screenshot(self, path: str) -> Optional[str]:
        """Take screenshot for debugging."""
        return self._async.run(self.bridge.take_screenshot(path))

    def get_page_state(self) -> Dict[str, Any]:
        """Get comprehensive page state."""
        return self._async.run(self.bridge.get_page_metrics())

    def get_cookies(self) -> List[Dict]:
        """Get current page cookies."""
        return self._async.run(self.bridge.get_cookies())

    def set_cookies(self, cookies: List[Dict]) -> None:
        """Restore cookies."""
        self._async.run(self.bridge.set_cookies(cookies))

    def fill_form(self, fields: Dict[str, str]) -> Dict[str, bool]:
        """Fill multiple form fields."""
        for selector in fields:
            is_safe, reason = self.security.validate_selector(selector)
            if not is_safe:
                raise ValueError(f"Unsafe selector '{selector}': {reason}")
        return self._async.run(self.bridge.fill_form(fields))

    def submit_form(self, selector: str) -> bool:
        """Submit a form."""
        is_safe, reason = self.security.validate_selector(selector)
        if not is_safe:
            raise ValueError(f"Unsafe selector: {reason}")
        return self._async.run(self.bridge.submit_form(selector))

    def close(self) -> None:
        """Close this session."""
        self._is_active = False
        try:
            self._async.run(self.bridge.disconnect(), timeout=5)
        except Exception:
            pass


# ─── Session Manager ──────────────────────────────────────────────────────────

class BrowserSessionManager:
    """
    Manages pool of Lightpanda browser sessions.

    Thread-safe session acquisition and release with:
    - Atomic state transitions (no race conditions)
    - Dead session cleanup
    - Error threshold-based session recycling
    - Duplicate-entry prevention on release

    Usage:
        manager = BrowserSessionManager()
        if manager.is_available:
            session = manager.acquire_session()
            try:
                result = session.navigate("https://example.com")
                markdown = session.get_markdown()
            finally:
                manager.release_session(session)
    """

    MAX_ERRORS_BEFORE_DESTROY = 5

    def __init__(self, max_instances: int = 5,
                 browser_path: str = "./lightpanda",
                 port: int = 9222,
                 timeout: int = 30):
        self.max_instances = max_instances
        self.port = port
        self.timeout = timeout
        self.launcher = BrowserLauncher(browser_path)
        self.security = BrowserSecurityValidator()
        self._async = AsyncBridge(timeout=timeout)
        self._sessions: Dict[str, BrowserSession] = {}
        self._available_sessions: List[str] = []
        self._lock = threading.Lock()
        self._browser_started = False
        self._session_counter = 0

    @property
    def is_available(self) -> bool:
        """Check if Lightpanda browser is available on this system."""
        return self.launcher.is_available

    def _ensure_browser_running(self) -> bool:
        """Start browser process if not already running."""
        if self._browser_started and self.launcher.is_running:
            return True

        if not self.is_available:
            return False

        try:
            success = self._async.run(self.launcher.launch(port=self.port))
            self._browser_started = success
            return success
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False

    def acquire_session(self, session_id: str = None) -> Optional[BrowserSession]:
        """
        Acquire a browser session from the pool.

        Thread-safe with atomic state transitions.
        Dead sessions are cleaned up automatically.

        Args:
            session_id: Optional specific session to reuse

        Returns:
            BrowserSession or None if unavailable
        """
        if not self._ensure_browser_running():
            return None

        with self._lock:
            # Try to reuse specified session
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                if session.is_active:
                    # Atomic removal — filter instead of .remove() to avoid crashes
                    self._available_sessions = [
                        s for s in self._available_sessions if s != session_id
                    ]
                    logger.debug(f"Reusing session: {session_id}")
                    return session
                else:
                    # Dead session — clean it up
                    logger.warning(f"Session {session_id} is dead, removing from pool")
                    del self._sessions[session_id]
                    self._available_sessions = [
                        s for s in self._available_sessions if s != session_id
                    ]

            # Try to reuse any available session
            while self._available_sessions:
                sid = self._available_sessions.pop(0)
                if sid in self._sessions and self._sessions[sid].is_active:
                    logger.debug(f"Acquired available session: {sid}")
                    return self._sessions[sid]
                else:
                    # Dead session in available pool — clean up
                    if sid in self._sessions:
                        logger.warning(f"Cleaning dead session from pool: {sid}")
                        del self._sessions[sid]

            # Create new session if under limit
            if len(self._sessions) < self.max_instances:
                return self._create_session()

        logger.warning("No sessions available and at max capacity")
        return None

    def _create_session(self) -> Optional[BrowserSession]:
        """Create a new browser session."""
        self._session_counter += 1
        session_id = f"session_{self._session_counter}"

        try:
            bridge = LightpandaBridge(
                host="127.0.0.1",
                port=self.port,
                default_timeout=self.timeout
            )
            self._async.run(bridge.connect())

            session = BrowserSession(
                session_id, bridge, self.security, self._async
            )
            self._sessions[session_id] = session

            logger.info(f"Created browser session: {session_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None

    def release_session(self, session: BrowserSession) -> None:
        """Return a session to the pool (thread-safe)."""
        with self._lock:
            if session.session_id not in self._sessions:
                return

            if session.metrics.error_count > self.MAX_ERRORS_BEFORE_DESTROY:
                # Too many errors — destroy and recreate
                logger.debug(
                    f"Session {session.session_id} has {session.metrics.error_count} "
                    "errors, destroying"
                )
                session.close()
                del self._sessions[session.session_id]
            else:
                # Prevent duplicate entries in available pool
                if session.session_id not in self._available_sessions:
                    self._available_sessions.append(session.session_id)
                    logger.debug(f"Released session: {session.session_id}")

    def release_with_error(self, session: BrowserSession) -> None:
        """Release session after an error occurred."""
        session.metrics.error_count += 1
        self.release_session(session)

    def cleanup_all(self) -> None:
        """Close all sessions and stop the browser."""
        with self._lock:
            for session in self._sessions.values():
                try:
                    session.close()
                except Exception:
                    pass
            self._sessions.clear()
            self._available_sessions.clear()

        try:
            self._async.run(self.launcher.kill(), timeout=10)
        except Exception:
            pass

        self._browser_started = False
        logger.info("All browser sessions cleaned up")

    def get_status(self) -> Dict[str, Any]:
        """Get current browser subsystem status."""
        with self._lock:
            active = sum(1 for s in self._sessions.values() if s.is_active)
            return {
                "binary_available": self.is_available,
                "binary_path": self.launcher.lightpanda_path,
                "browser_running": self.launcher.is_running,
                "browser_pid": self.launcher.pid,
                "port": self.port,
                "total_sessions": len(self._sessions),
                "active_sessions": active,
                "available_sessions": len(self._available_sessions),
                "max_instances": self.max_instances,
                "security_tokens": self.security.get_token_status(),
            }

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.cleanup_all()
        except Exception:
            pass


# ─── Session Store ────────────────────────────────────────────────────────────

class SessionStore:
    """Persist browser session state (cookies, metadata) across restarts."""

    def __init__(self, storage_path: str = None):
        from lirox.config import DATA_DIR
        self.storage_path = storage_path or os.path.join(DATA_DIR, "browser_sessions.json")

    def save_session_state(self, session: BrowserSession) -> None:
        """Save session cookies and metadata."""
        state = {
            "session_id": session.session_id,
            "last_url": session.metrics.last_url,
            "cookies": session.get_cookies(),
            "saved_at": datetime.now().isoformat(),
        }

        data = self._load_all()
        data[session.session_id] = state
        self._save_all(data)

    def load_session_state(self, session_id: str) -> Optional[Dict]:
        """Load saved session state."""
        data = self._load_all()
        return data.get(session_id)

    def restore_session(self, session: BrowserSession, session_id: str) -> bool:
        """Restore cookies to a session from saved state."""
        state = self.load_session_state(session_id)
        if not state:
            return False

        cookies = state.get("cookies", [])
        if cookies:
            session.set_cookies(cookies)
            return True
        return False

    def _load_all(self) -> Dict:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_all(self, data: Dict) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")
