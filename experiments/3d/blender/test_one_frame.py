"""
TEST 1: one MediaPipe frame drives ONE bone -- the left upper arm.

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python test_one_frame.py -- 26

Success = the printed angle error is near zero, and the debug line drawn
from the shoulder lies along the upper arm.

THE SPACE PROBLEM, stated once:

  rest.rotation_difference(target) is only valid if BOTH vectors are in
  the SAME space. This armature object carries a 90 degree X rotation and
  a 0.01 scale, so a direction in world space and a direction in armature
  space differ by exactly that -- and the resulting arm is 90 degrees
  wrong while every intermediate number looks plausible.

  Everything below works in ARMATURE space. mediapipe_to_blender() takes
  MediaPipe to Blender WORLD; world_to_armature_direction() takes it the
  last step. No axis is flipped anywhere else.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
MODEL = HERE / "jump_3d" / "jakke.glb"
MOTION = HERE / "jump_3d" / "motion.json"

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FRAME = int(args[0]) if args else 26

for required in (MODEL, MOTION):
    if not required.exists():
        raise FileNotFoundError(required)

# MediaPipe pose landmark indices
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24

BONE = "CC_Base_L_Upperarm"
CHILD = "CC_Base_L_Forearm"


# ---------------------------------------------------------------------
# THE one coordinate conversion. Nothing else touches an axis.
# ---------------------------------------------------------------------
def mediapipe_to_blender(x, y, z):
    """MediaPipe -> Blender WORLD.

    MediaPipe: +x right across the image, +y DOWN the image, +z away from
    the camera. This scene's world: +x right, +y up, +z toward the
    viewer. So y and z flip and x passes straight through.
    """
    return Vector((x, -y, -z))


def world_to_armature_direction(arm, v):
    """Blender WORLD -> ARMATURE space, direction only (no translation)."""
    return (arm.matrix_world.inverted().to_3x3() @ v).normalized()


# ---------------------------------------------------------------------
# helpers, named as asked
# ---------------------------------------------------------------------
def get_rest_direction(arm, bone_name, child_name):
    """Rest direction in ARMATURE space: where the bone points at rest.

    Taken as the offset to the child rather than the bone's own +Y, so it
    stays correct on rigs whose bone axes do not aim at the next joint.
    """
    a = arm.pose.bones[bone_name].bone.head_local
    b = arm.pose.bones[child_name].bone.head_local
    return (b - a).normalized()


def direction_to_quaternion(rest_dir, target_dir):
    """Shortest rotation carrying rest_dir onto target_dir. BOTH must
    already be in the same space -- this function cannot check that."""
    return rest_dir.rotation_difference(target_dir)


def apply_bone_rotation(arm, pose_bone, q_armature):
    """Apply an ARMATURE-space rotation to a pose bone.

    pose_bone.rotation_quaternion is in the bone's LOCAL space, so
    assigning an armature-space quaternion to it is the classic bug.
    Instead the bone's armature-space matrix is rebuilt and assigned;
    Blender converts to local, accounting for the parent.
    """
    rest3 = pose_bone.bone.matrix_local.to_3x3()
    new3 = q_armature.to_matrix() @ rest3
    pose_bone.matrix = Matrix.Translation(pose_bone.matrix.translation) @ new3.to_4x4()
    bpy.context.view_layer.update()


def angle_between(a, b):
    return math.degrees(a.normalized().angle(b.normalized()))


# ---------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(MODEL))
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for pb in arm.pose.bones:
    pb.rotation_mode = "QUATERNION"

frames = json.load(open(MOTION))["frames"]
frame = frames[FRAME]
pose = frame.get("pose_world") or frame["pose"]
print(f"\nframe {FRAME} of {len(frames)}   landmarks: {'pose_world' if frame.get('pose_world') else 'pose'}")

# ---- body-relative normalisation --------------------------------------
P = {i: mediapipe_to_blender(pose[i]["x"], pose[i]["y"], pose[i]["z"])
     for i in (L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP)}

hip_center = (P[L_HIP] + P[R_HIP]) / 2
shoulder_center = (P[L_SHOULDER] + P[R_SHOULDER]) / 2
shoulder_width = (P[L_SHOULDER] - P[R_SHOULDER]).length
torso = (shoulder_center - hip_center).length

print(f"hip centre      {tuple(round(v,3) for v in hip_center)}")
print(f"shoulder centre {tuple(round(v,3) for v in shoulder_center)}")
print(f"shoulder width  {shoulder_width:.4f}   torso {torso:.4f}")

# ---- the target -------------------------------------------------------
target_world = (P[L_ELBOW] - P[L_SHOULDER]).normalized()
target_arm = world_to_armature_direction(arm, target_world)

rest_arm = get_rest_direction(arm, BONE, CHILD)

print(f"\ntarget  (world)    {tuple(round(v,3) for v in target_world)}")
print(f"target  (armature) {tuple(round(v,3) for v in target_arm)}")
print(f"rest    (armature) {tuple(round(v,3) for v in rest_arm)}")
print(f"rest -> target is a {angle_between(rest_arm, target_arm):.1f} deg rotation")

q = direction_to_quaternion(rest_arm, target_arm)
apply_bone_rotation(arm, arm.pose.bones[BONE], q)

# ---- did it work? -----------------------------------------------------
a = arm.pose.bones[BONE].head
b = arm.pose.bones[CHILD].head
result = (b - a).normalized()
error = angle_between(result, target_arm)

print(f"\nresulting bone dir {tuple(round(v,3) for v in result)}")
print(f"ANGLE ERROR        {error:.4f} deg")
print("RESULT:", "PASS" if error < 1.0 else "FAIL")

# ---- debug line: target direction drawn from the shoulder -------------
length = arm.pose.bones[BONE].bone.length
mesh = bpy.data.meshes.new("debug_target")
mesh.from_pydata([a, a + target_arm * length], [(0, 1)], [])
obj = bpy.data.objects.new("DEBUG_target_L_upperarm", mesh)
bpy.context.collection.objects.link(obj)
obj.parent = arm
print(f"\ndrew DEBUG_target_L_upperarm from the shoulder along the target")

out = HERE / "jump_3d" / "test_one_frame.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print("saved:", out)
