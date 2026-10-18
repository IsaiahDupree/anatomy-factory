import sys, importlib
def di(pkg,key):
    for m in sys.modules:
        if m.endswith(pkg): return getattr(importlib.import_module(m),key)
    return None
LocationService=di("mpfb.services.locationservice","LocationService")
AssetService=di("mpfb.services.assetservice","AssetService")
print("LOC_METHODS", [m for m in dir(LocationService) if any(k in m.lower() for k in ('data','root','user','path')) and not m.startswith('__')])
for meth in ("get_user_data","get_mpfb_data","get_mh_user_data","get_user_config"):
    fn=getattr(LocationService,meth,None)
    if fn:
        try: print(meth,"=",fn())
        except Exception as e: print(meth,"err",e)
if AssetService:
    try: print("ROOTS_expressions", AssetService.get_asset_roots("expressions"))
    except Exception as e: print("roots_err",e)
    print("ASSET_INSTALL_METHODS",[m for m in dir(AssetService) if 'install' in m.lower() or 'pack' in m.lower()])
