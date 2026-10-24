import json
import os
import cv2

# ==========================================
# SETTINGS
# ==========================================

JSON_FILE = "Test_ITW.json"

# Your videos are here
RGB_FOLDER = "rgb"

OUTPUT_FILE = "final_demo.mp4"

WORDS = [
    "THANK YOU",
    "STUDENT",
    "APPLE",      # example: if missing -> fingerspell
    "BEFORE",
    "FRIDAY",
]


# ==========================================
# LOAD JSON
# ==========================================

with open(JSON_FILE, "r", encoding="utf-8") as f:
    id_to_gloss = json.load(f)

print("Loaded mappings:", len(id_to_gloss))


# ==========================================
# CREATE GLOSS -> IDs
# ==========================================

gloss_to_ids = {}

for video_id, gloss in id_to_gloss.items():

    gloss = gloss.upper().strip()

    if gloss not in gloss_to_ids:
        gloss_to_ids[gloss] = []

    gloss_to_ids[gloss].append(video_id)


print("Unique glosses:", len(gloss_to_ids))


# ==========================================
# FIND RGB VIDEO
# ==========================================

def find_video(gloss):

    gloss = gloss.upper().strip()

    # Gloss does not exist in JSON
    if gloss not in gloss_to_ids:
        return None, None

    ids = gloss_to_ids[gloss]

    # Some glosses have multiple IDs.
    # Try all of them until an RGB video is found.
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
# FINGERSPELL FALLBACK
# ==========================================

def fingerspell_word(word):

    word = word.upper()

    print("\nFINGER SPELL:", word)

    letters = []

    for letter in word:

        # Ignore spaces, hyphens, punctuation
        if not letter.isalpha():
            continue

        video_id, video_path = find_video(letter)

        if video_path is not None:

            print(
                letter,
                "->",
                video_id,
                "->",
                video_path
            )

            letters.append({
                "gloss": letter,
                "original_word": word,
                "id": video_id,
                "path": video_path,
                "type": "letter"
            })

        else:

            print(
                "MISSING LETTER:",
                letter
            )

    return letters


# ==========================================
# BUILD VIDEO SEQUENCE
# ==========================================

sequence = []

print("\nSEARCH RESULTS")
print("=" * 50)

for word in WORDS:

    word = word.upper().strip()

    video_id, video_path = find_video(word)

    # ======================================
    # NORMAL SIGN FOUND
    # ======================================

    if video_path is not None:

        print(
            word,
            "->",
            video_id,
            "-> FOUND"
        )

        sequence.append({
            "gloss": word,
            "original_word": word,
            "id": video_id,
            "path": video_path,
            "type": "word"
        })

    # ======================================
    # NOT FOUND -> SPELL LETTERS
    # ======================================

    else:

        print(
            word,
            "-> NOT FOUND"
        )

        print(
            "Using alphabet fallback..."
        )

        letter_videos = fingerspell_word(word)

        sequence.extend(letter_videos)


# ==========================================
# CHECK
# ==========================================

if len(sequence) == 0:

    print("\nNo videos could be found.")
    exit()


print("\nFINAL VIDEO SEQUENCE")
print("=" * 50)

for item in sequence:

    print(
        item["type"],
        "->",
        item["gloss"],
        "->",
        item["id"]
    )


# ==========================================
# GET VIDEO SETTINGS
# ==========================================

first_cap = cv2.VideoCapture(
    sequence[0]["path"]
)

fps = first_cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 30


width = int(
    first_cap.get(
        cv2.CAP_PROP_FRAME_WIDTH
    )
)

height = int(
    first_cap.get(
        cv2.CAP_PROP_FRAME_HEIGHT
    )
)

first_cap.release()


print("\nOUTPUT SETTINGS")
print("FPS:", fps)
print("Size:", width, "x", height)


# ==========================================
# CREATE OUTPUT
# ==========================================

fourcc = cv2.VideoWriter_fourcc(
    *"mp4v"
)

writer = cv2.VideoWriter(
    OUTPUT_FILE,
    fourcc,
    fps,
    (width, height)
)


# ==========================================
# WRITE EACH VIDEO
# ==========================================

for item in sequence:

    print(
        "Adding:",
        item["gloss"]
    )

    cap = cv2.VideoCapture(
        item["path"]
    )

    while True:

        success, frame = cap.read()

        if not success:
            break

        # Make all videos same size
        frame = cv2.resize(
            frame,
            (width, height)
        )


        # ==================================
        # SUBTITLE BACKGROUND
        # ==================================

        subtitle_height = 100

        cv2.rectangle(
            frame,
            (0, height - subtitle_height),
            (width, height),
            (0, 0, 0),
            -1
        )


        # ==================================
        # SUBTITLE TEXT
        # ==================================

        if item["type"] == "letter":

            text = (
                f"{item['original_word']} "
                f"- Fingerspell: {item['gloss']}"
            )

        else:

            text = item["gloss"]


        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.9
        thickness = 2

        text_size = cv2.getTextSize(
            text,
            font,
            font_scale,
            thickness
        )[0]

        text_width = text_size[0]

        x = max(
            10,
            int((width - text_width) / 2)
        )

        y = height - 40


        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA
        )


        # ==================================
        # SAVE FRAME
        # ==================================

        writer.write(frame)


        # ==================================
        # PREVIEW
        # ==================================

        cv2.imshow(
            "Auslan Demo",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


    cap.release()


# ==========================================
# FINISH
# ==========================================

writer.release()

cv2.destroyAllWindows()


print("\n==============================")
print("DONE")
print("==============================")

print(
    "Created:",
    OUTPUT_FILE
)