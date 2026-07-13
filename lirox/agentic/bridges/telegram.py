"""Telegram bridge — reach Lirox from your phone via a Telegram bot.

Dependency-free: talks to the official Telegram Bot API over HTTPS with
urllib (long-polling ``getUpdates``), matching the rest of lirox.agentic's
zero-extra-dependency network code.

SECURITY: a Telegram bot's chat is reachable by anyone who finds it (or is
added to a group with it). Because Lirox can execute shell commands and edit
files, this bridge REFUSES to start without an explicit chat-id allowlist —
there is no "trust everyone" mode. Set it up:

    1. Message @BotFather on Telegram, run /newbot, copy the token.
    2. Message your new bot anything, then visit
       https://api.telegram.org/bot<TOKEN>/getUpdates to read your chat id
       out of the JSON response (or message @userinfobot for your user id).
    3. export TELEGRAM_BOT_TOKEN=...
       export TELEGRAM_ALLOWED_CHAT_IDS=123456789,987654321
    4. lirox bridge telegram
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set

_logger = logging.getLogger("lirox.agentic.bridges.telegram")

_API = "https://api.telegram.org/bot{token}/{method}"
_MAX_MSG = 4000  # stay under Telegram's 4096-char limit with margin
_LONG_POLL_TIMEOUT = 30


class TelegramBridge:
    """Long-polls Telegram for messages and routes each into Lirox's
    MasterOrchestrator, replying with the final answer. One orchestrator
    instance is shared across chats (personal-assistant model: one owner,
    reachable from anywhere) — this is not a multi-tenant bot."""

    def __init__(
        self,
        token: str,
        allowed_chat_ids: Set[int],
        *,
        agent_mode: str = "default",
        request_timeout: float = _LONG_POLL_TIMEOUT + 10,
    ) -> None:
        if not token:
            raise ValueError("Telegram bot token is required")
        if not allowed_chat_ids:
            raise ValueError(
                "allowed_chat_ids must be non-empty — refusing to bridge a "
                "shell-capable agent to Telegram with no sender allowlist"
            )
        self.token = token
        self.allowed_chat_ids = set(allowed_chat_ids)
        self.agent_mode = agent_mode
        self.request_timeout = request_timeout
        self._offset = 0
        self._orch = None  # lazy — avoid importing the whole stack at construction

    # ── Telegram HTTP plumbing ────────────────────────────────────────────
    def _call(self, method: str, params: Optional[Dict] = None) -> Dict:
        url = _API.format(token=self.token, method=method)
        data = json.dumps(params or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API error on {method}: {body}")
        return body.get("result")

    def get_updates(self) -> List[Dict]:
        return self._call("getUpdates", {
            "offset": self._offset,
            "timeout": _LONG_POLL_TIMEOUT,
            "allowed_updates": ["message"],
        })

    def send_message(self, chat_id: int, text: str) -> None:
        for i in range(0, len(text), _MAX_MSG):
            chunk = text[i:i + _MAX_MSG] or "(empty response)"
            try:
                self._call("sendMessage", {"chat_id": chat_id, "text": chunk})
            except Exception as exc:  # noqa: BLE001
                _logger.warning("Failed to send Telegram message to %s: %s", chat_id, exc)

    # ── orchestrator plumbing ─────────────────────────────────────────────
    def _get_orchestrator(self):
        if self._orch is None:
            from lirox.orchestrator.master import MasterOrchestrator
            from lirox.agents.profile import UserProfile
            profile = UserProfile()
            self._orch = MasterOrchestrator(profile_data=profile.data)
        return self._orch

    def _run_query(self, text: str) -> str:
        from lirox.modes.agent_mode import set_agent_mode
        set_agent_mode(self.agent_mode)
        orch = self._get_orchestrator()
        final = ""
        for event in orch.run(text):
            if event.type == "done":
                final = event.message
        return final or "(no response)"

    # ── message handling ──────────────────────────────────────────────────
    def _handle_message(self, message: Dict) -> None:
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        if chat_id is None or not text:
            return
        if chat_id not in self.allowed_chat_ids:
            _logger.warning("Ignored message from non-allowlisted chat_id=%s", chat_id)
            return  # silent — don't confirm the bot's existence to strangers

        _logger.info("Telegram <- chat=%s: %s", chat_id, text[:200])
        try:
            answer = self._run_query(text)
        except Exception as exc:  # noqa: BLE001
            answer = f"Error: {exc}"
            _logger.exception("Error handling Telegram message")
        self.send_message(chat_id, answer)

    # ── main loop ─────────────────────────────────────────────────────────
    def poll_forever(self) -> None:
        _logger.info("Telegram bridge started — allowlisted chat_ids: %s", self.allowed_chat_ids)
        while True:
            try:
                updates = self.get_updates()
            except (urllib.error.URLError, TimeoutError) as exc:
                _logger.warning("Telegram getUpdates failed, retrying: %s", exc)
                time.sleep(5)
                continue
            except Exception as exc:  # noqa: BLE001
                _logger.error("Unexpected Telegram polling error: %s", exc)
                time.sleep(5)
                continue

            for update in updates:
                self._offset = max(self._offset, update.get("update_id", 0) + 1)
                message = update.get("message")
                if message:
                    self._handle_message(message)


def run_telegram_bridge() -> int:
    """CLI entry point: `lirox bridge telegram`."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    raw_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    allowed = {int(x) for x in raw_ids.split(",") if x.strip().lstrip("-").isdigit()}

    if not token:
        print("[Lirox] TELEGRAM_BOT_TOKEN is not set. See lirox/agentic/bridges/telegram.py "
              "for setup steps (message @BotFather to create a bot).")
        return 1
    if not allowed:
        print("[Lirox] TELEGRAM_ALLOWED_CHAT_IDS is not set or empty. Refusing to start: "
              "bridging Lirox to Telegram without a sender allowlist would let ANYONE who "
              "finds your bot run shell commands on this machine. Set it to your own chat "
              "id(s), comma-separated.")
        return 1

    bridge = TelegramBridge(token=token, allowed_chat_ids=allowed,
                            agent_mode=os.getenv("LIROX_BRIDGE_AGENT_MODE", "default"))
    try:
        bridge.poll_forever()
    except KeyboardInterrupt:
        print("\n[Lirox] Telegram bridge stopped.")
    return 0
