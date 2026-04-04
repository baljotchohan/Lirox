"""Lirox v2.0 Hardening Tests"""
import asyncio, time, os, sys, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAsyncBridge:
    def test_basic(self):
        from lirox.tools.browser_manager import AsyncBridge
        async def f(): return 42
        assert AsyncBridge(timeout=5).run(f()) == 42

    def test_timeout(self):
        from lirox.tools.browser_manager import AsyncBridge
        async def f(): await asyncio.sleep(10)
        with pytest.raises(TimeoutError):
            AsyncBridge(timeout=1).run(f(), timeout=1)

    def test_exception(self):
        from lirox.tools.browser_manager import AsyncBridge
        async def f(): raise ValueError("e")
        with pytest.raises(ValueError):
            AsyncBridge(timeout=5).run(f())

class TestSecurityHardened:
    def setup_method(self):
        from lirox.tools.browser_security import BrowserSecurityValidator
        self.v = BrowserSecurityValidator(rate_limit_per_domain=5, rate_limit_window=60)

    def test_azure(self):
        assert not self.v.validate_url("http://169.254.169.253/x")[0]

    def test_port(self):
        assert not self.v.validate_url("http://example.com:22")[0]

    def test_crlf(self):
        assert not self.v.validate_request_headers({"X": "a\r\nb"})[0]

    def test_null(self):
        assert not self.v.validate_request_headers({"X": "a\x00b"})[0]

    def test_host(self):
        assert not self.v.validate_request_headers({"Host": "evil"})[0]

    def test_safe(self):
        assert self.v.validate_request_headers({"X-C": "ok"})[0]

    def test_proto(self):
        assert not self.v.validate_javascript("o.__proto__.x=1")[0]

class TestCDPError:
    def test_fields(self):
        from lirox.tools.browser_bridge import CDPError
        e = CDPError(-32601, "Not found", method="Page.nav")
        assert e.method == "Page.nav" and "Page.nav" in str(e)

    def test_defaults(self):
        from lirox.tools.browser_bridge import CDPError
        e = CDPError(-1, "err")
        assert e.method == "" and e.params == {}

class TestPooling:
    def test_mounted(self):
        from lirox.tools.browser import BrowserTool
        assert BrowserTool().session.get_adapter("https://x.com") is not None

    def test_size(self):
        from lirox.tools.browser import BrowserTool
        a = BrowserTool().session.get_adapter("https://x.com")
        assert a._pool_connections == 10

class TestTokenBucket:
    def test_consume(self):
        from lirox.tools.browser_security import TokenBucket
        b = TokenBucket(5, 0.0)
        b.consume(1)
        assert b.available_tokens == 4 and b.used_tokens == 1

    def test_exhaust(self):
        from lirox.tools.browser_security import TokenBucket
        b = TokenBucket(3, 0.0)
        for _ in range(3): b.consume(1)
        assert not b.consume(1)

    def test_refill(self):
        from lirox.tools.browser_security import TokenBucket
        b = TokenBucket(5, 10.0)
        for _ in range(5): b.consume(1)
        time.sleep(0.6)
        assert b.available_tokens >= 4

    def test_status(self):
        from lirox.tools.browser_security import BrowserSecurityValidator
        s = BrowserSecurityValidator().get_token_status()
        assert all(k in s for k in ["available", "used", "capacity"])

class TestFallback:
    def test_init(self):
        from lirox.agent.executor import Executor
        e = Executor()
        assert e.browser and hasattr(e, 'headless_available')

class TestDiagnostics:
    def test_refused(self):
        from lirox.tools.network_diagnostics import NetworkDiagnostics
        m = NetworkDiagnostics.diagnose_error(ConnectionError("Connection refused"))
        assert "refused" in m.lower()

class TestRealTimeData:
    def test_stock(self):
        from lirox.tools.real_time_data import RealTimeDataExtractor
        r = RealTimeDataExtractor.extract_stock_data("AAPL $185.43 +2.5%", "AAPL")
        assert len(r["prices"]) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
