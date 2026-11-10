#!/usr/bin/env python3
"""THE BOX — frame renderer & muxer.

Usage:
    python films/the_box/render.py                 # full render + audio + mux
    python films/the_box/render.py --stills 7 22 88 157.4
    python films/the_box/render.py --no-audio      # silent video
    python films/the_box/render.py --start 0 --end 20   # partial render

Frames are written to a cache dir outside the repo (they are ~400 MB).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from films.the_box import timeline as TL          # noqa: E402
from films.the_box.engine import FPS, W, H         # noqa: E402

TOTAL = TL.TOTAL

FILM_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(FILM_DIR, "out")
DEFAULT_FRAMES = os.path.join(os.path.expanduser("~"), ".cache", "box_frames")


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def render_one(args):
    i, path = args
    img = TL.draw(i / FPS)
    img.save(path, "JPEG", quality=92)
    return i


def render_frames(frame_dir: str, start: int, end: int, workers: int):
    os.makedirs(frame_dir, exist_ok=True)
    jobs = [(i, os.path.join(frame_dir, f"f_{i:06d}.jpg"))
            for i in range(start, end)]
    t0 = time.time()
    done = 0
    with Pool(workers) as pool:
        for _ in pool.imap_unordered(render_one, jobs, chunksize=8):
            done += 1
            if done % 128 == 0 or done == len(jobs):
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (len(jobs) - done) / rate if rate else 0
                print(f"  {done}/{len(jobs)} frames  ({rate:.1f} fps, ETA {eta:.0f}s)",
                      flush=True)


def mux(frame_dir: str, out_mp4: str, audio: str | None, start: int):
    cmd = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error"]
    if start:
        cmd += ["-start_number", str(start)]
    cmd += ["-framerate", str(FPS), "-i", os.path.join(frame_dir, "f_%06d.jpg")]
    if audio and os.path.exists(audio):
        cmd += ["-i", audio]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p"]
    if audio and os.path.exists(audio):
        cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += ["-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description="Render THE BOX")
    ap.add_argument("--frames-dir", default=DEFAULT_FRAMES)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "the_box.mp4"))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--start", type=float, default=0.0, help="start time (s)")
    ap.add_argument("--end", type=float, default=TOTAL, help="end time (s)")
    ap.add_argument("--stills", nargs="*", type=float,
                    help="render given timestamps as PNGs and exit")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    if args.stills:
        os.makedirs(OUT_DIR, exist_ok=True)
        for t in args.stills:
            img = TL.draw(t)
            p = os.path.join(OUT_DIR, f"still_{t:06.2f}.png")
            img.save(p)
            print("wrote", p)
        return

    i0, i1 = int(args.start * FPS), min(int(round(args.end * FPS)), int(TOTAL * FPS))
    os.makedirs(OUT_DIR, exist_ok=True)
    audio = None if args.no_audio else os.path.join(OUT_DIR, "audio.wav")

    if audio and not os.path.exists(audio):
        print("building score…", flush=True)
        from films.the_box import audio as AU
        AU.main(audio)

    print(f"rendering frames {i0}–{i1} with {args.workers} workers…", flush=True)
    render_frames(args.frames_dir, i0, i1, args.workers)

    print("muxing…", flush=True)
    mux(args.frames_dir, args.out, audio, start=i0)
    size = os.path.getsize(args.out) / 1e6
    print(f"done → {args.out} ({size:.1f} MB)")

    if not args.keep_frames:
        for f in os.listdir(args.frames_dir):
            if f.startswith("f_") and f.endswith(".jpg"):
                os.remove(os.path.join(args.frames_dir, f))


if __name__ == "__main__":
    main()
