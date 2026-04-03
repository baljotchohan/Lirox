"""
Lirox v0.7 — Lightpanda CDP Bridge

Low-level Chrome DevTools Protocol communication layer for Lightpanda browser.
Communicates over WebSocket to control navigation, DOM, scripting, and extraction.

This module is async-native. Sync wrappers are provided by browser_manager.py.
"""

import json
import asyncio
import logging
import subprocess
import os
import signal
import time
from typing import Optional, List, Dict, Any

logger = logging.getLogger("lirox.browser.bridge")

# Try importing websockets — graceful fallback if not installed
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("websockets not installed — headless browser unavailable. pip install websockets")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class CDPError(Exception):
    """Error from Chrome DevTools Protocol — includes full context for debugging."""
    def __init__(self, code: int, message: str, method: str = "",
                 params: dict = None, response: dict = None):
        self.code = code
        self.method = method
        self.params = params or {}
        self.response = response or {}
        self.message = message
        super().__init__(f"CDP Error {code} [{method}]: {message}")

    def __repr__(self):
        return (f"CDPError(code={self.code}, method='{self.method}', "
                f"message='{self.message}')")


class LightpandaBridge:
    """
    Communicates with Lightpanda browser via Chrome DevTools Protocol (CDP).

    Usage:
        bridge = LightpandaBridge(host="localhost", port=9222)
        await bridge.connect()
        await bridge.navigate_to_url("https://example.com")
        html = await bridge.get_page_html()
        await bridge.disconnect()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9222,
                 default_timeout: int = 30):
        self.host = host
        self.port = port
        self.default_timeout = default_timeout
        self._ws = None
        self._msg_id = 0
        self._ws_url = None
        self._connected = False

    # ─── Connection Lifecycle ─────────────────────────────────────────────────

    async def connect(self, retries: int = 3, retry_delay: float = 1.0) -> None:
        """Connect to Lightpanda via CDP WebSocket with retry logic.

        Args:
            retries: Number of connection attempts (default 3)
            retry_delay: Initial delay between attempts in seconds (doubles each retry)
        """
        if not HAS_WEBSOCKETS:
            raise RuntimeError("websockets library not installed")

        last_error = None

        for attempt in range(retries):
            try:
                if attempt > 0:
                    delay = retry_delay * (2 ** (attempt - 1))
                    logger.info(f"Retrying CDP connection (attempt {attempt + 1}/{retries}) after {delay:.1f}s")
                    await asyncio.sleep(delay)

                # Get WebSocket debugger URL from CDP /json endpoint
                ws_url = await self._get_debugger_url()
                if not ws_url:
                    raise ConnectionError(
                        f"Cannot connect to Lightpanda at {self.host}:{self.port}. "
                        "Is the browser running?"
                    )

                self._ws_url = ws_url
                self._ws = await asyncio.wait_for(
                    websockets.connect(
                        ws_url,
                        max_size=10 * 1024 * 1024,
                        ping_interval=20,    # Keep-alive ping every 20s
                        ping_timeout=10,     # Fail if no pong in 10s
                    ),
                    timeout=10
                )
                self._connected = True

                # Enable required CDP domains — each wrapped individually
                for domain in ["Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"]:
                    try:
                        await self._send_command(domain, timeout=5)
                    except Exception as e:
                        logger.warning(f"Failed to enable {domain}: {e}")

                logger.info(f"Connected to Lightpanda CDP at {ws_url} (attempt {attempt + 1})")
                return  # Success

            except Exception as e:
                last_error = e
                self._connected = False
                self._ws = None
                logger.warning(f"CDP connection attempt {attempt + 1} failed: {e}")

        raise ConnectionError(f"WebSocket connection failed after {retries} attempts: {last_error}")

    async def disconnect(self) -> None:
        """Cleanly disconnect from CDP."""
        if self._ws and self._connected:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._connected = False
            self._ws = None
            logger.info("Disconnected from Lightpanda CDP")

    async def _get_debugger_url(self) -> Optional[str]:
        """Fetch the WebSocket debugger URL from Lightpanda's /json endpoint."""
        if not HAS_AIOHTTP:
            # Fallback: construct URL directly (common pattern)
            return f"ws://{self.host}:{self.port}"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{self.host}:{self.port}/json"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and data:
                            return data[0].get("webSocketDebuggerUrl")
                        return f"ws://{self.host}:{self.port}"
                    else:
                        # Some Lightpanda versions serve WS directly
                        return f"ws://{self.host}:{self.port}"
        except Exception:
            # Direct WebSocket connection attempt
            return f"ws://{self.host}:{self.port}"

    # ─── CDP Communication ────────────────────────────────────────────────────

    async def _send_command(self, method: str, params: Dict = None,
                            timeout: int = None) -> Dict:
        """Send a CDP command and wait for response."""
        if not self._connected or not self._ws:
            raise ConnectionError("Not connected to browser")

        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method}
        if params:
            msg["params"] = params

        try:
            await self._ws.send(json.dumps(msg))

            effective_timeout = timeout or self.default_timeout
            deadline = time.time() + effective_timeout

            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        self._ws.recv(),
                        timeout=min(2.0, deadline - time.time())
                    )
                    response = json.loads(raw)

                    # Match response to our request ID
                    if response.get("id") == self._msg_id:
                        if "error" in response:
                            err = response["error"]
                            raise CDPError(
                                code=err.get("code", -1),
                                message=err.get("message", "Unknown CDP error"),
                                method=method,
                                params=params,
                                response=response,
                            )
                        return response.get("result", {})

                    # Ignore events and other message IDs
                except asyncio.TimeoutError:
                    continue

            raise TimeoutError(f"CDP command '{method}' timed out after {effective_timeout}s")

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.ConnectionClosedError) if HAS_WEBSOCKETS else Exception:
            self._connected = False
            raise ConnectionError("WebSocket connection lost")

    # ─── Navigation & Page State ──────────────────────────────────────────────

    async def navigate_to_url(self, url: str,
                               wait_until: str = "load",
                               timeout: int = None) -> Dict:
        """
        Navigate to URL and wait for page load.

        Args:
            url: Target URL
            wait_until: "load" | "domcontentloaded" | "networkidle"
            timeout: Navigation timeout in seconds

        Returns:
            {"url": str, "status": int, "title": str}
        """
        result = await self._send_command("Page.navigate", {"url": url},
                                           timeout=timeout or 30)

        # Wait for load event
        try:
            effective_timeout = timeout or 30
            deadline = time.time() + effective_timeout

            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        self._ws.recv(),
                        timeout=min(2.0, deadline - time.time())
                    )
                    event = json.loads(raw)
                    event_method = event.get("method", "")

                    if wait_until == "load" and event_method == "Page.loadEventFired":
                        break
                    elif wait_until == "domcontentloaded" and event_method == "Page.domContentEventFired":
                        break
                except asyncio.TimeoutError:
                    continue

        except Exception:
            pass  # Best effort wait

        # Get final page info
        try:
            tree = await self._send_command("Page.getFrameTree", timeout=5)
            frame = tree.get("frameTree", {}).get("frame", {})
            return {
                "url": frame.get("url", url),
                "status": 200,
                "title": frame.get("name", ""),
                "frame_id": result.get("frameId", ""),
            }
        except Exception:
            return {"url": url, "status": 200, "title": "", "frame_id": ""}

    async def get_page_html(self) -> str:
        """Get the full HTML of the current page."""
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": "document.documentElement.outerHTML",
             "returnByValue": True},
            timeout=10
        )
        return result.get("result", {}).get("value", "")

    async def get_page_title(self) -> str:
        """Get page title."""
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": "document.title", "returnByValue": True},
            timeout=5
        )
        return result.get("result", {}).get("value", "")

    async def get_page_url(self) -> str:
        """Get current page URL."""
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": "window.location.href", "returnByValue": True},
            timeout=5
        )
        return result.get("result", {}).get("value", "")

    async def get_page_markdown(self) -> str:
        """
        Convert current page to semantic markdown.
        Uses in-page JS to extract structured text with headings.
        """
        script = """
        (function() {
            const body = document.body;
            if (!body) return '';
            
            // Remove noise elements
            const noise = ['script', 'style', 'nav', 'footer', 'header', 
                           'aside', 'noscript', 'svg', 'iframe'];
            const clone = body.cloneNode(true);
            noise.forEach(tag => {
                clone.querySelectorAll(tag).forEach(el => el.remove());
            });
            
            function nodeToMd(node, depth) {
                if (node.nodeType === 3) return node.textContent.trim();
                if (node.nodeType !== 1) return '';
                
                const tag = node.tagName.toLowerCase();
                let children = Array.from(node.childNodes)
                    .map(c => nodeToMd(c, depth + 1))
                    .filter(t => t.length > 0);
                let text = children.join(' ');
                
                if (['h1','h2','h3','h4','h5','h6'].includes(tag)) {
                    const level = parseInt(tag[1]);
                    return '\\n' + '#'.repeat(level) + ' ' + text + '\\n';
                }
                if (tag === 'p') return '\\n' + text + '\\n';
                if (tag === 'li') return '- ' + text;
                if (tag === 'a') {
                    const href = node.getAttribute('href') || '';
                    return '[' + text + '](' + href + ')';
                }
                if (tag === 'strong' || tag === 'b') return '**' + text + '**';
                if (tag === 'em' || tag === 'i') return '*' + text + '*';
                if (tag === 'code') return '`' + text + '`';
                if (tag === 'pre') return '\\n```\\n' + text + '\\n```\\n';
                if (tag === 'br') return '\\n';
                if (tag === 'img') {
                    const alt = node.getAttribute('alt') || '';
                    const src = node.getAttribute('src') || '';
                    return '![' + alt + '](' + src + ')';
                }
                if (tag === 'table') {
                    const rows = Array.from(node.querySelectorAll('tr'));
                    if (rows.length === 0) return '';
                    let md = '\\n';
                    rows.forEach((row, i) => {
                        const cells = Array.from(row.querySelectorAll('th, td'))
                            .map(c => c.textContent.trim());
                        md += '| ' + cells.join(' | ') + ' |\\n';
                        if (i === 0) {
                            md += '| ' + cells.map(() => '---').join(' | ') + ' |\\n';
                        }
                    });
                    return md;
                }
                return text;
            }
            
            let md = nodeToMd(clone, 0);
            // Clean up excessive whitespace
            md = md.replace(/\\n{3,}/g, '\\n\\n').trim();
            return md;
        })();
        """
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": script, "returnByValue": True},
            timeout=10
        )
        return result.get("result", {}).get("value", "")

    # ─── DOM Interactions ─────────────────────────────────────────────────────

    async def query_selector(self, selector: str) -> Optional[int]:
        """
        Find first element matching CSS selector.
        Returns node ID or None.
        """
        try:
            doc = await self._send_command("DOM.getDocument", timeout=5)
            root_id = doc.get("root", {}).get("nodeId", 0)

            result = await self._send_command(
                "DOM.querySelector",
                {"nodeId": root_id, "selector": selector},
                timeout=5
            )
            node_id = result.get("nodeId", 0)
            return node_id if node_id > 0 else None
        except Exception:
            return None

    async def query_selector_all(self, selector: str) -> List[int]:
        """Find all elements matching CSS selector. Returns list of node IDs."""
        try:
            doc = await self._send_command("DOM.getDocument", timeout=5)
            root_id = doc.get("root", {}).get("nodeId", 0)

            result = await self._send_command(
                "DOM.querySelectorAll",
                {"nodeId": root_id, "selector": selector},
                timeout=5
            )
            return [nid for nid in result.get("nodeIds", []) if nid > 0]
        except Exception:
            return []

    async def get_element_text(self, selector: str) -> str:
        """Get text content of element matching selector."""
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": f"document.querySelector('{selector}')?.textContent?.trim() || ''",
                "returnByValue": True
            },
            timeout=5
        )
        return result.get("result", {}).get("value", "")

    async def get_element_attribute(self, selector: str, attr: str) -> str:
        """Get attribute value of element matching selector."""
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": f"document.querySelector('{selector}')?.getAttribute('{attr}') || ''",
                "returnByValue": True
            },
            timeout=5
        )
        return result.get("result", {}).get("value", "")

    async def click_element(self, selector: str) -> bool:
        """Click element matching CSS selector."""
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": f"""
                    (function() {{
                        const el = document.querySelector('{selector}');
                        if (!el) return false;
                        el.scrollIntoView({{behavior: 'instant', block: 'center'}});
                        el.click();
                        return true;
                    }})()
                """,
                "returnByValue": True
            },
            timeout=5
        )
        return result.get("result", {}).get("value", False)

    async def type_in_element(self, selector: str, text: str, delay: int = 0) -> bool:
        """Type text into an input element."""
        safe_text = text.replace("'", "\\'").replace("\\", "\\\\")
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": f"""
                    (function() {{
                        const el = document.querySelector('{selector}');
                        if (!el) return false;
                        el.focus();
                        el.value = '{safe_text}';
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }})()
                """,
                "returnByValue": True
            },
            timeout=5
        )
        return result.get("result", {}).get("value", False)

    async def focus_element(self, selector: str) -> bool:
        """Focus an element."""
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": f"(function() {{ const e = document.querySelector('{selector}'); if(e) {{ e.focus(); return true; }} return false; }})()",
                "returnByValue": True
            },
            timeout=5
        )
        return result.get("result", {}).get("value", False)

    # ─── Wait Operations ──────────────────────────────────────────────────────

    async def wait_for_selector(self, selector: str,
                                 timeout: int = 10000) -> bool:
        """
        Wait for CSS selector to appear in DOM.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            True if found, False if timeout
        """
        start = time.time()
        deadline = start + (timeout / 1000)

        while time.time() < deadline:
            node_id = await self.query_selector(selector)
            if node_id:
                return True
            await asyncio.sleep(0.25)

        return False

    async def wait_for_navigation(self, timeout: int = 30000) -> None:
        """Wait for page navigation to complete."""
        deadline = time.time() + (timeout / 1000)

        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=min(1.0, deadline - time.time())
                )
                event = json.loads(raw)
                if event.get("method") == "Page.loadEventFired":
                    return
            except asyncio.TimeoutError:
                continue
            except Exception:
                return

    # ─── JavaScript Evaluation ────────────────────────────────────────────────

    async def evaluate_script(self, script: str, timeout: int = None) -> Any:
        """
        Evaluate JavaScript in page context.

        Args:
            script: JavaScript code to execute
            timeout: Evaluation timeout in seconds

        Returns:
            The returned value from the script
        """
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": script,
                "returnByValue": True,
                "awaitPromise": True
            },
            timeout=timeout or 10
        )

        val = result.get("result", {})
        if val.get("type") == "undefined":
            return None
        return val.get("value")

    # ─── Form Handling ────────────────────────────────────────────────────────

    async def submit_form(self, selector: str) -> bool:
        """Submit a form element."""
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": f"""
                    (function() {{
                        const form = document.querySelector('{selector}');
                        if (!form) return false;
                        form.submit();
                        return true;
                    }})()
                """,
                "returnByValue": True
            },
            timeout=5
        )
        return result.get("result", {}).get("value", False)

    async def fill_form(self, fields: Dict[str, str]) -> Dict[str, bool]:
        """
        Fill multiple form fields at once.

        Args:
            fields: {"selector": "value"} mapping

        Returns:
            {"selector": success_bool} mapping
        """
        results = {}
        for selector, value in fields.items():
            results[selector] = await self.type_in_element(selector, value)
        return results

    # ─── Data Extraction ──────────────────────────────────────────────────────

    async def extract_tables(self) -> List[List[Dict]]:
        """Extract all tables from page as list of row dicts."""
        script = """
        (function() {
            const tables = document.querySelectorAll('table');
            const result = [];
            tables.forEach(table => {
                const rows = [];
                const headers = [];
                const headerCells = table.querySelectorAll('thead th, tr:first-child th');
                headerCells.forEach(th => headers.push(th.textContent.trim()));
                
                const bodyRows = table.querySelectorAll('tbody tr, tr');
                bodyRows.forEach((tr, i) => {
                    if (i === 0 && headers.length > 0 && tr.querySelector('th')) return;
                    const cells = tr.querySelectorAll('td, th');
                    const row = {};
                    cells.forEach((cell, j) => {
                        const key = headers[j] || 'col_' + j;
                        row[key] = cell.textContent.trim();
                    });
                    if (Object.keys(row).length > 0) rows.push(row);
                });
                if (rows.length > 0) result.push(rows);
            });
            return JSON.stringify(result);
        })();
        """
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": script, "returnByValue": True},
            timeout=10
        )
        raw = result.get("result", {}).get("value", "[]")
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return []

    async def extract_links(self) -> List[Dict[str, str]]:
        """Extract all links from page."""
        script = """
        (function() {
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                links.push({
                    url: a.href,
                    text: a.textContent.trim(),
                    title: a.getAttribute('title') || ''
                });
            });
            return JSON.stringify(links);
        })();
        """
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": script, "returnByValue": True},
            timeout=10
        )
        raw = result.get("result", {}).get("value", "[]")
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return []

    async def extract_images(self) -> List[Dict[str, str]]:
        """Extract all images from page."""
        script = """
        (function() {
            const images = [];
            document.querySelectorAll('img').forEach(img => {
                images.push({
                    src: img.src || '',
                    alt: img.alt || '',
                    width: img.naturalWidth || 0,
                    height: img.naturalHeight || 0
                });
            });
            return JSON.stringify(images);
        })();
        """
        result = await self._send_command(
            "Runtime.evaluate",
            {"expression": script, "returnByValue": True},
            timeout=10
        )
        raw = result.get("result", {}).get("value", "[]")
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return []

    # ─── Cookies & Session ────────────────────────────────────────────────────

    async def get_cookies(self) -> List[Dict]:
        """Get all cookies for current page."""
        try:
            result = await self._send_command("Network.getCookies", timeout=5)
            return result.get("cookies", [])
        except Exception:
            return []

    async def set_cookies(self, cookies: List[Dict]) -> None:
        """Set cookies."""
        try:
            await self._send_command(
                "Network.setCookies",
                {"cookies": cookies},
                timeout=5
            )
        except Exception:
            pass

    # ─── Screenshots ──────────────────────────────────────────────────────────

    async def take_screenshot(self, path: str = None,
                               full_page: bool = False) -> Optional[str]:
        """
        Take a screenshot.

        Args:
            path: Save path (if None, returns base64)
            full_page: Capture full page or just viewport

        Returns:
            Base64 data if no path, else the path
        """
        try:
            params = {"format": "png"}
            if full_page:
                params["captureBeyondViewport"] = True

            result = await self._send_command(
                "Page.captureScreenshot",
                params,
                timeout=10
            )
            data = result.get("data", "")

            if path and data:
                import base64
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
                return path

            return data
        except Exception:
            return None

    # ─── Page Metrics ─────────────────────────────────────────────────────────

    async def get_page_metrics(self) -> Dict[str, Any]:
        """Get page performance metrics."""
        try:
            result = await self.evaluate_script("""
                JSON.stringify({
                    title: document.title,
                    url: window.location.href,
                    readyState: document.readyState,
                    elementCount: document.querySelectorAll('*').length,
                    linkCount: document.querySelectorAll('a').length,
                    imageCount: document.querySelectorAll('img').length,
                    formCount: document.querySelectorAll('form').length,
                    tableCount: document.querySelectorAll('table').length
                })
            """, timeout=5)
            return json.loads(result) if isinstance(result, str) else {}
        except Exception:
            return {}

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None


class BrowserLauncher:
    """Manages the Lightpanda browser process lifecycle."""

    def __init__(self, lightpanda_path: str = "./lightpanda"):
        self.lightpanda_path = lightpanda_path
        self._process: Optional[subprocess.Popen] = None

    @property
    def is_available(self) -> bool:
        """Check if Lightpanda binary exists and is executable."""
        return os.path.isfile(self.lightpanda_path) and os.access(
            self.lightpanda_path, os.X_OK
        )

    async def launch(self, port: int = 9222, headless: bool = True) -> bool:
        """
        Launch Lightpanda browser process.

        Returns:
            True if successfully launched and ready
        """
        if not self.is_available:
            logger.warning(f"Lightpanda binary not found at: {self.lightpanda_path}")
            return False

        if self._process and self._process.poll() is None:
            logger.info("Lightpanda already running")
            return True

        try:
            cmd = [self.lightpanda_path, "--host", "127.0.0.1", "--port", str(port)]

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )

            # Wait for browser to be ready
            ready = await self._wait_for_ready(port, timeout=30)
            if ready:
                logger.info(f"Lightpanda launched on port {port} (PID: {self._process.pid})")
            else:
                logger.error("Lightpanda failed to become ready")
                await self.kill()

            return ready

        except Exception as e:
            logger.error(f"Failed to launch Lightpanda: {e}")
            return False

    async def _wait_for_ready(self, port: int, timeout: int = 30) -> bool:
        """Poll the CDP endpoint until ready."""
        import socket

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()
                if result == 0:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)

        return False

    async def kill(self) -> None:
        """Kill the Lightpanda process."""
        if self._process:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                else:
                    self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            finally:
                self._process = None
                logger.info("Lightpanda process terminated")

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None
