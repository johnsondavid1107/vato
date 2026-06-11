"""Claude client: tool-use loop routed through the permission layer (§4, §6)."""

import logging
from typing import Callable

import anthropic

from brain.prompts import SYSTEM_PROMPT
from core.tools import ToolRouter

log = logging.getLogger("vato.brain")

FALLBACK_REPLY = (
    "I do beg your pardon — I seem to have lost my train of thought. "
    "Might you ask me again?"
)


class Brain:
    def __init__(self, cfg: dict, router: ToolRouter,
                 on_tool: Callable[[str, dict], None] | None = None):
        claude = cfg.get("claude", {})
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self._model = claude.get("model", "claude-sonnet-4-6")
        self._max_tokens = int(claude.get("max_tokens", 1024))
        self._router = router
        # Fired before each tool runs — the daemon uses it to flip the face
        # to the working back panel and push a ticker line (spec §4 step 4).
        self._on_tool = on_tool
        # Rolling plain-text history; full per-turn tool transcripts are not
        # persisted across turns in M1 (SQLite conversation_log arrives in M3).
        self._history: list[dict] = []
        self._max_history_turns = 12

    def respond(self, user_text: str, requester: str = "voice") -> str:
        self._router.begin_turn()
        turn: list[dict] = self._history + [{"role": "user", "content": user_text}]

        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                tools=self._router.definitions(),
                messages=turn,
            )

            if response.stop_reason == "pause_turn":
                turn.append({"role": "assistant", "content": response.content})
                continue

            if response.stop_reason == "tool_use":
                turn.append({"role": "assistant", "content": response.content})
                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log.info("tool call: %s %s", block.name, block.input)
                        if self._on_tool is not None:
                            try:
                                self._on_tool(block.name, dict(block.input))
                            except Exception:
                                log.exception("on_tool callback failed")
                        output = self._router.execute(block.name, dict(block.input), requester)
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        })
                turn.append({"role": "user", "content": results})
                continue

            break

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            text = FALLBACK_REPLY

        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": text})
        self._history = self._history[-2 * self._max_history_turns:]
        return text
