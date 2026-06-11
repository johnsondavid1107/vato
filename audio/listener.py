"""Wake word detection (openWakeWord) + record-until-silence (RMS VAD).

openWakeWord replaces the spec's original Porcupine choice — see manifest.md.
It is fully local and needs no account or API key; the spec's Phase 2 plan
(custom "Vato" model trained with openWakeWord) drops into the same config.
Raw audio never leaves the machine (spec §3, §6).
"""

import logging
import time
from pathlib import Path

import numpy as np
import openwakeword
import openwakeword.utils
from openwakeword.model import Model
from pvrecorder import PvRecorder

from audio.mute import MuteState

log = logging.getLogger("vato.audio")

# 80 ms @ 16 kHz — the chunk size openWakeWord is calibrated for.
FRAME_LENGTH = 1280
SAMPLE_RATE = 16_000


class VoiceListener:
    def __init__(self, cfg: dict, mute: MuteState):
        wake_cfg = cfg.get("wake", {})
        self._vad = cfg.get("vad", {})
        self._mute = mute
        self._threshold = float(wake_cfg.get("threshold", 0.5))

        model = (wake_cfg.get("model") or "hey_jarvis").strip()
        model_path = Path(model).expanduser()
        if model_path.suffix in (".onnx", ".tflite") and model_path.exists():
            # Custom model (e.g. a trained "Hey Vato"); fetch shared feature
            # models only. download_models is a no-op when already cached.
            openwakeword.utils.download_models(model_names=[])
            wakeword_models = [str(model_path)]
            self.wake_phrase = model_path.stem.replace("_", " ").title()
        else:
            if model not in openwakeword.MODELS:
                raise RuntimeError(
                    f"Unknown wake model {model!r}. Use one of "
                    f"{sorted(openwakeword.MODELS)} or a path to a .onnx file."
                )
            openwakeword.utils.download_models(model_names=[model])
            wakeword_models = [model]
            self.wake_phrase = model.replace("_", " ").title()

        self._oww = Model(
            wakeword_models=wakeword_models,
            inference_framework="onnx",
        )

        self.sample_rate = SAMPLE_RATE
        self._recorder = PvRecorder(
            frame_length=FRAME_LENGTH,
            device_index=int(wake_cfg.get("audio_device_index", -1)),
        )
        self._running = False

    # -- capture control ------------------------------------------------
    def resume(self) -> None:
        if not self._running:
            self._recorder.start()
            self._oww.reset()  # drop stale audio so old speech can't retrigger
            self._running = True

    def pause(self) -> None:
        """Fully stop audio capture (used while Vato speaks, and while muted)."""
        if self._running:
            self._recorder.stop()
            self._running = False

    def close(self) -> None:
        self.pause()
        self._recorder.delete()

    # -- main entry points ------------------------------------------------
    def wait_for_wake(self) -> None:
        """Block until the wake word fires. Honors mute: capture is fully
        stopped while muted and restarted on unmute."""
        while True:
            if self._mute.is_muted:
                self.pause()
                self._mute.wait_until_unmuted()
                continue
            self.resume()
            frame = np.array(self._recorder.read(), dtype=np.int16)
            scores = self._oww.predict(frame)
            if max(scores.values()) >= self._threshold:
                self._oww.reset()
                return

    def record_command(self) -> np.ndarray | None:
        """Record until silence. Returns int16 PCM at 16 kHz, or None if no
        speech was heard (or mute was hit mid-recording)."""
        threshold = float(self._vad.get("silence_threshold", 300))
        silence_duration = float(self._vad.get("silence_duration", 1.2))
        max_wait = float(self._vad.get("max_wait_for_speech", 6))
        max_seconds = float(self._vad.get("max_command_seconds", 12))

        self.resume()
        frames: list[np.ndarray] = []
        heard_speech = False
        silence_started: float | None = None
        t0 = time.monotonic()

        while True:
            if self._mute.is_muted:
                return None
            frame = np.array(self._recorder.read(), dtype=np.int16)
            frames.append(frame)
            rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
            now = time.monotonic()

            if rms >= threshold:
                heard_speech = True
                silence_started = None
            elif heard_speech:
                if silence_started is None:
                    silence_started = now
                elif now - silence_started >= silence_duration:
                    break
            elif now - t0 >= max_wait:
                return None

            if now - t0 >= max_seconds:
                break

        return np.concatenate(frames) if heard_speech else None
