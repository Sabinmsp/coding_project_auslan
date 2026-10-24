import cv2
import mediapipe as mp
import numpy as np

# =========================================================
# SETTINGS
# =========================================================

INPUT_VIDEO = "19.mp4"
OUTPUT_VIDEO = "output_19_2d.mp4"

WIDTH = 900
HEIGHT = 900

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
# HELPERS
# =========================================================

def point(landmark):
    """
    Convert MediaPipe normalized coordinate to canvas coordinate.
    """

    x = int(landmark.x * WIDTH)
    y = int(landmark.y * HEIGHT)

    return (x, y)


def draw_line(canvas, landmarks, a, b, thickness=5):

    if landmarks is None:
        return

    p1 = point(landmarks.landmark[a])
    p2 = point(landmarks.landmark[b])

    cv2.line(
        canvas,
        p1,
        p2,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA
    )


def draw_joint(canvas, landmarks, index, radius=7):

    if landmarks is None:
        return

    p = point(landmarks.landmark[index])

    cv2.circle(
        canvas,
        p,
        radius,
        (255, 255, 255),
        -1,
        cv2.LINE_AA
    )


def draw_hand(canvas, hand):

    if hand is None:
        return

    connections = [
        # thumb
        (0, 1), (1, 2), (2, 3), (3, 4),

        # index
        (0, 5), (5, 6), (6, 7), (7, 8),

        # middle
        (0, 9), (9, 10), (10, 11), (11, 12),

        # ring
        (0, 13), (13, 14), (14, 15), (15, 16),

        # pinky
        (0, 17), (17, 18), (18, 19), (19, 20),

        # palm
        (5, 9), (9, 13), (13, 17),
    ]

    for a, b in connections:

        p1 = point(hand.landmark[a])
        p2 = point(hand.landmark[b])

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            3,
            cv2.LINE_AA
        )

    for landmark in hand.landmark:

        p = point(landmark)

        cv2.circle(
            canvas,
            p,
            4,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


def draw_body(canvas, pose):

    if pose is None:
        return

    # MediaPipe Pose landmark IDs
    NOSE = 0

    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14

    LEFT_WRIST = 15
    RIGHT_WRIST = 16

    LEFT_HIP = 23
    RIGHT_HIP = 24

    # head / neck approximation
    draw_line(canvas, pose, LEFT_SHOULDER, RIGHT_SHOULDER)

    # left arm
    draw_line(canvas, pose, LEFT_SHOULDER, LEFT_ELBOW)
    draw_line(canvas, pose, LEFT_ELBOW, LEFT_WRIST)

    # right arm
    draw_line(canvas, pose, RIGHT_SHOULDER, RIGHT_ELBOW)
    draw_line(canvas, pose, RIGHT_ELBOW, RIGHT_WRIST)

    # torso
    draw_line(canvas, pose, LEFT_SHOULDER, LEFT_HIP)
    draw_line(canvas, pose, RIGHT_SHOULDER, RIGHT_HIP)

    draw_line(canvas, pose, LEFT_HIP, RIGHT_HIP)

    # torso diagonals
    draw_line(canvas, pose, LEFT_SHOULDER, RIGHT_HIP, 2)
    draw_line(canvas, pose, RIGHT_SHOULDER, LEFT_HIP, 2)

    # joints
    important_points = [
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

    for idx in important_points:
        draw_joint(canvas, pose, idx)


def draw_head(canvas, pose):

    if pose is None:
        return

    nose = point(pose.landmark[0])

    left_ear = point(pose.landmark[7])
    right_ear = point(pose.landmark[8])

    radius = int(
        abs(left_ear[0] - right_ear[0]) * 0.9
    )

    radius = max(radius, 30)

    center = (
        nose[0],
        nose[1] - int(radius * 0.15)
    )

    cv2.circle(
        canvas,
        center,
        radius,
        (255, 255, 255),
        3,
        cv2.LINE_AA
    )


# =========================================================
# OPEN VIDEO
# =========================================================

cap = cv2.VideoCapture(INPUT_VIDEO)

if not cap.isOpened():
    print(f"Could not open {INPUT_VIDEO}")
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 25

frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print("Video:", INPUT_VIDEO)
print("FPS:", fps)
print("Frames:", frame_count)

# =========================================================
# OUTPUT VIDEO
# =========================================================

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)

# =========================================================
# PROCESS VIDEO
# =========================================================

frame_number = 0

while True:

    success, frame = cap.read()

    if not success:
        break

    frame_number += 1

    # Convert OpenCV BGR -> RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Detect body / hands / face
    results = holistic.process(rgb)

    # blank 2D canvas
    canvas = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8
    )

    # draw body
    draw_body(
        canvas,
        results.pose_landmarks
    )

    # draw head
    draw_head(
        canvas,
        results.pose_landmarks
    )

    # draw left hand
    draw_hand(
        canvas,
        results.left_hand_landmarks
    )

    # draw right hand
    draw_hand(
        canvas,
        results.right_hand_landmarks
    )

    # text
    cv2.putText(
        canvas,
        f"Frame {frame_number}/{frame_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    writer.write(canvas)

    # show live
    cv2.imshow("Auslan 2D Avatar", canvas)

    # Q = quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
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