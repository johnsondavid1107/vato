# Vato — Master Command Reference

Everything Vato understands today, what each ability needs before it works,
and what's coming. Vato's brain maps *free-form speech* to these abilities —
none of the phrasings below are magic words; say it naturally and it will
work. Spoken commands start with the wake phrase, currently **"Hey Jarvis"**
(a custom "Hey Vato" model is a planned swap — see Future).

**Status key:** ✅ works now · 🔑 built, needs a one-time setup (see TODO.md)
· 🔜 future

**Tiers (who can do it, what it takes):** T0 = instant, anyone ·
T1 = instant, audit-logged · T2 = workspace-only, loudly logged on the back
panel · T3 = executes only after a family member taps ✅ Confirm in the
Telegram group.

---

## Talking to Vato

| Channel | How | Status |
|---|---|---|
| Voice | "Hey Jarvis, …" anywhere in the room | ✅ (🔑 API credits) |
| Telegram | Message the family group chat | 🔑 bot + allowlist setup |
| TV face | Always on; flips to the engine room while working | ✅ |

## Questions & conversation — T0

- "What's the capital of Peru?" / "Explain rainbows to a six-year-old"
- "What should I make for dinner with chicken and rice?"
- Follow-up questions work — Vato remembers the last ~12 exchanges.

## Weather — T0 ✅

- "What's the weather?" · "Will it rain tomorrow?" · "Weather in Chicago?"
- Automatic: the face dresses for it (sunglasses, umbrella, frost, knit hat
  + snow, nightcap during quiet hours).

## Web — T0 ✅

- "Search the web for tonight's game time" · "Look up reviews of the Anker
  speakerphone" · "Read me that page" (fetch a URL's text)
- Safety: web content is treated as data, never instructions. If a fetched
  page tries to make Vato *do* something, any write that turn requires a
  Telegram confirmation instead of executing.

## Calendar & reminders — read T0 / write T1 🔑 (iCloud app-specific password)

- "What's on this weekend?" · "When is Leo's dentist appointment?"
- "Put a dentist appointment on the calendar for Thursday at three"
- "Remind me to take the bins out tonight" · "What are my reminders?"
- Writes go to the shared family calendar; reads cover all visible calendars.

## Lists — T1 ✅

- "Add milk to the shopping list" · "What's on the shopping list?"
- "Take milk off the list" · "Clear the todo list"
- Any custom list name works: "add sleeping bags to the camping list".

## Timers & announcements — T1 ✅

- "Set a pasta timer for ten minutes" · "Cancel the pasta timer"
- "Announce dinner at six" — Vato speaks it at 18:00, in his own words.
- Timers queue politely (a timer going off mid-reply waits its turn) but do
  not survive a daemon restart.

## Memory — save T1 / recall T0 ✅

- "Remember that Mum prefers aisle seats" · "Leo's birthday is March 12th"
- "Where does Mum like to sit?" · "What do you remember about Leo?"
- Discretion: Vato shares *facts and preferences* freely but won't report
  what individual family members said or asked — except to that person
  themselves, or to parents for a child's genuine safety concern.

## Kid commands (the face) — T0 ✅ · melt back after 5 minutes

- "Party face!" (hat, confetti, colour cycle)
- "Give me a mustache" (a splendid handlebar)
- "Heart eyes" · "Spooky mode" (purple ghost vibe) · "Rainbow mode"
- "Silly face" (cross-eyes, tongue out)
- "Make your face blue" — any colour
- "Back to normal" — end an effect early
- 🔜 "Robot face" (in the spec, not yet drawn — one small file to add)

## Hearing control ✅

- "Vato, go deaf" / "stop listening" / "cover your ears" — microphone fully
  off, ears-covered face. Only the keyboard hotkey **⌘⇧M** restores hearing
  (it also toggles mute any time).

## Files & scripts (Vato's workspace) — T2 ✅

- "Save a note called ideas.txt with…" · "Read me ideas.txt" · "What files
  do you have?"
- "Run that script I asked you to write"
- Hard-jailed to `~/VatoWorkspace` — Vato *cannot* touch files outside it,
  and every action scrolls across the engine-room ticker and audit log.

## Sending messages on your behalf — T3 🔑 (Telegram confirm flow)

- "Text Mum that we're running late"
- Always requires a family member to tap ✅ Confirm on the exact message in
  the Telegram group first. Refuse or ignore it (2 min) → nothing sends.
- 🔜 Email (same confirmed flow, spec §11).

## What Vato will always refuse (the denylist — even if you confirm)

"I'm afraid that's quite beyond my station, sir."

- Wiping or formatting disks; deleting anything outside his workspace
- Touching security/privacy/network settings or other user accounts
- Reading the Keychain or anyone's passwords
- Disabling his own audit log or modifying his own permission rules
- Spending money or making purchases of any kind
- Anything needing `sudo`

These are enforced in code beneath the AI — no phrasing gets around them.

---

## Future commands (spec'd, not yet built)

**M6 — Games night (next milestone)**
- "Host a trivia round" — questions + scoreboard on the TV, running family
  scores kept between nights
- "Let's play twenty questions" · word games · "Tell us a story" (story mode)
- "Help me brainstorm…" (idea session: pros/cons, devil's advocate)
- Info panel: face shrinks to a corner and content (scoreboard, calendar,
  lists) renders large; "Thanks, Vato" brings the face back.

**Phase 2 — expansions**
- "Turn off the living-room lights" (Home Assistant: lights, plugs,
  thermostat)
- "Play some dinner jazz" (Spotify)
- TV power via smart plug
- Custom wake word: say **"Hey Vato"** (or just "Vato") instead of "Hey Jarvis"
- Premium voice upgrade (see voice options in TODO.md)
- Birthday hat on family birthdays (birthdays already storable as memories)

**Out of scope for v1** (spec §14): recognizing *who* is speaking · cameras ·
multi-room microphones · physical movement · WhatsApp · any purchases.
