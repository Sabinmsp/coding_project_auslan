"""
Draw the stored landmarks back onto the source video frames -- the check
that the extraction followed the signer, which no amount of comparing
JSON against JSON can tell you.

    ../.venv-1/bin/python scripts/qa_overlay.py hello thank-you doctor   # sign ids
    ../.venv-1/bin/python scripts/qa_overlay.py --random 12               # sample
    ../.venv-1/bin/python scripts/qa_overlay.py --low                     # flagged ones
    ../.venv-1/bin/python scripts/qa_overlay.py pay --frames 10 21 33     # exact frames
    ../.venv-1/bin/python scripts/qa_overlay.py pay --motion old.json --tag before
                                     # draw another motion file of the same clip

Writes datasets/processed/qa/<id>.jpg: 5 frames across the sign's active span, each
the original video frame with the stored pose (green), left hand
(orange), right hand (blue) and face (white) drawn over it. Frames where
a hand is absent from the stored data say so in the corner -- that is the
data the player will show, gaps included.
"""
import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402

MANIFEST = json.loads(paths.MANIFEST.read_text())
CATALOG = json.loads(paths.CATALOG.read_text())

POSE_LINKS = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24)]
HAND_LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (0, 9), (9, 10),
              (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16), (0, 17), (17, 18),
              (18, 19), (19, 20), (5, 9), (9, 13), (13, 17)]
COLOURS = {"pose": (200, 232, 126), "left_hand": (107, 143, 255), "right_hand": (255, 180, 111),
           "face": (240, 240, 240)}


def overlay(sid, frames_per_sheet=5, frames=None, motion=None, tag=""):
    s = MANIFEST["signs"][sid]
    if not s["clip"]:
        return None
    m = json.loads(Path(motion).read_text() if motion
                   else (paths.SIGN_MOTION / f"{s['clip']}.json").read_text())
    take = next(t for t in CATALOG["signs"][sid]["takes"] if t["clip"] == s["clip"])
    cap = cv2.VideoCapture(str(paths.VIDEO_ROOT / take["path"]))
    images = []
    while True:
        ok, im = cap.read()
        if not ok:
            break
        images.append(im)
    cap.release()
    n, sc = m["n"], m["scale"]
    picks = (np.array(frames) if frames is not None
             else np.linspace(int(n * 0.15), int(n * 0.85), frames_per_sheet).astype(int))
    tiles = []
    for i in picks:
        im = images[min(i, len(images) - 1)].copy()
        h, w = im.shape[:2]
        pt = lambda a, k: (int(a[2 * k] / sc * w), int(a[2 * k + 1] / sc * h))
        if m["pose"][i]:
            for a, b in POSE_LINKS:
                cv2.line(im, pt(m["pose"][i], a), pt(m["pose"][i], b), COLOURS["pose"], 2, cv2.LINE_AA)
        for key in ("left_hand", "right_hand"):
            a = m[key][i]
            if a:
                for x, y in HAND_LINKS:
                    cv2.line(im, pt(a, x), pt(a, y), COLOURS[key], 2, cv2.LINE_AA)
                for k in range(21):
                    cv2.circle(im, pt(a, k), 2, (255, 255, 255), -1, cv2.LINE_AA)
        if m["face"][i]:
            for k in range(len(m["face"][i]) // 2):
                cv2.circle(im, pt(m["face"][i], k), 1, COLOURS["face"], -1, cv2.LINE_AA)
        label = f"f{i}"
        missing = [k[0].upper() for k in ("left_hand", "right_hand") if not m[k][i]]
        if missing:
            label += "  no " + "+".join(missing) + " hand"
        cv2.putText(im, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(im, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(im)
    sheet = np.hstack(tiles)
    title = np.zeros((34, sheet.shape[1], 3), np.uint8)
    cv2.putText(title, f"{s['gloss']}   clip {s['clip']}   quality {s.get('q')}"
                + ("   LOW" if s.get("low") else "") + (f"   [{tag}]" if tag else ""), (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    out = paths.QA / f"{sid}{'_' + tag if tag else ''}.jpg"
    out.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(out), np.vstack([title, sheet]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--random", type=int)
    ap.add_argument("--low", action="store_true")
    ap.add_argument("--frames", nargs="*", type=int, help="exact frame numbers to draw")
    ap.add_argument("--motion", help="draw this motion file instead of the library's")
    ap.add_argument("--tag", default="", help="suffix for the output file name")
    args = ap.parse_args()
    avail = [i for i, s in MANIFEST["signs"].items() if s["clip"]]
    ids = list(args.ids)
    if args.random:
        random.seed(0)
        ids += random.sample(avail, min(args.random, len(avail)))
    if args.low:
        ids += [i for i in avail if MANIFEST["signs"][i].get("low")]
    for sid in ids:
        out = overlay(sid, frames=args.frames, motion=args.motion, tag=args.tag)
        print(f"{sid:28} -> {out.relative_to(paths.ROOT) if out else 'not extracted'}")


if __name__ == "__main__":
    main()
