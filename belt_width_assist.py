"""Experimental, dependency-free belt-relative size evidence. No model changes."""
from collections import deque
from dataclasses import dataclass
from math import isfinite
from statistics import median

@dataclass(frozen=True)
class BeltSettings:
    enabled: bool = True
    observe_only: bool = False
    width_mm: float = 1100.0  # ASSUMED, not measured at the site
    left_top: float = .44
    right_top: float = .61
    left_bottom: float = .215
    right_bottom: float = .775

    def valid(self):
        values=(self.width_mm,self.left_top,self.right_top,self.left_bottom,self.right_bottom)
        return (all(isfinite(v) for v in values) and 600 <= self.width_mm <= 2000
                and 0 <= self.left_top < self.right_top <= 1
                and 0 <= self.left_bottom < self.right_bottom <= 1)

class BeltWidthAssist:
    def __init__(self, settings=None):
        self.settings=settings or BeltSettings()
        self.samples={}

    def forget(self, track_id):
        self.samples.pop(track_id,None)

    def reset(self):
        self.samples.clear()

    def edges(self, y, width, height):
        c=self.settings;t=y/height
        return (width*(c.left_top+(c.left_bottom-c.left_top)*t),
                width*(c.right_top+(c.right_bottom-c.right_top)*t))

    def observe(self, track_id, box, boxes, width, height, frame, confident=True):
        c=self.settings
        if not c.enabled or not c.valid() or width <= 0 or height <= 0:
            self.forget(track_id);return
        x1,y1,x2,y2=map(float,box);bw=x2-x1;bh=y2-y1;cy=(y1+y2)/2
        if (not confident or not all(isfinite(v) for v in (x1,y1,x2,y2)) or bw<=0 or bh<=0
                or x1<=1 or y1<=1 or x2>=width-1 or y2>=height-1
                or not .35*height<=cy<=.75*height or not .45<=bh/bw<=.95):
            self.forget(track_id);return
        # Conservatively reject any significant intersecting/nested detection.
        for other_id, other in boxes:
            if other_id==track_id:continue
            a,b,d,e=map(float,other);area=(d-a)*(e-b)
            inter=max(0,min(x2,d)-max(x1,a))*max(0,min(y2,e)-max(y1,b))
            if area>0 and inter/min(bw*bh,area)>.03:
                self.forget(track_id);return
        left,right=self.edges(cy,width,height);span=right-left
        if span<=0 or x1<left or x2>right or not .35<=bw/span<=.88:
            self.forget(track_id);return
        values=self.samples.setdefault(track_id,deque(maxlen=12))
        if values and frame<=values[-1][0]:return
        if values and frame-values[-1][0]>5:values.clear()
        values.append((frame,bw/span*c.width_mm))

    def evidence(self, track_id, frame):
        values=self.samples.get(track_id)
        if not values or len(values)<5 or frame-values[-1][0]>5:return None
        mm=median(v for _,v in values)
        # Perspective/box fluctuations or changing pose: retain visual classifier.
        if (max(v for _,v in values)-min(v for _,v in values))/mm>.12:return None
        label='passenger' if 450<=mm<680 else '4x4' if 730<mm<=900 else None
        return {'diameter_mm':mm,'candidate':label,'observations':len(values),'assumed_width':True}

    def resolve(self, track_id, frame, visual_type, visual_score, ignore_observe=False):
        evidence=self.evidence(track_id,frame)
        if ((self.settings.observe_only and not ignore_observe) or not evidence or not evidence['candidate']
                or visual_type not in ('passenger','4x4') or visual_score>=.80):
            return visual_type,visual_score,False
        # A diameter estimate is not a calibrated class confidence. Keep original score.
        candidate=evidence['candidate']
        return candidate,visual_score,candidate!=visual_type
