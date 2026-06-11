# Manifest — deviations from VATO_SPEC.md

Short log of where the build intentionally differs from the spec, so future
sessions aren't confused. VATO_SPEC.md remains the source of truth for
everything not listed here.

## 1. Wake word: Porcupine → openWakeWord (June 2026)

- **Spec said:** Picovoice Porcupine with a custom "Hey Vato" keyword (§3).
- **Now:** openWakeWord with the pretrained **"Hey Jarvis"** model
  (`wake.model: hey_jarvis` in config.yaml).
- **Why:** Picovoice Console signup requires a company email; David doesn't
  have one. openWakeWord needs no account/key at all, and the spec's Phase 2
  already planned to switch to it for a custom "Vato" model — we adopted the
  Phase 2 engine early.
- **Knock-ons:** `PICOVOICE_ACCESS_KEY` removed from `.env`. Mic capture
  still uses `pvrecorder` (free Picovoice lib, no key needed). Custom wake
  phrase path: train "Hey Vato"/"Vato" via openWakeWord's Colab notebook,
  set `wake.model` to the `.onnx` path.

## 2. STT on this machine: whisper.cpp, not mlx-whisper (June 2026)

- **Spec said:** Phase 0 hardware is an Apple Silicon MacBook; STT via
  mlx-whisper with whisper.cpp fallback (§2, §3).
- **Now:** This dev machine is an **Intel Mac** (x86_64), so mlx can't
  install. `requirements.txt` guards mlx-whisper behind
  `platform_machine == "arm64"`; on this machine use
  `stt.engine: whisper_cpp` (whisper-cli is installed via brew).
- **Why:** Hardware reality; the spec's own fallback covers it. On an Apple
  Silicon machine the mlx default works unchanged.

## 3. Weather is trusted content — not behind the §6 firewall (June 2026)

- **Spec said:** all content fetched from the web is untrusted data (§6), and
  `get_weather` is a fetch.
- **Now:** `get_weather` does NOT set `returns_untrusted`, so a weather check
  followed by a household write in the same turn stays instant (Tier 1)
  instead of escalating to a Telegram confirmation.
- **Why:** David's call after feeling the friction ("check the weather and if
  it'll rain add X to the list" demanded a phone tap). Open-Meteo returns
  structured numbers from a fixed API, not attacker-controlled prose — the
  injection surface the firewall exists for. Free-text web content
  (`web_search`, `fetch_page`) remains untrusted and still escalates.
