"""Timers and scheduled announcements (spec §3 scheduler, §11).

APScheduler in-process; jobs live in memory, so pending timers do not survive
a daemon restart (acceptable for kitchen timers — documented in run.md).
Firing goes through the Announcer: chime, spoken alert, face cue. Proactivity
policy (spec §10): these scheduled things are the *only* unprompted speech.
"""

import datetime
import itertools
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from core.announce import Announcer

log = logging.getLogger("vato.scheduler")


def _duration_phrase(minutes: float, seconds: float) -> str:
    total = int(round(minutes * 60 + seconds))
    mins, secs = divmod(total, 60)
    parts = []
    if mins:
        parts.append(f"{mins} minute" + ("s" if mins != 1 else ""))
    if secs:
        parts.append(f"{secs} second" + ("s" if secs != 1 else ""))
    return " and ".join(parts) or "0 seconds"


class VatoScheduler:
    def __init__(self, announcer: Announcer, on_fire=None):
        self._announcer = announcer
        # on_fire(text): extra hook for the back-panel ticker / audit trail.
        self._on_fire = on_fire
        self._seq = itertools.count(1)
        self._sched = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 60})
        self._sched.start()

    def shutdown(self) -> None:
        self._sched.shutdown(wait=False)

    # ── firing ───────────────────────────────────────────────────────────────

    def _fire(self, text: str) -> None:
        log.info("Scheduled alert: %s", text)
        if self._on_fire is not None:
            try:
                self._on_fire(text)
            except Exception:
                pass
        self._announcer.say(text, chime=True)

    # ── tool functions (registered by the daemon) ────────────────────────────

    def tool_timer_set(self, minutes: float = 0, seconds: float = 0,
                       label: str | None = None) -> str:
        total = minutes * 60 + seconds
        if total <= 0:
            return "Timer not set — a positive duration is required."
        phrase = _duration_phrase(minutes, seconds)
        name = (label or "").strip()
        alert = (f"Pardon the interruption — the {name} timer is up."
                 if name else f"Pardon the interruption — your {phrase} timer is up.")
        when = datetime.datetime.now() + datetime.timedelta(seconds=total)
        job = self._sched.add_job(
            self._fire, "date", run_date=when, args=[alert],
            id=f"timer-{next(self._seq)}",
            name=name or f"{phrase} timer",
        )
        return (f"Timer '{job.name}' set for {phrase} "
                f"(rings at {when.strftime('%H:%M:%S')}).")

    def tool_timer_cancel(self, label: str | None = None) -> str:
        timers = [j for j in self._sched.get_jobs() if j.id.startswith("timer-")]
        if not timers:
            return "There are no timers running."
        want = (label or "").strip().lower()
        if want:
            matches = [j for j in timers if want in j.name.lower()]
            if not matches:
                running = ", ".join(j.name for j in timers)
                return f"No timer matching {label!r}. Running timers: {running}."
        elif len(timers) == 1:
            matches = timers
        else:
            running = ", ".join(j.name for j in timers)
            return f"Several timers are running ({running}) — which one?"
        for job in matches:
            job.remove()
        return "Cancelled: " + ", ".join(j.name for j in matches) + "."

    def tool_announce_at(self, time: str, message: str) -> str:
        when = self._parse_when(time)
        if when is None:
            return (f"Could not understand the time {time!r} — use HH:MM "
                    "or an ISO date-time.")
        if when <= datetime.datetime.now():
            return f"{when.strftime('%H:%M')} has already passed today."
        self._sched.add_job(
            self._fire, "date", run_date=when, args=[message],
            id=f"announce-{next(self._seq)}", name=f"announcement: {message[:40]}",
        )
        return f"Announcement scheduled for {when.strftime('%A %H:%M')}: {message}"

    @staticmethod
    def _parse_when(value: str) -> datetime.datetime | None:
        value = value.strip()
        try:  # ISO date-time first ("2026-06-10T18:00")
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            pass
        try:  # bare HH:MM means the next occurrence of that time
            t = datetime.time.fromisoformat(value)
        except ValueError:
            return None
        when = datetime.datetime.combine(datetime.date.today(), t)
        if when <= datetime.datetime.now():
            when += datetime.timedelta(days=1)
        return when


TIMER_SET_SCHEMA = {
    "type": "object",
    "properties": {
        "minutes": {"type": "number", "description": "Minutes until the timer rings."},
        "seconds": {"type": "number", "description": "Extra seconds, if any."},
        "label": {
            "type": "string",
            "description": "Optional name, e.g. 'pasta' for a pasta timer.",
        },
    },
    "required": [],
}

TIMER_CANCEL_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {
            "type": "string",
            "description": "Name of the timer to cancel. Omit if only one is running.",
        },
    },
    "required": [],
}

ANNOUNCE_AT_SCHEMA = {
    "type": "object",
    "properties": {
        "time": {
            "type": "string",
            "description": "When to speak: 'HH:MM' (next occurrence) or an ISO "
                           "date-time like '2026-06-10T18:00'.",
        },
        "message": {
            "type": "string",
            "description": "What Vato should say aloud, written in his butler "
                           "voice, e.g. 'Dinner is served.'",
        },
    },
    "required": ["time", "message"],
}
