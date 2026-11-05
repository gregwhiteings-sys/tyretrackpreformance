"""Detection-only dual OAK RVC2 adapter. No mask tensors or reconstruction.
Tyres: supplied verified 384 RGB detection blob. Foreign: 416 BGR YOLOv8 detector.
Host performs detection decoding and ByteTrack; device performs inference/encoding.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import cv2
from oak_ai import BLOB_SHA256,OakTracker,decode as decode_tyres
FRAME_SIZE=(480,270)

def validate_models(dai,root):
    root=Path(root)
    tyre=root.parent/'tyre_detector_oak.blob'
    if hashlib.sha256(tyre.read_bytes()).hexdigest()!=BLOB_SHA256:raise ValueError('Tyre detection blob integrity mismatch')
    blob=dai.OpenVINO.Blob(str(tyre))
    ins=list(blob.networkInputs.values());outs=list(blob.networkOutputs.values())
    if len(ins)!=1 or list(ins[0].dims)!=[384,384,3,1] or 'U8' not in str(ins[0].dataType):raise ValueError('Unexpected tyre input')
    if len(outs)!=1 or list(outs[0].dims)!=[3024,6,1]:raise ValueError('Tyre model must be detection only')
    hashes=json.loads((root/'sha256.json').read_text())
    for relative,digest in hashes.items():
        data=(root/relative).read_bytes()
        # Git on Windows may check text out with CRLF. JSON content must still
        # match the original export; compiled binary bytes stay strictly exact.
        if Path(relative).suffix.lower()=='.json':
            data=data.replace(b'\r\n',b'\n')
        if hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Foreign compiled integrity mismatch: '+relative)
    cfg=json.loads((root/'foreign/config.json').read_text())['model']
    blob=dai.OpenVINO.Blob(str(root/'foreign'/cfg['metadata']['path']))
    ins=list(blob.networkInputs.values())
    if len(ins)!=1 or list(ins[0].dims)!=[416,416,3,1] or 'U8' not in str(ins[0].dataType):raise ValueError('Unexpected foreign input')
    expected={o['name']:list(reversed(o['shape'])) for o in cfg['outputs']}
    if set(blob.networkOutputs)!=set(expected):raise ValueError('Foreign output mismatch')
    for name,dims in expected.items():
        if list(blob.networkOutputs[name].dims)!=dims:raise ValueError('Foreign tensor shape mismatch')
    return True

def build_pipeline(dai,root,recording=False,foreign_enabled=True):
    root=Path(root);validate_models(dai,root)
    p=dai.Pipeline();camera=p.create(dai.node.ColorCamera)
    camera.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    camera.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camera.setPreviewSize(*FRAME_SIZE);camera.setPreviewKeepAspectRatio(True)
    camera.setInterleaved(False);camera.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    camera.setFps(15);camera.setIspScale(1,3);camera.setVideoSize(640,360)
    def stream(name,out,size=4):
        node=p.create(dai.node.XLinkOut);node.setStreamName(name)
        node.input.setBlocking(False);node.input.setQueueSize(size);out.link(node.input)
    from oak_preview import live_output
    stream('live',live_output(camera),1)
    if recording:
        enc=p.create(dai.node.VideoEncoder)
        enc.setDefaultProfilePreset(15,dai.VideoEncoderProperties.Profile.H264_MAIN)
        enc.setBitrateKbps(1500);enc.setKeyframeFrequency(15);enc.setNumBFrames(0)
        enc.input.setBlocking(False);enc.input.setQueueSize(4)
        camera.video.link(enc.input);stream('recording',enc.bitstream,30)
    for kind in ('tyre','foreign') if foreign_enabled else ('tyre',):
        tyre=kind=='tyre';size=384 if tyre else 416
        manip=p.create(dai.node.ImageManip)
        manip.initialConfig.setResizeThumbnail(size,size)
        manip.initialConfig.setFrameType(dai.ImgFrame.Type.RGB888p if tyre else dai.ImgFrame.Type.BGR888p)
        manip.setMaxOutputFrameSize(size*size*3)
        manip.inputImage.setBlocking(False);manip.inputImage.setQueueSize(1)
        camera.preview.link(manip.inputImage)
        nn=p.create(dai.node.NeuralNetwork)
        nn.setBlobPath(str(root.parent/'tyre_detector_oak.blob' if tyre else root/'foreign/foreign_object.blob'))
        nn.setNumInferenceThreads(1);nn.input.setBlocking(False);nn.input.setQueueSize(1)
        manip.out.link(nn.input)
        stream('nn' if tyre else 'foreign_nn',nn.out,8)
        stream('rgb' if tyre else 'foreign_rgb',nn.passthrough,4)
    return p

def read_layers(packet,kind):
    if kind=='tyre':
        out=np.asarray(packet.getLayerFp16('output0'),dtype=np.float32)
        if out.size!=18144:raise ValueError('Malformed tyre detection tensor')
        return out
    out=np.asarray(packet.getLayerFp16('output0'),dtype=np.float32)
    if out.size!=5*3549:raise ValueError('Malformed foreign YOLOv8 output0 tensor')
    return {'output0':out.reshape(1,5,3549)}

def unletterbox(image,kind='tyre'):
    if kind=='tyre':
        if image.shape[:2]!=(384,384):raise ValueError('Unexpected tyre thumbnail')
        return cv2.cvtColor(cv2.resize(image[84:300],FRAME_SIZE),cv2.COLOR_RGB2BGR)
    if image.shape[:2]!=(416,416):raise ValueError('Unexpected foreign thumbnail')
    return cv2.resize(image[91:325],FRAME_SIZE)

def decode(raw,confidence=.1,iou=.5,agnostic=False):
    """Decode the one-class YOLOv8 [1,5,3549] RVC2 output."""
    if not isinstance(raw,dict):return decode_tyres(raw,confidence,iou,agnostic),None
    a=np.asarray(raw.get('output0'),dtype=np.float32)
    if a.shape not in ((1,5,3549),(5,3549)):
        raise ValueError(f'Unexpected foreign YOLOv8 output shape {a.shape}')
    a=a.reshape(5,3549);scores=a[4]
    valid=np.isfinite(a).all(0)&(scores>=confidence)&(scores<=1.001)&(a[2]>0)&(a[3]>0)
    boxes=[];kept_scores=[]
    for cx,cy,w,h,score in zip(a[0,valid],a[1,valid],a[2,valid],a[3,valid],scores[valid]):
        x1=max(0.,float(cx-w/2));x2=min(416.,float(cx+w/2))
        y1=max(91.,float(cy-h/2));y2=min(325.,float(cy+h/2))
        if x2<=x1 or y2<=y1:continue
        boxes.append([x1,y1,x2-x1,y2-y1]);kept_scores.append(float(score))
    if not boxes:return np.empty((0,6),np.float32),None
    indices=np.asarray(cv2.dnn.NMSBoxes(boxes,kept_scores,confidence,iou),dtype=int).reshape(-1)
    if not len(indices):return np.empty((0,6),np.float32),None
    chosen=np.asarray([[*boxes[i],kept_scores[i],0] for i in indices[:300]],dtype=np.float32)
    chosen[:,[0,2]]*=480/416;chosen[:,[1,3]]=(chosen[:,[1,3]]-91)*270/234
    chosen[:,2]+=chosen[:,0];chosen[:,3]+=chosen[:,1]
    return chosen,None
