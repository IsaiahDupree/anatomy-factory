# render_scene.py — JSON-driven anatomical scene builder + multi-pass renderer.
# Runs INSIDE Blender 4.4 headless:
#   blender --background --python render_scene.py -- <job.json>
# Produces per-pass PNG frame sequences under the job out dir + a render_manifest.json
# that factory.py consumes for FFmpeg assembly.
import bpy, sys, json, math, os, importlib
import mathutils

# ---------- helpers ----------
def get_args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []

def dynamic_import(pkg, key):
    for amod in sys.modules:
        if amod.endswith(pkg):
            return getattr(importlib.import_module(amod), key)
    raise ValueError("module not found: " + pkg)

def log(*a): print("RS:", *a, flush=True)

FORMATS = {"vertical": (1080, 1920), "horizontal": (1920, 1080), "square": (1080, 1080)}

def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def enable_optix(scene, samples):
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    try: prefs.get_devices()
    except Exception: pass
    devs = [d for d in prefs.devices if d.type == 'OPTIX']
    for d in prefs.devices: d.use = (d.type == 'OPTIX')
    scene.cycles.device = 'GPU' if devs else 'CPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True   # PROD: keep BVH/geo on device between frames
    log("render device:", scene.cycles.device, "optix:", [d.name for d in devs], "persistent_data=on")

def set_world(scene, rgb=(0.02, 0.02, 0.025)):
    world = bpy.data.worlds.new("W"); scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg: bg.inputs[0].default_value = (*rgb, 1.0); bg.inputs[1].default_value = 1.0

def activation_curve(action, f, f0, f1):
    t = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
    kind = action.get("type", "pulse")
    if kind == "pulse":  return math.sin(t * math.pi)
    if kind == "ramp":   return t
    if kind == "hold":   return float(action.get("value", 1.0))
    if kind == "array":
        vals = action.get("values", [0, 1, 0]); idx = t * (len(vals) - 1)
        lo = int(math.floor(idx)); hi = min(lo + 1, len(vals) - 1); frac = idx - lo
        return vals[lo] * (1 - frac) + vals[hi] * frac
    return math.sin(t * math.pi)

# ---------- subjects ----------
def make_primitive_muscle(scene):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1.0, location=(0, 0, 1.0))
    ob = bpy.context.active_object; ob.name = "Muscle"
    m = ob.modifiers.new("subsurf", 'SUBSURF'); m.levels = 1; m.render_levels = 2
    for p in ob.data.polygons: p.use_smooth = True
    mat = bpy.data.materials.new("MuscleMat"); mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); emis = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(emis.outputs['Emission'], out.inputs['Surface'])
    ob.data.materials.append(mat); ob["is_active_muscle"] = True
    return ob, {"emission": emis}

def make_mpfb_human(scene, macros, face=False):
    HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
    ob = HumanService.create_human()
    try:
        TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")
        HOP = dynamic_import("mpfb.entities.objectproperties", "HumanObjectProperties")
        for k, v in (macros or {}).items():
            HOP.set_value(k, float(v), entity_reference=ob)
        TargetService.reapply_macro_details(ob)
        log("mpfb macros applied:", macros)
    except Exception as e:
        log("mpfb macro apply skipped:", e)
    mat = bpy.data.materials.new("SkinMat"); mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.82, 0.60, 0.51, 1.0)
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value = 0.5
        if "Subsurface Weight" in bsdf.inputs: bsdf.inputs["Subsurface Weight"].default_value = 0.15
    ob.data.materials.clear(); ob.data.materials.append(mat)
    handles = {"principled": bsdf}
    if face:
        FaceService = dynamic_import("mpfb.services.faceservice", "FaceService")
        FaceService.load_targets(ob, load_arkit_faceunits=True)
        handles["faceservice"] = FaceService
        log("arkit face units loaded; installed=", FaceService.is_faceunits01_installed())
    return ob, handles

# ---------- facial animation (bake once, shared by all passes) ----------
def bake_expression(subject, handles, action, f0, f1):
    FaceService = handles.get("faceservice")
    if not FaceService: return
    sk_names = None
    if action.get("type") == "capture":
        cap = json.load(open(action["path"])); frames = cap["frames"]; n = len(frames)
        env = action.get("envelope")  # optional: fade a single-frame capture in/out
        seq = []
        for i in range(f0, f1 + 1):
            t = 0.0 if f1 == f0 else (i - f0) / (f1 - f0)
            src = frames[min(int(round(t * (n - 1))), n - 1)]
            e = activation_curve({"type": env}, i, f0, f1) if env else 1.0
            seq.append({k: float(v) * e for k, v in src.get("arkit", {}).items()})
    else:
        base = action.get("expression", {"mouthSmileLeft": 0.9, "mouthSmileRight": 0.9})
        env = {"type": action.get("envelope", "pulse"), "value": action.get("value", 1.0), "values": action.get("values")}
        seq = [{k: float(v) * activation_curve(env, i, f0, f1) for k, v in base.items()} for i in range(f0, f1 + 1)]
    for idx, i in enumerate(range(f0, f1 + 1)):
        FaceService.clear_expression(subject)
        FaceService.set_expression(subject, seq[idx])
        sk = subject.data.shape_keys
        if sk:
            for kb in sk.key_blocks:
                if kb.name.startswith('!ex-'): kb.keyframe_insert('value', frame=i)
    log("baked facial expression over", f0, "-", f1)

# ---------- camera library ----------
def bbox_world(ob):
    cs = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    return center, size, (min(zs), max(zs))

def setup_camera(scene, subject, cam_kind, f0, f1):
    center, size, (zmin, zmax) = bbox_world(subject)
    pivot = bpy.data.objects.new("Pivot", None); scene.collection.objects.link(pivot)
    cam_data = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam); scene.camera = cam; cam.parent = pivot
    dist = size * 2.2 + 1.0
    head_z = zmax - (zmax - zmin) * 0.07   # ~eye level for a standing human
    if cam_kind in ("FACE_CLOSEUP", "MACRO_MOUTH"):
        aim_z = zmin + (zmax - zmin) * 0.86   # eyes/nose of a standing human
        pivot.location = mathutils.Vector((center.x, center.y, aim_z))
        cam.location = (0, -(size * 0.30 + 0.28), 0); cam_data.lens = 70
        cam_data.sensor_fit = 'VERTICAL'
    elif cam_kind == "TORSO_CLOSEUP":
        pivot.location = mathutils.Vector((center.x, center.y, zmax - (zmax - zmin) * 0.28))
        cam.location = (0, -dist * 0.7, 0); cam_data.lens = 60
    else:  # FULL_BODY / STATIC / ORBIT
        pivot.location = center; cam.location = (0, -dist, 0); cam_data.lens = 50
    cam.rotation_euler = (math.radians(90), 0, 0)
    con = cam.constraints.new('TRACK_TO'); con.target = pivot
    con.track_axis = 'TRACK_NEGATIVE_Z'; con.up_axis = 'UP_Y'
    if cam_kind in ("ORBIT", "ORBIT_HEAD", "ORBIT_BODY"):
        pivot.rotation_euler = (0, 0, 0); pivot.keyframe_insert("rotation_euler", frame=f0)
        pivot.rotation_euler = (0, 0, math.radians(360)); pivot.keyframe_insert("rotation_euler", frame=f1)
        if pivot.animation_data and pivot.animation_data.action:
            for fc in pivot.animation_data.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    return cam

def add_lighting(scene, subject, portrait=False):
    center, size, (zmin, zmax) = bbox_world(subject)
    key = bpy.data.lights.new("Key", 'AREA'); key.energy = (180 if portrait else 500) * (size + 1)
    key.size = size * 1.5 + 0.5
    ko = bpy.data.objects.new("Key", key); scene.collection.objects.link(ko)
    ko.location = (size * 1.2, -size * 1.6, zmax + size * 0.2)
    ko.rotation_euler = (math.radians(62), 0, math.radians(28))
    fill = bpy.data.lights.new("Fill", 'AREA'); fill.energy = (70 if portrait else 150) * (size + 1)
    fill.size = size * 3
    fo = bpy.data.objects.new("Fill", fill); scene.collection.objects.link(fo)
    fo.location = (-size * 2.2, -size * 1.3, zmax * 0.6)
    rim = bpy.data.lights.new("Rim", 'AREA'); rim.energy = (120 if portrait else 260) * (size + 1)
    ro = bpy.data.objects.new("Rim", rim); scene.collection.objects.link(ro)
    ro.location = (-size * 0.6, size * 1.6, zmax + size * 0.3); ro.rotation_euler = (math.radians(-60), 0, math.radians(200))

def heat_color(a):
    return (0.10 + 0.90 * a, 0.015 + 0.42 * a * a, 0.01 + 0.20 * a ** 3, 1.0)

# ---------- passes ----------
def render_pass(scene, subject, handles, pass_name, action, f0, f1, out_dir, transparent_bg):
    os.makedirs(out_dir, exist_ok=True)
    scene.render.film_transparent = transparent_bg or (pass_name == "transparent")
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    emis = handles.get("emission"); bsdf = handles.get("principled")
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        a = activation_curve(action, f, f0, f1)
        if pass_name == "activation":
            if emis is not None:
                emis.inputs['Strength'].default_value = 0.4 + 2.3 * a   # PROD: no white blowout
                emis.inputs['Color'].default_value = heat_color(a)
                emis.inputs['Strength'].keyframe_insert('default_value', frame=f)
                emis.inputs['Color'].keyframe_insert('default_value', frame=f)
            elif bsdf is not None and "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = heat_color(a)
                if "Emission Strength" in bsdf.inputs:
                    bsdf.inputs["Emission Strength"].default_value = 2.0 * a
                    bsdf.inputs["Emission Strength"].keyframe_insert('default_value', frame=f)
                bsdf.inputs["Emission Color"].keyframe_insert('default_value', frame=f)
        if subject.get("is_active_muscle") and subject.name == "Muscle":
            s = 1.0 + 0.25 * a
            subject.scale = (s, 1.0 - 0.12 * a, s); subject.keyframe_insert("scale", frame=f)
    scene.render.filepath = os.path.join(out_dir, "frame_")
    log(f"rendering pass '{pass_name}' frames {f0}-{f1} -> {out_dir}")
    bpy.ops.render.render(animation=True)

# ---------- main ----------
def main():
    args = get_args()
    if not args: log("ERROR: no job json path"); sys.exit(2)
    with open(args[0]) as f: job = json.load(f)
    log("job:", job.get("name"))
    fmt = job.get("format", "vertical"); scale = float(job.get("scale_pct", 100)) / 100.0
    W, H = FORMATS.get(fmt, FORMATS["vertical"]); fps = int(job.get("fps", 24))
    dur = float(job.get("duration_s", 1.5)); nframes = max(2, int(round(dur * fps)))
    f0, f1 = 1, nframes; samples = int(job.get("samples", 24))
    passes = job.get("passes", ["activation", "transparent"])
    out_root = job.get("out_dir") or ("E:\\AnatomyFactory\\out\\" + job.get("name", "job"))

    clean_scene(); scene = bpy.context.scene
    scene.frame_start = f0; scene.frame_end = f1
    scene.render.resolution_x = int(W * scale); scene.render.resolution_y = int(H * scale)
    scene.render.resolution_percentage = 100; scene.render.fps = fps
    enable_optix(scene, samples); set_world(scene)

    subj = job.get("subject", {"type": "primitive_muscle"})
    action = job.get("action", {"type": "pulse"})
    is_face = subj.get("type") == "mpfb_human" and subj.get("face")
    if subj.get("type") == "mpfb_human":
        subject, handles = make_mpfb_human(scene, subj.get("macros"), face=bool(subj.get("face")))
    else:
        subject, handles = make_primitive_muscle(scene)
    add_lighting(scene, subject, portrait=(job.get("camera") in ("FACE_CLOSEUP", "MACRO_MOUTH")))
    setup_camera(scene, subject, job.get("camera", "ORBIT"), f0, f1)
    if is_face:
        bake_expression(subject, handles, action, f0, f1)

    manifest = {"name": job.get("name", "job"), "fps": fps, "frames": nframes,
                "resolution": [scene.render.resolution_x, scene.render.resolution_y],
                "format": fmt, "out_dir": out_root, "passes": {}}
    for p in passes:
        pdir = os.path.join(out_root, p)
        render_pass(scene, subject, handles, p, action, f0, f1, pdir, transparent_bg=(p == "transparent"))
        manifest["passes"][p] = {"dir": pdir, "pattern": "frame_%04d.png", "frames": nframes}

    os.makedirs(out_root, exist_ok=True)
    with open(os.path.join(out_root, "render_manifest.json"), "w") as f: json.dump(manifest, f, indent=2)
    log("RENDER_SCENE_DONE")

main()
