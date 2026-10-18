import bpy, sys, importlib
def di(pkg,key):
    for m in sys.modules:
        if m.endswith(pkg): return getattr(importlib.import_module(m),key)
    raise ValueError(pkg)
HumanService=di("mpfb.services.humanservice","HumanService")
FaceService=di("mpfb.services.faceservice","FaceService")
try: print("FACEUNITS01_INSTALLED", FaceService.is_faceunits01_installed())
except Exception as e: print("is_installed_err", e)
try: print("ARKIT_UNIT_COUNT", len(FaceService.ARKIT_FACEUNITS))
except Exception as e: print("arkit_const_err", e)
h=HumanService.create_human()
try:
    FaceService.load_targets(h, load_arkit_faceunits=True); print("LOAD_TARGETS_OK")
    FaceService.clear_expression(h)
    FaceService.set_expression(h, {"mouthSmileLeft":0.9,"mouthSmileRight":0.9,"cheekSquintLeft":0.5,"cheekSquintRight":0.5,"jawOpen":0.2})
    print("SET_EXPRESSION_OK")
    sk=h.data.shape_keys; n=len(sk.key_blocks) if sk else 0; print("SHAPE_KEYS",n)
    if sk:
        ex=[kb.name for kb in sk.key_blocks if kb.name.startswith('!ex-')]
        print("EX_KEY_COUNT",len(ex),"sample",ex[:4])
        for kb in sk.key_blocks:
            if 'mouthSmileLeft' in kb.name: print("mouthSmileLeft_value",round(kb.value,3))
except Exception as e:
    import traceback; print("FACE_ERR",repr(e)); traceback.print_exc()
