"""The brain: tool-use loop routed through the permission layer (§4, §6).

Two engines behind one Brain (June 2026 cost pivot — TODO.md "Pick the
brain"). The rest of Vato (router, tiers, Telegram, voice) never knows which
one is running:

- `anthropic` (default): Claude via the Anthropic SDK, with the prompt-cache
  breakpoint on the static persona block.
- `openai_compat`: any OpenAI-compatible endpoint — Gemini, Groq, DeepSeek —
  selected entirely by config.yaml `brain:` (base_url, model, api_key_env).

History is kept provider-neutral (plain user/assistant text), so switching
engines mid-project never corrupts state.
"""

import datetime
import json
import logging
import os
from typing import Callable

import anthropic

from brain.prompts import SYSTEM_PROMPT, TELEGRAM_NOTE
from core.config import ConfigError
from core.tools import ToolRouter
from memory.store import MemoryStore

log = logging.getLogger("vato.brain")

FALLBACK_REPLY = (
    "I do beg your pardon — I seem to have lost my train of thought. "
    "Might you ask me again?"
)


def brain_config(cfg: dict) -> dict:
    """The `brain:` section, falling back to the legacy `claude:` section."""
    return cfg.get("brain") or cfg.get("claude") or {}


class _AnthropicEngine:
    """Claude through the Anthropic SDK (tool use + prompt caching)."""

    def __init__(self, model: str, max_tokens: int):
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self._model = model
        self._max_tokens = max_tokens

    def run(self, system_static: str, system_dynamic: str, messages: list[dict],
            router: ToolRouter, on_tool: Callable[[str, dict], None],
            requester: str) -> str:
        turn = list(messages)
        system = [
            # Static block carries the cache breakpoint — it also caches the
            # tool schemas rendered before it (prefix match). Volatile content
            # (clock, facts) comes after so it can't invalidate the cache.
            {"type": "text", "text": system_static,
             "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": system_dynamic},
        ]
        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=router.definitions(),
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
                        args = dict(block.input)
                        on_tool(block.name, args)
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": router.execute(block.name, args, requester),
                        })
                turn.append({"role": "user", "content": results})
                continue

            break

        return "".join(b.text for b in response.content if b.type == "text").strip()


class _OpenAICompatEngine:
    """Any OpenAI-compatible chat-completions endpoint (Gemini, Groq, …)."""

    def __init__(self, model: str, max_tokens: int, base_url: str, api_key: str):
        from openai import OpenAI  # local import: only this engine needs it
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @staticmethod
    def convert_tools(definitions: list[dict]) -> list[dict]:
        """Anthropic tool schema → OpenAI function-calling schema."""
        return [{
            "type": "function",
            "function": {
                "name": d["name"],
                "description": d["description"],
                "parameters": d["input_schema"],
            },
        } for d in definitions]

    def run(self, system_static: str, system_dynamic: str, messages: list[dict],
            router: ToolRouter, on_tool: Callable[[str, dict], None],
            requester: str) -> str:
        turn = ([{"role": "system",
                  "content": system_static + "\n\n" + system_dynamic}]
                + list(messages))
        tools = self.convert_tools(router.definitions())
        while True:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=turn,
                tools=tools,
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                turn.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name,
                                     "arguments": tc.function.arguments},
                    } for tc in msg.tool_calls],
                })
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    on_tool(tc.function.name, args)
                    turn.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": router.execute(tc.function.name, args, requester),
                    })
                continue

            return (msg.content or "").strip()


def _build_engine(cfg: dict):
    brain = brain_config(cfg)
    provider = brain.get("provider", "anthropic")
    model = brain.get("model", "claude-haiku-4-5")
    max_tokens = int(brain.get("max_tokens", 1024))

    if provider == "anthropic":
        return _AnthropicEngine(model, max_tokens)

    if provider == "openai_compat":
        base_url = (brain.get("base_url") or "").strip()
        if not base_url:
            raise ConfigError(
                "brain.provider is openai_compat but brain.base_url is empty. "
                "See config.yaml.example for the Gemini values.")
        key_env = brain.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.environ.get(key_env, "").strip()
        if not api_key:
            raise ConfigError(
                f"brain.provider is openai_compat but {key_env} is not set "
                "in .env (brain.api_key_env names the variable to use).")
        return _OpenAICompatEngine(model, max_tokens, base_url, api_key)

    raise ConfigError(
        f"Unknown brain.provider {provider!r} — use 'anthropic' or 'openai_compat'.")


class Brain:
    def __init__(self, cfg: dict, router: ToolRouter,
                 on_tool: Callable[[str, dict], None] | None = None,
                 memory: MemoryStore | None = None,
                 channel: str = "voice"):
        self._engine = _build_engine(cfg)
        self._router = router
        # Fired before each tool runs — the daemon uses it to flip the face
        # to the working back panel and push a ticker line (spec §4 step 4).
        self._on_tool = on_tool
        # SQLite-backed conversation_log + per-turn fact injection (spec §10).
        self._memory = memory
        self._channel = channel
        # Rolling plain-text history kept in RAM — provider-neutral.
        self._history: list[dict] = []
        self._max_history_turns = 12
        log.info("Brain engine: %s (%s)", type(self._engine).__name__,
                 brain_config(cfg).get("model", "claude-haiku-4-5"))

    def _system_prompt(self, user_text: str) -> tuple[str, str]:
        """(static, dynamic) halves: byte-stable persona vs per-turn context
        (current date-time, relevant facts). Split so the Anthropic engine can
        cache the static half."""
        static = SYSTEM_PROMPT
        if self._channel == "telegram":
            static += TELEGRAM_NOTE

        now = datetime.datetime.now()
        dynamic = (f"CURRENT DATE & TIME: {now.strftime('%A, %B %d, %Y, %H:%M')}"
                   " (local). Compute ISO date-times for tools from this.")
        if self._memory is not None:
            facts = self._memory.fact_context(user_text)
            if facts:
                dynamic += ("\n\nRELEVANT HOUSEHOLD FACTS (from your memory):\n"
                            + facts)
        return static, dynamic

    def _notify_tool(self, name: str, args: dict) -> None:
        log.info("tool call: %s %s", name, args)
        if self._on_tool is not None:
            try:
                self._on_tool(name, args)
            except Exception:
                log.exception("on_tool callback failed")

    def respond(self, user_text: str, requester: str = "voice") -> str:
        self._router.begin_turn()
        static, dynamic = self._system_prompt(user_text)
        messages = self._history + [{"role": "user", "content": user_text}]

        text = self._engine.run(static, dynamic, messages, self._router,
                                self._notify_tool, requester)
        if not text:
            text = FALLBACK_REPLY

        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": text})
        self._history = self._history[-2 * self._max_history_turns:]
        if self._memory is not None:
            try:
                self._memory.log_conversation(self._channel, "user", user_text)
                self._memory.log_conversation(self._channel, "assistant", text)
            except Exception:
                log.exception("conversation_log write failed")
        return text
