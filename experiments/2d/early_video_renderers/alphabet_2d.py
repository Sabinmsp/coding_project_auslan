import cv2
import mediapipe as mp
import numpy as np
import os

# =====================================
# ALPHABET VIDEO IDS
# =====================================

ALPHABET = {
    "A": "29578",
    "B": "85499",
    "C": "08182",
    "D": "39696",
    "E": "12069",
    "F": "24415",
    "G": "54729",
    "H": "36617",
    "I": "89106",
    "J": "36956",
    "K": "26104",
    "L": "82429",
    "M": "61147",
    "N": "03218",

    # O missing for now

    "P": "61474",

    # Q missing for now

    "R": "75989",
    "S": "38832",
    "T": "36494",
    "U": "37017",
    "V": "69992",
    "W": "51828",
    "X": "64120",
    "Y": "40768",
    "Z": "20751",
}

RGB_FOLDER = "rgb"

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
# LANDMARK POINT
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
        (11, 12),
        (11, 13),
        (13, 15),
        (12, 14),
        (14, 16),
        (11, 23),
        (12, 24),
        (23, 24)
    ]

    for a, b in connections:

        if (
            L[a].visibility > 0.3
            and
            L[b].visibility > 0.3
        ):

            cv2.line(
                canvas,
                point(L[a]),
                point(L[b]),
                (255, 255, 255),
                5,
                cv2.LINE_AA
            )

    for i in [
        11, 12,
        13, 14,
        15, 16,
        23, 24
    ]:

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
# DRAW HANDS
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
# USER TYPES WORD
# =====================================

word = input(
    "Type a word to fingerspell: "
).upper().strip()


OUTPUT = (
    word.replace(" ", "_")
    + "_alphabet_2d.mp4"
)


# =====================================
# FIND FIRST VALID LETTER
# =====================================

first_path = None

for letter in word:

    if letter in ALPHABET:

        video_id = ALPHABET[letter]

        path = os.path.join(
            RGB_FOLDER,
            f"{video_id}_kf_rgb.mp4"
        )

        if os.path.exists(path):

            first_path = path
            break


if first_path is None:

    print(
        "No alphabet videos found."
    )

    holistic.close()

    exit()


# =====================================
# GET FPS
# =====================================

cap = cv2.VideoCapture(first_path)

fps = cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 30

cap.release()


# =====================================
# VIDEO WRITER
# =====================================

writer = cv2.VideoWriter(
    OUTPUT,
    cv2.VideoWriter_fourcc(
        *"mp4v"
    ),
    fps,
    (WIDTH, HEIGHT)
)


# =====================================
# PROCESS EACH LETTER
# =====================================

for letter in word:

    if not letter.isalpha():
        continue


    if letter not in ALPHABET:

        print(
            "Missing alphabet letter:",
            letter
        )

        continue


    video_id = ALPHABET[letter]

    path = os.path.join(
        RGB_FOLDER,
        f"{video_id}_kf_rgb.mp4"
    )


    if not os.path.exists(path):

        print(
            "Video missing:",
            path
        )

        continue


    print(
        "Processing:",
        letter,
        "->",
        video_id
    )


    cap = cv2.VideoCapture(path)


    while True:

        success, frame = cap.read()

        if not success:
            break


        # RGB for MediaPipe
        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        results = holistic.process(
            rgb
        )


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


        # hands
        draw_hand(
            canvas,
            results.left_hand_landmarks
        )

        draw_hand(
            canvas,
            results.right_hand_landmarks
        )


        # =================================
        # SUBTITLE
        # =================================

        cv2.rectangle(
            canvas,
            (0, HEIGHT - 90),
            (WIDTH, HEIGHT),
            (20, 20, 20),
            -1
        )


        subtitle = (
            f"{word}  -  {letter}"
        )


        font = cv2.FONT_HERSHEY_SIMPLEX

        size = cv2.getTextSize(
            subtitle,
            font,
            0.9,
            2
        )[0]


        x = max(
            10,
            int(
                (WIDTH - size[0])
                / 2
            )
        )


        cv2.putText(
            canvas,
            subtitle,
            (x, HEIGHT - 35),
            font,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )


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