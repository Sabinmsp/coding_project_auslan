import cv2
import mediapipe as mp
import numpy as np
import os

# ==========================================
# ALPHABET IDs
# ==========================================

# Clip IDs into rgb/{id}_kf_rgb.mp4 -- this project's own dataset.
# O and Q are NOT in that dataset (checked: zero clips for either letter
# anywhere in the 6,430-clip corpus). They come from the Auslan Signbank
# dictionary instead -- auslan.org.au/dictionary/words/O-1.html and
# .../Q-1.html -- downloaded directly and stored in
# auslan_2d_demo/fingerspell_letters/{O,Q}_signbank_raw.mp4, since they
# have no id in this scheme to look up. See auslan_2d_demo/README.md.
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
    "P": "61474",
    "R": "75989",
    "S": "38832",
    "T": "36494",
    "U": "37017",
    "V": "69992",
    "W": "51828",
    "X": "64120",
    "Y": "40768",
    "Z": "20751",
    # "O" and "Q": see auslan_2d_demo/fingerspell_letters/{O,Q}.mp4 -- not
    # clip IDs from rgb/, sourced from Auslan Signbank instead (see above).
}

RGB_FOLDER = "rgb"

WIDTH = 720
HEIGHT = 720


# ==========================================
# TYPE WORD
# ==========================================

WORD = input("Type word: ").upper().strip()

OUTPUT = f"{WORD}_2d_fingerspell.mp4"


# ==========================================
# MEDIAPIPE
# ==========================================

mp_holistic = mp.solutions.holistic
mp_hands = mp.solutions.hands

holistic = mp_holistic.Holistic(
    static_image_mode=False,
    model_complexity=0,
    smooth_landmarks=True,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3
)


# ==========================================
# POINT
# ==========================================

def point(lm):

    return (
        int(lm.x * WIDTH),
        int(lm.y * HEIGHT)
    )


# ==========================================
# DRAW BODY
# ==========================================

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


# ==========================================
# DRAW HAND
# ==========================================

def draw_hand(canvas, hand):

    if hand is None:
        return


    # finger lines
    for a, b in mp_hands.HAND_CONNECTIONS:

        cv2.line(
            canvas,
            point(hand.landmark[a]),
            point(hand.landmark[b]),
            (255, 255, 255),
            3,
            cv2.LINE_AA
        )


    # finger joints
    for lm in hand.landmark:

        cv2.circle(
            canvas,
            point(lm),
            4,
            (255, 255, 255),
            -1
        )


# ==========================================
# CREATE LETTER SEQUENCE
# ==========================================

sequence = []

for letter in WORD:

    if not letter.isalpha():
        continue


    if letter not in ALPHABET:

        print("Missing letter:", letter)

        continue


    video_id = ALPHABET[letter]

    video_path = os.path.join(
        RGB_FOLDER,
        f"{video_id}_kf_rgb.mp4"
    )


    if os.path.exists(video_path):

        sequence.append(
            (letter, video_path)
        )

        print(
            letter,
            "->",
            video_id
        )

    else:

        print(
            "Video missing:",
            video_path
        )


# ==========================================
# CHECK
# ==========================================

if len(sequence) == 0:

    print("No videos found.")

    holistic.close()

    exit()


# ==========================================
# FPS
# ==========================================

first = cv2.VideoCapture(
    sequence[0][1]
)

fps = first.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 30

first.release()


# ==========================================
# OUTPUT VIDEO
# ==========================================

writer = cv2.VideoWriter(
    OUTPUT,
    cv2.VideoWriter_fourcc(
        *"mp4v"
    ),
    fps,
    (WIDTH, HEIGHT)
)


# ==========================================
# PROCESS EVERY LETTER
# ==========================================

for letter, video_path in sequence:

    print(
        "Making 2D letter:",
        letter
    )


    cap = cv2.VideoCapture(
        video_path
    )


    while True:

        success, frame = cap.read()

        if not success:
            break


        # ==================================
        # MEDIAPIPE
        # ==================================

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = holistic.process(
            rgb
        )


        # ==================================
        # BLACK 2D CANVAS
        # ==================================

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


        # ==================================
        # SUBTITLE
        # ==================================

        cv2.rectangle(
            canvas,
            (0, HEIGHT - 90),
            (WIDTH, HEIGHT),
            (20, 20, 20),
            -1
        )


        subtitle = f"{WORD}   Letter: {letter}"


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
                (WIDTH - size[0]) / 2
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


        # save
        writer.write(
            canvas
        )


    cap.release()


# ==========================================
# FINISH
# ==========================================

writer.release()

holistic.close()


print()
print("DONE!")
print("Created:", OUTPUT)