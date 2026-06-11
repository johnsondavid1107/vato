"""iMessage sending via AppleScript (spec §8, §11) — Tier 3, always.

Sending anything outbound on a family member's behalf requires a Telegram
confirmation tap before this code ever runs; the ToolRouter enforces that.
First use prompts macOS for automation permission (Terminal → Messages).
"""

from system.control import MacSystemControl

SEND_IMESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "recipient": {
            "type": "string",
            "description": ("Phone number (with country code, e.g. +15551234567) "
                            "or the iMessage email address of the recipient."),
        },
        "message": {"type": "string", "description": "The message text to send."},
    },
    "required": ["recipient", "message"],
}


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


class IMessageService:
    def __init__(self, system: MacSystemControl):
        self._system = system

    def send_imessage(self, recipient: str, message: str) -> str:
        script = (
            'tell application "Messages"\n'
            '  set targetService to 1st account whose service type = iMessage\n'
            f'  set targetBuddy to participant "{_esc(recipient)}" of targetService\n'
            f'  send "{_esc(message)}" to targetBuddy\n'
            'end tell'
        )
        self._system.run_applescript(script)
        return f"iMessage sent to {recipient}."
