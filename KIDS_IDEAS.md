# Kids' Entertainment Roadmap — ideas backlog

David's ask (June 11, 2026): a bank of fun things kids can do with Vato,
to build **after the initial milestones (M1–M6) pass live acceptance**.
Nothing here is committed work — it's the menu to pick from. Most of these
ride on machinery that already exists (game_host + info panel + scoreboard,
kid effects registry, timers/announcer, memory facts), so unit costs are
small once M6 is proven.

**Constraints to respect when building any of these** (spec §14): no camera,
no speaker recognition (Vato can't *see* or tell kids apart by voice — kids
say their own names), music playback is Phase 2 (Spotify).

## Tier 1 — almost free (game_host + prompts already do 90%)

- **Riddle of the Day** — kid asks for a riddle; answer revealed on the info
  panel upside-down-style (last line) after they guess. Streaks tracked in
  game_state.
- **Would You Rather** — Vato asks outrageous-but-wholesome either/ors,
  tallies family votes on the scoreboard.
- **Rhyme Time / Word Chain / Categories** — already in the word-games
  umbrella; add per-game prompt patter and personal bests.
- **Tongue-Twister Challenge** — Vato invents one, kid repeats it three
  times fast, Vato judges generously. Difficulty levels.
- **Times-Tables Trainer / Spelling Bee** — parent saves the week's words or
  tables as memory facts; Vato quizzes, keeps personal bests in game_state,
  celebrates improvement (not just high scores).
- **Two Truths and a Lie** — Vato plays too (butler trivia about itself).
- **Kim's Memory Game** — panel shows 8 items for 20 seconds, then hides;
  kids recall them. Uses the panel timeout natively.
- **Jokes Hour / Knock-Knock Battles** — alternating jokes, family laughs
  decide the winner; Vato's are dry and butler-grade.

## Tier 2 — small new mechanics (a tool action or an effect file)

- **Search & Find (scavenger hunt)** — David's idea. Vato generates a list
  of household-findable items ("something older than Dad", "something
  blue that isn't clothing"), renders it on the panel with checkboxes,
  kids report finds by voice, Vato checks them off and runs a countdown
  timer. Needs: a `hunt` action that re-renders the list with ✓s + a timer
  tie-in (both mechanics exist).
- **Treasure Hunt with Clues** — Vato invents riddle-clues leading
  room-to-room to a parent-hidden prize. Parent whispers the hiding spot to
  Vato via Telegram (so kids can't overhear!) — fun use of the two channels.
- **Magic Tricks** — David's idea. Math-magic mind reading ("think of a
  number, double it…"), card-trick variants done verbally, "I predict…"
  with the prediction sealed on the Telegram channel beforehand and
  revealed on the panel after. Needs: a magician face effect (top hat +
  wand, one JSON file) and a `sealed prediction` gimmick via game_state.
- **Hide & Seek Referee** — Vato covers his ears (muted face!), counts down
  20 out loud, calls "ready or not, here they come!", then times the round.
- **Vato Says** (Simon Says) — face acts the commands too (blink, look
  left, party hat on) so kids copy the TV. Needs: a few one-shot face cues.
- **Fortune Teller Mode** — crystal-ball face effect + silly gracious
  fortunes ("I foresee… an unmade bed in your future, madam").
- **Staring Contest** — face goes unblinking wide-eyed (suppress the blink
  loop — one CSS class); first kid to laugh loses, honor system.
- **Robot face** — already in the spec's kid-command list but never drawn;
  one effect JSON + CSS. Do this one first, it's owed.

## Tier 3 — bigger builds (worth it if games night lands)

- **Choose-Your-Own-Adventure Story Mode** — branching bedtime stories
  starring the kids (names from memory facts), choices shown on the panel
  ("A: open the door / B: follow the cat"), chapter state in game_state so
  a story can continue tomorrow night. Quiet-hours aware: dims toward the
  sleeping face as the story winds down.
- **Mad Libs** — Vato collects words by voice ("give me a verb… a silly
  animal…"), reads the absurd result theatrically, full text on the panel.
- **Drawing Prompts + Gallery Judging** — "draw a dragon eating spaghetti —
  five minutes!" (timer), then kids hold drawings up and Vato awards
  whimsical category prizes ("Most Suspicious Use of Purple"). No camera —
  Vato judges by asking each artist to describe theirs (funnier anyway).
- **Daily Surprise** — a parent-scheduled announcement slot where Vato does
  one random bit at, say, 4pm: joke, fun fact, 60-second dance-party face,
  mini-riddle. Uses announce_at + a "surprise roulette" prompt.
- **Birthday Show** — birthday hat wardrobe (already unblocked) + a sung
  (well, recited — TTS) ode + party face + a this-day-in-history fact.
- **Phase 2 tie-ins** (need Spotify/Home Assistant): freeze dance (music
  stops at random), dance party mode with lights, karaoke night scoreboard.

## Notes for whoever builds these

- The pattern is always: **LLM is the entertainer, tools are props.**
  Resist building game logic into Python — game_host's generic
  show/award/end covers most of these; add new actions sparingly.
- New face effects are one JSON file each (face/effects/README.md).
- Persistent leaderboards/bests: game_state key per game, JSON values.
- Anything that needs Vato to *initiate* must go through scheduled
  announcements (proactivity policy, spec §10 — no unprompted chatter).
- Update COMMANDS.md as each ships.
