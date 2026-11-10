"""THE BOX — score & sound design.

A soft piano/music-box score, rain ambience and minimal SFX for a silent film.
Everything is synthesised with numpy — no samples, no API keys.
Output: out/audio.wav (44.1 kHz stereo, 160 s)
"""
from __future__ import annotations

import math
import wave

import numpy as np

SR = 44100
DUR = 160.0
N = int(SR * DUR)

# note names → frequency (A4 = 440)
_STEPS = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def f(name: str) -> float:
    """'A3' / 'C#5' → frequency."""
    step = _STEPS[name[0]]
    i = 1
    if len(name) > 1 and name[1] in "#b":
        step += 1 if name[1] == "#" else -1
        i = 2
    octave = int(name[i:])
    return 440.0 * 2 ** ((step + (octave - 4) * 12) / 12)


class Score:
    def __init__(self):
        self.music = np.zeros(N)
        self.sfx = np.zeros(N)
        self.rain = np.zeros(N)

    # -- primitives ------------------------------------------------------
    def _add(self, buf, t0, sig, amp=1.0):
        i0 = int(t0 * SR)
        if i0 >= N or i0 < -len(sig):
            return
        j0 = max(0, i0)
        s0 = j0 - i0
        i1 = min(N, i0 + len(sig))
        buf[j0:i1] += sig[s0:s0 + (i1 - j0)] * amp

    def piano(self, t0, freq, dur=1.6, amp=0.5, bright=1.0):
        n = int(dur * SR)
        t = np.arange(n) / SR
        sig = np.zeros(n)
        for h, w in ((1, 1.0), (2, 0.42 * bright), (3, 0.20 * bright),
                     (4, 0.10 * bright), (6, 0.05 * bright)):
            decay = np.exp(-t * (1.6 + h * 0.55))
            sig += w * decay * np.sin(2 * np.pi * freq * h * t +
                                      0.13 * h * np.sin(2 * np.pi * 5.2 * t))
        atk = np.minimum(1.0, t / 0.008)
        self._add(self.music, t0, sig * atk, amp * 0.21)

    def pluck(self, t0, freq, dur=0.9, amp=0.5):
        n = int(dur * SR)
        t = np.arange(n) / SR
        sig = np.zeros(n)
        for h, w in ((1, 1.0), (2, 0.5), (3, 0.32), (4, 0.18), (5, 0.10),
                     (6, 0.06)):
            sig += w * np.exp(-t * (3.2 + h * 1.1)) * np.sin(2 * np.pi * freq * h * t)
        atk = np.minimum(1.0, t / 0.004)
        self._add(self.music, t0, sig * atk, amp * 0.17)

    def bell(self, t0, freq, dur=1.8, amp=0.5):
        n = int(dur * SR)
        t = np.arange(n) / SR
        sig = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 2.2) +
               0.5 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 3.4) +
               0.28 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t * 4.6))
        atk = np.minimum(1.0, t / 0.003)
        self._add(self.music, t0, sig * atk, amp * 0.145)

    def pad(self, t0, freqs, dur=4.0, amp=0.5, attack=0.9):
        n = int(dur * SR)
        t = np.arange(n) / SR
        sig = np.zeros(n)
        for fr in freqs:
            for h, w in ((1, 1.0), (2, 0.34), (3, 0.16), (4, 0.08)):
                det = 1 + 0.0007 * ((h * fr) % 3 - 1)
                sig += w * np.sin(2 * np.pi * fr * h * det * t +
                                  0.9 * np.sin(2 * np.pi * 0.23 * t + fr))
        env = np.minimum(1.0, t / attack) * np.minimum(1.0, (dur - t) / 0.9)
        self._add(self.music, t0, sig * env, amp * 0.072 / max(1, len(freqs) ** 0.5))

    def thump(self, t0, freq=88, dur=0.32, amp=0.8):
        n = int(dur * SR)
        t = np.arange(n) / SR
        sig = np.sin(2 * np.pi * freq * (1 - 0.25 * t / dur) * t) * np.exp(-t * 11)
        self._add(self.sfx, t0, sig, amp * 0.44)

    def noise_hit(self, t0, dur=0.2, amp=0.6, lp=0.25, hp=0.0):
        n = int(dur * SR)
        t = np.arange(n) / SR
        rng = np.random.default_rng(int(t0 * 1000) % 99991)
        x = rng.standard_normal(n)
        # one-pole lowpass + optional highpass (diff)
        y = np.zeros(n)
        acc = 0.0
        for i in range(n):
            acc += lp * (x[i] - acc)
            y[i] = acc
        if hp > 0:
            y = x - y
        env = np.exp(-t * (4 / dur))
        self._add(self.sfx, t0, y * env, amp * 0.40)

    def slide(self, t0, f0, f1, dur=0.3, amp=0.6, kind="tri"):
        n = int(dur * SR)
        t = np.arange(n) / SR
        fr = f0 * (f1 / f0) ** (t / dur)
        ph = 2 * np.pi * np.cumsum(fr) / SR
        if kind == "tri":
            sig = 2 / np.pi * np.arcsin(np.sin(ph))
        else:
            sig = np.sin(ph)
        env = np.minimum(1, t / 0.012) * np.exp(-t * (2.2 / dur))
        self._add(self.sfx, t0, sig * env, amp * 0.30)

    def whoosh(self, t0, dur=0.5, amp=0.6, rise=True):
        n = int(dur * SR)
        t = np.arange(n) / SR
        rng = np.random.default_rng(int(t0 * 997) % 99991)
        x = rng.standard_normal(n)
        y = np.zeros(n)
        acc = 0.0
        for i in range(n):
            k = 0.06 + 0.30 * (t[i] / dur if rise else 1 - t[i] / dur)
            acc += k * (x[i] - acc)
            y[i] = acc
        env = np.sin(np.pi * t / dur) ** 1.6
        self._add(self.sfx, t0, y * env, amp * 0.4)

    def click(self, t0, amp=0.8):
        n = int(0.045 * SR)
        t = np.arange(n) / SR
        sig = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 240) + \
            0.7 * np.sin(2 * np.pi * 1150 * t) * np.exp(-t * 160)
        self._add(self.sfx, t0, sig, amp * 0.30)

    def rain_bed(self, t_start, t_end, amp=1.0, dip=None):
        """Filtered noise bed with slow texture."""
        i0, i1 = int(t_start * SR), int(min(N, t_end * SR))
        n = i1 - i0
        if n <= 0:
            return
        rng = np.random.default_rng(4242)
        x = rng.standard_normal(n)
        # gentle lowpass (two passes) + droplet ticks
        y = np.zeros(n)
        acc = 0.0
        for i in range(n):
            acc += 0.14 * (x[i] - acc)
            y[i] = acc
        y *= 0.9
        y += 0.22 * x  # hiss layer
        # slow amplitude texture
        t = np.arange(n) / SR
        y *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.13 * t) * np.sin(2 * np.pi * 0.041 * t)
        env = np.ones(n)
        fade = int(2.2 * SR)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        if dip:
            d0, d1 = int((dip[0] - t_start) * SR), int((dip[1] - t_start) * SR)
            env[max(0, d0):d1] *= 0.12
        self.rain[i0:i1] += y * env * amp * 0.17


# ----------------------------------------------------------------------------
# THE SCORE — beat by beat
# ----------------------------------------------------------------------------
def build() -> np.ndarray:
    s = Score()

    # ---- 0–5: the void. one distant note as the world appears.
    s.bell(3.6, f("A5"), dur=2.6, amp=0.32)

    # ---- 5–20: he walks in. curious music-box arpeggios (Am–F).
    arp_a = ["A3", "C4", "E4", "A4", "E4", "C4"]
    arp_f = ["F3", "A3", "C4", "F4", "C4", "A3"]
    for i in range(6):
        s.pluck(5.0 + i * 0.82, f(arp_a[i]), amp=0.42)
        s.pluck(10.2 + i * 0.82, f(arp_f[i]), amp=0.46)
    s.pad(5.0, [f("A2"), f("E3")], dur=5.4, amp=0.5)
    s.pad(10.2, [f("F2"), f("C3")], dur=5.4, amp=0.5)

    # THUK + taps
    s.thump(8.42, 82, amp=0.9)
    s.noise_hit(8.42, 0.10, amp=0.5, hp=0.6)
    s.click(12.78, amp=0.35)
    s.click(13.18, amp=0.35)
    s.bell(17.3, f("E5"), dur=1.4, amp=0.4)
    s.bell(18.4, f("A5"), dur=1.8, amp=0.5)

    # ---- 20–35: curiosity escalates (C–G, tension, comedy crash)
    arp_c = ["C4", "E4", "G4", "C5", "G4", "E4"]
    for i in range(6):
        s.pluck(20.3 + i * 0.78, f(arp_c[i]), amp=0.46)
    s.pad(20.2, [f("C3"), f("G3")], dur=5.0, amp=0.5)
    s.slide(23.35, 520, 320, 0.18, amp=0.4)            # slip
    s.slide(27.28, 300, 120, 0.20, amp=0.5)            # kick bonk
    for i, tt in enumerate(np.arange(28.7, 31.55, 0.31)):   # straining pulse
        s.pluck(tt, f("E4"), dur=0.4, amp=0.30 + 0.05 * i)
    s.slide(31.55, 640, 900, 0.28, amp=0.35, kind="sin")    # the slip-off
    s.thump(31.95, 74, dur=0.5, amp=1.0)                     # crash
    s.noise_hit(31.95, 0.32, amp=0.55, lp=0.12)
    s.slide(32.25, 300, 130, 0.42, amp=0.5)                  # womp-womp
    s.slide(32.75, 260, 110, 0.46, amp=0.42)
    s.pad(32.3, [f("A2")], dur=2.4, amp=0.4)

    # ---- 35–59.4: training montage. driving arpeggio, F–C–G–Am.
    prog = [("F3", "C4", "A3"), ("C3", "G3", "E4"), ("G3", "D4", "B3"),
            ("A3", "E4", "C5")]
    for i, tt in enumerate(np.arange(35.0, 59.4, 1.55)):
        ch = prog[i % 4]
        s.pad(tt, [f(ch[0])], dur=1.7, amp=0.42, attack=0.2)
        s.pluck(tt, f(ch[0]), amp=0.5)
        s.pluck(tt + 0.39, f(ch[1]), amp=0.36)
        s.pluck(tt + 0.78, f(ch[2]), amp=0.42)
        s.pluck(tt + 1.17, f(ch[1]), amp=0.34)
    for tt in (39.2, 43.4, 47.6, 51.8, 55.0):
        s.whoosh(tt - 0.10, 0.22, amp=0.5)               # montage cuts
    s.bell(52.6, f("E6"), dur=1.2, amp=0.42)             # flex glints
    s.bell(53.4, f("A5"), dur=1.2, amp=0.38)
    s.bell(54.2, f("C6"), dur=1.4, amp=0.36)
    s.slide(59.42, 320, 60, 0.30, amp=0.5)               # record stop
    # …silence 59.7–60.4 — the freeze lands.

    # ---- 60–80: anger. stabs, bonks, booms.
    s.thump(60.15, 92, dur=0.4, amp=0.8)
    s.pad(60.0, [f("A2"), f("E3")], dur=3.6, amp=0.55, attack=0.15)
    s.whoosh(62.45, 0.55, amp=0.7)                        # the throw
    s.thump(62.997, 70, dur=0.55, amp=1.0)                # landing
    s.noise_hit(62.997, 0.35, amp=0.5, lp=0.10)
    s.whoosh(65.28, 0.30, amp=0.6)                        # hammer swing
    s.slide(65.62, 340, 110, 0.26, amp=0.7)               # BONK
    s.thump(65.62, 80, dur=0.35, amp=0.8)
    s.whoosh(69.35, 0.65, amp=0.55)                       # stone falls
    s.thump(69.85, 58, dur=0.9, amp=1.1)                  # BOOM
    s.noise_hit(69.85, 0.55, amp=0.6, lp=0.08)
    s.whoosh(72.75, 0.5, amp=0.5)                         # jump
    s.thump(74.45, 76, dur=0.5, amp=0.95)                 # crash
    s.noise_hit(74.45, 0.4, amp=0.55, lp=0.12)
    s.slide(74.9, 240, 100, 0.5, amp=0.42)
    s.pad(76.0, [f("A2"), f("E3")], dur=4.4, amp=0.42, attack=1.2)

    # ---- 80–100: the lowest point. rain, sparse notes.
    s.rain_bed(80.0, 143.5, amp=1.0, dip=(115.1, 116.9))
    s.pad(81.5, [f("A2"), f("C3")], dur=6.5, amp=0.5, attack=1.8)
    s.piano(83.0, f("A2"), dur=2.6, amp=0.5)
    s.piano(86.2, f("E3"), dur=2.6, amp=0.42)
    s.piano(91.5, f("A2"), dur=2.8, amp=0.4)
    s.piano(95.6, f("C3"), dur=2.8, amp=0.38)
    s.pad(88.0, [f("A2")], dur=10.0, amp=0.34, attack=2.5)  # the stillness
    s.bell(98.6, f("E5"), dur=2.2, amp=0.30)

    # ---- 100–120: discovery. tension → click → silence → bloom.
    s.pad(100.2, [f("A2"), f("E3"), f("B3")], dur=6.0, amp=0.42, attack=1.5)
    s.bell(103.55, f("C6"), dur=1.6, amp=0.42)            # the glint
    # riser 108–113
    n_r = int(5.0 * SR)
    t_r = np.arange(n_r) / SR
    rng = np.random.default_rng(77)
    noise = rng.standard_normal(n_r)
    acc = np.zeros(n_r)
    a = 0.0
    for i in range(n_r):
        k = 0.02 + 0.22 * (t_r[i] / 5.0)
        a += k * (noise[i] - a)
        acc[i] = a
    s._add(s.sfx, 108.0, acc * (t_r / 5.0) ** 2.2, 0.34)
    for tt in np.arange(108.0, 113.0, 0.24):
        s.pluck(tt, f("E4"), dur=0.30, amp=0.10 + 0.22 * (tt - 108) / 5)
    s.click(113.32, amp=1.0)                              # CLICK
    # …pure silence 115–116.9 (rain dips too)
    s.thump(117.32, 300, dur=0.14, amp=0.5)               # latch pop
    s.slide(117.32, 180, 320, 0.12, amp=0.35, kind="sin")
    s.pad(117.5, [f("C3"), f("E3"), f("G3"), f("C4")], dur=4.2, amp=0.72,
          attack=0.7)                                     # the bloom
    for i, note in enumerate(["C5", "E5", "G5", "C6"]):
        s.bell(117.8 + i * 0.22, f(note), dur=2.2, amp=0.4)

    # ---- 120–140: the mirror. warm theme F–C–G–Am→C.
    s.pad(120.0, [f("F2"), f("C3"), f("A3")], dur=5.0, amp=0.55, attack=1.0)
    for tt, note in ((120.4, "C5"), (121.3, "A4"), (122.2, "G4"), (123.1, "E4"),
                     (124.0, "F4"), (125.2, "A4")):
        s.piano(tt, f(note), dur=2.2, amp=0.5)
    s.pad(125.0, [f("C3"), f("G3"), f("E4")], dur=5.0, amp=0.55, attack=1.0)
    for tt, note in ((125.4, "G4"), (126.3, "E4"), (127.2, "C4"), (128.4, "D4"),
                     (129.3, "E4")):
        s.piano(tt, f(note), dur=2.2, amp=0.48)
    s.bell(129.35, f("G5"), dur=1.8, amp=0.36)            # hand on chest
    s.pad(130.0, [f("G2"), f("D3"), f("B3")], dur=5.0, amp=0.55, attack=1.0)
    for tt, note in ((130.4, "B4"), (131.3, "A4"), (132.2, "G4"), (133.4, "E4")):
        s.piano(tt, f(note), dur=2.2, amp=0.48)
    s.bell(133.6, f("C6"), dur=1.8, amp=0.42)             # the reflection smiles
    s.pad(135.0, [f("A2"), f("E3"), f("C4")], dur=5.4, amp=0.55, attack=1.0)
    for tt, note in ((135.4, "A4"), (136.3, "C5"), (137.2, "E5"), (138.4, "A4")):
        s.piano(tt, f(note), dur=2.4, amp=0.5)

    # ---- 140–160: the ending. full theme, resolve, fade.
    s.pad(140.0, [f("F2"), f("C3"), f("A3")], dur=5.0, amp=0.6, attack=0.8)
    for tt, note in ((140.3, "C5"), (141.2, "A4"), (142.1, "F4"), (143.0, "G4"),
                     (144.2, "A4"), (145.4, "C5")):
        s.piano(tt, f(note), dur=2.6, amp=0.55)
    s.pad(145.0, [f("C3"), f("G3"), f("E4")], dur=5.0, amp=0.6, attack=0.8)
    for tt, note in ((145.3, "G4"), (146.2, "E4"), (147.4, "C4"), (148.6, "E4"),
                     (149.8, "G4")):
        s.piano(tt, f(note), dur=2.6, amp=0.52)
    s.pad(150.0, [f("G2"), f("D3"), f("B3")], dur=5.4, amp=0.62, attack=0.8)
    for tt, note in ((150.3, "D5"), (151.2, "B4"), (152.1, "G4"), (153.4, "A4"),
                     (154.6, "B4")):
        s.piano(tt, f(note), dur=2.8, amp=0.55)
    s.pad(155.0, [f("C3"), f("G3"), f("E4"), f("C5")], dur=5.0, amp=0.7,
          attack=1.0)                                     # final C major
    for tt, note in ((155.3, "C5"), (156.2, "E5"), (157.3, "G5"), (158.2, "C6")):
        s.piano(tt, f(note), dur=3.2, amp=0.55)
    s.bell(157.25, f("C6"), dur=2.8, amp=0.42)            # the tableau

    # ----------------------------------------------------------------------------
    # mix
    # ----------------------------------------------------------------------------
    t = np.arange(N) / SR

    # the "pure silence" beat — cut EVERYTHING for 2.4 s before the bloom
    gate = np.ones(N)
    g0, g1 = int(114.55 * SR), int(117.05 * SR)
    edge = int(0.12 * SR)
    gate[g0:g1] = 0.0
    gate[g0 - edge:g0] = np.linspace(1, 0, edge)
    gate[g1:g1 + edge] = np.linspace(0, 1, edge)
    s.music *= gate
    s.sfx *= gate
    s.rain *= gate

    mix = 0.92 * s.music + 1.0 * s.sfx + 0.85 * s.rain
    # master fade in/out
    fade = np.ones(N)
    fade[:int(0.6 * SR)] = np.linspace(0, 1, int(0.6 * SR))
    tail = int(2.2 * SR)
    fade[-tail:] = np.linspace(1, 0, tail) ** 1.4
    mix *= fade
    # soft clip + normalise
    mix = np.tanh(mix * 1.25)
    peak = np.max(np.abs(mix)) + 1e-9
    mix *= 0.88 / peak

    # gentle stereo width: tiny delay on the side channel
    d = int(0.011 * SR)
    left = mix
    right = np.concatenate([np.zeros(d), mix[:-d]])
    stereo = np.stack([0.94 * left + 0.16 * right,
                       0.94 * right + 0.16 * left], axis=1)
    return np.clip(stereo, -1.0, 1.0)


def main(out_path="out/audio.wav"):
    import os
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    stereo = build()
    pcm = (stereo * 32767).astype("<i2")
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {out_path} ({pcm.shape[0] / SR:.1f}s)")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "out/audio.wav")
