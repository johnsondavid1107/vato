"""Soft mute (spec §6): a global hotkey that fully stops audio capture.

The listener consults MuteState every frame; while muted the recorder is
stopped (no audio is captured at all) and the face shows the muted state.
"""

import logging
import threading
from typing import Callable

log = logging.getLogger("vato.mute")


class MuteState:
    def __init__(self):
        self._muted = False
        self._unmuted = threading.Event()
        self._unmuted.set()
        self._callbacks: list[Callable[[bool], None]] = []

    @property
    def is_muted(self) -> bool:
        return self._muted

    def on_change(self, callback: Callable[[bool], None]) -> None:
        self._callbacks.append(callback)

    def toggle(self) -> None:
        self._muted = not self._muted
        if self._muted:
            self._unmuted.clear()
        else:
            self._unmuted.set()
        log.info("Mute %s", "ON — audio capture stopped" if self._muted else "off")
        for cb in self._callbacks:
            cb(self._muted)

    def wait_until_unmuted(self) -> None:
        self._unmuted.wait()


def start_hotkey_listener(hotkey: str, mute: MuteState) -> None:
    """Register the global mute hotkey. Needs macOS Input Monitoring permission
    for the terminal/python running vatod (see README); degrades gracefully."""
    try:
        from pynput import keyboard
        listener = keyboard.GlobalHotKeys({hotkey: mute.toggle})
        listener.daemon = True
        listener.start()
        log.info("Mute hotkey registered: %s", hotkey)
    except Exception as exc:
        log.warning(
            "Mute hotkey unavailable (%s). Grant Input Monitoring permission to "
            "your terminal in System Settings → Privacy & Security, then restart.",
            exc,
        )
