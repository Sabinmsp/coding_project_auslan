"""
Keypoint layout.

The Auslan_Daily_Communication pose files use 136 keypoints:

      0- 16  body      COCO-17
     17- 25  feet/aux  (9 points, very low confidence -- unused)
     26- 93  face      68-point layout
     94-114  left hand  21-point layout
    115-135  right hand 21-point layout

Standard COCO-WholeBody (133) is also supported so the pipeline keeps working
if a lexicon is built from a different pose extractor.
"""

from dataclasses import dataclass


# --- COCO-17 body ----------------------------------------------------------

NOSE = 0
L_EYE, R_EYE = 1, 2
L_EAR, R_EAR = 3, 4
L_SHOULDER, R_SHOULDER = 5, 6
L_ELBOW, R_ELBOW = 7, 8
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANKLE, R_ANKLE = 15, 16

# Upper body only: the signers are seated, legs are never visible.
ARM_CHAINS = [
    (L_SHOULDER, L_ELBOW, L_WRIST),
    (R_SHOULDER, R_ELBOW, R_WRIST),
]

TORSO_QUAD = (L_SHOULDER, R_SHOULDER, R_HIP, L_HIP)

# --- 21-point hand ---------------------------------------------------------

HAND_WRIST = 0
FINGERS = {
    "thumb": (0, 1, 2, 3, 4),
    "index": (0, 5, 6, 7, 8),
    "middle": (0, 9, 10, 11, 12),
    "ring": (0, 13, 14, 15, 16),
    "pinky": (0, 17, 18, 19, 20),
}
PALM_ARCS = [(5, 9), (9, 13), (13, 17), (0, 5), (0, 17)]
FINGER_TIPS = (4, 8, 12, 16, 20)

# --- 68-point face ---------------------------------------------------------

FACE_JAW = tuple(range(0, 17))
FACE_BROW_R = tuple(range(17, 22))
FACE_BROW_L = tuple(range(22, 27))
FACE_NOSE_BRIDGE = tuple(range(27, 31))
FACE_NOSTRILS = tuple(range(31, 36))
FACE_EYE_R = tuple(range(36, 42))
FACE_EYE_L = tuple(range(42, 48))
FACE_MOUTH_OUTER = tuple(range(48, 60))
FACE_MOUTH_INNER = tuple(range(60, 68))


@dataclass(frozen=True)
class Layout:
    """Where each body part lives inside the keypoint array."""

    n_joints: int
    body: slice
    face: slice
    left_hand: slice
    right_hand: slice
    name: str = ""

    def slice_of(self, part):
        return getattr(self, part)


LAYOUT_136 = Layout(
    n_joints=136,
    body=slice(0, 17),
    face=slice(26, 94),
    left_hand=slice(94, 115),
    right_hand=slice(115, 136),
    name="auslan-136",
)

LAYOUT_133 = Layout(
    n_joints=133,
    body=slice(0, 17),
    face=slice(23, 91),
    left_hand=slice(91, 112),
    right_hand=slice(112, 133),
    name="coco-wholebody-133",
)

LAYOUT_17 = Layout(
    n_joints=17,
    body=slice(0, 17),
    face=slice(0, 0),
    left_hand=slice(0, 0),
    right_hand=slice(0, 0),
    name="coco-17",
)

_KNOWN = {l.n_joints: l for l in (LAYOUT_136, LAYOUT_133, LAYOUT_17)}


def detect_layout(n_joints):
    """Pick the keypoint layout for an array with `n_joints` joints."""
    if n_joints in _KNOWN:
        return _KNOWN[n_joints]
    if n_joints >= 133:
        # Unknown extractor: assume body + face + two hands packed at the end.
        return Layout(
            n_joints=n_joints,
            body=slice(0, 17),
            face=slice(n_joints - 110, n_joints - 42),
            left_hand=slice(n_joints - 42, n_joints - 21),
            right_hand=slice(n_joints - 21, n_joints),
            name=f"guessed-{n_joints}",
        )
    return Layout(
        n_joints=n_joints,
        body=slice(0, min(17, n_joints)),
        face=slice(0, 0),
        left_hand=slice(0, 0),
        right_hand=slice(0, 0),
        name=f"body-only-{n_joints}",
    )
