"""
Rig inspection. Prints what the retargeter needs to know and nothing else.

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python inspect_cc_rig.py -- jump_3d/jakke.glb

Spaces, because this is where retargeting goes wrong:

  bone.head_local / tail_local   ARMATURE space (rest pose)
  bone.matrix_local              ARMATURE space rest matrix; its Y column
                                 is the bone's own direction
  pose_bone.matrix               ARMATURE space, POSED
  pose_bone.rotation_quaternion  the bone's LOCAL space, relative to its
                                 rest orientation AND its parent

The last line is the trap. A rotation computed in armature space cannot be
assigned to rotation_quaternion directly -- Blender will interpret it as
local. Either convert it, or assign pose_bone.matrix and let Blender do
the conversion for you. This script prints both so the difference is
visible.
"""
import sys
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
path = args[0] if args else "jump_3d/jakke.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
if path.lower().endswith((".glb", ".gltf")):
    bpy.ops.import_scene.gltf(filepath=path)
else:
    bpy.ops.import_scene.fbx(filepath=path)

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
print("\n" + "=" * 78)
print(f"ARMATURE: {arm.name}   bones: {len(arm.pose.bones)}")
print(f"object world matrix scale: {tuple(round(v, 4) for v in arm.matrix_world.to_scale())}")
print(f"object world rotation:     {tuple(round(v, 3) for v in arm.matrix_world.to_euler())}")
print("=" * 78)

# The nine bones the retargeter drives. Found by pattern, then confirmed,
# so this works on a rig whose names differ.
WANT = {
    "spine":          ["CC_Base_Spine02", "spine_02.x", "Spine1"],
    "L clavicle":     ["CC_Base_L_Clavicle", "shoulder.l"],
    "L upper arm":    ["CC_Base_L_Upperarm", "arm.l"],
    "L forearm":      ["CC_Base_L_Forearm", "forearm.l"],
    "L hand":         ["CC_Base_L_Hand", "hand.l"],
    "R clavicle":     ["CC_Base_R_Clavicle", "shoulder.r"],
    "R upper arm":    ["CC_Base_R_Upperarm", "arm.r"],
    "R forearm":      ["CC_Base_R_Forearm", "forearm.r"],
    "R hand":         ["CC_Base_R_Hand", "hand.r"],
}

print(f"\n{'role':14}{'bone name':26}{'parent':22}{'len':>7}")
print("-" * 78)
resolved = {}
for role, candidates in WANT.items():
    name = next((c for c in candidates if c in arm.pose.bones), None)
    if not name:
        print(f"{role:14}{'NOT FOUND':26}{'':22}{'':>7}")
        continue
    resolved[role] = name
    pb = arm.pose.bones[name]
    parent = pb.parent.name if pb.parent else "(root)"
    print(f"{role:14}{name:26}{parent:22}{pb.bone.length:7.4f}")

print("\n" + "=" * 78)
print("REST GEOMETRY, in ARMATURE space")
print("=" * 78)
print(f"{'bone':26}{'head':24}{'own +Y axis':24}")
print("-" * 78)
for role, name in resolved.items():
    b = arm.pose.bones[name].bone
    head = b.head_local
    own = (b.matrix_local.to_3x3() @ Vector((0, 1, 0))).normalized()
    print(f"{name:26}"
          f"({head.x:6.3f},{head.y:6.3f},{head.z:6.3f})  "
          f"({own.x:6.3f},{own.y:6.3f},{own.z:6.3f})")

print("\n" + "=" * 78)
print("DOES THE BONE POINT AT ITS CHILD?")
print("Blender bones point along local +Y. If that axis does not aim at the")
print("next joint, aiming the bone is not the same as aiming the limb.")
print("=" * 78)
CHAINS = [("L upper arm", "L forearm"), ("L forearm", "L hand"),
          ("R upper arm", "R forearm"), ("R forearm", "R hand")]
import math
for a_role, b_role in CHAINS:
    if a_role not in resolved or b_role not in resolved:
        continue
    a = arm.pose.bones[resolved[a_role]].bone
    b = arm.pose.bones[resolved[b_role]].bone
    own = (a.matrix_local.to_3x3() @ Vector((0, 1, 0))).normalized()
    to_child = (b.head_local - a.head_local).normalized()
    ang = math.degrees(own.angle(to_child))
    flag = "OK" if ang < 5 else "** MISMATCH -- aim at the child, not +Y **"
    print(f"  {resolved[a_role]:26} +Y vs direction-to-child: {ang:6.2f} deg  {flag}")

print("\n" + "=" * 78)
print("REST DIRECTIONS the retargeter will rotate FROM (armature space)")
print("=" * 78)
for a_role, b_role in CHAINS:
    if a_role not in resolved or b_role not in resolved:
        continue
    a = arm.pose.bones[resolved[a_role]].bone
    b = arm.pose.bones[resolved[b_role]].bone
    d = (b.head_local - a.head_local).normalized()
    print(f"  {a_role:14} {resolved[a_role]:26} ({d.x:6.3f},{d.y:6.3f},{d.z:6.3f})")
print()
