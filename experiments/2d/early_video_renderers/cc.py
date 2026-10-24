import cv2
import mediapipe as mp
import numpy as np

# =========================================================
# SETTINGS
# =========================================================
INPUT_VIDEO = "3185.mp4"
OUTPUT_VIDEO = "3185_2d_avatar.mp4"

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
    refine_face_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# =========================================================
# HELPERS
# =========================================================
def to_xy(landmark):
    x = int(landmark.x * WIDTH)
    y = int(landmark.y * HEIGHT)
    return x, y


def draw_connection(canvas, landmarks, a, b, thickness=4):
    if landmarks is None:
        return

    p1 = to_xy(landmarks.landmark[a])
    p2 = to_xy(landmarks.landmark[b])

    cv2.line(canvas, p1, p2, (255, 255, 255), thickness)


def draw_point(canvas, landmarks, idx, radius=6):
    if landmarks is None:
        return

    p = to_xy(landmarks.landmark[idx])
    cv2.circle(canvas, p, radius, (255, 255, 255), -1)


def draw_hand(canvas, hand_landmarks):
    if hand_landmarks is None:
        return

    # MediaPipe hand connections
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4),       # thumb
        (0, 5), (5, 6), (6, 7), (7, 8),       # index
        (5, 9), (9, 10), (10, 11), (11, 12),  # middle
        (9, 13), (13, 14), (14, 15), (15, 16),# ring
        (13, 17), (17, 18), (18, 19), (19, 20),# pinky
        (0, 17)
    ]

    for a, b in connections:
        p1 = to_xy(hand_landmarks.landmark[a])
        p2 = to_xy(hand_landmarks.landmark[b])

        cv2.line(canvas, p1, p2, (255, 255, 255), 2)

    for i in range(21):
        draw_point(canvas, hand_landmarks, i, radius=3)


# =========================================================
# VIDEO
# =========================================================
cap = cv2.VideoCapture(INPUT_VIDEO)

fps = cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 25

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)

# =========================================================
# PROCESS FRAMES
# =========================================================
while True:
    ret, frame = cap.read()

    if not ret:
        break

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results = holistic.process(frame_rgb)

    canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

    pose = results.pose_landmarks

    # =====================================================
    # BODY
    # =====================================================
    if pose is not None:

        # shoulders
        draw_connection(canvas, pose, 11, 12)

        # left arm
        draw_connection(canvas, pose, 11, 13)
        draw_connection(canvas, pose, 13, 15)

        # right arm
        draw_connection(canvas, pose, 12, 14)
        draw_connection(canvas, pose, 14, 16)

        # torso
        draw_connection(canvas, pose, 11, 23)
        draw_connection(canvas, pose, 12, 24)
        draw_connection(canvas, pose, 23, 24)

        # legs
        draw_connection(canvas, pose, 23, 25)
        draw_connection(canvas, pose, 25, 27)

        draw_connection(canvas, pose, 24, 26)
        draw_connection(canvas, pose, 26, 28)

        # simple head
        nose = to_xy(pose.landmark[0])

        cv2.circle(
            canvas,
            nose,
            35,
            (255, 255, 255),
            3
        )

    # =====================================================
    # HANDS
    # =====================================================
    draw_hand(canvas, results.left_hand_landmarks)
    draw_hand(canvas, results.right_hand_landmarks)

    # =====================================================
    # LABEL
    # =====================================================
    cv2.putText(
        canvas,
        "Auslan gloss: FLASHING",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )

    writer.write(canvas)

    cv2.imshow("2D Avatar", canvas)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# =========================================================
# CLEANUP
# =========================================================
cap.release()
writer.release()
holistic.close()
cv2.destroyAllWindows()

print("Saved:", OUTPUT_VIDEO)