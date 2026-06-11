"""Single mouth for everything Vato says out loud.

Both the voice loop's replies and the scheduler's alerts/announcements go
through one Announcer holding one lock, so a timer going off mid-reply waits
its turn instead of talking over it. Handles the face cue (talking state with
the amplitude-synced mouth, then back to idle/muted) in one place.
"""

import subprocess
import threading

from audio.mute import MuteState
from audio.tts import Voice
from face.server import FaceServer

CHIME = "/System/Library/Sounds/Glass.aiff"


class Announcer:
    def __init__(self, voice: Voice, face: FaceServer, mute: MuteState):
        self._voice = voice
        self._face = face
        self._mute = mute
        self._lock = threading.Lock()

    def say(self, text: str, chime: bool = False) -> None:
        with self._lock:
            if chime:
                subprocess.run(["afplay", CHIME], check=False)
            self._face.set_state("talking", text=text)
            self._voice.speak(text, on_start=lambda env, dt: self._face.set_state(
                "talking", text=text, mouth={"envelope": env, "interval": dt}))
            self._face.set_state("muted" if self._mute.is_muted else "idle")
