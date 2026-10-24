"""
jump.mp4  ->  MediaPipe  ->  motion.json

Two passes, because one is not enough for the non-dominant hand.

PASS 1  Holistic over the whole frame: body pose plus both hands.

PASS 2  A dedicated Hands model re-run on a crop around each wrist,
        upscaled. Holistic sees the hand at whatever size it occupies in
        a 512x408 frame, which for a resting, low-contrast hand is far too
        small to fit reliably -- it still returns 21 landmarks, they are
        just wrong. Cropping to the forearm's neighbourhood and upscaling
        to 384px gives the palm detector something to work with.

Merged by quality, not by preference: pass 2 replaces pass 1 only where it
produces a hand that is geometrically possible. Measured on this clip, in
frames whose landmarks survive the viewer's sanity gates:

        left hand   25/51  ->  34/51
        right hand  46/51  ->  47/51

Two landmark sets are written per frame:

  pose        image space, x/y normalised 0..1 by frame width/height.
  pose_world  metres, origin at the hip midpoint, z on the same scale as
              x and y. This is the one that drives the 3D rig -- image
              space is stretched by the frame's aspect ratio and its z is
              not comparable to x/y, which bends the arms in the wrong
              plane.

Hand landmarks only come in image space, so width/height are recorded in
the header and index.html undoes the aspect stretch itself.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

HERE = Path(__file__).resolve().parent

# Crop geometry for pass 2, chosen by sweeping against the number of
# frames that survive the sanity gates -- not by eye.
CROP_HALF = 1.10        # half-width as a multiple of forearm length
CROP_OFFSET = 0.35      # centre this far past the wrist, along the forearm
CROP_SIZE = 384         # upscale target
CROP_CONFIDENCE = 0.2

# A hand that fails both passes leaves a hole, and a held pose reads as a
# freeze followed by a jump. Where the hole is short and bracketed by two
# good hands on either side, the in-between is far better estimated by
# interpolating them than by stopping. Long holes are left alone -- past a
# few frames the hand really has done something unobserved, and inventing
# it would be fiction rather than interpolation. Measured gap lengths on
# this clip: left [1,5,3,1,2,3,1,1], right [1,1,1].
MAX_INTERPOLATED_GAP = 4

mp_holistic = mp.solutions.holistic
mp_hands = mp.solutions.hands

ELBOW_WRIST = {"left": (13, 15), "right": (14, 16)}
FINGERS = {"index": [5, 6, 7, 8], "mid": [9, 10, 11, 12],
           "ring": [13, 14, 15, 16], "pinky": [17, 18, 19, 20]}
CURL_SIGN = {"left": 1, "right": -1}

# Face: the 128 of Holistic's 468 mesh points that outline the face, brows,
# eyes and lips. Holistic computes the full mesh on every frame regardless,
# so keeping these costs nothing at extraction time. Brows and mouth carry
# grammar in Auslan (question type, negation, mouthing) -- a figure without
# them cannot show any of it.
_fm = mp.solutions.face_mesh_connections
FACE_PARTS = {name: getattr(_fm, f"FACEMESH_{name.upper()}")
              for name in ("face_oval", "left_eyebrow", "right_eyebrow",
                           "left_eye", "right_eye", "lips")}
FACE_KEEP = sorted({i for edges in FACE_PARTS.values() for e in edges for i in e})

# Which version of the extraction logic produced a file. build_library.py
# re-extracts anything made by an older version.
#   2  three passes + face
#   3  hand ownership: a hand is only ever stored in the slot of the arm it
#      is attached to (below)
#   4  ownership with the ATTACHED margin, so touching hands are not dropped
EXTRACTOR_VERSION = 4

# HAND OWNERSHIP. Measured over the first 506 extracted signs: a correct
# hand's wrist point sits a median 0.05 shoulder-widths from its own arm's
# pose wrist (99% within 0.24). Wrist-crop results were further than 0.35 a
# quarter of the time -- because a crop around one wrist also contains the
# OTHER hand when the hands are close (PAY, HELP), and the crop found that
# one. Stored in the cropped side's slot, the same physical hand appeared
# twice and the real hand vanished: in PAY, 12 frames had a hand in the
# wrong slot and 11 had both slots holding the same hand.
OWN_WRIST_MAX = 0.35      # crop result: wrist must be this close to its own arm (shoulder widths)
# When the hands touch, the two wrists are close and a correctly attached hand
# can sit marginally nearer the OTHER wrist by noise alone (58 such cases in
# the 506 signs, all with own-gap < 0.15 and wrists 0.12-0.15 apart). Within
# this distance of its own wrist a hand counts as attached, whatever is nearer.
ATTACHED = 0.15
SAME_HAND_MAX = 0.15      # mean landmark distance below which two hands are one hand


def to_list(landmarks):
    if landmarks is None:
        return None
    return [{"x": float(p.x), "y": float(p.y), "z": float(p.z),
             "visibility": float(getattr(p, "visibility", 1.0))}
            for p in landmarks.landmark]


# ---------------------------------------------------------------------
# geometry, mirroring the viewer's sanity gates so the merge keeps the
# better hand rather than simply the newer one
# ---------------------------------------------------------------------
def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def is_possible(landmarks, side, aspect):
    """Could a real hand be in this configuration?"""
    if not landmarks or len(landmarks) != 21:
        return False
    P = [np.array([p["x"] * aspect, -p["y"], -p["z"] * aspect]) for p in landmarks]

    forward = (P[5] + P[17] + 2 * P[9]) / 4 - P[0]
    across = P[17] - P[5]
    nf, na = np.linalg.norm(forward), np.linalg.norm(across)
    if nf < 1e-9 or na < 1e-9:
        return False

    # palm axes must not be collapsed towards each other
    if np.linalg.norm(np.cross(unit(across), unit(forward))) < 0.35:
        return False
    # the hand must not be squashed to a line
    if na / nf < 0.40:
        return False

    curl = unit(unit(across) * CURL_SIGN[side])
    normal = unit(np.cross(curl, unit(forward)))
    curl = unit(np.cross(unit(forward), normal))

    # PIP is a one-way hinge: all four reading backwards means the fit is
    # inside out
    bends = []
    for idx in FINGERS.values():
        v1 = unit(P[idx[1]] - P[idx[0]])
        v2 = unit(P[idx[2]] - P[idx[1]])
        angle = np.arccos(np.clip(np.dot(v1, v2), -1, 1))
        bends.append(angle if np.dot(np.cross(v1, v2), curl) >= 0 else -angle)
    return np.degrees(np.median(bends)) >= -25


def _xy(p, aspect):
    return np.array([p["x"] * aspect, p["y"]])


def shoulder_width(pose, aspect):
    return float(np.linalg.norm(_xy(pose[11], aspect) - _xy(pose[12], aspect)))


def wrist_gaps(hand, side, pose, aspect):
    """(distance to own arm's wrist, distance to the other arm's wrist), in
    shoulder widths. Hand landmark 0 is the wrist."""
    own_i, other_i = (15, 16) if side == "left" else (16, 15)
    sw = shoulder_width(pose, aspect) or 1e-9
    root = _xy(hand[0], aspect)
    return (float(np.linalg.norm(root - _xy(pose[own_i], aspect))) / sw,
            float(np.linalg.norm(root - _xy(pose[other_i], aspect))) / sw)


def same_hand(a, b, pose, aspect):
    """True when two 21-point hands are one physical hand detected twice."""
    if not a or not b:
        return False
    sw = shoulder_width(pose, aspect) or 1e-9
    mean = np.mean([np.linalg.norm(_xy(p, aspect) - _xy(q, aspect)) for p, q in zip(a, b)])
    return mean / sw < SAME_HAND_MAX


def resolve_ownership(frame, aspect):
    """Drop hands stored in the wrong slot, then one of two slots holding the
    same hand. Returns {"wrong_slot": n, "duplicate": n}. Never invents a
    hand: a dropped slot is left empty for pass 2 / pass 3 to fill if they
    can do so correctly."""
    dropped = {"wrong_slot": 0, "duplicate": 0}
    pose = frame["pose"]
    if not pose:
        return dropped
    for side in ("left", "right"):
        key = f"{side}_hand"
        if frame[key]:
            own, other = wrist_gaps(frame[key], side, pose, aspect)
            if other < own and own > ATTACHED:
                frame[key], frame[f"{key}_source"] = None, None
                dropped["wrong_slot"] += 1
    L, R = frame["left_hand"], frame["right_hand"]
    if same_hand(L, R, pose, aspect):
        keep_left = wrist_gaps(L, "left", pose, aspect)[0] <= wrist_gaps(R, "right", pose, aspect)[0]
        drop = "right_hand" if keep_left else "left_hand"
        frame[drop], frame[f"{drop}_source"] = None, None
        dropped["duplicate"] += 1
    return dropped


def wrist_crop(pose, side, width, height):
    elbow_i, wrist_i = ELBOW_WRIST[side]
    ex, ey = pose[elbow_i]["x"] * width, pose[elbow_i]["y"] * height
    wx, wy = pose[wrist_i]["x"] * width, pose[wrist_i]["y"] * height

    forearm = float(np.hypot(wx - ex, wy - ey))
    if forearm < 5:
        return None

    dx, dy = (wx - ex) / forearm, (wy - ey) / forearm
    cx = wx + dx * forearm * CROP_OFFSET
    cy = wy + dy * forearm * CROP_OFFSET
    size = max(24, int(round(2 * forearm * CROP_HALF)))
    return int(round(cx)) - size // 2, int(round(cy)) - size // 2, size


def extract(input_video, face=False, log=print):
    """Run all three passes over one clip and return the motion dict.

    face=True also records the FACE_KEEP subset of the face mesh per frame
    under "face". Off by default so the CLI's output is unchanged for the
    existing callers (add_sign.py, fetch_signbank_letter.py, the 3D path).
    """
    input_video = Path(input_video)
    if not input_video.exists():
        raise FileNotFoundError(
            f"Source video missing: {input_video}\n"
            f"Put the clip there, or pass its path.")

    # =====================================================================
    # PASS 1 -- Holistic
    # =====================================================================
    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open {input_video} — the file exists but OpenCV cannot "
            f"decode it. Check the codec with: ffprobe {input_video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if fps <= 0:
        fps = 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    aspect = width / height if height else 1.0

    images = []
    while True:
        ok, image = cap.read()
        if not ok:
            break
        images.append(image)
    cap.release()

    log(f"Video: {input_video.name}  {width}x{height}  {len(images)} frames @ {fps}fps")
    log("Pass 1: Holistic…")

    frames = []
    with mp_holistic.Holistic(
            static_image_mode=False, model_complexity=2, smooth_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5) as holistic:
        for number, image in enumerate(images):
            result = holistic.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            frames.append({
                "frame": number,
                "pose": to_list(result.pose_landmarks),
                "pose_world": to_list(result.pose_world_landmarks),
                "left_hand": to_list(result.left_hand_landmarks),
                "right_hand": to_list(result.right_hand_landmarks),
                "left_hand_source": "holistic" if result.left_hand_landmarks else None,
                "right_hand_source": "holistic" if result.right_hand_landmarks else None,
            })
            if face:
                mesh = result.face_landmarks
                frames[-1]["face"] = (None if mesh is None else
                    [{"x": float(mesh.landmark[i].x), "y": float(mesh.landmark[i].y)}
                     for i in FACE_KEEP])
            if (number + 1) % 30 == 0:
                log("  processed:", number + 1)

    ownership = {"wrong_slot": 0, "duplicate": 0}
    for frame in frames:
        for k, v in resolve_ownership(frame, aspect).items():
            ownership[k] += v

    # =====================================================================
    # PASS 2 -- Hands on an upscaled crop around each wrist
    # =====================================================================
    log("Pass 2: Hands on wrist crops…")
    replaced = {"left": 0, "right": 0}
    recovered = {"left": 0, "right": 0}

    with mp_hands.Hands(static_image_mode=True, max_num_hands=2, model_complexity=1,
                        min_detection_confidence=CROP_CONFIDENCE) as hands:
        for number, image in enumerate(images):
            frame = frames[number]
            if not frame["pose"]:
                continue

            for side in ("left", "right"):
                # Pass 1 already good -> the crop result would be discarded
                # below ("leave it alone"), so don't pay for the inference.
                # Output is identical; this is ~1/3 of the runtime.
                if frame[f"{side}_hand"] is not None and \
                        is_possible(frame[f"{side}_hand"], side, aspect):
                    continue
                box = wrist_crop(frame["pose"], side, width, height)
                if not box:
                    continue
                x0, y0, size = box

                sx0, sy0 = max(0, x0), max(0, y0)
                sx1, sy1 = min(width, x0 + size), min(height, y0 + size)
                if sx1 <= sx0 or sy1 <= sy0:
                    continue

                canvas = np.zeros((size, size, 3), np.uint8)
                patch = image[sy0:sy1, sx0:sx1]
                canvas[sy0 - y0:sy0 - y0 + patch.shape[0],
                       sx0 - x0:sx0 - x0 + patch.shape[1]] = patch

                big = cv2.resize(canvas, (CROP_SIZE, CROP_SIZE), interpolation=cv2.INTER_CUBIC)
                result = hands.process(cv2.cvtColor(big, cv2.COLOR_BGR2RGB))
                if not result.multi_hand_landmarks:
                    continue

                # A crop around one wrist can contain BOTH hands when they are
                # close, so the crop side alone does not say which hand was
                # found. Ask for up to two, and keep only one whose wrist is
                # attached to this arm -- never the other hand, never a copy
                # of the hand already in the other slot.
                scale = size / width
                other_hand = frame["right_hand" if side == "left" else "left_hand"]
                candidate, best = None, None
                for found in result.multi_hand_landmarks:
                    c = [{"x": (x0 + p.x * size) / width,
                          "y": (y0 + p.y * size) / height,
                          "z": float(p.z) * scale, "visibility": 1.0}
                         for p in found.landmark]
                    own, other = wrist_gaps(c, side, frame["pose"], aspect)
                    if (own <= OWN_WRIST_MAX and (own < other or own <= ATTACHED)
                            and is_possible(c, side, aspect)
                            and not same_hand(c, other_hand, frame["pose"], aspect)
                            and (best is None or own < best)):
                        candidate, best = c, own
                if candidate is None:
                    continue

                key = f"{side}_hand"
                if frame[key] is None:
                    recovered[side] += 1
                elif not is_possible(frame[key], side, aspect):
                    replaced[side] += 1
                else:
                    continue          # pass 1 was already good; leave it alone

                frame[key] = candidate
                frame[f"{key}_source"] = "crop"

    # =====================================================================
    # PASS 3 -- bridge short holes
    # =====================================================================
    log("Pass 3: interpolating short gaps…")
    bridged = {"left": 0, "right": 0}

    for side in ("left", "right"):
        key = f"{side}_hand"
        good = [i for i, f in enumerate(frames) if is_possible(f[key], side, aspect)]
        if len(good) < 2:
            continue

        for a, b in zip(good, good[1:]):
            span = b - a
            if span < 2 or span - 1 > MAX_INTERPOLATED_GAP:
                continue
            left_lm, right_lm = frames[a][key], frames[b][key]
            for i in range(a + 1, b):
                t = (i - a) / span
                frames[i][key] = [
                    {"x": p["x"] * (1 - t) + q["x"] * t,
                     "y": p["y"] * (1 - t) + q["y"] * t,
                     "z": p["z"] * (1 - t) + q["z"] * t,
                     "visibility": 1.0}
                    for p, q in zip(left_lm, right_lm)]
                frames[i][f"{key}_source"] = "interpolated"
                bridged[side] += 1

    data = {"fps": fps, "width": width, "height": height,
            "frame_count": len(frames), "frames": frames}
    if face:
        data["face_indices"] = FACE_KEEP

    stats = {}
    for side in ("left", "right"):
        key = f"{side}_hand"
        total = sum(1 for f in frames if f[key])
        good = sum(1 for f in frames if is_possible(f[key], side, aspect))
        stats[side] = {"detected": total, "possible": good, "replaced": replaced[side],
                       "recovered": recovered[side], "bridged": bridged[side]}
        log(f"  {side:5}: {total}/{len(frames)} detected, {good} geometrically possible"
            f"   (crop replaced {replaced[side]}, recovered {recovered[side]},"
            f" bridged {bridged[side]})")
    stats["ownership_dropped"] = ownership
    stats["version"] = EXTRACTOR_VERSION
    log(f"  ownership: dropped {ownership['wrong_slot']} wrong-slot and "
        f"{ownership['duplicate']} duplicate hands from pass 1")
    return data, stats


if __name__ == "__main__":
    # One clip, the original (v1) motion format:
    #     python backend/extract_motion.py path/to/sign.mp4 [out.json]
    # Paths are taken as given (relative to where you run it). The library
    # build calls extract() directly instead -- see scripts/build_library.py.
    _args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not _args:
        sys.exit("usage: python backend/extract_motion.py <video.mp4> [out.json]")
    INPUT_VIDEO = Path(_args[0]).resolve()
    OUTPUT_JSON = (Path(_args[1]).resolve() if len(_args) > 1
                   else INPUT_VIDEO.with_suffix(".json"))
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    data, _ = extract(INPUT_VIDEO)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(data, f)
    print("DONE ->", OUTPUT_JSON)
