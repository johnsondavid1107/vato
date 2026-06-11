# Handoff — state as of June 11, 2026 (second session)

For the next session. Read VATO_SPEC.md (source of truth) and manifest.md
(deviations: openWakeWord "hey_jarvis"; whisper.cpp on this Intel machine;
**weather is trusted content** — new #3) before changing anything.
**David's pending items live in TODO.md — keep it updated.**

## Where we are

- **M1–M3: code-complete** (M1/M3 direct-drive verified, M2 screenshots).
  Still never live-verified — David hasn't bought API credits or generated
  the iCloud app-specific password (TODO.md).
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

## Blocked / waiting on David — see TODO.md

(1) API credits + **auto-reload & spend alert** (his June 11 question — the
answer: auto-reload is the real guard against the butler going silent),
(2) iCloud app-specific password + caldav self-test, (3) BotFather setup +
ID collection, (4) live acceptance M1–M5 on the rig.

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

## Next up: M6 — Games night (spec §11 game_host, §13)

Acceptance: Vato hosts a full trivia round with scoreboard, in character.

- `game_host` tool (Tier 0): trivia w/ persistent scores in `game_state`
  (table already exists in memory/store.py), 20 questions, word games,
  story mode.
- **Info panel** (spec §9): face shrinks to corner "host" position, content
  renders large, returns after timeout or "thanks, Vato" — natural co-build
  with the trivia scoreboard. Face server: `face/server.py`, UI in
  `face/index.html`/`face.js`.
- `idea_session` tool (Tier 0, spec §11) is the last unbuilt v1 tool besides
  game_host — could fold into M6 session.
- After M6: Phase 0 definition of done = all six milestones pass **live**
  on the MacBook + garage TV rig (blocked on TODO.md items).
