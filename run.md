# Running Vato (M1+M2) — quick reference

1. **Secrets** — `cp .env.example .env`, then fill in the one required key:
   - `ANTHROPIC_API_KEY` — from platform.claude.com
   - (No wake-word key needed — openWakeWord is local and account-free; see manifest.md)
2. **Config** — `cp config.yaml.example config.yaml`, set `location.name` to your city.
3. **STT for this Intel machine** — download a Whisper model and point the config at it:
   ```
   curl -L -o ~/ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
   ```
   then in `config.yaml`: `stt.engine: whisper_cpp` and `stt.whisper_cpp_model: ~/ggml-base.en.bin`.
   (On an Apple Silicon machine you'd skip this — the `mlx` default just works.)
4. **Run** — the venv is already set up with everything installed:
   ```
   source .venv/bin/activate && python vatod.py
   ```
   macOS will prompt for mic access on first run. For the mute hotkey (⌘⇧M), also grant your
   terminal Input Monitoring in Privacy & Security — without it everything else still works,
   only the hotkey is dead.
5. **Face on the TV** — the daemon prints the command:
   ```
   open -na "Google Chrome" --args --kiosk --app=http://127.0.0.1:8765
   ```
6. **Talk to it** — it answers to the pretrained phrase **"Hey Jarvis"**. Try
   "Hey Jarvis… what's the weather?" — face goes listening → thinking → talking while Daniel
   answers in character. For a real "Vato" wake word later: train a custom model with
   openWakeWord's free Colab notebook and set `wake.model` to the `.onnx` path.

## M2 acceptance walkthrough (Face v1)

Voice path (needs Anthropic API credits on the account):

- **Working flip + ticker**: "Hey Jarvis, what's the weather?" — the moment
  Claude calls the tool, the face flips 180° to the engine room; the ticker
  shows "Checking the weather for the household…"; it flips back and answers
  with the mouth synced to the speech amplitude.
- **Kid effects** (Tier 0, melt back after 5 min): "Hey Jarvis, party face!" ·
  "give me a mustache" · "heart eyes" · "spooky mode" · "silly face" ·
  "rainbow mode" · "make your face blue" · "back to normal".
- **Sleeping**: set `quiet_hours` in config.yaml to a window covering now;
  within a minute the idle face dims, lids droop, z z z, nightcap on.
- **Wardrobe**: automatic — re-checks the weather every 30 min
  (`wardrobe.refresh_minutes`). Sunny ≥ 75 °F → sunglasses; below freezing →
  frost creeping in + rosy cheeks; rain → umbrella + drops; snow → knit hat
  + snowflakes.

No-API test drive (click the face window first so it has keyboard focus):

- Keys **1–8** cycle idle / listening / thinking / talking / working /
  sleeping / muted / error.
- **e** cycles the kid effects (**E** clears) · **w** cycles wardrobe demos
  (**W** clears) · **t** pushes a sample ticker line.
- Or URL params: `http://127.0.0.1:8765/?demo=working` · `?effect=party` ·
  `?wardrobe=knit-hat,snow` · `?demo=sleeping&wardrobe=nightcap`
