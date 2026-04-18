"""Lirox — Autonomous AI Agent OS"""
try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("lirox")
except Exception:
    __version__ = "1.0.0"
