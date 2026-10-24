"""
Blender rig inspection.

Prints every armature, every bone name and the full bone hierarchy so the
retargeting layer can be written against the rig that actually exists
instead of assumed Mixamo names.

Run headless:

    /Applications/Blender.app/Contents/MacOS/Blender Jake.blend \
        --background --python inspect_rig.py

Or point it at an FBX instead of a .blend:

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python inspect_rig.py -- --fbx Jake.fbx
"""

import sys

import bpy


# ---------------------------------------------------------------------------
# args after the "--" separator belong to us, not to Blender
# ---------------------------------------------------------------------------

def script_args():
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def maybe_import_fbx(args):
    if "--fbx" not in args:
        return
    path = args[args.index("--fbx") + 1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    print(f"importing FBX: {path}")
    bpy.ops.import_scene.fbx(filepath=path)


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def describe_scene():
    rule("SCENE OBJECTS")
    print(f"{'name':<34}{'type':<12}{'parent':<24}")
    print("-" * 78)
    for obj in bpy.data.objects:
        parent = obj.parent.name if obj.parent else "-"
        print(f"{obj.name:<34}{obj.type:<12}{parent:<24}")

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    print(f"\n{len(meshes)} mesh object(s)")
    for m in meshes:
        mods = [f"{mod.type}" for mod in m.modifiers]
        groups = len(m.vertex_groups)
        print(f"  {m.name:<30} verts={len(m.data.vertices):<7} "
              f"vgroups={groups:<5} modifiers={mods}")


def print_hierarchy(bone, depth=0, is_last=True, prefix=""):
    """Draw the bone tree with box-drawing connectors."""
    if depth == 0:
        connector = ""
        child_prefix = ""
    else:
        connector = "`-- " if is_last else "|-- "
        child_prefix = "    " if is_last else "|   "

    print(f"  {prefix}{connector}{bone.name}")

    children = list(bone.children)
    for i, child in enumerate(children):
        print_hierarchy(
            child,
            depth + 1,
            is_last=(i == len(children) - 1),
            prefix=prefix + child_prefix,
        )


def describe_armature(obj):
    arm = obj.data
    bones = arm.bones

    rule(f"ARMATURE: {obj.name}   (armature data: {arm.name})")
    print(f"object name .......... {obj.name}")
    print(f"armature data name ... {arm.name}")
    print(f"bone count ........... {len(bones)}")
    print(f"world location ....... "
          f"({obj.location.x:.4f}, {obj.location.y:.4f}, {obj.location.z:.4f})")
    print(f"scale ................ "
          f"({obj.scale.x:.4f}, {obj.scale.y:.4f}, {obj.scale.z:.4f})")
    print(f"rotation mode ........ {obj.rotation_mode}")

    roots = [b for b in bones if b.parent is None]
    print(f"root bone(s) ......... {[b.name for b in roots]}")

    # --- flat list, easy to copy/paste back to me ---
    rule(f"BONE NAMES ({len(bones)}) -- {obj.name}")
    for i, bone in enumerate(sorted(bones, key=lambda b: b.name)):
        print(f"  [{i:>3}] {bone.name}")

    # --- hierarchy ---
    rule(f"BONE HIERARCHY -- {obj.name}")
    for root in roots:
        print_hierarchy(root)

    # --- geometry, needed to build the retarget rest pose ---
    rule(f"BONE GEOMETRY -- {obj.name}")
    print(f"{'bone':<30}{'parent':<28}{'len':>8}  connected")
    print("-" * 78)
    for bone in bones:
        parent = bone.parent.name if bone.parent else "-"
        print(f"{bone.name:<30}{parent:<28}{bone.length:>8.4f}  "
              f"{'yes' if bone.use_connect else 'no'}")

    # --- pose bone constraints can silently fight the retargeter ---
    constrained = [
        (pb.name, [c.type for c in pb.constraints])
        for pb in obj.pose.bones if pb.constraints
    ]
    rule(f"POSE CONSTRAINTS -- {obj.name}")
    if constrained:
        for name, kinds in constrained:
            print(f"  {name:<30}{kinds}")
        print("\nNOTE: these will override keyframed rotations unless "
              "muted or accounted for.")
    else:
        print("  none")

    # --- what the fingers are called matters most for Auslan ---
    rule(f"LIKELY FINGER BONES -- {obj.name}")
    tokens = ("thumb", "index", "middle", "ring", "pinky", "little",
              "finger", "hand")
    hits = [b.name for b in bones
            if any(t in b.name.lower() for t in tokens)]
    if hits:
        for name in sorted(hits):
            print(f"  {name}")
        print(f"\n  {len(hits)} candidate finger/hand bone(s)")
    else:
        print("  NONE FOUND -- this rig may not have finger bones.")
        print("  Auslan handshapes cannot be reproduced without them.")


def main():
    args = script_args()
    maybe_import_fbx(args)

    print(f"\nBlender {bpy.app.version_string}")
    blend = bpy.data.filepath or "(none - imported or empty scene)"
    print(f"file: {blend}")

    describe_scene()

    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not armatures:
        rule("NO ARMATURE FOUND")
        print("This file has no armature object, so there is nothing to")
        print("retarget onto. Check that the rig imported correctly.")
        return

    for obj in armatures:
        describe_armature(obj)

    rule("SUMMARY")
    for obj in armatures:
        print(f"  armature {obj.name!r}: {len(obj.data.bones)} bones")
    print("\nPaste the BONE NAMES and BONE HIERARCHY sections back to me.")


if __name__ == "__main__":
    main()
