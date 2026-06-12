// Vato face client. The daemon pushes everything over the WebSocket; this
// file only renders. Reconnects forever so the TV can be left on Chrome
// kiosk mode unattended.

const STATES = ["idle", "listening", "thinking", "talking", "working",
                "sleeping", "muted", "error"];

// ── State machine ──────────────────────────────────────────────────────────

let mouthAnim = null; // requestAnimationFrame id for the talking envelope

function setState(state, mouth) {
  if (!STATES.includes(state)) state = "idle";
  document.body.classList.remove(...STATES.map((s) => `state-${s}`));
  document.body.classList.add(`state-${state}`);
  stopMouth();
  if (state === "talking") startMouth(mouth);
}

// Amplitude-driven mouth (spec §9): the daemon sends the TTS loudness
// envelope; we replay it in real time as scaleY on the jaw. Without an
// envelope, fall back to the simple open/close loop.
function startMouth(mouth) {
  if (!mouth || !mouth.envelope || !mouth.envelope.length) {
    document.body.classList.add("no-envelope");
    return;
  }
  document.body.classList.remove("no-envelope");
  const { envelope, interval } = mouth;
  const t0 = performance.now();
  const el = document.querySelector(".mouth");
  function frame(now) {
    const i = Math.floor((now - t0) / 1000 / interval);
    if (i >= envelope.length) {
      el.style.setProperty("--jaw", 1);
      return;
    }
    // closed mouth ≈ .35, fully open = 1
    el.style.setProperty("--jaw", (0.35 + 0.65 * envelope[i]).toFixed(3));
    mouthAnim = requestAnimationFrame(frame);
  }
  mouthAnim = requestAnimationFrame(frame);
}

function stopMouth() {
  if (mouthAnim) cancelAnimationFrame(mouthAnim);
  mouthAnim = null;
  document.body.classList.remove("no-envelope");
  document.querySelector(".mouth").style.removeProperty("--jaw");
}

// ── Kid effects (spec §9) ───────────────────────────────────────────────────

let effectClasses = [];
let effectTimer = null;
let effectParticles = null;
let baseColor = "#e8483f";

function clearEffect() {
  if (effectTimer) clearTimeout(effectTimer);
  effectTimer = null;
  document.body.classList.remove("color-cycle", ...effectClasses);
  effectClasses = [];
  effectParticles = null;
  document.documentElement.style.setProperty("--face-color", baseColor);
  syncParticles();
}

function applyEffect(effect) {
  clearEffect();
  if (!effect) return;
  effectClasses = effect.body_classes || [];
  document.body.classList.add(...effectClasses);
  if (effect.color_cycle) document.body.classList.add("color-cycle");
  if (effect.face_color) {
    document.documentElement.style.setProperty("--face-color", effect.face_color);
  }
  effectParticles = effect.particles || null;
  syncParticles();
  // melt back (default 5 minutes; server sends remaining time on reconnect)
  effectTimer = setTimeout(clearEffect, (effect.duration_s || 300) * 1000);
}

// ── Weather wardrobe (spec §9) ──────────────────────────────────────────────

let wardrobeClasses = [];
let wardrobeParticles = null;

function applyWardrobe(items) {
  document.body.classList.remove(...wardrobeClasses);
  wardrobeClasses = [];
  wardrobeParticles = null;
  for (const item of items || []) {
    if (item === "rain" || item === "snow") wardrobeParticles = item;
    else wardrobeClasses.push(`wear-${item}`);
  }
  document.body.classList.add(...wardrobeClasses);
  syncParticles();
}

// ── Particles (confetti / hearts / rain / snow) ─────────────────────────────

const PARTICLE_SPECS = {
  confetti: { every: 90,  make: confettiBit },
  hearts:   { every: 350, make: () => textBit("heart", "♥", 3.5) },
  snow:     { every: 220, make: () => textBit("snow", "❅", 4) },
  rain:     { every: 60,  make: dropBit },
};
let particleTimer = null;

function syncParticles() {
  // effect particles win over wardrobe ones (party in the rain stays party)
  const kind = effectParticles || wardrobeParticles;
  if (particleTimer) clearInterval(particleTimer);
  particleTimer = null;
  if (!kind || !PARTICLE_SPECS[kind]) return;
  const spec = PARTICLE_SPECS[kind];
  particleTimer = setInterval(() => spawn(spec.make()), spec.every);
}

function spawn(el) {
  const holder = document.getElementById("particles");
  el.style.left = Math.random() * 100 + "vw";
  el.style.animationDuration = el.dataset.dur;
  holder.appendChild(el);
  setTimeout(() => el.remove(), parseFloat(el.dataset.dur) * 1000 + 200);
}

function confettiBit() {
  const el = document.createElement("div");
  el.className = "particle confetti";
  el.style.background = `hsl(${Math.floor(Math.random() * 360)}, 90%, 60%)`;
  el.dataset.dur = (2.2 + Math.random() * 2) + "s";
  return el;
}

function textBit(cls, char, dur) {
  const el = document.createElement("div");
  el.className = `particle ${cls}`;
  el.textContent = char;
  el.dataset.dur = (dur + Math.random() * 2.5) + "s";
  return el;
}

function dropBit() {
  const el = document.createElement("div");
  el.className = "particle drop";
  el.dataset.dur = (0.7 + Math.random() * 0.4) + "s";
  return el;
}

// ── Info panel (spec §9, M6) ────────────────────────────────────────────────
// The face shrinks to its corner host position while content renders large.

let panelTimer = null;

function applyPanel(panel) {
  if (panelTimer) clearTimeout(panelTimer);
  panelTimer = null;
  if (!panel) {
    document.body.classList.remove("panel-on");
    return;
  }
  document.getElementById("panel-title").textContent = panel.title || "";
  const lines = document.getElementById("panel-lines");
  lines.replaceChildren();
  for (const text of panel.lines || []) {
    const line = document.createElement("div");
    line.className = "panel-line";
    line.textContent = text;
    lines.appendChild(line);
  }
  document.getElementById("panel-footer").textContent = panel.footer || "";
  document.body.classList.add("panel-on");
  // return to the full face after the timeout (server re-syncs on reconnect)
  panelTimer = setTimeout(() => applyPanel(null), (panel.duration_s || 180) * 1000);
}

// ── Back-panel ticker ───────────────────────────────────────────────────────

function tickerLine(text) {
  const ticker = document.getElementById("ticker");
  const line = document.createElement("div");
  line.className = "line";
  line.textContent = text;
  ticker.appendChild(line);
  while (ticker.children.length > 6) ticker.firstChild.remove();
}

// ── WebSocket ───────────────────────────────────────────────────────────────

let knownEffects = []; // registry, sent in the config message; used by test keys

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "config") {
      if (msg.face_color) {
        baseColor = msg.face_color;
        document.documentElement.style.setProperty("--face-color", baseColor);
      }
      knownEffects = msg.effects || [];
    } else if (msg.type === "state") {
      if (!qs.has("demo")) setState(msg.state, msg.mouth);
    } else if (msg.type === "effect") {
      if (!qs.has("effect")) applyEffect(msg.effect);
    } else if (msg.type === "wardrobe") {
      if (!qs.has("wardrobe")) applyWardrobe(msg.items);
    } else if (msg.type === "panel") {
      if (!qs.has("panel")) applyPanel(msg.panel);
    } else if (msg.type === "ticker") {
      tickerLine(msg.text);
    }
  };

  ws.onclose = () => setTimeout(connect, 1500);
  ws.onerror = () => ws.close();
}

connect();

// Idle blinks: slow, every 4-8 s (spec §9), skipped while muted/error/sleeping.
function scheduleBlink() {
  const delay = 4000 + Math.random() * 4000;
  setTimeout(() => {
    const cls = document.body.classList;
    if (!cls.contains("state-muted") && !cls.contains("state-error") &&
        !cls.contains("state-sleeping")) {
      cls.add("blink");
      setTimeout(() => cls.remove("blink"), 140);
    }
    scheduleBlink();
  }, delay);
}
scheduleBlink();

// ── Local test keys (no API needed; harmless on a kiosk TV with no keyboard)
//   1-8  cycle through the eight states
//   e    cycle kid effects (30 s each)   E  clear effect
//   w    cycle wardrobe demos            W  clear wardrobe
//   t    push a sample ticker line

const WARDROBE_DEMOS = [
  ["sunglasses"], ["frost"], ["umbrella", "rain"],
  ["knit-hat", "snow"], ["nightcap"], [],
];
let demoEffect = 0, demoWardrobe = 0;

document.addEventListener("keydown", (ev) => {
  const n = parseInt(ev.key, 10);
  if (n >= 1 && n <= STATES.length) setState(STATES[n - 1]);
  else if (ev.key === "e" && knownEffects.length) {
    applyEffect({ ...knownEffects[demoEffect++ % knownEffects.length], duration_s: 30 });
  } else if (ev.key === "E") clearEffect();
  else if (ev.key === "w") applyWardrobe(WARDROBE_DEMOS[demoWardrobe++ % WARDROBE_DEMOS.length]);
  else if (ev.key === "W") applyWardrobe([]);
  else if (ev.key === "t") tickerLine("Checking the weather for the household…");
  else if (ev.key === "p") applyPanel(DEMO_PANEL);
  else if (ev.key === "P") applyPanel(null);
});

const DEMO_PANEL = {
  title: "Family Trivia — Round 2",
  lines: [
    "Q4: Which planet has the most moons?",
    "A) Earth   B) Saturn   C) Mars",
    "",
    "★★★  Leo — 3",
    "★★   Maya — 2",
    "★    Dad — 1",
  ],
  footer: "Say your answer after the chime…",
  duration_s: 120,
};

// Same demos as URL params, e.g. /?demo=working&effect=party&wardrobe=knit-hat,snow
const qs = new URLSearchParams(location.search);
window.addEventListener("load", () => setTimeout(() => {
  // small delay so the demo look wins over the initial WS state sync
  if (qs.has("demo")) setState(qs.get("demo"));
  if (qs.has("panel")) applyPanel(DEMO_PANEL);
  if (qs.has("wardrobe")) applyWardrobe(qs.get("wardrobe").split(",").filter(Boolean));
  if (qs.has("effect")) {
    // effects arrive with the config message; retry briefly until they have
    const tryEffect = () => {
      const fx = knownEffects.find((e) => e.name === qs.get("effect"));
      if (fx) applyEffect({ ...fx, duration_s: 600 });
      else setTimeout(tryEffect, 200);
    };
    tryEffect();
  }
  if (qs.has("demo") && qs.get("demo") === "working") {
    ["Searching the web for dinosaur facts…",
     "Adding event to the family calendar…",
     "Checking the weather for the household…"].forEach(tickerLine);
  }
}, 600));
