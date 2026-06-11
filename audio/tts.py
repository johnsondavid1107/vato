"""Text-to-speech behind a Voice interface (spec §3) so ElevenLabs can swap
in later without touching the rest of the codebase.

M2: speech is rendered to a WAV first so we can hand the face an amplitude
envelope before playback starts — the mouth opens and closes with the audio
(spec §9: amplitude-driven sync is sufficient).
"""

import array
import math
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Callable, Protocol

ENVELOPE_INTERVAL = 0.05  # seconds per envelope sample (20 fps mouth)

# on_start(envelope, interval): called just before audio playback begins.
# envelope is a list of 0..1 loudness values, one per `interval` seconds.
OnStart = Callable[[list[float], float], None]


class Voice(Protocol):
    def speak(self, text: str, on_start: OnStart | None = None) -> None: ...


def _envelope(wav_path: Path) -> tuple[list[float], float]:
    """RMS loudness per ENVELOPE_INTERVAL, normalised to 0..1."""
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
    samples = array.array("h", frames)
    if channels > 1:
        samples = samples[::channels]
    chunk = max(1, int(rate * ENVELOPE_INTERVAL))
    env = []
    for i in range(0, len(samples), chunk):
        block = samples[i:i + chunk]
        env.append(math.sqrt(sum(s * s for s in block) / len(block)))
    peak = max(env) or 1.0
    return [round(v / peak, 2) for v in env], ENVELOPE_INTERVAL


class MacSayVoice:
    """v1: macOS `say` with a dignified voice (default: Daniel)."""

    def __init__(self, cfg: dict):
        tts = cfg.get("tts", {})
        self.voice = tts.get("voice", "Daniel")
        self.rate = int(tts.get("rate", 175))

    def speak(self, text: str, on_start: OnStart | None = None) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            wav = Path(tmp.name)
            # Text via stdin so arbitrary reply content can't be parsed as flags.
            result = subprocess.run(
                ["say", "-v", self.voice, "-r", str(self.rate),
                 "-o", str(wav), "--file-format=WAVE", "--data-format=LEI16@22050"],
                input=text.encode("utf-8"),
                check=False,
            )
            if result.returncode != 0 or wav.stat().st_size == 0:
                # Rendering failed for some reason — speak directly, no sync.
                subprocess.run(
                    ["say", "-v", self.voice, "-r", str(self.rate)],
                    input=text.encode("utf-8"), check=False,
                )
                return
            if on_start is not None:
                try:
                    on_start(*_envelope(wav))
                except Exception:
                    pass  # mouth sync is cosmetic; never block speech on it
            subprocess.run(["afplay", str(wav)], check=False)
