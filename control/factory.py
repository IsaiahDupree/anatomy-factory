#!/usr/bin/env python3
"""factory.py — orion Anatomy Content Factory orchestrator.

One command turns a JSON job into finished vertical/square/horizontal clips:
    py factory.py job.json

Pipeline:  job.json -> Blender 4.4 (OptiX) render_scene.py -> per-pass PNG frames
           -> FFmpeg -> per-pass MP4 (primary format) + derived aspect ratios
           -> outputs_manifest.json

No stubs: every step shells a real tool already verified on orion.
"""
import json, os, subprocess, sys, time

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
RENDER_SCENE = r"C:\AnatomyFactory\blender\render_scene.py"
FFMPEG = "ffmpeg"

# derived aspect-ratio recipes (ffmpeg -vf) applied to the primary render
DERIVE = {
    "square":    "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080",
    "horizontal":"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0b0b0f",
    "vertical":  "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x0b0b0f",
}

def run(cmd, **kw):
    print("::", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, **kw)

def blender_render(job_path):
    r = run([BLENDER, "--background", "--python", RENDER_SCENE, "--", job_path])
    if r.returncode != 0:
        print("BLENDER_FAILED rc=", r.returncode); sys.exit(3)

def encode_pass(pass_dir, pattern, fps, out_mp4, vf=None, transparent=False):
    src = os.path.join(pass_dir, pattern)
    cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i", src]
    filt = "format=yuva420p," + (vf + ",") if vf else ""
    filt += "format=yuv420p"
    cmd += ["-vf", filt, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", out_mp4]
    return run(cmd, capture_output=True, text=True).returncode == 0

def encode_prores_transparent(pass_dir, pattern, fps, out_mov):
    # true-alpha master for the transparent pass (ProRes 4444)
    src = os.path.join(pass_dir, pattern)
    cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i", src,
           "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", out_mov]
    return run(cmd, capture_output=True, text=True).returncode == 0

def main():
    if len(sys.argv) < 2:
        print("usage: factory.py <job.json>"); sys.exit(2)
    job_path = os.path.abspath(sys.argv[1])
    with open(job_path) as f: job = json.load(f)
    name = job.get("name", "job")
    formats = job.get("deliver_formats", [job.get("format", "vertical")])
    t0 = time.time()

    print(f"=== [1/3] Blender render :: {name} ===")
    blender_render(job_path)

    out_root = job.get("out_dir") or (r"E:\AnatomyFactory\out" + "\\" + name)
    with open(os.path.join(out_root, "render_manifest.json")) as f: man = json.load(f)
    fps = man["fps"]

    print(f"=== [2/3] FFmpeg assembly ({len(man['passes'])} passes x {len(formats)} formats) ===")
    outputs = []
    clips_dir = os.path.join(out_root, "clips"); os.makedirs(clips_dir, exist_ok=True)
    for pname, p in man["passes"].items():
        for fmt in formats:
            vf = DERIVE.get(fmt)
            out_mp4 = os.path.join(clips_dir, f"{name}_{pname}_{fmt}.mp4")
            ok = encode_pass(p["dir"], p["pattern"], fps, out_mp4, vf=vf)
            if ok and os.path.exists(out_mp4):
                outputs.append(out_mp4); print("  OK", os.path.basename(out_mp4), os.path.getsize(out_mp4), "bytes")
        if pname == "transparent":
            out_mov = os.path.join(clips_dir, f"{name}_transparent_alpha.mov")
            if encode_prores_transparent(p["dir"], p["pattern"], fps, out_mov) and os.path.exists(out_mov):
                outputs.append(out_mov); print("  OK", os.path.basename(out_mov), os.path.getsize(out_mov), "bytes (alpha master)")

    manifest = {"name": name, "elapsed_s": round(time.time() - t0, 1),
                "render_manifest": man, "clips": outputs}
    with open(os.path.join(out_root, "outputs_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"=== [3/3] DONE :: {len(outputs)} clips in {manifest['elapsed_s']}s ===")
    for o in outputs: print("  ", o)
    print("FACTORY_DONE")

if __name__ == "__main__":
    main()
