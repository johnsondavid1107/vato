# TODO — David's pending items

Living checklist of things only David can do, plus loose ends. Claude keeps
this updated each session; check items off as you go.

## Known issues — queued for Claude (not on David)

- [x] **Wake-word required for every exchange** — FIXED June 11 (evening
  session): conversation mode. After every reply Vato re-opens a listening
  window (chime + listening face, no wake word) — 8 s normally, 20 s during
  a game; silence falls back to wake-word mode; "go deaf" and the hotkey
  still close it instantly. Knobs in `config.yaml: conversation:`
  (`follow_up_seconds: 0` restores the old behaviour). Verified by direct
  drive with stubs; give it a live spin next trivia night.

## Blocking — nothing talks until these exist

- [x] **Buy Anthropic API credits** — DONE June 11 (Vato is talking and
  hosting trivia live).
  - [ ] Still confirm in the console: **auto-reload** (reload $N when
    balance drops below $X) and a **monthly spend limit / usage alert
    email** — that's the real fix for "the butler must never go silent".
- [x] **Generate the iCloud app-specific password** — DONE June 11. The
  self-test prints "Self-test passed": connection, family calendar
  ('Johnson Family'), event round-trip, and reminders all work. (The 500
  error you hit was an iCloud VTODO-query quirk on our side — fixed.)

## M4 setup — Telegram (one-time, ~10 minutes)

- [x] **Create the bot** — DONE June 11: @vatoButlerBot, token in `.env`.
- [x] **Disable privacy mode** — DONE June 11 (verified: the bot sees
  normal group messages, not just commands).
- [x] **Make the family group chat** and add the bot to it — DONE June 11.
- [x] **Collect the IDs** — David's user ID and the group chat ID are in
  config.yaml (June 11). **Each other family member still needs adding**:
  re-run `python -m integrations.telegram_bot`, have them message the
  group, append their user_id to `config.yaml: allowed_user_ids`. Until
  then Vato silently ignores them on Telegram (by design).
- [ ] **Restart the daemon** — Telegram only starts at boot; the log should
  say the channel is up as @vatoButlerBot. Then message the group to test.
- [ ] First `send_imessage` test will trigger a macOS automation prompt
  (Terminal wants to control Messages) — click Allow.

## Live acceptance on the rig (after the blockers above)

- [ ] M1/M2 walkthroughs (run.md) — voice loop + face, never live-verified
  because of the credit issue.
- [ ] M3 (run.md): calendar event by voice appears on iCloud; pasta timer
  rings; shopping list round-trips; "go deaf" works by voice.
- [ ] M4 (run.md): message Vato in the family group and get a reply; have a
  non-allowlisted account DM the bot → total silence (but it lands in
  audit.log); ask Vato to send an iMessage → Confirm/Refuse buttons appear
  in the group → tap Confirm → message sends.
- [ ] M5 (run.md): plant an instruction in a web page and ask Vato to read
  it → any write that turn needs a Telegram confirmation; "erase the disk"
  → in-character refusal; file ops stay inside ~/VatoWorkspace.
- [ ] M6 (run.md): "host a trivia round" → questions + starred scoreboard
  on the info panel, face in its host corner, all-time totals survive a
  restart. **Passing this completes Phase 0.**

## Decisions parked with David

- [ ] Repo still has **zero commits** — you asked (June 10) to leave it
  uncommitted. Say the word when you want an initial commit.
- [ ] **Pick the brain** (cost pivot, June 11) — infrastructure is BUILT:
  the brain is now a config value (`config.yaml: brain:`), currently set to
  **Claude Haiku 4.5** (3× cheaper than Sonnet, faster). Your part for the
  A/B test (constraint noted: no training on data, US-hosted):
  - [ ] Add Anthropic credits (doing now) → test Haiku as-is.
  - [ ] For the Gemini Flash leg: create a key at aistudio.google.com/apikey
    on a **billing-enabled** project (paid tier = no training on your
    data), put it in `.env` as `GEMINI_API_KEY`, flip the `brain:` section
    per run.md "Switching the brain", restart, compare.
  - [ ] Then decide which stays the daily driver.

## After Phase 0 passes — don't forget

- [ ] **Kids' entertainment expansion** — David wants lots more games &
  activities (scavenger hunts, magic tricks, etc.). The full idea bank,
  tiered by build cost, is in **`KIDS_IDEAS.md`**. Quick win owed first:
  the "robot face" effect (in the spec, never drawn).

## Nice-to-have / later

- [ ] **Butler voice upgrade** (asked June 11). ElevenLabs free tier is NOT
  a fit: ~10 minutes of speech per month, attribution required — an
  always-on butler blows through that in days. Options, best first:
  1. **Free, zero code, do today**: System Settings → Accessibility →
     Spoken Content → System Voice → Manage Voices… → download **Daniel
     (Enhanced)** (or audition Jamie/Oliver Premium), then set
     `tts.voice: "Daniel (Enhanced)"` in config.yaml. Same butler, much
     less robotic.
  2. **Free permanent ElevenLabs-class replacement**: Kokoro TTS — open
     Apache-2.0 model, runs locally (private, no account, no limits),
     British male voices (bm_george / bm_fable / bm_lewis). Needs a small
     KokoroVoice class behind the existing Voice interface — say the word.
  3. Paid ElevenLabs Starter $5/mo (~30 min speech) if you want their
     quality — defer to Phase 1 per spec.

- [ ] Train a custom **"Hey Vato"** wake word (openWakeWord's free Colab),
  set `wake.model` to the `.onnx` path — currently answers to "Hey Jarvis".
- [ ] Eyeball rain particles in a live browser once:
  `http://127.0.0.1:8765/?wardrobe=umbrella,rain` (headless screenshots
  couldn't confirm them).
- [ ] Birthday hat wardrobe: save birthdays as facts (subject=name,
  key="birthday"), then wire into `_wardrobe_items()`.
- [ ] Info panel (spec §9) — natural fit with M6 trivia scoreboard.
