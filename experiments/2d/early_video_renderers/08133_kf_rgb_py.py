import cv2
import mediapipe as mp
import numpy as np

# -----------------------------
# FILE NAMES
# -----------------------------
INPUT_VIDEO = "08133_kf_rgb.mp4"
OUTPUT_VIDEO = "08133_2d.mp4"

# -----------------------------
# MEDIAPIPE
# -----------------------------
mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# -----------------------------
# OPEN VIDEO
# -----------------------------
cap = cv2.VideoCapture(INPUT_VIDEO)

if not cap.isOpened():
    print(f"Could not open: {INPUT_VIDEO}")
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print("Input:", INPUT_VIDEO)
print("FPS:", fps)
print("Frames:", frame_count)

# 2D output canvas size
WIDTH = 720
HEIGHT = 720

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

out = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)


# ---------------------------------------------------
# CONVERT MEDIAPIPE POSITION → OUR 2D CANVAS POSITION
# ---------------------------------------------------
def convert_point(landmark):

    # zoom in slightly
    scale = 1.35

    x = landmark.x - 0.5
    y = landmark.y - 0.5

    x *= scale
    y *= scale

    x = int((x + 0.5) * WIDTH)
    y = int((y + 0.5) * HEIGHT)

    return x, y


# ---------------------------------------------------
# DRAW CONNECTIONS
# ---------------------------------------------------
def draw_connections(canvas, landmarks, connections, thickness=4):

    if landmarks is None:
        return

    for connection in connections:

        start_index = connection[0]
        end_index = connection[1]

        start = landmarks.landmark[start_index]
        end = landmarks.landmark[end_index]

        # avoid very low confidence points
        if hasattr(start, "visibility"):
            if start.visibility < 0.4 or end.visibility < 0.4:
                continue

        p1 = convert_point(start)
        p2 = convert_point(end)

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA
        )


# ---------------------------------------------------
# DRAW JOINTS
# ---------------------------------------------------
def draw_points(canvas, landmarks, radius=5):

    if landmarks is None:
        return

    for landmark in landmarks.landmark:

        if hasattr(landmark, "visibility"):
            if landmark.visibility < 0.4:
                continue

        x, y = convert_point(landmark)

        cv2.circle(
            canvas,
            (x, y),
            radius,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


# ---------------------------------------------------
# PROCESS VIDEO
# ---------------------------------------------------
frame_number = 0

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame_number += 1

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results = holistic.process(rgb)

    # black background
    canvas = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8
    )

    # ----------------------------
    # BODY
    # ----------------------------
    draw_connections(
        canvas,
        results.pose_landmarks,
        mp_holistic.POSE_CONNECTIONS,
        thickness=5
    )

    draw_points(
        canvas,
        results.pose_landmarks,
        radius=5
    )

    # ----------------------------
    # LEFT HAND
    # ----------------------------
    draw_connections(
        canvas,
        results.left_hand_landmarks,
        mp_holistic.HAND_CONNECTIONS,
        thickness=2
    )

    draw_points(
        canvas,
        results.left_hand_landmarks,
        radius=3
    )

    # ----------------------------
    # RIGHT HAND
    # ----------------------------
    draw_connections(
        canvas,
        results.right_hand_landmarks,
        mp_holistic.HAND_CONNECTIONS,
        thickness=2
    )

    draw_points(
        canvas,
        results.right_hand_landmarks,
        radius=3
    )

    # progress
    cv2.putText(
        canvas,
        f"{frame_number}/{frame_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    out.write(canvas)

    cv2.imshow("2D Auslan", canvas)

    # press Q to stop
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# -----------------------------
# CLEAN UP
# -----------------------------
cap.release()
out.release()
holistic.close()
cv2.destroyAllWindows()

print()
print("DONE!")
print("Created:", OUTPUT_VIDEO)
