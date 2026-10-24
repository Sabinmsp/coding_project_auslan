import cv2
import mediapipe as mp
import json

VIDEO = "08133_kf_rgb.mp4"
OUTPUT = "08133_motion_world.json"

mp_holistic = mp.solutions.holistic


def to_list(lms):
    if lms is None:
        return None
    return [{"x": p.x, "y": p.y, "z": p.z} for p in lms.landmark]


cap = cv2.VideoCapture(VIDEO)

fps = cap.get(cv2.CAP_PROP_FPS)
if fps <= 0:
    fps = 25

data = {
    "fps": fps,
    "frames": []
}

with mp_holistic.Holistic(
    model_complexity=2,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as holistic:

    frame_num = 0

    while True:
        ok, frame = cap.read()

        if not ok:
            break

        frame_num += 1

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        result = holistic.process(rgb)

        data["frames"].append({
            "frame": frame_num,
            # image-space landmarks, normalised 0..1 (kept for 2D overlays)
            "pose": to_list(result.pose_landmarks),
            # metric landmarks in METRES, origin at the hip midpoint.
            # this is the one to drive a 3D skeleton with.
            "pose_world": to_list(result.pose_world_landmarks),
            "left_hand": to_list(result.left_hand_landmarks),
            "right_hand": to_list(result.right_hand_landmarks)
        })

        print("frame", frame_num)

cap.release()

with open(OUTPUT, "w") as f:
    json.dump(data, f)

print("DONE:", OUTPUT)
