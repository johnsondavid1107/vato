# TODO — David's pending items

Living checklist of things only David can do, plus loose ends. Claude keeps
this updated each session; check items off as you go.

## Blocking — nothing talks until these exist

- [ ] **Buy Anthropic API credits** — platform.claude.com → Plans & Billing.
  Every live test of M1–M5 fails with a 400 "credit balance is too low"
  until then. (Pending since the June 10 session.)
  - While you're there: turn on **auto-reload** (reload $N when balance
    drops below $X) and a **monthly spend limit / usage alert email** —
    that's the real fix for "the butler must never go silent". Typical
    household usage on Sonnet is rough cents per interaction (estimate in
    the June 11 session notes); $25–50/month of credits should be plenty
    to start.
- [ ] **Generate the iCloud app-specific password** — appleid.apple.com →
  Sign-In & Security → App-Specific Passwords (NOT your Apple ID password).
  Put it in `.env` (`ICLOUD_USERNAME` / `ICLOUD_APP_PASSWORD`), check
  `family_calendar_name` in config.yaml matches the shared calendar, then
  verify: `python -m integrations.caldav_icloud` → must print "Self-test
  passed".

## M4 setup — Telegram (one-time, ~10 minutes)

- [ ] **Create the bot**: message @BotFather on Telegram → `/newbot` → copy
  the token into `.env` as `TELEGRAM_BOT_TOKEN`.
- [ ] **Disable privacy mode** so the bot sees normal group messages (not
  just commands): @BotFather → `/setprivacy` → your bot → **Disable**.
- [ ] **Make the family group chat** and add the bot to it.
- [ ] **Collect the IDs**: run `python -m integrations.telegram_bot` — it
  prints the user ID and chat ID of every message it sees. Have each family
  member send a message in the group; copy the user IDs into
  `config.yaml: allowed_user_ids` and the group's chat ID into
  `telegram.family_chat_id`.
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
