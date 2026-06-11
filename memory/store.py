"""SQLite memory layer (spec §10) — single file in Vato's workspace.

Tables: facts, conversation_log, preferences, lists, game_state.
Retrieval is simple keyword/recency selection (spec: fine for v1); relevant
facts are injected per turn by the brain. Tool functions for the router live
here too, following the weather-module pattern (service + schemas).
"""

import re
import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id      INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    key     TEXT NOT NULL,
    value   TEXT NOT NULL,
    source  TEXT NOT NULL DEFAULT 'voice',
    ts      TEXT NOT NULL,
    UNIQUE (subject, key) ON CONFLICT REPLACE
);
CREATE TABLE IF NOT EXISTS conversation_log (
    id      INTEGER PRIMARY KEY,
    ts      TEXT NOT NULL,
    channel TEXT NOT NULL,
    role    TEXT NOT NULL,
    text    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    ts    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lists (
    id        INTEGER PRIMARY KEY,
    list_name TEXT NOT NULL,
    item      TEXT NOT NULL,
    done      INTEGER NOT NULL DEFAULT 0,
    ts        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS game_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    ts    TEXT NOT NULL
);
"""

_STOPWORDS = {
    "the", "and", "for", "what", "whats", "who", "whos", "does", "did",
    "have", "has", "had", "was", "were", "are", "you", "your", "vato",
    "please", "could", "would", "about", "tell", "know", "remember",
    "with", "that", "this", "they", "them", "her", "his", "our", "she",
    "him", "can", "get", "how", "when", "where", "like", "want",
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # tools run on the voice + scheduler threads
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.commit()

    def _run(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, params)
            rows = cur.fetchall()
            self._db.commit()
        return rows

    # ── facts ────────────────────────────────────────────────────────────────

    def save_fact(self, subject: str, key: str, value: str,
                  source: str = "voice") -> None:
        self._run(
            "INSERT INTO facts (subject, key, value, source, ts) VALUES (?,?,?,?,?)",
            (subject.strip(), key.strip(), value.strip(), source, _now()),
        )

    def lookup_facts(self, query: str, limit: int = 8) -> list[dict]:
        """Keyword match over subject/key/value, newest first (spec: simple
        keyword/recency selection is fine for v1)."""
        words = [w for w in re.findall(r"[a-z0-9']+", query.lower())
                 if len(w) >= 3 and w not in _STOPWORDS]
        if not words:
            return []
        clause = " OR ".join(
            ["lower(subject || ' ' || key || ' ' || value) LIKE ?"] * len(words))
        rows = self._run(
            f"SELECT subject, key, value, ts FROM facts WHERE {clause} "
            "ORDER BY ts DESC, id DESC LIMIT ?",
            tuple(f"%{w}%" for w in words) + (limit,),
        )
        return [dict(r) for r in rows]

    # ── conversation log ─────────────────────────────────────────────────────

    def log_conversation(self, channel: str, role: str, text: str) -> None:
        self._run(
            "INSERT INTO conversation_log (ts, channel, role, text) VALUES (?,?,?,?)",
            (_now(), channel, role, text),
        )

    # ── preferences ──────────────────────────────────────────────────────────

    def set_preference(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO preferences (key, value, ts) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (key, value, _now()),
        )

    def get_preference(self, key: str) -> str | None:
        rows = self._run("SELECT value FROM preferences WHERE key=?", (key,))
        return rows[0]["value"] if rows else None

    # ── lists ────────────────────────────────────────────────────────────────

    def list_add(self, list_name: str, item: str) -> None:
        self._run(
            "INSERT INTO lists (list_name, item, ts) VALUES (?,?,?)",
            (list_name, item.strip(), _now()),
        )

    def list_remove(self, list_name: str, item: str) -> int:
        """Remove by exact (case-insensitive) match, falling back to substring."""
        for pattern in (item.strip().lower(), f"%{item.strip().lower()}%"):
            rows = self._run(
                "DELETE FROM lists WHERE list_name=? AND lower(item) LIKE ? "
                "RETURNING item",
                (list_name, pattern),
            )
            if rows:
                return len(rows)
        return 0

    def list_items(self, list_name: str) -> list[str]:
        rows = self._run(
            "SELECT item FROM lists WHERE list_name=? AND done=0 ORDER BY id",
            (list_name,),
        )
        return [r["item"] for r in rows]

    def list_clear(self, list_name: str) -> int:
        rows = self._run(
            "DELETE FROM lists WHERE list_name=? RETURNING id", (list_name,))
        return len(rows)

    def list_names(self) -> list[str]:
        rows = self._run("SELECT DISTINCT list_name FROM lists ORDER BY list_name")
        return [r["list_name"] for r in rows]

    # ── game state (used by M6) ──────────────────────────────────────────────

    def set_game_state(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO game_state (key, value, ts) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (key, value, _now()),
        )

    def get_game_state(self, key: str) -> str | None:
        rows = self._run("SELECT value FROM game_state WHERE key=?", (key,))
        return rows[0]["value"] if rows else None

    # ── tool functions (registered by the daemon) ────────────────────────────

    def tool_lists(self, action: str, list: str = "shopping",
                   item: str | None = None) -> str:
        name = (list or "shopping").strip().lower()
        if action == "add":
            if not item:
                return "Nothing to add — 'item' is required."
            self.list_add(name, item)
            return f"Added {item!r} to the {name} list."
        if action == "remove":
            if not item:
                return "Nothing to remove — 'item' is required."
            n = self.list_remove(name, item)
            return (f"Removed {n} item(s) matching {item!r} from the {name} list."
                    if n else f"No item matching {item!r} on the {name} list.")
        if action == "show":
            items = self.list_items(name)
            if not items:
                others = [n for n in self.list_names() if n != name]
                extra = f" (other lists: {', '.join(others)})" if others else ""
                return f"The {name} list is empty.{extra}"
            return f"The {name} list: " + "; ".join(items)
        if action == "clear":
            n = self.list_clear(name)
            return f"Cleared the {name} list ({n} items removed)."
        return f"Unknown action {action!r}."

    def tool_save_fact(self, subject: str, key: str, value: str) -> str:
        self.save_fact(subject, key, value)
        return f"Noted: {subject} — {key}: {value}."

    def tool_lookup(self, query: str) -> str:
        facts = self.lookup_facts(query)
        if not facts:
            return "Nothing in memory matches that."
        return "Remembered facts: " + "; ".join(
            f"{f['subject']} — {f['key']}: {f['value']}" for f in facts)

    def fact_context(self, user_text: str, limit: int = 6) -> str:
        """Relevant-facts block injected into the system prompt each turn."""
        facts = self.lookup_facts(user_text, limit=limit)
        if not facts:
            return ""
        return "\n".join(
            f"- {f['subject']} — {f['key']}: {f['value']}" for f in facts)


LISTS_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["add", "remove", "show", "clear"]},
        "list": {
            "type": "string",
            "description": "List name, e.g. 'shopping', 'todo'. Defaults to 'shopping'.",
        },
        "item": {
            "type": "string",
            "description": "The item to add or remove (required for add/remove).",
        },
    },
    "required": ["action"],
}

SAVE_FACT_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {
            "type": "string",
            "description": "Who or what the fact is about, e.g. 'Mom', 'family', "
                           "'household'.",
        },
        "key": {
            "type": "string",
            "description": "Short label, e.g. 'preferred seat', 'birthday'.",
        },
        "value": {"type": "string", "description": "The fact itself."},
    },
    "required": ["subject", "key", "value"],
}

LOOKUP_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Keywords to search remembered facts for.",
        },
    },
    "required": ["query"],
}
