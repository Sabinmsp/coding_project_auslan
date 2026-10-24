import cv2
import mediapipe as mp
import numpy as np

# =========================================================
# FILES
# =========================================================
RGB_VIDEO = "08133_kf_rgb.mp4"
DEPTH_VIDEO = "08133_kf_depth.mp4"

OUTPUT_VIDEO = "08133_rgb_depth_2d.mp4"

# =========================================================
# MEDIAPIPE
# =========================================================
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

# =========================================================
# OPEN VIDEOS
# =========================================================
rgb_cap = cv2.VideoCapture(RGB_VIDEO)
depth_cap = cv2.VideoCapture(DEPTH_VIDEO)

if not rgb_cap.isOpened():
    raise RuntimeError("Could not open RGB video")

if not depth_cap.isOpened():
    raise RuntimeError("Could not open depth video")

fps = rgb_cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 30

WIDTH = 720
HEIGHT = 720

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

out = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)

# =========================================================
# NORMALIZED LANDMARK → CANVAS
# =========================================================
def to_canvas(lm):

    scale = 1.2

    x = lm.x - 0.5
    y = lm.y - 0.5

    x *= scale
    y *= scale

    cx = int((x + 0.5) * WIDTH)
    cy = int((y + 0.5) * HEIGHT)

    return cx, cy


# =========================================================
# GET DEPTH AT LANDMARK POSITION
# =========================================================
def get_depth_value(depth_frame, lm):

    h, w = depth_frame.shape[:2]

    x = int(lm.x * w)
    y = int(lm.y * h)

    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))

    # convert depth frame to grayscale if needed
    if len(depth_frame.shape) == 3:
        gray = cv2.cvtColor(
            depth_frame,
            cv2.COLOR_BGR2GRAY
        )
    else:
        gray = depth_frame

    # small area instead of one pixel
    size = 3

    x1 = max(0, x - size)
    x2 = min(w, x + size + 1)

    y1 = max(0, y - size)
    y2 = min(h, y + size + 1)

    patch = gray[y1:y2, x1:x2]

    if patch.size == 0:
        return 0

    return float(np.median(patch))


# =========================================================
# DEPTH → VISUAL SIZE
# =========================================================
def depth_to_radius(depth_value):

    """
    This makes landmarks visually larger/smaller
    depending on depth.

    This is NOT real centimetres.
    It is just a useful relative depth representation.
    """

    # depth video is displayed as grayscale
    # so normalize roughly from 0-255
    normalized = depth_value / 255.0

    radius = int(3 + normalized * 6)

    return max(3, min(radius, 9))


# =========================================================
# DRAW BODY
# =========================================================
def draw_body(canvas, pose, depth_frame):

    if pose is None:
        return

    L = pose.landmark

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

    for a, b in connections:

        la = L[a]
        lb = L[b]

        if la.visibility < 0.3 or lb.visibility < 0.3:
            continue

        p1 = to_canvas(la)
        p2 = to_canvas(lb)

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            6,
            cv2.LINE_AA
        )

    body_ids = [
        11, 12,
        13, 14,
        15, 16,
        23, 24,
        25, 26,
        27, 28
    ]

    for i in body_ids:

        lm = L[i]

        if lm.visibility < 0.3:
            continue

        d = get_depth_value(depth_frame, lm)
        r = depth_to_radius(d)

        cv2.circle(
            canvas,
            to_canvas(lm),
            r,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


# =========================================================
# DRAW HEAD
# =========================================================
def draw_head(canvas, pose, depth_frame):

    if pose is None:
        return

    nose = pose.landmark[0]

    if nose.visibility < 0.3:
        return

    d = get_depth_value(depth_frame, nose)

    radius = 30 + depth_to_radius(d)

    cv2.circle(
        canvas,
        to_canvas(nose),
        radius,
        (255, 255, 255),
        4,
        cv2.LINE_AA
    )


# =========================================================
# DRAW HAND WITH DEPTH
# =========================================================
def draw_hand(canvas, hand, depth_frame):

    if hand is None:
        return

    # lines between finger joints
    for a, b in mp_hands.HAND_CONNECTIONS:

        lm1 = hand.landmark[a]
        lm2 = hand.landmark[b]

        p1 = to_canvas(lm1)
        p2 = to_canvas(lm2)

        cv2.line(
            canvas,
            p1,
            p2,
            (255, 255, 255),
            4,
            cv2.LINE_AA
        )

    # all 21 hand points
    for lm in hand.landmark:

        depth_value = get_depth_value(
            depth_frame,
            lm
        )

        radius = depth_to_radius(
            depth_value
        )

        cv2.circle(
            canvas,
            to_canvas(lm),
            radius,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )


# =========================================================
# MAIN LOOP
# =========================================================
frame_num = 0

while True:

    rgb_ok, rgb_frame = rgb_cap.read()
    depth_ok, depth_frame = depth_cap.read()

    # stop if either video ends
    if not rgb_ok or not depth_ok:
        break

    frame_num += 1

    # resize depth to RGB dimensions
    depth_frame = cv2.resize(
        depth_frame,
        (
            rgb_frame.shape[1],
            rgb_frame.shape[0]
        )
    )

    rgb = cv2.cvtColor(
        rgb_frame,
        cv2.COLOR_BGR2RGB
    )

    pose_results = holistic.process(rgb)
    hand_results = hands.process(rgb)

    canvas = np.zeros(
        (HEIGHT, WIDTH, 3),
        dtype=np.uint8
    )

    # BODY
    draw_head(
        canvas,
        pose_results.pose_landmarks,
        depth_frame
    )

    draw_body(
        canvas,
        pose_results.pose_landmarks,
        depth_frame
    )

    # HANDS
    if hand_results.multi_hand_landmarks:

        for hand_landmarks in hand_results.multi_hand_landmarks:

            draw_hand(
                canvas,
                hand_landmarks,
                depth_frame
            )

    # label
    cv2.putText(
        canvas,
        "JUMP - RGB + DEPTH",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2
    )

    out.write(canvas)

    cv2.imshow(
        "RGB + Depth Avatar",
        canvas
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# =========================================================
# CLEANUP
# =========================================================
rgb_cap.release()
depth_cap.release()

out.release()

holistic.close()
hands.close()

cv2.destroyAllWindows()

print("DONE")
print("Created:", OUTPUT_VIDEO)
