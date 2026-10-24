import cv2
import mediapipe as mp
import numpy as np
from collections import deque

# =========================================================
# SETTINGS
# =========================================================

INPUT_VIDEO = "19.mp4"
OUTPUT_VIDEO = "output_19_nice_2d.mp4"

WIDTH = 900
HEIGHT = 900

SMOOTHING_WINDOW = 5

# =========================================================
# MEDIAPIPE
# =========================================================

mp_holistic = mp.solutions.holistic

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    enable_segmentation=False,
    refine_face_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# =========================================================
# SMOOTHING BUFFERS
# =========================================================

pose_history = deque(maxlen=SMOOTHING_WINDOW)
left_hand_history = deque(maxlen=SMOOTHING_WINDOW)
right_hand_history = deque(maxlen=SMOOTHING_WINDOW)


def landmarks_to_array(landmarks):

    if landmarks is None:
        return None

    result = []

    for lm in landmarks.landmark:
        result.append([
            lm.x,
            lm.y,
            lm.z
        ])

    return np.array(
        result,
        dtype=np.float32
    )


def smooth_landmarks(
    history,
    current
):

    if current is None:

        if len(history) == 0:
            return None

        return history[-1]

    history.append(current)

    return np.mean(
        np.stack(history),
        axis=0
    )


# =========================================================
# CANVAS TRANSFORM
# =========================================================

def get_pose_transform(pose):

    """
    Create a stable avatar position based on shoulder / hip location.

    Returns:
        center_x
        center_y
        scale
    """

    if pose is None or len(pose) < 25:

        return (
            WIDTH // 2,
            HEIGHT // 2,
            1.0
        )

    left_shoulder = pose[11]
    right_shoulder = pose[12]

    left_hip = pose[23]
    right_hip = pose[24]

    shoulder_center = (
        left_shoulder[:2]
        +
        right_shoulder[:2]
    ) / 2

    hip_center = (
        left_hip[:2]
        +
        right_hip[:2]
    ) / 2

    body_center = (
        shoulder_center
        +
        hip_center
    ) / 2

    shoulder_width = np.linalg.norm(
        left_shoulder[:2]
        -
        right_shoulder[:2]
    )

    if shoulder_width < 0.01:
        shoulder_width = 0.2

    desired_width = 330

    scale = (
        desired_width
        /
        (shoulder_width * WIDTH)
    )

    return (
        WIDTH // 2,
        int(HEIGHT * 0.45),
        scale
    )


def transform_point(
    point,
    pose_center,
    target_center,
    scale
):

    px = (
        point[0]
        -
        pose_center[0]
    )

    py = (
        point[1]
        -
        pose_center[1]
    )

    x = int(
        target_center[0]
        +
        px * WIDTH * scale
    )

    y = int(
        target_center[1]
        +
        py * HEIGHT * scale
    )

    return (
        x,
        y
    )


def get_pose_center(pose):

    if pose is None:
        return np.array(
            [0.5, 0.5]
        )

    left_shoulder = pose[11][:2]
    right_shoulder = pose[12][:2]

    left_hip = pose[23][:2]
    right_hip = pose[24][:2]

    shoulder_center = (
        left_shoulder
        +
        right_shoulder
    ) / 2

    hip_center = (
        left_hip
        +
        right_hip
    ) / 2

    return (
        shoulder_center
        +
        hip_center
    ) / 2


# =========================================================
# DRAWING HELPERS
# =========================================================

def draw_bone(
    canvas,
    points,
    a,
    b,
    pose_center,
    target_center,
    scale,
    thickness=12
):

    if points is None:
        return

    if len(points) <= max(a, b):
        return

    p1 = transform_point(
        points[a],
        pose_center,
        target_center,
        scale
    )

    p2 = transform_point(
        points[b],
        pose_center,
        target_center,
        scale
    )

    cv2.line(
        canvas,
        p1,
        p2,
        (220, 220, 220),
        thickness,
        cv2.LINE_AA
    )


def draw_joint(
    canvas,
    points,
    index,
    pose_center,
    target_center,
    scale,
    radius=9
):

    if points is None:
        return

    if len(points) <= index:
        return

    p = transform_point(
        points[index],
        pose_center,
        target_center,
        scale
    )

    cv2.circle(
        canvas,
        p,
        radius,
        (245, 245, 245),
        -1,
        cv2.LINE_AA
    )


# =========================================================
# DRAW BODY
# =========================================================

def draw_body(
    canvas,
    pose,
    pose_center,
    target_center,
    scale
):

    if pose is None:
        return

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14

    LEFT_WRIST = 15
    RIGHT_WRIST = 16

    LEFT_HIP = 23
    RIGHT_HIP = 24

    # torso polygon
    ls = transform_point(
        pose[LEFT_SHOULDER],
        pose_center,
        target_center,
        scale
    )

    rs = transform_point(
        pose[RIGHT_SHOULDER],
        pose_center,
        target_center,
        scale
    )

    lh = transform_point(
        pose[LEFT_HIP],
        pose_center,
        target_center,
        scale
    )

    rh = transform_point(
        pose[RIGHT_HIP],
        pose_center,
        target_center,
        scale
    )

    torso = np.array([
        ls,
        rs,
        rh,
        lh
    ], dtype=np.int32)

    cv2.fillPoly(
        canvas,
        [torso],
        (60, 60, 60)
    )

    # arms
    draw_bone(
        canvas,
        pose,
        LEFT_SHOULDER,
        LEFT_ELBOW,
        pose_center,
        target_center,
        scale,
        18
    )

    draw_bone(
        canvas,
        pose,
        LEFT_ELBOW,
        LEFT_WRIST,
        pose_center,
        target_center,
        scale,
        16
    )

    draw_bone(
        canvas,
        pose,
        RIGHT_SHOULDER,
        RIGHT_ELBOW,
        pose_center,
        target_center,
        scale,
        18
    )

    draw_bone(
        canvas,
        pose,
        RIGHT_ELBOW,
        RIGHT_WRIST,
        pose_center,
        target_center,
        scale,
        16
    )

    # shoulders
    draw_bone(
        canvas,
        pose,
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
        pose_center,
        target_center,
        scale,
        12
    )

    for idx in [
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
        LEFT_ELBOW,
        RIGHT_ELBOW,
        LEFT_WRIST,
        RIGHT_WRIST
    ]:

        draw_joint(
            canvas,
            pose,
            idx,
            pose_center,
            target_center,
            scale
        )


# =========================================================
# DRAW HAND
# =========================================================

HAND_CONNECTIONS = [
    # thumb
    (0,1),(1,2),(2,3),(3,4),

    # index
    (0,5),(5,6),(6,7),(7,8),

    # middle
    (0,9),(9,10),(10,11),(11,12),

    # ring
    (0,13),(13,14),(14,15),(15,16),

    # pinky
    (0,17),(17,18),(18,19),(19,20),

    # palm
    (5,9),(9,13),(13,17),(17,0)
]


def draw_hand(
    canvas,
    hand,
    pose_center,
    target_center,
    scale
):

    if hand is None:
        return

    for a, b in HAND_CONNECTIONS:

        p1 = transform_point(
            hand[a],
            pose_center,
            target_center,
            scale
        )

        p2 = transform_point(
            hand[b],
            pose_center,
            target_center,
            scale
        )

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            5,
            cv2.LINE_AA
        )

    for i, landmark in enumerate(hand):

        p = transform_point(
            landmark,
            pose_center,
            target_center,
            scale
        )

        radius = 5

        if i in [4, 8, 12, 16, 20]:
            radius = 7

        cv2.circle(
            canvas,
            p,
            radius,
            (250, 250, 250),
            -1,
            cv2.LINE_AA
        )


# =========================================================
# DRAW HEAD
# =========================================================

def draw_head(
    canvas,
    pose,
    pose_center,
    target_center,
    scale
):

    if pose is None:
        return

    nose = transform_point(
        pose[0],
        pose_center,
        target_center,
        scale
    )

    left_ear = transform_point(
        pose[7],
        pose_center,
        target_center,
        scale
    )

    right_ear = transform_point(
        pose[8],
        pose_center,
        target_center,
        scale
    )

    radius = int(
        abs(
            left_ear[0]
            -
            right_ear[0]
        ) * 0.75
    )

    radius = max(
        radius,
        38
    )

    center = (
        nose[0],
        nose[1] - 10
    )

    # face
    cv2.circle(
        canvas,
        center,
        radius,
        (85, 85, 85),
        -1,
        cv2.LINE_AA
    )

    cv2.circle(
        canvas,
        center,
        radius,
        (220, 220, 220),
        3,
        cv2.LINE_AA
    )

    # eyes
    eye_y = center[1] - 10

    cv2.circle(
        canvas,
        (center[0] - 15, eye_y),
        4,
        (255,255,255),
        -1
    )

    cv2.circle(
        canvas,
        (center[0] + 15, eye_y),
        4,
        (255,255,255),
        -1
    )

    # simple mouth
    cv2.ellipse(
        canvas,
        (center[0], center[1] + 15),
        (18, 8),
        0,
        0,
        180,
        (220,220,220),
        2,
        cv2.LINE_AA
    )


# =========================================================
# VIDEO
# =========================================================

cap = cv2.VideoCapture(
    INPUT_VIDEO
)

if not cap.isOpened():
    print(
        "Could not open:",
        INPUT_VIDEO
    )
    exit()

fps = cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 25

frame_count = int(
    cap.get(
        cv2.CAP_PROP_FRAME_COUNT
    )
)

fourcc = cv2.VideoWriter_fourcc(
    *"mp4v"
)

writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)

frame_number = 0

# =========================================================
# PROCESS
# =========================================================

while True:

    success, frame = cap.read()

    if not success:
        break

    frame_number += 1

    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    results = holistic.process(
        rgb
    )

    pose_raw = landmarks_to_array(
        results.pose_landmarks
    )

    left_raw = landmarks_to_array(
        results.left_hand_landmarks
    )

    right_raw = landmarks_to_array(
        results.right_hand_landmarks
    )

    pose = smooth_landmarks(
        pose_history,
        pose_raw
    )

    left_hand = smooth_landmarks(
        left_hand_history,
        left_raw
    )

    right_hand = smooth_landmarks(
        right_hand_history,
        right_raw
    )

    canvas = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8
    )

    if pose is not None:

        pose_center = get_pose_center(
            pose
        )

        center_x, center_y, scale = get_pose_transform(
            pose
        )

        target_center = (
            center_x,
            center_y
        )

        draw_body(
            canvas,
            pose,
            pose_center,
            target_center,
            scale
        )

        draw_head(
            canvas,
            pose,
            pose_center,
            target_center,
            scale
        )

        draw_hand(
            canvas,
            left_hand,
            pose_center,
            target_center,
            scale
        )

        draw_hand(
            canvas,
            right_hand,
            pose_center,
            target_center,
            scale
        )

    # top label
    cv2.putText(
        canvas,
        f"Frame {frame_number}/{frame_count}",
        (25, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (220,220,220),
        2,
        cv2.LINE_AA
    )

    # bottom caption box
    cv2.rectangle(
        canvas,
        (0, HEIGHT - 100),
        (WIDTH, HEIGHT),
        (20,20,20),
        -1
    )

    cv2.putText(
        canvas,
        "Auslan Motion",
        (30, HEIGHT - 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255,255,255),
        2,
        cv2.LINE_AA
    )

    writer.write(
        canvas
    )

    cv2.imshow(
        "Nice 2D Auslan Avatar",
        canvas
    )

    if (
        cv2.waitKey(1)
        & 0xFF
        == ord("q")
    ):
        break


# =========================================================
# CLEANUP
# =========================================================

cap.release()
writer.release()
holistic.close()

cv2.destroyAllWindows()

print()
print("DONE")
print("Saved:", OUTPUT_VIDEO)
