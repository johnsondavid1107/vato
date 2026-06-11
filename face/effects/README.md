# Effects registry (spec §9 kid commands)

Each `.json` file here is one kid effect. The face server loads the whole
directory at startup, builds the `set_face_effect` tool enum from the file
names, and ships the definitions to the browser — so adding a new effect is
one small file, no code.

Fields (all optional except `name`):

| field | meaning |
|---|---|
| `name` | effect id — must match the filename |
| `description` | shown to Claude so it can map free-form kid phrasing |
| `body_classes` | CSS classes added to `<body>` (accessories/expressions live in face.css) |
| `face_color` | static palette override (CSS color) |
| `color_cycle` | `true` → hue-cycle the background |
| `particles` | `confetti` \| `hearts` \| `rain` \| `snow` |
| `duration_s` | how long before the face melts back (default 300 = 5 min) |

Two pseudo-effects are built in, not files: `face_color` (takes a `color`
argument — "make your face blue") and `clear` (melt back immediately).
