import bpy, os, glob, math, collections, mathutils
OBJDIR=r"C:\AnatomyFactory\anatomy\bp3d\obj\isa_BP3D_4.0_obj_99"
MAP=r"C:\AnatomyFactory\anatomy\bp3d\isa_element_parts.txt"
OUTDIR=r"E:\AnatomyFactory\out\bp3d_arm"
os.makedirs(OUTDIR,exist_ok=True)

names_per_fj=collections.defaultdict(list)
with open(MAP,encoding="utf-8",errors="replace") as f:
    next(f)
    for line in f:
        p=[x.strip() for x in line.split("\t")]
        if len(p)>=3 and p[2]: names_per_fj[p[2]].append(p[1])

MUS=["biceps brachii","triceps brachii","deltoid","brachialis","coracobrachialis","pectoralis major","teres major","teres minor","infraspinatus","supraspinatus","subscapularis"]
BON=["humerus","radius","ulna","clavicle","scapula","capitate","hamate","metacarpal","carpal","phalanx"]
BAD=["left","artery","branch","nerve","vein","zone of","collateral","recurrent"]
def classify(nm):
    l=nm.lower()
    if any(b in l for b in BAD): return None
    if any(k in l for k in MUS): return "muscle"
    if any(k in l for k in BON): return "bone"
    return None

sel=[]
for fj,names in names_per_fj.items():
    path=os.path.join(OBJDIR,fj+".obj")
    if not os.path.exists(path): continue
    for nm in names:
        c=classify(nm)
        if c: sel.append((path,nm,c)); break
print("RS: selected parts:",len(sel))

bpy.ops.wm.read_factory_settings(use_empty=True)
def mat_bone():
    m=bpy.data.materials.new("Bone"); m.use_nodes=True; b=m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value=(0.86,0.82,0.74,1); b.inputs["Roughness"].default_value=0.55
    return m
def mat_musc():
    m=bpy.data.materials.new("Muscle"); m.use_nodes=True; b=m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value=(0.40,0.045,0.045,1); b.inputs["Roughness"].default_value=0.5
    if "Subsurface Weight" in b.inputs: b.inputs["Subsurface Weight"].default_value=0.06
    return m
BONE=mat_bone(); MUSC=mat_musc()
imported=[]
for path,nm,c in sel:
    before=set(bpy.data.objects)
    try: bpy.ops.wm.obj_import(filepath=path)
    except Exception as e: print("import err",nm,e); continue
    for o in [x for x in bpy.data.objects if x not in before]:
        o.name=nm; o["cls"]=c; o.scale=(0.001,0.001,0.001)  # mm -> m; anatomical vertical is world +Y (frame via camera)
        o.data.materials.clear(); o.data.materials.append(BONE if c=="bone" else MUSC)
        for pl in o.data.polygons: pl.use_smooth=True
        imported.append(o)
bpy.context.view_layer.update()

# keep ONE side (right): drop objects on the left half (x<0) for a clean single-arm shot
cx=[ (sum((o.matrix_world@mathutils.Vector(c) for c in o.bound_box), mathutils.Vector())/8).x for o in imported]
mid=sorted(cx)[len(cx)//2]
keep=[o for o,x in zip(imported,cx) if x>=mid]
for o in imported:
    if o not in keep: bpy.data.objects.remove(o,do_unlink=True)
imported=keep
bpy.context.view_layer.update()
print("RS: kept one side:",len(imported))

allc=[o.matrix_world@mathutils.Vector(c) for o in imported for c in o.bound_box]
xs=[c.x for c in allc]; ys=[c.y for c in allc]; zs=[c.z for c in allc]
center=mathutils.Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2))
ext=mathutils.Vector((max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)))
size=max(ext); print("RS: size",round(size,2),"ext",[round(v,2) for v in ext])

scene=bpy.context.scene
scene.render.engine='CYCLES'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'
try: prefs.get_devices()
except: pass
for d in prefs.devices: d.use=(d.type=='OPTIX')
scene.cycles.device='GPU'; scene.cycles.samples=64; scene.cycles.use_denoising=True
scene.render.resolution_x=1920; scene.render.resolution_y=1080  # extended arm suits 16:9
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='Standard'  # keep muscle red saturated (Filmic desaturates to pink)
w=bpy.data.worlds.new("W"); scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.02,0.02,0.025,1)

piv=bpy.data.objects.new("piv",None); scene.collection.objects.link(piv); piv.location=center
cam_d=bpy.data.cameras.new("C"); cam=bpy.data.objects.new("C",cam_d); scene.collection.objects.link(cam); scene.camera=cam
cam.parent=piv; cam_d.lens=50; cam_d.sensor_fit='AUTO'
# arm's long axis is world Y; frame it across a 16:9 landscape, tighter
hfov=2*math.atan(0.5*cam_d.sensor_width/cam_d.lens)
dist=(ext.y*0.5)/math.tan(hfov/2)*1.12+0.12
cam.location=(dist*0.28,0.0,dist*0.95)
con=cam.constraints.new('TRACK_TO'); con.target=piv; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'
for i,(loc,e) in enumerate([((size*0.9,size*0.9,size*0.9),300),((-size,size*0.4,size*0.7),110),((-size*0.3,size*0.6,-size),180)]):
    L=bpy.data.lights.new("L%d"%i,'AREA'); L.energy=e*(size+1); L.size=size*1.4
    lo=bpy.data.objects.new("L%d"%i,L); scene.collection.objects.link(lo)
    lo.location=(center.x+loc[0],center.y+loc[1],center.z+loc[2])
    c2=lo.constraints.new('TRACK_TO'); c2.target=piv; c2.track_axis='TRACK_NEGATIVE_Z'; c2.up_axis='UP_Y'

def render(path):
    scene.render.filepath=path; bpy.ops.render.render(write_still=True); print("RS: RENDERED",path)

render(os.path.join(OUTDIR,"arm_bones_muscles.png"))

# highlight pass: bright emissive on biceps, dim everything else
dim=bpy.data.materials.new("Dim"); dim.use_nodes=True
db=dim.node_tree.nodes["Principled BSDF"]; db.inputs["Base Color"].default_value=(0.55,0.55,0.60,1); db.inputs["Roughness"].default_value=0.6
db.inputs["Alpha"].default_value=0.12   # ghost the occluding muscles so the highlighted one shows through
dim.blend_method='BLEND'
hl=bpy.data.materials.new("HL"); hl.use_nodes=True
hb=hl.node_tree.nodes["Principled BSDF"]; hb.inputs["Base Color"].default_value=(0.9,0.1,0.1,1)
if "Emission Color" in hb.inputs: hb.inputs["Emission Color"].default_value=(1.0,0.15,0.05,1)
if "Emission Strength" in hb.inputs: hb.inputs["Emission Strength"].default_value=2.5
tgt=[o for o in imported if "biceps brachii" in o.name.lower()]
for o in imported:
    o.data.materials.clear(); o.data.materials.append(hl if o in tgt else dim)
print("RS: highlight target objs:",[o.name for o in tgt])
render(os.path.join(OUTDIR,"arm_highlight_biceps.png"))
print("RS: BP3D_ARM_DONE")
