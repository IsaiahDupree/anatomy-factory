#!/usr/bin/env python3
"""capture_to_arkit.py — MediaPipe capture front-end for the anatomy factory.

Image or video  ->  per-frame { 52 ARKit blendshape coeffs, head pose matrix, 33 body pose }  ->  JSON.
The ARKit coefficient NAMES (mouthSmileLeft, jawOpen, browDownLeft, ...) match MPFB's face-unit
shape-key names, so the JSON drives an MPFB rig directly.

Usage:  python capture_to_arkit.py <input.(jpg|png|mp4|mov)> <output.json>
Run in the mediapipe venv:  C:\\AnatomyFactory\\venvs\\mediapipe\\Scripts\\python.exe
"""
import sys, os, json
import cv2, mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

M = r"C:\AnatomyFactory\models"
FACE = os.path.join(M, "face_landmarker.task")
POSE = os.path.join(M, "pose_landmarker_full.task")
VIDEO_EXT = (".mp4", ".mov", ".avi", ".mkv", ".webm")

def pack(idx, t, fres, pres):
    bs = {}
    if fres.face_blendshapes:
        for c in fres.face_blendshapes[0]:
            bs[c.category_name] = round(c.score, 4)
    mtx = None
    if fres.facial_transformation_matrixes:
        mtx = [[round(float(v), 5) for v in row] for row in fres.facial_transformation_matrixes[0]]
    pose = []
    if pres.pose_landmarks:
        for lm in pres.pose_landmarks[0]:
            pose.append([round(lm.x, 4), round(lm.y, 4), round(lm.z, 4), round(lm.visibility, 3)])
    return {"frame": idx, "t": round(t, 4), "arkit": bs, "head_matrix": mtx, "pose": pose}

def main():
    inp, outp = sys.argv[1], sys.argv[2]
    is_video = os.path.splitext(inp)[1].lower() in VIDEO_EXT
    mode = vision.RunningMode.VIDEO if is_video else vision.RunningMode.IMAGE
    fl = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=FACE), running_mode=mode,
        output_face_blendshapes=True, output_facial_transformation_matrixes=True, num_faces=1))
    pl = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=POSE), running_mode=mode, num_poses=1))
    frames = []
    if is_video:
        cap = cv2.VideoCapture(inp); fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; i = 0
        while True:
            ok, frame = cap.read()
            if not ok: break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts = int(i / fps * 1000)
            frames.append(pack(i, ts / 1000.0, fl.detect_for_video(img, ts), pl.detect_for_video(img, ts)))
            i += 1
        cap.release(); meta = {"fps": fps, "source": inp, "n_frames": len(frames)}
    else:
        img = mp.Image.create_from_file(inp)
        frames.append(pack(0, 0.0, fl.detect(img), pl.detect(img)))
        meta = {"fps": 0, "source": inp, "n_frames": 1}
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    json.dump({"meta": meta, "frames": frames}, open(outp, "w"), indent=1)
    print("CAPTURE_OK frames=", len(frames), "->", outp)
    if frames and frames[0]["arkit"]:
        print("  top ARKit:", sorted(frames[0]["arkit"].items(), key=lambda x: -x[1])[:5])
        print("  n_pose_landmarks:", len(frames[0]["pose"]))

if __name__ == "__main__":
    main()
