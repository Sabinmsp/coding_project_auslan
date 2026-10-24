import pygame
import torch
import numpy as np
import math

# ==========================================
# CONFIG
# ==========================================

WIDTH = 800
HEIGHT = 800
FPS = 25

BG = (245, 245, 245)
SKIN = (235, 185, 145)
SHIRT = (45, 55, 70)
OUTLINE = (25, 25, 25)

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Auslan 2D Human Avatar")

clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 22)

# ==========================================
# LOAD AUSLAN POSE DATA
# ==========================================

data = torch.load(
    "video_2.pt",
    map_location="cpu",
    weights_only=False
)

clip_name = "video_2_0"

clip = data[clip_name]

kps = clip["Annotation"]["Signer"]["KPS"]

if torch.is_tensor(kps):
    kps = kps.cpu().numpy()

xy = kps[..., :2]

# ==========================================
# SMOOTH MOTION
# ==========================================

def smooth_pose(data, window=2):
    result = np.copy(data)

    for frame in range(len(data)):
        start = max(0, frame - window)
        end = min(len(data), frame + window + 1)

        result[frame] = np.nanmean(
            data[start:end],
            axis=0
        )

    return result


xy = smooth_pose(xy)

# ==========================================
# NORMALIZE USING ARM POINTS
# ==========================================

important_ids = [5, 6, 7, 8, 9, 10]

important = xy[:, important_ids]

valid = important[
    np.isfinite(important).all(axis=-1)
]

xmin, ymin = np.percentile(valid, 1, axis=0)
xmax, ymax = np.percentile(valid, 99, axis=0)

# ==========================================
# COORDINATE CONVERSION
# ==========================================

def to_screen(point):
    x, y = point

    sx = (x - xmin) / (xmax - xmin + 1e-6)
    sy = (y - ymin) / (ymax - ymin + 1e-6)

    px = int(180 + sx * 440)
    py = int(180 + sy * 400)

    return px, py


def get_point(points, index):
    if index >= len(points):
        return None

    point = points[index]

    if not np.isfinite(point).all():
        return None

    return to_screen(point)

# ==========================================
# DRAW HELPERS
# ==========================================

def draw_limb(start, end, width=18):
    if start is None or end is None:
        return

    pygame.draw.line(
        screen,
        OUTLINE,
        start,
        end,
        width + 4
    )

    pygame.draw.line(
        screen,
        SKIN,
        start,
        end,
        width
    )

    pygame.draw.circle(
        screen,
        OUTLINE,
        start,
        width // 2 + 2
    )

    pygame.draw.circle(
        screen,
        SKIN,
        start,
        width // 2
    )

    pygame.draw.circle(
        screen,
        OUTLINE,
        end,
        width // 2 + 2
    )

    pygame.draw.circle(
        screen,
        SKIN,
        end,
        width // 2
    )


def draw_hand(wrist):
    if wrist is None:
        return

    # palm
    pygame.draw.circle(
        screen,
        OUTLINE,
        wrist,
        16
    )

    pygame.draw.circle(
        screen,
        SKIN,
        wrist,
        13
    )

    # temporary fingers
    for i in range(5):
        angle = math.radians(
            -145 + i * 28
        )

        length = 24

        end = (
            int(wrist[0] + math.cos(angle) * length),
            int(wrist[1] + math.sin(angle) * length)
        )

        pygame.draw.line(
            screen,
            OUTLINE,
            wrist,
            end,
            5
        )

        pygame.draw.line(
            screen,
            SKIN,
            wrist,
            end,
            3
        )


def draw_face(head_center, expression="happy"):

    x, y = head_center

    # HEAD
    pygame.draw.circle(
        screen,
        OUTLINE,
        head_center,
        46
    )

    pygame.draw.circle(
        screen,
        SKIN,
        head_center,
        42
    )

    # EYES
    pygame.draw.circle(
        screen,
        OUTLINE,
        (x - 14, y - 8),
        4
    )

    pygame.draw.circle(
        screen,
        OUTLINE,
        (x + 14, y - 8),
        4
    )

    # EYEBROWS
    pygame.draw.line(
        screen,
        OUTLINE,
        (x - 22, y - 20),
        (x - 8, y - 23),
        3
    )

    pygame.draw.line(
        screen,
        OUTLINE,
        (x + 8, y - 23),
        (x + 22, y - 20),
        3
    )

    # NOSE
    pygame.draw.line(
        screen,
        OUTLINE,
        (x, y - 2),
        (x - 3, y + 8),
        2
    )

    # HAPPY FACE
    if expression == "happy":

        pygame.draw.arc(
            screen,
            OUTLINE,
            (x - 18, y, 36, 30),
            math.pi,
            math.pi * 2,
            4
        )

    # NEUTRAL FACE
    elif expression == "neutral":

        pygame.draw.line(
            screen,
            OUTLINE,
            (x - 14, y + 15),
            (x + 14, y + 15),
            3
        )

    # SAD FACE
    elif expression == "sad":

        pygame.draw.arc(
            screen,
            OUTLINE,
            (x - 18, y + 12, 36, 25),
            0,
            math.pi,
            4
        )

# ==========================================
# MAIN LOOP
# ==========================================

frame = 0
running = True
paused = False

while running:

    # --------------------------------------
    # EVENTS
    # --------------------------------------

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            if event.key == pygame.K_SPACE:
                paused = not paused

            if event.key == pygame.K_r:
                frame = 0

            if event.key == pygame.K_ESCAPE:
                running = False

    # --------------------------------------
    # BACKGROUND
    # --------------------------------------

    screen.fill(BG)

    # --------------------------------------
    # CURRENT FRAME
    # --------------------------------------

    pts = xy[frame]

    # --------------------------------------
    # ARM POINTS
    # --------------------------------------

    left_shoulder = get_point(pts, 5)
    right_shoulder = get_point(pts, 6)

    left_elbow = get_point(pts, 7)
    right_elbow = get_point(pts, 8)

    left_wrist = get_point(pts, 9)
    right_wrist = get_point(pts, 10)

    # --------------------------------------
    # DRAW BODY
    # --------------------------------------

    if left_shoulder and right_shoulder:

        shoulder_center = (
            (
                left_shoulder[0]
                + right_shoulder[0]
            ) // 2,
            (
                left_shoulder[1]
                + right_shoulder[1]
            ) // 2
        )

        shoulder_width = max(
            110,
            abs(
                right_shoulder[0]
                - left_shoulder[0]
            )
        )

        # ----------------------------------
        # HEAD
        # ----------------------------------

        head_center = (
            shoulder_center[0],
            shoulder_center[1] - 90
        )

        # neck
        pygame.draw.line(
            screen,
            SKIN,
            shoulder_center,
            (
                head_center[0],
                head_center[1] + 42
            ),
            18
        )

        # happy face
        draw_face(
            head_center,
            "happy"
        )

        # ----------------------------------
        # TORSO
        # ----------------------------------

        top_y = shoulder_center[1] + 5
        bottom_y = shoulder_center[1] + 180

        top_half = shoulder_width // 2
        bottom_half = int(
            shoulder_width * 0.35
        )

        torso = [
            (
                shoulder_center[0] - top_half,
                top_y
            ),
            (
                shoulder_center[0] + top_half,
                top_y
            ),
            (
                shoulder_center[0] + bottom_half,
                bottom_y
            ),
            (
                shoulder_center[0] - bottom_half,
                bottom_y
            )
        ]

        pygame.draw.polygon(
            screen,
            OUTLINE,
            torso
        )

        inner_torso = [
            (
                shoulder_center[0] - top_half + 4,
                top_y + 4
            ),
            (
                shoulder_center[0] + top_half - 4,
                top_y + 4
            ),
            (
                shoulder_center[0] + bottom_half - 4,
                bottom_y - 4
            ),
            (
                shoulder_center[0] - bottom_half + 4,
                bottom_y - 4
            )
        ]

        pygame.draw.polygon(
            screen,
            SHIRT,
            inner_torso
        )

    # --------------------------------------
    # REAL ARM MOVEMENT
    # --------------------------------------

    draw_limb(
        left_shoulder,
        left_elbow,
        20
    )

    draw_limb(
        left_elbow,
        left_wrist,
        17
    )

    draw_limb(
        right_shoulder,
        right_elbow,
        20
    )

    draw_limb(
        right_elbow,
        right_wrist,
        17
    )

    # --------------------------------------
    # HANDS
    # --------------------------------------

    draw_hand(left_wrist)
    draw_hand(right_wrist)

    # --------------------------------------
    # TEXT
    # --------------------------------------

    label = font.render(
        f"Auslan pose: {clip_name}",
        True,
        OUTLINE
    )

    screen.blit(
        label,
        (25, 25)
    )

    instructions = font.render(
        "SPACE pause | R restart | ESC quit",
        True,
        OUTLINE
    )

    screen.blit(
        instructions,
        (25, HEIGHT - 45)
    )

    # --------------------------------------
    # DISPLAY
    # --------------------------------------

    pygame.display.flip()

    # --------------------------------------
    # NEXT FRAME
    # --------------------------------------

    if not paused:

        frame += 1

        if frame >= len(xy):
            frame = 0

    clock.tick(FPS)

pygame.quit()