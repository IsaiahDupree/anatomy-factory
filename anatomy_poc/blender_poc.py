# Headless Blender OptiX proof-of-concept for the "anatomy content factory" backbone.
# Builds a tiny scene: a "muscle" icosphere that contracts/bulges while its emission
# ramps dark->bright with a per-frame "activation" value (0..1). Film-transparent RGBA,
# vertical framing, Cycles OptiX on the RTX 4070 SUPER. Renders an animation range.
import bpy, sys, math

FRAMES = 24  # ~1s @ 24fps — enough to prove the anim->frames->ffmpeg loop
W, H = 720, 1280  # vertical; small for a fast proof
SAMPLES = 24

# ---- reset scene ----
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = FRAMES

# ---- engine + OptiX GPU ----
scene.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
try:
    prefs.get_devices()
except Exception:
    pass
optix = []
for d in prefs.devices:
    if d.type == 'OPTIX':
        d.use = True; optix.append(d.name)
    else:
        d.use = (d.type == 'OPTIX')
scene.cycles.device = 'GPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
print("POC_OPTIX_DEVICES:", optix)
print("POC_CYCLES_DEVICE:", scene.cycles.device)

# ---- transparent film (RGBA foreground pass) ----
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.resolution_x = W
scene.render.resolution_y = H
scene.render.resolution_percentage = 100

# ---- "muscle" mesh ----
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1.0, location=(0,0,0))
muscle = bpy.context.active_object
muscle.name = "Muscle_Zygomaticus"
mod = muscle.modifiers.new("subsurf", 'SUBSURF'); mod.levels = 1; mod.render_levels = 2
for p in muscle.data.polygons: p.use_smooth = True

# ---- activation-driven emission material (dark -> bright glow) ----
mat = bpy.data.materials.new("MuscleActivation"); mat.use_nodes = True
nt = mat.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial')
emis = nt.nodes.new('ShaderNodeEmission')
nt.links.new(emis.outputs['Emission'], out.inputs['Surface'])
muscle.data.materials.append(mat)

# ---- camera + key light ----
cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam); scene.camera = cam
cam.location = (0, -4.2, 0.4); cam.rotation_euler = (math.radians(84), 0, 0)
light_data = bpy.data.lights.new("Key", 'AREA'); light_data.energy = 600
light = bpy.data.objects.new("Key", light_data); scene.collection.objects.link(light)
light.location = (2.5, -3, 3)

# ---- animate contraction + activation per frame ----
import os
OUT = sys.argv[-1] if len(sys.argv) > 1 else "poc"
os.makedirs(OUT, exist_ok=True)
def emiss_color(a):
    # dark red -> bright orange-white as activation 0..1
    return (0.15 + 0.85*a, 0.02 + 0.55*a*a, 0.02 + 0.30*a*a*a, 1.0)

scene.render.filepath = ""  # set per-frame below
for f in range(1, FRAMES+1):
    scene.frame_set(f)
    a = math.sin((f-1)/(FRAMES-1) * math.pi)  # 0 ->1 ->0 : one contraction
    # bulge: scale up in X/Z, shorten Y a touch (muscle shortens+bulges)
    muscle.scale = (1.0 + 0.35*a, 1.0 - 0.18*a, 1.0 + 0.35*a)
    emis.inputs['Strength'].default_value = 0.3 + 6.0*a
    emis.inputs['Color'].default_value = emiss_color(a)
    scene.render.filepath = os.path.join(OUT, f"frame_{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"POC_RENDERED frame {f}/{FRAMES} activation={a:.2f}")
print("POC_DONE")
