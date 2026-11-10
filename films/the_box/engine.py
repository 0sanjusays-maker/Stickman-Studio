"""THE BOX — procedural animation engine.

World units: stickman ≈ 1.8 units tall, ground at y = 0, +y is up, +x is right.
Camera shows `view_h` world units vertically; everything draws through a Painter
that converts world coordinates to supersampled screen pixels.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------------------
# Global specs
# ----------------------------------------------------------------------------
W, H = 1280, 720          # output resolution
SS = 2                    # supersampling factor
FPS = 24

INK = (24, 24, 28)
WHITE = (255, 255, 255)
GREY_BG_TOP = (223, 227, 233)
GREY_BG_BOT = (199, 205, 213)
CLOUD_A = (206, 212, 220)
CLOUD_B = (222, 227, 233)
RAIN_COL = (150, 163, 176)
WARM = (255, 214, 120)
WARM_PALE = (255, 238, 190)
GLOW_YEL = (255, 224, 130)
MIRROR_TOP = (236, 246, 250)
MIRROR_BOT = (188, 210, 222)

FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ----------------------------------------------------------------------------
# Math / easing helpers
# ----------------------------------------------------------------------------
def clamp(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_in(t):
    t = clamp(t)
    return t * t * t


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return t * t * t * (t * (t * 6 - 15) + 10)


def seg(t, t0, t1):
    """Normalised progress of t inside [t0, t1] (clamped)."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return clamp((t - t0) / (t1 - t0))


def substep(t, t0, t1, fn=smoothstep):
    """Interpolate 0→1 across [t0,t1] with easing fn."""
    return fn(seg(t, t0, t1))


def mix(a, b, t):
    """Blend colour tuples of equal length → ints for PIL."""
    return tuple(int(round(lerp(a[i], b[i], t))) for i in range(len(a)))


def rot(px, py, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return px * c - py * s, px * s + py * c


# ----------------------------------------------------------------------------
# Camera
# ----------------------------------------------------------------------------
@dataclass
class Camera:
    x: float = 0.0          # world x at screen centre
    y: float = 1.0          # world y at screen centre
    view_h: float = 4.0     # world units visible vertically
    shake_x: float = 0.0
    shake_y: float = 0.0

    def scale(self):
        return H * SS / self.view_h

    def w2s(self, wx, wy):
        s = self.scale()
        cx = W * SS / 2 + self.shake_x * SS
        cy = H * SS / 2 + self.shake_y * SS
        return cx + (wx - self.x) * s, cy - (wy - self.y) * s

    def wpix(self, w):
        """World length -> supersampled pixels."""
        return max(1, int(round(w * self.scale())))


def add_shake(cam: Camera, amp, t, t0, freq=28.0):
    """Decaying camera shake starting at t0."""
    dt = t - t0
    if dt < 0:
        return
    decay = math.exp(-dt * 6.5)
    cam.shake_x = amp * decay * math.sin(dt * freq * 2 * math.pi)
    cam.shake_y = amp * 0.6 * decay * math.cos(dt * freq * 2 * math.pi * 1.3)


# ----------------------------------------------------------------------------
# Painter: world-space drawing on a supersampled canvas
# ----------------------------------------------------------------------------
class Painter:
    def __init__(self, cam: Camera):
        self.cam = cam
        self.img = Image.new("RGB", (W * SS, H * SS), WHITE)
        self.d = ImageDraw.Draw(self.img)

    # -- primitives -----------------------------------------------------
    def line(self, p0, p1, width=0.035, color=INK, cap_joint=True):
        s0 = self.cam.w2s(*p0)
        s1 = self.cam.w2s(*p1)
        wpx = self.cam.wpix(width)
        self.d.line([s0, s1], fill=color, width=wpx)
        if cap_joint:
            r = wpx / 2
            for sx, sy in (s0, s1):
                self.d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=color)

    def poly(self, pts, fill=None, outline=None, width=0.02):
        spts = [self.cam.w2s(*p) for p in pts]
        if len(spts) < 3:
            return
        self.d.polygon(spts, fill=fill, outline=outline,
                       width=self.cam.wpix(width) if outline else 0)

    def circle(self, c, r, fill=None, outline=None, width=0.02):
        cx, cy = self.cam.w2s(*c)
        rp = self.cam.wpix(r)
        bbox = [cx - rp, cy - rp, cx + rp, cy + rp]
        self.d.ellipse(bbox, fill=fill, outline=outline,
                       width=self.cam.wpix(width) if outline else 0)

    def ellipse(self, c, rx, ry, fill=None, outline=None, width=0.02):
        cx, cy = self.cam.w2s(*c)
        rxp, ryp = self.cam.wpix(rx), self.cam.wpix(ry)
        bbox = [cx - rxp, cy - ryp, cx + rxp, cy + ryp]
        self.d.ellipse(bbox, fill=fill, outline=outline,
                       width=self.cam.wpix(width) if outline else 0)

    def arc(self, c, rx, ry, a0, a1, color=INK, width=0.03):
        cx, cy = self.cam.w2s(*c)
        rxp, ryp = self.cam.wpix(rx), self.cam.wpix(ry)
        self.d.arc([cx - rxp, cy - ryp, cx + rxp, cy + ryp], a0, a1,
                   fill=color, width=self.cam.wpix(width))

    def rect(self, p0, p1, fill=None, outline=None, width=0.02):
        s0 = self.cam.w2s(*p0)
        s1 = self.cam.w2s(*p1)
        x0, x1 = min(s0[0], s1[0]), max(s0[0], s1[0])
        y0, y1 = min(s0[1], s1[1]), max(s0[1], s1[1])
        self.d.rectangle([x0, y0, x1, y1], fill=fill, outline=outline,
                         width=self.cam.wpix(width) if outline else 0)

    def text(self, world_pos, text, size_world, color=INK, anchor="mm",
             tracking=0.0, font_path=FONT_PATH_BOLD):
        """Draw text; size_world = cap height in world units. Optional tracking."""
        px = self.cam.wpix(size_world)
        try:
            font = ImageFont.truetype(font_path, px)
        except OSError:
            font = ImageFont.load_default()
        cx, cy = self.cam.w2s(*world_pos)
        if tracking <= 0:
            bbox = self.d.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            ox = -tw / 2 if "m" in anchor[0] else 0
            oy = -th / 2 if "m" in anchor[1] else 0
            self.d.text((cx + ox, cy + oy), text, font=font, fill=color)
        else:
            track_px = self.cam.wpix(tracking)
            widths = []
            for ch in text:
                bb = self.d.textbbox((0, 0), ch, font=font)
                widths.append(bb[2] - bb[0])
            total = sum(widths) + track_px * (len(text) - 1)
            x = cx - total / 2
            bbox = self.d.textbbox((0, 0), "ME", font=font)
            th = bbox[3] - bbox[1]
            y = cy - th / 2 - bbox[1]
            for ch, cw in zip(text, widths):
                self.d.text((x, y), ch, font=font, fill=color)
                x += cw + track_px

    def overlay_alpha(self, color, alpha):
        """Flat colour veil (0..1) over the whole frame — cheap 'light' layer."""
        if alpha <= 0.01:
            return
        a = clamp(alpha)
        flat = Image.new("RGB", self.img.size, color)
        self.img = Image.blend(self.img, flat, a)
        self.d = ImageDraw.Draw(self.img)

    def vignette_to_white(self, alpha):
        """Radial fade toward white from the edges (used near the ending)."""
        if alpha <= 0.01:
            return
        import numpy as np
        h, w = self.img.size[1], self.img.size[0]
        yy, xx = np.mgrid[0:h:4, 0:w:4]           # quarter-res mask is plenty
        cx, cy = w / 2, h / 2
        r = np.sqrt(((xx - cx) / (w * 0.72)) ** 2 + ((yy - cy) / (h * 0.72)) ** 2)
        m = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * (255 * clamp(alpha))
        mask = Image.fromarray(m.astype("uint8"), "L").resize((w, h), Image.BILINEAR)
        veil = Image.new("RGB", self.img.size, WHITE)
        self.img.paste(veil, (0, 0), mask)
        self.d = ImageDraw.Draw(self.img)

    def finish(self):
        return self.img.resize((W, H), Image.BOX)


# ----------------------------------------------------------------------------
# Stickman rig
# ----------------------------------------------------------------------------
# Local coordinates: root = hip centre, +y up, character drawn facing +x.
L1, L2 = 0.34, 0.32        # upper arm, forearm
L3, L4 = 0.42, 0.40        # thigh, shin
HIP_H = L3 + L4            # standing hip height (feet at y=0)
TORSO = 0.62               # hip -> shoulder
NECK = 0.12
HEAD_R = 0.21


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0                 # hip height
    facing: int = 1                # +1 right, -1 left
    lean: float = 0.0              # torso tilt (deg, + = forward)
    head_tilt: float = 0.0
    sh_l: float = 8.0              # shoulder angles (0 = down)
    el_l: float = 12.0
    sh_r: float = -8.0
    el_r: float = -12.0
    hip_l: float = 6.0
    kn_l: float = -8.0
    hip_r: float = -6.0
    kn_r: float = 8.0
    thickness: float = 1.0
    eye: str = "open"      # open big dot squint happy shut wide angry
    mouth: str = "neutral"  # neutral smile frown open grit o grin flat shout
    brow: str = "none"      # none raise angry sad
    look: tuple = (0.0, 0.0)
    head_dx: float = 0.0    # extra head offset (side profile tweaks)
    head_dy: float = 0.0
    squash: float = 0.0     # vertical squash/stretch for impacts (− down)


def _joint(origin, ang_deg, length, facing):
    a = math.radians(ang_deg)
    dx = math.sin(a) * length * facing
    dy = -math.cos(a) * length
    return (origin[0] + dx, origin[1] + dy)


def stickman_points(p: Pose):
    """Compute all rig points in world space (back limbs first)."""
    fx = p.facing
    hip = (p.x, p.y)
    stretch = 1.0 + 0.10 * clamp(-p.squash, -1, 1)

    # torso (lean +deg = forward toward facing direction)
    shoulder = _joint(hip, 180 - p.lean, TORSO * stretch, fx)
    neck = _joint(shoulder, 180 - p.lean, NECK * stretch, fx)
    head_c = (
        neck[0] + fx * (0.045 + p.head_dx),
        neck[1] + HEAD_R * 1.02 * stretch + p.head_dy,
    )

    def arm(sh_ang, el_ang):
        sh = shoulder
        el = _joint(sh, sh_ang, L1, fx)
        wr = _joint(el, sh_ang + el_ang, L2, fx)
        return sh, el, wr

    def leg(hip_ang, kn_ang):
        hp = (hip[0] + fx * 0.02, hip[1])
        kn = _joint(hp, hip_ang, L3, fx)
        an = _joint(kn, hip_ang + kn_ang, L4, fx)
        return hp, kn, an

    return {
        "hip": hip,
        "shoulder": shoulder,
        "neck": neck,
        "head": (head_c[0], head_c[1], HEAD_R * stretch),
        "arm_back": arm(p.sh_r, p.el_r),
        "arm_front": arm(p.sh_l, p.el_l),
        "leg_back": leg(p.hip_r, p.kn_r),
        "leg_front": leg(p.hip_l, p.kn_l),
    }


def draw_stickman(painter: Painter, p: Pose):
    pts = stickman_points(p)
    w = 0.052 * p.thickness
    back_w = w * 0.62

    # contact shadow (shrinks as the character leaves the ground)
    alt = max(0.0, p.y - HIP_H)
    if alt < 1.1:
        k = 1.0 / (1.0 + alt * 1.8)
        painter.ellipse((p.x + 0.03, 0.012), 0.42 * k, 0.075 * k,
                        fill=(235, 235, 238))

    # back limbs (thinner = depth)
    for seg_pts in (pts["leg_back"], pts["arm_back"]):
        painter.line(seg_pts[0], seg_pts[1], back_w)
        painter.line(seg_pts[1], seg_pts[2], back_w)

    # front legs
    hp, kn, an = pts["leg_front"]
    painter.line(hp, kn, w)
    painter.line(kn, an, w)

    # torso
    painter.line(pts["hip"], pts["shoulder"], w)
    painter.line(pts["shoulder"], pts["neck"], w * 0.9)

    # head
    hx, hy, hr = pts["head"]
    painter.circle((hx, hy), hr, fill=WHITE, outline=INK, width=w * 0.85)

    # front arm
    sh, el, wr = pts["arm_front"]
    painter.line(sh, el, w)
    painter.line(el, wr, w)

    draw_face(painter, pts, p)


def draw_face(painter: Painter, pts, p: Pose):
    hx, hy, hr = pts["head"]
    fx = p.facing
    lx, ly = p.look
    tilt = p.head_tilt

    eye_sep = 0.088
    eye_y = hy + 0.028
    ex_base = hx + fx * 0.052
    pupil_off = 0.022

    ew = 0.050  # base eye radius

    if p.eye == "happy":
        r = ew * 1.15
        eye_sep = max(eye_sep, r * 2.6)
        for side in (-1, 1):
            ex = ex_base + side * eye_sep * 0.5 * fx + side * 0.012
            painter.arc((ex, eye_y), r, ew * 1.05, 195, 345, color=INK,
                        width=0.030)
    elif p.eye == "shut":
        r = ew * 1.1
        eye_sep = max(eye_sep, r * 2.6)
        for side in (-1, 1):
            ex = ex_base + side * eye_sep * 0.5 * fx + side * 0.012
            painter.arc((ex, eye_y), r, ew * 1.0, 15, 165, color=INK,
                        width=0.030)
    elif p.eye == "squint":
        for side in (-1, 1):
            ex = ex_base + side * eye_sep * 0.5 * fx + side * 0.012
            painter.line((ex - ew * 0.8, eye_y), (ex + ew * 0.8, eye_y), 0.028)
    elif p.eye == "dot":
        for side in (-1, 1):
            ex = ex_base + side * eye_sep * 0.5 * fx + side * 0.012
            painter.circle((ex, eye_y), ew * 0.34, fill=INK)
    elif p.eye in ("wide", "big", "angry"):
        scale = {"wide": 1.55, "big": 1.30, "angry": 0.95}[p.eye]
        r = ew * scale
        eye_sep = max(eye_sep, r * 2.45)
        for side in (-1, 1):
            ex = ex_base + side * eye_sep * 0.5 * fx + side * 0.012
            painter.circle((ex, eye_y), r, fill=WHITE, outline=INK,
                           width=0.022 if p.eye == "wide" else 0.026)
            pr = ew * (0.22 if p.eye == "wide" else 0.42)
            painter.circle((ex + lx * pupil_off * 1.3, eye_y - ly * pupil_off),
                           pr, fill=INK)
    else:  # open
        r = ew
        for side in (-1, 1):
            ex = ex_base + side * eye_sep * 0.5 * fx + side * 0.012
            painter.circle((ex, eye_y), r, fill=WHITE, outline=INK, width=0.026)
            painter.circle((ex + lx * pupil_off, eye_y - ly * pupil_off),
                           ew * 0.45, fill=INK)

    eyes = [(ex_base - eye_sep * 0.5 * fx - 0.012, eye_y),
            (ex_base + eye_sep * 0.5 * fx + 0.012, eye_y)]

    # brows
    brow_y = eye_y + 0.085
    if p.brow == "raise":
        for ex, ey in eyes:
            painter.arc((ex, brow_y + 0.02), 0.055, 0.035, 200, 340,
                        width=0.022)
    elif p.brow == "angry":
        for i, (ex, ey) in enumerate(eyes):
            inner_x = ex - fx * 0.035
            outer_x = ex + fx * 0.045
            painter.line((inner_x, brow_y - 0.028), (outer_x, brow_y + 0.012),
                         0.024)
    elif p.brow == "sad":
        for i, (ex, ey) in enumerate(eyes):
            inner_x = ex - fx * 0.035
            outer_x = ex + fx * 0.045
            painter.line((inner_x, brow_y + 0.012), (outer_x, brow_y - 0.024),
                         0.024)

    # mouth
    mx = hx + fx * 0.10
    my = hy - 0.105
    if p.mouth == "smile":
        painter.arc((mx - 0.005, my + 0.012), 0.075, 0.058, 20, 160, width=0.028)
    elif p.mouth == "grin":
        painter.arc((mx - 0.005, my + 0.03), 0.095, 0.075, 15, 165, width=0.030)
    elif p.mouth == "frown":
        painter.arc((mx - 0.005, my - 0.045), 0.075, 0.058, 200, 340, width=0.028)
    elif p.mouth == "open":
        painter.ellipse((mx, my), 0.052, 0.062, fill=INK)
    elif p.mouth == "shout":
        painter.ellipse((mx, my), 0.062, 0.082, fill=INK)
    elif p.mouth == "o":
        painter.circle((mx, my), 0.032, fill=INK)
    elif p.mouth == "grit":
        painter.ellipse((mx, my), 0.068, 0.038, fill=INK)
        for k in range(4):
            gx = mx - 0.05 + k * 0.033
            painter.line((gx, my - 0.03), (gx, my + 0.03), 0.010,
                         color=WHITE, cap_joint=False)
    elif p.mouth == "flat":
        painter.line((mx - 0.05, my), (mx + 0.05, my), 0.026)
    else:  # neutral
        painter.arc((mx - 0.005, my - 0.012), 0.055, 0.042, 12, 68, width=0.026)


# ----------------------------------------------------------------------------
# Poses / motion helpers
# ----------------------------------------------------------------------------
def walk_pose(t, x0, speed=1.28, facing=1, y=0.0, thickness=1.0,
              t_start=0.0, mood="relaxed", amp=1.0, stride=1.0):
    """Walk cycle pose. x0 = world x, y = height offset above standing hip."""
    p = Pose(x=x0, y=HIP_H + y, facing=facing, thickness=thickness)
    ph = (t - t_start) * 2.05 * speed / 1.28  # step frequency
    a = 2 * math.pi * ph

    swing_hip = 26 * amp * stride
    p.hip_l = swing_hip * math.sin(a)
    p.hip_r = swing_hip * math.sin(a + math.pi)
    p.kn_l = -34 * amp * max(0.0, -math.sin(a + 0.9)) - 6
    p.kn_r = -34 * amp * max(0.0, -math.sin(a + math.pi + 0.9)) - 6
    p.sh_l = -16 * amp * math.sin(a) + (6 if mood == "confident" else 0)
    p.sh_r = -16 * amp * math.sin(a + math.pi) + (6 if mood == "confident" else 0)
    p.el_l = 16 + 10 * max(0.0, math.sin(a))
    p.el_r = 16 + 10 * max(0.0, math.sin(a + math.pi))
    p.y += 0.035 * amp * abs(math.sin(a))
    p.lean = 4.5 if mood != "confident" else 6.5
    p.head_tilt = 0
    if mood == "relaxed":
        p.eye, p.mouth, p.brow = "open", "neutral", "none"
    elif mood == "confident":
        p.eye, p.mouth, p.brow = "open", "smile", "raise"
    elif mood == "sad":
        p.eye, p.mouth, p.brow = "dot", "frown", "sad"
        p.lean = -2
    return p


def idle_pose(x, y=0.0, facing=1, thickness=1.0, t=0.0, breathe=1.0):
    p = Pose(x=x, y=HIP_H + y, facing=facing, thickness=thickness)
    p.y += 0.012 * math.sin(t * 2.1) * breathe
    p.sh_l, p.el_l = 10, 14
    p.sh_r, p.el_r = -8, -10
    return p


def sit_pose(x, y=0.0, facing=1, thickness=1.0, t=0.0, head_low=0.0,
             knees_up=True, breathe=1.0):
    """Seated on the ground, knees up (defeat). head_low 0..1 slumps him."""
    p = Pose(x=x, y=y, facing=facing, thickness=thickness)
    p.y = 0.18 + y
    p.lean = 16 + 26 * head_low
    p.head_tilt = 10 * head_low
    p.head_dy = -0.13 * head_low
    # steep thighs (knees clearly above the hip), shins straight down
    p.hip_l, p.kn_l = 126, -131
    p.hip_r, p.kn_r = 120, -126
    # forearms drooping onto the knees
    p.sh_l, p.el_l = 30 + 14 * head_low, 42
    p.sh_r, p.el_r = 24 + 14 * head_low, 40
    p.y += 0.010 * math.sin(t * 1.9) * breathe
    return p


# ----------------------------------------------------------------------------
# Box prop
# ----------------------------------------------------------------------------
@dataclass
class Box:
    x: float = 0.0
    y: float = 0.0              # bottom of box
    size: float = 0.72
    lid: float = 0.0            # 0 closed → 1 fully open
    glow: float = 0.0           # seam glow intensity
    tilt: float = 0.0           # rotate whole box (deg)
    button: float = 0.0         # button visibility 0..1
    press: float = 0.0          # button pressed 0..1
    mirror: float = 0.0         # mirror visible 0..1
    wobble: float = 0.0
    held: bool = False


def draw_box(painter: Painter, b: Box, light_rays: float = 0.0):
    s = b.size
    px, py = b.x, b.y
    if b.tilt:
        pass  # tilt handled by caller offsetting y (cheap wobble)
    front_h = s * 0.82
    ox, oy = s * 0.30, s * 0.26   # isometric-ish offset for top/side

    fl = (px - s / 2, py)
    fr = (px + s / 2, py)
    ftl = (px - s / 2, py + front_h)
    ftr = (px + s / 2, py + front_h)
    btl = (ftl[0] + ox, ftl[1] + oy)
    btr = (ftr[0] + ox, ftr[1] + oy)
    side_r = [ftr, btr, (btr[0], btr[1] - front_h), fr]

    if not b.held:
        painter.ellipse((px + 0.05, 0.012), s * 0.72, s * 0.11,
                        fill=(235, 235, 238))

    # seam glow: soft halo around the silhouette + light leak on the lid edge
    if b.glow > 0.01:
        g = b.glow
        hull = [fl, fr, (btr[0], btr[1] - front_h), btr, btl, ftl]
        for i, wmul in enumerate((5.0, 3.0, 1.7)):
            col = mix(WHITE, GLOW_YEL, g * (0.28 + 0.24 * i))
            painter.poly(hull, outline=col, width=0.02 * wmul)

    top_face = [ftl, ftr, btr, btl]
    front_face = [fl, fr, ftr, ftl]
    painter.poly(top_face, fill=(252, 251, 246), outline=INK, width=0.022)
    painter.poly(side_r, fill=(228, 226, 219), outline=INK, width=0.022)
    painter.poly(front_face, fill=(243, 241, 235), outline=INK, width=0.022)

    if b.glow > 0.01:
        # bright seam where the lid meets the body
        painter.line(ftl, ftr, 0.030, color=mix(WHITE, GLOW_YEL, b.glow),
                     cap_joint=False)

    # light rays from closed-glowing box / open box
    if light_rays > 0.01:
        cx, cy = px, py + front_h * 0.9
        for k in range(7):
            ang = math.radians(35 + k * 16 + 6 * math.sin(k * 2.1))
            ln = s * (1.4 + 0.7 * ((k * 37) % 10) / 10) * light_rays
            dx, dy = math.cos(ang), math.sin(ang)
            wdt = 0.05 * light_rays
            painter.line((cx, cy), (cx + dx * ln, cy + dy * ln), wdt,
                         color=mix(WHITE, WARM_PALE, 0.75), cap_joint=False)

    # lid
    if b.lid > 0.01:
        hinge_l, hinge_r = btl, btr
        ang = -105 * ease_out(b.lid)
        v = (btl[0] - ftl[0], btl[1] - ftl[1])  # depth vector
        rot_v = rot(v[0], v[1], ang)
        tl2 = (hinge_l[0] - rot_v[0] * 1.0, hinge_l[1] - rot_v[1] * 1.0)
        v2 = (btr[0] - ftr[0], btr[1] - ftr[1])
        rot_v2 = rot(v2[0], v2[1], ang)
        tr2 = (hinge_r[0] - rot_v2[0] * 1.0, hinge_r[1] - rot_v2[1] * 1.0)
        lid_face = [hinge_l, hinge_r, tr2, tl2]
        painter.poly(lid_face, fill=(250, 248, 242), outline=INK, width=0.022)

        # interior / mirror
        if b.mirror > 0.01 and b.lid > 0.35:
            mx0, mx1 = px - s * 0.32, px + s * 0.32
            my0, my1 = py + front_h * 0.12, py + front_h * 0.72
            painter.rect((mx0, my0), (mx1, my1), fill=MIRROR_BOT)
            # vertical gradient bands
            for i in range(6):
                t = i / 5
                yy0 = lerp(my0, my1, t)
                yy1 = lerp(my0, my1, t + 1 / 6)
                col = mix(MIRROR_BOT, MIRROR_TOP, t)
                painter.rect((mx0, yy0), (mx1, yy1), fill=col)
            painter.rect((mx0, my0), (mx1, my1), outline=INK, width=0.02)
            # shimmer streaks
            for k in range(3):
                sx = lerp(mx0, mx1, 0.18 + 0.28 * k)
                painter.poly(
                    [(sx, my1), (sx + 0.12, my1),
                     (sx + 0.02 - 0.10, my0), (sx - 0.10, my0)],
                    fill=(246, 251, 253))
            # glow around mirror
            if b.mirror > 0.4:
                for wm in (3.0, 1.8):
                    painter.rect((mx0 - 0.02, my0 - 0.02), (mx1 + 0.02, my1 + 0.02),
                                 outline=mix(WHITE, WARM, 0.35 * b.mirror),
                                 width=0.02 * wm)

    # button on right side face
    if b.button > 0.01:
        bx = px + s * 0.5 + ox * 0.42
        by = py + front_h * 0.42
        r = 0.045 * (1 - 0.3 * b.press)
        painter.circle((bx, by), r * 1.7, fill=(214, 212, 205))
        painter.circle((bx, by), r, fill=(120, 118, 112), outline=INK,
                       width=0.016)
        painter.circle((bx - r * 0.3, by + r * 0.3), r * 0.3,
                       fill=(210, 210, 205))


# ----------------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------------
def draw_background(painter: Painter, grey: float, frame: int):
    """White ↔ grey sky. grey=0 pure white, 1 = full storm grey."""
    if grey <= 0.01:
        return
    g = clamp(grey)
    top = mix(WHITE, GREY_BG_TOP, g)
    bot = mix(WHITE, GREY_BG_BOT, g)
    # horizontal gradient bands across the visible screen
    n = 9
    for i in range(n):
        col = mix(top, bot, (i + 0.5) / n)
        y0 = (H * SS) * i / n
        y1 = (H * SS) * (i + 1) / n
        painter.d.rectangle([0, y0, W * SS, y1], fill=col)


def draw_clouds(painter: Painter, amount: float, t: float):
    if amount <= 0.01:
        return
    clouds = [
        (-2.2, 3.6, 1.5, 0.55),
        (1.8, 4.3, 1.9, 0.62),
        (5.2, 3.2, 1.3, 0.48),
        (-5.4, 4.6, 1.7, 0.5),
        (8.6, 4.0, 1.5, 0.5),
    ]
    for i, (cx, cy, rx, ry) in enumerate(clouds):
        cx = cx + 0.10 * t + i * 0.03
        col = mix(WHITE, CLOUD_B if i % 2 else CLOUD_A, clamp(amount))
        for k, (dx, dy, rm) in enumerate(
                ((-0.62, -0.06, 0.62), (0.0, 0.16, 1.0), (0.66, -0.02, 0.7),
                 (-0.25, 0.05, 0.85), (0.32, 0.06, 0.8))):
            painter.ellipse((cx + dx * rx, cy + dy * ry),
                            rx * rm, ry * rm, fill=col)


def draw_rain(painter: Painter, amount: float, frame: int, extra_speed=1.0):
    if amount <= 0.01:
        return
    cam = painter.cam
    rng = random.Random(7777)
    n = 110
    vw = cam.view_h * W / H
    x_min = cam.x - vw * 0.75
    x_max = cam.x + vw * 0.75
    top_y = cam.y + cam.view_h * 0.75
    span_y = cam.view_h * 1.5
    for i in range(n):
        x0 = rng.uniform(x_min, x_max)
        speed = rng.uniform(2.6, 4.2) * extra_speed
        phase = rng.uniform(0, span_y)
        ln = rng.uniform(0.16, 0.30)
        y = top_y - ((frame / FPS * speed + phase) % span_y)
        col = mix(WHITE, RAIN_COL, 0.55 * clamp(amount))
        painter.line((x0, y), (x0 - 0.055 * ln * 3, y - ln), 0.011,
                     color=col, cap_joint=False)


def draw_ground_dark(painter: Painter, amount: float):
    if amount <= 0.01:
        return
    col = mix(WHITE, (178, 186, 196), clamp(amount))
    painter.rect((-60, -3.0), (60, 0.02), fill=col)


# ----------------------------------------------------------------------------
# Effects
# ----------------------------------------------------------------------------
def sparkle(painter: Painter, pos, r, t, phase=0.0, color=WARM):
    """4-point manga glint, pulsing."""
    pulse = 0.75 + 0.25 * math.sin(t * 6 + phase)
    r = r * pulse
    x, y = pos
    painter.poly([(x, y + r), (x + r * 0.22, y + r * 0.22),
                  (x + r, y), (x + r * 0.22, y - r * 0.22),
                  (x, y - r), (x - r * 0.22, y - r * 0.22),
                  (x - r, y), (x - r * 0.22, y + r * 0.22)], fill=color)


def star_burst(painter: Painter, pos, r, t, t0, color=WARM):
    """Impact star — expands + fades over ~0.35 s."""
    dt = t - t0
    if dt < 0 or dt > 0.4:
        return
    k = dt / 0.4
    rr = r * (0.35 + 1.15 * k)
    x, y = pos
    pts = []
    n = 10
    for i in range(n):
        ang = math.pi * 2 * i / n
        rad = rr if i % 2 == 0 else rr * 0.42
        pts.append((x + math.cos(ang) * rad, y + math.sin(ang) * rad))
    col = mix(color, WHITE, k * 0.7)
    painter.poly(pts, fill=col, outline=INK, width=0.012)


def dust_puff(painter: Painter, pos, t, t0, r=0.5, n=6, color=(225, 225, 228)):
    dt = t - t0
    if dt < 0 or dt > 0.9:
        return
    k = dt / 0.9
    rng = random.Random(int(pos[0] * 100) + int(t0 * 100))
    x, y = pos
    for i in range(n):
        ang = rng.uniform(0, math.pi * 2)
        dist = rng.uniform(0.25, 1.0) * r * (0.4 + k * 1.5)
        rr = r * rng.uniform(0.16, 0.34) * (1 - k * 0.75)
        col = mix(WHITE, color, 0.8 * (1 - k))
        painter.circle((x + math.cos(ang) * dist,
                        y + abs(math.sin(ang)) * dist * 0.55), rr, fill=col)


def sweat_drop(painter: Painter, pos, t, t0):
    dt = t - t0
    if dt < 0 or dt > 1.1:
        return
    k = dt / 1.1
    x, y = pos
    yy = y - k * 0.42
    painter.ellipse((x, yy), 0.030, 0.042, fill=(176, 205, 226),
                    outline=(120, 160, 195), width=0.012)
    painter.circle((x + 0.012, yy + 0.016), 0.011, fill=(230, 242, 250))


def speed_lines(painter: Painter, cam_target, count=5, length=0.9, color=(225, 225, 228)):
    rng = random.Random(int(cam_target[0] * 77))
    x, y = cam_target
    for i in range(count):
        yy = y + rng.uniform(-0.65, 0.65)
        ln = length * rng.uniform(0.6, 1.25)
        painter.line((x + rng.uniform(0.4, 1.1), yy),
                     (x + rng.uniform(0.4, 1.1) + ln, yy),
                     rng.uniform(0.014, 0.028), color=color, cap_joint=False)


def rain_splash(painter: Painter, pos, t, phase, r=0.06):
    """Small ripple + droplets where rain hits the box top."""
    period = 0.62
    k = ((t + phase) % period) / period
    if k > 0.5:
        return
    kk = k / 0.5
    x, y = pos
    painter.arc((x, y), r * (0.4 + kk * 1.6), r * 0.35 * (0.4 + kk * 1.6),
                200, 340, color=RAIN_COL, width=0.012)
    for s in (-1, 1):
        painter.circle((x + s * r * (0.3 + kk * 1.1),
                        y + r * (1.1 - kk * 1.4)), r * 0.16, fill=RAIN_COL)


def light_rays_burst(painter: Painter, pos, t, t0, spread=35, n=8, length=1.6):
    dt = t - t0
    if dt < 0 or dt > 2.2:
        return
    k = dt / 2.2
    x, y = pos
    for i in range(n):
        ang = math.radians(-90 + (i - (n - 1) / 2) * (spread / max(1, n - 1)) * 2)
        ln = length * (0.4 + k * 1.2) * (0.7 + 0.3 * math.sin(i * 2.4))
        painter.line((x, y), (x + math.cos(ang) * ln, y - math.sin(ang) * ln),
                     0.055 * (1 - k * 0.8), color=mix(WARM_PALE, WHITE, k),
                     cap_joint=False)


def ripple_ring(painter: Painter, pos, t, t0, r0=0.05, r1=0.5, color=INK):
    dt = t - t0
    if dt < 0 or dt > 0.55:
        return
    k = dt / 0.55
    r = lerp(r0, r1, ease_out(k))
    painter.circle(pos, r, outline=mix(color, WHITE, k), width=0.014 * (1 - k * 0.6))


def flash_frame(painter: Painter, t, t0, peak=0.85, dur=0.12):
    dt = t - t0
    if dt < 0 or dt > dur:
        return
    painter.overlay_alpha(WHITE, peak * (1 - dt / dur))
