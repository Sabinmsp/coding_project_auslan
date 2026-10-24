"""
MediaPipe landmarks -> CC4 rig animation (Blender).

Direction-vector retargeting: every driven bone is *aimed* along the vector
between the two MediaPipe joints it corresponds to. Bone positions are never
set directly, so limb lengths stay exactly as the rig defines them and the
character cannot drift or stretch.

    /Applications/Blender.app/Contents/MacOS/Blender Jake_rig.blend \
        --background --python retarget.py -- \
        --npz 08133_kf_rgb_landmarks.npz --out Jake_08133.blend --render

Coordinate spaces
-----------------
The armature object carries a +90 deg X rotation, so in ARMATURE OBJECT space
the rig is Y-up:

    +X = character's left     +Y = up     +Z = forward (toward camera)

MediaPipe pose_world is metric, hip-centred, and:

    +x = character's left     +y = down   -z = toward camera

so the conversion is (x, -y, -z). Verified against the rest pose, not assumed.
"""

import argparse
import sys

import numpy as np

import bpy
from mathutils import Matrix, Quaternion, Vector


# ---------------------------------------------------------------------------
# MediaPipe pose landmark indices
# ---------------------------------------------------------------------------

NOSE = 0
L_EAR, R_EAR = 7, 8
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_PINKY, R_PINKY = 17, 18
L_INDEX, R_INDEX = 19, 20
L_HIP, R_HIP = 23, 24


# ---------------------------------------------------------------------------
# rig bone names (confirmed by inspect_rig.py -- Reallusion CC4, not Mixamo)
# ---------------------------------------------------------------------------

ARMATURE = "Armature"

SPINE01 = "CC_Base_Spine01"
SPINE02 = "CC_Base_Spine02"
NECK = "CC_Base_NeckTwist01"
HEAD = "CC_Base_Head"

L_UPPERARM, R_UPPERARM = "CC_Base_L_Upperarm", "CC_Base_R_Upperarm"
L_FOREARM, R_FOREARM = "CC_Base_L_Forearm", "CC_Base_R_Forearm"
L_HAND, R_HAND = "CC_Base_L_Hand", "CC_Base_R_Hand"

# Parent-first. Twist bones (ForearmTwist/UpperarmTwist) are deliberately
# excluded -- driving them is what produces mangled arms.
BONE_ORDER = [
    SPINE01, SPINE02, NECK,
    L_UPPERARM, L_FOREARM, L_HAND,
    R_UPPERARM, R_FOREARM, R_HAND,
]


# ---------------------------------------------------------------------------
# coordinate conversion + cleanup
# ---------------------------------------------------------------------------

def mp_to_object(pts):
    """MediaPipe world coords -> armature object space. pts: (..., 3)."""
    out = np.empty_like(pts)
    out[..., 0] = pts[..., 0]
    out[..., 1] = -pts[..., 1]
    out[..., 2] = -pts[..., 2]
    return out


def smooth_series(pts, window=5):
    """Centred moving average over the frame axis to damp MediaPipe jitter."""
    frames = pts.shape[0]
    window = min(int(window) | 1, max(1, (frames // 2) * 2 - 1))
    if window < 3 or frames < 3:
        return pts
    pad = window // 2
    padded = np.pad(pts, ((pad, pad), (0, 0), (0, 0)), mode="edge")
    kernel = np.ones(window) / window
    out = np.empty_like(pts)
    for j in range(pts.shape[1]):
        for axis in range(pts.shape[2]):
            out[:, j, axis] = np.convolve(padded[:, j, axis], kernel, "valid")
    return out


def vec(a, b):
    """Direction from point a to point b as a mathutils Vector."""
    d = Vector((float(b[0] - a[0]), float(b[1] - a[1]), float(b[2] - a[2])))
    return d.normalized() if d.length > 1e-8 else None


# ---------------------------------------------------------------------------
# aiming
# ---------------------------------------------------------------------------

def aim_bone(pose_bone, target_dir, weight=1.0):
    """
    Rotate a pose bone so its +Y axis points along `target_dir`.

    Works in armature object space, which is what pose_bone.matrix uses.
    `weight` blends between the bone's current direction and the target,
    which keeps the spine from over-bending.
    """
    if target_dir is None:
        return

    m = pose_bone.matrix.copy()
    current = (m.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()

    rot = current.rotation_difference(target_dir)
    if weight < 1.0:
        rot = Quaternion().slerp(rot, float(weight))

    basis = rot.to_matrix() @ m.to_3x3()
    pose_bone.matrix = Matrix.Translation(m.translation) @ basis.to_4x4()

    # Children read their parent's world matrix, so it must be committed
    # before the next bone in the chain is aimed.
    bpy.context.view_layer.update()


def frame_targets(p, cfg):
    """
    Build {bone_name: direction} for one frame.

    p is (33, 3) in armature object space.
    """
    hip_mid = (p[L_HIP] + p[R_HIP]) / 2.0
    sho_mid = (p[L_SHOULDER] + p[R_SHOULDER]) / 2.0
    ear_mid = (p[L_EAR] + p[R_EAR]) / 2.0

    spine_dir = vec(hip_mid, sho_mid)

    return {
        SPINE01: (spine_dir, cfg.spine_weight),
        SPINE02: (spine_dir, cfg.spine_weight),
        NECK: (vec(sho_mid, ear_mid), cfg.head_weight),

        L_UPPERARM: (vec(p[L_SHOULDER], p[L_ELBOW]), 1.0),
        L_FOREARM: (vec(p[L_ELBOW], p[L_WRIST]), 1.0),
        L_HAND: (vec(p[L_WRIST], p[L_INDEX]), cfg.hand_weight),

        R_UPPERARM: (vec(p[R_SHOULDER], p[R_ELBOW]), 1.0),
        R_FOREARM: (vec(p[R_ELBOW], p[R_WRIST]), 1.0),
        R_HAND: (vec(p[R_WRIST], p[R_INDEX]), cfg.hand_weight),
    }


# ---------------------------------------------------------------------------
# main retarget
# ---------------------------------------------------------------------------

def retarget(cfg):
    data = np.load(cfg.npz, allow_pickle=True)
    pose_world = data["pose_world"][..., :3].astype(np.float64)
    pose_ok = data["pose_ok"]
    fps = float(data["fps"]) if "fps" in data else 30.0
    n_frames = pose_world.shape[0]

    print(f"landmarks .... {cfg.npz}")
    print(f"frames ....... {n_frames} @ {fps:g} fps")
    print(f"body detected  {pose_ok.mean() * 100:.1f}% of frames")

    pts = mp_to_object(pose_world)
    pts = smooth_series(pts, cfg.smooth)

    # sanity check the coordinate mapping against the data itself
    up = float((pts[:, NOSE, 1] - pts[:, L_HIP, 1]).mean())
    left = float((pts[:, L_SHOULDER, 0] - pts[:, R_SHOULDER, 0]).mean())
    print(f"\ncoordinate check:")
    print(f"  nose above hip (+Y)      {up:+.3f}  {'OK' if up > 0 else 'WRONG'}")
    print(f"  L shoulder left of R (+X){left:+.3f}  "
          f"{'OK' if left > 0 else 'WRONG'}")
    if up <= 0 or left <= 0:
        raise SystemExit("coordinate conversion is wrong -- aborting")

    arm = bpy.data.objects.get(ARMATURE)
    if arm is None:
        raise SystemExit(f"no object named {ARMATURE!r}")

    bpy.context.view_layer.objects.active = arm
    arm.animation_data_clear()
    bpy.ops.object.mode_set(mode="POSE")

    driven = []
    for name in BONE_ORDER:
        pb = arm.pose.bones.get(name)
        if pb is None:
            print(f"  ! missing bone {name}, skipping")
            continue
        pb.rotation_mode = "QUATERNION"
        driven.append(name)
    print(f"\ndriving {len(driven)} bones: {', '.join(driven)}")

    scene = bpy.context.scene
    scene.render.fps = int(round(fps))
    scene.frame_start = 1
    scene.frame_end = n_frames

    # reset to rest so frame 1 starts clean
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()

    for f in range(n_frames):
        scene.frame_set(f + 1)

        if not pose_ok[f]:
            # hold the previous pose rather than snapping to rest
            for name in driven:
                arm.pose.bones[name].keyframe_insert(
                    "rotation_quaternion", frame=f + 1)
            continue

        targets = frame_targets(pts[f], cfg)
        for name in driven:
            direction, weight = targets[name]
            aim_bone(arm.pose.bones[name], direction, weight)

        for name in driven:
            arm.pose.bones[name].keyframe_insert(
                "rotation_quaternion", frame=f + 1)

        if (f + 1) % 10 == 0:
            print(f"  keyed {f + 1}/{n_frames}", end="\r", flush=True)

    bpy.ops.object.mode_set(mode="OBJECT")
    print(" " * 40, end="\r")
    print(f"keyframed {n_frames} frames on {len(driven)} bones")

    if cfg.out:
        bpy.ops.wm.save_as_mainfile(filepath=cfg.out)
        print(f"saved: {cfg.out}")

    return arm, n_frames, fps


# ---------------------------------------------------------------------------
# preview render (Step 8 -- proves the motion actually transferred)
# ---------------------------------------------------------------------------

def setup_preview(arm, cfg):
    """Front-facing camera + key light framing the character."""
    scene = bpy.context.scene

    # Character faces world -Y (object +Z forward, rotated +90 deg about X).
    body = bpy.data.objects.get("CC_Base_Body")
    if body is not None:
        corners = [arm.matrix_world @ Vector(c)
                   for c in body.bound_box]
        zs = [c.z for c in corners]
        xs = [c.x for c in corners]
        top, bottom = max(zs), min(zs)
    else:
        top, bottom, xs = 1.7, 0.0, [-0.5, 0.5]

    height = max(top - bottom, 1e-3)
    # frame the upper body: that is where signing happens
    focus_z = bottom + height * 0.78
    span = max(height * 0.42, max(xs) - min(xs), 0.4)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)

    dist = span * 2.6
    cam.location = Vector((0.0, -dist, focus_z))
    cam.rotation_euler = (np.pi / 2, 0.0, 0.0)
    scene.camera = cam

    key = bpy.data.lights.new("Key", type="AREA")
    key.energy = 400.0
    key.size = 3.0
    key_obj = bpy.data.objects.new("Key", key)
    key_obj.location = Vector((-dist * 0.7, -dist * 0.8, focus_z + span))
    key_obj.rotation_euler = (np.pi / 3, 0.0, -np.pi / 5)
    scene.collection.objects.link(key_obj)

    fill = bpy.data.lights.new("Fill", type="AREA")
    fill.energy = 150.0
    fill.size = 4.0
    fill_obj = bpy.data.objects.new("Fill", fill)
    fill_obj.location = Vector((dist * 0.8, -dist * 0.6, focus_z))
    fill_obj.rotation_euler = (np.pi / 2.4, 0.0, np.pi / 4)
    scene.collection.objects.link(fill_obj)

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (
        0.05, 0.05, 0.06, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    scene.world = world

    scene.render.resolution_x = cfg.width
    scene.render.resolution_y = cfg.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = cfg.render_dir + "/frame_"

    engine = "BLENDER_EEVEE_NEXT"
    try:
        scene.render.engine = engine
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    print(f"render engine: {scene.render.engine}")
    if hasattr(scene, "eevee"):
        try:
            scene.eevee.taa_render_samples = 16
        except AttributeError:
            pass


def render_preview(cfg):
    print(f"\nrendering preview -> {cfg.render_dir}")
    bpy.ops.render.render(animation=True, write_still=False)
    print("render done")


# ---------------------------------------------------------------------------

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="retarget.py")
    ap.add_argument("--npz", required=True)
    ap.add_argument("--out", default=None, help="output .blend")
    ap.add_argument("--smooth", type=int, default=5,
                    help="moving-average window in frames (0 disables)")
    ap.add_argument("--spine-weight", type=float, default=0.45,
                    help="0 = rigid spine, 1 = follow landmarks fully")
    ap.add_argument("--head-weight", type=float, default=0.75)
    ap.add_argument("--hand-weight", type=float, default=0.85)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--render-dir", default="render_preview")
    ap.add_argument("--width", type=int, default=540)
    ap.add_argument("--height", type=int, default=720)
    return ap.parse_args(argv)


def main():
    cfg = parse_args()
    arm, n_frames, fps = retarget(cfg)
    if cfg.render:
        setup_preview(arm, cfg)
        render_preview(cfg)


if __name__ == "__main__":
    main()
