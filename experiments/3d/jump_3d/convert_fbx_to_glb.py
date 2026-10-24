import bpy, sys, os
args = sys.argv[sys.argv.index("--") + 1:]
src, dst = args[0], args[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
for img in bpy.data.images:
    if img.size[0] > 1024 or img.size[1] > 1024:
        img.scale(min(img.size[0],1024), min(img.size[1],1024))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=dst, export_format='GLB', export_yup=True,
    export_skins=True, export_animations=False, export_morph=True,
    export_image_format='JPEG', export_jpeg_quality=85,
)
print("EXPORTED:", os.path.getsize(dst))
