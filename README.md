# Vato — Household Robot Butler

An always-on, voice-activated butler that lives on a TV screen. Full
specification: [VATO_SPEC.md](VATO_SPEC.md) — that document is the source of
truth for design decisions.

**Status: Milestone 2 (face v1).** All eight expressions including the 180°
working flip with the live engine-room ticker, kid effects ("party face!"),
and the weather-driven wardrobe (sunglasses, umbrella, frost…).

## How it works

```
"Hey Jarvis" (openWakeWord, local) → record until silence (RMS VAD)
  → transcribe locally (mlx-whisper) → Claude API with tools
  → macOS `say` (Daniel voice) → face animates in Chrome on the TV,
    mouth synced to the speech amplitude
```

While Claude runs a tool, the face flips 180° to its engine-room back panel
(gears, LEDs) and streams what it's doing in plain language on the ticker —
Tier 2/3 audit entries scroll there too. During quiet hours the idle face
sleeps (nightcap, z z z); the weather wardrobe re-checks the sky every 30
minutes.

### Audio & privacy disclosure (for the family)

Wake-word detection and speech transcription run **entirely on this machine**.
Raw audio never leaves the laptop. Only the **text transcript** of what you
say *after* the wake word is sent to the Claude API. The mute hotkey
(default ⌘⇧M) fully stops audio capture — the face shows X-eyes until
un-muted.

### Known limitation (Phase 0, by design)

The MacBook's internal mic will perform poorly across the room or over noise.
This is expected — do not judge the concept's viability on far-field
performance. Phase 1 swaps in a USB conference speakerphone.

## Setup

Requires an Apple Silicon Mac, Python 3.11+, and Google Chrome.

### 1. Install

```bash
cd vato
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Secrets → `.env`

```bash
cp .env.example .env
```

Fill in (the only key M1 needs):

- `ANTHROPIC_API_KEY` — https://platform.claude.com → API Keys

The wake word engine (openWakeWord) is fully local and needs no account or
key — see [manifest.md](manifest.md) for why this deviates from the spec.

### 3. Config → `config.yaml`

```bash
cp config.yaml.example config.yaml
```

At minimum set `location.name` (for weather). Everything else has sane
defaults.

**Wake word:** Vato answers to the pretrained phrase **"Hey Jarvis"** out of
the box. To get a real **"Vato"** wake word, train a custom model with
openWakeWord's free Colab notebook (no account needed — see
https://github.com/dscripka/openWakeWord) and point `wake.model` in
`config.yaml` at the downloaded `.onnx` file.

### 4. macOS permissions

- **Microphone** — macOS will prompt on first run; grant it to your terminal.
- **Input Monitoring** (for the mute hotkey) — System Settings → Privacy &
  Security → Input Monitoring → add your terminal app. Without it the
  daemon still runs; only the hotkey is disabled.

## Run

```bash
source .venv/bin/activate
python vatod.py
```

First run downloads the wake-word models (a few MB) and the Whisper model
(~500 MB for `whisper-small.en`) — give it a minute. When you see
`Voice loop ready`, it's listening.

**Put the face on the TV:** the daemon prints the kiosk command, e.g.

```bash
open -na "Google Chrome" --args --kiosk --app=http://127.0.0.1:8765
```

Drag that Chrome window to the TV display first (or open it there), then it
goes full-bleed — no chrome, no cursor. Exit kiosk mode with ⌘Q.

**Try it:**
- "Hey Jarvis, what's the weather?"
- "Hey Jarvis, what's the weather in Tokyo?"
- "Hey Jarvis, who wrote Pride and Prejudice?"
- ⌘⇧M to mute (X-eyes face, capture fully stopped), ⌘⇧M again to unmute.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Wake word never fires | Check mic permission; lower `wake.threshold` (e.g. 0.35); speak within ~2 m (Phase 0 limitation) |
| Random false wakes | Raise `wake.threshold` (e.g. 0.65) |
| Recording cuts off mid-sentence | Raise `vad.silence_duration` |
| Records forever / picks up noise | Raise `vad.silence_threshold` |
| Mute hotkey does nothing | Grant Input Monitoring (step 4), restart the daemon |
| `mlx-whisper` install fails | You're not on Apple Silicon; use `stt.engine: whisper_cpp` (`brew install whisper-cpp` + a ggml model) |

## Repo layout (spec §12)

```
core/          daemon, tool router + tiers, audit log, config
audio/         wake word, VAD, whisper, tts (Voice interface), mute
brain/         Claude client, butler system prompt
system/        SystemControl protocol + MacSystemControl (workspace jail)
integrations/  weather (Open-Meteo); caldav/telegram arrive in M3/M4
face/          web app (state machine) + reference images + effects/ (M2)
memory/        SQLite layer (M3)
audit/         append-only audit.log (gitignored)
```

## Milestones

- [x] **M1 — Voice loop**: wake → STT → Claude → TTS, face states, mute hotkey
      *(code-complete & component-verified; live end-to-end acceptance test
      still pending — needs `.env`/`config.yaml` filled in and a real
      "Hey Jarvis, what's the weather?" on the actual rig)*
- [x] **M2 — Face v1**: all expressions, 180° working flip + ticker, kid effects, weather wardrobe
      *(code-complete; every state/effect/wardrobe verified via screenshots.
      Voice-driven kid commands need API credits for the live acceptance run)*
- [ ] **M3 — Actions**: iCloud calendar (CalDAV), timers, lists, audit populating
- [ ] **M4 — Telegram**: family group chat, allowlist, Tier-3 confirm buttons
- [ ] **M5 — Security validation**: prompt-injection escalation, denylist, workspace jail
- [ ] **M6 — Games night**: trivia with scoreboard
