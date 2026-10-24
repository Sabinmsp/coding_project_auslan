import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Load the phrase: "we need water"
data = np.load("extracted_keypoints/video_1_48.npy")

# Keep only the WATER part
# 63 total frames -> try frames 38 to 62
data = data[38:63]

SUBTITLE = "WATER"
FPS = 25

BODY_CONNECTIONS = [
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12)
]

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20)
]

fig, ax = plt.subplots(figsize=(7, 7))

def valid(p, threshold=0.03):
    return p[2] > threshold and p[0] != 0 and p[1] != 0

def draw_lines(points, connections, width=3):
    for a, b in connections:
        if valid(points[a]) and valid(points[b]):
            ax.plot(
                [points[a][0], points[b][0]],
                [points[a][1], points[b][1]],
                linewidth=width
            )

def update(i):
    ax.clear()

    frame = data[i]

    body = frame[0:26]
    left_hand = frame[94:115]
    right_hand = frame[115:136]

    valid_points = frame[
        (frame[:,2] > 0.1) &
        (frame[:,0] > 0) &
        (frame[:,1] > 0)
    ]

    if len(valid_points):
        xmin = valid_points[:,0].min()
        xmax = valid_points[:,0].max()
        ymin = valid_points[:,1].min()
        ymax = valid_points[:,1].max()

        ax.set_xlim(xmin - 100, xmax + 100)
        ax.set_ylim(ymax + 100, ymin - 100)

    ax.set_aspect("equal")
    ax.axis("off")

    draw_lines(body, BODY_CONNECTIONS, 7)
    draw_lines(left_hand, HAND_CONNECTIONS, 2)
    draw_lines(right_hand, HAND_CONNECTIONS, 2)

    for hand in [left_hand, right_hand]:
        good = hand[:,2] > 0.03
        ax.scatter(hand[good,0], hand[good,1], s=10)

    ax.text(
        0.5,
        0.05,
        "WATER",
        transform=ax.transAxes,
        ha="center",
        fontsize=25,
        fontweight="bold"
    )

animation = FuncAnimation(
    fig,
    update,
    frames=len(data),
    interval=1000/FPS,
    repeat=True
)

plt.show()