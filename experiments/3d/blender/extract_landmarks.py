"""
MediaPipe Holistic -> saved landmark arrays.

The retargeting layer needs the XYZ coordinates as data, not as pixels burnt
into a video. This runs Holistic over one clip and writes everything to a
single .npz.

    .venv-1/bin/python extract_landmarks.py 08133_kf_rgb.mp4

Produces 08133_kf_rgb_landmarks.npz containing:

    pose_world   (F, 33, 4)  x, y, z, visibility -- METRES, hip-centred
    pose_image   (F, 33, 4)  x, y, z, visibility -- normalised 0..1
    left_hand    (F, 21, 3)  normalised 0..1, z relative to wrist
    right_hand   (F, 21, 3)
    face         (F, N,  3)  normalised 0..1
    pose_ok      (F,)  bool   was a body detected this frame
    left_ok      (F,)  bool
    right_ok     (F,)  bool
    face_ok      (F,)  bool
    fps, width, height, source

pose_world is the array to retarget from: it is already metric and rooted at
the hips, so it does not need the perspective undone.
"""

import argparse
import os
import sys

import cv2
import numpy as np


def landmarks_to_array(landmark_list, count, dims=3):
    """Flatten a MediaPipe landmark list, or zeros when nothing was detected."""
    out = np.zeros((count, dims), dtype=np.float32)
    if landmark_list is None:
        return out, False
    for i, lm in enumerate(landmark_list.landmark[:count]):
        out[i, 0] = lm.x
        out[i, 1] = lm.y
        out[i, 2] = lm.z
        if dims == 4:
            out[i, 3] = getattr(lm, "visibility", 1.0)
    return out, True


def extract(video_path, out_path=None, model_complexity=2,
            refine_face=True, min_det=0.5, min_track=0.5, progress=True):
    import mediapipe as mp

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise SystemExit(f"could not open {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"source ....... {video_path}")
    print(f"size ......... {width}x{height} @ {fps:g} fps, {total} frames")
    print(f"complexity ... {model_complexity} (2 = most accurate)")

    holistic = mp.solutions.holistic.Holistic(
        static_image_mode=False,
        model_complexity=model_complexity,
        smooth_landmarks=True,
        enable_segmentation=False,
        refine_face_landmarks=refine_face,
        min_detection_confidence=min_det,
        min_tracking_confidence=min_track,
    )

    pose_world, pose_image = [], []
    left_hand, right_hand, face = [], [], []
    pose_ok, left_ok, right_ok, face_ok = [], [], [], []
    n_face = 478 if refine_face else 468

    frame_no = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_no += 1

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            res = holistic.process(rgb)

            pw, ok_w = landmarks_to_array(res.pose_world_landmarks, 33, 4)
            pi, ok_i = landmarks_to_array(res.pose_landmarks, 33, 4)
            lh, ok_l = landmarks_to_array(res.left_hand_landmarks, 21, 3)
            rh, ok_r = landmarks_to_array(res.right_hand_landmarks, 21, 3)
            fc, ok_f = landmarks_to_array(res.face_landmarks, n_face, 3)

            pose_world.append(pw)
            pose_image.append(pi)
            left_hand.append(lh)
            right_hand.append(rh)
            face.append(fc)
            pose_ok.append(ok_w and ok_i)
            left_ok.append(ok_l)
            right_ok.append(ok_r)
            face_ok.append(ok_f)

            if progress and frame_no % 10 == 0:
                print(f"  {frame_no}/{total}", end="\r", flush=True)
    finally:
        cap.release()
        holistic.close()

    if not pose_world:
        raise SystemExit("no frames decoded")

    data = {
        "pose_world": np.stack(pose_world),
        "pose_image": np.stack(pose_image),
        "left_hand": np.stack(left_hand),
        "right_hand": np.stack(right_hand),
        "face": np.stack(face),
        "pose_ok": np.array(pose_ok, dtype=bool),
        "left_ok": np.array(left_ok, dtype=bool),
        "right_ok": np.array(right_ok, dtype=bool),
        "face_ok": np.array(face_ok, dtype=bool),
        "fps": np.float32(fps),
        "width": np.int32(width),
        "height": np.int32(height),
        "source": np.array(os.path.basename(video_path)),
    }

    if out_path is None:
        stem = os.path.splitext(video_path)[0]
        out_path = f"{stem}_landmarks.npz"
    np.savez_compressed(out_path, **data)

    n = len(data["pose_ok"])
    print(" " * 30, end="\r")
    print(f"\nframes ....... {n}")
    print(f"body ......... {data['pose_ok'].mean() * 100:5.1f}% of frames")
    print(f"left hand .... {data['left_ok'].mean() * 100:5.1f}%")
    print(f"right hand ... {data['right_ok'].mean() * 100:5.1f}%")
    print(f"face ......... {data['face_ok'].mean() * 100:5.1f}%")

    vis = data["pose_world"][..., 3]
    print(f"\nmean pose visibility, key joints:")
    for name, idx in (("l_shoulder", 11), ("r_shoulder", 12),
                      ("l_elbow", 13), ("r_elbow", 14),
                      ("l_wrist", 15), ("r_wrist", 16),
                      ("l_hip", 23), ("r_hip", 24)):
        print(f"  {name:<12} {vis[:, idx].mean():.3f}")

    size_mb = os.path.getsize(out_path) / 1e6
    print(f"\nsaved: {out_path}  ({size_mb:.2f} MB)")
    return out_path


def main():
    ap = argparse.ArgumentParser(
        description="Extract MediaPipe Holistic landmarks to .npz")
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--complexity", type=int, default=2, choices=[0, 1, 2],
                    help="pose model complexity (default 2, most accurate)")
    ap.add_argument("--no-refine-face", action="store_true")
    ap.add_argument("--min-detection", type=float, default=0.5)
    ap.add_argument("--min-tracking", type=float, default=0.5)
    args = ap.parse_args()

    extract(
        args.video,
        out_path=args.out,
        model_complexity=args.complexity,
        refine_face=not args.no_refine_face,
        min_det=args.min_detection,
        min_track=args.min_tracking,
    )


if __name__ == "__main__":
    sys.exit(main())
