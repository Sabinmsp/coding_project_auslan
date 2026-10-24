import cv2
import mediapipe as mp
import numpy as np

# =========================
# FILES
# =========================
INPUT_VIDEO = "08133_kf_rgb.mp4"
OUTPUT_VIDEO = "08133_jump_2d.mp4"

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
# VIDEO INPUT
# =========================
cap = cv2.VideoCapture(INPUT_VIDEO)

if not cap.isOpened():
    raise RuntimeError(f"Cannot open {INPUT_VIDEO}")

fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# output size
WIDTH = 720
HEIGHT = 720

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

out = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)

# =========================
# LANDMARK CONVERSION
# =========================
def point(lm):
    """
    Convert MediaPipe normalized coordinates
    into our 2D avatar canvas.
    """

    # zoom
    scale = 1.25

    x = lm.x - 0.5
    y = lm.y - 0.5

    x *= scale
    y *= scale

    x = int((x + 0.5) * WIDTH)
    y = int((y + 0.5) * HEIGHT)

    return x, y


# =========================
# DRAW BODY
# =========================
def draw_body(canvas, pose):

    if pose is None:
        return

    L = pose.landmark

    # important body landmark IDs
    connections = [
        # shoulders
        (11, 12),

        # left arm
        (11, 13),
        (13, 15),

        # right arm
        (12, 14),
        (14, 16),

        # torso
        (11, 23),
        (12, 24),
        (23, 24),

        # left leg
        (23, 25),
        (25, 27),

        # right leg
        (24, 26),
        (26, 28),
    ]

    for a, b in connections:

        la = L[a]
        lb = L[b]

        if la.visibility < 0.3 or lb.visibility < 0.3:
            continue

        p1 = point(la)
        p2 = point(lb)

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            8,
            cv2.LINE_AA
        )

    # body joints
    joint_ids = [
        11, 12,
        13, 14,
        15, 16,
        23, 24,
        25, 26,
        27, 28
    ]

    for i in joint_ids:

        lm = L[i]

        if lm.visibility < 0.3:
            continue

        cv2.circle(
            canvas,
            point(lm),
            8,
            (255, 255, 255),
            -1
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

    x, y = point(nose)

    cv2.circle(
        canvas,
        (x, y),
        38,
        (255, 255, 255),
        5,
        cv2.LINE_AA
    )


# =========================
# DRAW HAND + FINGERS
# =========================
def draw_hand(canvas, hand):

    if hand is None:
        return

    connections = mp_hands.HAND_CONNECTIONS

    for a, b in connections:

        p1 = point(hand.landmark[a])
        p2 = point(hand.landmark[b])

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            4,
            cv2.LINE_AA
        )

    # draw all 21 finger points
    for lm in hand.landmark:

        cv2.circle(
            canvas,
            point(lm),
            6,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


# =========================
# MAIN LOOP
# =========================
frame_num = 0

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame_num += 1

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # body
    results = holistic.process(rgb)

    # separate hand detector
    hand_results = hands.process(rgb)

    # black canvas
    canvas = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8
    )

    # draw avatar
    draw_head(
        canvas,
        results.pose_landmarks
    )

    draw_body(
        canvas,
        results.pose_landmarks
    )

    # hands
    if hand_results.multi_hand_landmarks:

        for hand_landmarks in hand_results.multi_hand_landmarks:

            draw_hand(
                canvas,
                hand_landmarks
            )

    # label
    cv2.putText(
        canvas,
        "JUMP",
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 255, 255),
        3
    )

    cv2.putText(
        canvas,
        f"{frame_num}/{frame_count}",
        (20, HEIGHT - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    out.write(canvas)

    cv2.imshow(
        "2D Auslan Avatar",
        canvas
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# =========================
# CLEANUP
# =========================
cap.release()
out.release()

holistic.close()
hands.close()

cv2.destroyAllWindows()

print("DONE")
print("Input :", INPUT_VIDEO)
print("Gloss :", "JUMP")
print("Output:", OUTPUT_VIDEO)