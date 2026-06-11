"""Append-only JSONL audit log (spec §6).

Every routed action is recorded: timestamp, channel (voice/telegram),
requester, action, args, tier, outcome. Tier 2/3 entries additionally feed
the back-panel ticker via on_record (spec §6 "loudly logged").
"""

import json
import threading
import time
from pathlib import Path
from typing import Callable


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.on_record: Callable[[dict], None] | None = None

    def record(self, *, channel: str, requester: str, action: str,
               args: dict, tier: int, outcome: str) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "channel": channel,
            "requester": requester,
            "action": action,
            "args": args,
            "tier": tier,
            "outcome": outcome,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        if self.on_record is not None:
            try:
                self.on_record(entry)
            except Exception:
                pass  # the ticker must never break the audit trail
