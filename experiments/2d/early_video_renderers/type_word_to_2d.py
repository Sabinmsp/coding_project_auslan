import cv2
import mediapipe as mp
import numpy as np
import json
import os

# ==========================================
# SETTINGS
# ==========================================

JSON_FILE = "Test_ITW.json"
RGB_FOLDER = "rgb"

WIDTH = 720
HEIGHT = 720


# ==========================================
# LOAD JSON
# ==========================================

with open(JSON_FILE, "r", encoding="utf-8") as f:
    id_to_gloss = json.load(f)

gloss_to_ids = {}

for video_id, gloss in id_to_gloss.items():

    gloss = gloss.upper().strip()

    if gloss not in gloss_to_ids:
        gloss_to_ids[gloss] = []

    gloss_to_ids[gloss].append(video_id)


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
# HELPERS
# ==========================================

def to_point(lm):

    x = int(lm.x * WIDTH)
    y = int(lm.y * HEIGHT)

    return x, y


def find_video(gloss):

    gloss = gloss.upper().strip()

    if gloss not in gloss_to_ids:
        return None, None

    ids = gloss_to_ids[gloss]

    for video_id in ids:

        filename = f"{video_id}_kf_rgb.mp4"

        path = os.path.join(
            RGB_FOLDER,
            filename
        )

        if os.path.exists(path):

            return video_id, path

    return None, None


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

        (23, 24),
    ]

    for a, b in connections:

        if L[a].visibility < 0.3:
            continue

        if L[b].visibility < 0.3:
            continue

        cv2.line(
            canvas,
            to_point(L[a]),
            to_point(L[b]),
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
                to_point(L[i]),
                6,
                (255, 255, 255),
                -1
            )

    nose = L[0]

    if nose.visibility > 0.3:

        cv2.circle(
            canvas,
            to_point(nose),
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

    for a, b in mp_hands.HAND_CONNECTIONS:

        cv2.line(
            canvas,
            to_point(hand.landmark[a]),
            to_point(hand.landmark[b]),
            (255, 255, 255),
            3,
            cv2.LINE_AA
        )

    for lm in hand.landmark:

        cv2.circle(
            canvas,
            to_point(lm),
            4,
            (255, 255, 255),
            -1
        )


# ==========================================
# GET SIGN SEQUENCE
# ==========================================

def build_sequence(word):

    word = word.upper().strip()

    sequence = []

    # Try normal sign first
    video_id, path = find_video(word)

    if path:

        print(
            "FOUND:",
            word,
            "->",
            video_id
        )

        sequence.append({
            "label": word,
            "path": path
        })

        return sequence


    # ======================================
    # FALLBACK TO ALPHABET
    # ======================================

    print(
        "WORD NOT FOUND:",
        word
    )

    print(
        "Using fingerspelling..."
    )


    for letter in word:

        if not letter.isalpha():
            continue

        video_id, path = find_video(letter)

        if path:

            print(
                letter,
                "->",
                video_id
            )

            sequence.append({
                "label": letter,
                "path": path
            })

        else:

            print(
                "Missing letter:",
                letter
            )

    return sequence


# ==========================================
# USER INPUT
# ==========================================

word = input(
    "\nType a word/gloss: "
)

word = word.upper().strip()

sequence = build_sequence(word)


if len(sequence) == 0:

    print(
        "No usable video found."
    )

    holistic.close()

    exit()


# ==========================================
# OUTPUT FILE
# ==========================================

safe_name = word.replace(
    " ",
    "_"
)

OUTPUT_FILE = (
    f"{safe_name}_2d.mp4"
)


# ==========================================
# FPS
# ==========================================

first_cap = cv2.VideoCapture(
    sequence[0]["path"]
)

fps = first_cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 30

first_cap.release()


# ==========================================
# VIDEO WRITER
# ==========================================

fourcc = cv2.VideoWriter_fourcc(
    *"mp4v"
)

writer = cv2.VideoWriter(
    OUTPUT_FILE,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)


# ==========================================
# PROCESS EACH SIGN
# ==========================================

for item in sequence:

    label = item["label"]
    path = item["path"]

    print(
        "Processing:",
        label
    )

    cap = cv2.VideoCapture(path)


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
        # BLACK CANVAS
        # ==================================

        canvas = np.zeros(
            (HEIGHT, WIDTH, 3),
            dtype=np.uint8
        )


        # ==================================
        # DRAW BODY
        # ==================================

        draw_body(
            canvas,
            results.pose_landmarks
        )


        # ==================================
        # LEFT HAND
        # ==================================

        draw_hand(
            canvas,
            results.left_hand_landmarks
        )


        # ==================================
        # RIGHT HAND
        # ==================================

        draw_hand(
            canvas,
            results.right_hand_landmarks
        )


        # ==================================
        # SUBTITLE
        # ==================================

        subtitle = label

        # If fingerspelling,
        # show original word as well
        if label != word:

            subtitle = (
                f"{word} - {label}"
            )


        cv2.rectangle(
            canvas,
            (0, HEIGHT - 80),
            (WIDTH, HEIGHT),
            (20, 20, 20),
            -1
        )


        font = cv2.FONT_HERSHEY_SIMPLEX

        text_size = cv2.getTextSize(
            subtitle,
            font,
            1,
            2
        )[0]


        x = int(
            (WIDTH - text_size[0]) / 2
        )


        cv2.putText(
            canvas,
            subtitle,
            (max(10, x), HEIGHT - 30),
            font,
            1,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )


        # ==================================
        # SAVE FRAME
        # ==================================

        writer.write(
            canvas
        )


    cap.release()


# ==========================================
# FINISH
# ==========================================

writer.release()

holistic.close()

print(
    "\nDONE"
)

print(
    "Created:",
    OUTPUT_FILE
)