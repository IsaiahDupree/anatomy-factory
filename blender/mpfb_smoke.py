# Headless MPFB controllability + render smoke test on orion.
import bpy, sys, math, importlib

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            m = importlib.import_module(amod)
            return getattr(m, key)
    raise ValueError("module not found: " + absolute_package_str)

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
try:
    TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")
    HumanObjectProperties = dynamic_import("mpfb.entities.objectproperties", "HumanObjectProperties")
except Exception as e:
    TargetService = None; HumanObjectProperties = None
    print("MPFB_MACRO_API_UNAVAILABLE:", e)

print("MPFB_IMPORT_OK")
human = HumanService.create_human()
print("MPFB_HUMAN_CREATED name=", human.name, "verts=", len(human.data.vertices))

# push a muscular macro (best-effort; body macros: gender/age/muscle/weight/height/...)
if HumanObjectProperties and TargetService:
    try:
        HumanObjectProperties.set_value("muscle", 0.9, entity_reference=human)
        HumanObjectProperties.set_value("weight", 0.35, entity_reference=human)
        TargetService.reapply_macro_details(human)
        print("MPFB_MACRO_APPLIED muscle=0.9 weight=0.35")
    except Exception as e:
        print("MPFB_MACRO_SKIPPED:", e)

# frame + render on OptiX
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
try: prefs.get_devices()
except Exception: pass
for d in prefs.devices: d.use = (d.type == 'OPTIX')
scene.cycles.device = 'GPU'; scene.cycles.samples = 16; scene.cycles.use_denoising = True
scene.render.resolution_x = 720; scene.render.resolution_y = 1280
scene.render.image_settings.file_format = 'PNG'

# bounding box center/height for framing
import mathutils
coords = [human.matrix_world @ mathutils.Vector(c) for c in human.bound_box]
zs = [c.z for c in coords]; cz = (min(zs)+max(zs))/2.0; top = max(zs)
cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam); scene.camera = cam
cam.location = (0, -3.6, cz); cam.rotation_euler = (math.radians(90),0,0)
cam_data.lens = 50
light = bpy.data.lights.new("Key",'AREA'); light.energy=1200; light.size=3
lo = bpy.data.objects.new("Key",light); scene.collection.objects.link(lo)
lo.location=(2.5,-3,top+0.5); lo.rotation_euler=(math.radians(60),0,math.radians(35))
scene.render.filepath = "E:\\AnatomyFactory\\out\\mpfb_smoke.png"
bpy.ops.render.render(write_still=True)
print("MPFB_RENDER_DONE ->", scene.render.filepath)
