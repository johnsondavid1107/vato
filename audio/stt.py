"""Local speech-to-text: mlx-whisper (Apple Silicon) with whisper.cpp fallback.

Spoken audio is transcribed locally; only the resulting text is ever sent to
the Claude API (spec §3, §6).
"""

import logging
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger("vato.stt")

SAMPLE_RATE = 16_000


class Transcriber:
    def __init__(self, cfg: dict):
        stt_cfg = cfg.get("stt", {})
        self._engine = stt_cfg.get("engine", "mlx")
        self._mlx_model = stt_cfg.get("mlx_model", "mlx-community/whisper-small.en-mlx")
        self._cpp_model = (stt_cfg.get("whisper_cpp_model") or "").strip()

        if self._engine == "mlx":
            try:
                import mlx_whisper  # noqa: F401  (verify it imports on this machine)
                self._mlx_whisper = mlx_whisper
            except ImportError as exc:
                raise RuntimeError(
                    "mlx-whisper is not installed (it requires Apple Silicon). "
                    "Either `pip install mlx-whisper`, or set stt.engine: whisper_cpp "
                    "in config.yaml with a ggml model path."
                ) from exc
            log.info("STT: mlx-whisper, model %s (downloads on first use)", self._mlx_model)
        elif self._engine == "whisper_cpp":
            self._cpp_bin = (
                shutil.which("whisper-cli") or shutil.which("whisper-cpp")
            )
            if not self._cpp_bin:
                raise RuntimeError(
                    "whisper.cpp binary not found. `brew install whisper-cpp` "
                    "provides whisper-cli."
                )
            if not self._cpp_model or not Path(self._cpp_model).expanduser().exists():
                raise RuntimeError(
                    "stt.whisper_cpp_model must point to a ggml model file "
                    "(e.g. ggml-base.en.bin)."
                )
            log.info("STT: whisper.cpp at %s, model %s", self._cpp_bin, self._cpp_model)
        else:
            raise RuntimeError(f"Unknown stt.engine: {self._engine!r} (use mlx or whisper_cpp)")

    def transcribe(self, pcm16: np.ndarray) -> str:
        if self._engine == "mlx":
            return self._transcribe_mlx(pcm16)
        return self._transcribe_cpp(pcm16)

    def _transcribe_mlx(self, pcm16: np.ndarray) -> str:
        audio = pcm16.astype(np.float32) / 32768.0
        result = self._mlx_whisper.transcribe(audio, path_or_hf_repo=self._mlx_model)
        return result["text"].strip()

    def _transcribe_cpp(self, pcm16: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        try:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm16.tobytes())
            proc = subprocess.run(
                [
                    self._cpp_bin,
                    "-m", str(Path(self._cpp_model).expanduser()),
                    "-f", wav_path,
                    "-nt",          # no timestamps
                    "-np",          # no progress prints
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"whisper.cpp failed: {proc.stderr.strip()}")
            return proc.stdout.strip()
        finally:
            Path(wav_path).unlink(missing_ok=True)
