import cv2
import mediapipe as mp
import numpy as np
import os

# ============================================================
# SETTINGS
# ============================================================

WIDTH = 900
HEIGHT = 900
FPS = 25

OUTPUT_VIDEO = "auslan_7_sign_demo_stable.mp4"

SIGN_VIDEOS = [
    ("19.mp4", "RECYCLE"),
    ("44.mp4", "USE"),
    ("78.mp4", "WORRIED"),
    ("1630.mp4", "TOOLS"),
    ("2240.mp4", "NEAT"),
    ("2778.mp4", "DR"),
    ("3185.mp4", "FLASHING"),
]

FULL_SEQUENCE = (
    "RECYCLE  |  USE  |  WORRIED  |  TOOLS  |  NEAT  |  DR  |  FLASHING"
)

PAUSE_SECONDS = 0.25
PAUSE_FRAMES = int(FPS * PAUSE_SECONDS)

MAX_MISSING_FRAMES = 6

# smoothing:
# 0.0 = very smooth but slow
# 1.0 = no smoothing
SMOOTH_ALPHA = 0.65

# ============================================================
# MEDIAPIPE
# ============================================================

mp_holistic = mp.solutions.holistic

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=2,
    smooth_landmarks=True,
    enable_segmentation=False,
    refine_face_landmarks=False,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3,
)

# ============================================================
# HELPERS
# ============================================================

def landmark_to_xy(landmark):
    x = int(landmark.x * WIDTH)
    y = int(landmark.y * HEIGHT)
    return x, y


def copy_landmarks(landmarks):
    """
    Convert MediaPipe landmarks into a simple numpy array.
    Shape: [num_landmarks, 2]
    """

    if landmarks is None:
        return None

    points = []

    for lm in landmarks.landmark:
        points.append([
            lm.x * WIDTH,
            lm.y * HEIGHT
        ])

    return np.array(points, dtype=np.float32)


def smooth_points(current, previous, alpha=0.65):
    """
    Smooth jitter using exponential moving average.
    """

    if current is None:
        return previous

    if previous is None:
        return current

    if current.shape != previous.shape:
        return current

    return (
        alpha * current
        + (1.0 - alpha) * previous
    )


def draw_line_points(canvas, points, a, b, thickness=4):
    if points is None:
        return

    if a >= len(points) or b >= len(points):
        return

    p1 = points[a]
    p2 = points[b]

    if not np.isfinite(p1).all():
        return

    if not np.isfinite(p2).all():
        return

    p1 = tuple(np.int32(p1))
    p2 = tuple(np.int32(p2))

    cv2.line(
        canvas,
        p1,
        p2,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA
    )


# ============================================================
# DRAW BODY
# ============================================================

def draw_pose(canvas, pose_points):

    if pose_points is None:
        return

    # shoulders
    draw_line_points(canvas, pose_points, 11, 12)

    # left arm
    draw_line_points(canvas, pose_points, 11, 13)
    draw_line_points(canvas, pose_points, 13, 15)

    # right arm
    draw_line_points(canvas, pose_points, 12, 14)
    draw_line_points(canvas, pose_points, 14, 16)

    # torso
    draw_line_points(canvas, pose_points, 11, 23)
    draw_line_points(canvas, pose_points, 12, 24)
    draw_line_points(canvas, pose_points, 23, 24)

    # left leg
    draw_line_points(canvas, pose_points, 23, 25)
    draw_line_points(canvas, pose_points, 25, 27)

    # right leg
    draw_line_points(canvas, pose_points, 24, 26)
    draw_line_points(canvas, pose_points, 26, 28)

    # head
    if len(pose_points) > 0:

        nose = pose_points[0]

        if np.isfinite(nose).all():

            cv2.circle(
                canvas,
                tuple(np.int32(nose)),
                45,
                (255, 255, 255),
                3,
                cv2.LINE_AA
            )


# ============================================================
# DRAW HANDS
# ============================================================

HAND_CONNECTIONS = [
    # thumb
    (0, 1), (1, 2), (2, 3), (3, 4),

    # index
    (0, 5), (5, 6), (6, 7), (7, 8),

    # middle
    (5, 9), (9, 10), (10, 11), (11, 12),

    # ring
    (9, 13), (13, 14), (14, 15), (15, 16),

    # pinky
    (13, 17), (17, 18), (18, 19), (19, 20),

    # palm
    (0, 17),
]


def draw_hand(canvas, hand_points):

    if hand_points is None:
        return

    for a, b in HAND_CONNECTIONS:

        draw_line_points(
            canvas,
            hand_points,
            a,
            b,
            thickness=2
        )

    for p in hand_points:

        if not np.isfinite(p).all():
            continue

        x, y = np.int32(p)

        cv2.circle(
            canvas,
            (x, y),
            3,
            (255, 255, 255),
            -1
        )


# ============================================================
# SUBTITLES
# ============================================================

def draw_subtitle(canvas, current_word):

    # title
    cv2.putText(
        canvas,
        "Auslan 2D Avatar Prototype",
        (25, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # bottom panel
    cv2.rectangle(
        canvas,
        (0, HEIGHT - 150),
        (WIDTH, HEIGHT),
        (0, 0, 0),
        -1
    )

    # current sign
    cv2.putText(
        canvas,
        f"Current sign: {current_word}",
        (30, HEIGHT - 95),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # full sequence
    cv2.putText(
        canvas,
        FULL_SEQUENCE,
        (30, HEIGHT - 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA
    )


# ============================================================
# VIDEO WRITER
# ============================================================

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    FPS,
    (WIDTH, HEIGHT)
)

total_frames = 0

last_canvas = None

# ============================================================
# PROCESS EACH SIGN VIDEO
# ============================================================

for filename, gloss in SIGN_VIDEOS:

    print()
    print("=" * 60)
    print("Processing:", filename)
    print("Gloss:", gloss)
    print("=" * 60)

    if not os.path.exists(filename):

        print("[MISSING]", filename)
        continue

    cap = cv2.VideoCapture(filename)

    # --------------------------------------------------------
    # Reset tracking memory for each video
    # --------------------------------------------------------

    last_pose = None
    last_left_hand = None
    last_right_hand = None

    smoothed_pose = None
    smoothed_left = None
    smoothed_right = None

    pose_missing = 0
    left_missing = 0
    right_missing = 0

    clip_frames = 0

    while True:

        ok, frame = cap.read()

        if not ok:
            break

        frame = cv2.resize(
            frame,
            (WIDTH, HEIGHT)
        )

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = holistic.process(rgb)

        # ====================================================
        # GET CURRENT LANDMARKS
        # ====================================================

        current_pose = copy_landmarks(
            results.pose_landmarks
        )

        current_left = copy_landmarks(
            results.left_hand_landmarks
        )

        current_right = copy_landmarks(
            results.right_hand_landmarks
        )

        # ====================================================
        # POSE FALLBACK
        # ====================================================

        if current_pose is not None:

            last_pose = current_pose
            pose_missing = 0

        else:

            pose_missing += 1

        if pose_missing <= MAX_MISSING_FRAMES:

            pose_to_use = last_pose

        else:

            pose_to_use = None


        # ====================================================
        # LEFT HAND FALLBACK
        # ====================================================

        if current_left is not None:

            last_left_hand = current_left
            left_missing = 0

        else:

            left_missing += 1

        if left_missing <= MAX_MISSING_FRAMES:

            left_to_use = last_left_hand

        else:

            left_to_use = None


        # ====================================================
        # RIGHT HAND FALLBACK
        # ====================================================

        if current_right is not None:

            last_right_hand = current_right
            right_missing = 0

        else:

            right_missing += 1

        if right_missing <= MAX_MISSING_FRAMES:

            right_to_use = last_right_hand

        else:

            right_to_use = None


        # ====================================================
        # SMOOTH LANDMARKS
        # ====================================================

        smoothed_pose = smooth_points(
            pose_to_use,
            smoothed_pose,
            SMOOTH_ALPHA
        )

        smoothed_left = smooth_points(
            left_to_use,
            smoothed_left,
            SMOOTH_ALPHA
        )

        smoothed_right = smooth_points(
            right_to_use,
            smoothed_right,
            SMOOTH_ALPHA
        )

        # ====================================================
        # DRAW
        # ====================================================

        canvas = np.zeros(
            (HEIGHT, WIDTH, 3),
            dtype=np.uint8
        )

        draw_pose(
            canvas,
            smoothed_pose
        )

        draw_hand(
            canvas,
            smoothed_left
        )

        draw_hand(
            canvas,
            smoothed_right
        )

        draw_subtitle(
            canvas,
            gloss
        )

        writer.write(canvas)

        last_canvas = canvas.copy()

        clip_frames += 1
        total_frames += 1


    cap.release()

    print(
        f"Rendered {clip_frames} frames for {gloss}"
    )

    # ========================================================
    # PAUSE BETWEEN SIGNS
    # ========================================================

    if last_canvas is not None:

        for _ in range(PAUSE_FRAMES):

            writer.write(
                last_canvas
            )

            total_frames += 1


# ============================================================
# CLEANUP
# ============================================================

writer.release()

holistic.close()

duration = total_frames / FPS

print()
print("=" * 60)
print("DONE")
print("=" * 60)

print("Output:", OUTPUT_VIDEO)
print("Total frames:", total_frames)
print(f"Duration: {duration:.2f} seconds")