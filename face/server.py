"""Face UI server: serves the static web app and pushes face state over a
WebSocket (spec §4, §9). The voice loop runs in a worker thread and calls
set_state(), which marshals onto the asyncio loop.

M2 surface: kid effects (loaded from face/effects/*.json), weather wardrobe
overlays, the back-panel task ticker, quiet-hours sleeping, and an amplitude
envelope for talking mouth sync.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

from aiohttp import web, WSMsgType

log = logging.getLogger("vato.face")

STATIC_DIR = Path(__file__).parent / "static"
EFFECTS_DIR = Path(__file__).parent / "effects"

DEFAULT_EFFECT_SECONDS = 300  # spec §9: kid effects melt back after 5 minutes
TICKER_KEEP = 30              # recent ticker lines replayed to reconnecting TVs


def load_effects() -> dict[str, dict]:
    """Read the effects registry: one small JSON file per effect (spec §9)."""
    effects = {}
    for path in sorted(EFFECTS_DIR.glob("*.json")):
        try:
            effect = json.loads(path.read_text(encoding="utf-8"))
            effects[effect["name"]] = effect
        except (json.JSONDecodeError, KeyError):
            log.exception("Bad effect file skipped: %s", path.name)
    return effects


class FaceServer:
    def __init__(self, cfg: dict):
        face = cfg.get("face", {})
        self.host = face.get("host", "127.0.0.1")
        self.port = int(face.get("port", 8765))
        self.face_color = face.get("face_color", "#e8483f")
        self.effects = load_effects()
        self._clients: set[web.WebSocketResponse] = set()
        self._state = {"state": "idle", "text": None, "mouth": None}
        self._quiet = False            # quiet hours: idle renders as sleeping
        self._wardrobe: list[str] = []
        self._effect: dict | None = None
        self._effect_expires = 0.0
        self._ticker: list[str] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/ws", self._websocket)
        app.router.add_static("/static", STATIC_DIR)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        log.info("Face UI at %s", self.url)

    # -- state API (thread-safe) -----------------------------------------
    def set_state(self, state: str, text: str | None = None,
                  mouth: dict | None = None) -> None:
        if state == "idle" and self._quiet:
            state = "sleeping"  # spec §9: quiet hours
        self._state = {"state": state, "text": text, "mouth": mouth}
        self._send({"type": "state", **self._state})

    def set_quiet(self, quiet: bool) -> None:
        """Quiet hours on/off. Re-renders idle<->sleeping if currently resting."""
        if quiet == self._quiet:
            return
        self._quiet = quiet
        if self._state["state"] in ("idle", "sleeping"):
            self.set_state("idle")

    def set_wardrobe(self, items: list[str]) -> None:
        """Weather wardrobe (spec §9): e.g. ['sunglasses'], ['knit-hat', 'snow']."""
        if items == self._wardrobe:
            return
        self._wardrobe = items
        log.info("Wardrobe: %s", ", ".join(items) or "(plain)")
        self._send({"type": "wardrobe", "items": items})

    def set_effect(self, name: str, color: str | None = None,
                   duration_s: float | None = None) -> str:
        """Apply a kid effect by registry name, or the built-ins
        'face_color' (needs color) and 'clear'. Returns a line for the model."""
        if name == "clear":
            self._effect = None
            self._send({"type": "effect", "effect": None})
            return "Face restored to normal."

        if name == "face_color":
            if not color:
                return "Tool error: face_color needs a CSS color."
            effect = {"name": "face_color", "face_color": color}
        elif name in self.effects:
            effect = dict(self.effects[name])
        else:
            return f"Tool error: unknown effect {name!r}. Known: {', '.join(self.effects)}"

        seconds = float(duration_s or effect.get("duration_s") or DEFAULT_EFFECT_SECONDS)
        effect["duration_s"] = seconds
        self._effect = effect
        self._effect_expires = time.monotonic() + seconds
        self._send({"type": "effect", "effect": effect})
        return f"Effect {name!r} applied; it melts back after {round(seconds / 60)} minute(s)."

    def ticker(self, text: str) -> None:
        """Back-panel task ticker line, plain language (spec §9)."""
        self._ticker.append(text)
        self._ticker = self._ticker[-TICKER_KEEP:]
        self._send({"type": "ticker", "text": text})

    def _send(self, payload: dict) -> None:
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._broadcast(json.dumps(payload)), self._loop)

    async def _broadcast(self, message: str) -> None:
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_str(message)
            except ConnectionResetError:
                dead.add(ws)
        self._clients -= dead

    # -- handlers ----------------------------------------------------------
    async def _index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    async def _websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._clients.add(ws)
        # Full sync so a kiosk reconnect lands in the right look.
        await ws.send_str(json.dumps({
            "type": "config",
            "face_color": self.face_color,
            "effects": list(self.effects.values()),
        }))
        await ws.send_str(json.dumps({"type": "wardrobe", "items": self._wardrobe}))
        if self._effect is not None:
            remaining = self._effect_expires - time.monotonic()
            if remaining > 0:
                effect = dict(self._effect)
                effect["duration_s"] = remaining
                await ws.send_str(json.dumps({"type": "effect", "effect": effect}))
            else:
                self._effect = None
        for line in self._ticker:
            await ws.send_str(json.dumps({"type": "ticker", "text": line, "replay": True}))
        await ws.send_str(json.dumps({"type": "state", **self._state}))
        try:
            async for msg in ws:
                if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
        finally:
            self._clients.discard(ws)
        return ws
