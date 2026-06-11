"""vatod — the single long-running daemon (spec §3, §4).

M1: wake word → record → local STT → Claude (tools) → TTS → face states
over WebSocket; mute hotkey fully stops capture.
M2: the working flip with live ticker (tool calls + Tier 2/3 audit lines),
kid effects via the set_face_effect tool, weather wardrobe on a schedule,
quiet-hours sleeping, amplitude-synced talking mouth.
"""

import asyncio
import datetime
import logging
import subprocess
import threading

from audio.listener import VoiceListener
from audio.mute import MuteState, start_hotkey_listener
from audio.stt import Transcriber
from audio.tts import MacSayVoice
from brain.client import Brain
from core.audit import AuditLog
from core.config import ROOT, load_config, require_env
from core.tools import Tool, ToolRouter
from face.server import FaceServer
from integrations.weather import (
    CLEAR_CODES, GET_WEATHER_SCHEMA, RAIN_CODES, SNOW_CODES, WeatherService,
)

log = logging.getLogger("vato")

CHIME = "/System/Library/Sounds/Glass.aiff"
ERROR_APOLOGY = (
    "I do apologise — something went awry on my end. Do give me another moment."
)


def _chime() -> None:
    subprocess.Popen(["afplay", CHIME])


def _build_router(cfg: dict, audit: AuditLog, weather: WeatherService,
                  face: FaceServer) -> ToolRouter:
    router = ToolRouter(audit, channel="voice")
    router.register(Tool(
        name="get_weather",
        tier=0,
        description=(
            "Get current weather and today's forecast. Call with no arguments "
            "for the household's home location, or pass a city name."
        ),
        input_schema=GET_WEATHER_SCHEMA,
        fn=weather.get_weather,
        returns_untrusted=True,  # external content — feeds the §6 firewall
        ticker_line=lambda args: (
            f"Checking the weather for {args.get('location') or 'the household'}…"
        ),
    ))

    effect_names = list(face.effects) + ["face_color", "clear"]
    router.register(Tool(
        name="set_face_effect",
        tier=0,
        description=(
            "Change Vato's on-screen face with a fun temporary effect (the kid "
            "commands). Map free-form phrasing to the nearest effect: "
            + "; ".join(f"'{e['name']}' = {e.get('description', e['name'])}"
                        for e in face.effects.values())
            + ". Use 'face_color' with a CSS color for requests like 'make "
            "your face blue', and 'clear' to go back to normal early. Effects "
            "melt back on their own after five minutes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "effect": {"type": "string", "enum": effect_names},
                "color": {
                    "type": "string",
                    "description": "CSS color, only for effect 'face_color'.",
                },
                "minutes": {
                    "type": "number",
                    "description": "How long to keep it. Omit for the default 5.",
                },
            },
            "required": ["effect"],
        },
        fn=lambda effect, color=None, minutes=None: face.set_effect(
            effect, color, minutes * 60 if minutes else None),
        ticker_line=lambda args: f"Putting on the {args.get('effect')} face…",
    ))
    return router


def _voice_loop(listener: VoiceListener, transcriber: Transcriber, brain: Brain,
                voice: MacSayVoice, face: FaceServer, mute: MuteState) -> None:
    log.info('Voice loop ready — say "%s".', listener.wake_phrase)
    while True:
        try:
            listener.wait_for_wake()
            log.info("Wake word detected")
            face.set_state("listening")
            _chime()

            pcm = listener.record_command()
            if pcm is None:
                log.info("No speech heard; back to idle")
                face.set_state("muted" if mute.is_muted else "idle")
                continue

            face.set_state("thinking")
            listener.pause()  # don't capture while transcribing/replying
            transcript = transcriber.transcribe(pcm)
            if not transcript:
                face.set_state("idle")
                continue
            log.info("Heard: %s", transcript)

            reply = brain.respond(transcript)
            log.info("Vato: %s", reply)

            # Fallback jaw loop now; the envelope upgrade lands via on_start
            # once the speech is rendered (mouth then tracks the audio).
            face.set_state("talking", text=reply)
            voice.speak(reply, on_start=lambda env, dt: face.set_state(
                "talking", text=reply, mouth={"envelope": env, "interval": dt}))
            face.set_state("muted" if mute.is_muted else "idle")

        except Exception:
            log.exception("Interaction failed")
            face.set_state("error")
            try:
                listener.pause()
                voice.speak(ERROR_APOLOGY)
            except Exception:
                pass
            face.set_state("muted" if mute.is_muted else "idle")


# ── Ambient loop: quiet hours + weather wardrobe (spec §9) ────────────────────

def _parse_hhmm(value: str) -> datetime.time:
    hour, minute = value.split(":")
    return datetime.time(int(hour), int(minute))


def _in_quiet_hours(cfg: dict, now: datetime.datetime | None = None) -> bool:
    quiet = cfg.get("quiet_hours") or {}
    try:
        start = _parse_hhmm(quiet.get("start", "21:00"))
        end = _parse_hhmm(quiet.get("end", "07:00"))
    except (ValueError, AttributeError):
        return False
    t = (now or datetime.datetime.now()).time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # window crosses midnight


def _wardrobe_items(cond: dict, quiet: bool) -> list[str]:
    """Map current conditions to overlays (spec §9 environmental wardrobe)."""
    items = []
    if cond["code"] in SNOW_CODES:
        items += ["knit-hat", "snow"]
    elif cond["code"] in RAIN_CODES:
        items += ["umbrella", "rain"]
    if cond["temp_c"] <= 0:
        items.append("frost")
    elif (cond["temp_c"] >= 24 and cond["is_day"]
          and cond["code"] in CLEAR_CODES and "knit-hat" not in items):
        items.append("sunglasses")
    if quiet:
        items.append("nightcap")  # pre-sleeping
    return items


async def _ambient_loop(cfg: dict, face: FaceServer, weather: WeatherService) -> None:
    refresh = float(cfg.get("wardrobe", {}).get("refresh_minutes", 30)) * 60
    last_weather = 0.0
    cond: dict | None = None
    while True:
        quiet = _in_quiet_hours(cfg)
        face.set_quiet(quiet)

        now = asyncio.get_running_loop().time()
        if now - last_weather >= refresh or cond is None:
            try:
                cond = await asyncio.to_thread(weather.current_conditions)
                last_weather = now
            except Exception as exc:
                log.warning("Wardrobe weather check failed: %s", exc)
        if cond is not None:
            face.set_wardrobe(_wardrobe_items(cond, quiet))
        await asyncio.sleep(60)


async def _serve(cfg: dict, face: FaceServer, weather: WeatherService,
                 voice_thread: threading.Thread) -> None:
    await face.start()
    print()
    print(f"  Vato's face:  {face.url}")
    print(f'  TV kiosk:     open -na "Google Chrome" --args --kiosk --app={face.url}')
    print()
    asyncio.create_task(_ambient_loop(cfg, face, weather))
    voice_thread.start()
    await asyncio.Event().wait()  # run until Ctrl-C


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config()
    require_env("ANTHROPIC_API_KEY")  # the SDK reads it; fail fast if missing

    audit_path = cfg.get("audit", {}).get("path", "audit/audit.log")
    audit = AuditLog(ROOT / audit_path)
    face = FaceServer(cfg)
    weather = WeatherService(cfg)
    router = _build_router(cfg, audit, weather, face)

    # Tier 2/3 audit entries scroll across the back-panel ticker (spec §6).
    audit.on_record = lambda e: face.ticker(
        f"[tier {e['tier']}] {e['action']} {e['args']} → {e['outcome']}"
    ) if e["tier"] >= 2 else None

    # Tool calls flip the face to the engine room with a plain-language line
    # (spec §4 step 4, §9) — except face effects, which belong on the front.
    def on_tool(name: str, args: dict) -> None:
        face.ticker(router.describe_call(name, args))
        if name != "set_face_effect":
            face.set_state("working")

    brain = Brain(cfg, router, on_tool=on_tool)
    voice = MacSayVoice(cfg)

    log.info("Loading speech-to-text (first run downloads the Whisper model)...")
    transcriber = Transcriber(cfg)

    mute = MuteState()
    mute.on_change(lambda muted: face.set_state("muted" if muted else "idle"))
    listener = VoiceListener(cfg, mute)
    start_hotkey_listener(cfg.get("mute", {}).get("hotkey", "<cmd>+<shift>+m"), mute)

    voice_thread = threading.Thread(
        target=_voice_loop,
        args=(listener, transcriber, brain, voice, face, mute),
        daemon=True,
        name="voice-loop",
    )

    try:
        asyncio.run(_serve(cfg, face, weather, voice_thread))
    except KeyboardInterrupt:
        log.info("Shutting down. Good night, sir.")
    finally:
        listener.close()
