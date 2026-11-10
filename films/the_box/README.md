# 🎬 THE BOX — a stickman silent film

> *Poora safar box kholne ka nahi tha. Poora safar khud ko improve karne ka tha.*

A complete, procedurally animated silent film (2:40, 720p24) — one stickman, one
box, and an emotional journey from curiosity to obsession, rage, defeat and
discovery. No dialogue, no AI APIs, no assets: every frame is drawn from code
and every note is synthesised.

**Watch:** [`out/the_box.mp4`](out/the_box.mp4) · **Screenplay:** [`screenplay.md`](screenplay.md)

---

## The 9 scenes

| # | Time | Scene | Camera |
|---|------|-------|--------|
| 1 | 0:00 | Empty World — 5 s of void, then a walk and a *THUK* | Extreme wide |
| 2 | 0:10 | The Box — touch, poke, lift, shake… and a glow | Medium |
| 3 | 0:20 | Curiosity — 4 attempts, 1 stubborn box, 1 fall | Close-up |
| 4 | 0:35 | Obsession — training montage, then the freeze | Montage |
| 5 | 1:00 | Anger — throw, hammer, stone, jump. Box: fine | Dynamic |
| 6 | 1:20 | Lowest Point — rain, stillness, 10 seconds of nothing | Wide |
| 7 | 1:40 | The Discovery — a glint on a tiny button. *CLICK* | Close-up |
| 8 | 2:00 | Inside — no treasure. A mirror | Top shot |
| 9 | 2:20 | Ending — smile, walk on, and the reveal | Slow pull-back |

## Files

| File | What it is |
|------|------------|
| `screenplay.md` | The full visual screenplay — second-by-second (camera / action / emotion / audience) |
| `engine.py` | Animation engine: camera, stickman rig, faces, box prop, rain, effects |
| `timeline.py` | The executable screenplay — all 9 scenes, every beat |
| `audio.py` | Original score + SFX + rain, synthesised with numpy |
| `render.py` | Frame renderer (multiprocess) + ffmpeg muxer |
| `serve.py` | Static server with Range support, for the screening page |
| `out/` | The film (`the_box.mp4`), `audio.wav`, screening page (`index.html`) |

## Re-render

```bash
python -m venv .venv && .venv/bin/pip install Pillow numpy imageio-ffmpeg

.venv/bin/python films/the_box/render.py            # full film (~1 min, 2 workers)
.venv/bin/python films/the_box/render.py --stills 8.5 27.3 91 125 157.5
.venv/bin/python films/the_box/serve.py 8000        # screening page → http://localhost:8000
```

Frames are cached in `~/.cache/box_frames` (kept out of git). Audio rebuilds in ~3 s.

## Production notes

- **1 character + 1 prop** — the whole film runs on a parametric stickman rig
  (joint angles + expression states) and a single box object.
- The **box never takes damage** — its indifference is the joke *and* the message.
- **Silence is structural**: the void (0–5 s), the comedic freeze (59.75 s), and
  the 2.5 s of *absolute zero* before the box opens (114.55 s).
- The **mirror reveal** is the theme: the box changed him on the journey, not at
  the destination. The final pull-back shows thousands of boxes — every one of
  them another journey.
