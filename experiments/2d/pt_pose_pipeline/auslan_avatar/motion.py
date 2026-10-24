"""
Motion processing: canonicalisation, cleaning, retiming and blending.

Clips come from different source videos, so their raw pixel coordinates are
not comparable. Everything here works in *canonical* space:

    origin  = midpoint between the shoulders
    unit    = shoulder width
    +y      = down (screen convention, matching the source data)

Only in that space can the end of one sign be blended into the start of
the next.
"""

import numpy as np

from . import skeleton as sk


DEFAULT_CONF = 0.10


# ---------------------------------------------------------------------------
# cleaning
# ---------------------------------------------------------------------------


def fill_gaps(xy, valid):
    """
    Interpolate low-confidence joints across time.

    xy    : (F, J, 2)
    valid : (F, J) bool
    Returns (filled_xy, usable) where `usable` marks joints seen at least once.
    """
    frames, joints, _ = xy.shape
    out = xy.copy()
    usable = valid.any(axis=0)
    t = np.arange(frames)

    for j in range(joints):
        if not usable[j]:
            continue
        good = valid[:, j]
        if good.all():
            continue
        for axis in (0, 1):
            out[:, j, axis] = np.interp(t, t[good], xy[good, j, axis])

    return out, usable


def smooth(xy, window=5):
    """Centred moving average over time; window is forced odd and clamped."""
    frames = xy.shape[0]
    window = min(int(window) | 1, max(1, frames // 2 * 2 - 1))
    if window < 3 or frames < 3:
        return xy

    pad = window // 2
    padded = np.pad(xy, ((pad, pad), (0, 0), (0, 0)), mode="edge")
    kernel = np.ones(window) / window
    out = np.empty_like(xy)
    for j in range(xy.shape[1]):
        for axis in (0, 1):
            out[:, j, axis] = np.convolve(padded[:, j, axis], kernel, mode="valid")
    return out


# ---------------------------------------------------------------------------
# canonicalisation
# ---------------------------------------------------------------------------


def stabilize_roll(xy, max_tilt_deg=12.0, smooth_window=9):
    """
    Damp implausible torso roll.

    The shoulder keypoints are noisy: in this dataset a single sign can show
    a ~50 degree swing in shoulder-line angle at ~0.8 confidence, which reads
    as the avatar toppling over. Each frame is rotated rigidly about the
    shoulder midpoint so the residual tilt stays within `max_tilt_deg`.
    Rotating the *whole* frame keeps hands in the correct position and
    orientation relative to the body, which is what carries meaning.
    """
    if max_tilt_deg is None:
        return xy

    ls, rs = xy[:, sk.L_SHOULDER], xy[:, sk.R_SHOULDER]
    v = ls - rs
    theta = np.arctan2(v[:, 1], v[:, 0])

    # unwrap + smooth so the correction does not itself jitter
    theta_s = np.unwrap(theta)
    if smooth_window and len(theta_s) >= 3:
        w = min(int(smooth_window) | 1, len(theta_s) // 2 * 2 + 1)
        if w >= 3:
            theta_s = np.convolve(
                np.pad(theta_s, w // 2, mode="edge"), np.ones(w) / w, "valid"
            )

    limit = np.radians(max_tilt_deg)
    target = np.clip(theta_s, -limit, limit)
    delta = target - theta

    pivot = (ls + rs) / 2.0
    cos, sin = np.cos(delta), np.sin(delta)

    rel = xy - pivot[:, None, :]
    out = np.empty_like(xy)
    out[..., 0] = rel[..., 0] * cos[:, None] - rel[..., 1] * sin[:, None]
    out[..., 1] = rel[..., 0] * sin[:, None] + rel[..., 1] * cos[:, None]
    return out + pivot[:, None, :]


def hand_coverage(clip, layout, conf_min=DEFAULT_CONF):
    """
    Per-frame fraction of each hand's 21 joints that were actually detected.

    Returns (F, 2) float: column 0 left hand, column 1 right hand. The
    renderer uses this to decide whether an articulated hand is supported by
    real data or would be invented.
    """
    conf = clip.kps[..., 2]
    out = np.zeros((conf.shape[0], 2))
    for col, part in enumerate(("left_hand", "right_hand")):
        hs = layout.slice_of(part)
        if hs.stop > hs.start:
            out[:, col] = (conf[:, hs] >= conf_min).mean(axis=1)
    return out


def _repair_unseen(xy, usable, layout):
    """
    Give joints that were never detected in *this* clip a sane position.

    fill_gaps can only interpolate a joint that is seen at least once, so a
    joint missing from an entire clip keeps whatever coordinates the
    extractor emitted alongside its ~0 confidence. The lexicon-wide `usable`
    mask is a union across signs, so such a joint can still be selected for
    drawing -- POSSUM's right hand carries a joint at 0.02 confidence sitting
    4.5 shoulder-widths off screen, which wrecks the framing. Park these on
    the nearest meaningful anchor instead.
    """
    out = xy.copy()
    shoulder_mid = (out[:, sk.L_SHOULDER] + out[:, sk.R_SHOULDER]) / 2.0

    for part, wrist in (("left_hand", sk.L_WRIST), ("right_hand", sk.R_WRIST)):
        hs = layout.slice_of(part)
        for j in range(hs.start, hs.stop):
            if not usable[j]:
                out[:, j] = out[:, wrist]

    fs = layout.face
    head_anchor = out[:, sk.NOSE] if usable[sk.NOSE] else shoulder_mid
    for j in range(fs.start, fs.stop):
        if not usable[j]:
            out[:, j] = head_anchor

    for j in range(layout.body.start, layout.body.stop):
        if not usable[j]:
            out[:, j] = shoulder_mid

    return out


def canonicalize(clip, layout=None, conf_min=DEFAULT_CONF, anchor_hands=True,
                 smooth_window=5, max_tilt_deg=12.0, skeleton=None,
                 refine_pose=True):
    """
    Turn a raw PoseClip into canonical-space motion.

    Returns (xy, usable):
        xy     : (F, J, 2) float, shoulder-width units, shoulder-mid at origin
        usable : (J,) bool, joints that were ever detected

    With refine_pose=False only gap-filling and normalisation are applied,
    which is what the pipeline wants on its first pass: it measures one
    shared skeleton across every sign before refining any of them.
    """
    layout = layout or sk.detect_layout(clip.n_joints)
    raw = clip.kps
    xy = raw[..., :2].astype(np.float64)
    conf = raw[..., 2]
    valid = conf >= conf_min

    xy, usable = fill_gaps(xy, valid)

    # Anchor: clip-level median so genuine body sway survives.
    ls, rs = xy[:, sk.L_SHOULDER], xy[:, sk.R_SHOULDER]
    origin = np.median((ls + rs) / 2.0, axis=0)
    width = float(np.median(np.linalg.norm(ls - rs, axis=1)))
    if not np.isfinite(width) or width < 1e-6:
        width = 1.0

    xy = (xy - origin) / width
    xy = _repair_unseen(xy, usable, layout)

    if refine_pose:
        xy = refine(xy, layout, usable, skeleton=skeleton,
                    anchor_hands=anchor_hands, max_tilt_deg=max_tilt_deg,
                    smooth_window=smooth_window)
    return xy, usable


def refine(xy, layout, usable, skeleton=None, anchor_hands=True,
           max_tilt_deg=12.0, smooth_window=5):
    """Retarget, re-anchor the hands, damp roll, then smooth."""
    if skeleton is not None:
        xy = retarget(xy, layout, skeleton)
    if anchor_hands:
        xy = _anchor_hands(xy, layout, usable)
    if max_tilt_deg is not None:
        xy = stabilize_roll(xy, max_tilt_deg=max_tilt_deg)
    if smooth_window:
        xy = smooth(xy, smooth_window)
    return xy


# ---------------------------------------------------------------------------
# skeletal retargeting
# ---------------------------------------------------------------------------

ARM_BONES = [
    (sk.L_SHOULDER, sk.L_ELBOW), (sk.L_ELBOW, sk.L_WRIST),
    (sk.R_SHOULDER, sk.R_ELBOW), (sk.R_ELBOW, sk.R_WRIST),
]


def measure_skeleton(motions, layout):
    """
    Derive one consistent skeleton from every sign in the lexicon.

    Pose extraction on this dataset produces rubber limbs -- an upper arm
    whose length varies by 60% within a single clip, forearms half their
    proper length, left/right asymmetry of 30%. Since the signs are also cut
    from different source videos, each would otherwise animate a differently
    proportioned body. Taking the median bone length across the whole lexicon
    and forcing left/right symmetry gives every sign the same figure.
    """
    def med(fn):
        vals = np.concatenate([fn(m) for m in motions])
        vals = vals[np.isfinite(vals) & (vals > 1e-6)]
        return float(np.median(vals)) if vals.size else 0.0

    upper = med(lambda m: np.concatenate([
        np.linalg.norm(m[:, sk.L_ELBOW] - m[:, sk.L_SHOULDER], axis=1),
        np.linalg.norm(m[:, sk.R_ELBOW] - m[:, sk.R_SHOULDER], axis=1)]))
    fore = med(lambda m: np.concatenate([
        np.linalg.norm(m[:, sk.L_WRIST] - m[:, sk.L_ELBOW], axis=1),
        np.linalg.norm(m[:, sk.R_WRIST] - m[:, sk.R_ELBOW], axis=1)]))

    # A forearm should be close to the upper arm; clamp obvious collapses.
    if fore < upper * 0.55:
        fore = upper * 0.80

    skel = {
        "bones": {
            (sk.L_SHOULDER, sk.L_ELBOW): upper,
            (sk.R_SHOULDER, sk.R_ELBOW): upper,
            (sk.L_ELBOW, sk.L_WRIST): fore,
            (sk.R_ELBOW, sk.R_WRIST): fore,
        }
    }

    fs = layout.face
    if fs.stop > fs.start:
        def face_dist(m):
            sm = (m[:, sk.L_SHOULDER] + m[:, sk.R_SHOULDER]) / 2
            return np.linalg.norm(m[:, fs].mean(axis=1) - sm, axis=1)

        def face_width(m):
            f = m[:, fs]
            return f[..., 0].max(axis=1) - f[..., 0].min(axis=1)

        skel["head_dist"] = med(face_dist)
        skel["face_width"] = med(face_width)

    for part in ("left_hand", "right_hand"):
        hs = layout.slice_of(part)
        if hs.stop <= hs.start:
            continue
        knuckles = [hs.start + k for k in (5, 9, 13, 17)]
        skel.setdefault("hand_span", med(
            lambda m: np.linalg.norm(
                m[:, knuckles] - m[:, hs.start][:, None, :], axis=2
            ).mean(axis=1)
        ))
    return skel


def retarget(xy, layout, skel):
    """
    Reset bone lengths to the canonical skeleton, keeping bone directions.

    Direction is what encodes the sign; length is extractor noise.
    """
    out = xy.copy()

    for a, b in ARM_BONES:
        target = skel["bones"].get((a, b))
        if not target:
            continue
        v = xy[:, b] - xy[:, a]
        n = np.linalg.norm(v, axis=1, keepdims=True)
        v = np.divide(v, np.where(n < 1e-6, 1.0, n))
        out[:, b] = out[:, a] + v * target

    fs = layout.face
    if fs.stop > fs.start and skel.get("head_dist"):
        face = out[:, fs]
        centre = face.mean(axis=1)

        if skel.get("face_width"):
            w = face[..., 0].max(axis=1) - face[..., 0].min(axis=1)
            s = np.where(w > 1e-6, skel["face_width"] / np.maximum(w, 1e-6), 1.0)
            s = np.clip(s, 0.6, 1.6)[:, None, None]
            face = (face - centre[:, None, :]) * s + centre[:, None, :]

        sm = (out[:, sk.L_SHOULDER] + out[:, sk.R_SHOULDER]) / 2
        v = centre - sm
        n = np.linalg.norm(v, axis=1, keepdims=True)
        v = np.divide(v, np.where(n < 1e-6, 1.0, n))
        out[:, fs] = face + (sm + v * skel["head_dist"] - centre)[:, None, :]

    span = skel.get("hand_span")
    if span:
        for part in ("left_hand", "right_hand"):
            hs = layout.slice_of(part)
            if hs.stop <= hs.start:
                continue
            hand = out[:, hs]
            wrist = hand[:, sk.HAND_WRIST][:, None, :]
            knuckles = [5, 9, 13, 17]
            cur = np.linalg.norm(hand[:, knuckles] - wrist, axis=2).mean(axis=1)
            s = np.where(cur > 1e-6, span / np.maximum(cur, 1e-6), 1.0)
            s = np.clip(s, 0.5, 2.0)[:, None, None]
            out[:, hs] = (hand - wrist) * s + wrist

    return out


def _anchor_hands(xy, layout, usable):
    """
    Glue each hand's own wrist point onto the body wrist.

    Hand detections in this dataset are low confidence and often drift a few
    centimetres off the arm; without this the hands render detached.
    """
    out = xy.copy()
    pairs = [
        (layout.left_hand, sk.L_WRIST),
        (layout.right_hand, sk.R_WRIST),
    ]
    for hand_slice, body_wrist in pairs:
        start, stop = hand_slice.start, hand_slice.stop
        if stop <= start:
            continue
        if not usable[start:stop].any():
            continue
        offset = out[:, body_wrist, :] - out[:, start + sk.HAND_WRIST, :]
        out[:, start:stop, :] += offset[:, None, :]
    return out


# ---------------------------------------------------------------------------
# retiming
# ---------------------------------------------------------------------------


def resample(xy, n_frames):
    """Linear resample of a motion along the time axis."""
    n_frames = max(2, int(n_frames))
    frames = xy.shape[0]
    if frames == n_frames:
        return xy.copy()
    if frames == 1:
        return np.repeat(xy, n_frames, axis=0)

    src = np.linspace(0.0, 1.0, frames)
    dst = np.linspace(0.0, 1.0, n_frames)
    out = np.empty((n_frames,) + xy.shape[1:], dtype=xy.dtype)
    for j in range(xy.shape[1]):
        for axis in (0, 1):
            out[:, j, axis] = np.interp(dst, src, xy[:, j, axis])
    return out


def smoothstep(t):
    """Cubic ease-in-out on [0, 1]."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def edge_pose(xy, at_start, blend=3):
    """Average the first/last few frames for a stable hand-off pose."""
    blend = max(1, min(int(blend), xy.shape[0]))
    return xy[:blend].mean(axis=0) if at_start else xy[-blend:].mean(axis=0)


def transition(pose_a, pose_b, n_frames):
    """
    Eased interpolation between two canonical poses.

    Endpoints are excluded: the caller already renders pose_a as the last
    frame of the outgoing sign and pose_b as the first of the incoming one.
    """
    n_frames = max(0, int(n_frames))
    if n_frames == 0:
        return np.empty((0,) + pose_a.shape, dtype=pose_a.dtype)
    t = (np.arange(1, n_frames + 1) / (n_frames + 1.0))
    w = smoothstep(t)[:, None, None]
    return pose_a[None] * (1.0 - w) + pose_b[None] * w


def transition_length(pose_a, pose_b, layout, fps=25.0,
                      min_frames=4, max_frames=16, per_unit=14.0):
    """
    Scale the transition with how far the hands actually have to travel.

    A small adjustment gets a short bridge; crossing the signing space gets
    a longer one.
    """
    idx = []
    for part in ("left_hand", "right_hand"):
        s = layout.slice_of(part)
        if s.stop > s.start:
            idx.extend([s.start + sk.HAND_WRIST])
    idx.extend([sk.L_WRIST, sk.R_WRIST, sk.L_ELBOW, sk.R_ELBOW])
    idx = [i for i in idx if i < pose_a.shape[0]]

    dist = float(np.linalg.norm(pose_a[idx] - pose_b[idx], axis=1).mean())
    n = int(round(per_unit * dist))
    return int(np.clip(n, min_frames, max_frames))


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


class Segment:
    """One stretch of the final timeline."""

    __slots__ = ("word", "kind", "start", "end")

    def __init__(self, word, kind, start, end):
        self.word = word
        self.kind = kind  # "sign" | "transition" | "hold"
        self.start = start
        self.end = end

    def __repr__(self):
        return (
            f"Segment({self.word!r}, {self.kind}, "
            f"{self.start}-{self.end}, {self.end - self.start}f)"
        )

    def __len__(self):
        return self.end - self.start


def resample_flags(flags, n_frames):
    """Nearest-neighbour resample for per-frame boolean/coverage tracks."""
    n_frames = max(2, int(n_frames))
    idx = np.round(np.linspace(0, len(flags) - 1, n_frames)).astype(int)
    return flags[idx]


def build_timeline(motions, words, layout, fps=25.0, speed=1.0,
                   min_sign_seconds=0.72, lead_in=6, tail=8,
                   transition_kwargs=None, flags=None):
    """
    Concatenate per-sign motions into one continuous animation.

    motions : list of (F, J, 2) canonical arrays, in signing order
    words   : matching list of English glosses

    Returns (frames, segments, flag_track). `flags` is an optional list of
    (F, K) per-frame tracks -- hand coverage, say -- carried through the same
    retiming and blending so they stay aligned with the motion.
    """
    if not motions:
        raise ValueError("no motions to build a timeline from")

    transition_kwargs = dict(transition_kwargs or {})
    min_frames = max(2, int(round(min_sign_seconds * fps)))

    # Retime each sign: enforce a legible minimum, then apply global speed.
    staged = []
    staged_flags = []
    for i, m in enumerate(motions):
        n = max(min_frames, m.shape[0])
        n = max(2, int(round(n / max(speed, 1e-3))))
        staged.append(resample(m, n))
        if flags is not None:
            staged_flags.append(resample_flags(flags[i], n))

    chunks = []
    flag_chunks = []
    segments = []
    cursor = 0

    def push(array, word, kind, flag=None):
        nonlocal cursor
        if array.shape[0] == 0:
            return
        chunks.append(array)
        if flags is not None:
            flag_chunks.append(flag)
        segments.append(Segment(word, kind, cursor, cursor + array.shape[0]))
        cursor += array.shape[0]

    # Rest before the first sign.
    def flag_at(i, start):
        if flags is None:
            return None
        row = staged_flags[i][0] if start else staged_flags[i][-1]
        return row

    if lead_in > 0:
        first = edge_pose(staged[0], at_start=True)
        f = flag_at(0, True)
        push(np.repeat(first[None], int(lead_in), axis=0), words[0], "hold",
             None if f is None else np.repeat(f[None], int(lead_in), axis=0))

    for i, (motion, word) in enumerate(zip(staged, words)):
        push(motion, word, "sign",
             None if flags is None else staged_flags[i])

        if i + 1 < len(staged):
            a = edge_pose(motion, at_start=False)
            b = edge_pose(staged[i + 1], at_start=True)
            n = transition_length(a, b, layout, fps=fps, **transition_kwargs)
            bridge = None
            if flags is not None:
                # Only keep a hand through the join if both sides have it.
                joint = np.minimum(flag_at(i, False), flag_at(i + 1, True))
                bridge = np.repeat(joint[None], n, axis=0)
            push(transition(a, b, n), f"{word}→{words[i + 1]}", "transition",
                 bridge)

    if tail > 0:
        last = edge_pose(staged[-1], at_start=False)
        f = flag_at(len(staged) - 1, False)
        push(np.repeat(last[None], int(tail), axis=0), words[-1], "hold",
             None if f is None else np.repeat(f[None], int(tail), axis=0))

    track = np.concatenate(flag_chunks, axis=0) if flags is not None else None
    return np.concatenate(chunks, axis=0), segments, track
