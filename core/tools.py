"""Tool registry and router with the tier model from spec §6.

Every tool is registered with a fixed tier; the LLM cannot change it.
Tiers: 0 read-only · 1 household writes · 2 workspace system actions ·
3 Telegram-confirmed.

Tier-3 enforcement (M4): before a Tier-3 action runs, the router blocks on
`confirmer` — a callable the Telegram channel provides that posts an inline
Confirm/Refuse button to the family group chat and waits for a tap from an
allowlisted member. No confirmer configured → Tier-3 actions are refused.

Prompt-injection firewall (§6, mechanical): tools that return fetched
content set `returns_untrusted`; once such content has entered the current
turn, every Tier 1-3 action in the same turn is escalated to Tier 3 —
regardless of what the LLM asks for. Read-only actions are unaffected.
"""

import json
from dataclasses import dataclass
from typing import Callable

from core.audit import AuditLog

# confirmer(plain_text_description) -> (approved, detail) — detail is a short
# human phrase like "approved by David" / "refused by Mum" / "timed out".
Confirmer = Callable[[str], tuple[bool, str]]


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
    def __init__(self, audit: AuditLog, channel: str = "voice",
                 confirmer: Confirmer | None = None):
        self._tools: dict[str, Tool] = {}
        self._audit = audit
        self._channel = channel
        self.confirmer = confirmer
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

        tier = tool.tier
        escalated = self.untrusted_content_seen and 1 <= tier < 3
        if escalated:
            tier = 3  # §6 firewall: untrusted content seen → writes need a human

        confirm_note = ""
        if tier >= 3:
            approved, detail = self._confirm(name, args, requester, escalated)
            if not approved:
                self._audit.record(
                    channel=self._channel, requester=requester, action=name,
                    args=args, tier=tier,
                    outcome=f"not executed: {detail}"
                            + (" [escalated: untrusted content in turn]"
                               if escalated else ""),
                )
                return (f"Action NOT executed — {detail}. "
                        + ("This action was escalated because fetched content "
                           "entered this conversation turn; only a family "
                           "member's Telegram confirmation can authorise it. "
                           if escalated else "")
                        + "Explain this to the family member, in character.")
            confirm_note = f" ({detail})"

        try:
            result = tool.fn(**args)
            outcome = "ok" + confirm_note
        except Exception as exc:  # tool errors go back to the model, not up the stack
            result = f"Tool error: {exc}"
            outcome = f"error: {exc}{confirm_note}"
        if tool.returns_untrusted:
            self.untrusted_content_seen = True
        self._audit.record(
            channel=self._channel,
            requester=requester,
            action=name,
            args=args,
            tier=tier,
            outcome=outcome + (" [escalated: untrusted content in turn]"
                               if escalated else ""),
        )
        return result

    def _confirm(self, name: str, args: dict, requester: str,
                 escalated: bool) -> tuple[bool, str]:
        """Block on a Telegram inline-button confirmation (spec §6 Tier 3).

        The message shows the exact action and arguments in plain language —
        the family approves what will actually run, not a paraphrase."""
        if self.confirmer is None:
            return False, ("no Telegram confirmation channel is set up, and "
                           "this action requires a family member's approval")
        text = (
            f"⚠️ Confirmation required\n"
            f"Requested via {self._channel} by {requester}:\n"
            f"{self.describe_call(name, args)}\n\n"
            f"Exact action: {name} {json.dumps(args, ensure_ascii=False)}"
        )
        if escalated:
            text += ("\n\nEscalated automatically: content fetched from "
                     "outside entered this turn (§6 firewall).")
        try:
            return self.confirmer(text)
        except Exception as exc:
            return False, f"the confirmation request failed ({exc})"
