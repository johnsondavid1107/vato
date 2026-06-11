"""CalDAV against iCloud (spec §8) — the portable primary path.

Events read/write on the shared family calendar (config:
family_calendar_name), read-only across other visible calendars; reminders
via VTODO. Auth is an app-specific password (appleid.apple.com →
Sign-In & Security → App-Specific Passwords) in .env as ICLOUD_USERNAME /
ICLOUD_APP_PASSWORD. Connection is lazy so the daemon boots fine while the
credentials are still placeholders.

Self-test once credentials are real:  python -m integrations.caldav_icloud
"""

import datetime
import logging
import os
import threading

import caldav

log = logging.getLogger("vato.caldav")

ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"
SETUP_HINT = (
    "iCloud sign-in failed or is not configured. Generate an app-specific "
    "password at appleid.apple.com (Sign-In & Security → App-Specific "
    "Passwords) and set ICLOUD_USERNAME and ICLOUD_APP_PASSWORD in .env, "
    "then try again."
)


def _local_tz() -> datetime.tzinfo:
    return datetime.datetime.now().astimezone().tzinfo


def _parse_dt(value: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(value.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_local_tz())
    return dt


def _fmt_dt(value) -> str:
    """Human line for a DTSTART/DUE value (datetime or all-day date)."""
    if isinstance(value, datetime.datetime):
        return value.astimezone(_local_tz()).strftime("%a %b %-d %H:%M")
    if isinstance(value, datetime.date):
        return value.strftime("%a %b %-d (all day)")
    return str(value)


class ICloudCalendarService:
    def __init__(self, cfg: dict):
        self._family_name = (cfg.get("family_calendar_name") or "Family").strip()
        self._lock = threading.Lock()
        self._principal: caldav.Principal | None = None

    # ── connection ───────────────────────────────────────────────────────────

    def _connect(self) -> caldav.Principal:
        with self._lock:
            if self._principal is not None:
                return self._principal
            user = os.environ.get("ICLOUD_USERNAME", "").strip()
            password = os.environ.get("ICLOUD_APP_PASSWORD", "").strip()
            if not user or not password:
                raise RuntimeError(SETUP_HINT)
            client = caldav.DAVClient(
                url=ICLOUD_CALDAV_URL, username=user, password=password)
            try:
                self._principal = client.principal()
            except caldav.lib.error.AuthorizationError as exc:
                raise RuntimeError(SETUP_HINT) from exc
            return self._principal

    def calendars(self) -> list[caldav.Calendar]:
        return self._connect().calendars()

    def family_calendar(self) -> caldav.Calendar:
        want = self._family_name.lower()
        cals = self.calendars()
        for cal in cals:
            if (cal.name or "").strip().lower() == want:
                return cal
        names = ", ".join(repr(c.name) for c in cals) or "none visible"
        raise RuntimeError(
            f"No calendar named {self._family_name!r} on this iCloud account "
            f"(visible calendars: {names}). Set family_calendar_name in "
            "config.yaml to one of those."
        )

    def _todo_calendars(self) -> list[caldav.Calendar]:
        cals = [c for c in self.calendars()
                if "VTODO" in (c.get_supported_components() or [])]
        if not cals:
            raise RuntimeError("No reminder (VTODO) lists visible on this account.")
        return cals

    # ── tool functions (registered by the daemon) ────────────────────────────

    def calendar_read(self, days: int = 7, start_date: str | None = None,
                      calendar: str | None = None) -> str:
        start = (_parse_dt(start_date) if start_date
                 else datetime.datetime.now(_local_tz()).replace(
                     hour=0, minute=0, second=0, microsecond=0))
        end = start + datetime.timedelta(days=max(1, int(days)))

        if calendar:
            cals = [c for c in self.calendars()
                    if calendar.strip().lower() in (c.name or "").lower()]
            if not cals:
                return f"No calendar matching {calendar!r} is visible."
        else:
            cals = self.calendars()

        found = []
        for cal in cals:
            try:
                hits = cal.search(start=start, end=end, event=True, expand=True)
            except Exception as exc:  # some iCloud collections 500 on REPORT
                log.warning("search failed on %r: %s", cal.name, exc)
                continue
            for ev in hits:
                comp = ev.icalendar_component
                dtstart = comp.get("DTSTART")
                found.append((
                    dtstart.dt if dtstart is not None else start,
                    f"{_fmt_dt(dtstart.dt) if dtstart is not None else '?'} — "
                    f"{comp.get('SUMMARY', 'untitled')} [{cal.name}]",
                ))

        def sort_key(pair):
            value = pair[0]
            if isinstance(value, datetime.datetime):
                return value.astimezone(_local_tz())
            return datetime.datetime.combine(value, datetime.time.min, _local_tz())

        found.sort(key=sort_key)
        window = f"{start.strftime('%b %-d')} – {end.strftime('%b %-d')}"
        if not found:
            return f"No events between {window}."
        return f"Events {window}:\n" + "\n".join(line for _, line in found[:30])

    def calendar_write(self, title: str, start: str, end: str | None = None,
                       duration_minutes: float = 60, all_day: bool = False,
                       location: str | None = None,
                       description: str | None = None) -> str:
        cal = self.family_calendar()
        kwargs: dict = {"summary": title}
        if location:
            kwargs["location"] = location
        if description:
            kwargs["description"] = description
        if all_day:
            day = _parse_dt(start).date()
            kwargs["dtstart"] = day
            kwargs["dtend"] = day + datetime.timedelta(days=1)
            when = day.strftime("%A %b %-d (all day)")
        else:
            dtstart = _parse_dt(start)
            dtend = (_parse_dt(end) if end
                     else dtstart + datetime.timedelta(minutes=duration_minutes))
            kwargs["dtstart"] = dtstart
            kwargs["dtend"] = dtend
            when = dtstart.strftime("%A %b %-d at %H:%M")
        cal.save_event(**kwargs)
        return f"Created event {title!r} on the {cal.name} calendar, {when}."

    def reminders_read(self) -> str:
        lines = []
        for cal in self._todo_calendars():
            for todo in cal.todos():  # pending only, by default
                comp = todo.icalendar_component
                due = comp.get("DUE")
                due_txt = f" (due {_fmt_dt(due.dt)})" if due is not None else ""
                lines.append(f"{comp.get('SUMMARY', 'untitled')}{due_txt} [{cal.name}]")
        if not lines:
            return "No pending reminders."
        return "Pending reminders:\n" + "\n".join(lines[:30])

    def reminders_write(self, title: str, due: str | None = None,
                        list: str | None = None) -> str:
        cals = self._todo_calendars()
        target = cals[0]
        if list:
            want = list.strip().lower()
            for cal in cals:
                if want in (cal.name or "").lower():
                    target = cal
                    break
            else:
                names = ", ".join(repr(c.name) for c in cals)
                return f"No reminder list matching {list!r} (lists: {names})."
        kwargs: dict = {"summary": title}
        if due:
            kwargs["due"] = _parse_dt(due)
        target.save_todo(**kwargs)
        due_txt = f", due {kwargs['due'].strftime('%A %b %-d %H:%M')}" if due else ""
        return f"Added reminder {title!r} to {target.name}{due_txt}."


CALENDAR_READ_SCHEMA = {
    "type": "object",
    "properties": {
        "days": {
            "type": "integer",
            "description": "How many days ahead to look. Default 7.",
        },
        "start_date": {
            "type": "string",
            "description": "ISO date to start from, e.g. '2026-06-12'. "
                           "Omit for today.",
        },
        "calendar": {
            "type": "string",
            "description": "Limit to one calendar by name. Omit for all visible.",
        },
    },
    "required": [],
}

CALENDAR_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Event title."},
        "start": {
            "type": "string",
            "description": "ISO date-time, e.g. '2026-06-12T15:00'. For all-day "
                           "events an ISO date is enough.",
        },
        "end": {
            "type": "string",
            "description": "ISO date-time. Omit to use duration_minutes.",
        },
        "duration_minutes": {
            "type": "number",
            "description": "Length when 'end' is omitted. Default 60.",
        },
        "all_day": {"type": "boolean", "description": "All-day event."},
        "location": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["title", "start"],
}

REMINDERS_READ_SCHEMA = {"type": "object", "properties": {}, "required": []}

REMINDERS_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "The reminder text."},
        "due": {
            "type": "string",
            "description": "Optional ISO date-time the reminder is due.",
        },
        "list": {
            "type": "string",
            "description": "Reminder list name. Omit for the default list.",
        },
    },
    "required": ["title"],
}


# ── self-test: python -m integrations.caldav_icloud ──────────────────────────

def _selftest() -> int:
    import sys

    from core.config import load_config

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    svc = ICloudCalendarService(cfg)

    print("1) Connecting to iCloud CalDAV…")
    try:
        cals = svc.calendars()
    except RuntimeError as exc:
        print(f"   FAIL: {exc}")
        return 1
    print(f"   OK — {len(cals)} collections visible:")
    for cal in cals:
        comps = ",".join(cal.get_supported_components() or [])
        print(f"   - {cal.name!r} ({comps})")

    print(f"2) Looking for the family calendar "
          f"({cfg.get('family_calendar_name', 'Family')!r})…")
    try:
        family = svc.family_calendar()
    except RuntimeError as exc:
        print(f"   FAIL: {exc}")
        return 1
    print(f"   OK — {family.name!r}")

    print("3) Round-tripping a test event (create → read → delete)…")
    stamp = datetime.datetime.now().strftime("%H%M%S")
    title = f"Vato self-test {stamp} (safe to delete)"
    tomorrow_noon = (datetime.datetime.now(_local_tz()) +
                     datetime.timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    print("   " + svc.calendar_write(title, tomorrow_noon.isoformat()))
    listing = svc.calendar_read(days=3)
    if title not in listing:
        print("   FAIL: created event did not come back in calendar_read")
        return 1
    print("   OK — event visible via calendar_read")
    for ev in family.search(start=tomorrow_noon - datetime.timedelta(hours=1),
                            end=tomorrow_noon + datetime.timedelta(hours=2),
                            event=True):
        if str(ev.icalendar_component.get("SUMMARY", "")) == title:
            ev.delete()
            print("   OK — test event deleted")
            break

    print("4) Reminders (VTODO)…")
    try:
        print("   " + svc.reminders_read().splitlines()[0])
        print("   OK")
    except RuntimeError as exc:
        print(f"   note: {exc} (reminders optional; calendar still passes)")

    print("\nSelf-test passed — M3 calendar acceptance can run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
