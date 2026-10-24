"""
Three-panel debug comparison (Step 8).

    LEFT   original MP4
    MIDDLE MediaPipe skeleton drawn from the saved landmarks
    RIGHT  rendered 3D avatar frames

Lets you tell at a glance whether an error came from landmark extraction or
from Blender retargeting: if the middle panel is right and the right panel is
wrong, the bug is in the retargeter.

    .venv-1/bin/python make_comparison.py \
        --video 08133_kf_rgb.mp4 \
        --npz 08133_kf_rgb_landmarks.npz \
        --render-dir render_preview \
        --out 08133_comparison.mp4
"""

import argparse
import glob
import os

import cv2
import numpy as np


POSE_EDGES = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (15, 17), (15, 19), (15, 21), (16, 18), (16, 20), (16, 22),
]
HAND_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]


def draw_skeleton(canvas, pose, lh, rh, lh_ok, rh_ok, vis_min=0.5):
    h, w = canvas.shape[:2]

    def px(p):
        return int(p[0] * w), int(p[1] * h)

    for a, b in POSE_EDGES:
        if pose[a, 3] < vis_min or pose[b, 3] < vis_min:
            continue
        cv2.line(canvas, px(pose[a]), px(pose[b]), (90, 220, 90), 2,
                 cv2.LINE_AA)
    for i in range(33):
        if pose[i, 3] < vis_min:
            continue
        cv2.circle(canvas, px(pose[i]), 3, (60, 180, 60), -1, cv2.LINE_AA)

    for hand, ok, colour in ((lh, lh_ok, (80, 160, 255)),
                             (rh, rh_ok, (255, 170, 60))):
        if not ok:
            continue
        for a, b in HAND_EDGES:
            cv2.line(canvas, px(hand[a]), px(hand[b]), colour, 1, cv2.LINE_AA)
        for i in range(21):
            cv2.circle(canvas, px(hand[i]), 2, colour, -1, cv2.LINE_AA)
    return canvas


def label(img, text, colour=(240, 240, 240)):
    cv2.rectangle(img, (0, 0), (img.shape[1], 30), (25, 25, 28), -1)
    cv2.putText(img, text, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                colour, 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--npz", required=True)
    ap.add_argument("--render-dir", required=True)
    ap.add_argument("--out", default="comparison.mp4")
    ap.add_argument("--height", type=int, default=560)
    args = ap.parse_args()

    data = np.load(args.npz, allow_pickle=True)
    pose_image = data["pose_image"]
    left_hand, right_hand = data["left_hand"], data["right_hand"]
    left_ok, right_ok = data["left_ok"], data["right_ok"]
    fps = float(data["fps"])

    cap = cv2.VideoCapture(args.video)
    source = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        source.append(frame)
    cap.release()

    renders = sorted(glob.glob(os.path.join(args.render_dir, "frame_*.png")))
    n = min(len(source), len(pose_image), len(renders))
    print(f"video {len(source)}  landmarks {len(pose_image)}  "
          f"renders {len(renders)}  -> using {n}")
    if n == 0:
        raise SystemExit("nothing to compare")

    H = args.height

    def fit(img):
        scale = H / img.shape[0]
        return cv2.resize(img, (max(1, int(img.shape[1] * scale)), H))

    panels = []
    for i in range(n):
        left = fit(source[i].copy())
        mid = fit(source[i].copy())
        mid = (mid * 0.28).astype(np.uint8)
        draw_skeleton(mid, pose_image[i], left_hand[i], right_hand[i],
                      bool(left_ok[i]), bool(right_ok[i]))
        right = fit(cv2.imread(renders[i])[:, :, :3])

        label(left, "1. SOURCE VIDEO")
        label(mid, "2. MEDIAPIPE LANDMARKS")
        label(right, "3. RETARGETED 3D AVATAR")

        panels.append(np.hstack([left, mid, right]))

    h, w = panels[0].shape[:2]
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"),
                             fps, (w, h))
    for p in panels:
        writer.write(p)
    writer.release()
    print(f"saved: {args.out}  ({w}x{h}, {n} frames @ {fps:g} fps)")


if __name__ == "__main__":
    main()
