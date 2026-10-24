"""
Bake the captured arm motion onto Jake in Blender and keyframe it.

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python animate_avatar.py

Scope: clavicle -> upperarm -> forearm, both sides. That is what this
script always claimed to do. The full retargeter -- wrists, all five
digits, per-segment confidence, sanity gates -- lives in
jump_3d/index.html; this is the Blender path for rendering, not a second
implementation of it.

It previously failed four ways, all of them silent until runtime:

  1. `for frame_id, frame in enumerate(motion)` iterated the top-level
     dict's KEYS, so `frame` was the string "fps".
  2. `frame["pose"]["left_shoulder"]` indexed a 33-element LIST by name.
  3. `armature.pose.bones["LeftUpperArm"]` is not in this rig; the bones
     are named CC_Base_L_Upperarm.
  4. The path was relative to the working directory, so running it from
     anywhere but the project root raised FileNotFoundError.

It also aimed bones with `direction.to_track_quat()`, which ignores the
rest pose. Character Creator bones carry their own local axes, so a bone
must be rotated RELATIVE to where it already rests, and the source must
be expressed in the body's frame rather than the camera's.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

# --------------------------------------------------------------------
# resolved against THIS FILE, never the working directory
# --------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
MOTION_PATH = HERE / "jump_3d" / "motion.json"
MODEL_PATH = HERE / "jump_3d" / "jakke.glb"

for required in (MOTION_PATH, MODEL_PATH):
    if not required.exists():
        raise FileNotFoundError(
            f"Missing: {required}\n"
            f"Run jump_3d/extract_motion.py first, or point the path at your copy.")

with open(MOTION_PATH) as f:
    motion = json.load(f)

frames = motion["frames"]
fps = motion.get("fps", 30)
print(f"Loaded {len(frames)} frames @ {fps}fps from {MOTION_PATH}")

# --------------------------------------------------------------------
# MediaPipe pose landmark indices
# --------------------------------------------------------------------
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24

ARMS = {
    "left": dict(clavicle="CC_Base_L_Clavicle", upper="CC_Base_L_Upperarm",
                 fore="CC_Base_L_Forearm", hand="CC_Base_L_Hand",
                 shoulder=L_SHOULDER, elbow=L_ELBOW, wrist=L_WRIST),
    "right": dict(clavicle="CC_Base_R_Clavicle", upper="CC_Base_R_Upperarm",
                  fore="CC_Base_R_Forearm", hand="CC_Base_R_Hand",
                  shoulder=R_SHOULDER, elbow=R_ELBOW, wrist=R_WRIST),
}


def mp_vector(landmark):
    """MediaPipe (+y down, +z away) -> Blender-ish (+y up, +z toward camera)."""
    return Vector((landmark["x"], -landmark["y"], -landmark["z"]))


def ortho_basis(across, up):
    """Gram-Schmidt with `up` primary. Shoulder line and torso are not
    perpendicular on a real body, so orthogonality is never assumed.

    The guard is defensive, not a fix for anything observed here: on this
    clip the elbow plane never collapses onto the bone. But normalising a
    near-zero vector would silently yield a basis that is not orthonormal,
    and every rotation built from it would be garbage, so it is worth the
    three lines."""
    y = up.normalized()
    x = across - y * across.dot(y)
    if x.length < 1e-4:
        # any axis will do for roll; pick the one least aligned with y
        fallback = min((Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
                       key=lambda v: abs(v.dot(y)))
        x = fallback - y * fallback.dot(y)
    x.normalize()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()   # columns x, y, z


# --------------------------------------------------------------------
# scene
# --------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(MODEL_PATH))

armature = next(o for o in bpy.data.objects if o.type == "ARMATURE")
print(f"Armature: {armature.name} ({len(armature.pose.bones)} bones)")

missing = [n for arm in ARMS.values() for n in
           (arm["clavicle"], arm["upper"], arm["fore"], arm["hand"])
           if n not in armature.pose.bones]
if missing:
    raise KeyError(f"Bones not in this rig: {missing}")

for bone in armature.pose.bones:
    bone.rotation_mode = "QUATERNION"

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = len(frames)
scene.render.fps = int(round(fps))


def rest_direction(bone):
    """Bone's rest direction in armature space (Blender bones point +Y)."""
    return (bone.bone.matrix_local.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()


def set_orientation(bone, target_dir, reference):
    """Rotate `bone` so it points along target_dir, with roll pinned by
    `reference`, relative to its own rest orientation."""
    rest_basis = ortho_basis(reference, rest_direction(bone))
    target_basis = ortho_basis(reference, target_dir)
    rotation = target_basis @ rest_basis.inverted()
    new_3x3 = rotation @ bone.bone.matrix_local.to_3x3()
    bone.matrix = Matrix.Translation(bone.matrix.translation) @ new_3x3.to_4x4()
    bpy.context.view_layer.update()


keyed = 0
skipped = 0

for index, frame in enumerate(frames):
    pose = frame.get("pose_world") or frame.get("pose")
    if not pose or len(pose) < 25:
        skipped += 1
        continue

    scene.frame_set(index + 1)

    # ---- body frame: camera space is not body space -----------------
    ls, rs = mp_vector(pose[L_SHOULDER]), mp_vector(pose[R_SHOULDER])
    lh, rh = mp_vector(pose[L_HIP]), mp_vector(pose[R_HIP])
    source_basis = ortho_basis(ls - rs, (ls + rs) / 2 - (lh + rh) / 2)

    # ARMATURE space, not world space. pose_bone.matrix is interpreted in
    # armature space, and the glTF import leaves this armature rotated
    # +90 degrees about X -- mixing the two put every bone exactly 90
    # degrees out.
    jl = armature.pose.bones[ARMS["left"]["upper"]].head
    jr = armature.pose.bones[ARMS["right"]["upper"]].head
    jhip = armature.pose.bones["CC_Base_Hip"].head
    jchest = armature.pose.bones["CC_Base_Spine02"].head
    avatar_basis = ortho_basis(jl - jr, jchest - jhip)

    to_avatar = avatar_basis @ source_basis.inverted()

    shoulder_mid = (ls + rs) / 2

    for side, spec in ARMS.items():
        shoulder = to_avatar @ mp_vector(pose[spec["shoulder"]])
        elbow = to_avatar @ mp_vector(pose[spec["elbow"]])
        wrist = to_avatar @ mp_vector(pose[spec["wrist"]])

        upper_dir = elbow - shoulder
        fore_dir = wrist - elbow
        if upper_dir.length < 1e-6 or fore_dir.length < 1e-6:
            continue

        # The elbow plane pins the roll. to_track_quat() cannot: it gives
        # the shortest arc, leaving the twist about the bone arbitrary.
        plane = upper_dir.cross(fore_dir)
        if plane.length < 1e-6:
            plane = avatar_basis.col[2].copy()
        plane.normalize()

        clavicle_dir = (to_avatar @ (mp_vector(pose[spec["shoulder"]]) - shoulder_mid))

        chain = [
            (armature.pose.bones[spec["clavicle"]], clavicle_dir, avatar_basis.col[2]),
            (armature.pose.bones[spec["upper"]], upper_dir, plane),
            (armature.pose.bones[spec["fore"]], fore_dir, plane),
        ]
        for bone, direction, reference in chain:
            if direction.length < 1e-6:
                continue
            set_orientation(bone, direction.normalized(), reference)
            bone.keyframe_insert("rotation_quaternion", frame=index + 1)
            keyed += 1

print(f"\nDONE: keyed {keyed} bone rotations over {len(frames) - skipped} frames"
      f" ({skipped} frames had no pose)")

out = HERE / "jump_3d" / "jake_arms_baked.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print("Saved:", out)
