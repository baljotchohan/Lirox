"""Messaging bridges — reach Lirox from your phone.

Ported from OpenClaw and Hermes Agent's signature capability: a personal agent
that runs on your machine but is reachable through the messaging apps you
already use (Telegram, WhatsApp, Discord, Slack), rather than only through a
terminal REPL.

Only the Telegram bridge is implemented (dependency-free, simplest official
Bot API). Every bridge in this package MUST hard-enforce a sender allowlist —
bridging a shell-capable agent to a public messaging platform without one is
a real vulnerability, not a convenience trade-off.
"""
