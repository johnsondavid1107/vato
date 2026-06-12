"""Games night + idea sessions (spec §10 game_state, §11 game_host /
idea_session, §13 M6).

Division of labour: the LLM is the quizmaster — it invents the questions,
judges the answers, and keeps the patter in character. This module is the
scorekeeper and stagehand: authoritative scores (so a long game can't drift
out of the model's pruned history), persistent all-time family totals in
SQLite, and the info panel renders (spec §9).
"""

import json
import logging

from face.server import FaceServer
from memory.store import MemoryStore

log = logging.getLogger("vato.games")

ALLTIME_KEY = "alltime_points"
GAMES_PLAYED_KEY = "games_played"

GAME_HOST_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["start", "show", "award", "scoreboard", "end",
                     "clear_panel"],
            "description": (
                "start: begin a game (game + players). "
                "show: put content on the TV info panel (title + lines), e.g. "
                "a trivia question with options, a word puzzle, a story "
                "chapter heading. "
                "award: give points to a player (re-renders the scoreboard). "
                "scoreboard: show current scores. "
                "end: finish — persists all-time totals and shows the final "
                "board. clear_panel: back to the full face ('thanks, Vato')."
            ),
        },
        "game": {"type": "string",
                 "description": "For start: trivia, twenty questions, word game, story…"},
        "players": {"type": "array", "items": {"type": "string"},
                    "description": "For start: who's playing, first names."},
        "player": {"type": "string", "description": "For award: who scored."},
        "points": {"type": "number", "description": "For award: how many (default 1)."},
        "title": {"type": "string", "description": "For show: panel heading."},
        "lines": {"type": "array", "items": {"type": "string"},
                  "description": ("For show: the large on-screen lines (a "
                                  "question, options, clues…). Keep each short; "
                                  "~8 fit. Empty string makes a gap.")},
        "footer": {"type": "string", "description": "For show: small italic line at the bottom."},
    },
    "required": ["action"],
}

IDEA_SESSION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "The idea being worked, short."},
        "pros": {"type": "array", "items": {"type": "string"}},
        "cons": {"type": "array", "items": {"type": "string"},
                 "description": "Include the devil's-advocate points here."},
        "next_steps": {"type": "array", "items": {"type": "string"},
                       "description": "Optional: how to validate it cheaply."},
    },
    "required": ["title", "pros", "cons"],
}


class GameHost:
    def __init__(self, memory: MemoryStore, face: FaceServer):
        self._memory = memory
        self._face = face
        # One game at a time, household-wide (voice + Telegram share it).
        self._game: str | None = None
        self._scores: dict[str, float] = {}

    @property
    def active(self) -> bool:
        """A game is in progress (conversation mode lengthens its follow-up
        window while this is true — the family deliberates answers)."""
        return self._game is not None

    # ── persistence ──────────────────────────────────────────────────────────

    def _alltime(self) -> dict[str, float]:
        raw = self._memory.get_game_state(ALLTIME_KEY)
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def _bank_scores(self) -> None:
        alltime = self._alltime()
        for player, pts in self._scores.items():
            alltime[player] = alltime.get(player, 0) + pts
        self._memory.set_game_state(ALLTIME_KEY, json.dumps(alltime))
        played = int(self._memory.get_game_state(GAMES_PLAYED_KEY) or 0)
        self._memory.set_game_state(GAMES_PLAYED_KEY, str(played + 1))

    # ── rendering ────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(pts: float) -> str:
        return str(int(pts)) if pts == int(pts) else f"{pts:g}"

    def _score_lines(self) -> list[str]:
        ranked = sorted(self._scores.items(), key=lambda kv: -kv[1])
        return [f"{'★' * min(int(p), 10) or '·'}  {name} — {self._fmt(p)}"
                for name, p in ranked]

    def _show_scoreboard(self, title: str, footer: str = "") -> None:
        self._face.set_panel(title=title, lines=self._score_lines(),
                             footer=footer)

    # ── the tool ─────────────────────────────────────────────────────────────

    def tool_game_host(self, action: str, game: str | None = None,
                       players: list[str] | None = None,
                       player: str | None = None, points: float | None = None,
                       title: str | None = None, lines: list[str] | None = None,
                       footer: str | None = None) -> str:
        if action == "start":
            self._game = game or "trivia"
            self._scores = {p: 0 for p in (players or [])}
            self._show_scoreboard(f"{self._game.title()} — let's begin!",
                                  footer="Scores so far")
            alltime = self._alltime()
            standings = ", ".join(
                f"{n}: {self._fmt(p)}" for n, p in
                sorted(alltime.items(), key=lambda kv: -kv[1])) or "none yet"
            return (f"Game '{self._game}' started with "
                    f"{', '.join(self._scores) or 'no named players'}. "
                    f"All-time family points (for your patter): {standings}.")

        if action == "show":
            self._face.set_panel(title=title or (self._game or "").title(),
                                 lines=lines or [], footer=footer)
            return "Displayed on the television."

        if action == "award":
            if not player:
                return "Tool error: award needs a player name."
            self._scores[player] = self._scores.get(player, 0) + (
                points if points is not None else 1)
            self._show_scoreboard("Scoreboard")
            return ("Scores now: " + ", ".join(
                f"{n}: {self._fmt(p)}" for n, p in
                sorted(self._scores.items(), key=lambda kv: -kv[1])))

        if action == "scoreboard":
            self._show_scoreboard("Scoreboard")
            return ("Current scores: " + (", ".join(
                f"{n}: {self._fmt(p)}" for n, p in self._scores.items())
                or "no points yet"))

        if action == "end":
            if self._game is None:
                self._face.clear_panel()
                return "No game was running."
            final = ", ".join(f"{n}: {self._fmt(p)}" for n, p in
                              sorted(self._scores.items(), key=lambda kv: -kv[1]))
            self._bank_scores()
            self._show_scoreboard("Final scores", footer="Thank you for playing!")
            alltime = self._alltime()
            standings = ", ".join(
                f"{n}: {self._fmt(p)}" for n, p in
                sorted(alltime.items(), key=lambda kv: -kv[1]))
            self._game, self._scores = None, {}
            return (f"Game over. Final: {final or 'no scores'}. "
                    f"All-time family points: {standings or 'none'}. "
                    "The board stays up a moment; clear_panel when thanked.")

        if action == "clear_panel":
            self._face.clear_panel()
            return "Panel cleared; back to the full face."

        return f"Tool error: unknown action {action!r}."


def make_idea_session(face: FaceServer):
    """idea_session tool fn (spec §11): structured brainstorm board on the TV."""

    def idea_session(title: str, pros: list[str], cons: list[str],
                     next_steps: list[str] | None = None) -> str:
        lines = [f"✓ {p}" for p in pros] + [""] + [f"✗ {c}" for c in cons]
        if next_steps:
            lines += [""] + [f"→ {s}" for s in next_steps]
        face.set_panel(title=f"Idea: {title}", lines=lines,
                       footer="Devil's advocacy included, sir.")
        return ("Board displayed. Walk through it briefly aloud; the "
                "details are on screen.")

    return idea_session
