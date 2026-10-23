"""Real checkpoint loading/inference, blob contract and replay selection checks."""
from pathlib import Path
import hashlib,json,tempfile,subprocess,sys,os
import cv2,numpy as np,torch
from ultralytics import YOLO
R=Path(__file__).resolve().parent
torch.set_num_threads(2)
manifest=json.loads((R/'integrated_models.json').read_text())
for name,digest in manifest.items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==digest
capture=cv2.VideoCapture(str(R/'test_data/oak_h264_sample.h264'));ok,frame=capture.read();capture.release()
assert ok,'No sample frame'
for name,task in [('tyre_detector.pt','detect'),('tyre_segmenter.pt','segment')]:
 model=YOLO(R/name);assert model.task==task
 assert model.names=={0:'passenger',1:'4x4'},model.names
 result=model.predict(frame,imgsz=384,device='cpu',verbose=False)[0]
 assert result.boxes is not None
 print('PASS real checkpoint/inference',name,task,len(result.boxes))
import depthai as dai
from oak_rvc2 import validate_models
assert validate_models(dai,R/'rvc2_models')
with tempfile.TemporaryDirectory() as tmp:
 tmp=Path(tmp);video=tmp/'clip.mp4'
 writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),15,(480,270))
 for _ in range(3):writer.write(cv2.resize(frame,(480,270)))
 writer.release()
 for name in ('tyre_detector.pt','tyre_segmenter.pt'):
  out=tmp/name
  subprocess.run([sys.executable,str(R/'offline_replay.py'),'--video',str(video),'--model',str(R/name),'--output',str(out),'--mode','horizontal'],check=True,env={**os.environ,'OMP_NUM_THREADS':'2'})
  summary=json.loads((out/'test_summary.json').read_text())
  assert summary['frames']==3 and summary['production_totals_modified'] is False
  assert summary['mask_review']==('segmenter' in name)
  if 'segmenter' in name:
   points=json.loads((out/'point_comparison.json').read_text())
   assert points['shared_track_ids'] and points['shared_frames']
   assert 'horizontal' in points['results']
print('PASS both real replay modes, compiled OAK contract, model hashes and production isolation')
