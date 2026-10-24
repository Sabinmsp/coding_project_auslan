import cv2
import mediapipe as mp
import numpy as np

# =====================================
# TWO WORDS
# =====================================

VIDEOS = [
    ("THANK YOU", "rgb/64788_kf_rgb.mp4"),
    ("STUDENT", "rgb/40255_kf_rgb.mp4"),
]

OUTPUT = "final_2words_2d.mp4"

WIDTH = 720
HEIGHT = 720


# =====================================
# MEDIAPIPE
# =====================================

mp_holistic = mp.solutions.holistic
mp_hands = mp.solutions.hands

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=0,
    smooth_landmarks=True,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3
)


# =====================================
# LANDMARK -> CANVAS
# =====================================

def point(lm):
    return (
        int(lm.x * WIDTH),
        int(lm.y * HEIGHT)
    )


# =====================================
# DRAW BODY
# =====================================

def draw_body(canvas, pose):

    if pose is None:
        return

    L = pose.landmark

    connections = [
        (11, 12),   # shoulders
        (11, 13),
        (13, 15),   # left arm
        (12, 14),
        (14, 16),   # right arm
        (11, 23),
        (12, 24),
        (23, 24)
    ]

    for a, b in connections:

        if L[a].visibility > 0.3 and L[b].visibility > 0.3:

            cv2.line(
                canvas,
                point(L[a]),
                point(L[b]),
                (255, 255, 255),
                5,
                cv2.LINE_AA
            )

    body_points = [
        11, 12,
        13, 14,
        15, 16,
        23, 24
    ]

    for i in body_points:

        if L[i].visibility > 0.3:

            cv2.circle(
                canvas,
                point(L[i]),
                6,
                (255, 255, 255),
                -1
            )

    # head
    nose = L[0]

    if nose.visibility > 0.3:

        cv2.circle(
            canvas,
            point(nose),
            30,
            (255, 255, 255),
            3
        )


# =====================================
# DRAW HAND + FINGERS
# =====================================

def draw_hand(canvas, hand):

    if hand is None:
        return

    for a, b in mp_hands.HAND_CONNECTIONS:

        cv2.line(
            canvas,
            point(hand.landmark[a]),
            point(hand.landmark[b]),
            (255, 255, 255),
            3,
            cv2.LINE_AA
        )

    for lm in hand.landmark:

        cv2.circle(
            canvas,
            point(lm),
            4,
            (255, 255, 255),
            -1
        )


# =====================================
# GET OUTPUT FPS
# =====================================

first_cap = cv2.VideoCapture(VIDEOS[0][1])

fps = first_cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 30

first_cap.release()


# =====================================
# VIDEO WRITER
# =====================================

writer = cv2.VideoWriter(
    OUTPUT,
    cv2.VideoWriter_fourcc(*"mp4v"),
    fps,
    (WIDTH, HEIGHT)
)


# =====================================
# PROCESS BOTH VIDEOS
# =====================================

for gloss, video_path in VIDEOS:

    print("Processing:", gloss)

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Could not open:", video_path)
        continue

    while True:

        success, frame = cap.read()

        if not success:
            break

        # OpenCV BGR -> RGB
        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        # MediaPipe
        results = holistic.process(rgb)

        # black background
        canvas = np.zeros(
            (HEIGHT, WIDTH, 3),
            dtype=np.uint8
        )

        # body
        draw_body(
            canvas,
            results.pose_landmarks
        )

        # left hand
        draw_hand(
            canvas,
            results.left_hand_landmarks
        )

        # right hand
        draw_hand(
            canvas,
            results.right_hand_landmarks
        )

        # =================================
        # SUBTITLE BOX
        # =================================

        cv2.rectangle(
            canvas,
            (0, HEIGHT - 80),
            (WIDTH, HEIGHT),
            (20, 20, 20),
            -1
        )

        # =================================
        # SUBTITLE
        # =================================

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        thickness = 2

        text_size = cv2.getTextSize(
            gloss,
            font,
            font_scale,
            thickness
        )[0]

        x = int(
            (WIDTH - text_size[0]) / 2
        )

        cv2.putText(
            canvas,
            gloss,
            (x, HEIGHT - 30),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA
        )

        # save frame
        writer.write(canvas)

    cap.release()


# =====================================
# FINISH
# =====================================

writer.release()
holistic.close()

print()
print("DONE")
print("Created:", OUTPUT)