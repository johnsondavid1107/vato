"""Tool registry and router with the tier model from spec §6.

Every tool is registered with a fixed tier; the LLM cannot change it.
Tiers: 0 read-only · 1 household writes · 2 workspace system actions ·
3 Telegram-confirmed. M1 ships Tier-0 tools only; the Tier-3 confirmation
flow arrives with Telegram in M4.

Prompt-injection firewall plumbing: tools that return fetched/untrusted
content set `returns_untrusted`, and the router tracks whether untrusted
content has entered the current turn. Mechanical escalation of Tier 1-3
actions to Tier 3 in that case is wired in at M4/M5 when confirmations exist.
"""

from dataclasses import dataclass
from typing import Callable

from core.audit import AuditLog


@dataclass
class Tool:
    name: str
    tier: int
    description: str
    input_schema: dict
    fn: Callable[..., str]
    returns_untrusted: bool = False
    # Plain-language back-panel ticker line for a call (spec §9), e.g.
    # lambda args: f"Checking the weather for {args.get('location') or 'home'}…"
    ticker_line: Callable[[dict], str] | None = None


class ToolRouter:
    def __init__(self, audit: AuditLog, channel: str = "voice"):
        self._tools: dict[str, Tool] = {}
        self._audit = audit
        self._channel = channel
        self.untrusted_content_seen = False

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def definitions(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def begin_turn(self) -> None:
        self.untrusted_content_seen = False

    def describe_call(self, name: str, args: dict) -> str:
        """Plain-language line for the back-panel ticker."""
        tool = self._tools.get(name)
        if tool is not None and tool.ticker_line is not None:
            try:
                return tool.ticker_line(args)
            except Exception:
                pass
        return f"Running {name}…"

    def execute(self, name: str, args: dict, requester: str = "voice") -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            result = tool.fn(**args)
            outcome = "ok"
        except Exception as exc:  # tool errors go back to the model, not up the stack
            result = f"Tool error: {exc}"
            outcome = f"error: {exc}"
        if tool.returns_untrusted:
            self.untrusted_content_seen = True
        self._audit.record(
            channel=self._channel,
            requester=requester,
            action=name,
            args=args,
            tier=tool.tier,
            outcome=outcome,
        )
        return result
