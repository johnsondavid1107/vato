# Handoff — state as of June 10, 2026

For the next session. Read VATO_SPEC.md (source of truth) and manifest.md
(intentional deviations: openWakeWord "hey_jarvis" instead of Porcupine;
whisper.cpp on this Intel dev machine) before changing anything.

## Where we are

- **M1 (voice loop): code-complete.** The "errors" David hit in the live
  acceptance test were Anthropic API 400s — *"credit balance is too low"*,
  i.e. billing, not bugs. Wake → record → STT all worked in his log.
- **M2 (Face v1): code-complete and screenshot-verified this session.**
  All 8 expressions (incl. 180° working flip with live engine-room ticker
  and quiet-hours sleeping), amplitude-synced talking mouth, 6 kid effects
  via the Tier-0 `set_face_effect` tool, weather wardrobe on a 30-min
  schedule. Verification details and a no-API test drive are in run.md
  ("M2 acceptance walkthrough").
- **M3–M6: not started.**

## Blocked / waiting on David

1. **Buy API credits** (platform.claude.com → Plans & Billing). Until then
   no Claude call succeeds, so the live acceptance runs for M1 *and* M2's
   voice path (kid commands, working flip on a real question) are pending.
2. **Run the live acceptance on the rig** once credits exist:
   "Hey Jarvis, what's the weather?" (flip + ticker + synced mouth) and
   "Hey Jarvis, party face!" (effect + 5-min melt-back).
3. Optional: train a custom **"Hey Vato"** wake word (openWakeWord Colab,
   free), set `wake.model` to the `.onnx` path.

## Small loose ends (nice-to-have, not blocking)

- Rain particles couldn't be confirmed in headless screenshots (virtual-time
  artifact; same code path as snow, which renders). Eyeball once in a live
  browser: `http://127.0.0.1:8765/?wardrobe=umbrella,rain`.
- "Vato, go deaf" voice-mute command (spec §6) — only the ⌘⇧M hotkey exists.
  Natural to add as a Tier-0 tool when wiring more tools in M3.
- The repo has **no git commits yet** — everything is untracked. Worth an
  initial commit (`.env`, `config.yaml`, `audit/` are already gitignored —
  verify before committing).
- Date-aware wardrobe bonuses (birthday hat) need the M3 memory layer; the
  info panel (spec §9) belongs with M3/M6 content.

## Next up: M3 — Actions (spec §13)

Acceptance: a calendar event created by voice appears on the iCloud family
calendar; timers and lists work; audit log populating.

- **CalDAV/iCloud** (spec §8): `caldav` lib, app-specific password in `.env`
  (needs David to generate one at appleid.apple.com), shared calendar from
  `config.yaml: family_calendar_name`. Tools: `calendar_read` (Tier 0),
  `calendar_write` (Tier 1). Reminders via VTODO.
- **SQLite memory layer** (spec §10): `memory/` is an empty package — schema
  for facts, conversation_log, preferences, lists, game_state. Tools:
  `lists` (Tier 1), `memory_save_fact` / `memory_lookup` (Tier 1/0).
- **Timers/announcements**: APScheduler (in requirements? check), `timer_set`
  / `timer_cancel` / `announce_at` (Tier 1) — spoken alert + face cue.
- Plumbing already in place to reuse: tool tiers + audit in
  `core/tools.py` (set `ticker_line` per tool for the back panel),
  `returns_untrusted` flag for the §6 firewall, `face.ticker()` /
  `face.set_state("working")` happen automatically via the daemon's
  `on_tool` hook in `core/daemon.py`.

## M2 code map (what changed this session)

- `face/effects/*.json` — one file per kid effect; loaded by
  `face/server.py: load_effects()`, enum + descriptions feed the tool.
- `face/server.py` — effects/wardrobe/ticker/quiet-hours/mouth-envelope
  broadcast; full state replay to reconnecting kiosks.
- `face/static/` — flip card (front face / back panel), all CSS states,
  accessories (SVG in index.html), particles, test keys + `?demo=` params.
- `audio/tts.py` — renders to WAV, computes RMS envelope, `on_start`
  callback before `afplay` (Voice protocol changed accordingly).
- `core/daemon.py` — `_ambient_loop` (quiet hours + wardrobe),
  `_wardrobe_items()` mapping, `on_tool` → flip+ticker, effect tool
  registration.
- `integrations/weather.py` — `current_conditions()` (°C/code/is_day) +
  code groups RAIN/SNOW/CLEAR_CODES.
- `core/audit.py: on_record` → Tier≥2 entries hit the ticker.
- `brain/client.py` — `on_tool` callback; `brain/prompts.py` — kid-command
  guidance.
