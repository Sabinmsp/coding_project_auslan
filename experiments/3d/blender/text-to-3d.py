import cv2
import mediapipe as mp
import numpy as np
import matplotlib.pyplot as plt

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas


# ============================================
# SETTINGS
# ============================================

INPUT_VIDEO = "08133_kf_rgb.mp4"
OUTPUT_VIDEO = "08133_3d_avatar.mp4"

WIDTH = 900
HEIGHT = 900


# ============================================
# MEDIAPIPE
# ============================================

mp_holistic = mp.solutions.holistic


# --------------------------------------------
# BODY CONNECTIONS
# --------------------------------------------

BODY_CONNECTIONS = [
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

    # hips / legs
    (23, 25),
    (25, 27),

    (24, 26),
    (26, 28),
]


# --------------------------------------------
# HAND CONNECTIONS
# --------------------------------------------

HAND_CONNECTIONS = [
    # thumb
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),

    # index
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),

    # middle
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),

    # ring
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),

    # pinky
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),

    # palm
    (5, 9),
    (9, 13),
    (13, 17),
]


# ============================================
# HELPERS
# ============================================

def landmark_to_xyz(lm):
    """
    Convert MediaPipe normalized coordinates
    into coordinates easier to display in 3D.
    """

    x = (lm.x - 0.5) * 2

    # invert Y so head is visually up
    y = -(lm.y - 0.5) * 2

    # depth
    z = -lm.z

    return np.array([x, y, z])


def get_points(landmarks):
    """
    Convert MediaPipe landmarks into numpy array.
    """

    if landmarks is None:
        return None

    return np.array([
        landmark_to_xyz(lm)
        for lm in landmarks.landmark
    ])


def transform_hand(hand_points, wrist_body_point):
    """
    Hand landmarks use their own depth scale.

    Align hand wrist position with body wrist
    so the fingers stay attached to the arm.
    """

    if hand_points is None:
        return None

    hand = hand_points.copy()

    original_wrist = hand[0]

    hand = hand - original_wrist

    # hand scale
    hand *= 0.55

    # attach to body wrist
    hand += wrist_body_point

    return hand


def smooth_points(current, previous, alpha=0.65):

    if current is None:
        return previous

    if previous is None:
        return current

    return alpha * current + (1 - alpha) * previous


# ============================================
# 3D DRAWING
# ============================================

def render_3d(body, left_hand, right_hand):

    fig = plt.figure(
        figsize=(9, 9),
        dpi=100
    )

    canvas = FigureCanvas(fig)

    ax = fig.add_subplot(
        111,
        projection="3d"
    )


    # --------------------------------
    # BODY
    # --------------------------------

    if body is not None:

        for a, b in BODY_CONNECTIONS:

            p1 = body[a]
            p2 = body[b]

            ax.plot(
                [p1[0], p2[0]],
                [p1[2], p2[2]],
                [p1[1], p2[1]],
                linewidth=5
            )


        # joints

        important_joints = [
            11, 12,
            13, 14,
            15, 16,
            23, 24
        ]

        for joint in important_joints:

            p = body[joint]

            ax.scatter(
                p[0],
                p[2],
                p[1],
                s=45
            )


        # --------------------------------
        # HEAD
        # --------------------------------

        nose = body[0]

        ax.scatter(
            nose[0],
            nose[2],
            nose[1],
            s=350
        )


    # --------------------------------
    # HAND DRAW FUNCTION
    # --------------------------------

    def draw_hand(hand):

        if hand is None:
            return

        for a, b in HAND_CONNECTIONS:

            p1 = hand[a]
            p2 = hand[b]

            ax.plot(
                [p1[0], p2[0]],
                [p1[2], p2[2]],
                [p1[1], p2[1]],
                linewidth=2
            )

        ax.scatter(
            hand[:, 0],
            hand[:, 2],
            hand[:, 1],
            s=12
        )


    draw_hand(left_hand)
    draw_hand(right_hand)


    # --------------------------------
    # CAMERA
    # --------------------------------

    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.0, 1.0)
    ax.set_zlim(-1.1, 1.1)


    # camera angle

    ax.view_init(
        elev=5,
        azim=-90
    )


    # remove grid / axes

    ax.set_axis_off()


    plt.tight_layout(
        pad=0
    )


    # ========================================
    # MATPLOTLIB -> OPENCV FRAME
    # ========================================

    canvas.draw()

    image = np.asarray(
        canvas.buffer_rgba()
    )

    image = cv2.cvtColor(
        image,
        cv2.COLOR_RGBA2BGR
    )

    image = cv2.resize(
        image,
        (WIDTH, HEIGHT)
    )

    plt.close(fig)

    return image


# ============================================
# VIDEO
# ============================================

cap = cv2.VideoCapture(INPUT_VIDEO)

if not cap.isOpened():

    raise FileNotFoundError(
        f"Cannot open {INPUT_VIDEO}"
    )


fps = cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0:
    fps = 25


fourcc = cv2.VideoWriter_fourcc(
    *"mp4v"
)

writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    fps,
    (WIDTH, HEIGHT)
)


# ============================================
# SMOOTHING MEMORY
# ============================================

previous_body = None
previous_left = None
previous_right = None


# ============================================
# MEDIAPIPE MODEL
# ============================================

with mp_holistic.Holistic(

    static_image_mode=False,

    model_complexity=2,

    smooth_landmarks=True,

    refine_face_landmarks=False,

    min_detection_confidence=0.5,

    min_tracking_confidence=0.5

) as holistic:


    frame_number = 0


    while cap.isOpened():


        success, frame = cap.read()


        if not success:
            break


        frame_number += 1


        # ------------------------------------
        # BGR -> RGB
        # ------------------------------------

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        # ------------------------------------
        # MEDIAPIPE
        # ------------------------------------

        results = holistic.process(rgb)


        # ------------------------------------
        # BODY
        # ------------------------------------

        body = get_points(
            results.pose_landmarks
        )


        # ------------------------------------
        # HANDS
        # ------------------------------------

        left_hand = get_points(
            results.left_hand_landmarks
        )

        right_hand = get_points(
            results.right_hand_landmarks
        )


        # ------------------------------------
        # ATTACH HANDS TO BODY
        # ------------------------------------

        if body is not None:


            # MediaPipe Pose:
            #
            # 15 = left wrist
            # 16 = right wrist


            if left_hand is not None:

                left_hand = transform_hand(
                    left_hand,
                    body[15]
                )


            if right_hand is not None:

                right_hand = transform_hand(
                    right_hand,
                    body[16]
                )


        # ====================================
        # SMOOTH MOTION
        # ====================================

        body = smooth_points(
            body,
            previous_body
        )

        left_hand = smooth_points(
            left_hand,
            previous_left
        )

        right_hand = smooth_points(
            right_hand,
            previous_right
        )


        previous_body = body
        previous_left = left_hand
        previous_right = right_hand


        # ====================================
        # DRAW 3D AVATAR
        # ====================================

        avatar_frame = render_3d(

            body,

            left_hand,

            right_hand

        )


        # ------------------------------------
        # FRAME NUMBER
        # ------------------------------------

        cv2.putText(

            avatar_frame,

            f"Frame {frame_number}",

            (30, 50),

            cv2.FONT_HERSHEY_SIMPLEX,

            1,

            (30, 30, 30),

            2

        )


        writer.write(
            avatar_frame
        )


        print(
            f"\rProcessing frame {frame_number}",
            end=""
        )


# ============================================
# FINISH
# ============================================

cap.release()

writer.release()


print(
    f"\n\nDONE ✅\nSaved to: {OUTPUT_VIDEO}"
)