"""THE BOX — scene-by-scene timeline (the screenplay, executable).

Time codes (seconds):
  S1  0–10    Empty world / entry / trip       Extreme wide
  S2  10–20   The box: touch → lift → shake    Medium
  S3  20–35   Curiosity: 4 attempts → fall     Close-up
  S4  35–60   Obsession: training montage      Montage
  S5  60–80   Anger: throw/hammer/stone/jump   Dynamic
  S6  80–100  Lowest point: rain, stillness    Wide
  S7  100–120 Discovery: the tiny button       Close-up
  S8  120–140 Inside: the mirror               Top shot
  S9  140–160 Ending: smile, walk on, reveal   Slow pull-back
"""
from __future__ import annotations

import math
import random

from PIL import Image

from . import engine as E
from .engine import (Camera, Painter, Pose, Box, FPS, W, H, WHITE, INK, WARM,
                     WARM_PALE, GLOW_YEL, MIRROR_TOP, MIRROR_BOT,
                     HIP_H, HEAD_R, TORSO,
                     clamp, lerp, seg, smoothstep, ease_in, ease_out,
                     ease_in_out, substep, mix, rot,
                     draw_stickman, draw_box, stickman_points,
                     walk_pose, idle_pose, sit_pose)

TOTAL = 160.0  # seconds

# world landmarks
BOX_X = 0.0        # box resting place (S1–S4)
THROW_X = 2.5      # where the box lands after the throw (S5 onwards)
BOX_S = 0.60


# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------
def with_pose(p: Pose, **kw) -> Pose:
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def hand_hold_box(p: Pose, box: Box, lift=0.0):
    """Anchor the box to the character's front wrist (one-hand carry)."""
    pts = stickman_points(p)
    _, _, wr = pts["arm_front"]
    box.x = wr[0] + 0.16 * p.facing
    box.y = wr[1] - box.size * 0.55 + lift
    box.held = True
    return wr


def both_hands_hold_box(p: Pose, box: Box, overhead=False):
    pts = stickman_points(p)
    _, _, wr_l = pts["arm_front"]
    _, _, wr_r = pts["arm_back"]
    cx = (wr_l[0] + wr_r[0]) / 2
    cy = (wr_l[1] + wr_r[1]) / 2
    box.x = cx
    box.y = cy - box.size * (1.05 if overhead else 0.55)
    box.held = True


def draw_finger(painter: Painter, tip, back, width=0.15):
    """Foreground hand reaching in: forearm, fist, and one pointing finger."""
    painter.line(back, tip, width * 0.62)
    fist = (tip[0] - width * 0.28, tip[1] + width * 0.30)
    painter.circle(fist, width * 0.62, fill=INK)
    painter.line(fist, tip, width * 0.42)
    painter.circle(tip, width * 0.26, fill=INK)


def draw_hammer(painter: Painter, wrist, ang_deg, scale=1.0):
    """Sledgehammer held at wrist, pointing along ang_deg (0 = down)."""
    a = math.radians(ang_deg)
    hx = wrist[0] + math.sin(a) * 0.02
    hy = wrist[1] - math.cos(a) * 0.02
    end = (hx + math.sin(a) * 1.15 * scale, hy - math.cos(a) * 1.15 * scale)
    painter.line((hx, hy), end, 0.055 * scale)
    # head at the far end, perpendicular
    pa = a + math.pi / 2
    dx, dy = math.sin(pa) * 0.30 * scale, -math.cos(pa) * 0.30 * scale
    painter.poly([(end[0] - dx, end[1] - dy), (end[0] + dx, end[1] + dy),
                  (end[0] + dx * 0.9 - math.sin(a) * 0.22 * scale,
                   end[1] + dy * 0.9 + math.cos(a) * 0.22 * scale),
                  (end[0] - dx * 0.9 - math.sin(a) * 0.22 * scale,
                   end[1] - dy * 0.9 + math.cos(a) * 0.22 * scale)],
                 fill=(120, 122, 128), outline=INK, width=0.02)


def draw_dumbbell(painter: Painter, wrist, ang_deg, scale=1.0):
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    half = 0.34 * scale
    p0 = (wrist[0] - sa * half, wrist[1] - ca * half)
    p1 = (wrist[0] + sa * half, wrist[1] + ca * half)
    painter.line(p0, p1, 0.05 * scale)
    for pp, sgn in ((p0, -1), (p1, 1)):
        painter.poly(
            [(pp[0] - ca * 0.16 * scale, pp[1] + sa * 0.16 * scale),
             (pp[0] + ca * 0.16 * scale, pp[1] - sa * 0.16 * scale),
             (pp[0] + ca * 0.16 * scale + sgn * sa * 0.10 * scale,
              pp[1] - sa * 0.16 * scale + sgn * ca * 0.10 * scale),
             (pp[0] - ca * 0.16 * scale + sgn * sa * 0.10 * scale,
              pp[1] + sa * 0.16 * scale + sgn * ca * 0.10 * scale)],
            fill=(120, 122, 128), outline=INK, width=0.02)


def draw_stone(painter: Painter, pos, r, seed=3):
    rng = random.Random(seed)
    pts = []
    for i in range(9):
        ang = math.pi * 2 * i / 9
        rr = r * rng.uniform(0.78, 1.12)
        pts.append((pos[0] + math.cos(ang) * rr * 1.15,
                    pos[1] + math.sin(ang) * rr * 0.92))
    painter.poly(pts, fill=(150, 152, 158), outline=INK, width=0.025)
    for k in range(3):
        cx = pos[0] + rng.uniform(-0.4, 0.4) * r
        cy = pos[1] + rng.uniform(-0.35, 0.35) * r
        painter.poly([(cx, cy), (cx + r * 0.28, cy + r * 0.1),
                      (cx + r * 0.1, cy + r * 0.32)],
                     fill=(128, 130, 136))


def draw_arrow(painter: Painter, x0, x1, y, width=0.13):
    painter.line((x0, y), (x1 - width * 2.4, y), width)
    painter.poly([(x1, y), (x1 - width * 2.6, y + width * 1.75),
                  (x1 - width * 2.6, y - width * 1.75)], fill=INK)


def poly_sit_slim(p, head_low):
    return sit_pose(p.x, facing=p.facing, thickness=p.thickness, t=p.y,
                    head_low=head_low)


# ----------------------------------------------------------------------------
# global environment state (grey sky / rain / clouds) by time
# ----------------------------------------------------------------------------
def env_amounts(t):
    """(grey, clouds, rain, ground) across the whole film."""
    # white world until the low point; storm 82–146; clears for the finale
    grey = smoothstep(seg(t, 80.5, 84.5)) * (1 - smoothstep(seg(t, 144.5, 148.5)))
    clouds = smoothstep(seg(t, 81.5, 85.5)) * (1 - smoothstep(seg(t, 143.5, 147.5)))
    rain = smoothstep(seg(t, 82.5, 86.5)) * (1 - smoothstep(seg(t, 140.0, 143.5)))
    # "pure silence" beat: rain visually softens briefly
    rain *= 1.0 - 0.45 * smoothstep(seg(t, 115.2, 115.9)) * (1 - smoothstep(seg(t, 116.8, 117.6)))
    ground = 0.55 * grey
    return grey, clouds, rain, ground


# ----------------------------------------------------------------------------
# SCENE 1 — EMPTY WORLD (0–10) extreme wide
# ----------------------------------------------------------------------------
def scene1(t, p: Painter, cam: Camera):
    cam.y = 1.35
    cam.view_h = lerp(8.4, 7.4, ease_in_out(seg(t, 6.0, 10.0)))
    cam.x = lerp(-2.6, -1.7, ease_in_out(seg(t, 0.0, 10.0)))

    box = Box(x=BOX_X, y=0, size=BOX_S)
    if t < 5.0:
        # five full seconds of nothing — the void does the talking
        return

    if t < 8.42:
        # he strolls in from the left, relaxed, glancing around
        x = lerp(-6.2, BOX_X - 0.62, ease_in_out(seg(t, 5.0, 8.42)) * 0.22
                 + seg(t, 5.0, 8.42) * 0.78)
        man = walk_pose(t, x0=x, t_start=5.0, speed=1.63)
        man.eye, man.mouth, man.brow = "open", "neutral", "none"
        if 6.15 < t < 6.75:                     # glance left
            man.look, man.head_tilt = (-1, 0.4), -10
        elif 7.25 < t < 7.85:                   # glance right
            man.look, man.head_tilt = (1, 0.35), 8
        draw_box(p, box)
        draw_stickman(p, man)
        return

    if t < 9.25:
        # THUK — his foot catches the box
        dt = t - 8.42
        recoil = ease_out(clamp(dt / 0.55))
        x = lerp(BOX_X - 0.62, BOX_X - 1.42, recoil)
        man = Pose(x=x, y=HIP_H + 0.04, facing=1)
        man.lean = lerp(16, -18, smoothstep(clamp(dt / 0.32)))
        man.hip_l, man.kn_l = lerp(30, -18, recoil), lerp(-18, -8, recoil)
        man.hip_r, man.kn_r = lerp(-24, 12, recoil), lerp(-34, -16, recoil)
        man.sh_l, man.el_l = lerp(30, -128, ease_out(clamp(dt / 0.28))), 22
        man.sh_r, man.el_r = lerp(20, -110, ease_out(clamp(dt / 0.30))), 18
        man.eye, man.mouth = ("wide", "o") if dt < 0.5 else ("open", "flat")
        man.brow = "raise" if dt < 0.5 else "none"
        man.look = (0.2, -0.5)
        draw_box(p, box)
        draw_stickman(p, man)
        E.star_burst(p, (BOX_X + 0.05, 0.52), 0.42, t, 8.42)
        E.dust_puff(p, (BOX_X - 0.35, 0.12), t, 8.45, r=0.4)
        return

    # 9.25–10 — he stands over it and stares down
    man = idle_pose(BOX_X - 0.92, t=t, facing=1)
    man.lean = 10
    man.head_tilt = 22
    man.look = (0.7, -1)
    man.eye, man.mouth, man.brow = "open", "o", "raise"
    man.sh_l, man.el_l = 42, 38
    man.sh_r, man.el_r = 36, 34
    draw_box(p, box)
    draw_stickman(p, man)


# ----------------------------------------------------------------------------
# SCENE 2 — THE BOX (10–20) medium
# ----------------------------------------------------------------------------
def scene2(t, p: Painter, cam: Camera):
    cam.y = 1.05
    cam.view_h = 3.3
    cam.x = lerp(-1.15, -0.72, ease_in_out(seg(t, 10, 20)))

    box = Box(x=BOX_X, y=0, size=BOX_S)
    man = idle_pose(BOX_X - 0.92, t=t, facing=1)
    man.eye, man.mouth, man.brow = "big", "neutral", "raise"
    man.look = (0.6, -0.9)
    man.head_tilt = 16

    if t < 11.5:
        # long curious look
        man.sh_l, man.el_l = 38, 32
        man.sh_r, man.el_r = 32, 28
    elif t < 12.6:
        # reach down and touch the lid
        k = ease_in_out(seg(t, 11.5, 12.3))
        man = Pose(x=BOX_X - 0.92 + 0.26 * k, y=HIP_H - 0.10 * k, facing=1)
        man.lean = 10 + 22 * k
        man.head_tilt = 16 + 10 * k
        man.look = (0.5, -1)
        man.eye, man.mouth, man.brow = "big", "o", "raise"
        man.sh_l, man.el_l = lerp(30, 66, k), lerp(30, 18, k)
        man.sh_r, man.el_r = 24, 26
        man.hip_l, man.kn_l = lerp(8, 26, k), lerp(-10, -30, k)
        man.hip_r, man.kn_r = lerp(-8, -2, k), lerp(-6, -14, k)
    elif t < 13.6:
        # two quick pokes
        poke = 1 if (12.6 < t < 12.82 or 13.12 < t < 13.32) else 0
        man = Pose(x=BOX_X - 0.66, y=HIP_H - 0.10, facing=1)
        man.lean = 32
        man.head_tilt = 26
        man.look = (0.5, -1)
        man.eye, man.mouth, man.brow = "big", "o" if poke else "neutral", "raise"
        man.sh_l, man.el_l = (74, 10) if poke else (66, 18)
        man.sh_r, man.el_r = 24, 26
        man.hip_l, man.kn_l = 26, -30
        man.hip_r, man.kn_r = -2, -14
        if poke:
            E.sparkle(p, (BOX_X - 0.02, 0.66), 0.14, t, phase=t * 9)
    elif t < 15.6:
        # pick it up — it's light
        k = ease_in_out(seg(t, 13.6, 14.6))
        man = Pose(x=BOX_X - 0.66 + 0.06 * k, y=HIP_H - 0.10 + 0.10 * k,
                   facing=1)
        man.lean = lerp(30, 6, k)
        man.head_tilt = lerp(26, -6, k)
        man.look = (0.3, 0.1)
        man.eye, man.mouth, man.brow = "big", "o", "raise"
        man.sh_l, man.el_l = lerp(66, 8, k), lerp(18, 74, k)
        man.sh_r, man.el_r = lerp(24, -4, k), lerp(26, 40, k)
        man.hip_l, man.kn_l = lerp(26, 8, k), lerp(-30, -10, k)
        man.hip_r, man.kn_r = -6, -8
        draw_stickman(p, man)
        bx = lerp(BOX_X, BOX_X - 0.52, k)
        by = lerp(0, 1.02, ease_out(k))
        box.x, box.y = bx, by
        box.held = k > 0.2
        draw_box(p, box)
        return
    elif t < 17.2:
        # weigh it — it's almost nothing
        man = Pose(x=BOX_X - 0.88, y=HIP_H, facing=1)
        man.lean = 2
        man.head_tilt = -8
        man.look = (0.35, 0.15)
        man.eye, man.mouth, man.brow = "big", "o", "raise"
        man.sh_l, man.el_l = 8, 78
        man.sh_r, man.el_r = -4, 44
        draw_stickman(p, man)
        box.x, box.y = BOX_X - 0.50, 1.06 + 0.09 * math.sin((t - 15.6) * 6.5)
        box.held = True
        box.glow = 0.25 + 0.2 * math.sin((t - 15.6) * 6.5)
        draw_box(p, box)
        return
    else:
        # shake it — light leaks from the seams
        man = Pose(x=BOX_X - 0.88, y=HIP_H, facing=1)
        man.lean = 4
        man.head_tilt = -4
        man.look = (0.35, 0.1)
        man.eye, man.mouth, man.brow = "big", "grin", "raise"
        man.sh_l, man.el_l = 22, 88
        man.sh_r, man.el_r = 6, 52
        j = 0.05 * math.sin((t - 17.2) * 22)
        draw_stickman(p, man)
        box.x, box.y = BOX_X - 0.48 + j, 1.08
        box.held = True
        box.glow = 0.45 + 0.45 * (0.5 + 0.5 * math.sin((t - 17.2) * 9))
        draw_box(p, box)
        for i in range(4):
            sp = ((t - 17.2) * 0.9 + i * 0.23) % 1.0
            E.sparkle(p, (box.x - 0.3 + i * 0.2 + 0.05 * math.sin(t * 7 + i),
                          box.y + 0.15 + sp * 0.75), 0.10 + 0.05 * i % 2,
                      t, phase=i * 1.7)
        return

    draw_stickman(p, man)
    draw_box(p, box)


# ----------------------------------------------------------------------------
# SCENE 3 — CURIOSITY (20–35) close-up, comedy escalation
# ----------------------------------------------------------------------------
def scene3(t, p: Painter, cam: Camera):
    cam.y = 1.45
    cam.view_h = 2.45
    cam.x = lerp(-0.85, -0.55, seg(t, 20, 35))

    box = Box(x=BOX_X - 0.30, y=0.80, size=BOX_S, glow=0.0)

    # base: standing, holding the box at chest height
    man = Pose(x=BOX_X - 1.05, y=HIP_H, facing=1, thickness=1.0)

    if t < 21.6:
        # excited — big eyes, little bounces
        b = 0.035 * math.sin(t * 5.2)
        man.y += abs(b)
        man.eye, man.mouth, man.brow = "big", "grin", "raise"
        man.look = (0.45, 0.05)
        man.head_tilt = -6
        man.sh_l, man.el_l = 26, 84
        man.sh_r, man.el_r = 8, 50
        box.x, box.y = BOX_X - 0.30, 0.84 + b
    elif t < 23.7:
        # ATTEMPT 1 — pull the lid. nothing.
        k = seg(t, 21.6, 23.3)
        strain = math.sin(t * 42) * 0.016 if t > 22.1 else 0
        man.x += strain
        man.lean = lerp(6, -26, ease_in_out(k))
        man.eye, man.mouth = ("shut", "grit")
        man.brow = "angry"
        man.look = (0.5, -0.3)
        man.sh_l, man.el_l = lerp(26, 96, k), lerp(84, 26, k)
        man.sh_r, man.el_r = lerp(8, 84, k), lerp(50, 18, k)
        if t > 23.3:  # slip — hands fly off
            sl = ease_out(seg(t, 23.3, 23.7))
            man.lean = lerp(-26, 12, sl)
            man.sh_l, man.el_l = lerp(96, -140, sl), lerp(26, 30, sl)
            man.sh_r, man.el_r = lerp(84, -125, sl), lerp(18, 26, sl)
            man.eye, man.mouth, man.brow = "wide", "o", "raise"
        box.x = BOX_X - 0.30 - 0.10 * ease_in_out(k) + (0.16 * sl if t > 23.3 else 0)
        box.y = 0.80 + 0.10 * ease_in_out(k)
        box.tilt = 4 * math.sin(t * 30) if 22.1 < t < 23.3 else 0
    elif t < 26.2:
        # ATTEMPT 2 — both hands, twist and pull
        k = seg(t, 23.7, 25.9)
        man.x += math.sin(t * 38) * 0.012 * (t > 24.2)
        man.lean = lerp(10, -22, ease_in_out(k))
        man.eye, man.mouth, man.brow = "shut", "grit", "angry"
        man.sh_l, man.el_l = lerp(30, 88, k), lerp(80, 30, k)
        man.sh_r, man.el_r = lerp(10, 76, k), lerp(52, 22, k)
        box.x = BOX_X - 0.30 + 0.035 * math.sin(t * 24) * (t > 24.2)
        box.y = 0.84 + 0.02 * math.cos(t * 24) * (t > 24.2)
        box.tilt = 7 * math.sin(t * 24) * (t > 24.2)
    elif t < 28.7:
        # ATTEMPT 3 — kick it
        k = seg(t, 26.2, 27.25)
        if t < 27.25:
            man.x = lerp(BOX_X - 1.18, BOX_X - 1.02, ease_out(k))
            man.eye, man.mouth, man.brow = "angry", "grit", "angry"
            man.sh_l, man.el_l = -62, 40
            man.sh_r, man.el_r = -78, 36
            man.hip_l = lerp(-26, 58, ease_in(k))
            man.kn_l = lerp(-42, -16, k)
            man.hip_r, man.kn_r = -16, -24
            man.lean = -12
        else:
            # hop back, clutching the foot — comedy
            kk = seg(t, 27.25, 28.7)
            man.x = BOX_X - 1.02 - 0.55 * ease_out(kk)
            man.y = HIP_H + abs(math.sin((t - 27.25) * 9)) * 0.16 * (1 - kk)
            man.eye, man.mouth, man.brow = "shut", "open", "sad"
            man.hip_l, man.kn_l = 62, -118
            man.hip_r, man.kn_r = -8, -10
            man.sh_l, man.el_l = 130, 62
            man.sh_r, man.el_r = 118, 58
            man.lean = -14
            man.head_tilt = -12
        box.x, box.y = BOX_X - 0.30, 0.0
        box.tilt = 0
        if 27.25 < t < 27.7:
            E.star_burst(p, (BOX_X - 0.42, 0.32), 0.5, t, 27.25)
    elif t < 32.1:
        # ATTEMPT 4 — everything he has
        k = seg(t, 28.7, 31.6)
        man = Pose(x=BOX_X - 1.18, y=HIP_H, facing=1)
        man.x += math.sin(t * 46) * 0.020 * (t > 29.2)
        man.lean = lerp(12, -34, ease_in_out(k))
        man.eye, man.mouth, man.brow = "shut", "grit", "angry"
        man.sh_l, man.el_l = lerp(40, 108, k), lerp(60, 12, k)
        man.sh_r, man.el_r = lerp(22, 96, k), lerp(46, 8, k)
        man.hip_l, man.kn_l = lerp(12, 34, k), lerp(-12, -26, k)
        man.hip_r, man.kn_r = lerp(-12, -30, k), lerp(-10, -22, k)
        box.x, box.y = BOX_X - 0.30, 0.86 + 0.10 * ease_in_out(k)
        box.tilt = 3 * math.sin(t * 40)
        if t > 31.6:  # RELEASE — he crashes to the ground
            cr = seg(t, 31.6, 32.1)
            man = Pose(x=lerp(BOX_X - 1.18, BOX_X - 1.72, ease_out(cr)),
                       y=lerp(HIP_H, 0.16, ease_in(cr)), facing=1)
            man.head_dy = -0.16 * ease_in(cr)
            man.lean = lerp(-34, 84, ease_in(cr))
            man.hip_l, man.kn_l = lerp(34, -86, ease_in(cr)), lerp(-26, -6, cr)
            man.hip_r, man.kn_r = lerp(-30, -80, ease_in(cr)), lerp(-22, -4, cr)
            man.sh_l, man.el_l = lerp(108, 168, ease_in(cr)), lerp(12, -8, cr)
            man.sh_r, man.el_r = lerp(96, 158, ease_in(cr)), lerp(8, -6, cr)
            man.eye = "wide" if cr < 0.5 else "shut"
            man.mouth, man.brow = "o", "raise"
            box.x, box.y = BOX_X - 0.30, lerp(0.96, 0, ease_in(cr))
            E.dust_puff(p, (man.x + 0.2, 0.12), t, 31.95, r=0.62, n=8)
    else:
        # 32.1–35 — flat on his back. box: untouched. beat.
        man = Pose(x=BOX_X - 1.72, y=0.16, facing=1)
        man.head_dy = -0.16
        man.lean = 84
        man.hip_l, man.kn_l = -86, -6
        man.hip_r, man.kn_r = -80, -4
        man.sh_l, man.el_l = 168, -8
        man.sh_r, man.el_r = 158, -6
        if t < 33.2:
            man.eye, man.mouth, man.brow = "wide", "o", "raise"
        else:
            man.eye, man.mouth, man.brow = "shut", "flat", "sad"
        box.x, box.y = BOX_X - 0.30, 0
        if 32.1 < t < 32.9:
            E.star_burst(p, (man.x + 0.75, 0.75), 0.3, t, 32.15)
            E.star_burst(p, (man.x + 0.45, 0.95), 0.22, t, 32.3)

    draw_box(p, box)
    draw_stickman(p, man)


# ----------------------------------------------------------------------------
# SCENE 4 — OBSESSION (35–60) montage
# ----------------------------------------------------------------------------
def scene4(t, p: Painter, cam: Camera):
    box = Box(x=BOX_X, y=0, size=BOX_S)

    if t < 39.2:
        # SHOT A — dumbbell curls (arms thicken rep by rep)
        cam.x, cam.y, cam.view_h = -0.2, 1.35, 3.1
        k = seg(t, 35, 39.2)
        man = Pose(x=-0.2, y=HIP_H, facing=1, thickness=1.0 + 0.12 * k)
        rep = (t - 35) * 1.45
        curl = 0.5 + 0.5 * math.sin(rep * math.pi * 2)
        man.eye, man.mouth, man.brow = "squint", "grit", "angry"
        man.sh_l, man.el_l = -22, 112          # hand on hip
        man.sh_r, man.el_r = 12, lerp(28, 118, curl)
        man.lean = 3
        draw_stickman(p, man)
        pts = stickman_points(man)
        _, _, wr = pts["arm_front"]
        draw_dumbbell(p, (wr[0] + 0.05, wr[1] + 0.02), lerp(80, 10, curl))
        if curl > 0.9:
            E.dust_puff(p, (man.x + 0.28, 1.75), t, 35 + int(rep) * 0.7, r=0.14,
                        n=3, color=(225, 225, 228))
        return

    if t < 43.4:
        # SHOT B — push-ups
        cam.x, cam.y, cam.view_h = 0.15, 0.95, 2.7
        k = seg(t, 39.2, 43.4)
        man = Pose(x=0.15, y=0.55, facing=1, thickness=1.04 + 0.12 * k)
        down = 0.5 - 0.5 * math.cos((t - 39.2) * 3.4)
        man.y -= down * 0.16
        man.lean = 88
        man.hip_l, man.kn_l = -58, -14
        man.hip_r, man.kn_r = -52, -12
        man.sh_l, man.el_l = -4 + down * 26, -2 + down * 20
        man.sh_r, man.el_r = 2 + down * 26, -4 + down * 20
        man.eye, man.mouth, man.brow = "squint", "grit", "angry"
        draw_stickman(p, man)
        return

    if t < 47.6:
        # SHOT C — running with speed lines
        cam.view_h = 3.4
        k = seg(t, 43.4, 47.6)
        x = lerp(-2.3, 1.6, k)
        cam.x = x + 0.55
        cam.y = 1.30
        man = walk_pose(t, x0=x, t_start=43.4, speed=2.2, thickness=1.10 + 0.12 * k,
                        amp=1.12, stride=1.28, mood="confident")
        man.eye, man.mouth, man.brow = "squint", "open", "angry"
        draw_stickman(p, man)
        E.speed_lines(p, (x - 1.15, 1.35), count=6, length=1.15)
        E.speed_lines(p, (x - 1.3, 0.75), count=4, length=0.9)
        return

    if t < 51.8:
        # SHOT D — pull-ups
        cam.x, cam.y, cam.view_h = 0.45, 1.85, 3.3
        k = seg(t, 47.6, 51.8)
        rep = (t - 47.6) * 0.82
        up = 0.5 - 0.5 * math.cos(rep * math.pi * 2)
        man = Pose(x=0.45, y=1.27 + up * 0.42, facing=1,
                   thickness=1.14 + 0.12 * k)
        man.sh_l, man.el_l = 172, -10
        man.sh_r, man.el_r = 178, -6
        man.hip_l, man.kn_l = 10, -30
        man.hip_r, man.kn_r = 6, -36
        man.eye, man.mouth, man.brow = "squint", "grit", "angry"
        draw_stickman(p, man)
        p.line((0.45 - 0.85, 2.52), (0.45 + 0.85, 2.52), 0.05)
        return

    if t < 55.0:
        # SHOT E — the flex. body changed. glints.
        cam.x, cam.y, cam.view_h = 0.35, 1.35, 3.15
        man = Pose(x=0.35, y=HIP_H, facing=1, thickness=1.38)
        man.sh_l, man.el_l = -104, -72
        man.sh_r, man.el_r = 104, 72
        man.hip_l, man.kn_l = -16, -8
        man.hip_r, man.kn_r = 16, 8
        man.eye, man.mouth, man.brow = "big", "grin", "raise"
        draw_stickman(p, man)
        for i, (dx, dy, ph) in enumerate(((-0.62, 1.62, 0), (0.62, 1.62, 1.7),
                                          (0.0, 2.05, 3.1))):
            E.sparkle(p, (man.x + dx, dy), 0.17, t, phase=ph)
        return

    if t < 58.6:
        # RETURN — walks back to the box, confident
        cam.x, cam.y, cam.view_h = lerp(0.9, -0.35, ease_in_out(seg(t, 55, 58.6))), 1.25, 3.4
        x = lerp(2.15, BOX_X - 1.05, ease_in_out(seg(t, 55, 58.6)))
        man = walk_pose(t, x0=x, t_start=55, speed=0.89, thickness=1.38,
                        mood="confident")
        man.eye, man.mouth, man.brow = "open", "smile", "raise"
        draw_box(p, box)
        draw_stickman(p, man)
        return

    if t < 59.6:
        # ATTEMPT — one easy pull… nothing.
        k = seg(t, 58.6, 59.35)
        man = Pose(x=BOX_X - 1.05 + 0.15 * k, y=HIP_H, facing=1, thickness=1.38)
        man.lean = lerp(6, -12, ease_in_out(k))
        man.sh_l, man.el_l = lerp(30, 86, ease_in_out(k)), lerp(60, 24, k)
        man.sh_r, man.el_r = 8, 44
        man.hip_l, man.kn_l = 12, -14
        man.eye, man.mouth, man.brow = "open", "smile", "raise"
        if t > 59.35:  # hand slips off
            sl = ease_out(seg(t, 59.35, 59.6))
            man.lean = lerp(-12, 8, sl)
            man.sh_l, man.el_l = lerp(86, 20, sl), lerp(24, 80, sl)
        draw_box(p, box)
        draw_stickman(p, man)
        return

    # 59.6–60 — the freeze. the smile dies.
    man = Pose(x=BOX_X - 0.90, y=HIP_H, facing=1, thickness=1.38)
    man.lean = 4
    man.sh_l, man.el_l = 18, 76
    man.sh_r, man.el_r = 4, 42
    man.eye, man.mouth, man.brow = "dot", "flat", "none"
    man.look = (0.5, -0.2)
    draw_box(p, box)
    draw_stickman(p, man)
    E.sweat_drop(p, (man.x + 0.34, 1.78), t, 59.62)


# ----------------------------------------------------------------------------
# SCENE 5 — ANGER (60–80) dynamic camera
# ----------------------------------------------------------------------------
def scene5(t, p: Painter, cam: Camera):
    box = Box(x=BOX_X, y=0, size=BOX_S)

    if t < 63.6:
        # overhead grab → HURL. camera whips after the box.
        k = seg(t, 60, 61.6)
        man = Pose(x=BOX_X - 1.02, y=HIP_H, facing=1, thickness=1.38)
        man.eye, man.mouth, man.brow = "angry", "shout", "angry"
        if t < 61.6:
            cam.x, cam.y, cam.view_h = -0.35, 1.75, 3.6
            man.sh_l, man.el_l = lerp(20, 172, ease_in_out(k)), lerp(60, -12, k)
            man.sh_r, man.el_r = lerp(6, 178, ease_in_out(k)), lerp(40, -8, k)
            man.lean = lerp(6, -10, k)
            bx, by = BOX_X - 0.62, lerp(1.15, 2.42, ease_in_out(k))
            box.x, box.y = bx, by
            box.held = True
            box.glow = 0.5
            draw_box(p, box)
            draw_stickman(p, man)
            return
        # release at 61.6 — parabola to the right, then it lands and settles
        dt = t - 61.6
        vx, vy, g = 2.23, 2.6, 6.2
        t_land = (vy + math.sqrt(vy * vy + 2 * g * 2.42)) / g
        if dt < t_land:
            bx = BOX_X - 0.62 + vx * dt
            by = 2.42 + vy * dt - 0.5 * g * dt * dt
            landed = False
        else:
            bx = BOX_X - 0.62 + vx * t_land
            tl = dt - t_land
            by = abs(math.sin(tl * 9)) * 0.62 * math.exp(-tl * 3.2)
            landed = True
        box.x, box.y = bx, max(0, by)
        box.held = False
        cam.x = lerp(-0.35, clamp(bx + 0.2, -0.35, 3.2), ease_out(clamp(dt / 0.55)))
        cam.y = lerp(1.75, clamp(by * 0.72 + 0.95, 1.35, 2.85), ease_out(clamp(dt / 0.55)))
        cam.view_h = 3.6
        draw_box(p, box)
        # man recoils after the throw
        man = Pose(x=BOX_X - 1.05, y=HIP_H, facing=1, thickness=1.38)
        man.lean = 14
        man.sh_l, man.el_l = 128, -24
        man.sh_r, man.el_r = 112, -18
        man.eye, man.mouth, man.brow = "angry", "shout", "angry"
        draw_stickman(p, man)
        if abs(t - (61.6 + t_land)) < 0.12:
            E.star_burst(p, (bx, 0.40), 0.55, t, 61.6 + t_land)
            E.dust_puff(p, (bx, 0.15), t, 61.6 + t_land, r=0.5)
        return

    box.x, box.y = THROW_X, 0

    if t < 67.7:
        # HAMMER
        cam.x, cam.y, cam.view_h = THROW_X - 1.0, 1.5, 3.6
        man = Pose(x=THROW_X - 1.28, y=HIP_H, facing=1, thickness=1.38)
        man.eye, man.mouth, man.brow = "angry", "shout", "angry"
        if t < 65.45:
            k = seg(t, 63.6, 65.1)
            man.sh_l, man.el_l = lerp(20, 168, ease_in_out(k)), lerp(40, -18, k)
            man.sh_r, man.el_r = lerp(6, 176, ease_in_out(k)), lerp(30, -14, k)
            man.lean = lerp(8, -12, k)
            draw_stickman(p, man)
            pts = stickman_points(man)
            _, _, wr = pts["arm_front"]
            draw_hammer(p, (wr[0] + 0.12, wr[1] + 0.1), -95 + 25 * k)
            draw_box(p, box)
        elif t < 66.1:
            k = seg(t, 65.45, 65.62)  # the slam
            ang = lerp(-70, 8, ease_in(k))
            man.sh_l, man.el_l = lerp(168, 92, ease_in(k)), lerp(-18, 26, k)
            man.sh_r, man.el_r = lerp(176, 82, ease_in(k)), lerp(-14, 22, k)
            man.lean = lerp(-12, 26, ease_in(k))
            draw_stickman(p, man)
            pts = stickman_points(man)
            _, _, wr = pts["arm_front"]
            draw_hammer(p, (wr[0] + 0.22, wr[1] - 0.12), ang)
            draw_box(p, box)
            E.flash_frame(p, t, 65.62, peak=0.8, dur=0.1)
            E.star_burst(p, (THROW_X - 0.15, 0.52), 0.68, t, 65.62)
        else:
            # recoil — hammer flies off, he stumbles
            k = seg(t, 66.1, 67.7)
            man.x += 0.16 * math.sin((t - 66.1) * 7) * (1 - k)
            man.lean = lerp(26, -6, ease_out(k))
            man.sh_l, man.el_l = lerp(92, -30, ease_out(k)), lerp(26, 40, k)
            man.sh_r, man.el_r = lerp(82, -20, ease_out(k)), lerp(22, 36, k)
            man.eye, man.mouth, man.brow = "wide", "o", "angry"
            draw_stickman(p, man)
            hk = seg(t, 66.1, 67.0)
            hx = lerp(THROW_X - 0.6, THROW_X - 2.6, ease_out(hk))
            hy = lerp(0.9, 0.05, ease_in(hk))
            draw_hammer(p, (hx, hy), lerp(30, 96, hk))
            draw_box(p, box)
        return

    if t < 71.8:
        # STONE dropped from the sky
        cam.x, cam.y, cam.view_h = THROW_X - 0.9, 1.8, 4.6
        man = Pose(x=THROW_X - 1.55, y=HIP_H, facing=1, thickness=1.38)
        man.eye, man.mouth, man.brow = "wide", "o", "raise"
        man.head_tilt = -26
        man.look = (0.1, 1)
        man.sh_l, man.el_l = -128, 26
        man.sh_r, man.el_r = -112, 22
        draw_box(p, box)
        if t < 69.85:
            k = ease_in(seg(t, 67.7, 69.85))
            sy = lerp(6.4, 0.48, k)
            draw_stone(p, (THROW_X, sy), 0.62)
            draw_stickman(p, man)
        elif t < 71.0:
            E.flash_frame(p, t, 69.85, peak=0.75, dur=0.12)
            E.star_burst(p, (THROW_X, 0.62), 0.9, t, 69.85)
            # two halves slide apart
            hk = ease_out(seg(t, 69.85, 70.6))
            draw_stone(p, (THROW_X - 0.98 * hk, 0.34), 0.42, seed=5)
            draw_stone(p, (THROW_X + 1.02 * hk, 0.32), 0.42, seed=9)
            draw_stickman(p, man)
            E.dust_puff(p, (THROW_X, 0.2), t, 69.85, r=0.9, n=9)
        else:
            draw_stone(p, (THROW_X - 0.98, 0.34), 0.42, seed=5)
            draw_stone(p, (THROW_X + 1.02, 0.32), 0.42, seed=9)
            draw_stickman(p, man)
        draw_box(p, box)
        return

    if t < 76.2:
        # JUMP ATTACK — he misses the box and eats the ground
        cam.view_h = 4.2
        if t < 73.0:
            cam.x, cam.y = THROW_X - 0.9, 1.25
            k = seg(t, 71.8, 72.7)
            man = Pose(x=THROW_X - 1.5, y=HIP_H - 0.28 * ease_in_out(k),
                       facing=1, thickness=1.38)
            man.lean = lerp(6, 30, k)
            man.hip_l, man.kn_l = lerp(10, 52, k), lerp(-12, -86, k)
            man.hip_r, man.kn_r = lerp(-10, 44, k), lerp(-10, -80, k)
            man.sh_l, man.el_l = lerp(10, -60, k), lerp(30, 44, k)
            man.sh_r, man.el_r = lerp(4, -70, k), lerp(24, 40, k)
            man.eye, man.mouth, man.brow = "angry", "shout", "angry"
            draw_box(p, box)
            draw_stickman(p, man)
        elif t < 74.25:
            k = seg(t, 73.0, 74.25)
            x = lerp(THROW_X - 1.5, THROW_X - 0.15, ease_in_out(k))
            y = lerp(HIP_H - 0.28, HIP_H + 1.72, math.sin(k * math.pi))
            cam.x, cam.y = x + 0.25, clamp(y * 0.55 + 0.9, 1.3, 2.7)
            man = Pose(x=x, y=y, facing=1, thickness=1.38)
            man.lean = lerp(30, -38, k)
            man.hip_l, man.kn_l = lerp(52, -34, k), lerp(-86, -58, k)
            man.hip_r, man.kn_r = lerp(44, -28, k), lerp(-80, -52, k)
            man.sh_l, man.el_l = lerp(-60, -160, k), lerp(44, -20, k)
            man.sh_r, man.el_r = lerp(-70, -170, k), lerp(40, -16, k)
            man.eye, man.mouth, man.brow = "angry", "shout", "angry"
            draw_box(p, box)
            draw_stickman(p, man)
        else:
            # crash — the box slides, he doesn't
            cam.x, cam.y = THROW_X - 0.55, 1.35
            k = seg(t, 74.25, 76.2)
            man = Pose(x=THROW_X - 0.2 + 0.25 * ease_out(clamp(k * 2)),
                       y=lerp(HIP_H + 0.2, 0.16, ease_in(clamp(k * 2.6))),
                       facing=1, thickness=1.38)
            man.head_dy = -0.16 * ease_in(clamp(k * 2.6))
            man.lean = lerp(-38, 82, ease_in(clamp(k * 2.6)))
            man.hip_l, man.kn_l = lerp(-34, -84, ease_in(clamp(k * 2.6))), lerp(-58, -6, k)
            man.hip_r, man.kn_r = lerp(-28, -78, ease_in(clamp(k * 2.6))), lerp(-52, -4, k)
            man.sh_l, man.el_l = lerp(-160, 172, ease_in(clamp(k * 2.2))), lerp(-20, -6, k)
            man.sh_r, man.el_r = lerp(-170, 160, ease_in(clamp(k * 2.2))), lerp(-16, -4, k)
            man.eye = "wide" if k < 0.25 else "shut"
            man.mouth, man.brow = "o", "raise"
            draw_box(p, box)
            draw_stickman(p, man)
            E.flash_frame(p, t, 74.45, peak=0.55, dur=0.1)
            E.star_burst(p, (man.x + 0.55, 0.8), 0.55, t, 74.45)
            E.dust_puff(p, (man.x + 0.1, 0.12), t, 74.5, r=0.7, n=8)
        return

    # 76.2–80 — exhausted. sitting. staring.
    cam.x, cam.y, cam.view_h = lerp(THROW_X - 0.85, THROW_X - 1.25, seg(t, 76.2, 80)), 1.35, lerp(3.4, 4.4, seg(t, 78, 80))
    man = sit_pose(THROW_X - 1.45, t=t, head_low=lerp(0.25, 0.55, seg(t, 76.2, 80)),
                   thickness=1.38)
    if t < 78.2:
        man.y += 0.035 * math.sin(t * 7.5)      # chest heaving
        man.eye, man.mouth, man.brow = "dot", "open", "sad"
    else:
        man.eye, man.mouth, man.brow = "dot", "flat", "sad"
    man.look = (0.8, -0.4)
    draw_box(p, box)
    draw_stickman(p, man)
    if t < 77.6:
        E.sweat_drop(p, (man.x + 0.42, 1.62), t, 76.6)
        E.sweat_drop(p, (man.x + 0.30, 1.70), t, 77.1)


# ----------------------------------------------------------------------------
# SCENE 6 — LOWEST POINT (80–100) wide, rain, stillness
# ----------------------------------------------------------------------------
def scene6(t, p: Painter, cam: Camera):
    cam.x = lerp(THROW_X - 1.15, THROW_X - 0.95, seg(t, 80, 100))
    cam.y = 1.25
    cam.view_h = lerp(5.6, 6.9, ease_in_out(seg(t, 80, 90)))

    box = Box(x=THROW_X, y=0, size=BOX_S)
    head_low = lerp(0.55, 1.0, seg(t, 80, 87))
    breathe = 1.0 if t < 88 else 0.35
    man = sit_pose(THROW_X - 1.45, t=t, head_low=head_low, thickness=1.38,
                   breathe=breathe)
    man.eye, man.mouth, man.brow = "dot", "frown" if t > 86 else "flat", "sad"
    man.look = (0.8, -0.6)
    if t > 98.0:
        man.head_dy += 0.025 * seg(t, 98, 100)   # head lifts a hair
    draw_box(p, box)
    draw_stickman(p, man)

    # wet ground reflections — soft vertical smudges
    if t > 83:
        a = smoothstep(seg(t, 83, 87)) * 0.5
        col = mix(WHITE, (196, 203, 212), a)
        p.ellipse((man.x + 0.1, 0.012), 0.62, 0.085, fill=col)
        p.ellipse((THROW_X + 0.05, 0.012), 0.58, 0.08, fill=col)


# ----------------------------------------------------------------------------
# SCENE 7 — THE DISCOVERY (100–120) close-up
# ----------------------------------------------------------------------------
def scene7(t, p: Painter, cam: Camera):
    box = Box(x=THROW_X, y=0, size=BOX_S)
    btn = (THROW_X + 0.375, 0.205)          # tiny button on the side face

    if t < 104.2:
        # water runs down the side… and glints on something
        cam.x = THROW_X - 0.05
        cam.y = 0.62
        cam.view_h = 1.55
        box.button = smoothstep(seg(t, 100.5, 101.4))
        draw_box(p, box)
        # rain streaks on the box top
        for i in range(4):
            E.rain_splash(p, (THROW_X - 0.22 + i * 0.15, 0.53 + 0.02 * (i % 2)),
                          t, i * 0.17, r=0.055)
        # sliding water line down the right face
        wk = ((t - 100) * 0.55) % 1.0
        p.line((THROW_X + 0.25, 0.49 - wk * 0.42), (THROW_X + 0.265, 0.42 - wk * 0.42),
               0.016, color=(150, 178, 196))
        if t > 103.4:
            E.sparkle(p, btn, 0.13, t, phase=1.0)
        # him, small in the frame above — head turns
        man = sit_pose(THROW_X - 1.12, t=t, head_low=0.35, thickness=1.38)
        man.eye, man.mouth, man.brow = "dot", "flat", "sad"
        if t > 103.6:
            man.look, man.head_tilt = (1, 0.2), -10
            man.eye, man.mouth, man.brow = "open", "o", "raise"
        draw_stickman(p, man)
        return

    if t < 113.0:
        # slow push-in on the button; his finger creeps in
        k = ease_in_out(seg(t, 104.2, 112.6))
        cam.view_h = lerp(1.55, 0.82, k)
        cam.x = lerp(THROW_X - 0.05, btn[0] - 0.12, k)
        cam.y = lerp(0.62, 0.32, k)
        box.button = 1.0
        draw_box(p, box)
        if t > 107.0:
            fk = ease_in_out(seg(t, 107.0, 112.8))
            tremble = 0.008 * math.sin(t * 17) if t > 110 else 0
            tip = (lerp(btn[0] + 1.35, btn[0] + 0.10, fk) + tremble,
                   lerp(0.62, btn[1] + 0.015, fk))
            back = (tip[0] + 1.35, tip[1] + 0.55)
            draw_finger(p, tip, back, width=0.17)
        return

    if t < 115.2:
        # CLICK.
        cam.view_h = 0.82
        cam.x = btn[0] - 0.12
        cam.y = 0.32
        box.button = 1.0
        box.press = smoothstep(seg(t, 113.0, 113.4))
        draw_box(p, box)
        fk = seg(t, 113.0, 113.35)
        tip = (lerp(btn[0] + 0.10, btn[0] + 0.015, fk), btn[1] + 0.015)
        draw_finger(p, tip, (tip[0] + 1.35, tip[1] + 0.55), width=0.17)
        E.ripple_ring(p, btn, t, 113.3, r0=0.03, r1=0.42)
        return

    if t < 117.3:
        # silence. the finger withdraws. nothing happens…
        cam.view_h = lerp(0.82, 1.15, seg(t, 115.2, 117.3))
        cam.x = btn[0] - 0.12
        cam.y = lerp(0.32, 0.42, seg(t, 115.2, 117.3))
        box.button, box.press = 1.0, 1.0
        draw_box(p, box)
        if t < 116.4:
            fk = seg(t, 115.2, 116.3)
            tip = (lerp(btn[0] + 0.015, btn[0] + 1.3, ease_out(fk)),
                   lerp(btn[1] + 0.015, 0.75, ease_out(fk)))
            draw_finger(p, tip, (tip[0] + 1.35, tip[1] + 0.55), width=0.17)
        return

    # 117.3–120 — the lid unlatches… and light spills out
    k = seg(t, 117.3, 118.1)
    cam.view_h = lerp(1.15, 1.5, seg(t, 117.3, 120))
    cam.x = lerp(btn[0] - 0.12, THROW_X - 0.1, seg(t, 117.3, 119))
    cam.y = lerp(0.42, 0.68, seg(t, 117.3, 120))
    box.button, box.press = 1.0, 1.0
    box.glow = clamp(seg(t, 117.3, 118.0))
    if t < 118.4:
        box.lid = 0.10 * ease_out(seg(t, 117.3, 118.4))
        draw_box(p, box, light_rays=0.55 * seg(t, 117.3, 118.4))
    else:
        box.lid = lerp(0.10, 1.0, ease_in_out(seg(t, 118.4, 119.4)))
        box.mirror = smoothstep(seg(t, 118.7, 119.6))
        draw_box(p, box, light_rays=lerp(0.55, 1.0, seg(t, 118.4, 119.2)))
    E.light_rays_burst(p, (THROW_X, 0.62), t, 118.4, length=2.2)

    # cut to his face — pure shock
    if t > 119.55:
        cam.x = THROW_X - 1.1
        cam.y = 1.5
        cam.view_h = 1.25
        man = Pose(x=THROW_X - 1.1, y=HIP_H, facing=1, thickness=1.38)
        man.eye, man.mouth, man.brow = "wide", "o", "raise"
        man.look = (1, 0.15)
        man.sh_l, man.el_l = 8, 20
        man.sh_r, man.el_r = -6, 16
        draw_stickman(p, man)
        p.overlay_alpha(WARM_PALE, 0.16)


# ----------------------------------------------------------------------------
# SCENE 8 — INSIDE (120–140) stylised top shot
# ----------------------------------------------------------------------------
def draw_topview(p: Painter, t, smile=0.0, nod=0.0, hand_chest=0.0):
    """Camera above: the open box, the mirror, and him leaning over it."""
    cx, cy = THROW_X, 0.55
    s = 0.92
    # box body (top view): square with a soft inner rim
    p.rect((cx - s / 2, cy - s / 2), (cx + s / 2, cy + s / 2),
           fill=(243, 241, 235), outline=INK, width=0.03)
    p.rect((cx - s / 2 - 0.10, cy - s / 2 - 0.10),
           (cx + s / 2 + 0.10, cy + s / 2 + 0.10),
           outline=INK, width=0.022)
    # open lid flipped back (top edge)
    p.poly([(cx - s / 2, cy + s / 2), (cx + s / 2, cy + s / 2),
            (cx + s / 2 + 0.18, cy + s / 2 + 0.42),
            (cx - s / 2 - 0.18, cy + s / 2 + 0.42)],
           fill=(250, 248, 242), outline=INK, width=0.028)
    # the mirror inside
    mx0, mx1 = cx - s * 0.36, cx + s * 0.36
    my0, my1 = cy - s * 0.36, cy + s * 0.36
    for i in range(7):
        yy0 = lerp(my0, my1, i / 7)
        yy1 = lerp(my0, my1, (i + 1) / 7)
        p.rect((mx0, yy0), (mx1, yy1), fill=mix(MIRROR_BOT, MIRROR_TOP, i / 6))
    p.rect((mx0, my0), (mx1, my1), outline=INK, width=0.026)
    for k in range(2):
        sx = lerp(mx0, mx1, 0.22 + 0.34 * k)
        p.poly([(sx, my1), (sx + 0.14, my1), (sx + 0.02, my0), (sx - 0.12, my0)],
               fill=(246, 251, 253))

    # his reflection, looking up out of the mirror
    rr = s * 0.21
    fx, fy = cx, cy + 0.02
    p.circle((fx, fy), rr, fill=(252, 253, 253), outline=INK, width=0.022)
    p.circle((fx - rr * 0.32, fy + rr * 0.18), rr * 0.16, fill=INK)
    p.circle((fx + rr * 0.32, fy + rr * 0.18), rr * 0.16, fill=INK)
    if smile > 0:
        p.arc((fx, fy - rr * 0.02), rr * 0.42, rr * 0.36 * (0.6 + 0.6 * smile),
              20, 160, width=0.022)
    else:
        p.line((fx - rr * 0.22, fy - rr * 0.38), (fx + rr * 0.22, fy - rr * 0.38),
               0.02)

    # him: head + shoulders entering from the bottom of the frame
    hy = cy - s * 1.28 - nod * 0.10
    p.circle((cx, hy + 0.52), 0.34, fill=WHITE, outline=INK, width=0.05)
    p.line((cx, hy + 0.22), (cx, hy + 0.42), 0.075)
    p.line((cx, hy + 0.22), (cx - 0.55, hy + 0.55), 0.062)
    p.line((cx, hy + 0.22), (cx + 0.55, hy + 0.55), 0.062)
    if hand_chest > 0:
        p.line((cx - 0.55, hy + 0.55), (cx - 0.22 + 0.2 * (1 - hand_chest),
                                        hy + 0.30), 0.058)
    # soft warm bloom around the mirror
    p.ellipse((cx, cy), s * 0.95 + 0.06 * math.sin(t * 1.7), s * 0.80,
              outline=mix(WHITE, WARM, 0.30), width=0.05)


def scene8(t, p: Painter, cam: Camera):
    cam.x, cam.y = THROW_X, 0.42
    cam.view_h = lerp(1.75, 2.55, ease_in_out(seg(t, 120, 124)))
    smile = smoothstep(seg(t, 133.5, 135.2))
    nod = math.sin(seg(t, 136.2, 138.4) * math.pi) * 0.6 if t > 136.2 else 0
    hand = smoothstep(seg(t, 129.2, 131.0)) * (1 - smoothstep(seg(t, 134.0, 135.6)))
    draw_topview(p, t, smile=smile, nod=nod, hand_chest=hand)
    if 129.0 < t < 130.2:
        E.sparkle(p, (THROW_X - 0.62, 1.28), 0.16, t, phase=0.5)
    if t > 137.2:
        p.overlay_alpha(WARM_PALE, 0.10)


# ----------------------------------------------------------------------------
# SCENE 9 — ENDING (140–160) slow pull back
# ----------------------------------------------------------------------------
def scatter_boxes():
    """The field of boxes — deterministic, spread out, drawn when near the view."""
    rng = random.Random(2024)
    xs = [THROW_X + rng.uniform(-30, 32) for _ in range(240)]
    xs.sort()
    out = []
    last = None
    for x in xs:
        if last is not None and x - last < 1.05:
            continue
        last = x
        out.append((x, rng.uniform(-0.22, 0.10), BOX_S * rng.uniform(0.85, 1.18)))
    return out


FIELD = None


def scene9(t, p: Painter, cam: Camera):
    global FIELD
    if FIELD is None:
        FIELD = scatter_boxes()

    box = Box(x=THROW_X, y=0, size=BOX_S)

    if t < 143.2:
        # close the lid, pat it — thank you, next
        cam.x = lerp(THROW_X - 0.75, THROW_X - 0.45, ease_in_out(seg(t, 140, 143.2)))
        cam.y = 1.15
        cam.view_h = 3.2
        k = ease_in_out(seg(t, 140, 141.2))
        box.lid = 1 - k
        box.mirror = 1 - k
        box.button, box.press = 1.0, 0.0
        man = Pose(x=THROW_X - 0.95, y=HIP_H, facing=1, thickness=1.38)
        man.lean = 12 * k
        man.sh_l, man.el_l = lerp(30, 62, k), lerp(40, 22, k)
        man.sh_r, man.el_r = 8, 36
        man.eye, man.mouth, man.brow = "happy", "smile", "none"
        man.look = (0.5, -0.5)
        if t > 141.4:
            pat = 0.05 * max(0.0, math.sin((t - 141.4) * 7)) * \
                (1 - seg(t, 142.2, 143.0))
            man.sh_l, man.el_l = 62 - pat * 300, 22 + pat * 300
            box.y = -pat * 0.6
        draw_box(p, box)
        draw_stickman(p, man)
        return

    # one continuous walk — the camera starts easing out and never stops
    x = lerp(THROW_X - 0.95, THROW_X + 5.0, seg(t, 143.2, 157.2))
    man = walk_pose(t, x0=x, t_start=143.2, speed=0.30, thickness=1.38,
                    mood="confident")
    man.eye, man.mouth, man.brow = "happy", "smile", "none"

    if t < 151.0:
        cam.x = lerp(THROW_X - 0.45, THROW_X + 1.25, ease_in_out(seg(t, 143.2, 151)))
        cam.y = 1.15
        cam.view_h = lerp(3.2, 4.6, ease_in_out(seg(t, 147, 151)))
        draw_box(p, box)
        draw_stickman(p, man)
        return

    # 151–157.2 — pull back… and the world fills with boxes
    cam.x = lerp(THROW_X + 1.25, THROW_X + 3.75, ease_in_out(seg(t, 151, 157.2)))
    cam.y = 1.55
    cam.view_h = lerp(4.6, 15.5, ease_in_out(seg(t, 151, 157.2)))
    for bx, by, bs in FIELD:
        if abs(bx - cam.x) < cam.view_h * (W / H) * 0.62 + 1.5:
            draw_box(p, Box(x=bx, y=by, size=bs))
    draw_box(p, box)
    draw_stickman(p, man)
    p.vignette_to_white(0.30 * seg(t, 155.6, 157.2))


# ----------------------------------------------------------------------------
# FINAL TABLEAU + END CARD
# ----------------------------------------------------------------------------
def tableau(t, p: Painter, cam: Camera):
    cam.x, cam.y, cam.view_h = 0.2, 1.15, 4.4
    box = Box(x=-1.15, y=0, size=BOX_S)
    draw_box(p, box)
    man = walk_pose(157.2, x0=0.25, t_start=156.4, speed=0.30, thickness=1.0,
                    mood="confident")
    man.eye, man.mouth = "happy", "smile"
    draw_stickman(p, man)
    draw_arrow(p, 1.45, 3.35, 1.32, width=0.16)

    # the film fades to white… and THE END stays
    veil = smoothstep(seg(t, 158.75, 159.45))
    if veil > 0:
        p.overlay_alpha(WHITE, veil)
    a = smoothstep(seg(t, 158.3, 158.95)) * 0.88
    if a > 0:
        col = mix(WHITE, INK, a)
        p.text((0.2, 2.62), "THE END", 0.52, color=col, tracking=0.16)


# ----------------------------------------------------------------------------
# master frame renderer
# ----------------------------------------------------------------------------
IMPACTS = [
    (8.42, 5), (27.25, 4), (31.95, 6), (62.997, 9), (65.62, 11),
    (69.85, 13), (74.45, 10),
]


def apply_shakes(cam: Camera, t):
    for t0, amp in IMPACTS:
        dt = t - t0
        if 0 <= dt < 1.1:
            decay = math.exp(-dt * 6.5)
            cam.shake_x += amp * decay * math.sin(dt * 28 * 2 * math.pi)
            cam.shake_y += amp * 0.6 * decay * math.cos(dt * 36 * 2 * math.pi)
def draw(t: float) -> Image.Image:
    t = clamp(t, 0, TOTAL - 1e-3)
    frame = int(round(t * FPS))
    cam = Camera()
    p = Painter(cam)

    apply_shakes(cam, t)

    grey, clouds, rain, ground = env_amounts(t)
    E.draw_background(p, grey, frame)
    E.draw_clouds(p, clouds, t)
    if ground > 0.01 and t < 157.2:
        E.draw_ground_dark(p, ground)

    if t < 10:
        scene1(t, p, cam)
    elif t < 20:
        scene2(t, p, cam)
    elif t < 35:
        scene3(t, p, cam)
    elif t < 60:
        scene4(t, p, cam)
        for cut in (39.2, 43.4, 47.6, 51.8, 55.0):
            E.flash_frame(p, t, cut, peak=0.32, dur=0.07)
    elif t < 80:
        scene5(t, p, cam)
    elif t < 100:
        scene6(t, p, cam)
    elif t < 120:
        scene7(t, p, cam)
    elif t < 140:
        scene8(t, p, cam)
    elif t < 157.2:
        scene9(t, p, cam)
    else:
        tableau(t, p, cam)

    if rain > 0.01:
        E.draw_rain(p, rain, frame)

    return p.finish()
