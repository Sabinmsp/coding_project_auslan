import cv2
import mediapipe as mp
import numpy as np

# =========================
# INPUT / OUTPUT
# =========================

INPUT_VIDEO = "final_demo.mp4"
OUTPUT_VIDEO = "final_demo_2d.mp4"

WIDTH = 720
HEIGHT = 720


# =========================
# MEDIAPIPE
# =========================

mp_holistic = mp.solutions.holistic
mp_hands = mp.solutions.hands

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.4,
    min_tracking_confidence=0.4
)

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=1,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3
)


# =========================
# OPEN VIDEO
# =========================

cap = cv2.VideoCapture(INPUT_VIDEO)

if not cap.isOpened():
    raise RuntimeError(
        f"Could not open {INPUT_VIDEO}"
    )

fps = cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 30


fourcc = cv2.VideoWriter_fourcc(
    *"mp4v"
)

writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)


# =========================
# LANDMARK TO CANVAS
# =========================

def to_canvas(lm):

    x = int(lm.x * WIDTH)
    y = int(lm.y * HEIGHT)

    return x, y


# =========================
# DRAW BODY
# =========================

def draw_body(canvas, pose):

    if pose is None:
        return

    landmarks = pose.landmark

    # selected body connections
    connections = [
        (11, 12),

        (11, 13),
        (13, 15),

        (12, 14),
        (14, 16),

        (11, 23),
        (12, 24),

        (23, 24),

        (23, 25),
        (25, 27),

        (24, 26),
        (26, 28),
    ]

    # draw lines
    for a, b in connections:

        p1 = landmarks[a]
        p2 = landmarks[b]

        if p1.visibility < 0.3:
            continue

        if p2.visibility < 0.3:
            continue

        cv2.line(
            canvas,
            to_canvas(p1),
            to_canvas(p2),
            (255, 255, 255),
            6,
            cv2.LINE_AA
        )

    # draw joints
    body_points = [
        11, 12,
        13, 14,
        15, 16,
        23, 24,
        25, 26,
        27, 28
    ]

    for index in body_points:

        lm = landmarks[index]

        if lm.visibility < 0.3:
            continue

        cv2.circle(
            canvas,
            to_canvas(lm),
            7,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


# =========================
# DRAW HEAD
# =========================

def draw_head(canvas, pose):

    if pose is None:
        return

    nose = pose.landmark[0]

    if nose.visibility < 0.3:
        return

    x, y = to_canvas(nose)

    cv2.circle(
        canvas,
        (x, y),
        32,
        (255, 255, 255),
        4,
        cv2.LINE_AA
    )


# =========================
# DRAW HANDS
# =========================

def draw_hand(canvas, hand):

    if hand is None:
        return

    # finger connections
    for a, b in mp_hands.HAND_CONNECTIONS:

        p1 = hand.landmark[a]
        p2 = hand.landmark[b]

        cv2.line(
            canvas,
            to_canvas(p1),
            to_canvas(p2),
            (255, 255, 255),
            4,
            cv2.LINE_AA
        )

    # all 21 landmarks
    for lm in hand.landmark:

        cv2.circle(
            canvas,
            to_canvas(lm),
            5,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


# =========================
# MAIN LOOP
# =========================

frame_number = 0

while True:

    success, frame = cap.read()

    if not success:
        break

    frame_number += 1

    # MediaPipe needs RGB
    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    pose_results = holistic.process(
        rgb
    )

    hand_results = hands.process(
        rgb
    )


    # black canvas
    canvas = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8
    )


    # =========================
    # DRAW
    # =========================

    draw_head(
        canvas,
        pose_results.pose_landmarks
    )

    draw_body(
        canvas,
        pose_results.pose_landmarks
    )


    if hand_results.multi_hand_landmarks:

        for hand_landmarks in hand_results.multi_hand_landmarks:

            draw_hand(
                canvas,
                hand_landmarks
            )


    # =========================
    # TITLE
    # =========================

    cv2.putText(
        canvas,
        "AUSLAN 2D AVATAR",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )


    # =========================
    # SAVE
    # =========================

    writer.write(
        canvas
    )

    cv2.imshow(
        "2D Auslan Avatar",
        canvas
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# =========================
# CLEAN UP
# =========================

cap.release()
writer.release()

holistic.close()
hands.close()

cv2.destroyAllWindows()


print("\nDONE")
print("Created:", OUTPUT_VIDEO)