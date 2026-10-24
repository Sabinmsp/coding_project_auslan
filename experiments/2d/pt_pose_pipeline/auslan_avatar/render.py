"""
2D human avatar renderer (OpenCV).

Draws a canonical-space pose as a stylised upper-body figure: shirt torso,
skin-toned capsule arms, a head built from the face landmarks, and fully
articulated 21-point hands.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from . import skeleton as sk


@dataclass
class Palette:
    background: tuple = (247, 244, 240)
    shirt: tuple = (70, 55, 45)
    shirt_shade: tuple = (52, 40, 33)
    skin: tuple = (150, 190, 235)
    skin_shade: tuple = (120, 158, 205)
    outline: tuple = (32, 28, 26)
    feature: tuple = (40, 35, 32)
    line: tuple = (28, 28, 28)      # stick-figure stroke

    def bgr(self, name):
        return getattr(self, name)


@dataclass
class View:
    """Canonical-space -> pixel mapping."""

    scale: float
    cx: float
    cy: float

    def to_px(self, pts):
        pts = np.atleast_2d(pts)
        out = np.empty(pts.shape, dtype=np.int32)
        out[:, 0] = np.round(self.cx + pts[:, 0] * self.scale)
        out[:, 1] = np.round(self.cy + pts[:, 1] * self.scale)
        return out

    def pt(self, p):
        return (
            int(round(self.cx + p[0] * self.scale)),
            int(round(self.cy + p[1] * self.scale)),
        )


def torso_quad(ls, rs, length=1.45, taper=0.80, shoulder_pad=0.12):
    """
    Build the torso outline from the shoulder line alone.

    The dataset's signers are seated behind a table, so the hip keypoints are
    occluded and the extractor places them almost arbitrarily -- and does so
    with high confidence, which means confidence alone cannot reject them.
    Measured hips therefore drift up to a full shoulder-width sideways and
    shear the body. Hanging the torso off the shoulders instead keeps the
    figure rigid and consistent between signs.

    Returns the quad (top-right, top-left, bottom-left, bottom-right).
    """
    ls = np.asarray(ls, dtype=np.float64)
    rs = np.asarray(rs, dtype=np.float64)
    across = ls - rs
    width = float(np.linalg.norm(across))
    if width < 1e-6:
        across, width = np.array([1.0, 0.0]), 1.0
    u = across / width

    # Perpendicular to the shoulder line, pointing down the screen.
    down = np.array([-u[1], u[0]])
    if down[1] < 0:
        down = -down

    mid = (ls + rs) / 2.0
    half = width * (0.5 + shoulder_pad)
    bottom = mid + down * (length * width)
    return np.array([
        mid - u * half,
        mid + u * half,
        bottom + u * half * taper,
        bottom - u * half * taper,
    ])


def fit_view(frames, usable, layout, width, height, margin=0.10,
             torso_length=1.45):
    """
    Choose scale/offset so the whole animation stays inside the canvas.

    Uses every joint we will actually draw, across every frame, so the figure
    never drifts out of shot mid-video.
    """
    idx = _drawn_indices(layout, usable)
    pts = frames[:, idx, :].reshape(-1, 2)

    # The torso is synthesised rather than tracked, so add its corners
    # explicitly or the body would be allowed to run off the bottom.
    corners = np.concatenate([
        torso_quad(frames[i, sk.L_SHOULDER], frames[i, sk.R_SHOULDER],
                   length=torso_length)
        for i in range(frames.shape[0])
    ], axis=0)
    pts = np.concatenate([pts, corners], axis=0)
    pts = pts[np.isfinite(pts).all(axis=1)]
    if pts.size == 0:
        return View(scale=min(width, height) * 0.3, cx=width / 2, cy=height / 2)

    # Robust bounds: a couple of stray keypoints would otherwise double the
    # required width and shrink the figure to nothing.
    lo = np.percentile(pts, 0.5, axis=0)
    hi = np.percentile(pts, 99.5, axis=0)
    span = np.maximum(hi - lo, 1e-3)

    # Head sits above the shoulders and is drawn as a blob wider than its
    # landmarks, so pad the top a little extra.
    pad_x = span[0] * margin
    pad_y = span[1] * margin
    lo = lo - np.array([pad_x, pad_y * 1.6])
    hi = hi + np.array([pad_x, pad_y])
    span = hi - lo

    scale = min(width / span[0], height / span[1])
    cx = width / 2 - (lo[0] + hi[0]) / 2 * scale
    cy = height / 2 - (lo[1] + hi[1]) / 2 * scale
    return View(scale=scale, cx=cx, cy=cy)


def _drawn_indices(layout, usable):
    # Hips are deliberately excluded: they are occluded in this dataset and
    # their bogus positions would otherwise dominate the framing.
    idx = [
        sk.NOSE, sk.L_EAR, sk.R_EAR,
        sk.L_SHOULDER, sk.R_SHOULDER,
        sk.L_ELBOW, sk.R_ELBOW,
        sk.L_WRIST, sk.R_WRIST,
    ]
    for part in ("face", "left_hand", "right_hand"):
        s = layout.slice_of(part)
        idx.extend(i for i in range(s.start, s.stop) if usable[i])
    return sorted({i for i in idx if i < len(usable) and usable[i]})


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------


def _hand_flags(hands):
    """Normalise the per-frame hand flag pair into two booleans."""
    if hands is None:
        return True, True
    return bool(hands[0]), bool(hands[1])


def _capsule(img, a, b, width, fill, outline, outline_w=3):
    """A rounded limb segment: dark outline under a filled core."""
    cv2.line(img, a, b, outline, width + outline_w * 2, cv2.LINE_AA)
    cv2.circle(img, a, (width + outline_w * 2) // 2, outline, -1, cv2.LINE_AA)
    cv2.circle(img, b, (width + outline_w * 2) // 2, outline, -1, cv2.LINE_AA)
    cv2.line(img, a, b, fill, width, cv2.LINE_AA)
    cv2.circle(img, a, width // 2, fill, -1, cv2.LINE_AA)
    cv2.circle(img, b, width // 2, fill, -1, cv2.LINE_AA)


def _poly(img, pts, color, thickness=2, closed=False):
    if len(pts) < 2:
        return
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], closed, color,
                  thickness, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# renderer
# ---------------------------------------------------------------------------


class AvatarRenderer:
    def __init__(self, layout, usable, view, palette=None, show_face=True,
                 torso_length=1.45):
        self.layout = layout
        self.usable = usable
        self.view = view
        self.palette = palette or Palette()
        self.show_face = show_face
        self.torso_length = torso_length
        self.unit = view.scale  # pixels per shoulder-width

    # -- helpers ----------------------------------------------------------

    def _px(self, frame, index):
        return self.view.pt(frame[index])

    def _part(self, frame, part):
        s = self.layout.slice_of(part)
        return frame[s.start:s.stop] if s.stop > s.start else None

    def _part_usable(self, part):
        s = self.layout.slice_of(part)
        if s.stop <= s.start:
            return False
        return bool(self.usable[s.start:s.stop].any())

    def _w(self, fraction, minimum=2):
        return max(int(minimum), int(round(self.unit * fraction)))

    # -- pieces -----------------------------------------------------------

    def draw_torso(self, img, frame):
        p = self.palette
        ls = np.asarray(frame[sk.L_SHOULDER])
        rs = np.asarray(frame[sk.R_SHOULDER])

        quad = torso_quad(ls, rs, length=self.torso_length)
        pts = self.view.to_px(quad)
        cv2.fillPoly(img, [pts.reshape(-1, 1, 2)], p.shirt, cv2.LINE_AA)
        _poly(img, pts, p.outline, max(2, self._w(0.012)), closed=True)

        # collar
        mid = (ls + rs) / 2
        cv2.ellipse(
            img, self.view.pt(mid),
            (self._w(0.17), self._w(0.09)),
            0, 0, 180, p.shirt_shade, -1, cv2.LINE_AA,
        )

    def draw_head(self, img, frame):
        p = self.palette
        face = self._part(frame, "face")
        ls, rs = frame[sk.L_SHOULDER], frame[sk.R_SHOULDER]
        neck_base = (np.asarray(ls) + np.asarray(rs)) / 2

        if face is not None and self._part_usable("face"):
            lo, hi = face.min(axis=0), face.max(axis=0)
            centre = (lo + hi) / 2
            rx = max((hi[0] - lo[0]) / 2, 1e-3) * 1.18
            ry = max((hi[1] - lo[1]) / 2, 1e-3) * 1.05
            centre = centre - np.array([0.0, ry * 0.18])
        else:
            centre = np.asarray(frame[sk.NOSE]) - np.array([0.0, 0.12])
            ear = abs(frame[sk.L_EAR][0] - frame[sk.R_EAR][0])
            rx = max(ear * 0.85, 0.24)
            ry = rx * 1.22

        # neck
        _capsule(
            img, self.view.pt(neck_base),
            self.view.pt(centre + np.array([0.0, ry * 0.55])),
            self._w(0.17), p.skin_shade, p.outline, max(2, self._w(0.008)),
        )

        axes = (max(3, int(rx * self.unit)), max(3, int(ry * self.unit)))
        cpx = self.view.pt(centre)
        cv2.ellipse(img, cpx, axes, 0, 0, 360, p.outline, -1, cv2.LINE_AA)
        cv2.ellipse(
            img, cpx,
            (max(2, axes[0] - self._w(0.014)), max(2, axes[1] - self._w(0.014))),
            0, 0, 360, p.skin, -1, cv2.LINE_AA,
        )

        if self.show_face:
            if face is not None and self._part_usable("face"):
                self._draw_face_landmarks(img, face)
            else:
                self._draw_face_stylised(img, centre, rx, ry)

    def _draw_face_landmarks(self, img, face):
        """Eyes, brows and mouth straight from the 68-point face model."""
        p = self.palette
        t_fine = max(1, self._w(0.007, 1))
        t_bold = max(2, self._w(0.011, 2))

        for group, closed, thick in (
            (sk.FACE_BROW_R, False, t_bold),
            (sk.FACE_BROW_L, False, t_bold),
            (sk.FACE_EYE_R, True, t_fine),
            (sk.FACE_EYE_L, True, t_fine),
            (sk.FACE_MOUTH_OUTER, True, t_bold),
            (sk.FACE_NOSE_BRIDGE, False, t_fine),
        ):
            if max(group) >= len(face):
                continue
            _poly(img, self.view.to_px(face[list(group)]), p.feature,
                  thick, closed=closed)

        # pupils
        for eye in (sk.FACE_EYE_R, sk.FACE_EYE_L):
            if max(eye) >= len(face):
                continue
            c = face[list(eye)].mean(axis=0)
            cv2.circle(img, self.view.pt(c), max(1, self._w(0.016, 1)),
                       p.feature, -1, cv2.LINE_AA)

        # mouth interior, so open/closed reads clearly
        if max(sk.FACE_MOUTH_INNER) < len(face):
            inner = self.view.to_px(face[list(sk.FACE_MOUTH_INNER)])
            if cv2.contourArea(inner.astype(np.int32)) > 4:
                cv2.fillPoly(img, [inner.reshape(-1, 1, 2)],
                             (60, 60, 95), cv2.LINE_AA)

    def _draw_face_stylised(self, img, centre, rx, ry):
        p = self.palette
        cx, cy = centre
        eye_dx, eye_dy = rx * 0.36, ry * 0.12
        r = max(2, self._w(0.022))
        for sign in (-1, 1):
            cv2.circle(img, self.view.pt((cx + sign * eye_dx, cy - eye_dy)),
                       r, p.feature, -1, cv2.LINE_AA)
            a = self.view.pt((cx + sign * eye_dx - rx * 0.18, cy - ry * 0.36))
            b = self.view.pt((cx + sign * eye_dx + rx * 0.18, cy - ry * 0.42))
            cv2.line(img, a, b, p.feature, max(2, self._w(0.012)), cv2.LINE_AA)
        box = (
            self.view.pt((cx - rx * 0.34, cy + ry * 0.18)),
            self.view.pt((cx + rx * 0.34, cy + ry * 0.62)),
        )
        cv2.ellipse(
            img,
            ((box[0][0] + box[1][0]) // 2, (box[0][1] + box[1][1]) // 2),
            (abs(box[1][0] - box[0][0]) // 2, abs(box[1][1] - box[0][1]) // 2),
            0, 20, 160, p.feature, max(2, self._w(0.012)), cv2.LINE_AA,
        )

    def draw_arms(self, img, frame):
        p = self.palette
        upper = self._w(0.155)
        fore = self._w(0.125)
        edge = max(2, self._w(0.010))
        for shoulder, elbow, wrist in sk.ARM_CHAINS:
            if not (self.usable[shoulder] and self.usable[elbow]):
                continue
            s = self._px(frame, shoulder)
            e = self._px(frame, elbow)
            _capsule(img, s, e, upper, p.shirt, p.outline, edge)
            if self.usable[wrist]:
                w = self._px(frame, wrist)
                _capsule(img, e, w, fore, p.skin, p.outline, edge)

    def draw_hand(self, img, frame, part, body_wrist, articulated=True):
        p = self.palette
        hand = self._part(frame, part)
        if (hand is None or not self._part_usable(part) or len(hand) < 21
                or not articulated):
            self._draw_fist(img, frame[body_wrist])
            return

        pts = self.view.to_px(hand)
        edge = max(2, self._w(0.008))
        palm_w = self._w(0.085)

        # palm mass
        palm_idx = [0, 5, 9, 13, 17]
        palm = pts[palm_idx]
        cv2.fillPoly(img, [palm.reshape(-1, 1, 2)], p.outline, cv2.LINE_AA)
        cv2.polylines(img, [palm.reshape(-1, 1, 2)], True, p.outline,
                      palm_w, cv2.LINE_AA)
        inner = (palm - palm.mean(axis=0)) * 0.80 + palm.mean(axis=0)
        cv2.fillPoly(img, [inner.astype(np.int32).reshape(-1, 1, 2)],
                     p.skin, cv2.LINE_AA)

        # fingers, tapering toward the tips
        for name, chain in sk.FINGERS.items():
            base = 0.062 if name != "thumb" else 0.072
            for k in range(len(chain) - 1):
                a, b = pts[chain[k]], pts[chain[k + 1]]
                w = self._w(base * (1.0 - 0.16 * k))
                _capsule(img, tuple(a), tuple(b), w, p.skin, p.outline, edge)

        for tip in sk.FINGER_TIPS:
            cv2.circle(img, tuple(pts[tip]), max(1, self._w(0.020)),
                       p.skin_shade, -1, cv2.LINE_AA)

    def _draw_fist(self, img, wrist_xy):
        """Fallback blob when a hand was never detected."""
        p = self.palette
        c = self.view.pt(wrist_xy)
        cv2.circle(img, c, self._w(0.13), p.outline, -1, cv2.LINE_AA)
        cv2.circle(img, c, self._w(0.13) - max(2, self._w(0.010)),
                   p.skin, -1, cv2.LINE_AA)

    # -- frame ------------------------------------------------------------

    def render(self, frame, canvas=None, size=None, hands=None):
        """Render one canonical pose. Returns a BGR image."""
        if canvas is None:
            h, w = size
            canvas = np.full((h, w, 3), self.palette.background, np.uint8)

        self.draw_torso(canvas, frame)
        self.draw_head(canvas, frame)
        self.draw_arms(canvas, frame)
        left, right = _hand_flags(hands)
        self.draw_hand(canvas, frame, "left_hand", sk.L_WRIST, left)
        self.draw_hand(canvas, frame, "right_hand", sk.R_WRIST, right)
        return canvas


# ---------------------------------------------------------------------------
# stick figure
# ---------------------------------------------------------------------------


class StickRenderer:
    """
    Minimal line-art avatar: one stroke weight, one colour, no fills.

    The fleshed-out renderer gives every joint a thick capsule, which makes
    the noisy hand tracking in this dataset look far worse than it is -- a
    finger a few pixels out becomes a fat slab crossing the forearm. Thin
    uniform strokes keep the same information on screen while reading as a
    diagram rather than a broken body.
    """

    def __init__(self, layout, usable, view, palette=None, show_face=True,
                 torso_length=1.45, stroke=0.030, joint_dots=True):
        self.layout = layout
        self.usable = usable
        self.view = view
        self.palette = palette or Palette()
        self.show_face = show_face
        self.torso_length = torso_length
        self.stroke = stroke
        self.joint_dots = joint_dots
        self.unit = view.scale

    # -- helpers ----------------------------------------------------------

    def _w(self, fraction=None, minimum=1):
        f = self.stroke if fraction is None else fraction
        return max(int(minimum), int(round(self.unit * f)))

    def _part(self, frame, part):
        s = self.layout.slice_of(part)
        return frame[s.start:s.stop] if s.stop > s.start else None

    def _part_usable(self, part):
        s = self.layout.slice_of(part)
        return s.stop > s.start and bool(self.usable[s.start:s.stop].any())

    def _line(self, img, a, b, width=None):
        cv2.line(img, a, b, self.palette.line,
                 width or self._w(), cv2.LINE_AA)

    def _dot(self, img, p, r=None):
        cv2.circle(img, p, r or max(2, self._w(self.stroke * 1.3)),
                   self.palette.line, -1, cv2.LINE_AA)

    # -- pieces -----------------------------------------------------------

    def draw_body(self, img, frame):
        """Shoulder bar, spine and hip bar -- the classic stick torso."""
        ls = np.asarray(frame[sk.L_SHOULDER])
        rs = np.asarray(frame[sk.R_SHOULDER])
        quad = torso_quad(ls, rs, length=self.torso_length)
        top_r, top_l, bot_l, bot_r = quad

        shoulder_mid = (top_l + top_r) / 2.0
        hip_mid = (bot_l + bot_r) / 2.0

        w = self._w()
        self._line(img, self.view.pt(top_r), self.view.pt(top_l), w)
        self._line(img, self.view.pt(shoulder_mid), self.view.pt(hip_mid), w)
        self._line(img, self.view.pt(bot_r), self.view.pt(bot_l), w)

        if self.joint_dots:
            for p in (ls, rs):
                self._dot(img, self.view.pt(p))

    def draw_head(self, img, frame):
        face = self._part(frame, "face")
        ls, rs = frame[sk.L_SHOULDER], frame[sk.R_SHOULDER]
        neck_base = (np.asarray(ls) + np.asarray(rs)) / 2.0

        if face is not None and self._part_usable("face"):
            lo, hi = face.min(axis=0), face.max(axis=0)
            centre = (lo + hi) / 2.0
            radius = max((hi[0] - lo[0]) / 2.0, 1e-3) * 1.15
            centre = centre - np.array([0.0, radius * 0.10])
        else:
            centre = np.asarray(frame[sk.NOSE]) - np.array([0.0, 0.12])
            radius = max(abs(frame[sk.L_EAR][0] - frame[sk.R_EAR][0]) * 0.85,
                         0.24)

        r_px = max(4, int(radius * self.unit))
        c_px = self.view.pt(centre)

        # neck
        self._line(img, self.view.pt(neck_base),
                   self.view.pt(centre + np.array([0.0, radius * 0.9])))
        cv2.circle(img, c_px, r_px, self.palette.line, self._w(), cv2.LINE_AA)

        if self.show_face:
            self._draw_face(img, face, centre, radius)

    def _draw_face(self, img, face, centre, radius):
        """Two eyes and a mouth -- enough expression, no detail to go wrong."""
        eye_r = max(1, int(radius * self.unit * 0.10))

        if face is not None and self._part_usable("face") \
                and max(sk.FACE_EYE_L) < len(face):
            for eye in (sk.FACE_EYE_R, sk.FACE_EYE_L):
                c = face[list(eye)].mean(axis=0)
                cv2.circle(img, self.view.pt(c), eye_r, self.palette.line,
                           -1, cv2.LINE_AA)
            mouth = face[list(sk.FACE_MOUTH_OUTER)]
            _poly(img, self.view.to_px(mouth), self.palette.line,
                  max(1, self._w(self.stroke * 0.6)), closed=True)
        else:
            for sign in (-1, 1):
                c = centre + np.array([sign * radius * 0.34, -radius * 0.15])
                cv2.circle(img, self.view.pt(c), eye_r, self.palette.line,
                           -1, cv2.LINE_AA)
            a = self.view.pt(centre + np.array([-radius * 0.3, radius * 0.4]))
            b = self.view.pt(centre + np.array([radius * 0.3, radius * 0.4]))
            self._line(img, a, b, max(1, self._w(self.stroke * 0.7)))

    def draw_arms(self, img, frame):
        w = self._w()
        for shoulder, elbow, wrist in sk.ARM_CHAINS:
            if not (self.usable[shoulder] and self.usable[elbow]):
                continue
            s = self.view.pt(frame[shoulder])
            e = self.view.pt(frame[elbow])
            self._line(img, s, e, w)
            if self.usable[wrist]:
                self._line(img, e, self.view.pt(frame[wrist]), w)
            if self.joint_dots:
                self._dot(img, e)

    def draw_hand(self, img, frame, part, body_wrist, articulated=True):
        hand = self._part(frame, part)
        thin = max(1, self._w(self.stroke * 0.62))

        if (hand is None or not self._part_usable(part) or len(hand) < 21
                or not articulated):
            # No usable handshape: draw a closed fist rather than inventing
            # fingers out of joints the extractor never saw.
            cv2.circle(img, self.view.pt(frame[body_wrist]),
                       max(3, self._w(self.stroke * 1.9)),
                       self.palette.line, self._w(), cv2.LINE_AA)
            return

        pts = self.view.to_px(hand)
        for chain in sk.FINGERS.values():
            for k in range(len(chain) - 1):
                cv2.line(img, tuple(pts[chain[k]]), tuple(pts[chain[k + 1]]),
                         self.palette.line, thin, cv2.LINE_AA)
        for a, b in sk.PALM_ARCS:
            cv2.line(img, tuple(pts[a]), tuple(pts[b]),
                     self.palette.line, thin, cv2.LINE_AA)

    # -- frame ------------------------------------------------------------

    def render(self, frame, canvas=None, size=None, hands=None):
        if canvas is None:
            h, w = size
            canvas = np.full((h, w, 3), self.palette.background, np.uint8)

        self.draw_body(canvas, frame)
        self.draw_head(canvas, frame)
        self.draw_arms(canvas, frame)
        left, right = _hand_flags(hands)
        self.draw_hand(canvas, frame, "left_hand", sk.L_WRIST, left)
        self.draw_hand(canvas, frame, "right_hand", sk.R_WRIST, right)
        return canvas


MONO_PALETTE = Palette(
    background=(255, 255, 255),
    line=(20, 20, 20),
    outline=(20, 20, 20),
    feature=(20, 20, 20),
)

STYLES = {"human": AvatarRenderer, "stick": StickRenderer}


def default_palette(style):
    """Plain black-on-white for the stick style, shaded colours otherwise."""
    return MONO_PALETTE if style == "stick" else Palette()


def make_renderer(style, *args, **kwargs):
    """Build the renderer for a named style."""
    try:
        cls = STYLES[style]
    except KeyError:
        raise ValueError(
            f"unknown style {style!r}; choose from {sorted(STYLES)}"
        ) from None
    if cls is AvatarRenderer:
        kwargs.pop("stroke", None)
        kwargs.pop("joint_dots", None)
    return cls(*args, **kwargs)
