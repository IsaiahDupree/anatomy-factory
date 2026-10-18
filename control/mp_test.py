import urllib.request, os, mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
M=r'C:\AnatomyFactory\models'; D=r'C:\AnatomyFactory\downloads'
os.makedirs(M,exist_ok=True)
face=os.path.join(M,'face_landmarker.task'); pose=os.path.join(M,'pose_landmarker_full.task'); img=os.path.join(D,'portrait.jpg')
urls={face:'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
      pose:'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task',
      img:'https://storage.googleapis.com/mediapipe-assets/portrait.jpg'}
for p,u in urls.items():
    if not os.path.exists(p): urllib.request.urlretrieve(u,p); print('downloaded',os.path.basename(p))
mpimg=mp.Image.create_from_file(img)
fl=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=face),
    output_face_blendshapes=True, output_facial_transformation_matrixes=True, num_faces=1))
r=fl.detect(mpimg)
print('FACES',len(r.face_landmarks),'LANDMARKS',len(r.face_landmarks[0]) if r.face_landmarks else 0)
if r.face_blendshapes:
    bs=r.face_blendshapes[0]; print('ARKIT_BLENDSHAPES',len(bs))
    for c in sorted(bs,key=lambda x:-x.score)[:6]: print(f'  {c.category_name}={c.score:.3f}')
pl=vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=pose), num_poses=1))
pr=pl.detect(mpimg)
print('POSES',len(pr.pose_landmarks),'BODY_LANDMARKS',len(pr.pose_landmarks[0]) if pr.pose_landmarks else 0)
print('MEDIAPIPE_OK')
