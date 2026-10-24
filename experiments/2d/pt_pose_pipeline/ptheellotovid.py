import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# =========================================================
# SETTINGS
# =========================================================

NPY_FILE = "extracted_keypoints/video_1_0.npy"

SUBTITLE = "HELLO"

FPS = 25

# =========================================================
# LOAD KEYPOINTS
# =========================================================

kps = np.load(NPY_FILE)

print("Loaded:", NPY_FILE)
print("Shape:", kps.shape)

# Expected:
# (54, 136, 3)

# =========================================================
# BODY CONNECTIONS
# =========================================================

# First 17 points appear to be body pose points.
# These connections follow a common pose skeleton layout.

BODY_CONNECTIONS = [
    (0, 1),
    (0, 2),

    (1, 3),
    (2, 4),

    (5, 6),

    (5, 7),
    (7, 9),

    (6, 8),
    (8, 10),

    (5, 11),
    (6, 12),

    (11, 12),

    (11, 13),
    (13, 15),

    (12, 14),
    (14, 16)
]

# =========================================================
# HAND CONNECTIONS
# =========================================================

HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),

    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),

    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),

    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),

    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20)
]

# =========================================================
# IMPORTANT
# =========================================================
#
# Your 136 keypoints likely contain:
#
# body
# face
# left hand
# right hand
#
# For the first prototype we use:
#
# body: first 17
#
# hands: last 42 points
#        21 left + 21 right
#
# This is a reasonable first test.
#
# =========================================================

BODY_START = 0
BODY_END = 17

LEFT_HAND_START = 94
LEFT_HAND_END = 115

RIGHT_HAND_START = 115
RIGHT_HAND_END = 136

# =========================================================
# FIGURE
# =========================================================

fig, ax = plt.subplots(figsize=(7, 8))

ax.set_title("Auslan 2D Avatar")

ax.set_xlim(250, 1000)
ax.set_ylim(1100, 100)

ax.set_aspect("equal")

# subtitle
subtitle_text = ax.text(
    0.5,
    0.05,
    SUBTITLE,
    transform=ax.transAxes,
    ha="center",
    va="center",
    fontsize=20
)

# =========================================================
# DRAW CONNECTION FUNCTION
# =========================================================

def draw_connections(points, connections):

    for a, b in connections:

        if a >= len(points) or b >= len(points):
            continue

        x1, y1, c1 = points[a]
        x2, y2, c2 = points[b]

        if c1 > 0.1 and c2 > 0.1:

            ax.plot(
                [x1, x2],
                [y1, y2],
                linewidth=2
            )

# =========================================================
# UPDATE EACH FRAME
# =========================================================

def update(frame_number):

    ax.clear()

    ax.set_xlim(250, 1000)
    ax.set_ylim(1100, 100)

    ax.set_aspect("equal")

    ax.set_title("Auslan 2D Avatar - HELLO")

    frame = kps[frame_number]

    # =========================================
    # BODY
    # =========================================

    body = frame[
        BODY_START:BODY_END
    ]

    valid_body = body[:, 2] > 0.1

    ax.scatter(
        body[valid_body, 0],
        body[valid_body, 1],
        s=30
    )

    draw_connections(
        body,
        BODY_CONNECTIONS
    )

    # =========================================
    # LEFT HAND
    # =========================================

    left_hand = frame[
        LEFT_HAND_START:LEFT_HAND_END
    ]

    valid_left = left_hand[:, 2] > 0.05

    ax.scatter(
        left_hand[valid_left, 0],
        left_hand[valid_left, 1],
        s=20
    )

    draw_connections(
        left_hand,
        HAND_CONNECTIONS
    )

    # =========================================
    # RIGHT HAND
    # =========================================

    right_hand = frame[
        RIGHT_HAND_START:RIGHT_HAND_END
    ]

    valid_right = right_hand[:, 2] > 0.05

    ax.scatter(
        right_hand[valid_right, 0],
        right_hand[valid_right, 1],
        s=20
    )

    draw_connections(
        right_hand,
        HAND_CONNECTIONS
    )

    # =========================================
    # SUBTITLE
    # =========================================

    ax.text(
        0.5,
        0.03,
        "HELLO",
        transform=ax.transAxes,
        ha="center",
        fontsize=22
    )

    ax.text(
        0.02,
        0.97,
        f"Frame: {frame_number + 1}/{len(kps)}",
        transform=ax.transAxes,
        va="top"
    )

# =========================================================
# ANIMATION
# =========================================================

animation = FuncAnimation(
    fig,
    update,
    frames=len(kps),
    interval=1000 / FPS,
    repeat=True
)

plt.show()