import sys, importlib, inspect
def di(pkg,key):
    for m in sys.modules:
        if m.endswith(pkg): return getattr(importlib.import_module(m),key)
    raise ValueError(pkg)
AssetService=di("mpfb.services.assetservice","AssetService")
zip_path=r"C:\AnatomyFactory\downloads\faceunits01.zip"
try: print("SIG_fix", str(inspect.signature(AssetService.fix_and_extract_asset_pack_zip)))
except Exception as e: print("sig_err",e)
try: print("CHECK", AssetService.check_asset_pack_zip(zip_path))
except Exception as e: print("check_err",repr(e))
try:
    res=AssetService.fix_and_extract_asset_pack_zip(zip_path); print("EXTRACT_RESULT", res)
except Exception as e:
    import traceback; print("EXTRACT_ERR",repr(e)); traceback.print_exc()
for m in ("rescan_pack_metadata","invalidate_pack_metadata_cache"):
    fn=getattr(AssetService,m,None)
    if fn:
        try: fn()
        except Exception as e: print(m,"err",e)
FaceService=di("mpfb.services.faceservice","FaceService")
print("FACEUNITS01_INSTALLED", FaceService.is_faceunits01_installed(force_recheck=True))
HumanService=di("mpfb.services.humanservice","HumanService")
h=HumanService.create_human()
FaceService.load_targets(h, load_arkit_faceunits=True)
FaceService.clear_expression(h)
FaceService.set_expression(h, {"mouthSmileLeft":0.9,"mouthSmileRight":0.9,"cheekSquintLeft":0.55,"cheekSquintRight":0.55,"jawOpen":0.15})
sk=h.data.shape_keys
ex=[kb for kb in sk.key_blocks if kb.name.startswith('!ex-')] if sk else []
print("EX_KEY_COUNT", len(ex))
nz=[(kb.name,round(kb.value,3)) for kb in ex if kb.value>0.001]
print("NONZERO_EX", nz[:8])
print("INSTALL_DONE")
