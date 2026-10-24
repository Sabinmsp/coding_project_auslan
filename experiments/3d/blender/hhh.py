import cv2
import mediapipe as mp
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from mpl_toolkits.mplot3d import Axes3D

# =====================================================
# FILES
# =====================================================

INPUT_VIDEO = "08133_kf_rgb.mp4"
OUTPUT_VIDEO = "08133_clean_3d.mp4"

# =====================================================
# MEDIAPIPE
# =====================================================

mp_holistic = mp.solutions.holistic

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# =====================================================
# OPEN VIDEO
# =====================================================

cap = cv2.VideoCapture(INPUT_VIDEO)

if not cap.isOpened():
    print("Could not open video:", INPUT_VIDEO)
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 30

frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print("FPS:", fps)
print("Frames:", frame_count)

# =====================================================
# BODY LANDMARK INDEXES
# MediaPipe Pose
# =====================================================

NOSE = 0

LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12

LEFT_ELBOW = 13
RIGHT_ELBOW = 14

LEFT_WRIST = 15
RIGHT_WRIST = 16

LEFT_HIP = 23
RIGHT_HIP = 24


# =====================================================
# BODY CONNECTIONS
# =====================================================

BODY_CONNECTIONS = [
    (LEFT_SHOULDER, RIGHT_SHOULDER),

    (LEFT_SHOULDER, LEFT_ELBOW),
    (LEFT_ELBOW, LEFT_WRIST),

    (RIGHT_SHOULDER, RIGHT_ELBOW),
    (RIGHT_ELBOW, RIGHT_WRIST),

    (LEFT_SHOULDER, LEFT_HIP),
    (RIGHT_SHOULDER, RIGHT_HIP),

    (LEFT_HIP, RIGHT_HIP),
]


# =====================================================
# HAND CONNECTIONS
# =====================================================

HAND_CONNECTIONS = list(mp_holistic.HAND_CONNECTIONS)


# =====================================================
# GET XYZ POINT
# =====================================================

def get_xyz(landmark):

    # MediaPipe:
    # x = horizontal
    # y = vertical
    # z = depth

    x = landmark.x - 0.5

    # invert y so up is positive
    y = -(landmark.y - 0.5)

    z = -landmark.z

    return np.array([x, y, z])


# =====================================================
# NORMALIZE BODY
# =====================================================

def normalize_points(points, center, scale):

    normalized = {}

    for key, point in points.items():

        normalized[key] = (point - center) / scale

    return normalized


# =====================================================
# CREATE FIGURE
# =====================================================

fig = plt.figure(figsize=(7, 7))

ax = fig.add_subplot(
    111,
    projection="3d"
)

writer = FFMpegWriter(
    fps=fps,
    metadata={"title": "Clean 3D Auslan Skeleton"}
)


# =====================================================
# VIDEO WRITER LOOP
# =====================================================

with writer.saving(
    fig,
    OUTPUT_VIDEO,
    dpi=120
):

    frame_number = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame_number += 1

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = holistic.process(rgb)

        ax.clear()

        # =============================================
        # CAMERA
        # =============================================

        ax.set_xlim(-1.0, 1.0)
        ax.set_ylim(-0.8, 0.8)
        ax.set_zlim(-1.0, 1.0)

        ax.set_xlabel("X")
        ax.set_ylabel("Depth")
        ax.set_zlabel("Y")

        # mostly front view
        ax.view_init(
            elev=8,
            azim=-90
        )

        ax.set_title(
            f"3D Auslan Motion - Frame {frame_number}"
        )

        # =============================================
        # NEED POSE LANDMARKS
        # =============================================

        if results.pose_landmarks:

            pose = results.pose_landmarks.landmark

            body_points = {}

            important_body = [
                NOSE,

                LEFT_SHOULDER,
                RIGHT_SHOULDER,

                LEFT_ELBOW,
                RIGHT_ELBOW,

                LEFT_WRIST,
                RIGHT_WRIST,

                LEFT_HIP,
                RIGHT_HIP,
            ]

            for idx in important_body:

                landmark = pose[idx]

                if landmark.visibility > 0.3:

                    body_points[idx] = get_xyz(
                        landmark
                    )

            # =========================================
            # NORMALIZATION CENTER
            # =========================================

            if (
                LEFT_SHOULDER in body_points and
                RIGHT_SHOULDER in body_points
            ):

                left_shoulder = body_points[
                    LEFT_SHOULDER
                ]

                right_shoulder = body_points[
                    RIGHT_SHOULDER
                ]

                center = (
                    left_shoulder +
                    right_shoulder
                ) / 2

                shoulder_width = np.linalg.norm(
                    left_shoulder -
                    right_shoulder
                )

                if shoulder_width < 0.001:
                    shoulder_width = 1

                body_points = normalize_points(
                    body_points,
                    center,
                    shoulder_width
                )

                # =====================================
                # DRAW BODY
                # =====================================

                for start_idx, end_idx in BODY_CONNECTIONS:

                    if (
                        start_idx in body_points and
                        end_idx in body_points
                    ):

                        p1 = body_points[start_idx]
                        p2 = body_points[end_idx]

                        ax.plot(
                            [p1[0], p2[0]],
                            [p1[2], p2[2]],
                            [p1[1], p2[1]],
                            linewidth=4
                        )

                # =====================================
                # BODY JOINTS
                # =====================================

                for point in body_points.values():

                    ax.scatter(
                        point[0],
                        point[2],
                        point[1],
                        s=40
                    )

                # =====================================
                # LEFT HAND
                # =====================================

                if results.left_hand_landmarks:

                    left_hand = (
                        results
                        .left_hand_landmarks
                        .landmark
                    )

                    left_hand_points = []

                    for lm in left_hand:

                        p = get_xyz(lm)

                        p = (
                            p - center
                        ) / shoulder_width

                        left_hand_points.append(p)

                    for start_idx, end_idx in HAND_CONNECTIONS:

                        p1 = left_hand_points[
                            start_idx
                        ]

                        p2 = left_hand_points[
                            end_idx
                        ]

                        ax.plot(
                            [p1[0], p2[0]],
                            [p1[2], p2[2]],
                            [p1[1], p2[1]],
                            linewidth=2
                        )

                    for p in left_hand_points:

                        ax.scatter(
                            p[0],
                            p[2],
                            p[1],
                            s=10
                        )

                # =====================================
                # RIGHT HAND
                # =====================================

                if results.right_hand_landmarks:

                    right_hand = (
                        results
                        .right_hand_landmarks
                        .landmark
                    )

                    right_hand_points = []

                    for lm in right_hand:

                        p = get_xyz(lm)

                        p = (
                            p - center
                        ) / shoulder_width

                        right_hand_points.append(p)

                    for start_idx, end_idx in HAND_CONNECTIONS:

                        p1 = right_hand_points[
                            start_idx
                        ]

                        p2 = right_hand_points[
                            end_idx
                        ]

                        ax.plot(
                            [p1[0], p2[0]],
                            [p1[2], p2[2]],
                            [p1[1], p2[1]],
                            linewidth=2
                        )

                    for p in right_hand_points:

                        ax.scatter(
                            p[0],
                            p[2],
                            p[1],
                            s=10
                        )

        # =============================================
        # SAVE FRAME
        # =============================================

        writer.grab_frame()

        print(
            f"\rProcessing {frame_number}/{frame_count}",
            end=""
        )


# =====================================================
# CLEANUP
# =====================================================

cap.release()

holistic.close()

plt.close(fig)

print("\n")
print("DONE!")
print("Created:", OUTPUT_VIDEO)