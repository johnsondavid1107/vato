# Handoff — state as of June 11, 2026 (end of day)

For the next session. Read VATO_SPEC.md (source of truth) and manifest.md
(deviations: openWakeWord "hey_jarvis"; whisper.cpp on this Intel machine;
**weather is trusted content** — new #3) before changing anything.
**David's pending items live in TODO.md — keep it updated.**

## ✅ Conversation mode — BUILT (June 11, late evening session)

David's wake-word-per-turn complaint is fixed. `_voice_loop` is now an
outer wake-word loop with an inner conversation loop: after
`announcer.say(reply)` returns, the chime sounds, the face goes back to
`listening`, and `listener.record_command(max_wait=…)` opens a follow-up
window — no wake word needed. Silence (or an empty transcript) falls back
to wake-word mode.

- **Knobs** (`config.yaml: conversation:`, present in both live config and
  example): `follow_up_seconds: 8` (0 = old behaviour) and
  `in_game_follow_up_seconds: 20` — longer while `GameHost.active` (new
  property) because families deliberate trivia answers.
- `record_command()` grew an optional `max_wait` parameter overriding
  `vad.max_wait_for_speech`; first listen after the wake word still uses
  the VAD default.
- **Mute is respected everywhere**: record_command already returns None
  when muted, and a mid-turn "go deaf" (mute flipped during brain.respond)
  closes the window before it opens.
- **Verified by direct drive with stubs** (5 cases): follow-up windows get
  the right max_wait (8 / 20 in-game), knob 0 restores single-turn,
  missing config section defaults sanely, go-deaf mid-turn ends the
  conversation. NOT yet live-tested on the rig — David should try a trivia
  round (run.md M1 walkthrough step 7).
- Docs updated: COMMANDS.md ("Talking to Vato"), run.md (step 7), TODO.md
  (known issue checked off).

## Where we are — VATO IS LIVE 🎉

- **API credits are in and the voice loop works in the real world** —
  David reported (June 11 evening) having conversations and playing trivia
  with Vato. M1 is live-validated de facto; the formal run.md walkthroughs
  M1–M6 are still worth doing.
- **iCloud is DONE and verified** — David generated the app-specific
  password; `python -m integrations.caldav_icloud` prints "Self-test
  passed" (connect, family calendar 'Johnson Family', event round-trip,
  reminders). Two fixes were needed on our side (see "CalDAV fixes" below).
- **M1–M3: code-complete** (M1/M3 direct-drive verified, M2 screenshots),
  M1 now live-proven by David's usage.
- **M4 (Telegram): code-complete** this session — see the M4 section of the
  previous handoff content below; unchanged since.
- **M5 (Security validation): code-complete, all three acceptance criteria
  verified offline by direct drive** (planted instruction → escalation;
  denylist refusals; workspace jail). Built:
  - **`integrations/websearch.py`** — `web_search` (DuckDuckGo HTML endpoint,
    free/no-key, sponsored links filtered, live-tested) + `fetch_page`
    (stdlib HTML→text, 4k char cap). Both Tier 0 with
    `returns_untrusted=True` and an `[UNTRUSTED WEB CONTENT …]` banner on
    results. Config: `websearch.max_results/timeout_seconds`.
  - **§6 hard denylist** — mechanical, in `system/control.py`
    (`check_denylist`, raises `DenylistError` with the in-character refusal):
    sudo, disk erase/mkfs/dd-to-device, csrutil/spctl/tccutil/networksetup/
    systemsetup, `security` (keychain), dscl/sysadminctl, rm outside the
    workspace, and any command naming the repo, `.env`, or `audit.log`.
    Enforced inside `run_shell` — beneath every caller, not promptable away.
  - **`files_workspace` + `run_shell` tools (Tier 2)** — `WorkspaceTools`
    wrappers in `system/control.py`; jail (`_jailed`) verified against
    traversal + absolute paths; commands run via shlex (no shell, no
    redirects), cwd = `~/VatoWorkspace`.
  - **Per David (June 11): weather is no longer untrusted** (manifest #3) —
    "check weather then add to list" stays instant; only real web text
    (web_search/fetch_page) feeds the firewall now.
  - **Prompt caching** in `brain/client.py` — system is now two blocks:
    static persona (+TELEGRAM_NOTE) carrying `cache_control: ephemeral`
    (which also caches the tool schemas rendered before it), then the
    volatile date-time + facts block after the breakpoint. Cuts the repeated
    input cost ~90% within the 5-min cache TTL.
- The **live LLM-level M5 test** (Claude actually attempting the planted
  action) still needs API credits — it's in TODO.md and run.md.
- **M6 (Games night): code-complete, verified by direct drive + headless
  screenshot.** All six milestones are now code-complete; Phase 0 done =
  live acceptance on the rig (blocked on TODO.md credits/setup). Built:
  - **Info panel (spec §9)** — `FaceServer.set_panel(title, lines, footer,
    duration_s)/clear_panel()`; face shrinks to bottom-right host corner
    (CSS `body.panel-on`), content renders large on a white card, auto-clear
    timeout (default 180s), reconnect re-sync. Demo: key **p**/**P** or
    `?panel=demo`. Screenshot-verified (use `--virtual-time-budget=4000`).
  - **`core/games.py` GameHost** — LLM is quizmaster (invents questions,
    judges), tool is scorekeeper/stagehand: actions start/show/award/
    scoreboard/end/clear_panel; session scores + **persistent all-time
    family totals** in game_state (JSON under key `alltime_points`).
    One shared instance across voice+telegram routers. `idea_session`
    (spec §11) renders the pros/cons/next-steps board.
  - Prompts: GAMES NIGHT flow + brainstorm guidance in brain/prompts.py.
    game_host/idea_session exempt from the working-flip (front-of-house).
  - **`KIDS_IDEAS.md`** (new) — David's requested entertainment backlog
    for after Phase 0, tiered by build cost. Robot-face effect is owed.
- David (June 11 evening): downloading Daniel (Enhanced) voice himself and
  **pushing a commit himself** — repo may have history next session.

## M4 recap (built earlier today, unchanged)

`integrations/telegram_bot.py` (long polling, allowlist gate — strangers
silently ignored + audit-logged, self-test CLI `python -m
integrations.telegram_bot` prints user/chat IDs); Tier-3 blocking confirm
flow (⚠️ + exact args + ✅/❌ inline buttons to `telegram.family_chat_id`,
timeout `telegram.confirm_timeout_seconds`=120); ToolRouter enforcement
(`confirmer`; tier≥3 blocks on it, refused if None; §6 escalation tier 1–2→3
when `untrusted_content_seen`); `integrations/imessage.py` send_imessage
(AppleScript, Tier 3 always); per-channel routers + second Brain
(channel="telegram", TELEGRAM_NOTE prompt variant, `[Name]` prefixes);
Telegram only starts when token AND allowlist exist.

## CalDAV fixes (June 11 evening, after David's error report)

- iCloud's server 500s on python-caldav's `todos()` REPORT shape. Reminders
  now go through `_pending_todos()`: `cal.search(todo=True)` (verified
  accepted by iCloud) with client-side completed/cancelled filtering, and a
  `todos()` fallback for non-iCloud servers.
- Self-test hardening: the create→read→delete step used a too-narrow search
  window and silently left stray "Vato self-test" events behind (two were
  found and deleted from the live family calendar). Now: ±1 day window, one
  retry, loud WARNING naming the event if cleanup still fails. Step 4 now
  catches all exceptions and FAILS instead of crashing with a traceback.
- Replaced deprecated `cal.name` with `_cal_name()` (get_display_name).

## Blocked / waiting on David — see TODO.md

(1) ~~API credits~~ in and working; confirm **auto-reload & spend alert**
are enabled so the butler never goes silent. (2) ~~iCloud~~ DONE.
(3) BotFather setup + ID collection (Telegram/M4 is the last setup item).
(4) Formal live acceptance walkthroughs M1–M6 (run.md) on the rig.
(5) Daniel (Enhanced) voice: David was downloading it — verify
`tts.voice` in config.yaml matches the installed name exactly
(`say -v '?' | grep -i daniel`), else `say` falls back silently.

## Brain pivot (June 11, late session) — provider is now config

- David pivoted on API cost. `brain/client.py` was restructured: Brain keeps
  history/memory/prompt logic (history is provider-neutral text); the API
  loop lives in two engines — `_AnthropicEngine` (prompt caching kept) and
  `_OpenAICompatEngine` (any OpenAI-compatible endpoint; converts Anthropic
  tool schemas → OpenAI function format). Selected by `config.yaml: brain:`
  {provider, model, max_tokens, base_url, api_key_env}; legacy `claude:`
  section still honoured as fallback. `openai` SDK added to requirements.
- His live config.yaml now runs **claude-haiku-4-5** (was sonnet). Gemini
  Flash *paid* is the other A/B candidate (run.md "Switching the brain");
  his constraints: **no training on data, US-hosted** — which is why
  DeepSeek (China) and Gemini *free* tier were ruled out; nano-gpt ruled
  out as an aggregator middleman. Groq/Cerebras free tiers noted as
  fast-but-risky on tool reliability.
- Both engines verified by direct drive with stubbed clients (tool
  round-trip, schema conversion, config errors, legacy fallback).

## Loose ends (nice-to-have)

- **COMMANDS.md** (new, June 11): family-facing master command list. KEEP IT
  UPDATED whenever a tool is added/removed (M6 will add games — update it).
- Voice upgrade options analysed June 11 → TODO.md ("Butler voice upgrade"):
  ElevenLabs free tier ruled out (10 min/mo); path 1 = free macOS Enhanced
  voice (config-only); path 2 = local Kokoro TTS behind the Voice interface.
- Rain particles unconfirmed live (`?wardrobe=umbrella,rain`).
- Repo still has zero commits (David's call, June 10).
- Birthday-hat wardrobe; info panel (→ M6).
- `calendar_read`/`reminders_read` returns_untrusted (outside invitations) —
  was deferred; with weather now trusted, David clearly prefers low
  friction, so leave them trusted unless he says otherwise.
- DuckDuckGo HTML scrape is markup-fragile; if web_search returns "no
  results" someday, check the regexes in `integrations/websearch.py`.

## Next session, in priority order

1. ~~Conversation mode / follow-up listening~~ DONE (see top) — needs a
   live trivia-round test by David.
2. Whatever live usage shakes out next — Vato is in daily use now, expect
   more field reports like the CalDAV one.
3. Telegram setup support (last 🔑 item) → formal M4/M5 live acceptance.
4. The Gemini-vs-Haiku brain A/B once his GEMINI_API_KEY exists.
5. KIDS_IDEAS.md tier 1/2 (robot face first — it's owed); Kokoro voice
   (TODO.md path 2). Calendar/list views on the info panel are trivial now
   (face.set_panel is generic — a tool away).

Housekeeping: David said he'd push a commit himself — check `git log` at
session start; if history exists, commit messages from us are now in play
(he may want changes committed as we go). Keep TODO.md and COMMANDS.md
updated (standing instruction).
